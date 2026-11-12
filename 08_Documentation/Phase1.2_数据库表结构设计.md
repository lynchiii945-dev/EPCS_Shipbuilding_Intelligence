# Phase1.2 数据库表结构设计（CREATE TABLE 草案）

> 本文件为 Phase 1.2 **迁移脚本草案**（对应 `01_Data/migrations/001_init.sql`，本阶段**不执行**，仅作为架构交付），仅供 Phase 评审与后续实现依据。
> 约定：所有 `id` 为 `char(32)`（UUID 无连字符）；时间以 ISO8601 UTC 文本存储；公共字段 `created_at/updated_at/created_by/updated_by/is_deleted/deleted_at/info_nature` 为各业务表通用基字段。表结构**幂等**（含 `IF NOT EXISTS`）。不引入第一期不必要设施。
> 数据库：`01_Data/epcs_intelligence.db`。

---

## 0. 元信息与辅助（建议由脚本补齐，表中字段含义见数据字典）

```sql
-- 建库时 PRAGMA
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS schema_version (
    version        INTEGER PRIMARY KEY,
    applied_at     TEXT NOT NULL,
    description    TEXT
);
```

---

## 1. 域1 —— 项目与组织

```sql
CREATE TABLE IF NOT EXISTS project (
    id                 TEXT PRIMARY KEY,              -- UUID char(32)
    project_code       TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL,
    main_object_entity_id TEXT,                        -- FK→entity(表后置，动态)
    contract_summary   TEXT,
    status             TEXT NOT NULL DEFAULT 'ACTIVE', -- system_config 归口
    started_at         TEXT,
    planned_end_at     TEXT,
    ended_at           TEXT,
    info_nature        TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at         TEXT NOT NULL,
    updated_at         TEXT,
    created_by         TEXT,
    updated_by         TEXT,
    is_deleted         INTEGER NOT NULL DEFAULT 0,
    deleted_at         TEXT
);

CREATE TABLE IF NOT EXISTS project_phase (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL REFERENCES project(id),
    phase_code         TEXT NOT NULL,                  -- E/P/C/S
    name               TEXT,
    seq_no             INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'ACTIVE',
    valid_from         TEXT,
    valid_to           TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT,
    is_deleted         INTEGER NOT NULL DEFAULT 0,
    deleted_at         TEXT,
    UNIQUE(project_id, phase_code, seq_no)
);

CREATE TABLE IF NOT EXISTS organization (
    id                 TEXT PRIMARY KEY,
    org_code           TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL,
    org_type           TEXT NOT NULL,                  -- 船东/船厂/… dim 归口
    parent_id          TEXT REFERENCES organization(id),
    created_at         TEXT NOT NULL,
    is_deleted         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS person (
    id                 TEXT PRIMARY KEY,
    organization_id    TEXT NOT NULL REFERENCES organization(id),
    name               TEXT NOT NULL,
    email              TEXT,
    created_at         TEXT NOT NULL,
    is_deleted         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_person_org ON person(organization_id);

CREATE TABLE IF NOT EXISTS project_member (
    id                 TEXT PRIMARY KEY,
    project_id         TEXT NOT NULL REFERENCES project(id),
    organization_id    TEXT NOT NULL REFERENCES organization(id),
    person_id          TEXT REFERENCES person(id),
    role_name          TEXT NOT NULL,
    role_kind          TEXT,                            -- 项目角色/合同角色
    valid_from         TEXT,
    valid_to           TEXT,
    is_contract_carrier INTEGER NOT NULL DEFAULT 0,     -- 弱合同载体 B.1
    created_at         TEXT NOT NULL,
    is_deleted         INTEGER NOT NULL DEFAULT 0,
    UNIQUE(project_id, organization_id, person_id, role_name, valid_from)
);
CREATE INDEX IF NOT EXISTS idx_pm_proj ON project_member(project_id);

-- 维度目录（同构）
CREATE TABLE IF NOT EXISTS discipline (
    id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    parent_id TEXT REFERENCES discipline(id), is_standard INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS area (
    id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    parent_id TEXT REFERENCES area(id), is_standard INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS system (
    id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    parent_id TEXT REFERENCES system(id), is_standard INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS equipment_category (
    id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    parent_id TEXT REFERENCES equipment_category(id), created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS equipment (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    category_id        TEXT REFERENCES equipment_category(id),
    system_id          TEXT REFERENCES system(id),
    manufacturer_entity_id TEXT,                        -- FK→entity
    equip_type         TEXT,
    created_at         TEXT NOT NULL,
    is_deleted         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_equip_sys ON equipment(system_id);
CREATE INDEX IF NOT EXISTS idx_equip_cat ON equipment(category_id);

-- 项目×维度关联（G1 横向施加）
CREATE TABLE IF NOT EXISTS project_discipline (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    discipline_id TEXT NOT NULL REFERENCES discipline(id),
    UNIQUE(project_id, discipline_id));
CREATE TABLE IF NOT EXISTS project_area (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    area_id TEXT NOT NULL REFERENCES area(id),
    UNIQUE(project_id, area_id));
CREATE TABLE IF NOT EXISTS project_system (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    system_id TEXT NOT NULL REFERENCES system(id),
    UNIQUE(project_id, system_id));
CREATE TABLE IF NOT EXISTS project_equipment (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    equipment_id TEXT NOT NULL REFERENCES equipment(id),
    UNIQUE(project_id, equipment_id));
```

---

## 2. 域2 —— 计划管理

```sql
CREATE TABLE IF NOT EXISTS plan (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    name TEXT NOT NULL, plan_code TEXT, level TEXT,     -- L1..L4 归口
    status TEXT NOT NULL DEFAULT 'DRAFT', created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_plan_proj ON plan(project_id);

CREATE TABLE IF NOT EXISTS plan_version (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    version_no TEXT NOT NULL, content_hash TEXT,
    is_forecast INTEGER NOT NULL DEFAULT 0,             -- 滚动预测版
    snapshot_json TEXT, status TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    UNIQUE(plan_id, version_no));

CREATE TABLE IF NOT EXISTS baseline_version (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    plan_version_id TEXT NOT NULL REFERENCES plan_version(id),
    baseline_no TEXT NOT NULL, approved_at TEXT NOT NULL,
    approved_by TEXT, is_active INTEGER NOT NULL DEFAULT 0,
    is_readonly INTEGER NOT NULL DEFAULT 1,             -- 只读受保护
    UNIQUE(plan_id, baseline_no),
    UNIQUE(plan_id, is_active));                        -- 见 ADR-8（部分索引精化）
CREATE UNIQUE INDEX IF NOT EXISTS idx_baseline_active ON baseline_version(plan_id) WHERE is_active=1;

CREATE TABLE IF NOT EXISTS plan_activity (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    code TEXT, name TEXT NOT NULL, is_milestone INTEGER NOT NULL DEFAULT 0,
    discipline_id TEXT, area_id TEXT, system_id TEXT,    -- 主维度快捷；副维度走 tag
    planned_start TEXT, planned_end TEXT,
    status TEXT NOT NULL DEFAULT 'PLANNED', created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_activity_plan ON plan_activity(plan_id);
CREATE INDEX IF NOT EXISTS idx_activity_milestone ON plan_activity(is_milestone);

CREATE TABLE IF NOT EXISTS activity_dependency (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    predecessor_id TEXT NOT NULL REFERENCES plan_activity(id),
    successor_id   TEXT NOT NULL REFERENCES plan_activity(id),
    relation_type  TEXT NOT NULL CHECK(relation_type IN ('FS','SS','FF','SF')),
    lag_days INTEGER,
    CHECK(predecessor_id <> successor_id),
    UNIQUE(plan_id, predecessor_id, successor_id, relation_type));

CREATE TABLE IF NOT EXISTS progress_record (
    id TEXT PRIMARY KEY, plan_activity_id TEXT NOT NULL REFERENCES plan_activity(id),
    record_at TEXT NOT NULL, progress_pct REAL NOT NULL DEFAULT 0
        CHECK(progress_pct BETWEEN 0 AND 100),
    actual_start TEXT, actual_end TEXT, note TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT', created_at TEXT NOT NULL,
    UNIQUE(plan_activity_id, record_at));
```

---

## 3. 域3 —— 信息与文件（来源域）

```sql
CREATE TABLE IF NOT EXISTS email (
    id TEXT PRIMARY KEY, message_id_text TEXT UNIQUE,
    from_addr TEXT, to_addrs TEXT, cc_addrs TEXT,       -- JSON 文本
    subject TEXT NOT NULL, body_markdown TEXT,          -- 正文按隔离边界授权
    source_time TEXT NOT NULL, created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS email_attachment (
    id TEXT PRIMARY KEY, email_id TEXT NOT NULL REFERENCES email(id),
    filename TEXT NOT NULL, file_kind TEXT, sha256 TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS document (
    id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL,
    doc_code TEXT, doc_type TEXT, is_readonly INTEGER NOT NULL DEFAULT 1,
    sha256 TEXT, created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_sha ON document(sha256) WHERE sha256 IS NOT NULL;

CREATE TABLE IF NOT EXISTS document_version (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES document(id),
    version_no TEXT NOT NULL, file_path TEXT, sha256 TEXT,
    snapshot_json TEXT, notes TEXT, created_at TEXT NOT NULL,
    UNIQUE(document_id, version_no));

CREATE TABLE IF NOT EXISTS drawing (
    id TEXT PRIMARY KEY, project_id TEXT, drawing_no TEXT UNIQUE,
    name TEXT NOT NULL, doc_type TEXT NOT NULL DEFAULT 'DRAWING',
    is_readonly INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS drawing_version (
    id TEXT PRIMARY KEY, drawing_id TEXT NOT NULL REFERENCES drawing(id),
    revision TEXT, file_path TEXT, sha256 TEXT, created_at TEXT NOT NULL,
    UNIQUE(drawing_id, revision));

-- DWG 对象预留（不装 SDK/不解析，仅结构占位 ADR-10）
CREATE TABLE IF NOT EXISTS drawing_object (
    id TEXT PRIMARY KEY, drawing_id TEXT NOT NULL REFERENCES drawing(id),
    obj_type TEXT, ref_entity_id TEXT, ref_area_id TEXT, ref_system_id TEXT,
    geometry_json TEXT, reserved_data TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS meeting (
    id TEXT PRIMARY KEY, project_id TEXT, title TEXT NOT NULL,
    held_at TEXT, organizer_person_id TEXT, participant_ids TEXT, -- JSON
    transcript_ptr TEXT, source_time TEXT, created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS meeting_minutes (
    id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL REFERENCES meeting(id),
    version_no TEXT, content_md TEXT, is_final INTEGER NOT NULL DEFAULT 0,
    source_time TEXT, created_at TEXT NOT NULL, UNIQUE(meeting_id, version_no));

CREATE TABLE IF NOT EXISTS message (
    id TEXT PRIMARY KEY, project_id TEXT, sender_person_id TEXT,
    content_md TEXT, sent_at TEXT, channel TEXT, source_time TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

-- 统一来源桥（多态，无硬 FK）
CREATE TABLE IF NOT EXISTS source_reference (
    id TEXT PRIMARY KEY, traced_entity_type TEXT NOT NULL, traced_entity_id TEXT NOT NULL,
    source_type TEXT NOT NULL, source_id TEXT NOT NULL,
    context_excerpt TEXT, locator TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT', confidence REAL,
    source_time TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sr_entity ON source_reference(traced_entity_type, traced_entity_id);
CREATE INDEX IF NOT EXISTS idx_sr_source ON source_reference(source_type, source_id);

-- 证据
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY, project_id TEXT, title TEXT NOT NULL,
    body TEXT, evidence_kind TEXT, sha256 TEXT, created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS evidence_link (
    id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL REFERENCES evidence(id),
    ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, link_role TEXT, context_excerpt TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_el_ref ON evidence_link(ref_type, ref_id);
```

---

## 4. 域4 —— 问题/风险/任务闭环

```sql
CREATE TABLE IF NOT EXISTS issue (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    ref_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description_md TEXT,
    status TEXT NOT NULL DEFAULT 'NEW',                 -- 状态机 bid§4.2
    severity TEXT, priority TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, created_by TEXT, updated_by TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT);
CREATE INDEX IF NOT EXISTS idx_issue_proj ON issue(project_id);
CREATE INDEX IF NOT EXISTS idx_issue_status ON issue(status);

CREATE TABLE IF NOT EXISTS issue_status_history (
    id TEXT PRIMARY KEY, issue_id TEXT NOT NULL REFERENCES issue(id),
    old_status TEXT, new_status TEXT NOT NULL, transition TEXT,
    changed_by TEXT, changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
    info_nature TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS risk (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    ref_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description_md TEXT,
    probability TEXT, impact TEXT, exposure TEXT, status TEXT NOT NULL DEFAULT 'NEW',
    strategy TEXT, info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT);
CREATE INDEX IF NOT EXISTS idx_risk_proj ON risk(project_id);

CREATE TABLE IF NOT EXISTS risk_status_history (
    id TEXT PRIMARY KEY, risk_id TEXT NOT NULL REFERENCES risk(id),
    old_status TEXT, new_status TEXT NOT NULL, transition TEXT,
    changed_by TEXT, changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS task (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    ref_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description_md TEXT,
    assignee_person_id TEXT, due_at TEXT, priority TEXT, status TEXT NOT NULL DEFAULT 'NEW',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT);
CREATE INDEX IF NOT EXISTS idx_task_proj ON task(project_id);

CREATE TABLE IF NOT EXISTS task_status_history (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES task(id),
    old_status TEXT, new_status TEXT NOT NULL, transition TEXT,
    changed_by TEXT, changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS action_measure (
    id TEXT PRIMARY KEY, ref_no TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    measure_type TEXT NOT NULL,                        -- RISK_RESPONSE / ISSUE_REMEDY
    source_owner_type TEXT, source_owner_id TEXT,      -- 泛化属主(risk/issue)
    due_at TEXT, status TEXT NOT NULL DEFAULT 'OPEN', info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT);

CREATE TABLE IF NOT EXISTS decision (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    ref_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL, conclusion_md TEXT,
    decided_by_person_id TEXT, decided_at TEXT, status TEXT NOT NULL DEFAULT 'OPEN',
    info_nature TEXT NOT NULL DEFAULT 'DECISION',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT);

CREATE TABLE IF NOT EXISTS decision_link (
    id TEXT PRIMARY KEY, decision_id TEXT NOT NULL REFERENCES decision(id),
    ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, link_role TEXT,
    context_excerpt TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_dl_ref ON decision_link(ref_type, ref_id);

-- 通用对象桥（B.3/B.4 全链路 M:N）
CREATE TABLE IF NOT EXISTS object_link (
    id TEXT PRIMARY KEY, link_role TEXT NOT NULL,     -- role 归口
    left_type TEXT NOT NULL, left_id TEXT NOT NULL,
    right_type TEXT NOT NULL, right_id TEXT NOT NULL,
    context_excerpt TEXT, info_nature TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_ol_left ON object_link(left_type, left_id);
CREATE INDEX IF NOT EXISTS idx_ol_right ON object_link(right_type, right_id);
```

---

## 5. 域5 —— 实体关系与知识

```sql
CREATE TABLE IF NOT EXISTS entity (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, entity_kind TEXT NOT NULL,
    canonical_source_id TEXT REFERENCES entity(id),   -- 合并主实体
    status TEXT NOT NULL DEFAULT 'ACTIVE',            -- ACTIVE/MERGED/SUPERSEDED
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT);
CREATE INDEX IF NOT EXISTS idx_entity_name ON entity(name);

CREATE TABLE IF NOT EXISTS entity_alias (
    id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entity(id),
    alias TEXT NOT NULL, alias_type TEXT,
    source_reference_id TEXT, confirm_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL, UNIQUE(entity_id, alias));

CREATE TABLE IF NOT EXISTS entity_identifier (
    id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entity(id),
    id_type TEXT NOT NULL, source_from TEXT, identifier TEXT NOT NULL,
    source_reference_id TEXT, effective_from TEXT, created_at TEXT NOT NULL,
    UNIQUE(id_type, identifier));

CREATE TABLE IF NOT EXISTS entity_relationship (
    id TEXT PRIMARY KEY, left_entity_id TEXT NOT NULL REFERENCES entity(id),
    right_entity_id TEXT NOT NULL REFERENCES entity(id),
    relation_type TEXT NOT NULL,                       -- synonym/merge/holonym/…
    confirm_status TEXT NOT NULL DEFAULT 'PENDING',
    source_reference_id TEXT, created_at TEXT NOT NULL,
    CHECK(left_entity_id <> right_entity_id),
    UNIQUE(left_entity_id, right_entity_id, relation_type));

CREATE TABLE IF NOT EXISTS knowledge_item (
    id TEXT PRIMARY KEY, project_id TEXT, ref_no TEXT UNIQUE, title TEXT NOT NULL,
    summary TEXT, info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    status TEXT NOT NULL DEFAULT 'PUBLISHED', created_at TEXT NOT NULL, updated_at TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT);

CREATE TABLE IF NOT EXISTS knowledge_version (
    id TEXT PRIMARY KEY, knowledge_item_id TEXT NOT NULL REFERENCES knowledge_item(id),
    version_no TEXT NOT NULL, content_md TEXT, sha256 TEXT, snapshot_json TEXT,
    created_at TEXT NOT NULL, UNIQUE(knowledge_item_id, version_no));

CREATE TABLE IF NOT EXISTS knowledge_entity_link (
    id TEXT PRIMARY KEY, knowledge_version_id TEXT NOT NULL REFERENCES knowledge_version(id),
    entity_id TEXT NOT NULL REFERENCES entity(id), created_at TEXT NOT NULL,
    UNIQUE(knowledge_version_id, entity_id));
```

---

## 6. 域6 —— AI 处理与系统治理

```sql
CREATE TABLE IF NOT EXISTS ingestion_job (
    id TEXT PRIMARY KEY, project_id TEXT, source_type TEXT NOT NULL,
    source_id TEXT, channel TEXT, status TEXT NOT NULL DEFAULT 'INGESTING',
    started_at TEXT, finished_at TEXT, run_meta TEXT,   -- JSON
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ai_analysis_run (
    id TEXT PRIMARY KEY, project_id TEXT, run_type TEXT NOT NULL,
    model TEXT, input_ref TEXT, output_summary TEXT, status TEXT NOT NULL DEFAULT 'RUNNING',
    started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS extraction_result (
    id TEXT PRIMARY KEY, ingestion_job_id TEXT REFERENCES ingestion_job(id),
    ai_analysis_run_id TEXT REFERENCES ai_analysis_run(id),
    candidate_type TEXT NOT NULL,                      -- 实体/问题/风险/分类…
    candidate_json TEXT, raw_text TEXT,
    info_nature TEXT NOT NULL DEFAULT 'AI_INFERENCE',
    confidence REAL,                                   -- 路由：REJECT/ignored
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS review_queue (
    id TEXT PRIMARY KEY, extraction_result_id TEXT REFERENCES extraction_result(id),
    reviewer_person_id TEXT, review_type TEXT NOT NULL,
    candidate_summary TEXT, suggested_entity_id TEXT,
    decision TEXT,                                      -- ACCEPT_AS_NEW / MERGE_TO / REJECT
    target_entity_id TEXT,                              -- 合并目标
    reviewed_at TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_rq_status ON review_queue(decision);
CREATE INDEX IF NOT EXISTS idx_rq_suggest ON review_queue(suggested_entity_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY, project_id TEXT, actor_type TEXT NOT NULL, -- USER/AI
    actor_id TEXT, action_code TEXT NOT NULL, target_type TEXT, target_id TEXT,
    before_json TEXT, after_json TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target_type, target_id);

CREATE TABLE IF NOT EXISTS system_config (
    id TEXT PRIMARY KEY, config_key TEXT NOT NULL UNIQUE, config_value TEXT NOT NULL,
    description TEXT, config_group TEXT, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);

-- Phase 后期启用（仅预留骨架 D.2-2）
CREATE TABLE IF NOT EXISTS user (
    id TEXT PRIMARY KEY, person_id TEXT, username TEXT UNIQUE, password_hash TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS role (
    id TEXT PRIMARY KEY, role_code TEXT UNIQUE, name TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS permission (
    id TEXT PRIMARY KEY, permission_code TEXT UNIQUE, name TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_role (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES user(id),
    role_id TEXT NOT NULL REFERENCES role(id), UNIQUE(user_id, role_id));
CREATE TABLE IF NOT EXISTS role_permission (
    id TEXT PRIMARY KEY, role_id TEXT NOT NULL REFERENCES role(id),
    permission_id TEXT NOT NULL REFERENCES permission(id), UNIQUE(role_id, permission_id));
```

---

## 7. 共享桥表与 FTS5 trigram 索引

### 7.1 对象×维度 多值标签（B.2 正交）
```sql
CREATE TABLE IF NOT EXISTS object_dimension_tag (
    id TEXT PRIMARY KEY, tagged_object_type TEXT NOT NULL,
    tagged_object_id TEXT NOT NULL,
    dimension TEXT NOT NULL CHECK(dimension IN ('EPCS_PHASE','DISCIPLINE','AREA','SYSTEM')),
    value_type TEXT NOT NULL DEFAULT 'REF',            -- REF / FREE_TEXT
    value_id TEXT, value_text TEXT,
    created_at TEXT NOT NULL, created_by TEXT);
CREATE INDEX IF NOT EXISTS idx_odt_obj ON object_dimension_tag(tagged_object_type, tagged_object_id);
CREATE INDEX IF NOT EXISTS idx_odt_dim ON object_dimension_tag(dimension, value_id);
```

### 7.2 FTS5 trigram（中文检索唯一事实，G6/OQ-7）
> 注：SQLite FTS5 外部内容表 `content=` 关联主表按 `content_rowid=id`；因主表 `id` 为 TEXT，需配合主表自增 rowid 或改用内容表方式。实现参考：以各表 **rowid** 为 content_rowid，`id`(TEXT) 存进 FTS 并作为返回指针。此处草案给出两种范式并标注建议。

```sql
-- 形式A（推荐 · 外部内容表 + trigram）
CREATE VIRTUAL TABLE IF NOT EXISTS issue_fts USING fts5(
    title, description_md,
    content='issue', content_rowid='rowid', tokenize='trigram');

-- 形式B（独立触发器同步）——与内容表触发器，见版本规范
CREATE VIRTUAL TABLE IF NOT EXISTS email_fts USING fts5(subject, body_markdown, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(name, snapshot_json, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS drawing_fts  USING fts5(name, drawing_no, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS meeting_fts USING fts5(title, content_md, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5(content_md, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS risk_fts     USING fts5(title, description_md, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS task_fts     USING fts5(title, description_md, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(title, content_md, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts   USING fts5(name, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS entity_alias_fts USING fts5(alias, tokenize='trigram');
CREATE VIRTUAL TABLE IF NOT EXISTS action_measure_fts USING fts5(name, tokenize='trigram');
```

- 同义词/近义召回：`entity_alias` 先 fuzzy 命中 → 映射 `entity`；主表候选再与 `source_reference`/`entity_relationship` 间链（ADR-7）。

---

## 8. 触发器草案（基线只读 & 禁物理删除 & FTS 同步）

### 8.1 基线只读强拦（OQ-3）
```sql
-- 基线一旦 approved 即只读：阻断 UPDATE/DELETE
CREATE TRIGGER IF NOT EXISTS trg_baseline_ro_update
BEFORE UPDATE ON baseline_version
WHEN OLD.is_readonly = 1 AND (NEW.is_active <> OLD.is_active) IS 0
BEGIN
    SELECT RAISE(ABORT, 'baseline is read-only');
END;
-- 变体：对任意字段改动的 UPDATE 拦截（细化见 ADR-8）

CREATE TRIGGER IF NOT EXISTS trg_baseline_ro_delete
BEFORE DELETE ON baseline_version
WHEN OLD.is_readonly = 1
BEGIN
    SELECT RAISE(ABORT, 'baseline is read-only; force-delete requires admin+audit');
END;
```

### 8.2 正式记录禁物理删除（问题 9）
```sql
CREATE TRIGGER IF NOT EXISTS trg_issue_no_delete
BEFORE DELETE ON issue
BEGIN
    SELECT RAISE(ABORT, 'physical delete disabled; use soft delete (is_deleted=1) via audit flow');
END;
-- 其他正式表同模式：risk/task/decision/document/drawing/knowledge_item/entity
```

### 8.3 FTS 同步触发器（外挂形式B示例）
```sql
CREATE TRIGGER IF NOT EXISTS trg_issue_ai AFTER INSERT ON issue
BEGIN
    INSERT INTO issue_fts(rowid, title, description_md)
    VALUES (new.rowid, new.title, new.description_md);
END;
CREATE TRIGGER IF NOT EXISTS trg_issue_au AFTER UPDATE ON issue
WHEN old.title IS NOT new.title OR old.description_md IS NOT new.description_md
BEGIN
    UPDATE issue_fts SET title=new.title, description_md=new.description_md WHERE rowid=new.rowid;
END;
CREATE TRIGGER IF NOT EXISTS trg_issue_ad AFTER DELETE ON issue
BEGIN
    INSERT INTO issue_fts(issue_fts, rowid, title, description_md) VALUES('delete', old.rowid, old.title, old.description_md);
END;
-- 其余内容表同法，迁移脚本批量生成。
```

---

## 9. 索引策略小结

| 类型 | 说明 |
|---|---|
| 唯一索引 | project_code / organization.org_code / plan code / ref_no(issue/risk/task/decision) / entity_identifier(id_type,identifier) 等 |
| 关系索引 | 所有 project_vs_* 关联表 (project_id) 与被引维度 id |
| 桥表索引 | object_link(left/right)、source_reference(entity/source)、object_dimension_tag(obj/dim) |
| 时间索引 | source_time/created_at（报表/历史）按需 |
| FTS | 全部内容文本表 trigram；short 命中靠 alias 补偿 |

> 本草案为**第一期够用**版本：不引入分库分表、不做冗余物化视图、不扩展触发器复杂度；FTS 同步触发器若查询量可控可改为**定时/摄入时批量重建**（ADR-7 权衡后定）。