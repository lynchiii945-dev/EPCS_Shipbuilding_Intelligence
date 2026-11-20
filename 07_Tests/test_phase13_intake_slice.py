# -*- coding: utf-8 -*-
"""统一资料入口薄切片与迁移运行器测试。只使用内存库和临时目录。"""
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "01_Data"))
sys.path.insert(0, str(REPO / "01_Data" / "scripts"))
sys.path.insert(0, str(REPO / "03_Application"))

import init_db
from epcs_intake.extract import propose
from epcs_intake.files import HashMismatch
from epcs_intake.readers import extract_pdf_text
from epcs_intake.service import AlreadyDecided, IntakeService, NotApproved
from migrations.connection import connect
from migrations.runner import (
    SchemaMismatchError,
    apply_statements,
    migrate,
    migrate_conn,
)
from migrations.schema_check import entity_table_names, fts_names
from migrations.slice_ddl import PARENT_ONLY_TABLES, STATEMENTS

REAL_DB = REPO / "01_Data" / "epcs_intelligence.db"
REAL_INBOX = REPO / "01_Data" / "intake" / "inbox"
SAMPLE = """# 铺缆船集控台说明

项目编号：CMHI-001
项目名称：铺缆船集控台改造

集控台是船舶机舱的集中控制位置。

问题：齿轮箱FAT推迟，需要关闭。
"""


def _inbox_names():
    if not REAL_INBOX.exists():
        return []
    return sorted(path.name for path in REAL_INBOX.iterdir())


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._db_existed = REAL_DB.exists()
        cls._inbox = _inbox_names()

    @classmethod
    def tearDownClass(cls):
        if REAL_DB.exists() != cls._db_existed:
            raise AssertionError("测试碰到了仓库里的 epcs_intelligence.db")
        if _inbox_names() != cls._inbox:
            raise AssertionError("测试往仓库入口写入了文件")

    def test_fresh_memory_then_skip(self):
        conn = connect(":memory:")
        first = migrate_conn(conn)
        self.assertEqual(first.status, "applied")
        self.assertEqual(len(first.fingerprint), 64)
        self.assertEqual(len(first.tables), 19)
        self.assertEqual(first.fts, ())
        applied = conn.execute("SELECT applied_at, ddl_fingerprint FROM schema_version").fetchone()
        conn.execute(
            "INSERT INTO organization (id, org_code, name, org_type, created_at)"
            " VALUES ('org-1','C','单位','COMPANY','t')"
        )
        second = migrate_conn(conn)
        self.assertEqual(second.status, "skipped")
        self.assertEqual(
            conn.execute("SELECT applied_at, ddl_fingerprint FROM schema_version").fetchone(),
            applied,
        )
        self.assertEqual(conn.execute("SELECT count(*) FROM organization").fetchone()[0], 1)
        conn.close()

    def test_altered_table_is_rejected(self):
        conn = connect(":memory:")
        migrate_conn(conn)
        fingerprint = conn.execute("SELECT ddl_fingerprint FROM schema_version").fetchone()[0]
        conn.execute("ALTER TABLE organization ADD COLUMN extra_note TEXT")
        with self.assertRaises(SchemaMismatchError):
            migrate_conn(conn)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(organization)")]
        self.assertIn("extra_note", cols)
        self.assertEqual(
            conn.execute("SELECT ddl_fingerprint FROM schema_version").fetchone()[0],
            fingerprint,
        )
        conn.close()

    def test_dropped_trigger_is_not_recreated(self):
        conn = connect(":memory:")
        migrate_conn(conn)
        conn.execute("DROP TRIGGER trg_er_immutable_d")
        with self.assertRaises(SchemaMismatchError):
            migrate_conn(conn)
        self.assertIsNone(
            conn.execute(
                "SELECT name FROM sqlite_master WHERE name='trg_er_immutable_d'"
            ).fetchone()
        )
        conn.close()

    def test_fingerprint_tamper_is_rejected(self):
        conn = connect(":memory:")
        migrate_conn(conn)
        conn.execute(
            "UPDATE schema_version SET ddl_fingerprint=? WHERE version=1",
            ("0" * 64,),
        )
        with self.assertRaises(SchemaMismatchError):
            migrate_conn(conn)
        self.assertEqual(
            conn.execute("SELECT ddl_fingerprint FROM schema_version").fetchone()[0],
            "0" * 64,
        )
        conn.close()

    def test_partial_schema_is_rejected(self):
        conn = connect(":memory:")
        conn.execute("CREATE TABLE project (id TEXT)")
        with self.assertRaises(SchemaMismatchError):
            migrate_conn(conn)
        self.assertEqual(entity_table_names(conn), ("project",))
        conn.close()

    def test_failed_migration_rolls_back(self):
        conn = connect(":memory:")
        with self.assertRaises(RuntimeError):
            apply_statements(
                conn,
                list(STATEMENTS) + ["SELECT * FROM table_that_does_not_exist"],
                version=1,
                description="boom",
            )
        self.assertEqual(entity_table_names(conn), ())
        self.assertEqual(
            conn.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0],
            0,
        )
        conn.close()

    def test_factory_turns_foreign_keys_on_and_wal_persists(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = str(Path(folder.name) / "slice.db")
        migrate(path)
        raw = sqlite3.connect(path)
        self.assertEqual(raw.execute("PRAGMA foreign_keys").fetchone()[0], 0)
        self.assertEqual(raw.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        raw.close()
        again = connect(path)
        self.assertEqual(again.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            again.execute(
                "INSERT INTO document_version (id, document_id, version_no, created_at)"
                " VALUES ('v','missing','1','t')"
            )
        again.close()

    def test_table_list_excludes_sqlite_catalog(self):
        conn = connect(":memory:")
        migrate_conn(conn)
        names = entity_table_names(conn)
        self.assertEqual(len(names), 19)
        self.assertNotIn("sqlite_schema", names)
        total = conn.execute(
            "SELECT count(*) FROM pragma_table_list WHERE type='table'"
        ).fetchone()[0]
        self.assertEqual(total, 21)
        catalog = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM pragma_table_list"
                " WHERE type='table' AND name LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        self.assertEqual(catalog, ["sqlite_schema", "sqlite_temp_schema"])
        self.assertEqual(fts_names(conn), ())
        conn.close()

    def test_uuid_check_coverage(self):
        conn = connect(":memory:")
        migrate_conn(conn)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO project (id, project_code, name, created_at)"
                " VALUES ('bad','P','船','t')"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO person (id, organization_id, name, created_at)"
                " VALUES ('bad','missing','人','t')"
            )
        conn.execute(
            "INSERT INTO document (id, name, created_at) VALUES ('not-a-uuid','说明','t')"
        )
        self.assertEqual(
            conn.execute("SELECT count(*) FROM document WHERE id='not-a-uuid'").fetchone()[0],
            1,
        )
        conn.close()

    def test_init_db_keeps_trigram_check(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = str(Path(folder.name) / "init.db")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertTrue(init_db.init(db_path=path))
        text = buf.getvalue()
        self.assertIn("集控台", text)
        self.assertIn("命中=1", text)
        self.assertNotIn("应为 0", text)
        self.assertIn("applied", text)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertTrue(init_db.init(db_path=path))
        self.assertIn("skipped", buf.getvalue())
        empty = str(Path(folder.name) / "empty.db")
        sqlite3.connect(empty).close()
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertTrue(init_db.check(db_path=empty))
        self.assertIn("尚未迁移", buf.getvalue())
        self.assertNotIn("应为 0", buf.getvalue())


class IntakeSliceTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.service = IntakeService(self.root)
        self.inbox = self.root / "01_Data" / "intake" / "inbox"

    def tearDown(self):
        self._tmpdir.cleanup()
        if REAL_DB.exists():
            raise AssertionError("测试创建了仓库数据库")

    def _reviewer(self):
        return self.service.register_reviewer("审核人", "船厂", "YARD-1")

    def _write(self, relative, text):
        path = self.inbox / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_rules_do_not_read_filename(self):
        found = propose("只是一段说明，没有编号。", readable=True)
        types = [item["candidate_type"] for item in found]
        self.assertNotIn("PROJECT_FACT", types)
        self.assertNotIn("KNOWLEDGE", types)
        pending = propose("", readable=False)
        self.assertEqual(pending[0]["candidate_type"], "PENDING_PARSE")
        self.assertEqual(pending[0]["confidence"], 0.0)
        self.assertFalse(pending[0]["payload"]["understood"])

    def test_pdf_flate_text_is_extracted(self):
        data = _pdf("CMHI-009")
        self.assertNotIn(b"CMHI-009", data)
        self.assertIn("CMHI-009", extract_pdf_text(data))

    def test_unapproved_paths_do_not_publish(self):
        self._write("note.md", SAMPLE)
        item = self.service.submit_inbox()[0]
        document_id = item["document_id"]
        for call in (
            lambda: self.service.archive_original(document_id),
            lambda: self.service.write_knowledge(document_id),
            lambda: self.service.confirm_project_fact(document_id),
        ):
            with self.assertRaises(NotApproved):
                call()
        self.assertEqual(_files(self.root / "01_Data" / "archive"), [])
        self.assertEqual(_files(self.root / "00_Vault" / "知识"), [])
        conn = self.service.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM project").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM knowledge_item").fetchone()[0], 0)
            natures = {
                row[0]
                for row in conn.execute("SELECT DISTINCT info_nature FROM extraction_result")
            }
            self.assertNotIn("CONFIRMED_FACT", natures)
            self.assertEqual(
                conn.execute("SELECT count(*) FROM review_decision").fetchone()[0], 0
            )
        finally:
            conn.close()

    def test_reject_does_not_archive_or_confirm(self):
        self._write("note.md", SAMPLE)
        document_id = self.service.submit_inbox()[0]["document_id"]
        reviewer = self._reviewer()
        self.service.reject(document_id, reviewer, "证据不足")
        self.assertEqual(_files(self.root / "01_Data" / "archive"), [])
        self.assertEqual(_files(self.root / "00_Vault" / "知识"), [])
        conn = self.service.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM project").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM knowledge_item").fetchone()[0], 0)
            decision = conn.execute("SELECT decision FROM review_decision").fetchone()[0]
            self.assertEqual(decision, "REJECT")
            self.assertNotIn(
                "CONFIRMED_FACT",
                [row[0] for row in conn.execute("SELECT info_nature FROM extraction_result")],
            )
        finally:
            conn.close()

    def test_approve_copies_source_and_records_fact(self):
        source = self._write("note.md", SAMPLE)
        before = source.read_bytes()
        document_id = self.service.submit_inbox()[0]["document_id"]
        reviewer = self._reviewer()
        result = self.service.approve(document_id, reviewer, "编号和名称都在原文里")
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue(source.is_file())
        archive = Path(result["archive_path"])
        self.assertEqual(archive.read_bytes(), before)
        self.assertIn("/archive/company/", result["archive_path"].replace("\\", "/"))
        note = Path(result["vault_path"]).read_text(encoding="utf-8")
        self.assertIn("file_id: %s" % document_id, note)
        self.assertIn("CMHI-001", note)
        self.assertIn("不把它们写入 issue", note)
        conn = self.service.connect()
        try:
            project = conn.execute(
                "SELECT id, project_code, info_nature FROM project"
            ).fetchone()
            self.assertEqual(project[1], "CMHI-001")
            self.assertEqual(project[2], "CONFIRMED_FACT")
            self.assertEqual(
                conn.execute("SELECT project_id FROM document WHERE id=?", (document_id,)).fetchone()[0],
                project[0],
            )
            refs = conn.execute(
                "SELECT source_id, traced_entity_type FROM source_reference"
            ).fetchall()
            self.assertTrue(refs)
            self.assertTrue(all(row[0] == document_id for row in refs))
            snapshot = conn.execute(
                "SELECT snapshot_json FROM knowledge_version"
            ).fetchone()[0]
            self.assertIn(document_id, snapshot)
            linked = conn.execute(
                "SELECT object_type, relation FROM review_result_object"
            ).fetchone()
            self.assertEqual(linked, ("KNOWLEDGE_ITEM", "CREATED"))
            for table in PARENT_ONLY_TABLES:
                count = conn.execute("SELECT count(*) FROM %s" % table).fetchone()[0]
                self.assertEqual(count, 0, table)
            self.assertEqual(
                [path.name for path in self.root.rglob("*.db")],
                ["epcs_intelligence.db"],
            )
        finally:
            conn.close()
        self.assertEqual(self.service.archive_original(document_id), result["archive_path"])
        with self.assertRaises(AlreadyDecided):
            self.service.approve(document_id, reviewer, "再次通过")
        self.assertEqual(len(_files(self.root / "01_Data" / "archive")), 1)

    def test_same_filename_does_not_merge_matters(self):
        self._write("a/spec.md", "项目编号：CMHI-001\n项目名称：甲船\n# 甲\n")
        self._write("b/spec.md", "项目编号：ASSO-77\n项目名称：乙船\n# 乙\n")
        items = self.service.submit_inbox()
        self.assertEqual(len(items), 2)
        self.assertEqual(len({item["document_id"] for item in items}), 2)
        self.assertEqual(len({item["batch_id"] for item in items}), 1)
        reviewer = self._reviewer()
        self.service.approve(items[0]["document_id"], reviewer, "只确认甲船")
        conn = self.service.connect()
        try:
            codes = [row[0] for row in conn.execute("SELECT project_code FROM project")]
        finally:
            conn.close()
        self.assertEqual(codes, ["CMHI-001"])

    def test_same_content_is_one_identity(self):
        body = "项目编号：DUP-10\n项目名称：重复船\n# 重复\n"
        self._write("one.md", body)
        self._write("nested/two.md", body)
        items = self.service.submit_inbox()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["document_id"], items[1]["document_id"])
        self.assertTrue(items[1]["duplicate"])
        conn = self.service.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM document").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM review_queue").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM ingestion_job").fetchone()[0], 2)
        finally:
            conn.close()

    def test_filename_is_not_project_code(self):
        self._write("CMHI-001.md", "只是一段说明，没有编号。\n")
        document_id = self.service.submit_inbox()[0]["document_id"]
        self.service.approve(document_id, self._reviewer(), "没有项目字段")
        conn = self.service.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM project").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM knowledge_item").fetchone()[0], 0)
        finally:
            conn.close()
        self.assertEqual(_files(self.root / "00_Vault" / "知识"), [])
        self.assertEqual(len(_files(self.root / "01_Data" / "archive")), 1)

    def test_hash_mismatch_blocks_formal_writes(self):
        self._write("note.md", SAMPLE)
        document_id = self.service.submit_inbox()[0]["document_id"]
        reviewer = self._reviewer()

        def corrupt(src, dest, *args, **kwargs):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"corrupt")

        original = __import__("epcs_intake.files", fromlist=["shutil"]).shutil.copy2
        try:
            __import__("epcs_intake.files", fromlist=["shutil"]).shutil.copy2 = corrupt
            with self.assertRaises(HashMismatch):
                self.service.approve(document_id, reviewer, "应该失败")
        finally:
            __import__("epcs_intake.files", fromlist=["shutil"]).shutil.copy2 = original
        self.assertEqual(_files(self.root / "01_Data" / "archive"), [])
        self.assertEqual(_files(self.root / "00_Vault" / "知识"), [])
        conn = self.service.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM project").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM review_decision").fetchone()[0], 0)
            status = conn.execute("SELECT status FROM review_queue").fetchone()[0]
            self.assertEqual(status, "PENDING")
        finally:
            conn.close()

    def test_unknown_reviewer_rolls_back_archive(self):
        source = self._write("note.md", SAMPLE)
        before = source.read_bytes()
        document_id = self.service.submit_inbox()[0]["document_id"]
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.approve(document_id, "0" * 32, "没有这个人")
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(_files(self.root / "01_Data" / "archive"), [])
        conn = self.service.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM project").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT status FROM review_queue").fetchone()[0], "PENDING")
        finally:
            conn.close()

    def test_unparsed_file_is_not_pretended_understood(self):
        path = self.inbox / "drawing.bin"
        path.write_bytes(b"\x00\x01not-text")
        item = self.service.submit_inbox()[0]
        conn = self.service.connect()
        try:
            row = conn.execute(
                "SELECT doc_type, extracted_text FROM document d"
                " JOIN document_version v ON v.document_id=d.id WHERE d.id=?",
                (item["document_id"],),
            ).fetchone()
            self.assertEqual(row[0], "UNPARSED")
            self.assertIsNone(row[1])
            kind = conn.execute("SELECT candidate_type, confidence FROM extraction_result").fetchone()
            self.assertEqual(kind, ("PENDING_PARSE", 0.0))
        finally:
            conn.close()
        self.service.approve(item["document_id"], self._reviewer(), "只收原件")
        self.assertEqual(len(_files(self.root / "01_Data" / "archive")), 1)
        self.assertEqual(_files(self.root / "00_Vault" / "知识"), [])
        conn = self.service.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM project").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM knowledge_item").fetchone()[0], 0)
        finally:
            conn.close()

    def test_personal_zone_and_pdf_inbox(self):
        self._write("mine.md", "个人笔记\n项目编号：OWN-1\n项目名称：自有船\n# 自有\n")
        pdf_path = self.inbox / "sheet.pdf"
        pdf_path.write_bytes(_pdf("CMHI-009"))
        items = {Path(item["path"]).name: item for item in self.service.submit_inbox()}
        reviewer = self._reviewer()
        personal = self.service.approve(items["mine.md"]["document_id"], reviewer, "个人资料")
        self.assertIn("/archive/personal/", personal["archive_path"].replace("\\", "/"))
        pdf_result = self.service.approve(items["sheet.pdf"]["document_id"], reviewer, "图纸文字")
        conn = self.service.connect()
        try:
            text = conn.execute(
                "SELECT extracted_text FROM document_version WHERE document_id=?",
                (items["sheet.pdf"]["document_id"],),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertIn("CMHI-009", text)
        self.assertTrue(pdf_result["archive_path"])

    def test_does_not_scan_outside_or_follow_symlink(self):
        secret = self.root / "secret.md"
        secret.write_text("项目编号：SECRET-999\n项目名称：机密\n# 机密\n", encoding="utf-8")
        outside = self.root / "outside.md"
        outside.write_text(SAMPLE, encoding="utf-8")
        (self.inbox / "link.md").symlink_to(secret)
        self._write("inside.md", "舱内记录\n")
        items = self.service.submit_inbox()
        self.assertEqual([Path(item["path"]).name for item in items], ["inside.md"])
        conn = self.service.connect()
        try:
            blob = " ".join(
                row[0] or ""
                for row in conn.execute(
                    "SELECT extracted_text FROM document_version"
                )
            )
        finally:
            conn.close()
        self.assertNotIn("SECRET-999", blob)
        self.assertNotIn("铺缆船", blob)

    def test_code_stays_inside_repo_paths(self):
        for path in (REPO / "03_Application" / "epcs_intake").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("epcs_kb", text)
            self.assertNotIn("src/aipm", text)
            self.assertNotIn("个人知识库", text)

    def test_command_line_submit_and_approve(self):
        self._write("note.md", SAMPLE)
        script = REPO / "01_Data" / "scripts" / "intake_slice.py"
        reviewer = _run(script, self.root, [
            "reviewer", "--name", "审核人", "--org-name", "船厂", "--org-code", "YARD-1",
        ])
        submitted = _run(script, self.root, ["submit"])
        approved = _run(script, self.root, [
            "approve",
            "--document", submitted[0]["document_id"],
            "--reviewer", reviewer["person_id"],
            "--reason", "命令行通过",
        ])
        self.assertTrue(Path(approved["archive_path"]).is_file())
        self.assertIn(submitted[0]["document_id"], Path(approved["vault_path"]).read_text(encoding="utf-8"))

    def test_extraction_original_cannot_be_overwritten(self):
        self._write("note.md", SAMPLE)
        document_id = self.service.submit_inbox()[0]["document_id"]
        conn = self.service.connect()
        try:
            with self.assertRaises(sqlite3.IntegrityError) as caught:
                conn.execute(
                    "UPDATE extraction_result SET raw_text='hack'"
                    " WHERE raw_text LIKE '%CMHI-001%'"
                )
            self.assertIn("immutable", str(caught.exception))
            stored = conn.execute(
                "SELECT raw_text FROM extraction_result WHERE raw_text LIKE '%CMHI-001%'"
            ).fetchone()[0]
            self.assertIn("CMHI-001", stored)
            self.assertNotEqual(document_id, "")
        finally:
            conn.close()


def _files(root):
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file() and path.name != ".gitkeep"]


def _run(script, root, args):
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(root)] + args,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def _pdf(ascii_text):
    stream = b"BT /F1 12 Tf 72 100 Td (" + ascii_text.encode("ascii") + b") Tj ET"
    compressed = zlib.compress(stream)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144]"
        b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        (b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(compressed))
        + compressed
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += ("%d 0 obj\n" % index).encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += ("xref\n0 %d\n" % (len(objects) + 1)).encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += ("%010d 00000 n \n" % offset).encode("ascii")
    out += (
        "trailer << /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref)
    ).encode("ascii")
    return bytes(out)


if __name__ == "__main__":
    unittest.main()
