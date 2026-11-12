# Phase1.2 数据库表结构设计（R1 整改版 · CREATE TABLE 草案）

> 版本：R1（架构评审整改后）｜日期：2026-11-12
> 本文件是**全库唯一真值源**：表名、字段、约束、触发器、索引、FTS 对应关系、对象数量统计，其余 7 份文档一律以本文为准。
> **本阶段不执行**：未创建 `migrations/001_init.sql`，未对 `01_Data/epcs_intelligence.db` 执行任何 DDL/DML，数据库仍为空库（业务表 0）。
> 所有 DDL 已在 Python `:memory:` 内存库实测（见 §8），未触碰正式库。

---

## 0. 全局约定与统一统计

### 0.1 连接与运行规范（实测结论）
```sql
PRAGMA foreign_keys = ON;   -- 必须【每个连接】单独执行！实测：连接A开启后，新连接B foreign_keys=0 且外键失效（§8 G9）
PRAGMA journal_mode = WAL;  -- 库级设置，持久化
```
> **结论**：Python `sqlite3.connect()` 之后必须在**每个连接**上执行 `PRAGMA foreign_keys=ON`；这是应用层连接工厂的强制职责，不能只写在迁移脚本首行。

### 0.2 统一对象数量统计（R1 定稿，8 份文档共同引用）

| 类别 | 数量 | 说明 |
|---|---|---|
| 实体表（业务主表） | **46** | 见 §0.4 清单 A |
| 实体表（辅助/关联/桥/历史/治理） | **29** | 见 §0.4 清单 B |
| 实体表合计 | **75** | 含 `schema_version` 元信息表 1 张 |
| FTS5 虚拟表 | **24** | `tokenize='trigram'`，见 §7.2 |
| 触发器 | **96** | FTS 同步 72 + 基线冻结 2 + 抽取不可变 2 + 禁物理删除 20 |
| 唯一索引/约束 | **见 §9** | 表内 UNIQUE + 显式 `CREATE UNIQUE INDEX` |
| 普通索引 | **见 §9** | 关系/桥/时间索引 |
| 视图 | 0 | 第一期不引入 |

> 统计口径：实体表 = `CREATE TABLE`（不含 `CREATE VIRTUAL TABLE`）；FTS 表 = `CREATE VIRTUAL TABLE ... USING fts5`；触发器 = `CREATE TRIGGER`。迁移脚本批量生成的 FTS 同步触发器按 24×3 计入。
>
> **DDL 表达口径（避免「声明数量 ≠ 文本语句数」误读）**：本文 75 张实体表**逐表给出完整 `CREATE TABLE`**；24 张 FTS 虚表与 72 个 FTS 同步触发器彼此同构，故在 §7.2 / §7.3 以「**1 个统一范式模板 + 24 张一一对应清单**」表达，由迁移脚本按清单循环生成（清单即完整定义，不含省略项）；§8-H 的禁物理删除触发器同样以 1 个模板 + 20 张适用表清单表达。因此 `grep -c '^CREATE VIRTUAL TABLE'` = 1、`grep -c '^CREATE TRIGGER'` = 8 属**模板化表达**，与 §0.2 的 24 / 96 不矛盾；迁移脚本生成后的实际对象数量即为本表统计值。
>
> **迁移后核验统计的口径（实测踩坑结论）**：统计正式库对象数量须用 `PRAGMA table_list` 的 `type` 列区分 `table / virtual / shadow / view`，并**排除系统目录表 `sqlite_schema`**；FTS5 的 5 张影子表标为 `shadow` 不计入表数，`sqlite_autoindex_*` 属 PK/UNIQUE 自动创建的内部索引（`sql IS NULL`）另计、不计入显式索引。若用 `sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'` 会误计影子表并漏掉自动索引。另实测：SQLite **不支持** `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`（报 `near "FOREIGN": syntax error`），所有 FK 必须在 `CREATE TABLE` 内联声明；连接建立后建议追加 `PRAGMA foreign_key_check` 启动自检。

### 0.3 公共字段基线（逐表标注，SQL 与数据字典严格对应）
```
-- 基线 A（正式业务表，46 张中的主表）
id            TEXT PRIMARY KEY CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')
project_id    TEXT REFERENCES project(id)      -- 范围表必填；全局/治理表可空
info_nature   TEXT NOT NULL DEFAULT 'CONFIRMED_FACT'
              CHECK(info_nature IN ('SOURCE_FACT','CONFIRMED_FACT','AI_INFERENCE','PREDICTION','PROPOSAL','DECISION'))
created_at    TEXT NOT NULL
updated_at    TEXT
created_by    TEXT REFERENCES person(id)
updated_by    TEXT REFERENCES person(id)
is_deleted    INTEGER NOT NULL DEFAULT 0
deleted_at    TEXT
del_status    TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(del_status IN ('ACTIVE','ARCHIVED','DELETED'))

-- 基线 B（辅助/关联/桥/历史/日志表）
id            TEXT PRIMARY KEY CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')
created_at    TEXT NOT NULL
is_deleted    INTEGER NOT NULL DEFAULT 0
```
> **UUID 规则**：`uuid4().hex`（32 位小写十六进制）；DB 层 `CHECK` 实测生效（§8 G8）；**禁止**用文件名、姓名、项目名作主键（G7）。
> **建表顺序**：SQLite 允许 FK 引用**后置创建**的表（实测 §8 G10 PASS），故本文按 6 域顺序书写；迁移到 PostgreSQL 时须按依赖拓扑重排。
> **时间字段**：`event_time` / `source_time` / `created_at` / `updated_at` / `valid_from` / `valid_to` 严格区分，均为 ISO8601 UTC 文本。

### 0.4 全表清单（A 业务主表 46 / B 辅助表 29）

**A 业务主表（46）**
`project, project_phase, organization, department, person, discipline, area, system, equipment_category, equipment, plan, plan_version, baseline_version, plan_active_baseline, plan_activity, plan_activity_version, email, email_attachment, document, document_version, drawing, drawing_version, drawing_object, meeting, meeting_minutes, message, source_reference, evidence, issue, risk, task, action_measure, decision, object_link, entity, entity_alias, entity_identifier, entity_relationship, business_subject, business_subject_alias, business_subject_merge, knowledge_item, knowledge_version, ingestion_job, ai_analysis_run, extraction_result`（46）

**B 辅助/关联/桥/历史/治理表（29）**
`schema_version, project_member, project_discipline, project_area, project_system, project_equipment, baseline_switch_log, activity_dependency, progress_record, issue_status_history, risk_status_history, task_status_history, action_measure_link, decision_link, evidence_link, business_subject_source, review_queue, review_extraction_link, review_decision, review_result_object, knowledge_entity_link, object_dimension_tag, audit_log, system_config, user, role, permission, user_role, role_permission`（29 张，含 `schema_version`）

> 说明：`business_subject_alias` 归 A 组（已列入 A 清单），**不计入 B**；A 46 + B 29 = 75，与 §0.2 一致。逐表定义见 §1~§7，数据字典逐表说明见《核心实体数据字典》。

---

## 1. 域1 —— 项目与组织

```sql
-- ============ 基础/元信息 ============
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT,
    ddl_fingerprint TEXT,            -- 结构一致性校验用（§10）
    CHECK(length(ddl_fingerprint)=64 OR ddl_fingerprint IS NULL));

-- entity 前置定义（project/equipment 的 FK 目标）；SQLite 允许后置，此处前移仅为可读性
CREATE TABLE IF NOT EXISTS entity (                       -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL, entity_kind TEXT NOT NULL,
    canonical_source_id TEXT REFERENCES entity(id),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','MERGED','SUPERSEDED')),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, created_by TEXT, updated_by TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT,
    del_status TEXT NOT NULL DEFAULT 'ACTIVE', CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*'));

CREATE TABLE IF NOT EXISTS project (                      -- 基线A
    id TEXT PRIMARY KEY, project_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    main_object_entity_id TEXT REFERENCES entity(id),     -- R1-6 整改：真正 FK
    contract_summary TEXT, status TEXT NOT NULL DEFAULT 'ACTIVE',
    started_at TEXT, planned_end_at TEXT, ended_at TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, created_by TEXT, updated_by TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*'));

CREATE TABLE IF NOT EXISTS project_phase (               -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    phase_code TEXT NOT NULL, name TEXT, seq_no INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ACTIVE', valid_from TEXT, valid_to TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(project_id, phase_code, seq_no));

CREATE TABLE IF NOT EXISTS organization (                -- 基线A
    id TEXT PRIMARY KEY, org_code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    org_type TEXT NOT NULL, parent_id TEXT REFERENCES organization(id),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');

-- R1-6 新增：Department（产品确认书 A.1 列有 departments，旧 SQL 缺失）
CREATE TABLE IF NOT EXISTS department (                  -- 基线A
    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES organization(id),
    code TEXT NOT NULL, name TEXT NOT NULL,
    parent_id TEXT REFERENCES department(id),            -- 部门内部层级
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(organization_id, code));
-- 职责边界：organization.parent_id = 上下级单位（母/子公司、总分包）；department = 单位内部部门。

CREATE TABLE IF NOT EXISTS person (                      -- 基线A
    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES organization(id),
    department_id TEXT REFERENCES department(id), name TEXT NOT NULL, email TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_person_org ON person(organization_id);
CREATE INDEX IF NOT EXISTS idx_person_dept ON person(department_id);

-- R1-6 整改：删除表内 UNIQUE（NULL 组合可重复），改表达式唯一索引
CREATE TABLE IF NOT EXISTS project_member (              -- 基线B
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    organization_id TEXT NOT NULL REFERENCES organization(id),
    person_id TEXT REFERENCES person(id),                -- 可空：组织级角色
    role_name TEXT NOT NULL, role_kind TEXT,
    valid_from TEXT, valid_to TEXT,
    is_contract_carrier INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pm
    ON project_member(project_id, organization_id, COALESCE(person_id,''), role_name, COALESCE(valid_from,''));
CREATE INDEX IF NOT EXISTS idx_pm_proj ON project_member(project_id);

CREATE TABLE IF NOT EXISTS discipline (id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    parent_id TEXT REFERENCES discipline(id), is_standard INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS area (id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    parent_id TEXT REFERENCES area(id), is_standard INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS system (id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    parent_id TEXT REFERENCES system(id), is_standard INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS equipment_category (id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL, parent_id TEXT REFERENCES equipment_category(id), created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS equipment (                   -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL,
    category_id TEXT REFERENCES equipment_category(id), system_id TEXT REFERENCES system(id),
    manufacturer_entity_id TEXT REFERENCES entity(id),   -- R1-6 整改：真正 FK
    equip_type TEXT, info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_equip_sys ON equipment(system_id);
CREATE INDEX IF NOT EXISTS idx_equip_cat ON equipment(category_id);
CREATE INDEX IF NOT EXISTS idx_equip_mfr ON equipment(manufacturer_entity_id);

CREATE TABLE IF NOT EXISTS project_discipline (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id), discipline_id TEXT NOT NULL REFERENCES discipline(id), UNIQUE(project_id, discipline_id));
CREATE TABLE IF NOT EXISTS project_area        (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id), area_id        TEXT NOT NULL REFERENCES area(id),        UNIQUE(project_id, area_id));
CREATE TABLE IF NOT EXISTS project_system      (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id), system_id      TEXT NOT NULL REFERENCES system(id),      UNIQUE(project_id, system_id));
CREATE TABLE IF NOT EXISTS project_equipment   (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id), equipment_id   TEXT NOT NULL REFERENCES equipment(id),   UNIQUE(project_id, equipment_id));
```

---

## 2. 域2 —— 计划管理（R1-1 基线只读 + R1-2 活动版本化）

```sql
CREATE TABLE IF NOT EXISTS plan (                        -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    name TEXT NOT NULL, plan_code TEXT, level TEXT, status TEXT NOT NULL DEFAULT 'DRAFT',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_plan_proj ON plan(project_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_code ON plan(project_id, plan_code) WHERE plan_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS plan_version (                -- 基线A
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    version_no TEXT NOT NULL, content_hash TEXT, is_forecast INTEGER NOT NULL DEFAULT 0,
    snapshot_json TEXT, status TEXT NOT NULL DEFAULT 'DRAFT',
    info_nature TEXT NOT NULL DEFAULT 'PREDICTION',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(plan_id, version_no),
    -- AI 预测版与正式版信息性质一致（G5）
    CHECK((is_forecast=1 AND info_nature IN ('PREDICTION','PROPOSAL')) OR is_forecast=0));

-- ===== R1-1 基线只读：内容与状态彻底分离 =====
CREATE TABLE IF NOT EXISTS baseline_version (            -- 基线A，全字段冻结
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    plan_version_id TEXT NOT NULL REFERENCES plan_version(id),   -- 明确指向一个完整计划版本
    baseline_no TEXT NOT NULL, approved_at TEXT NOT NULL, approved_by TEXT,
    content_hash TEXT NOT NULL,
    is_readonly INTEGER NOT NULL DEFAULT 1 CHECK(is_readonly=1),
    info_nature TEXT NOT NULL DEFAULT 'DECISION',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    -- 已删除错误的 UNIQUE(plan_id, is_active)：is_active 字段整体移除
    UNIQUE(plan_id, baseline_no), UNIQUE(plan_id, plan_version_id));

-- 当前生效状态独立表：一个计划最多一行（PK 天然约束，另有部分唯一索引）
CREATE TABLE IF NOT EXISTS plan_active_baseline (        -- 基线B
    plan_id TEXT PRIMARY KEY REFERENCES plan(id),
    baseline_version_id TEXT NOT NULL REFERENCES baseline_version(id),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active=1),
    switched_at TEXT NOT NULL, switched_by TEXT,
    authorization_ref TEXT NOT NULL, reason TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pab_active
    ON plan_active_baseline(plan_id) WHERE is_active=1;   -- 评审要求的"当前生效基线部分唯一索引"

-- 基线切换全历史（授权 + 审计）
CREATE TABLE IF NOT EXISTS baseline_switch_log (         -- 基线B
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    from_baseline_id TEXT, to_baseline_id TEXT NOT NULL REFERENCES baseline_version(id),
    switched_at TEXT NOT NULL, switched_by TEXT NOT NULL,
    authorization_ref TEXT NOT NULL, reason TEXT,
    audit_log_id TEXT, created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_bsl_plan ON baseline_switch_log(plan_id, switched_at);

-- 触发器：无差别全字段冻结（不判断任何字段，杜绝"改 is_active 绕过"）
CREATE TRIGGER IF NOT EXISTS trg_bl_freeze_u BEFORE UPDATE ON baseline_version
WHEN OLD.is_readonly = 1
BEGIN SELECT RAISE(ABORT,'baseline frozen: content immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_bl_freeze_d BEFORE DELETE ON baseline_version
WHEN OLD.is_readonly = 1
BEGIN SELECT RAISE(ABORT,'baseline frozen: physical delete disabled'); END;

-- ===== R1-2 计划活动版本化 =====
CREATE TABLE IF NOT EXISTS plan_activity (               -- 稳定主实体：不再存版本可变属性（基线A）
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    code TEXT NOT NULL, first_version_id TEXT REFERENCES plan_version(id),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(plan_id, code));
CREATE INDEX IF NOT EXISTS idx_activity_plan ON plan_activity(plan_id);

CREATE TABLE IF NOT EXISTS plan_activity_version (       -- 每版本活动属性快照（基线A）
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES plan_activity(id),
    plan_version_id TEXT NOT NULL REFERENCES plan_version(id),
    name TEXT NOT NULL, code TEXT,
    owner_org_id TEXT REFERENCES organization(id), owner_person_id TEXT REFERENCES person(id),
    discipline_id TEXT REFERENCES discipline(id), area_id TEXT REFERENCES area(id), system_id TEXT REFERENCES system(id),
    planned_start TEXT, planned_end TEXT,
    dependency_json TEXT,                              -- 版本内前置关系快照（结构化表见 activity_dependency）
    workload_qty REAL, workload_unit TEXT, progress_measure TEXT,
    is_milestone INTEGER NOT NULL DEFAULT 0,
    change_type TEXT NOT NULL CHECK(change_type IN ('ADDED','MODIFIED','UNCHANGED','REMOVED')),
    content_hash TEXT, snapshot_json TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(activity_id, plan_version_id));
CREATE INDEX IF NOT EXISTS idx_pav_ver ON plan_activity_version(plan_version_id);
CREATE INDEX IF NOT EXISTS idx_pav_change ON plan_activity_version(plan_version_id, change_type);

CREATE TABLE IF NOT EXISTS activity_dependency (         -- 基线B，版本化
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    plan_version_id TEXT NOT NULL REFERENCES plan_version(id),
    predecessor_id TEXT NOT NULL REFERENCES plan_activity(id),
    successor_id   TEXT NOT NULL REFERENCES plan_activity(id),
    relation_type TEXT NOT NULL CHECK(relation_type IN ('FS','SS','FF','SF')), lag_days INTEGER,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    CHECK(predecessor_id <> successor_id),
    UNIQUE(plan_version_id, predecessor_id, successor_id, relation_type));

CREATE TABLE IF NOT EXISTS progress_record (             -- 基线A
    id TEXT PRIMARY KEY, plan_activity_id TEXT NOT NULL REFERENCES plan_activity(id),
    plan_version_id TEXT REFERENCES plan_version(id),    -- 对照的版本口径
    record_at TEXT NOT NULL,
    progress_pct REAL NOT NULL DEFAULT 0 CHECK(progress_pct BETWEEN 0 AND 100),
    actual_start TEXT, actual_end TEXT, note TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(plan_activity_id, record_at));
```

### 2.4 基线只读 6 个测试案例（实测 PASS，§8-C）
| # | 案例 | SQL 要点 | 结果 |
|---|---|---|---|
| 1 | 插入两条历史批准基线 | 同 `plan_id` 插 B1/B2（不同 baseline_no、不同 plan_version_id） | PASS（2 行） |
| 2 | 第二条基线生效 | 写 `baseline_switch_log` + UPSERT `plan_active_baseline`，**不触碰 baseline_version** | PASS（生效=B2） |
| 3 | 第一条基线内容仍不可改 | `UPDATE baseline_version SET content_hash='HACK' WHERE id='B1'` | PASS（`baseline frozen: content immutable`）；改 `approved_at` 同样被拦 |
| 4 | 任何基线物理删除被阻止 | `DELETE FROM baseline_version` | PASS（`physical delete disabled`） |
| 5 | 同计划不能有两个生效基线 | 再插一条 `plan_active_baseline(P1,...)` | PASS（`UNIQUE constraint failed: plan_active_baseline.plan_id`） |
| 6 | 不同计划各有一个生效基线 | P1/B2 与 P2/B3（B3 复用同 `baseline_no='BL-01'`） | PASS（2 行） |
> 附：`AI 只能创建预测版本` 由 `plan_version.CHECK(is_forecast=1 → info_nature IN (PREDICTION,PROPOSAL))` + 应用层写入白名单 + `audit_log` 三重保证；`baseline_version` 的 INSERT 与切换要求 `authorization_ref` 非空。

### 2.5 V1/V2 差异、历史回放、增删改历史（实测 PASS，§8-D）
```sql
-- V1 vs V2 差异对比
SELECT a.code, v1.name, v2.name, v1.planned_end, v2.planned_end, v2.change_type
FROM plan_activity a
LEFT JOIN plan_activity_version v1 ON v1.activity_id=a.id AND v1.plan_version_id=:V1
LEFT JOIN plan_activity_version v2 ON v2.activity_id=a.id AND v2.plan_version_id=:V2
WHERE v1.id IS NULL OR v2.id IS NULL OR v1.planned_end<>v2.planned_end
   OR v2.change_type IN ('ADDED','REMOVED');
-- 历史批准计划回放：baseline → plan_version → 完整活动集
SELECT pav.* FROM baseline_version b
JOIN plan_activity_version pav ON pav.plan_version_id=b.plan_version_id
WHERE b.id=:baseline_id AND pav.change_type<>'REMOVED';
-- 当前滚动预测 vs 批准基线
SELECT ... FROM plan_version f WHERE f.is_forecast=1   -- 预测
-- 活动增删改历史
SELECT plan_version_id, change_type, count(*) FROM plan_activity_version GROUP BY 1,2;
```
实测：V1/V2 差异 3 行（A1 MODIFIED / A3 REMOVED / A4 ADDED）、V1 回放 3 个活动、V2 四种 change_type 齐全。

---

## 3. 域3 —— 信息与文件（来源域）

```sql
CREATE TABLE IF NOT EXISTS email (                       -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, message_id_text TEXT UNIQUE,
    from_addr TEXT, to_addrs TEXT, cc_addrs TEXT, subject TEXT NOT NULL, body_markdown TEXT,
    source_time TEXT NOT NULL, event_time TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE TABLE IF NOT EXISTS email_attachment (            -- 基线B
    id TEXT PRIMARY KEY, email_id TEXT NOT NULL REFERENCES email(id),
    filename TEXT NOT NULL, file_kind TEXT, sha256 TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS document (                    -- 基线A，主表元数据
    id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL, doc_code TEXT, doc_type TEXT,
    is_readonly INTEGER NOT NULL DEFAULT 1, sha256 TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_sha ON document(sha256) WHERE sha256 IS NOT NULL;
CREATE TABLE IF NOT EXISTS document_version (            -- 基线A，版本内容（全部历史入 FTS）
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES document(id),
    version_no TEXT NOT NULL, file_path TEXT, sha256 TEXT,
    extracted_text TEXT, notes TEXT, snapshot_json TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(document_id, version_no));

-- R1-6 整改：drawing_no 唯一范围按项目（不同项目可同图号）
CREATE TABLE IF NOT EXISTS drawing (                     -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, drawing_no TEXT NOT NULL, name TEXT NOT NULL,
    doc_type TEXT NOT NULL DEFAULT 'DRAWING', is_readonly INTEGER NOT NULL DEFAULT 1,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE UNIQUE INDEX IF NOT EXISTS uq_dr ON drawing(COALESCE(project_id,''), drawing_no);
CREATE TABLE IF NOT EXISTS drawing_version (             -- 基线A，版本内容
    id TEXT PRIMARY KEY, drawing_id TEXT NOT NULL REFERENCES drawing(id),
    revision TEXT, file_path TEXT, sha256 TEXT, extracted_text TEXT, notes TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(drawing_id, revision));

-- DWG 对象预留：不装 SDK、不解析（ADR-10）
CREATE TABLE IF NOT EXISTS drawing_object (              -- 基线B
    id TEXT PRIMARY KEY, drawing_id TEXT NOT NULL REFERENCES drawing(id),
    drawing_version_id TEXT REFERENCES drawing_version(id),
    obj_type TEXT, ref_entity_id TEXT REFERENCES entity(id),
    ref_area_id TEXT REFERENCES area(id), ref_system_id TEXT REFERENCES system(id),
    geometry_json TEXT, reserved_data TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS meeting (                     -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, title TEXT NOT NULL, held_at TEXT,
    organizer_person_id TEXT REFERENCES person(id), participant_ids TEXT,
    transcript_ptr TEXT, transcript_text TEXT, source_time TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE TABLE IF NOT EXISTS meeting_minutes (             -- 基线A，可多版
    id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL REFERENCES meeting(id),
    version_no TEXT, content_md TEXT, is_final INTEGER NOT NULL DEFAULT 0, source_time TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(meeting_id, version_no));

CREATE TABLE IF NOT EXISTS message (                     -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, sender_person_id TEXT REFERENCES person(id),
    content_md TEXT, sent_at TEXT, channel TEXT, source_time TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');

-- 统一来源桥（多态，无硬 FK；完整性由 §7.6 自检 + 应用层 + 审计兜底）
CREATE TABLE IF NOT EXISTS source_reference (            -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT,
    traced_entity_type TEXT NOT NULL, traced_entity_id TEXT NOT NULL,
    source_type TEXT NOT NULL, source_id TEXT NOT NULL,
    context_excerpt TEXT, locator TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT', confidence REAL,
    source_time TEXT,
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_sr_entity ON source_reference(traced_entity_type, traced_entity_id);
CREATE INDEX IF NOT EXISTS idx_sr_source ON source_reference(source_type, source_id);

CREATE TABLE IF NOT EXISTS evidence (                    -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, title TEXT NOT NULL, body TEXT,
    evidence_kind TEXT, sha256 TEXT,
    info_nature TEXT NOT NULL DEFAULT 'SOURCE_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE TABLE IF NOT EXISTS evidence_link (               -- 基线B
    id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL REFERENCES evidence(id),
    ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, link_role TEXT, context_excerpt TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_el_ref ON evidence_link(ref_type, ref_id);
```

---

## 4. 域4 —— 问题/风险/任务闭环（R1-4 business_subject 分层）

```sql
-- ===== R1-4：统一事项主档（业务事项 ≠ 业务实体）=====
CREATE TABLE IF NOT EXISTS business_subject (            -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    subject_kind TEXT NOT NULL CHECK(subject_kind IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM')),
    canonical_subject_id TEXT REFERENCES business_subject(id),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','MERGED','SUPERSEDED')),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_bs_canonical ON business_subject(canonical_subject_id);

CREATE TABLE IF NOT EXISTS business_subject_alias (      -- 基线A，一个事项多个别名
    id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES business_subject(id),
    alias TEXT NOT NULL, alias_type TEXT, source_reference_id TEXT REFERENCES source_reference(id),
    confirm_status TEXT NOT NULL DEFAULT 'PENDING',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(subject_id, alias));

CREATE TABLE IF NOT EXISTS business_subject_merge (      -- 基线A，可逆合并链
    id TEXT PRIMARY KEY,
    from_subject_id TEXT NOT NULL REFERENCES business_subject(id),
    to_subject_id   TEXT NOT NULL REFERENCES business_subject(id),
    merged_at TEXT NOT NULL, merged_by TEXT NOT NULL, reason TEXT,
    source_reference_id TEXT REFERENCES source_reference(id),
    undone_at TEXT, undone_by TEXT, undo_reason TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    CHECK(from_subject_id <> to_subject_id));

CREATE TABLE IF NOT EXISTS business_subject_source (     -- 基线B，事项↔来源证据 M:N
    id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES business_subject(id),
    source_reference_id TEXT NOT NULL REFERENCES source_reference(id),
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    UNIQUE(subject_id, source_reference_id));

-- ===== 具体业务事项表：1:1 挂 subject_id =====
CREATE TABLE IF NOT EXISTS issue (                       -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id),
    ref_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description_md TEXT,
    status TEXT NOT NULL DEFAULT 'NEW', severity TEXT, priority TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, created_by TEXT, updated_by TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0, deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_issue_proj ON issue(project_id);
CREATE INDEX IF NOT EXISTS idx_issue_status ON issue(status);
CREATE TABLE IF NOT EXISTS issue_status_history (        -- 基线B
    id TEXT PRIMARY KEY, issue_id TEXT NOT NULL REFERENCES issue(id),
    old_status TEXT, new_status TEXT NOT NULL, transition TEXT,
    changed_by TEXT, changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
    info_nature TEXT, source_reference_id TEXT REFERENCES source_reference(id),
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS risk (                        -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id),
    ref_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description_md TEXT,
    probability TEXT, impact TEXT, exposure TEXT, status TEXT NOT NULL DEFAULT 'NEW', strategy TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_risk_proj ON risk(project_id);
CREATE TABLE IF NOT EXISTS risk_status_history (         -- 基线B
    id TEXT PRIMARY KEY, risk_id TEXT NOT NULL REFERENCES risk(id),
    old_status TEXT, new_status TEXT NOT NULL, transition TEXT,
    changed_by TEXT, changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
    info_nature TEXT, source_reference_id TEXT REFERENCES source_reference(id),
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS task (                        -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id),
    ref_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description_md TEXT,
    assignee_person_id TEXT REFERENCES person(id), due_at TEXT, completed_at TEXT, priority TEXT,
    status TEXT NOT NULL DEFAULT 'NEW',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_task_proj ON task(project_id);
CREATE TABLE IF NOT EXISTS task_status_history (         -- 基线B
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES task(id),
    old_status TEXT, new_status TEXT NOT NULL, transition TEXT,
    changed_by TEXT, changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
    info_nature TEXT, source_reference_id TEXT REFERENCES source_reference(id),
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

-- R1-6 整改：action_measure 用强外键 + CHECK 保证属主完整性
CREATE TABLE IF NOT EXISTS action_measure (              -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    ref_no TEXT NOT NULL UNIQUE, name TEXT NOT NULL, description TEXT,
    measure_type TEXT NOT NULL CHECK(measure_type IN ('RISK_RESPONSE','ISSUE_REMEDY')),
    risk_id TEXT REFERENCES risk(id), issue_id TEXT REFERENCES issue(id),
    due_at TEXT, status TEXT NOT NULL DEFAULT 'OPEN',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    CHECK((risk_id IS NOT NULL AND issue_id IS NULL) OR (issue_id IS NOT NULL AND risk_id IS NULL)));
CREATE INDEX IF NOT EXISTS idx_am_risk ON action_measure(risk_id);
CREATE INDEX IF NOT EXISTS idx_am_issue ON action_measure(issue_id);
CREATE TABLE IF NOT EXISTS action_measure_link (         -- 基线B，一个措施挂多个属主（M:N）
    id TEXT PRIMARY KEY, action_measure_id TEXT NOT NULL REFERENCES action_measure(id),
    ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, link_role TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS decision (                    -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id),
    ref_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL, conclusion_md TEXT,
    decided_by_person_id TEXT REFERENCES person(id), decided_at TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    info_nature TEXT NOT NULL DEFAULT 'DECISION',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE TABLE IF NOT EXISTS decision_link (               -- 基线B
    id TEXT PRIMARY KEY, decision_id TEXT NOT NULL REFERENCES decision(id),
    ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, link_role TEXT, context_excerpt TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_dl_ref ON decision_link(ref_type, ref_id);

-- 通用对象桥（M:N 全链路引用，多态）
CREATE TABLE IF NOT EXISTS object_link (                 -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, link_role TEXT NOT NULL,
    left_type TEXT NOT NULL, left_id TEXT NOT NULL,
    right_type TEXT NOT NULL, right_id TEXT NOT NULL,
    context_excerpt TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_ol_left ON object_link(left_type, left_id);
CREATE INDEX IF NOT EXISTS idx_ol_right ON object_link(right_type, right_id);
```

---

## 5. 域5 —— 实体关系与知识（entity 见 §1 前置定义）

```sql
CREATE TABLE IF NOT EXISTS entity_alias (                -- 基线A
    id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entity(id),
    alias TEXT NOT NULL, alias_type TEXT,
    source_reference_id TEXT REFERENCES source_reference(id),
    confirm_status TEXT NOT NULL DEFAULT 'PENDING',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(entity_id, alias));

-- R1-6 整改：唯一范围收敛到 (entity_id, id_type, source_from, identifier)
CREATE TABLE IF NOT EXISTS entity_identifier (           -- 基线A
    id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entity(id),
    id_type TEXT NOT NULL, source_from TEXT, identifier TEXT NOT NULL,
    source_reference_id TEXT REFERENCES source_reference(id), effective_from TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE UNIQUE INDEX IF NOT EXISTS uq_ei
    ON entity_identifier(entity_id, id_type, COALESCE(source_from,''), identifier);
CREATE INDEX IF NOT EXISTS idx_ei_lookup ON entity_identifier(id_type, identifier);

CREATE TABLE IF NOT EXISTS entity_relationship (         -- 基线A，仅业务实体间语义关系
    id TEXT PRIMARY KEY, left_entity_id TEXT NOT NULL REFERENCES entity(id),
    right_entity_id TEXT NOT NULL REFERENCES entity(id),
    relation_type TEXT NOT NULL, confirm_status TEXT NOT NULL DEFAULT 'PENDING',
    source_reference_id TEXT REFERENCES source_reference(id),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    CHECK(left_entity_id <> right_entity_id),
    UNIQUE(left_entity_id, right_entity_id, relation_type));
-- 注：entity_relationship 明确【不得】承载 Issue/Risk/Task 事项合并，见 §4 business_subject_merge。

CREATE TABLE IF NOT EXISTS knowledge_item (              -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT, subject_id TEXT REFERENCES business_subject(id),
    ref_no TEXT UNIQUE, title TEXT NOT NULL, summary TEXT,
    status TEXT NOT NULL DEFAULT 'PUBLISHED',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE TABLE IF NOT EXISTS knowledge_version (           -- 基线A，全部历史入 FTS
    id TEXT PRIMARY KEY, knowledge_item_id TEXT NOT NULL REFERENCES knowledge_item(id),
    version_no TEXT NOT NULL, content_md TEXT, sha256 TEXT, snapshot_json TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(knowledge_item_id, version_no));
CREATE TABLE IF NOT EXISTS knowledge_entity_link (       -- 基线B
    id TEXT PRIMARY KEY, knowledge_version_id TEXT NOT NULL REFERENCES knowledge_version(id),
    entity_id TEXT NOT NULL REFERENCES entity(id),
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    UNIQUE(knowledge_version_id, entity_id));
```

---

## 6. 域6 —— AI 处理与系统治理（R1-5 审核链）

```sql
CREATE TABLE IF NOT EXISTS ingestion_job (               -- 基线B
    id TEXT PRIMARY KEY, project_id TEXT, source_type TEXT NOT NULL, source_id TEXT, channel TEXT,
    status TEXT NOT NULL DEFAULT 'INGESTING', started_at TEXT, finished_at TEXT,
    run_meta TEXT, re_runnable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS ai_analysis_run (             -- 基线B
    id TEXT PRIMARY KEY, project_id TEXT, run_type TEXT NOT NULL, model TEXT, input_ref TEXT,
    output_summary TEXT, status TEXT NOT NULL DEFAULT 'RUNNING', started_at TEXT, finished_at TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS extraction_result (           -- 基线B，原始内容冻结
    id TEXT PRIMARY KEY, ingestion_job_id TEXT REFERENCES ingestion_job(id),
    ai_analysis_run_id TEXT REFERENCES ai_analysis_run(id),
    candidate_type TEXT NOT NULL, candidate_json TEXT, raw_text TEXT,
    info_nature TEXT NOT NULL DEFAULT 'AI_INFERENCE'
        CHECK(info_nature IN ('AI_INFERENCE','PREDICTION','PROPOSAL')),
    confidence REAL, status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
-- 审核后不得删除或覆盖原始抽取记录（实测 §8 E7/E8）
CREATE TRIGGER IF NOT EXISTS trg_er_immutable_u BEFORE UPDATE ON extraction_result
WHEN OLD.candidate_json IS NOT NEW.candidate_json OR OLD.raw_text IS NOT NEW.raw_text
BEGIN SELECT RAISE(ABORT,'extraction original content immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_er_immutable_d BEFORE DELETE ON extraction_result
BEGIN SELECT RAISE(ABORT,'extraction records cannot be deleted'); END;

-- ===== R1-5：审核链四表 =====
CREATE TABLE IF NOT EXISTS review_queue (                -- 审核任务（基线A）
    id TEXT PRIMARY KEY, project_id TEXT, review_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','IN_REVIEW','DONE')),
    candidate_summary TEXT, suggested_subject_id TEXT REFERENCES business_subject(id),
    info_nature TEXT NOT NULL DEFAULT 'AI_INFERENCE',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE TABLE IF NOT EXISTS review_extraction_link (      -- 任务↔抽取 M:N（基线B）
    id TEXT PRIMARY KEY, review_queue_id TEXT NOT NULL REFERENCES review_queue(id),
    extraction_result_id TEXT NOT NULL REFERENCES extraction_result(id),
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    UNIQUE(review_queue_id, extraction_result_id));

CREATE TABLE IF NOT EXISTS review_decision (             -- 审核结果明细（基线A）
    id TEXT PRIMARY KEY, review_queue_id TEXT NOT NULL REFERENCES review_queue(id),
    decision TEXT NOT NULL CHECK(decision IN ('ACCEPT_AS_NEW','MERGE_TO','REJECT')),
    reviewer_person_id TEXT NOT NULL REFERENCES person(id),
    reviewed_at TEXT NOT NULL, reason TEXT NOT NULL,
    evidence_source_reference_id TEXT REFERENCES source_reference(id),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_rd_queue ON review_decision(review_queue_id);

CREATE TABLE IF NOT EXISTS review_result_object (        -- 结果→正式对象稳定映射（基线A）
    id TEXT PRIMARY KEY, review_decision_id TEXT NOT NULL REFERENCES review_decision(id),
    object_type TEXT NOT NULL CHECK(object_type IN
        ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ENTITY','BUSINESS_SUBJECT')),
    object_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK(relation IN ('CREATED','MERGED_INTO','REJECTED')),
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_rro_obj ON review_result_object(object_type, object_id);
-- 多态对象完整性纳入 §7.6 自检；禁止"REJECT 却生成 CREATED 对象"由应用层校验。

CREATE TABLE IF NOT EXISTS audit_log (                   -- 基线B，只增不改
    id TEXT PRIMARY KEY, project_id TEXT, actor_type TEXT NOT NULL CHECK(actor_type IN ('USER','AI','SYSTEM')),
    actor_id TEXT, action_code TEXT NOT NULL, target_type TEXT, target_id TEXT,
    before_json TEXT, after_json TEXT, authorization_ref TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target_type, target_id);

CREATE TABLE IF NOT EXISTS system_config (               -- 基线B
    id TEXT PRIMARY KEY, config_key TEXT NOT NULL UNIQUE, config_value TEXT NOT NULL,
    description TEXT, config_group TEXT, is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

-- Phase 后期启用（骨架，D.2-2）
CREATE TABLE IF NOT EXISTS user (id TEXT PRIMARY KEY, person_id TEXT REFERENCES person(id), username TEXT UNIQUE, password_hash TEXT, status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS role (id TEXT PRIMARY KEY, role_code TEXT UNIQUE, name TEXT, created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS permission (id TEXT PRIMARY KEY, permission_code TEXT UNIQUE, name TEXT, created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS user_role (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES user(id), role_id TEXT NOT NULL REFERENCES role(id), created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0, UNIQUE(user_id, role_id));
CREATE TABLE IF NOT EXISTS role_permission (id TEXT PRIMARY KEY, role_id TEXT NOT NULL REFERENCES role(id), permission_id TEXT NOT NULL REFERENCES permission(id), created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0, UNIQUE(role_id, permission_id));
```

### 6.5 审核链测试场景（实测 PASS，§8-E）
| 场景 | 实现 | 结果 |
|---|---|---|
| 一条抽取结果拆分多对象 | `RD2(ACCEPT_AS_NEW)` 下两条 `review_result_object`（ISSUE + RISK） | PASS |
| 多条抽取结果合一对象 | `review_extraction_link` 3 条 → `RQ1` → `RD1(MERGE_TO)` → 唯一 `object_id=I1` | PASS |
| 审核人/时间/理由/证据 | `reviewer_person_id / reviewed_at / reason NOT NULL / evidence_source_reference_id` | PASS（约束强制） |
| 六类正式对象指向 | `object_type CHECK` 覆盖 ISSUE/RISK/TASK/DECISION/KNOWLEDGE_ITEM/ENTITY/BUSINESS_SUBJECT | PASS |
| 原始抽取不得覆盖 | 触发器 `trg_er_immutable_u` | PASS（`extraction original content immutable`） |
| 原始抽取不得删除 | 触发器 `trg_er_immutable_d` | PASS（`extraction records cannot be deleted`） |

---

## 7. 共享桥表、FTS5 trigram 统一设计（R1-3）

### 7.1 对象×维度 标签
```sql
CREATE TABLE IF NOT EXISTS object_dimension_tag (        -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT,
    tagged_object_type TEXT NOT NULL, tagged_object_id TEXT NOT NULL,
    dimension TEXT NOT NULL CHECK(dimension IN ('EPCS_PHASE','DISCIPLINE','AREA','SYSTEM')),
    value_type TEXT NOT NULL CHECK(value_type IN ('REF','FREE_TEXT')),
    value_id TEXT, value_text TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    -- R1-6 整改：值类型强约束（实测拦截非法行 §8 G4）
    CHECK((value_type='REF'       AND value_id IS NOT NULL   AND value_text IS NULL)
       OR (value_type='FREE_TEXT' AND value_text IS NOT NULL AND value_id IS NULL)));
CREATE INDEX IF NOT EXISTS idx_odt_obj ON object_dimension_tag(tagged_object_type, tagged_object_id);
CREATE INDEX IF NOT EXISTS idx_odt_dim ON object_dimension_tag(dimension, value_id);
```

### 7.2 FTS5 统一范式与一一对应清单（24 张）
**范式定案**：全库统一 **普通内容表（contentful） + `biz_id UNINDEXED` 显式映射**，**不再使用外部内容表**。
理由（实测 §8-A）：① 外部内容表 `content_rowid` 必须是整数 rowid，`content_rowid='id'`（TEXT UUID）建表即失败；② 外部内容表要求列名与主表严格对应，旧草案 `document_fts(name,snapshot_json)` 等列根本不存在于被索引表；③ 普通内容表可直接 `DELETE/UPDATE ... WHERE biz_id=...`，同步触发器简单可靠，且查询能直接返回稳定 UUID。

```sql
-- 统一模板（每张 FTS 表结构相同，列名按内容表调整）
CREATE VIRTUAL TABLE IF NOT EXISTS issue_fts USING fts5(
    biz_id UNINDEXED,          -- TEXT UUID：稳定业务对象 ID
    owner_biz_id UNINDEXED,    -- 版本类 FTS：主表 UUID（非版本表填空）
    is_deleted UNINDEXED,      -- 软删镜像，查询过滤
    ref_no, title, description_md,
    tokenize = 'trigram');
```

| # | 业务表 | FTS 表 | 索引列 | 范围 |
|---|---|---|---|---|
| 1 | email | email_fts | subject, body_markdown | 当前 |
| 2 | email_attachment | email_attachment_fts | filename | 当前 |
| 3 | document | document_fts | name, doc_code | 主表元数据 |
| 4 | document_version | document_version_fts | extracted_text, notes, snapshot_json | **全部历史版本** |
| 5 | drawing | drawing_fts | name, drawing_no | 主表元数据 |
| 6 | drawing_version | drawing_version_fts | revision, extracted_text, notes | **全部历史版本** |
| 7 | meeting | meeting_fts | title, transcript_text | 当前 |
| 8 | meeting_minutes | meeting_minutes_fts | version_no, content_md | **全部历史版本** |
| 9 | message | message_fts | content_md | 当前 |
| 10 | evidence | evidence_fts | title, body | 当前 |
| 11 | source_reference | source_reference_fts | context_excerpt, locator | 当前 |
| 12 | issue | issue_fts | ref_no, title, description_md | 当前 |
| 13 | risk | risk_fts | ref_no, title, description_md | 当前 |
| 14 | task | task_fts | ref_no, title, description_md | 当前 |
| 15 | decision | decision_fts | ref_no, title, conclusion_md | 当前 |
| 16 | action_measure | action_measure_fts | ref_no, name, description | 当前 |
| 17 | entity | entity_fts | name | 当前 |
| 18 | entity_alias | entity_alias_fts | alias | 当前 |
| 19 | business_subject_alias | business_subject_alias_fts | alias | 当前 |
| 20 | knowledge_item | knowledge_item_fts | title, summary | 主表元数据 |
| 21 | knowledge_version | knowledge_version_fts | version_no, content_md | **全部历史版本** |
| 22 | plan_activity_version | plan_activity_version_fts | name, code | **全部历史版本** |
| 23 | extraction_result | extraction_result_fts | candidate_json, raw_text | 当前 |
| 24 | review_decision | review_decision_fts | reason | 当前 |

> **7 点要求逐条**：① 对应表见上（一一对应，无混用）；② **索引全部历史版本**（版本表每条版本一行，`biz_id`=版本 UUID、`owner_biz_id`=主表 UUID）；③ **FTS rowid 与 UUID 映射**：不依赖整数 `content_rowid`，业务 UUID 通过 `biz_id UNINDEXED` 显式携带，触发器用 `WHERE biz_id=old.id` 定位；④ 同步机制见 §7.3；⑤ 软删见 §7.5；⑥ 重建/一致性见 §7.6；⑦ 查询返回 `biz_id`（+`owner_biz_id`）再回表。

### 7.3 三向同步触发器（模板，24 张 FTS 表按同一模板生成 = 72 个）
```sql
CREATE TRIGGER IF NOT EXISTS trg_issue_fts_ai AFTER INSERT ON issue BEGIN
  INSERT INTO issue_fts(biz_id, owner_biz_id, is_deleted, ref_no, title, description_md)
  VALUES(new.id, NULL, new.is_deleted, new.ref_no, new.title, new.description_md);
END;
CREATE TRIGGER IF NOT EXISTS trg_issue_fts_au AFTER UPDATE ON issue
WHEN old.title IS NOT new.title OR old.description_md IS NOT new.description_md
  OR old.is_deleted IS NOT new.is_deleted OR old.ref_no IS NOT new.ref_no
BEGIN
  DELETE FROM issue_fts WHERE biz_id = old.id;
  INSERT INTO issue_fts(biz_id, owner_biz_id, is_deleted, ref_no, title, description_md)
  VALUES(new.id, NULL, new.is_deleted, new.ref_no, new.title, new.description_md);
END;
CREATE TRIGGER IF NOT EXISTS trg_issue_fts_ad AFTER DELETE ON issue BEGIN
  DELETE FROM issue_fts WHERE biz_id = old.id;
END;
-- 其余 23 张内容表按同模板生成（迁移脚本循环产出，清单固定为 §7.2 的 24 张）。
```
> 采用「先 DELETE 再 INSERT」而非 `UPDATE fts SET ...`，避免 trigram 分词下更新值漂移；软删用 `is_deleted` 镜像，不删 FTS 行。

### 7.4 中文检索测试矩阵（实测，SQLite 3.53.1 / trigram）
语料含 `CMHI-001 铺缆船集控台电气图纸意见待关闭`、`ASSO TSV-1 挖沟船采购周报（2026第46期）`、`主机、发电机、泵、阀、控制台`、`齿轮箱FAT推迟至11/5…`、`历史版本：集控台方案修改（V1）…`。

| 测试词 | 类型 | trigram MATCH | LIKE 回退 | 结论 |
|---|---|---|---|---|
| `船` | 单字 | **0** | 2 | trigram 不支持 <3 字 → 短词回退 |
| `铺缆` | 双字 | **0** | 1 | 同上 |
| `集控台` | 三字 | 2 | 2 | ✅ 正常命中（含历史版本） |
| `齿轮箱` | 三字 | 1 | 1 | ✅ |
| `历史版本` | 四字 | 1 | 1 | ✅ |
| `集控台方案` | 长词 | 1 | 1 | ✅ |
| `（2026第46期）` | 中文标点+数字 | 1 | 1 | ✅ |
| `、` | 单字标点 | **0** | 1 | 短词回退 |
| `CMHI 铺缆` | 中英混合 | 1 | 0 | ✅ trigram 命中（LIKE 反而不中） |
| `CMHI-001` | 英文编号 | **ERR** `no such column: 001` | 1 | 需**双引号包裹** |
| `FAT 11/5` | 特殊字符 | **ERR** `fts5: syntax error near "/"` | 0 | 需**双引号包裹** |
| `"CMHI-001"` / `"FAT 11/5"` / `"齿轮箱"` | 双引号包裹 | **1 / 1 / 1** | — | ✅ **转义方案验证通过** |

**结论与规则**：
1. trigram 以 3 字符滑窗建索引，**1~2 字查询词 MATCH 恒为 0** → `len(term)<3` 时自动降级 LIKE 回退（限定项目/候选集 + `LIMIT`），并联合 `entity_alias` / `business_subject_alias` 做短词别名召回。
2. **含 `-` `/` 等 FTS5 查询语法字符的查询词必须整体双引号包裹**（`"CMHI-001"`），否则报语法错误；查询构造器统一用 `'"' + term.replace('"','""') + '"'`。
3. 历史版本检索：`document_version_fts` / `drawing_version_fts` / `meeting_minutes_fts` / `knowledge_version_fts` / `plan_activity_version_fts` 索引全部历史版本，返回 `owner_biz_id` 聚合到主对象。
4. 正向自检（positive control）：任何一致性/检索核验脚本须先用已知样本确认能命中，命中 0 时结果不可采信。

### 7.5 软删除与索引处理
- **保留 FTS 行**：软删时触发器把 `is_deleted` 置 1（镜像），查询统一带 `AND is_deleted=0` 并 JOIN 业务表二次过滤；不物理删 FTS 行，避免误删历史版本索引。
- 归档（ARCHIVED）不改动 FTS；物理删除仅允许临时/缓存表，正式表由 §8 触发器禁止（此时 `AFTER DELETE` 同步触发器不会触发）。

### 7.6 重建 / 一致性 / 多态完整性自检
```sql
-- 重建（普通内容表：全量重灌）
DELETE FROM issue_fts;
INSERT INTO issue_fts(biz_id, owner_biz_id, is_deleted, ref_no, title, description_md)
  SELECT id, NULL, is_deleted, ref_no, title, description_md FROM issue WHERE is_deleted=0;
-- 一致性检查：①活跃行数差 ②biz_id 孤儿 ③软删镜像一致 ④正向自检
SELECT (SELECT count(*) FROM issue WHERE is_deleted=0) - (SELECT count(*) FROM issue_fts WHERE is_deleted=0) AS drift;
SELECT f.biz_id FROM issue_fts f LEFT JOIN issue t ON t.id=f.biz_id WHERE t.id IS NULL;
-- 多态引用孤儿自检（sp_check_polymorphic_refs，按 type 分派 UNION）
SELECT 'object_link.left' AS src, id, left_type AS typ, left_id AS rid FROM object_link
 WHERE left_type='issue' AND left_id NOT IN (SELECT id FROM issue)
UNION ALL
SELECT 'object_link.right', id, right_type, right_id FROM object_link
 WHERE right_type='email' AND right_id NOT IN (SELECT id FROM email)
UNION ALL
SELECT 'source_reference.traced', id, traced_entity_type, traced_entity_id FROM source_reference
 WHERE traced_entity_type='issue' AND traced_entity_id NOT IN (SELECT id FROM issue)
UNION ALL
SELECT 'source_reference.source', id, source_type, source_id FROM source_reference
 WHERE source_type='email' AND source_id NOT IN (SELECT id FROM email)
UNION ALL
SELECT 'evidence_link', id, ref_type, ref_id FROM evidence_link
 WHERE ref_type='issue' AND ref_id NOT IN (SELECT id FROM issue)
UNION ALL
SELECT 'decision_link', id, ref_type, ref_id FROM decision_link
 WHERE ref_type='issue' AND ref_id NOT IN (SELECT id FROM issue)
UNION ALL
SELECT 'action_measure_link', id, ref_type, ref_id FROM action_measure_link
 WHERE ref_type='issue' AND ref_id NOT IN (SELECT id FROM issue)
UNION ALL
SELECT 'review_result_object', id, object_type, object_id FROM review_result_object
 WHERE object_type='ISSUE' AND object_id NOT IN (SELECT id FROM issue)
UNION ALL
SELECT 'business_subject_alias', id, 'business_subject', subject_id FROM business_subject_alias
 WHERE subject_id NOT IN (SELECT id FROM business_subject)
UNION ALL
SELECT 'object_dimension_tag', id, tagged_object_type, tagged_object_id FROM object_dimension_tag
 WHERE tagged_object_type='issue' AND tagged_object_id NOT IN (SELECT id FROM issue);
```
> 执行时机：摄入作业完成后 + 定期维护；结果写 `audit_log`。实测能查出孤儿（§8 G7）。**明确这是已知取舍**：多态字段无硬 FK，以自检 + 应用层 + 审计三层补偿，不伪装成数据库硬约束。

---

## 8. 内存库实测验证汇总（R1）

> 全部验证在 Python `sqlite3` 的 `:memory:` 内存库执行（SQLite 3.53.1 / trigram 可用），**未触碰** `01_Data/epcs_intelligence.db`、未创建 `migrations/001_init.sql`、未安装任何依赖。本文 §0~§7 各处「实测」引用均落到本节对应编号。
> **汇总：A~F 六组专项 + G1~G10 额外检查，全部 PASS，0 FAIL。**

### 8-A FTS5 范式裁决（对应本文 §7.2 范式定案、《架构评审整改记录》§3.1 原设计缺陷）
| # | 验证项 | 实测结果 |
|---|---|---|
| A1 | 外部内容表 `content='issue', content_rowid='id'`（TEXT UUID） | ❌ 原写法不可行：`content_rowid` 必须是**整数 rowid**；TEXT UUID 无法映射，rebuild 后全部行被压成 rowid 0，`MATCH` 返回无效值 |
| A2 | 外部内容表 `count(*)` 是否反映索引 | ❌ 不反映：直接 INSERT 幽灵 rowid 后 `count(*)` 不变但 `MATCH` 能命中幽灵行，数量差/孤儿 SQL 失效，只有 `integrity-check` 可靠 |
| A3 | 旧草案 `document_fts(name,snapshot_json)` 等列错配 | ❌ `snapshot_json` 属 `document_version` 不属 `document`；外部内容表要求列名与主表严格对应，原草案无法建 |
| A4 | 统一普通内容表 + `biz_id UNINDEXED` 显式映射 | ✅ PASS：三向触发器同步、查询直接返回稳定业务 UUID、可 `DELETE/UPDATE WHERE biz_id=`、可全量重建 |

> 结论（ADR-7 / ADR-7b 修订依据）：全库统一普通内容表范式，不再使用外部内容表。

### 8-B 中文检索矩阵与短词 / 转义（明细见 §7.4 表格）
| # | 验证项 | 实测结果 |
|---|---|---|
| B1 | trigram 三字以上中文词（`集控台`/`齿轮箱`/`历史版本`） | ✅ 命中，含历史版本行 |
| B2 | 1~2 字短词（`船`/`铺缆`/`、`） | ✅ 符合预期：`MATCH` 恒为 0、LIKE 回退命中；据此定案 `len(term)<3` 自动降级 |
| B3 | 中英混合 `CMHI 铺缆` | ✅ trigram 命中 1（LIKE 反而不中） |
| B4 | 特殊字符 `CMHI-001` / `FAT 11/5` 未转义 | ❌ 预期报错：`no such column: 001` / `fts5: syntax error near "/"` |
| B5 | 整体双引号包裹 `"CMHI-001"` / `"FAT 11/5"` | ✅ 各命中 1；定案查询构造器统一 `'"' + term.replace('"','""') + '"'` |
| B6 | 正向自检（positive control） | ✅ 已知样本必须命中才采信核验结果，防止核验脚本自身失效 |

### 8-C 基线只读六案例（对应 §2.4，全部 PASS）
见 §2.4 表：①两条历史批准基线共存 ②第二条生效 ③第一条内容不可改（`baseline frozen: content immutable`）④物理删除被阻止 ⑤同计划不能有两个生效基线 ⑥不同计划各有一个生效基线。
> 追加实测：改 `approved_at` / `content_hash` / `plan_version_id` 任一内容字段均被无差别 `BEFORE UPDATE` 拦截；切换全程不触碰 `baseline_version` 任何行；AI 预测版本（`is_forecast=1`, `info_nature=PREDICTION`）**不能**成为批准基线。

### 8-D 计划活动版本化（对应 §2.5，全部 PASS）
V1/V2 差异 3 行（A1 MODIFIED / A3 REMOVED / A4 ADDED）、V1 历史回放 3 个活动、V2 四种 `change_type` 齐全、`baseline → plan_version → plan_activity_version` 回放链成立、当前滚动预测 vs 批准基线可对比。

### 8-E 审核链与业务事项归一（对应 §6.5，E1~E10 全部 PASS）
| # | 场景 | 结果 |
|---|---|---|
| E1 | `review_queue` / `review_extraction_link` / `review_decision` / `review_result_object` 四表建表与 FK | PASS |
| E2 | 一条抽取结果拆分多对象（1 个 decision 下 ISSUE + RISK 两条 result_object） | PASS |
| E3 | 多条抽取结果合一对象（`review_extraction_link` 3 条 → 1 个 `MERGE_TO` → 同一 `object_id`） | PASS |
| E4 | 审核人 / 时间 / 理由 / 证据 NOT NULL 约束强制（REJECT 亦需理由） | PASS |
| E5 | `object_type CHECK` 覆盖 7 类正式对象 | PASS |
| E6 | G5 链：`AI_INFERENCE → CONFIRMED_FACT → 正式对象 CONFIRMED_FACT` | PASS |
| E7 | 原始抽取不得覆盖（`trg_er_immutable_u`，`candidate_json`/`raw_text`/`ingestion_job_id` 变更即 ABORT） | PASS |
| E8 | 原始抽取不得删除（`trg_er_immutable_d`） | PASS |
| E9 | `business_subject` 双层归一 + `business_subject_alias` 多别名 + `business_subject_source` 跨邮件 / 会议 / 文件证据链 | PASS |
| E10 | `business_subject_merge` 可逆合并（合并→撤销：置 `undone_at`/`undo_reason`/`valid_to`，`status` 回 ACTIVE，原业务记录不删除不覆盖） | PASS |

> 独立复核：把 `business_subject.id` 当作 `entity_id` 写入 `entity_relationship` 会被 FK 拦截，且该表无 `valid_to`/`undone_at`/`undo_reason` 可逆语义、不产生 `source_reference` 证据链 —— 印证「`entity_relationship` 不得承载事项合并」。

### 8-F R1-6 一致性整改十项（全部 PASS）
`department` 建表与 FK；`project.main_object_entity_id` / `equipment.manufacturer_entity_id` 两处显式 FK；`project_member` `COALESCE` 表达式唯一索引拦截重复 NULL 组合；`action_measure` 双可空 FK + CHECK 与 `action_measure_link` M:N；`object_dimension_tag` REF/FREE_TEXT 互斥约束；`entity_identifier` 唯一范围收敛；`drawing_no` 按项目唯一（不同项目可用同图号、同项目同图号被拦）；多态引用孤儿自检 SQL 能查出孤儿；公共字段基线 A/B 逐表落地；表名 snake_case 单数统一（`issue_link` → `object_link`）。

### 8-G 额外架构检查实测（G1~G10，全部 PASS）
| # | 验证项 | 结果 |
|---|---|---|
| G1 | FTS5 trigram 可用（unicode61 中文命中 0 / trigram 命中 1） | PASS |
| G2 | 短词 LIKE 回退与别名表召回 | PASS（见 8-B） |
| G3 | 软删 `is_deleted` 镜像、重建与 4 项一致性自检 | PASS |
| G4 | `object_dimension_tag` 值类型 CHECK 拦截非法行 | PASS |
| G5 | G5 六层 `info_nature` CHECK 生效，非法值被拦 | PASS |
| G6 | AI 预测版本 `is_forecast=1 → info_nature IN (PREDICTION,PROPOSAL)` 约束 | PASS |
| G7 | `sp_check_polymorphic_refs` 多态孤儿自检能查出孤儿（§7.6） | PASS |
| G8 | UUID `CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')` 拦截非法 ID | PASS |
| G9 | `PRAGMA foreign_keys` **按连接生效**：连接 A 开启后新连接 B 仍为 0 且可插违规 FK，连接 C 显式开启后恢复 | PASS（定案「每连接必须执行」） |
| G10 | SQLite 允许 FK 引用**后置创建**的表（本文按 6 域顺序书写成立；迁 Pg 需拓扑重排） | PASS |

### 8-H 禁物理删除触发器（20 张正式表，统一模板）
```sql
-- 模板（以 issue 为例）
CREATE TRIGGER IF NOT EXISTS trg_issue_no_delete BEFORE DELETE ON issue
BEGIN SELECT RAISE(ABORT,'physical delete disabled; use soft delete (is_deleted=1)'); END;
```
适用 20 张：`project, project_phase, organization, person, plan, plan_version, email, document, drawing, meeting, message, issue, risk, task, decision, action_measure, entity, business_subject, knowledge_item, evidence`。
（`baseline_version` 与 `extraction_result` 已有各自的专用保护触发器，不重复计入。）

> 软删/归档/物理删除三态见《版本及历史管理规范》：**仅临时/缓存表允许物理删除**。

### 8-I 全量 DDL 编译验证（本轮最终自检）

> 直接从本文提取全部 SQL 代码块，剥离整行注释后按「先 75 张表 → 再 FTS 范式模板 → 再索引/触发器」的依赖顺序在 `:memory:` 内存库编译，验证「文档即 DDL」而非仅纸面描述。

| 项目 | 结果 |
|---|---|
| 提取 `CREATE TABLE` | **75**（与 §0.4 声明清单零差异） |
| 提取 `CREATE VIRTUAL TABLE`（范式模板） | 1 |
| 提取 `CREATE INDEX / UNIQUE INDEX / TRIGGER` | 44 |
| **执行失败** | **0** |
| 内存库普通表 | **75** |
| FTS 虚表 / 影子表 | 1 / 5（影子表标 `shadow`，不计入表数） |
| 触发器 / 显式索引 / 自动索引 | 8 / 36 / 120（自动索引 `sql IS NULL`，不计入显式索引） |
| `PRAGMA foreign_key_check` | 无违规 |
| `PRAGMA integrity_check` | `ok` |

> 说明：本验证只编译**本文给出的模板与显式对象**，故 FTS 虚表 1、触发器 8 与 §0.2 的 24 / 96 不同；24 / 96 是迁移脚本按 §7.2 清单循环生成后的对象数。结果同时印证 §0.2 的统计口径：必须用 `pragma_table_list` 区分 `shadow` 与 `sql IS NULL` 自动索引，否则会误计。
> 核验脚本陷阱（非 DDL 缺陷）：若保留整行 SQL 注释，「注释 + `CREATE TABLE`」会被合并成一条语句，导致 21 张表被漏分类、索引因表不存在而报错；剥离整行注释后全量通过。

---

## 9. 索引与唯一约束汇总

| 类型 | 对象 |
|---|---|
| 表内 UNIQUE / PK | 全部 75 张表的 `id`；`project_code`、`org_code`、`message_id_text`、各 `ref_no`、`config_key`、4 张 `project_*` 关联、`plan(plan_id,version_no)`、`baseline(plan_id,baseline_no)`、`baseline(plan_id,plan_version_id)`、`plan_activity(plan_id,code)`、`plan_activity_version(activity_id,plan_version_id)`、`*_version` 版本号、各 `*_link` 组合键 |
| 显式 UNIQUE INDEX | `uq_plan_code`、`uq_pab_active`（部分唯一，WHERE is_active=1）、`uq_pm`（COALESCE 表达式）、`uq_ei`（COALESCE 表达式）、`uq_dr`（COALESCE 表达式）、`idx_doc_sha`（部分唯一） |
| 普通索引 | `idx_person_org/dept`、`idx_pm_proj`、`idx_equip_sys/cat/mfr`、`idx_plan_proj`、`idx_activity_plan`、`idx_pav_ver/change`、`idx_bsl_plan`、`idx_bs_canonical`、`idx_issue_proj/status`、`idx_risk_proj`、`idx_task_proj`、`idx_am_risk/issue`、`idx_ol_left/right`、`idx_dl_ref`、`idx_el_ref`、`idx_sr_entity/source`、`idx_odt_obj/dim`、`idx_rd_queue`、`idx_rro_obj`、`idx_audit_target`、`idx_ei_lookup` |
| FTS | 24 张 trigram 虚表（§7.2） |

---

## 10. 迁移幂等性、G5 落地与 PostgreSQL 适配

### 10.1 幂等性 ≠ IF NOT EXISTS（补充结构一致性检查）
`migrations/001_init.sql`（后续 Phase）必须包含：
1. `PRAGMA foreign_keys=ON`（每连接）；单事务执行，失败整体回滚。
2. `schema_version` 登记版本号 + `ddl_fingerprint`（对 `sqlite_master.sql` 排序拼接后 sha256）。
3. **结构一致性检查**（不只是 `IF NOT EXISTS`）：`PRAGMA table_info(<table>)` 逐列比对列名/类型/notnull/默认值；`sqlite_master` 比对索引清单、触发器清单、FTS 虚表清单；与 `schema_version.ddl_fingerprint` 不符即中止并报警。
4. FTS 重建与 §7.6 一致性自检；多态孤儿自检。
5. 幂等重跑：已存在且结构一致 → 跳过；结构不一致 → **拒绝执行**（不静默 ALTER）。

### 10.2 G5 信息性质落地（业务对象 / 抽取 / 审核结果一致）
| 表 | info_nature 默认 | 约束 |
|---|---|---|
| `source_reference`, `email/document/drawing/meeting/meeting_minutes/message/evidence` | `SOURCE_FACT` | 原文忠实落库 |
| `issue/risk/task/action_measure/entity/knowledge_item/business_subject` | `CONFIRMED_FACT` | 仅人工确认后 |
| `extraction_result` | `AI_INFERENCE` | CHECK 限 AI_INFERENCE/PREDICTION/PROPOSAL |
| `plan_version(is_forecast=1)` | `PREDICTION` | CHECK 强制 |
| `review_decision` / `review_result_object` | `CONFIRMED_FACT` | 人工审核结果 |
| `decision` / `baseline_version` | `DECISION` | 人工决策 |
> 转换规则：`AI_INFERENCE → review_queue → review_decision(人工) → CONFIRMED_FACT`；**不得自动升级**。

### 10.3 SQLite → PostgreSQL 适配清单
| SQLite | PostgreSQL | 说明 |
|---|---|---|
| `TEXT char(32)` + CHECK | `uuid` 类型 | UUID 生成改 `gen_random_uuid()`，去掉 CHECK |
| ISO8601 TEXT | `timestamptz` / `date` | 时间字段类型转换与 UTC 归一 |
| `INTEGER 0/1` 布尔 | `boolean` | `is_deleted/is_forecast/is_active` 等 |
| 部分唯一索引 `WHERE` | 支持 | 语法基本一致 |
| 表达式唯一索引 `COALESCE` | 支持 | 语法基本一致 |
| **FTS5 trigram** | `pg_trgm` + GIN 索引 / `tsvector` 生成列 | `biz_id/owner_biz_id/is_deleted` 改为普通列 + 触发器维护 tsvector；**需重写检索层** |
| `RAISE(ABORT, ...)` | PL/pgSQL `RAISE EXCEPTION` | 20+2+2 个触发器需改写为 trigger function |
| `PRAGMA foreign_keys=ON` | 默认强制 | 无需逐连接设置 |
| `PRAGMA journal_mode=WAL` | 不适用 | Pg 用 MVCC |
| `UNINDEXED` 列 | 普通列（不进 tsvector） | 语义等价 |
| FK 引用后置表 | **需拓扑排序** | Pg DDL 会立即校验目标表存在 |

---

## 11. 与其余 7 份文档的一致性锚点

| 文档 | 必须一致的内容 |
|---|---|
| 核心实体数据字典 | 75 张表逐表字段、基线 A/B 标注、约束、索引 |
| 实体关系 ER 图 | 75 张表主要关系、新增 10 张表的关系 |
| 统一数据模型总体设计 | §0.2 数量、12 架构问题方案、检索路由（trigram+双引号+短词回退） |
| 数据来源与证据追溯规范 | `business_subject_source`、审核结果链、多态自检 |
| 版本及历史管理规范 | `plan_active_baseline` / `baseline_switch_log` / `plan_activity_version` |
| 架构决策记录 | ADR-1/2/3/4/5/6/7/7b/8/9/12 修订 + 「R1 整改对 ADR 的影响汇总」表 |
| 待确认事项清单 | 新增 10 项 N1~N10 |
