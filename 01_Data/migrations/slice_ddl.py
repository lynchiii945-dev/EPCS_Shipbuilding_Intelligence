# -*- coding: utf-8 -*-
"""本切片实际使用的 DDL，语句文本来自 R2 真值源对应 CREATE。

不改字段与约束。未纳入域 1 里本切片不写的表，也不生成 FTS 虚表。
entity / department / business_subject / ai_analysis_run 只因 SQLite
在外键列为 NULL 时仍要求父表存在而创建，流水线不向它们写入业务行。
"""
import re

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT,
    ddl_fingerprint TEXT,            -- 结构一致性校验用（§10）
    CHECK(length(ddl_fingerprint)=64 OR ddl_fingerprint IS NULL));""",
    """CREATE TABLE IF NOT EXISTS entity (                       -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL, entity_kind TEXT NOT NULL,
    canonical_source_id TEXT REFERENCES entity(id),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','MERGED','SUPERSEDED')),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, created_by TEXT, updated_by TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT,
    del_status TEXT NOT NULL DEFAULT 'ACTIVE', CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*'));""",
    """CREATE TABLE IF NOT EXISTS project (                      -- 基线A
    id TEXT PRIMARY KEY, project_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    main_object_entity_id TEXT REFERENCES entity(id),     -- R1-6 整改：真正 FK
    contract_summary TEXT, status TEXT NOT NULL DEFAULT 'ACTIVE',
    started_at TEXT, planned_end_at TEXT, ended_at TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, created_by TEXT, updated_by TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*'));""",
    """CREATE TABLE IF NOT EXISTS organization (                -- 基线A
    id TEXT PRIMARY KEY, org_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    org_type TEXT NOT NULL, parent_id TEXT REFERENCES organization(id),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE TABLE IF NOT EXISTS department (                  -- 基线A
    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES organization(id),
    code TEXT NOT NULL, name TEXT NOT NULL,
    parent_id TEXT REFERENCES department(id),            -- 部门内部层级
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(organization_id, code));""",
    """CREATE TABLE IF NOT EXISTS person (                      -- 基线A
    -- R2-B4（QA 阶段 B 补强核验 S5-2）：人员 ID 锚点必须带 UUID CHECK，
    -- 否则「所有审计责任人字段一律为 person.id 的 32 位小写 hex UUID」在数据库层无落点。
    id TEXT PRIMARY KEY CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*'),
    organization_id TEXT NOT NULL REFERENCES organization(id),
    department_id TEXT REFERENCES department(id), name TEXT NOT NULL, email TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE INDEX IF NOT EXISTS idx_person_org ON person(organization_id);""",
    """CREATE INDEX IF NOT EXISTS idx_person_dept ON person(department_id);""",
    """CREATE TABLE IF NOT EXISTS document (                    -- 基线A，主表元数据
    id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL, doc_code TEXT, doc_type TEXT,
    is_readonly INTEGER NOT NULL DEFAULT 1, sha256 TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_sha ON document(sha256) WHERE sha256 IS NOT NULL;""",
    """CREATE TABLE IF NOT EXISTS document_version (            -- 基线A，版本内容（全部历史入 FTS）
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES document(id),
    version_no TEXT NOT NULL, file_path TEXT, sha256 TEXT,
    extracted_text TEXT, notes TEXT, snapshot_json TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(document_id, version_no));""",
    """CREATE TABLE IF NOT EXISTS source_reference (            -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT,
    traced_entity_type TEXT NOT NULL, traced_entity_id TEXT NOT NULL,
    source_type TEXT NOT NULL, source_id TEXT NOT NULL,
    context_excerpt TEXT, locator TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT', confidence REAL,
    source_time TEXT,
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE INDEX IF NOT EXISTS idx_sr_entity ON source_reference(traced_entity_type, traced_entity_id);""",
    """CREATE INDEX IF NOT EXISTS idx_sr_source ON source_reference(source_type, source_id);""",
    """CREATE TABLE IF NOT EXISTS business_subject (            -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    subject_kind TEXT NOT NULL CHECK(subject_kind IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM')),
    canonical_subject_id TEXT REFERENCES business_subject(id),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','MERGED','SUPERSEDED')),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE INDEX IF NOT EXISTS idx_bs_canonical ON business_subject(canonical_subject_id);""",
    """CREATE TABLE IF NOT EXISTS knowledge_item (              -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, subject_id TEXT REFERENCES business_subject(id),
    ref_no TEXT UNIQUE, title TEXT NOT NULL, summary TEXT,
    status TEXT NOT NULL DEFAULT 'PUBLISHED',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE TABLE IF NOT EXISTS knowledge_version (           -- 基线A，全部历史入 FTS
    id TEXT PRIMARY KEY, knowledge_item_id TEXT NOT NULL REFERENCES knowledge_item(id),
    version_no TEXT NOT NULL, content_md TEXT, sha256 TEXT, snapshot_json TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(knowledge_item_id, version_no));""",
    """CREATE TABLE IF NOT EXISTS ingestion_job (               -- 基线B
    id TEXT PRIMARY KEY, project_id TEXT, source_type TEXT NOT NULL, source_id TEXT, channel TEXT,
    status TEXT NOT NULL DEFAULT 'INGESTING', started_at TEXT, finished_at TEXT,
    run_meta TEXT, re_runnable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);""",
    """CREATE TABLE IF NOT EXISTS ai_analysis_run (             -- 基线B
    id TEXT PRIMARY KEY, project_id TEXT, run_type TEXT NOT NULL, model TEXT, input_ref TEXT,
    output_summary TEXT, status TEXT NOT NULL DEFAULT 'RUNNING', started_at TEXT, finished_at TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);""",
    """CREATE TABLE IF NOT EXISTS extraction_result (           -- 基线B，原始内容冻结
    id TEXT PRIMARY KEY, ingestion_job_id TEXT REFERENCES ingestion_job(id),
    ai_analysis_run_id TEXT REFERENCES ai_analysis_run(id),
    candidate_type TEXT NOT NULL, candidate_json TEXT, raw_text TEXT,
    info_nature TEXT NOT NULL DEFAULT 'AI_INFERENCE'
        CHECK(info_nature IN ('AI_INFERENCE','PREDICTION','PROPOSAL')),
    confidence REAL, status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);""",
    """CREATE TRIGGER IF NOT EXISTS trg_er_immutable_u BEFORE UPDATE ON extraction_result
WHEN OLD.candidate_json IS NOT NEW.candidate_json OR OLD.raw_text IS NOT NEW.raw_text
BEGIN SELECT RAISE(ABORT,'extraction original content immutable'); END;""",
    """CREATE TRIGGER IF NOT EXISTS trg_er_immutable_d BEFORE DELETE ON extraction_result
BEGIN SELECT RAISE(ABORT,'extraction records cannot be deleted'); END;""",
    """CREATE TABLE IF NOT EXISTS review_queue (                -- 审核任务（基线A）
    id TEXT PRIMARY KEY, project_id TEXT, review_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','IN_REVIEW','DONE')),
    candidate_summary TEXT, suggested_subject_id TEXT REFERENCES business_subject(id),
    info_nature TEXT NOT NULL DEFAULT 'AI_INFERENCE',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE TABLE IF NOT EXISTS review_extraction_link (      -- 任务↔抽取 M:N（基线B）
    id TEXT PRIMARY KEY, review_queue_id TEXT NOT NULL REFERENCES review_queue(id),
    extraction_result_id TEXT NOT NULL REFERENCES extraction_result(id),
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    UNIQUE(review_queue_id, extraction_result_id));""",
    """CREATE TABLE IF NOT EXISTS review_decision (             -- 审核结果明细（基线A）
    id TEXT PRIMARY KEY, review_queue_id TEXT NOT NULL REFERENCES review_queue(id),
    decision TEXT NOT NULL CHECK(decision IN ('ACCEPT_AS_NEW','MERGE_TO','REJECT')),
    reviewer_person_id TEXT NOT NULL REFERENCES person(id),
    reviewed_at TEXT NOT NULL, reason TEXT NOT NULL,
    evidence_source_reference_id TEXT NOT NULL REFERENCES source_reference(id),   -- R2-P3：NOT NULL + FK
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE INDEX IF NOT EXISTS idx_rd_queue ON review_decision(review_queue_id);""",
    """CREATE TRIGGER IF NOT EXISTS trg_rd_evidence_i BEFORE INSERT ON review_decision
WHEN (SELECT is_deleted FROM source_reference WHERE id = NEW.evidence_source_reference_id) <> 0
BEGIN SELECT RAISE(ABORT,'review evidence: source_reference is soft-deleted'); END;""",
    """CREATE TRIGGER IF NOT EXISTS trg_rd_evidence_u BEFORE UPDATE OF evidence_source_reference_id ON review_decision
WHEN (SELECT is_deleted FROM source_reference WHERE id = NEW.evidence_source_reference_id) <> 0
BEGIN SELECT RAISE(ABORT,'review evidence: source_reference is soft-deleted'); END;""",
    """CREATE TABLE IF NOT EXISTS review_result_object (        -- 结果→正式对象稳定映射（基线A）
    id TEXT PRIMARY KEY, review_decision_id TEXT NOT NULL REFERENCES review_decision(id),
    object_type TEXT NOT NULL CHECK(object_type IN
        ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ENTITY','BUSINESS_SUBJECT')),
    object_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK(relation IN ('CREATED','MERGED_INTO','REJECTED')),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');""",
    """CREATE INDEX IF NOT EXISTS idx_rro_obj ON review_result_object(object_type, object_id);""",
)

_CREATE_TABLE = re.compile(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", re.I)

def table_names(statements=STATEMENTS):
    names = []
    for sql in statements:
        match = _CREATE_TABLE.search(sql)
        if match:
            names.append(match.group(1))
    return tuple(names)

TABLES = table_names()

# SQLite 要求这些被引用的父表存在。本切片不向它们插入业务行。
PARENT_ONLY_TABLES = frozenset({
    "entity",
    "department",
    "business_subject",
    "ai_analysis_run",
})

_FORBIDDEN = frozenset({
    "project_phase", "project_member", "discipline", "area", "system",
    "equipment", "equipment_category", "project_discipline", "project_area",
    "project_system", "project_equipment", "email", "issue", "risk", "task",
    "plan", "object_dimension_tag", "user", "evidence",
})

_EXPECTED = (
    "schema_version",
    "entity",
    "project",
    "organization",
    "department",
    "person",
    "document",
    "document_version",
    "source_reference",
    "business_subject",
    "knowledge_item",
    "knowledge_version",
    "ingestion_job",
    "ai_analysis_run",
    "extraction_result",
    "review_queue",
    "review_extraction_link",
    "review_decision",
    "review_result_object",
)

if set(TABLES) & _FORBIDDEN:
    raise RuntimeError("切片 DDL 含有本刀明确不做的表: %s" % (set(TABLES) & _FORBIDDEN))
if TABLES != _EXPECTED:
    raise RuntimeError("表清单或顺序偏离切片定义: %s" % (TABLES,))
for _sql in STATEMENTS:
    if not _sql.lstrip().upper().startswith("CREATE"):
        raise RuntimeError("迁移语句必须是 CREATE，连接参数由连接工厂负责")
    if "VIRTUAL TABLE" in _sql.upper() or "_fts" in _sql.lower():
        raise RuntimeError("本切片不生成 FTS 对象")
