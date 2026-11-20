# -*- coding: utf-8 -*-
"""统一入口薄切片。

登记 → 阅读 → 规则建议 → 人工审核。未通过审核时，不归档、不写知识库、
不把项目事实标成已确认。审核通过后才复制原件、写 00_Vault，并在同一个
EPCS 库里记下带原始资料 ID 的正式记录。
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from migrations.connection import connect
from migrations.runner import migrate_conn

from epcs_intake.extract import propose
from epcs_intake.files import HashMismatch, copy_and_verify, is_inside, safe_filename, sha256_file
from epcs_intake.readers import read_bytes


class IntakeError(Exception):
    pass


class NotApproved(IntakeError):
    pass


class AlreadyDecided(IntakeError):
    pass


class Layout(object):
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.inbox = self.root / "01_Data" / "intake" / "inbox"
        self.archive_company = self.root / "01_Data" / "archive" / "company"
        self.archive_personal = self.root / "01_Data" / "archive" / "personal"
        self.vault_knowledge = self.root / "00_Vault" / "知识"
        self.database = self.root / "01_Data" / "epcs_intelligence.db"

    def ensure_dirs(self):
        for path in (
            self.inbox,
            self.archive_company,
            self.archive_personal,
            self.vault_knowledge,
        ):
            path.mkdir(parents=True, exist_ok=True)


def new_id():
    return uuid.uuid4().hex


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dumps(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class IntakeService(object):
    def __init__(self, root):
        self.layout = Layout(root)
        self.layout.ensure_dirs()

    def connect(self):
        conn = connect(str(self.layout.database))
        migrate_conn(conn)
        return conn

    def register_reviewer(self, name, org_name, org_code):
        conn = self.connect()
        try:
            conn.execute("BEGIN")
            try:
                row = conn.execute(
                    "SELECT id FROM organization WHERE org_code=?",
                    (org_code,),
                ).fetchone()
                if row:
                    org_id = row[0]
                else:
                    org_id = new_id()
                    conn.execute(
                        "INSERT INTO organization"
                        " (id, org_code, name, org_type, created_at)"
                        " VALUES (?,?,?,?,?)",
                        (org_id, org_code, org_name, "COMPANY", utcnow()),
                    )
                person_id = new_id()
                conn.execute(
                    "INSERT INTO person (id, organization_id, name, created_at)"
                    " VALUES (?,?,?,?)",
                    (person_id, org_id, name, utcnow()),
                )
                conn.execute("COMMIT")
                return person_id
            except Exception:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

    def submit_inbox(self):
        batch_id = new_id()
        results = []
        for path in self._inbox_files():
            results.append(self._register_file(path, batch_id))
        return results

    def approve(self, document_id, reviewer_person_id, reason, zone=None):
        if not reason or not str(reason).strip():
            raise IntakeError("审核必须写明理由")
        conn = self.connect()
        archive_path = None
        vault_path = None
        committed = False
        try:
            plan = self._load_plan(conn, document_id)
            if zone is None:
                zone = plan["zone"]
            if zone not in ("company", "personal"):
                raise IntakeError("归档分区只能是 company 或 personal")
            source = Path(plan["source_path"])
            if not is_inside(source, self.layout.inbox) or not source.is_file():
                raise IntakeError("来源文件必须仍在统一入口内，且不能被移动")
            before = source.read_bytes()
            dest_root = (
                self.layout.archive_personal if zone == "personal"
                else self.layout.archive_company
            )
            dest = dest_root / document_id / safe_filename(source.name)
            archive_path = copy_and_verify(source, dest, plan["sha256"])
            if source.read_bytes() != before:
                raise IntakeError("归档过程中来源文件被改动，已中止")
            conn.execute("BEGIN")
            try:
                project_id = self._confirm_project(conn, plan)
                note = self._render_note(plan, archive_path, project_id)
                knowledge_id = None
                if note:
                    vault_path = self.layout.vault_knowledge / (document_id + ".md")
                    knowledge_id = self._write_knowledge_rows(
                        conn, plan, project_id, note, vault_path, archive_path
                    )
                    vault_path.parent.mkdir(parents=True, exist_ok=True)
                    vault_path.write_text(note, encoding="utf-8")
                evidence_id = self._source_row(
                    conn,
                    project_id=project_id,
                    traced_type="DOCUMENT",
                    traced_id=document_id,
                    source_id=document_id,
                    locator=str(source),
                    excerpt=(plan["text"] or plan["note"] or "")[:180],
                    confidence=None,
                )
                if knowledge_id:
                    self._source_row(
                        conn,
                        project_id=project_id,
                        traced_type="KNOWLEDGE_ITEM",
                        traced_id=knowledge_id,
                        source_id=document_id,
                        locator="line:1",
                        excerpt=plan["title"],
                        confidence=0.6,
                    )
                decision_id = new_id()
                conn.execute(
                    "INSERT INTO review_decision"
                    " (id, review_queue_id, decision, reviewer_person_id, reviewed_at,"
                    "  reason, evidence_source_reference_id, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        decision_id, plan["queue_id"], "ACCEPT_AS_NEW",
                        reviewer_person_id, utcnow(), reason.strip(),
                        evidence_id, utcnow(),
                    ),
                )
                if knowledge_id:
                    conn.execute(
                        "INSERT INTO review_result_object"
                        " (id, review_decision_id, object_type, object_id, relation, created_at)"
                        " VALUES (?,?,?,?,?,?)",
                        (new_id(), decision_id, "KNOWLEDGE_ITEM", knowledge_id, "CREATED", utcnow()),
                    )
                self._finish(conn, plan, "ACCEPTED", "DONE", archive_path, project_id)
                conn.execute("COMMIT")
                committed = True
            except Exception:
                conn.execute("ROLLBACK")
                raise
            return {
                "document_id": document_id,
                "project_id": project_id,
                "archive_path": str(archive_path),
                "vault_path": str(vault_path) if vault_path else "",
                "zone": zone,
            }
        except Exception:
            if not committed:
                _unlink(archive_path)
                _unlink(vault_path)
            raise
        finally:
            conn.close()

    def reject(self, document_id, reviewer_person_id, reason):
        if not reason or not str(reason).strip():
            raise IntakeError("驳回必须写明理由")
        conn = self.connect()
        try:
            plan = self._load_plan(conn, document_id)
            conn.execute("BEGIN")
            try:
                evidence_id = self._source_row(
                    conn,
                    project_id=None,
                    traced_type="DOCUMENT",
                    traced_id=document_id,
                    source_id=document_id,
                    locator=plan["source_path"],
                    excerpt="驳回所依据的原始资料，不是已确认项目事实",
                    confidence=None,
                )
                conn.execute(
                    "INSERT INTO review_decision"
                    " (id, review_queue_id, decision, reviewer_person_id, reviewed_at,"
                    "  reason, evidence_source_reference_id, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        new_id(), plan["queue_id"], "REJECT", reviewer_person_id,
                        utcnow(), reason.strip(), evidence_id, utcnow(),
                    ),
                )
                self._finish(conn, plan, "REJECTED", "DONE", None, None)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

    def archive_original(self, document_id):
        """没有已通过的审核时拒绝。通过之后只返回已有副本，不另做一次复制。"""
        conn = self.connect()
        try:
            self._require_accept(conn, document_id)
            return self._existing_archive(document_id)
        finally:
            conn.close()

    def write_knowledge(self, document_id):
        conn = self.connect()
        try:
            self._require_accept(conn, document_id)
            path = self.layout.vault_knowledge / (document_id + ".md")
            if not path.is_file():
                raise IntakeError("审核已通过，但这份资料没有知识笔记")
            return str(path)
        finally:
            conn.close()

    def confirm_project_fact(self, document_id):
        conn = self.connect()
        try:
            self._require_accept(conn, document_id)
            row = conn.execute(
                "SELECT project_id FROM document WHERE id=?",
                (document_id,),
            ).fetchone()
            if not row or not row[0]:
                raise IntakeError("这份资料没有已确认的项目事实")
            fact = conn.execute(
                "SELECT id, project_code, name, info_nature FROM project WHERE id=?",
                (row[0],),
            ).fetchone()
            return {
                "project_id": fact[0],
                "project_code": fact[1],
                "name": fact[2],
                "info_nature": fact[3],
            }
        finally:
            conn.close()

    def _require_accept(self, conn, document_id):
        if not self._decision_id(conn, document_id, "ACCEPT_AS_NEW"):
            raise NotApproved("未审核通过，不能归档、不能写知识、也不能确认项目事实")

    def _decision_id(self, conn, document_id, decision):
        return conn.execute(
            "SELECT d.id FROM review_decision d"
            " JOIN review_queue q ON q.id=d.review_queue_id"
            " JOIN review_extraction_link l ON l.review_queue_id=q.id"
            " JOIN extraction_result e ON e.id=l.extraction_result_id"
            " JOIN ingestion_job j ON j.id=e.ingestion_job_id"
            " WHERE j.source_type='DOCUMENT' AND j.source_id=? AND d.decision=?"
            "   AND d.is_deleted=0 LIMIT 1",
            (document_id, decision),
        ).fetchone()

    def _inbox_files(self):
        inbox = self.layout.inbox
        found = []
        for dirpath, dirnames, filenames in os.walk(inbox, followlinks=False):
            dirnames[:] = [name for name in dirnames if name != ".git"]
            for name in filenames:
                if name == ".gitkeep":
                    continue
                path = Path(dirpath) / name
                if path.is_symlink() or not is_inside(path, inbox):
                    continue
                if path.is_file():
                    found.append(path)
        found.sort(key=lambda item: str(item.relative_to(inbox)))
        return found

    def _register_file(self, path, batch_id):
        digest = sha256_file(path)
        data = path.read_bytes()
        if sha256_file(path) != digest:
            raise IntakeError("读取期间文件内容发生变化")
        read = read_bytes(data, path.suffix)
        readable = read.kind != "UNPARSED"
        conn = self.connect()
        try:
            conn.execute("BEGIN")
            try:
                existing = conn.execute(
                    "SELECT id FROM document WHERE sha256=? AND is_deleted=0",
                    (digest,),
                ).fetchone()
                relative = str(path.relative_to(self.layout.inbox))
                if existing:
                    document_id = existing[0]
                    conn.execute(
                        "INSERT INTO ingestion_job"
                        " (id, source_type, source_id, channel, status, started_at,"
                        "  finished_at, run_meta, re_runnable, created_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            new_id(), "DOCUMENT", document_id, "INTAKE", "DUPLICATE",
                            utcnow(), utcnow(),
                            dumps({
                                "batch_id": batch_id,
                                "source_path": str(path),
                                "relative_path": relative,
                                "content_sha256": digest,
                                "duplicate_of": document_id,
                            }),
                            0, utcnow(),
                        ),
                    )
                    conn.execute("COMMIT")
                    return {
                        "document_id": document_id,
                        "created": False,
                        "duplicate": True,
                        "batch_id": batch_id,
                        "sha256": digest,
                        "status": "DUPLICATE",
                        "path": str(path),
                    }
                document_id = new_id()
                job_id = new_id()
                queue_id = new_id()
                status = "PENDING_REVIEW" if readable else "PENDING_PARSE"
                suggestions = propose(read.text, readable=readable)
                summary = _summary(suggestions, path.name)
                snapshot = {
                    "file_id": document_id,
                    "batch_id": batch_id,
                    "source_path": str(path),
                    "relative_path": relative,
                    "read_status": "READ" if readable else "PENDING_PARSE",
                    "archive_path": None,
                }
                now = utcnow()
                conn.execute(
                    "INSERT INTO document"
                    " (id, name, doc_type, sha256, info_nature, created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (document_id, path.name, read.kind, digest, "SOURCE_FACT", now),
                )
                conn.execute(
                    "INSERT INTO document_version"
                    " (id, document_id, version_no, file_path, sha256, extracted_text,"
                    "  notes, snapshot_json, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        new_id(), document_id, "1", str(path), digest,
                        read.text if readable else None,
                        read.note or None,
                        dumps(snapshot), now,
                    ),
                )
                conn.execute(
                    "INSERT INTO ingestion_job"
                    " (id, source_type, source_id, channel, status, started_at, run_meta, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        job_id, "DOCUMENT", document_id, "INTAKE", status, now,
                        dumps({
                            "batch_id": batch_id,
                            "source_path": str(path),
                            "relative_path": relative,
                            "content_sha256": digest,
                            "read_status": snapshot["read_status"],
                        }),
                        now,
                    ),
                )
                conn.execute(
                    "INSERT INTO review_queue"
                    " (id, review_type, status, candidate_summary, info_nature, created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (queue_id, "INTAKE", "PENDING", summary, "PROPOSAL", now),
                )
                for item in suggestions:
                    extraction_id = new_id()
                    conn.execute(
                        "INSERT INTO extraction_result"
                        " (id, ingestion_job_id, candidate_type, candidate_json, raw_text,"
                        "  info_nature, confidence, status, created_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            extraction_id, job_id, item["candidate_type"],
                            dumps(item["payload"]), item["raw_text"],
                            item["info_nature"], item["confidence"], "PENDING", now,
                        ),
                    )
                    conn.execute(
                        "INSERT INTO review_extraction_link"
                        " (id, review_queue_id, extraction_result_id, created_at)"
                        " VALUES (?,?,?,?)",
                        (new_id(), queue_id, extraction_id, now),
                    )
                conn.execute("COMMIT")
                return {
                    "document_id": document_id,
                    "created": True,
                    "duplicate": False,
                    "batch_id": batch_id,
                    "sha256": digest,
                    "status": status,
                    "path": str(path),
                }
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

    def _load_plan(self, conn, document_id):
        if self._decision_id(conn, document_id, "ACCEPT_AS_NEW") or self._decision_id(
            conn, document_id, "REJECT"
        ) or self._decision_id(conn, document_id, "MERGE_TO"):
            raise AlreadyDecided("这份资料已经有审核决定")
        doc = conn.execute(
            "SELECT id, name, sha256, doc_type FROM document WHERE id=? AND is_deleted=0",
            (document_id,),
        ).fetchone()
        if not doc:
            raise IntakeError("资料不存在")
        version = conn.execute(
            "SELECT id, file_path, extracted_text, notes, snapshot_json"
            " FROM document_version WHERE document_id=? AND version_no='1'",
            (document_id,),
        ).fetchone()
        job = conn.execute(
            "SELECT id, status FROM ingestion_job"
            " WHERE source_type='DOCUMENT' AND source_id=?"
            "   AND status IN ('PENDING_REVIEW','PENDING_PARSE')"
            " ORDER BY created_at LIMIT 1",
            (document_id,),
        ).fetchone()
        if not job:
            raise IntakeError("没有待审核的投递")
        queue = conn.execute(
            "SELECT DISTINCT q.id FROM review_queue q"
            " JOIN review_extraction_link l ON l.review_queue_id=q.id"
            " JOIN extraction_result e ON e.id=l.extraction_result_id"
            " WHERE e.ingestion_job_id=? AND q.status='PENDING'",
            (job[0],),
        ).fetchone()
        if not queue:
            raise IntakeError("没有待审核队列")
        rows = conn.execute(
            "SELECT candidate_type, candidate_json, raw_text, confidence"
            " FROM extraction_result WHERE ingestion_job_id=? ORDER BY created_at, id",
            (job[0],),
        ).fetchall()
        parsed = []
        for row in rows:
            parsed.append({
                "candidate_type": row[0],
                "payload": json.loads(row[1] or "{}"),
                "raw_text": row[2],
                "confidence": row[3],
            })
        zone = "company"
        project = None
        knowledge = []
        matters = []
        for item in parsed:
            payload = item["payload"]
            if item["candidate_type"] == "CLASSIFICATION":
                zone = payload.get("zone") or "company"
            elif item["candidate_type"] == "PROJECT_FACT" and payload.get("eligible"):
                project = payload
            elif item["candidate_type"] == "KNOWLEDGE":
                knowledge.append(payload)
            elif item["candidate_type"] == "BUSINESS_MATTER":
                matters.append(payload)
        title = knowledge[0]["title"] if knowledge else doc[1]
        return {
            "document_id": doc[0],
            "filename": doc[1],
            "sha256": doc[2],
            "doc_type": doc[3],
            "version_id": version[0],
            "source_path": version[1],
            "text": version[2] or "",
            "note": version[3] or "",
            "snapshot": json.loads(version[4] or "{}"),
            "job_id": job[0],
            "queue_id": queue[0],
            "zone": zone,
            "project": project,
            "knowledge": knowledge,
            "matters": matters,
            "title": title,
            "suggestions": parsed,
        }

    def _confirm_project(self, conn, plan):
        project = plan["project"]
        if not project:
            return None
        code = project.get("project_code")
        name = project.get("name")
        if not code or not name:
            return None
        found = conn.execute(
            "SELECT id FROM project WHERE project_code=? AND is_deleted=0",
            (code,),
        ).fetchone()
        if found:
            project_id = found[0]
        else:
            project_id = new_id()
            conn.execute(
                "INSERT INTO project (id, project_code, name, info_nature, created_at)"
                " VALUES (?,?,?,?,?)",
                (project_id, code, name, "CONFIRMED_FACT", utcnow()),
            )
        conn.execute(
            "UPDATE document SET project_id=?, updated_at=? WHERE id=?",
            (project_id, utcnow(), plan["document_id"]),
        )
        return project_id

    def _write_knowledge_rows(self, conn, plan, project_id, note, vault_path, archive_path):
        knowledge_id = new_id()
        now = utcnow()
        summary = ""
        if plan["knowledge"]:
            summary = plan["knowledge"][0].get("summary") or ""
        elif plan["project"]:
            summary = plan["project"].get("name") or ""
        conn.execute(
            "INSERT INTO knowledge_item"
            " (id, project_id, ref_no, title, summary, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (
                knowledge_id, project_id, "KN-" + plan["document_id"],
                plan["title"], summary[:240], now,
            ),
        )
        snapshot = {
            "file_id": plan["document_id"],
            "content_sha256": plan["sha256"],
            "source_path": plan["source_path"],
            "archive_path": str(archive_path),
            "vault_path": str(vault_path),
        }
        encoded = note.encode("utf-8")
        conn.execute(
            "INSERT INTO knowledge_version"
            " (id, knowledge_item_id, version_no, content_md, sha256, snapshot_json, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                new_id(), knowledge_id, "1", note,
                hashlib.sha256(encoded).hexdigest(),
                dumps(snapshot), now,
            ),
        )
        return knowledge_id

    def _source_row(self, conn, *, project_id, traced_type, traced_id, source_id,
                    locator, excerpt, confidence):
        row_id = new_id()
        conn.execute(
            "INSERT INTO source_reference"
            " (id, project_id, traced_entity_type, traced_entity_id, source_type,"
            "  source_id, context_excerpt, locator, info_nature, confidence, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                row_id, project_id, traced_type, traced_id, "DOCUMENT", source_id,
                excerpt, locator, "SOURCE_FACT", confidence, utcnow(),
            ),
        )
        return row_id

    def _finish(self, conn, plan, extraction_status, job_status, archive_path, project_id):
        now = utcnow()
        conn.execute(
            "UPDATE extraction_result SET status=? WHERE ingestion_job_id=?",
            (extraction_status, plan["job_id"]),
        )
        conn.execute(
            "UPDATE review_queue SET status='DONE', updated_at=? WHERE id=?",
            (now, plan["queue_id"]),
        )
        conn.execute(
            "UPDATE ingestion_job SET status=?, finished_at=? WHERE id=?",
            (job_status, now, plan["job_id"]),
        )
        snapshot = dict(plan["snapshot"])
        snapshot["archive_path"] = str(archive_path) if archive_path else None
        snapshot["project_id"] = project_id
        snapshot["file_id"] = plan["document_id"]
        conn.execute(
            "UPDATE document_version SET snapshot_json=?, updated_at=? WHERE id=?",
            (dumps(snapshot), now, plan["version_id"]),
        )

    def _render_note(self, plan, archive_path, project_id):
        if not (plan["knowledge"] or plan["matters"] or plan["project"]):
            return ""
        lines = [
            "---",
            "file_id: %s" % plan["document_id"],
            "content_sha256: %s" % plan["sha256"],
            "source_path: %s" % plan["source_path"],
            "archive_path: %s" % archive_path,
            "project_id: %s" % (project_id or ""),
            "---",
            "",
            "# %s" % plan["title"],
            "",
            "来源资料：`%s`" % plan["document_id"],
            "",
        ]
        if plan["project"] and project_id:
            lines.extend([
                "## 已确认项目事实",
                "项目编号：%s" % plan["project"]["project_code"],
                "项目名称：%s" % plan["project"]["name"],
                "",
            ])
        else:
            lines.extend(["## 已确认项目事实", "无。", ""])
        if plan["knowledge"]:
            lines.append("## 知识")
            for item in plan["knowledge"]:
                lines.append("### %s" % item["title"])
                if item.get("summary"):
                    lines.append(item["summary"])
                lines.append("")
        if plan["matters"]:
            lines.extend([
                "## 业务事项建议",
                "这些是已审核的规则建议。本切片不把它们写入 issue、risk 或 task 表。",
            ])
            for item in plan["matters"]:
                lines.append("- %s：%s（%s）" % (item["kind"], item["text"], item["locator"]))
            lines.append("")
        if plan["text"]:
            lines.extend(["## 标准化文本", "", plan["text"], ""])
        return "\n".join(lines)

    def _existing_archive(self, document_id):
        for root in (self.layout.archive_company, self.layout.archive_personal):
            folder = root / document_id
            if not folder.is_dir():
                continue
            files = [path for path in folder.iterdir() if path.is_file()]
            if files:
                return str(files[0])
        raise IntakeError("审核已通过，但没有找到归档副本")


def _summary(suggestions, filename):
    for item in suggestions:
        payload = item["payload"]
        if item["candidate_type"] == "PROJECT_FACT" and payload.get("project_code"):
            return "项目事实建议 %s" % payload["project_code"]
        if item["candidate_type"] == "PENDING_PARSE":
            return "待解析 " + filename
    return filename


def _unlink(path):
    if path is None:
        return
    target = Path(path)
    if target.is_file():
        target.unlink()
