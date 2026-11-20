# Phase1.2 数据库表结构设计（R2 定向整改版 · CREATE TABLE 草案）

> 版本：R2（Phase 1.2 复审「数据模型完整性与证据追溯」定向整改后）｜日期：2026-11-12
> 本文件是**全库唯一真值源**：表名、字段、约束、触发器、索引、FTS 对应关系、对象数量统计，其余文档一律以本文为准。
> **R1 原稿**已由主理人快照至 `09_Archive/Phase1.2_R1_原稿/`（10 份 .md）并由 Git 提交 `7ac25c3` 完整保留；本文只改 `08_Documentation/` 下的当前版本，归档副本不回改。
> **本阶段不执行**：未创建 `migrations/001_init.sql`，未对 `01_Data/epcs_intelligence.db` 执行任何 DDL/DML，数据库仍为空库（业务表 0）。
> 所有 R1/R2 DDL 均在 Python `:memory:` 内存库（SQLite **3.53.1**）实测（见 §8 与 §12），未触碰正式库；测试脚本只写在操作系统临时目录，未写入项目目录。
> **R2 只针对复审 7 项阻断（P1~P7）+ 4 项实现边界（B1~B4）做定向整改**，不全面重做 Phase 1.2；R1 六项整改结论继续有效，被 R2 修订的结论已明确标注。
> **R2 全文统一统计口径**：实体表 **75** ／ FTS5 虚表 **24** ／ 触发器 **126** ／ 视图 **0**（见 §0.2）。

---

## 0. 全局约定与统一统计

### 0.1 连接与运行规范（实测结论）
```sql
PRAGMA foreign_keys = ON;   -- 必须【每个连接】单独执行！实测：连接A开启后，新连接B foreign_keys=0 且外键失效（§8 G9）
PRAGMA journal_mode = WAL;  -- 库级设置，持久化
```
> **结论**：Python `sqlite3.connect()` 之后必须在**每个连接**上执行 `PRAGMA foreign_keys=ON`；这是应用层连接工厂的强制职责，不能只写在迁移脚本首行。

### 0.2 统一对象数量统计（R2 定稿，全部 R2 文档共同引用）

| 类别 | 数量 | 说明 |
|---|---|---|
| 实体表（业务主表） | **46** | 见 §0.4 清单 A |
| 实体表（辅助/关联/桥/历史/治理） | **29** | 见 §0.4 清单 B |
| 实体表合计 | **75** | 含 `schema_version` 元信息表 1 张 |
| FTS5 虚拟表 | **24** | `tokenize='trigram'`，见 §7.2 |
| 触发器 | **126** | R1 的 **96**（FTS 同步 72 + 基线冻结 2 + 抽取不可变 2 + 禁物理删除 20）＋ R2 新增 **30**：业务主键/归属不可变 24（§7.7）＋ 审核证据校验 2（§6 / P3）＋ 可逆合并链守卫与联动 4（§4 / P7） |
| 唯一索引/约束 | **见 §9** | 表内 UNIQUE + 显式 `CREATE UNIQUE INDEX`；R2 新增 3 个 `UNIQUE(plan_id,id)` 复合外键父键（§2）与 1 个部分唯一索引 `uq_bsm_active_from`（§4） |
| 普通索引 | **见 §9** | 关系/桥/时间索引 |
| 视图 | **0** | 第一期不引入（P7 的权威根解析不引入视图，由有效合并链 + 自检 SQL 完成） |

> **R2 统计变化说明（唯一口径）**：R2 **未新增/删除任何实体表、FTS 虚表或视图**；触发器由 96 → **126**（+30，全部为数据库级约束所需）；实体表仅新增 2 个非空列 `plan_activity_version.plan_id` 与 `progress_record.plan_id`（§2，P1）；另补 **3 个列级 FK**（三张 `*_status_history.changed_by → person(id)`，B3/B4）与 **1 个列级 UUID CHECK**（`person.id`，B4）——均为列约束，**不改变**实体表 / FTS 虚表 / 触发器 / 视图 / 显式索引计数。全部 R2 文档一律引用本表，**禁止再出现「触发器 96」或任何宣称整改已整体通过 / 全部闭环的 R1 口径与结论**。
>
> 统计口径：实体表 = `CREATE TABLE`（不含 `CREATE VIRTUAL TABLE`）；FTS 表 = `CREATE VIRTUAL TABLE ... USING fts5`；触发器 = `CREATE TRIGGER`。迁移脚本批量生成的 FTS 同步触发器按 24×3、业务主键/归属不可变触发器按 24×1 计入（§7.7 给出确定生成规则与 24 行逐表映射表，不再是笼统的「循环生成」）。
>
> **DDL 表达口径（避免「声明数量 ≠ 文本语句数」误读）**：本文 75 张实体表**逐表给出完整 `CREATE TABLE`**；24 张 FTS 虚表、72 个 FTS 同步触发器、24 个 ID/归属不可变触发器、20 个禁物理删除触发器彼此同构，故在 §7.2 / §7.3 / §7.7 / §8-H 以「**统一范式模板 + 24 行逐表字段映射表 / 20 张适用表清单**」表达（R2-B1 已把「循环生成」细化为确定生成规则 + 逐表字段映射 + 生成结果核验方法）；清单即完整定义，不含省略项；另在 §7.3 额外给出 1 张版本表 FTS 虚表与 3 个同步触发器的**完整变体示例**（用于证明 `owner_biz_id` 取值规则，见 §8-I 双口径对照）。因此 `grep -c '^CREATE VIRTUAL TABLE'` = 2、`grep -c '^CREATE TRIGGER'` = 19 属**模板化表达**，与 §0.2 的 24 / 126 不矛盾；迁移脚本按 §7.7 生成后的实际对象数量即为本表统计值（内存库实测 24 / 126，见 §8-J）。
>
> **迁移后核验统计的口径（QA 阶段 A 实测 E5 + R2 复核，唯一正确口径）**：统计正式库普通表数量须用 **`PRAGMA table_list`**（**不是** `sqlite_master`），取 `type='table' AND name NOT LIKE 'sqlite_%'` —— 该视图下 `type='table'` 的系统目录表有 **两张**（`sqlite_schema` 与 `sqlite_temp_schema`），**只排除 `sqlite_schema` 会得到 76 而非 75**；`name NOT LIKE 'sqlite_%'` 一次排除两表，得 75。FTS5 的 5 张影子表在 `table_list` 中标为 `shadow`（在 `sqlite_master` 中却标为 `table`），故用 `sqlite_master` 计数会误计影子表并漏掉自动索引；`sqlite_autoindex_*`（`sql IS NULL`）属 PK/UNIQUE 自动创建的内部索引，不计入显式索引。本文 §7.7 ① / §8-I 均按此口径。另实测：SQLite **不支持** `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`（报 `near "FOREIGN": syntax error`），所有 FK 必须在 `CREATE TABLE` 内联声明；连接建立后建议追加 `PRAGMA foreign_key_check` 启动自检。

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
> **UUID 规则**：`uuid4().hex`（32 位小写十六进制）；**禁止**用文件名、姓名、项目名作主键（G7）。
> **R2-B4 精确化（QA 阶段 B 补强核验 S5-2）**：上面的 `id TEXT PRIMARY KEY CHECK(...)` 是**字段基线范式的规范写法**；当前数据库级 CHECK **显式声明于 `project` / `entity` / `person` 三张表**（§1；§8 G8 实测拦截非法 ID），其中 `person` 由 R2-B4 补齐，作为「所有审计责任人字段 = `person.id`」这一口径的数据库锚点。其余表的 `id` 由应用层 `uuid4().hex` 生成、§7.6.3 B4 格式自检与迁移阶段 `PRAGMA table_info` / `ddl_fingerprint` 结构一致性检查兜底；**全表 UUID CHECK 覆盖列入 Phase 1.3 迁移前复核**（《Phase1.2_R2_架构评审整改完成报告.md》§8 遗留事项）。本轮不把 CHECK 扩大到 75 张表，以免超出 P1~P7 / B1~B4 定向整改范围；此现状如实披露，不作「全库 CHECK 已生效」的不实结论。
> **建表顺序**：SQLite 允许 FK 引用**后置创建**的表（实测 §8 G10 PASS），故本文按 6 域顺序书写；迁移到 PostgreSQL 时须按依赖拓扑重排。
> **时间字段**：`event_time` / `source_time` / `created_at` / `updated_at` / `valid_from` / `valid_to` 严格区分，均为 ISO8601 UTC 文本。

### 0.4 全表清单（A 业务主表 46 / B 辅助表 29）

**A 业务主表（46）**
`project, project_phase, organization, department, person, discipline, area, system, equipment_category, equipment, plan, plan_version, baseline_version, plan_active_baseline, plan_activity, plan_activity_version, email, email_attachment, document, document_version, drawing, drawing_version, drawing_object, meeting, meeting_minutes, message, source_reference, evidence, issue, risk, task, action_measure, decision, object_link, entity, entity_alias, entity_identifier, entity_relationship, business_subject, business_subject_alias, business_subject_merge, knowledge_item, knowledge_version, ingestion_job, ai_analysis_run, extraction_result`（46）

**B 辅助/关联/桥/历史/治理表（29）**
`schema_version, project_member, project_discipline, project_area, project_system, project_equipment, baseline_switch_log, activity_dependency, progress_record, issue_status_history, risk_status_history, task_status_history, action_measure_link, decision_link, evidence_link, business_subject_source, review_queue, review_extraction_link, review_decision, review_result_object, knowledge_entity_link, object_dimension_tag, audit_log, system_config, user, role, permission, user_role, role_permission`（29 张，含 `schema_version`）

> 说明：`business_subject_alias` 归 A 组（已列入 A 清单），**不计入 B**；A 46 + B 29 = 75，与 §0.2 一致。逐表定义见 §1~§7，数据字典逐表说明见《核心实体数据字典》。
> **R2 补充**：R2 未增删任何表，清单 A/B 与 R1 完全一致；仅 `plan_activity_version` / `progress_record` 各增 1 个 `plan_id TEXT NOT NULL`（P1），`review_decision.evidence_source_reference_id` 由可空改 `NOT NULL`（P3），`business_subject_merge.merged_by` 由 `NOT NULL` 文本改为可空 `REFERENCES person(id)`（P7/B4）。字段级变化见 §12 变更总表。

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
    -- R2-B4（QA 阶段 B 补强核验 S5-2）：人员 ID 锚点必须带 UUID CHECK，
    -- 否则「所有审计责任人字段一律为 person.id 的 32 位小写 hex UUID」在数据库层无落点。
    id TEXT PRIMARY KEY CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*'),
    organization_id TEXT NOT NULL REFERENCES organization(id),
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

## 2. 域2 —— 计划管理（R1-1 基线只读 + R1-2 活动版本化；R2-P1 跨计划一致性）

> **R2-P1 决策（见 ADR-13）**：采用**复合唯一键 + 共享 `plan_id` 的复合外键**，在数据库层保证「计划域所有对象同属一个计划」，**不依赖应用层约定**。
> 机制：在父表 `plan_version` / `plan_activity` / `baseline_version` 上各建 `UNIQUE(plan_id, id)`（SQLite 复合外键要求被引用列存在列数、顺序匹配的 UNIQUE / PRIMARY KEY 索引）；子表用**同一个 `plan_id` 列**同时参与多个复合外键，使 `plan_id` 只能取一个值——任何跨计划拼装必然违反其中一个 FK。
> 覆盖 7 张子表：`plan_activity_version`、`activity_dependency`、`baseline_version`、`plan_active_baseline`、`plan_activity.first_version_id`、`progress_record`、`baseline_switch_log`。SQLite 复合外键为 MATCH SIMPLE 语义：任一子列为 NULL 时跳过该 FK 检查，故 `first_version_id` / `from_baseline_id` / `progress_record.plan_version_id` 等**可空引用仍合法**（NULL = 无该版本口径），但一旦非空就必须同计划。
> **反向测试（内存库实测全部被 `FOREIGN KEY constraint failed` 拒绝）**：「A 计划活动挂到 B 计划版本」（`plan_activity_version` / `first_version_id` / `progress_record` 三条路径）、「A 计划基线指向 B 计划版本」、「A 计划生效基线指向 B 计划基线」、「依赖跨计划」、「切换日志跨计划」；**正向测试**：同计划的 6 类对象全部插入成功。详见 §12-P1 与《R2 架构评审整改记录》。

```sql
-- ===== R2-P1：以下计划域 DDL 内含复合唯一键 / 复合外键；父键 UNIQUE(plan_id,id) 必须先行建立 =====
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
    UNIQUE(plan_id, id),                                 -- R2-P1：复合外键父键（被 plan_activity_version / activity_dependency / baseline_version / progress_record 引用）
    -- AI 预测版与正式版信息性质一致（G5）
    CHECK((is_forecast=1 AND info_nature IN ('PREDICTION','PROPOSAL')) OR is_forecast=0));

-- ===== R1-1 基线只读：内容与状态彻底分离（R2-P1 补同计划保证）=====
CREATE TABLE IF NOT EXISTS baseline_version (            -- 基线A，全字段冻结
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    plan_version_id TEXT NOT NULL,                       -- R2-P1：改由下方复合 FK 同时保证「存在」与「同计划」
    baseline_no TEXT NOT NULL, approved_at TEXT NOT NULL,
    approved_by TEXT REFERENCES person(id),              -- R2-B3/B4：补人员 FK（统一 person.id 口径）
    content_hash TEXT NOT NULL,
    is_readonly INTEGER NOT NULL DEFAULT 1 CHECK(is_readonly=1),
    info_nature TEXT NOT NULL DEFAULT 'DECISION',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    -- 已删除错误的 UNIQUE(plan_id, is_active)：is_active 字段整体移除
    UNIQUE(plan_id, baseline_no), UNIQUE(plan_id, plan_version_id),
    UNIQUE(plan_id, id),                                 -- R2-P1：复合外键父键（被 plan_active_baseline / baseline_switch_log 引用）
    FOREIGN KEY(plan_id, plan_version_id) REFERENCES plan_version(plan_id, id));  -- R2-P1

-- 当前生效状态独立表：一个计划最多一行（PK 天然约束，另有部分唯一索引）
CREATE TABLE IF NOT EXISTS plan_active_baseline (        -- 基线B（R2-P1 补同计划保证）
    plan_id TEXT PRIMARY KEY REFERENCES plan(id),
    baseline_version_id TEXT NOT NULL,                   -- R2-P1：改由下方复合 FK 约束
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active=1),
    switched_at TEXT NOT NULL,
    switched_by TEXT REFERENCES person(id),              -- R2-B3/B4：补人员 FK
    authorization_ref TEXT NOT NULL, reason TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(plan_id, baseline_version_id) REFERENCES baseline_version(plan_id, id));  -- R2-P1：A 计划状态不可能指向 B 计划基线
CREATE UNIQUE INDEX IF NOT EXISTS uq_pab_active
    ON plan_active_baseline(plan_id) WHERE is_active=1;   -- 评审要求的"当前生效基线部分唯一索引"

-- 基线切换全历史（授权 + 审计；R2-B3 补齐 FK，R2-P1 顺带保证同计划）
CREATE TABLE IF NOT EXISTS baseline_switch_log (         -- 基线B
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    from_baseline_id TEXT,                               -- 可空：首次切换无来源基线；非空时必须同计划
    to_baseline_id TEXT NOT NULL,
    switched_at TEXT NOT NULL,
    switched_by TEXT NOT NULL REFERENCES person(id),     -- R2-B4：统一 person.id，禁止姓名/自由文本
    authorization_ref TEXT NOT NULL, reason TEXT,
    audit_log_id TEXT REFERENCES audit_log(id),          -- R2-B3：补 FK（原为无约束文本，属遗漏）
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(plan_id, from_baseline_id) REFERENCES baseline_version(plan_id, id),  -- R2-P1/B3（可空，NULL 跳过）
    FOREIGN KEY(plan_id, to_baseline_id)   REFERENCES baseline_version(plan_id, id)); -- R2-P1/B3
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
    code TEXT NOT NULL,
    first_version_id TEXT,                               -- R2-P1：改由下方复合 FK 约束（可空，NULL 跳过）
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(plan_id, code),
    UNIQUE(plan_id, id),                                 -- R2-P1：复合外键父键（被 plan_activity_version / activity_dependency / progress_record 引用）
    FOREIGN KEY(plan_id, first_version_id) REFERENCES plan_version(plan_id, id));  -- R2-P1：活动首次版本必须同计划
CREATE INDEX IF NOT EXISTS idx_activity_plan ON plan_activity(plan_id);

CREATE TABLE IF NOT EXISTS plan_activity_version (       -- 每版本活动属性快照（基线A，R2-P1 新增 plan_id）
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plan(id),           -- R2-P1：新增；两个复合 FK 共享此列
    activity_id TEXT NOT NULL,                           -- R2-P1：改由下方复合 FK 约束
    plan_version_id TEXT NOT NULL,                       -- R2-P1：改由下方复合 FK 约束
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
    UNIQUE(activity_id, plan_version_id),
    FOREIGN KEY(plan_id, activity_id)     REFERENCES plan_activity(plan_id, id),   -- R2-P1：活动与版本必须同计划
    FOREIGN KEY(plan_id, plan_version_id) REFERENCES plan_version(plan_id, id));   -- R2-P1
CREATE INDEX IF NOT EXISTS idx_pav_ver ON plan_activity_version(plan_version_id);
CREATE INDEX IF NOT EXISTS idx_pav_change ON plan_activity_version(plan_version_id, change_type);

CREATE TABLE IF NOT EXISTS activity_dependency (         -- 基线B，版本化（R2-P1 三重复合 FK）
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    plan_version_id TEXT NOT NULL,                       -- R2-P1：改由下方复合 FK 约束
    predecessor_id TEXT NOT NULL,                        -- R2-P1：改由下方复合 FK 约束
    successor_id   TEXT NOT NULL,                        -- R2-P1：改由下方复合 FK 约束
    relation_type TEXT NOT NULL CHECK(relation_type IN ('FS','SS','FF','SF')), lag_days INTEGER,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0,
    CHECK(predecessor_id <> successor_id),
    UNIQUE(plan_version_id, predecessor_id, successor_id, relation_type),
    -- R2-P1：版本、前置活动、后置活动共享 plan_id，三者必须同属一个计划
    FOREIGN KEY(plan_id, plan_version_id) REFERENCES plan_version(plan_id, id),
    FOREIGN KEY(plan_id, predecessor_id)  REFERENCES plan_activity(plan_id, id),
    FOREIGN KEY(plan_id, successor_id)    REFERENCES plan_activity(plan_id, id));

CREATE TABLE IF NOT EXISTS progress_record (             -- 基线A（R2-P1 新增 plan_id）
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plan(id),           -- R2-P1：新增；与下列复合 FK 共享
    plan_activity_id TEXT NOT NULL,                      -- R2-P1：改由下方复合 FK 约束
    plan_version_id TEXT,                               -- 可空：无对照版本口径；非空必须同计划
    record_at TEXT NOT NULL,
    progress_pct REAL NOT NULL DEFAULT 0 CHECK(progress_pct BETWEEN 0 AND 100),
    actual_start TEXT, actual_end TEXT, note TEXT,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    UNIQUE(plan_activity_id, record_at),
    FOREIGN KEY(plan_id, plan_activity_id) REFERENCES plan_activity(plan_id, id),  -- R2-P1
    FOREIGN KEY(plan_id, plan_version_id)  REFERENCES plan_version(plan_id, id)); -- R2-P1
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

> **R2-P1 追加测试（内存库实测，见 §8-J / §12-P1）**：
> - **正向（预期通过）**：同一计划内插入 `plan_activity_version`、`activity_dependency`、`plan_active_baseline`、`progress_record`、`baseline_switch_log`、`plan_activity(first_version_id)` 六类对象，全部 PASS。
> - **反向（预期被 `FOREIGN KEY constraint failed` 拒绝）**：① 把 A 计划的 `plan_activity_version` 挂到 B 计划版本；② 把 A 计划活动的 `first_version_id` 指向 B 计划版本；③ 把 A 计划基线指向 B 计划版本；④ 把 A 计划生效基线指向 B 计划基线；⑤ `activity_dependency.successor_id` 跨计划；⑥ `progress_record.plan_version_id` 跨计划；⑦ `baseline_switch_log.from_baseline_id` 跨计划。**7 项全部由数据库拒绝**，不需要应用层参与。

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

-- ===== R2-P7：可逆合并链数据库级保护（守卫 + 联动 + 撤销）=====
-- R1 只有 CHECK(from<>to)，无法阻止循环 / 多目标 / 合并到非根 / canonical 不一致；R2 纳入：
--   ① 部分唯一索引 uq_bsm_active_from  → 一个 from 只能有一个【有效】合并目标（多目标被拦）；
--   ② trg_bsm_guard_i                  → 目标必须是 ACTIVE 有效根；禁止循环与多级链（保证 canonical 恒为根）；
--   ③ trg_bsm_apply_i                  → 合并时由数据库联动写 from_subject.status / canonical_subject_id；
--   ④ trg_bsm_guard_u                  → 撤销必须填齐撤销三字段、禁止篡改 from/to、禁止复活已撤销行；
--   ⑤ trg_bsm_apply_u                  → 撤销时由数据库联动恢复 from_subject 状态（事务 + 触发器共同实现）。
-- is_active=1 为有效合并、=0 为已撤销（R1 无 is_undone 字段，此处沿用 is_active，等价于 WHERE is_undone=0）。
CREATE TABLE IF NOT EXISTS business_subject_merge (      -- 基线A，可逆合并链
    id TEXT PRIMARY KEY,
    from_subject_id TEXT NOT NULL REFERENCES business_subject(id),
    to_subject_id   TEXT NOT NULL REFERENCES business_subject(id),
    merged_at TEXT NOT NULL,
    merged_by TEXT REFERENCES person(id),                -- R2-B4：统一 person.id；可空 = SYSTEM/AI 执行（须写 audit_log）
    reason TEXT,
    source_reference_id TEXT REFERENCES source_reference(id),
    undone_at TEXT,
    undone_by TEXT REFERENCES person(id),                -- R2-B4：统一 person.id
    undo_reason TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    CHECK(from_subject_id <> to_subject_id));            -- 禁止自合并
CREATE UNIQUE INDEX IF NOT EXISTS uq_bsm_active_from
    ON business_subject_merge(from_subject_id) WHERE is_active = 1;   -- R2-P7：有效合并链唯一性
CREATE TRIGGER IF NOT EXISTS trg_bsm_guard_i BEFORE INSERT ON business_subject_merge
WHEN NEW.is_active = 1 AND (
       EXISTS(SELECT 1 FROM business_subject_merge m WHERE m.from_subject_id = NEW.to_subject_id AND m.is_active = 1)
    OR EXISTS(SELECT 1 FROM business_subject_merge m WHERE m.to_subject_id = NEW.from_subject_id AND m.is_active = 1)
    OR (SELECT status FROM business_subject WHERE id = NEW.to_subject_id) <> 'ACTIVE')
BEGIN SELECT RAISE(ABORT,'invalid merge: target must be an active root; no cycle / no multi-level chain'); END;
CREATE TRIGGER IF NOT EXISTS trg_bsm_apply_i AFTER INSERT ON business_subject_merge
WHEN NEW.is_active = 1
BEGIN
  UPDATE business_subject SET status='MERGED', canonical_subject_id=NEW.to_subject_id, updated_at=NEW.merged_at
   WHERE id = NEW.from_subject_id;
END;
CREATE TRIGGER IF NOT EXISTS trg_bsm_guard_u BEFORE UPDATE ON business_subject_merge
WHEN (OLD.from_subject_id IS NOT NEW.from_subject_id
   OR OLD.to_subject_id   IS NOT NEW.to_subject_id
   OR (OLD.is_active = 0 AND NEW.is_active = 1))
   OR (OLD.is_active = 1 AND NEW.is_active = 0 AND (
          NEW.undone_at IS NULL OR NEW.undone_by IS NULL OR NEW.undo_reason IS NULL
       OR EXISTS(SELECT 1 FROM business_subject_merge m
                 WHERE m.to_subject_id = OLD.from_subject_id AND m.is_active = 1 AND m.id <> OLD.id)))
BEGIN SELECT RAISE(ABORT,'invalid merge update/undo: chain would become inconsistent'); END;
CREATE TRIGGER IF NOT EXISTS trg_bsm_apply_u AFTER UPDATE OF is_active ON business_subject_merge
WHEN OLD.is_active = 1 AND NEW.is_active = 0
BEGIN
  UPDATE business_subject SET status='ACTIVE', canonical_subject_id=NULL, updated_at=NEW.undone_at
   WHERE id = NEW.from_subject_id
     AND NOT EXISTS(SELECT 1 FROM business_subject_merge m
                    WHERE m.from_subject_id = NEW.from_subject_id AND m.is_active = 1);
END;

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
    changed_by TEXT REFERENCES person(id), changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
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
    changed_by TEXT REFERENCES person(id), changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
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
    changed_by TEXT REFERENCES person(id), changed_at TEXT NOT NULL, reason TEXT, reopen_count INTEGER NOT NULL DEFAULT 0,
    info_nature TEXT, source_reference_id TEXT REFERENCES source_reference(id),
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);

-- ===== R2-P2 定案（ADR-14）：恰好一个【主属主】+ 0..N【附加属主】=====
-- R1 整改报告/数据字典曾写「至少一个非空」，并把 action_measure_link 说成「一个措施挂多个属主 M:N」，
-- 与本表 XOR CHECK 矛盾。R2 明确：XOR CHECK 约束的是「唯一主属主」（恰好一个非空且不能双非空）；
-- action_measure_link 只承载 0..N 个【附加属主】，不得重复登记主属主（一致性自检见 §7.6）。
-- 全部文档（报告 / 字典 / ER / SQL / 总体设计）统一措辞：「恰好一个主属主 + 0..N 附加属主」。
CREATE TABLE IF NOT EXISTS action_measure (              -- 基线A
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(id),
    ref_no TEXT NOT NULL UNIQUE, name TEXT NOT NULL, description TEXT,
    measure_type TEXT NOT NULL CHECK(measure_type IN ('RISK_RESPONSE','ISSUE_REMEDY')),
    risk_id TEXT REFERENCES risk(id), issue_id TEXT REFERENCES issue(id),
    due_at TEXT, status TEXT NOT NULL DEFAULT 'OPEN',
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE',
    CHECK((risk_id IS NOT NULL AND issue_id IS NULL) OR (issue_id IS NOT NULL AND risk_id IS NULL)),  -- R2-P2：XOR = 恰好一个主属主（不是「至少一个」）
    -- R2-P2（QA 阶段 A 补充）：measure_type 必须与【唯一主属主】语义一致。
    -- R1 允许 measure_type='RISK_RESPONSE' 却挂 issue_id（或反之），无任何语义 CHECK，属真实缺陷。
    -- 本 CHECK 蕴含并强化上面的 XOR：RISK_RESPONSE⇒risk_id、ISSUE_REMEDY⇒issue_id，且不双非空。
    CHECK((measure_type='RISK_RESPONSE' AND risk_id  IS NOT NULL AND issue_id IS NULL)
       OR (measure_type='ISSUE_REMEDY'  AND issue_id IS NOT NULL AND risk_id  IS NULL)));
CREATE INDEX IF NOT EXISTS idx_am_risk ON action_measure(risk_id);
CREATE INDEX IF NOT EXISTS idx_am_issue ON action_measure(issue_id);
CREATE TABLE IF NOT EXISTS action_measure_link (         -- 基线B，0..N 附加属主（不得重复登记主属主，见 §7.6.3 自检）
    id TEXT PRIMARY KEY, action_measure_id TEXT NOT NULL REFERENCES action_measure(id),
    ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, link_role TEXT,
    created_at TEXT NOT NULL, is_deleted INTEGER NOT NULL DEFAULT 0);
-- R2-P2（QA 补充）职责边界：action_measure_link.ref_id 是【多态引用、无硬 FK】（与 object_link 等一致）。
-- R1 中 ref_id 可写不存在的对象且被接受；R2 由 §7.6.2 的 q7 分支（target 23 类全集 + IS NULL 反连接）
-- 保证孤儿【必然被检出】，并配合应用层校验 + audit_log 留痕三层补偿；不伪装成数据库硬 FK（ADR-14）。
-- 同时由 §7.6.3 的 P2 自检禁止把主属主重复登记进附加关联表。

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

-- ===== R2-P3：所有审核决定必须绑定来源证据（NOT NULL + FK + 触发器校验未软删）=====
-- R1 真值源此处为可空「evidence_source_reference_id TEXT REFERENCES source_reference(id)」，
-- 但《数据来源与证据追溯规范》与 R1 整改报告均声称「证据必填」，§6.5 验证表更写「PASS（约束强制）」——
-- 属文档与 SQL 不一致的不实结论。R2 决策（ADR-15）：不允许例外审核类型，全部决定一律绑定证据。
CREATE TABLE IF NOT EXISTS review_decision (             -- 审核结果明细（基线A）
    id TEXT PRIMARY KEY, review_queue_id TEXT NOT NULL REFERENCES review_queue(id),
    decision TEXT NOT NULL CHECK(decision IN ('ACCEPT_AS_NEW','MERGE_TO','REJECT')),
    reviewer_person_id TEXT NOT NULL REFERENCES person(id),
    reviewed_at TEXT NOT NULL, reason TEXT NOT NULL,
    evidence_source_reference_id TEXT NOT NULL REFERENCES source_reference(id),   -- R2-P3：NOT NULL + FK
    info_nature TEXT NOT NULL DEFAULT 'CONFIRMED_FACT',
    created_at TEXT NOT NULL, updated_at TEXT, is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT, del_status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE INDEX IF NOT EXISTS idx_rd_queue ON review_decision(review_queue_id);
-- FK 保证「证据存在」，触发器保证「证据未软删」（FK 不检查 is_deleted）；2 个触发器计入 §0.2 的 126
CREATE TRIGGER IF NOT EXISTS trg_rd_evidence_i BEFORE INSERT ON review_decision
WHEN (SELECT is_deleted FROM source_reference WHERE id = NEW.evidence_source_reference_id) <> 0
BEGIN SELECT RAISE(ABORT,'review evidence: source_reference is soft-deleted'); END;
CREATE TRIGGER IF NOT EXISTS trg_rd_evidence_u BEFORE UPDATE OF evidence_source_reference_id ON review_decision
WHEN (SELECT is_deleted FROM source_reference WHERE id = NEW.evidence_source_reference_id) <> 0
BEGIN SELECT RAISE(ABORT,'review evidence: source_reference is soft-deleted'); END;
-- 纵深：证据事后被软删的既有决定，由 §7.6 扩展一致性自检 SQL 检出并报警（不新增触发器）

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
| 审核人/时间/理由/证据 | `reviewer_person_id / reviewed_at / reason` 三个 `NOT NULL`；**`evidence_source_reference_id` 在 R1 真值源中可空** | **R1 不实结论 → R2 闭环**：R1 此处写「PASS（约束强制）」与 R1 SQL 不符（证据可空）；R2 改 `NOT NULL` + FK + `trg_rd_evidence_i/u`（拒绝软删证据），见 §12-P3 正/反向用例 |
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
  OR old.id IS NOT new.id                             -- R2-P5 纵深：主键变化也纳入重同步（版本表另含归属外键变化）
BEGIN
  DELETE FROM issue_fts WHERE biz_id = old.id;
  INSERT INTO issue_fts(biz_id, owner_biz_id, is_deleted, ref_no, title, description_md)
  VALUES(new.id, NULL, new.is_deleted, new.ref_no, new.title, new.description_md);
END;
CREATE TRIGGER IF NOT EXISTS trg_issue_fts_ad AFTER DELETE ON issue BEGIN
  DELETE FROM issue_fts WHERE biz_id = old.id;
END;
-- 其余 19 张非版本表按同模板生成；5 张版本表必须用下方 owner_biz_id 变体（清单固定为 §7.2 的 24 张）。
```

**版本表模板变体（R2-P5：修复 §7.2 与 §7.3 的 `owner_biz_id` 矛盾）**
```sql
-- 以 document_version 为例；虚表定义与 §7.7 映射表第 4 行一致（其余 23 张按映射表生成）
CREATE VIRTUAL TABLE IF NOT EXISTS document_version_fts USING fts5(
    biz_id UNINDEXED, owner_biz_id UNINDEXED, is_deleted UNINDEXED,
    extracted_text, notes, snapshot_json, tokenize='trigram');
-- owner_biz_id 取归属外键列，绝不为 NULL
CREATE TRIGGER IF NOT EXISTS trg_document_version_fts_ai AFTER INSERT ON document_version BEGIN
  INSERT INTO document_version_fts(biz_id, owner_biz_id, is_deleted, extracted_text, notes, snapshot_json)
  VALUES(new.id, new.document_id, new.is_deleted, new.extracted_text, new.notes, new.snapshot_json);
END;
CREATE TRIGGER IF NOT EXISTS trg_document_version_fts_au AFTER UPDATE ON document_version
WHEN old.extracted_text IS NOT new.extracted_text OR old.notes IS NOT new.notes
  OR old.snapshot_json IS NOT new.snapshot_json OR old.is_deleted IS NOT new.is_deleted
  OR old.id IS NOT new.id OR old.document_id IS NOT new.document_id   -- R2-P5：归属变化纳入同步
BEGIN
  DELETE FROM document_version_fts WHERE biz_id = old.id;
  INSERT INTO document_version_fts(biz_id, owner_biz_id, is_deleted, extracted_text, notes, snapshot_json)
  VALUES(new.id, new.document_id, new.is_deleted, new.extracted_text, new.notes, new.snapshot_json);
END;
CREATE TRIGGER IF NOT EXISTS trg_document_version_fts_ad AFTER DELETE ON document_version BEGIN
  DELETE FROM document_version_fts WHERE biz_id = old.id;
END;
-- 另 4 张版本表（drawing_version / meeting_minutes / knowledge_version / plan_activity_version）
-- 按 §7.7 的 24 行映射表把 document_id 换成对应归属列（drawing_id / meeting_id / knowledge_item_id / activity_id）。
```
> **R2-P5 矛盾修复说明（QA 阶段 A 发现）**：R1 §7.3 模板写死 `VALUES(new.id, NULL, ...)`，使 `owner_biz_id` **恒为 NULL**，与 §7.2 第②条「版本类 FTS 的 `owner_biz_id` = 主表 UUID」直接冲突。R2 明确：`NULL` **仅适用于 19 张非版本表**；5 张版本表一律按 §7.7 映射表的「归属外键列」取值。方案 A 重建 SQL 同步采用版本表变体（§7.6.1），并配合 §7.7 的 24 个 `BEFORE UPDATE OF id, <归属>` 不可变触发器，从数据库级杜绝 `owner_biz_id` 漂移。
> 采用「先 DELETE 再 INSERT」而非 `UPDATE fts SET ...`，避免 trigram 分词下更新值漂移；软删用 `is_deleted` 镜像，不删 FTS 行。
>
> **R2-P5 决策（业务主键 ID 不可变）**：R1 的 `AFTER UPDATE` 触发器 `WHEN` 未覆盖主键 `id`（以及版本表决定 `owner_biz_id` 的归属外键，如 `document_version.document_id`）变化，会造成 FTS 行漂移。R2 采用**数据库级保证**：
> 1. 对 **24 张内容表**统一生成 `BEFORE UPDATE OF id ... WHEN old.id IS NOT new.id → RAISE(ABORT,'business primary key id immutable')`；版本类 5 张表（`document_version` / `drawing_version` / `meeting_minutes` / `knowledge_version` / `plan_activity_version`）的触发器同时覆盖归属外键列，禁止 `owner_biz_id` 来源被改写。模板与 24 行清单见 §7.7，共 **24 个触发器**，计入 §0.2 的 126。
> 2. 同步触发器 `WHEN` 补 `old.id IS NOT new.id`（及版本表归属外键变化）作为**纵深防御**：即便未来放宽不可变规则，FTS 仍能按 `old.id` 先删、`new.id` 再插正确重同步。
> 3. 理由：UUID 主键被多态引用（`object_link` / `source_reference` / 各 `*_link`）大量指向，主键一旦可变，所有引用链断裂且无法用 FK 补偿；故「不可变」是唯一可接受语义。

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
- **R2-P5 方案 A（审核人倾向方案，本轮定案）**：重建必须同步**全部记录（含软删）**并保留 `is_deleted` 镜像，`INSERT ... SELECT` **不得**带 `WHERE is_deleted=0`。R1 §7.6 示例带该条件，会把软删记录从 FTS 清除、造成重建前后状态不一致，**该写法已作废**；正确 SQL 与一致性检查见 §7.6。软删 FTS 行「保留 + 过滤」的 N4 待确认项按此方案 A 收敛（仍保留容量实测后的复核）。

### 7.6 重建 / 一致性 / 多态完整性自检（R2 重写，P5 / P6 / B2）

#### 7.6.1 方案 A 重建与一致性检查（R2-P5）
```sql
-- 重建（方案 A：同步【全部记录，含软删】；绝不写 WHERE is_deleted=0）
DELETE FROM issue_fts;
INSERT INTO issue_fts(biz_id, owner_biz_id, is_deleted, ref_no, title, description_md)
  SELECT id, NULL, is_deleted, ref_no, title, description_md FROM issue;   -- 无 WHERE
-- ① 全量行数差（含软删；R1 的「活跃行数差」已作废）
SELECT (SELECT count(*) FROM issue) - (SELECT count(*) FROM issue_fts) AS drift;
-- ② biz_id 孤儿（FTS 行无对应业务行）
SELECT f.biz_id FROM issue_fts f LEFT JOIN issue t ON t.id=f.biz_id WHERE t.id IS NULL;
-- ③ 软删镜像一致（逐行比对，含软删行；IS NOT 保证 NULL 安全）
SELECT t.id, t.is_deleted, f.is_deleted FROM issue t
LEFT JOIN issue_fts f ON f.biz_id = t.id
WHERE f.biz_id IS NULL OR f.is_deleted IS NOT t.is_deleted;
-- ④ trigram 正向自检（已知样本必须命中；命中 0 时全部核验结果不可采信）
SELECT count(*) AS hit FROM issue_fts WHERE issue_fts MATCH '"集控台"';
-- ⑤ R2-B2：重复 biz_id 检测（正常态必须返回 0 行）
SELECT biz_id, count(*) AS n FROM issue_fts GROUP BY biz_id HAVING count(*) > 1;
-- ⑥ 版本表方案 A 重建变体（R2-P5：owner_biz_id 取归属外键，与 §7.3 模板变体一致）
--    以 document_version 为例；其余 4 张版本表按 §7.7 映射表替换归属列与文本列
DELETE FROM document_version_fts;
INSERT INTO document_version_fts(biz_id, owner_biz_id, is_deleted, extracted_text, notes, snapshot_json)
  SELECT id, document_id, is_deleted, extracted_text, notes, snapshot_json
    FROM document_version;                            -- 无 WHERE：含软删全量
```
> 24 张 FTS 表按 §7.7 的 **24 行逐表字段映射表**循环生成上述检查；版本类 FTS 的 `biz_id` 恒为版本表 `id`、`owner_biz_id` 取映射表指定列（⑥ 给出可执行变体，`NULL` 只用于非版本表）。R1 的「活跃行数差」（只比 `is_deleted=0`）改为**全量行数差**：方案 A 重建后 FTS 中同时存在活跃与软删行，只比活跃行会掩盖软删镜像漂移。
> **B2 结论**：`biz_id` **不加**唯一约束（FTS5 虚表不支持 UNIQUE / `CREATE INDEX`）；其唯一性由「主表 `id` 主键全局唯一（`uuid4().hex` + CHECK）＋ 三向同步触发器（INSERT 一次、UPDATE 先删后插、DELETE 删除）」共同保证，上述 ⑤ 为可执行的兜底检测。人为插入重复 `biz_id` 行时该语句能检出（§8-J 实测）。

#### 7.6.2 `check_polymorphic_refs`（R2-P6：应用层 SQL 自检语句集，**非存储过程**）

> **醒目声明**：SQLite **没有原生存储过程**。`check_polymorphic_refs`（R1 曾名 `sp_check_polymorphic_refs`）**不是存储过程、不能 `CALL`**，而是**由应用层在「摄入作业完成后 + 定期维护 + 迁移/重建后」执行的一组 SQL 自检语句集**；输出为「孤儿行清单」，结果写入 `audit_log`。`sp_` 前缀会误导后续开发人员以为可直接调用，R2 全文统一改名并加此声明。
> **R2 type 值口径统一**：全部多态 `type` 值统一为**大写**，与 `review_result_object.object_type`、`business_subject.subject_kind` 的 CHECK 枚举一致，消除 R1 中小写 `'issue'` / `'email'` 与大写 `'ISSUE'` 混用；SQL 用 `UPPER(type)` 归一以兼容历史数据，**非法 type 值同样被检出**（LEFT JOIN 不到 `target` → `t.id IS NULL`）。

**完整映射清单：引用字段 → 合法 type 值 → 目标表 → 检测分支（覆盖全部 8 类多态引用 / 10 个分支）**

| # | 引用字段（源表.列） | 合法 type 值 | 目标表（按 type 分派） | 分支 |
|---|---|---|---|---|
| 1 | `object_link.left_type / left_id` | 全部 23 类（见下方 `target`） | 23 张目标表 | `q1` |
| 2 | `object_link.right_type / right_id` | 全部 23 类 | 23 张目标表 | `q2` |
| 3 | `source_reference.traced_entity_type / traced_entity_id` | ISSUE, RISK, TASK, DECISION, KNOWLEDGE_ITEM, ACTION_MEASURE, BUSINESS_SUBJECT, ENTITY, PLAN_ACTIVITY, PLAN_VERSION, BASELINE_VERSION, DOCUMENT, DRAWING, EVIDENCE | 对应 14 张目标表 | `q3` |
| 4 | `source_reference.source_type / source_id` | EMAIL, EMAIL_ATTACHMENT, DOCUMENT, **DOCUMENT_VERSION**, DRAWING, **DRAWING_VERSION**, MEETING, **MEETING_MINUTES**, **MESSAGE**, EVIDENCE | 对应 10 张目标表 | `q4` |
| 5 | `evidence_link.ref_type / ref_id` | 全部 23 类 | 23 张目标表 | `q5` |
| 6 | `decision_link.ref_type / ref_id` | 全部 23 类 | 23 张目标表 | `q6` |
| 7 | `action_measure_link.ref_type / ref_id` | 全部 23 类 | 23 张目标表 | `q7` |
| 8 | `review_result_object.object_type / object_id` | ISSUE, **RISK**, **TASK**, DECISION, **KNOWLEDGE_ITEM**, ENTITY, BUSINESS_SUBJECT（CHECK 7 类） | 对应 7 张目标表 | `q8` |
| 9 | `business_subject_alias.subject_id` | 固定 BUSINESS_SUBJECT（硬 FK，纳入自检作一致性复核） | `business_subject` | `q9` |
| 10 | `object_dimension_tag.tagged_object_type / tagged_object_id` | ISSUE, RISK, TASK, DECISION, KNOWLEDGE_ITEM, PLAN_ACTIVITY, DOCUMENT, DRAWING, EMAIL, MEETING, MESSAGE, ENTITY, ACTION_MEASURE, SOURCE_REFERENCE, REVIEW_DECISION | 对应 15 张目标表 | `q10` |

> 「全部 23 类」= `issue, risk, task, decision, knowledge_item, action_measure, business_subject, entity, plan_activity, plan_version, baseline_version, email, email_attachment, document, document_version, drawing, drawing_version, meeting, meeting_minutes, message, evidence, source_reference, review_decision`。R1 的自检只演示 `issue` / `email` / `ISSUE` 三种类型，**未证明** `document_version` / `drawing_version` / `meeting_minutes` / `message` / `risk` / `task` / `knowledge_item` 等合法类型可检查；R2 上表逐类列全，且自检 SQL 用统一 `target` 全集覆盖。
>
> **R2-P4 决策（QA 追问 `review_result_object(object_type='ENTITY')`）**：`ENTITY` 是 `review_result_object` 的**合法多态类型**（§6 `object_type CHECK` 的 7 类之一），表示审核结果可直接落到船舶/设备/区域/组织等实体对象；已显式登记进上表 `q8` 分支与 `target` 全集（`SELECT 'ENTITY', id FROM entity`），故**不加 CHECK 禁止、不改 DDL**。这**不表示 Entity 变成 BusinessSubject**：`business_subject.subject_kind` 仍不含 `ENTITY` / `PLAN_ACTIVITY`，`entity` 仍无 `subject_id`，Entity 的来源追溯仍直接走 `source_reference`（见《数据来源与证据追溯规范》§1 与本文 §12.1 P4 行）。

```sql
-- check_polymorphic_refs：完整可执行孤儿检测（IS NULL 反连接，不是 NOT IN）
WITH target AS (
  SELECT 'ISSUE' AS typ, id FROM issue
  UNION ALL SELECT 'RISK', id FROM risk
  UNION ALL SELECT 'TASK', id FROM task
  UNION ALL SELECT 'DECISION', id FROM decision
  UNION ALL SELECT 'KNOWLEDGE_ITEM', id FROM knowledge_item
  UNION ALL SELECT 'ACTION_MEASURE', id FROM action_measure
  UNION ALL SELECT 'BUSINESS_SUBJECT', id FROM business_subject
  UNION ALL SELECT 'ENTITY', id FROM entity
  UNION ALL SELECT 'PLAN_ACTIVITY', id FROM plan_activity
  UNION ALL SELECT 'PLAN_VERSION', id FROM plan_version
  UNION ALL SELECT 'BASELINE_VERSION', id FROM baseline_version
  UNION ALL SELECT 'EMAIL', id FROM email
  UNION ALL SELECT 'EMAIL_ATTACHMENT', id FROM email_attachment
  UNION ALL SELECT 'DOCUMENT', id FROM document
  UNION ALL SELECT 'DOCUMENT_VERSION', id FROM document_version
  UNION ALL SELECT 'DRAWING', id FROM drawing
  UNION ALL SELECT 'DRAWING_VERSION', id FROM drawing_version
  UNION ALL SELECT 'MEETING', id FROM meeting
  UNION ALL SELECT 'MEETING_MINUTES', id FROM meeting_minutes
  UNION ALL SELECT 'MESSAGE', id FROM message
  UNION ALL SELECT 'EVIDENCE', id FROM evidence
  UNION ALL SELECT 'SOURCE_REFERENCE', id FROM source_reference
  UNION ALL SELECT 'REVIEW_DECISION', id FROM review_decision
),
q1 AS (SELECT 'object_link.left' AS src, r.id AS ref_row_id, r.left_type AS typ, r.left_id AS rid
       FROM object_link r LEFT JOIN target t ON t.typ=UPPER(r.left_type) AND t.id=r.left_id
       WHERE t.id IS NULL OR UPPER(r.left_type) NOT IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ACTION_MEASURE','BUSINESS_SUBJECT','ENTITY','PLAN_ACTIVITY','PLAN_VERSION','BASELINE_VERSION','EMAIL','EMAIL_ATTACHMENT','DOCUMENT','DOCUMENT_VERSION','DRAWING','DRAWING_VERSION','MEETING','MEETING_MINUTES','MESSAGE','EVIDENCE','SOURCE_REFERENCE','REVIEW_DECISION')),
q2 AS (SELECT 'object_link.right', r.id, r.right_type, r.right_id
       FROM object_link r LEFT JOIN target t ON t.typ=UPPER(r.right_type) AND t.id=r.right_id
       WHERE t.id IS NULL OR UPPER(r.right_type) NOT IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ACTION_MEASURE','BUSINESS_SUBJECT','ENTITY','PLAN_ACTIVITY','PLAN_VERSION','BASELINE_VERSION','EMAIL','EMAIL_ATTACHMENT','DOCUMENT','DOCUMENT_VERSION','DRAWING','DRAWING_VERSION','MEETING','MEETING_MINUTES','MESSAGE','EVIDENCE','SOURCE_REFERENCE','REVIEW_DECISION')),
q3 AS (SELECT 'source_reference.traced', r.id, r.traced_entity_type, r.traced_entity_id
       FROM source_reference r LEFT JOIN target t ON t.typ=UPPER(r.traced_entity_type) AND t.id=r.traced_entity_id
       WHERE t.id IS NULL OR UPPER(r.traced_entity_type) NOT IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ACTION_MEASURE','BUSINESS_SUBJECT','ENTITY','PLAN_ACTIVITY','PLAN_VERSION','BASELINE_VERSION','DOCUMENT','DRAWING','EVIDENCE')),
q4 AS (SELECT 'source_reference.source', r.id, r.source_type, r.source_id
       FROM source_reference r LEFT JOIN target t ON t.typ=UPPER(r.source_type) AND t.id=r.source_id
       WHERE t.id IS NULL OR UPPER(r.source_type) NOT IN ('EMAIL','EMAIL_ATTACHMENT','DOCUMENT','DOCUMENT_VERSION','DRAWING','DRAWING_VERSION','MEETING','MEETING_MINUTES','MESSAGE','EVIDENCE')),
q5 AS (SELECT 'evidence_link', r.id, r.ref_type, r.ref_id
       FROM evidence_link r LEFT JOIN target t ON t.typ=UPPER(r.ref_type) AND t.id=r.ref_id
       WHERE t.id IS NULL OR UPPER(r.ref_type) NOT IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ACTION_MEASURE','BUSINESS_SUBJECT','ENTITY','PLAN_ACTIVITY','PLAN_VERSION','BASELINE_VERSION','EMAIL','EMAIL_ATTACHMENT','DOCUMENT','DOCUMENT_VERSION','DRAWING','DRAWING_VERSION','MEETING','MEETING_MINUTES','MESSAGE','EVIDENCE','SOURCE_REFERENCE','REVIEW_DECISION')),
q6 AS (SELECT 'decision_link', r.id, r.ref_type, r.ref_id
       FROM decision_link r LEFT JOIN target t ON t.typ=UPPER(r.ref_type) AND t.id=r.ref_id
       WHERE t.id IS NULL OR UPPER(r.ref_type) NOT IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ACTION_MEASURE','BUSINESS_SUBJECT','ENTITY','PLAN_ACTIVITY','PLAN_VERSION','BASELINE_VERSION','EMAIL','EMAIL_ATTACHMENT','DOCUMENT','DOCUMENT_VERSION','DRAWING','DRAWING_VERSION','MEETING','MEETING_MINUTES','MESSAGE','EVIDENCE','SOURCE_REFERENCE','REVIEW_DECISION')),
q7 AS (SELECT 'action_measure_link', r.id, r.ref_type, r.ref_id
       FROM action_measure_link r LEFT JOIN target t ON t.typ=UPPER(r.ref_type) AND t.id=r.ref_id
       WHERE t.id IS NULL OR UPPER(r.ref_type) NOT IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ACTION_MEASURE','BUSINESS_SUBJECT','ENTITY','PLAN_ACTIVITY','PLAN_VERSION','BASELINE_VERSION','EMAIL','EMAIL_ATTACHMENT','DOCUMENT','DOCUMENT_VERSION','DRAWING','DRAWING_VERSION','MEETING','MEETING_MINUTES','MESSAGE','EVIDENCE','SOURCE_REFERENCE','REVIEW_DECISION')),
q8 AS (SELECT 'review_result_object', r.id, r.object_type, r.object_id
       FROM review_result_object r LEFT JOIN target t ON t.typ=UPPER(r.object_type) AND t.id=r.object_id
       WHERE t.id IS NULL OR UPPER(r.object_type) NOT IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ENTITY','BUSINESS_SUBJECT')),
q9 AS (SELECT 'business_subject_alias', r.id, 'BUSINESS_SUBJECT', r.subject_id
       FROM business_subject_alias r LEFT JOIN target t ON t.typ='BUSINESS_SUBJECT' AND t.id=r.subject_id
       WHERE t.id IS NULL),
q10 AS (SELECT 'object_dimension_tag', r.id, r.tagged_object_type, r.tagged_object_id
       FROM object_dimension_tag r LEFT JOIN target t ON t.typ=UPPER(r.tagged_object_type) AND t.id=r.tagged_object_id
       WHERE t.id IS NULL OR UPPER(r.tagged_object_type) NOT IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','PLAN_ACTIVITY','DOCUMENT','DRAWING','EMAIL','MEETING','MESSAGE','ENTITY','ACTION_MEASURE','SOURCE_REFERENCE','REVIEW_DECISION'))
SELECT * FROM q1 UNION ALL SELECT * FROM q2 UNION ALL SELECT * FROM q3
UNION ALL SELECT * FROM q4 UNION ALL SELECT * FROM q5 UNION ALL SELECT * FROM q6
UNION ALL SELECT * FROM q7 UNION ALL SELECT * FROM q8 UNION ALL SELECT * FROM q9
UNION ALL SELECT * FROM q10;
```
> **双向验证要求（每个分支都必须做）**：① **正向**——写入「合法 type + 目标表中确实存在的 id」的正常数据，自检必须返回 **0 行**（且 trigram/映射正向控制有效，否则结果不可采信）；② **反向**——写入「不存在的 id（孤儿）」或「非法/未登记的 type 值」，自检必须检出该行且 `src` 等于对应分支名。R2 内存库实测：正常态 10 分支合计 0 行；注入 10 行孤儿/非法 type 后 **10 个分支全部检出**（§8-J）。输出结果写入 `audit_log`。

#### 7.6.3 R2 扩展一致性检查（P2 / P3 / P7 / B4，同属自检语句集）
```sql
-- P2：action_measure_link 不得重复登记主属主（职责边界）
SELECT l.id FROM action_measure_link l JOIN action_measure am ON am.id = l.action_measure_id
WHERE (UPPER(l.ref_type)='RISK'  AND l.ref_id = am.risk_id)
   OR (UPPER(l.ref_type)='ISSUE' AND l.ref_id = am.issue_id);
-- P3：审核决定引用的证据事后被软删（触发器管写入时，本句管事后）
SELECT rd.id FROM review_decision rd
JOIN source_reference sr ON sr.id = rd.evidence_source_reference_id
WHERE sr.is_deleted <> 0 AND rd.is_deleted = 0;
-- P7：canonical_subject_id / status 与有效合并关系一致（撤销后状态不一致可被检出）
SELECT bs.id FROM business_subject bs
LEFT JOIN business_subject_merge m ON m.from_subject_id = bs.id AND m.is_active = 1
WHERE (m.id IS NOT NULL AND (bs.status <> 'MERGED' OR bs.canonical_subject_id IS NOT m.to_subject_id))
   OR (m.id IS NULL AND (bs.status = 'MERGED' OR bs.canonical_subject_id IS NOT NULL));
-- B4：审计责任人字段格式统一（32 位小写 hex 或 NULL；非法格式由 FK + UUID CHECK 双重拦截）
SELECT 'business_subject_merge.merged_by' AS fld, id FROM business_subject_merge
 WHERE merged_by IS NOT NULL AND (length(merged_by) <> 32 OR merged_by GLOB '*[^0-9a-f]*')
UNION ALL
SELECT 'issue_status_history.changed_by', id FROM issue_status_history
 WHERE changed_by IS NOT NULL AND (length(changed_by) <> 32 OR changed_by GLOB '*[^0-9a-f]*');
```
> 执行时机：摄入作业完成后 + 定期维护 + 每次迁移/重建后；结果写 `audit_log`。**明确这是已知取舍**：多态字段无硬 FK，以 `check_polymorphic_refs` 自检 + 应用层校验 + 审计三层补偿，不伪装成数据库硬约束（ADR-4 / ADR-5 / ADR-16）。

### 7.7 R2-B1：FTS / 触发器确定生成规则 + 24 行逐表字段映射表 + 生成结果核验

> R1 只写「统一模板 + 清单，由迁移脚本循环生成」，不足以进入迁移阶段。R2-B1 给出**确定的生成规则**、**逐表字段映射表（24 行）**与**生成结果核验方法**，全部在 `:memory:` 内存库实测可执行（§8-J）。

**生成规则（确定性，无歧义）**：
1. 输入为下表 24 行映射；每行含 `业务表 / FTS 表 / biz_id 来源 / owner_biz_id 来源 / is_deleted 来源 / 文本列清单 / 是否版本表`。
2. `biz_id` 恒取业务表 `id`；`is_deleted` 恒取业务表 `is_deleted`；`owner_biz_id` 对版本表取「归属外键列」，非版本表固定 `NULL`。
3. FTS 虚表固定列序：`biz_id UNINDEXED, owner_biz_id UNINDEXED, is_deleted UNINDEXED, <文本列...>, tokenize='trigram'`。
4. 每行生成 4 个对象：1 张 `CREATE VIRTUAL TABLE`；3 个同步触发器 `trg_<表>_fts_ai / _au / _ad`；1 个不可变触发器 `trg_<表>_id_immutable`（`BEFORE UPDATE OF id`；版本表另含归属外键列）。UPDATE 触发器 `WHEN` 固定为「各文本列 `old IS NOT new` ＋ `old.id IS NOT new.id` ＋ 版本表 `old.<归属> IS NOT new.<归属>`」。
5. 禁物理删除 20 张正式表按 §8-H 清单生成 `trg_<表>_no_delete`（1 个模板 + 20 行清单）。
6. **禁止**任何「凭空补列 / 按类型猜列」逻辑：映射表即完整定义，生成脚本不得访问业务表 schema 做推断。

**逐表字段映射表（24 行，R2 定稿）**

| # | 业务表 | FTS 表 | biz_id | owner_biz_id | is_deleted | 文本列（FTS 索引列） | 版本表 |
|---|---|---|---|---|---|---|---|
| 1 | `email` | `email_fts` | `email.id` | NULL | `email.is_deleted` | subject, body_markdown | 否 |
| 2 | `email_attachment` | `email_attachment_fts` | `email_attachment.id` | NULL | 同表 | filename | 否 |
| 3 | `document` | `document_fts` | `document.id` | NULL | 同表 | name, doc_code | 否 |
| 4 | `document_version` | `document_version_fts` | `document_version.id` | `document_id` | 同表 | extracted_text, notes, snapshot_json | **是** |
| 5 | `drawing` | `drawing_fts` | `drawing.id` | NULL | 同表 | name, drawing_no | 否 |
| 6 | `drawing_version` | `drawing_version_fts` | `drawing_version.id` | `drawing_id` | 同表 | revision, extracted_text, notes | **是** |
| 7 | `meeting` | `meeting_fts` | `meeting.id` | NULL | 同表 | title, transcript_text | 否 |
| 8 | `meeting_minutes` | `meeting_minutes_fts` | `meeting_minutes.id` | `meeting_id` | 同表 | version_no, content_md | **是** |
| 9 | `message` | `message_fts` | `message.id` | NULL | 同表 | content_md | 否 |
| 10 | `evidence` | `evidence_fts` | `evidence.id` | NULL | 同表 | title, body | 否 |
| 11 | `source_reference` | `source_reference_fts` | `source_reference.id` | NULL | 同表 | context_excerpt, locator | 否 |
| 12 | `issue` | `issue_fts` | `issue.id` | NULL | 同表 | ref_no, title, description_md | 否 |
| 13 | `risk` | `risk_fts` | `risk.id` | NULL | 同表 | ref_no, title, description_md | 否 |
| 14 | `task` | `task_fts` | `task.id` | NULL | 同表 | ref_no, title, description_md | 否 |
| 15 | `decision` | `decision_fts` | `decision.id` | NULL | 同表 | ref_no, title, conclusion_md | 否 |
| 16 | `action_measure` | `action_measure_fts` | `action_measure.id` | NULL | 同表 | ref_no, name, description | 否 |
| 17 | `entity` | `entity_fts` | `entity.id` | NULL | 同表 | name | 否 |
| 18 | `entity_alias` | `entity_alias_fts` | `entity_alias.id` | NULL | 同表 | alias | 否 |
| 19 | `business_subject_alias` | `business_subject_alias_fts` | 同表 `id` | NULL | 同表 | alias | 否 |
| 20 | `knowledge_item` | `knowledge_item_fts` | `knowledge_item.id` | NULL | 同表 | title, summary | 否 |
| 21 | `knowledge_version` | `knowledge_version_fts` | `knowledge_version.id` | `knowledge_item_id` | 同表 | version_no, content_md | **是** |
| 22 | `plan_activity_version` | `plan_activity_version_fts` | `plan_activity_version.id` | `activity_id` | 同表 | name, code | **是** |
| 23 | `extraction_result` | `extraction_result_fts` | `extraction_result.id` | NULL | 同表 | candidate_json, raw_text | 否 |
| 24 | `review_decision` | `review_decision_fts` | `review_decision.id` | NULL | 同表 | reason | 否 |

> 「同表」= 该行「业务表」自身的同名列。5 张版本表（#4/#6/#8/#21/#22）索引**全部历史版本**，每条版本一行。

**ID / 归属不可变触发器统一模板（24 张表按映射表生成）**
```sql
-- 非版本表（以 issue 为例）
CREATE TRIGGER IF NOT EXISTS trg_issue_id_immutable BEFORE UPDATE OF id ON issue
WHEN old.id IS NOT new.id
BEGIN SELECT RAISE(ABORT,'business primary key id immutable'); END;
-- 版本表（以 document_version 为例；归属外键同时不可变，保证 owner_biz_id 不漂移）
CREATE TRIGGER IF NOT EXISTS trg_document_version_id_immutable
BEFORE UPDATE OF id, document_id ON document_version
WHEN old.id IS NOT new.id OR old.document_id IS NOT new.document_id
BEGIN SELECT RAISE(ABORT,'business primary key id immutable'); END;
```

**生成结果核验方法（迁移后必须执行，全部可执行）**
```sql
-- ① 对象计数（QA E5 唯一口径：PRAGMA table_list + name NOT LIKE 'sqlite_%' 一次排除两张系统目录表）
SELECT (SELECT count(*) FROM pragma_table_list
        WHERE type='table' AND name NOT LIKE 'sqlite_%') AS entity_tables,      -- 期望 75（76 = 漏排除 sqlite_temp_schema 的错值）
       (SELECT count(*) FROM pragma_table_list
        WHERE type='virtual' AND name LIKE '%_fts') AS fts_tables,              -- 期望 24
       (SELECT count(*) FROM sqlite_master WHERE type='trigger') AS triggers;   -- 期望 126
-- ② 命名规则与分组计数
SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%_fts_ai';        -- 24
SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%_fts_au';        -- 24
SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%_fts_ad';        -- 24
SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%_id_immutable';  -- 24
SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%_no_delete';     -- 20
-- ③ 逐表字段映射核验：FTS 列序必须等于 [biz_id, owner_biz_id, is_deleted] + 该行文本列
--    对 24 行逐行执行 PRAGMA table_info(<fts表>)，比对列名与顺序（内存库实测 24/24 一致，见 §8-J）
-- ④ 结构完整性
PRAGMA foreign_key_check;    -- 无违规
PRAGMA integrity_check;      -- ok
-- ⑤ 方案 A 重建 + §7.6 五项一致性自检 + check_polymorphic_refs，结果写 audit_log
```
> 实测结论：按上述规则在内存库生成后，虚表 **24**、模板化触发器 **116**（72 同步 + 24 不可变 + 20 禁删除），加上 10 个专用触发器（基线冻结 2 + 抽取不可变 2 + 审核证据 2 + 合并链 4）= **126**，与 §0.2 完全一致（§8-J）。

---

## 8. 内存库实测验证汇总（R1 + R2）

> 全部验证在 Python `sqlite3` 的 `:memory:` 内存库执行（SQLite **3.53.1** / trigram 可用），**未触碰** `01_Data/epcs_intelligence.db`、未创建 `migrations/001_init.sql`、未安装任何依赖；R2 自检脚本只写于操作系统临时目录，未写入项目目录。本文 §0~§7 各处「实测」引用均落到本节对应编号。
> **R1 汇总（历史结论，保留）**：A~F 六组专项 + G1~G10 额外检查，全部 PASS、0 FAIL。
> **R2 汇总（见 §8-J）**：针对 7 项阻断 + 4 项实现边界，全部新增/修改 DDL 与 SQL 的编译 + 正/反向行为测试 **129 项，全部 PASS、0 FAIL**；按 §7.7 生成规则核验 **24 张 FTS 虚表 / 126 触发器**。R1 中被 R2 修订的结论已逐条标注（§6.5、§8-E E4、§8-F、§8-G G3/G7、§8-I）。

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
| E4 | 审核人 / 时间 / 理由 / 证据 NOT NULL 约束强制（REJECT 亦需理由） | **R1 结论不实**：R1 真值源 `evidence_source_reference_id` 可空，仅前三项 `NOT NULL`；R2-P3 已补 `NOT NULL` + FK + `trg_rd_evidence_i/u` 并给出正/反向用例（§12-P3），本行以 R2 结论为准 |
| E5 | `object_type CHECK` 覆盖 7 类正式对象 | PASS |
| E6 | G5 链：`AI_INFERENCE → CONFIRMED_FACT → 正式对象 CONFIRMED_FACT` | PASS |
| E7 | 原始抽取不得覆盖（`trg_er_immutable_u`，`candidate_json`/`raw_text`/`ingestion_job_id` 变更即 ABORT） | PASS |
| E8 | 原始抽取不得删除（`trg_er_immutable_d`） | PASS |
| E9 | `business_subject` 双层归一 + `business_subject_alias` 多别名 + `business_subject_source` 跨邮件 / 会议 / 文件证据链 | PASS |
| E10 | `business_subject_merge` 可逆合并（合并→撤销：置 `undone_at`/`undo_reason`/`valid_to`，`status` 回 ACTIVE，原业务记录不删除不覆盖） | PASS |

> 独立复核：把 `business_subject.id` 当作 `entity_id` 写入 `entity_relationship` 会被 FK 拦截，且该表无 `valid_to`/`undone_at`/`undo_reason` 可逆语义、不产生 `source_reference` 证据链 —— 印证「`entity_relationship` 不得承载事项合并」。

### 8-F R1-6 一致性整改十项（全部 PASS）
`department` 建表与 FK；`project.main_object_entity_id` / `equipment.manufacturer_entity_id` 两处显式 FK；`project_member` `COALESCE` 表达式唯一索引拦截重复 NULL 组合；`action_measure` XOR CHECK（**R2-P2 定案：恰好一个主属主，不是「至少一个」**）与 `action_measure_link`（0..N 附加属主，不得重复登记主属主）；`object_dimension_tag` REF/FREE_TEXT 互斥约束；`entity_identifier` 唯一范围收敛；`drawing_no` 按项目唯一（不同项目可用同图号、同项目同图号被拦）；多态引用孤儿自检 SQL 能查出孤儿；公共字段基线 A/B 逐表落地；表名 snake_case 单数统一（`issue_link` → `object_link`）。

### 8-G 额外架构检查实测（G1~G10，全部 PASS）
| # | 验证项 | 结果 |
|---|---|---|
| G1 | FTS5 trigram 可用（unicode61 中文命中 0 / trigram 命中 1） | PASS |
| G2 | 短词 LIKE 回退与别名表召回 | PASS（见 8-B） |
| G3 | 软删 `is_deleted` 镜像、重建与 4 项一致性自检 | R1 PASS；**重建 SQL 已由 R2-P5 方案 A 修订**（同步含软删的全部记录、去掉 `WHERE is_deleted=0`），一致性检查扩为 5 项（§7.6.1） |
| G4 | `object_dimension_tag` 值类型 CHECK 拦截非法行 | PASS |
| G5 | G5 六层 `info_nature` CHECK 生效，非法值被拦 | PASS |
| G6 | AI 预测版本 `is_forecast=1 → info_nature IN (PREDICTION,PROPOSAL)` 约束 | PASS |
| G7 | `check_polymorphic_refs`（R1 名 `sp_check_polymorphic_refs`；R2 改名并声明**非存储过程**）多态孤儿自检能查出孤儿（§7.6） | R1 PASS（仅演示部分类型）；**R2-P6 扩展为 8 类 / 10 分支全类型映射 + IS NULL 反连接 + 双向验证**（§7.6.2 / §8-J） |
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

### 8-I 全量 DDL 编译验证（R1 结论保留，R2 复核）

> R1 曾「直接从本文提取全部 SQL 代码块，剥离整行注释后按『先 75 张表 → 再 FTS 范式模板 → 再索引/触发器』依赖顺序在 `:memory:` 内存库编译」，证明「文档即 DDL」。R2 **未改动的表 DDL 与 R1 完全一致**，该结论继续有效；R2 另对全部新增/修改的 DDL 与 SQL 做编译 + 行为测试（§8-J / §12）。

| 项目 | 结果 |
|---|---|
| 75 张实体表 `CREATE TABLE` | 执行失败 **0**（R1 §8-I 验证；R2 改动的表在 §12 逐条复验） |
| 从本文 §0~§8 各 SQL 代码块提取的 `CREATE` 语句 | **133** 条全部编译通过，执行失败 **0**（75 `CREATE TABLE` + 2 FTS 虚表〔1 范式模板 + 1 版本表变体示例〕+ 19 显式触发器 + 37 显式索引；`PRAGMA foreign_key_check` 无违规、`integrity_check = ok`）；§7.6.2 完整自检 SQL 与 §7.6.1 方案 A 重建 SQL（含版本表变体）亦单独执行通过 |
| 按 §7.7 生成规则循环生成的模板化对象 | **24** 张 FTS 虚表 + **116** 个触发器（72 同步 + 24 不可变 + 20 禁删除） |
| 加上 10 个专用触发器（基线冻结 2 + 抽取不可变 2 + 审核证据 2 + 合并链 4） | 触发器合计 **126**（= §0.2 口径） |
| `PRAGMA foreign_key_check` | 无违规 |
| `PRAGMA integrity_check` | `ok` |

> 说明：文本中的「2 个 FTS 虚表〔范式模板 + 版本表变体示例〕 / 19 个显式 `CREATE TRIGGER`」是**模板化表达**，与 §0.2 的 24 / 126 不矛盾；迁移脚本按 §7.7 的 24 行映射表生成后对象数即为统计值。统计须用 `PRAGMA table_list` 的 `type` 列区分 `table / virtual / shadow / view`，并以 `name NOT LIKE 'sqlite_%'` 一次排除 `sqlite_schema` 与 `sqlite_temp_schema` 两张系统目录表（**只排除前者得 76 而非 75**，QA 阶段 A 实测 E5）；`sqlite_autoindex_*`（`sql IS NULL`）属 PK/UNIQUE 自动索引，不计入显式索引。
>
> **「文档显式 DDL」与「迁移生成后对象」双口径对照（QA 要求区分，避免被判定为自相矛盾）**
>
> | 口径 | 实体表 | FTS 虚表 | 触发器 | 含义 |
> |---|---|---|---|---|
> | 文档显式 DDL（本文各 SQL 代码块，可逐条 grep / 编译） | 75 | **2**（1 范式模板 + 1 版本表变体示例） | **19**（本文显式给出的专用触发器与模板示例） | 「文档即 DDL」编译验证的对象；FTS 与多数触发器以「1 模板 + 清单」表达 |
> | 迁移生成后对象（**§0.2 正式统计口径**） | 75 | **24** | **126**（116 模板化 + 10 专用） | 按 §7.7 的 24 行映射表 / §8-H 的 20 张清单循环生成后的正式库对象数 |
>
> 两者是**同一设计的两种表达层级**，不是两套互相矛盾的数字：QA 阶段 A 对 R1 实测的「1 张 FTS / 8 触发器」属第一行口径（当时）；R2 因新增审核证据触发器、合并链守卫触发器、版本表模板变体示例（虚表 + 3 同步触发器）等，显式对象增至 2 张 FTS / 19 触发器，而生成后口径恒为 24 / 126。**复审请以第二行（§0.2）为准，编译验证请以第一行为准。**
>
> 核验脚本陷阱（非 DDL 缺陷）：若保留整行 SQL 注释，「注释 + `CREATE TABLE`」会被合并成一条语句导致漏分类；剥离整行注释后全量通过。R2 自检脚本同样遵循此规则（Python `executescript` 支持含 `BEGIN...END` 的触发器体）。

### 8-J R2 定向整改内存库自检（新，129 项 PASS / 0 FAIL）

> 环境：Python 3.13 / `sqlite3` `:memory:` / **SQLite 3.53.1**；每个连接单独执行 `PRAGMA foreign_keys=ON`（G9 结论）。脚本仅置于操作系统临时目录，**未写入项目目录、未创建任何 .sql 迁移文件、未触碰正式库**。

| 分组 | 覆盖 | 正向（预期通过） | 反向（预期被拒绝 / 检出） | 结果 |
|---|---|---|---|---|
| J1 / P1 跨计划一致性 | 3 个 `UNIQUE(plan_id,id)` 父键 + 7 张子表复合 FK | 6 类同计划对象插入成功 | 7 项跨计划写入全部被 `FOREIGN KEY constraint failed` 拒绝 | PASS |
| J2 / P2 属主语义 | XOR CHECK + **`measure_type` 语义 CHECK** + `action_measure_link` + `q7` 全类型 | 恰好 1 主属主且 `measure_type` 匹配 + 2 条合法附加属主 | 双主属主 / 零主属主 / **`RISK_RESPONSE` 挂 `issue_id`** / **`ISSUE_REMEDY` 挂 `risk_id`** 被 `CHECK` 拒绝；**`link.ref_id` 孤儿被 `q7` 检出**；重复登记主属主被自检检出 | PASS |
| J3 / P3 审核证据 | `NOT NULL` + FK + 2 触发器 | 有效证据写入成功 | 空证据（`NOT NULL`）/ 证据不存在（FK）/ 证据已软删（触发器）/ UPDATE 换软删证据（触发器）/ 事后软删（自检） | PASS |
| J4 / P5 方案 A 重建 | 全量重建（含**版本表 `owner_biz_id` 变体**）+ 5 项一致性 + 24 不可变触发器 | 重建前后 3 行 / 1 软删镜像一致；版本表 `owner_biz_id` = 归属主表 UUID；重复 `biz_id` 检测返回 0 行 | 复现 R1 旧 SQL（带 `WHERE is_deleted=0`）重建后**仅 2 行**，证明状态不一致；`UPDATE id` 与版本表归属外键变更被 ABORT；§7.3 恒 `NULL` 旧模板被判定为缺陷并由变体取代 | PASS |
| J5 / P6 自检语句集 | 23 类 `target` 全集 + 8 类引用 / 10 分支 | 正常数据 10 分支合计 **0 行** | 注入 10 行孤儿 / 非法 type 后 **10 个分支全部检出** | PASS |
| J6 / P7 可逆合并链 | 部分唯一索引 + 4 触发器 | 合法链 A→B / C→B、撤销联动状态恢复、撤销后重新合并 | 循环 B→A / 合并到非根 / 多目标（`UNIQUE`）/ 自合并（`CHECK`）/ 撤销缺字段 / 篡改 from-to / 复活已撤销 / 撤销后状态不一致（自检检出） | PASS |
| J7 / B1 生成规则 | 24 行映射 + 确定规则 + 核验 SQL | 生成 24 虚表 / 72 同步 / 24 不可变 / 20 禁删除 = **116**，加 10 专用 = **126**；24 行字段映射逐表比对 0 差异 | — | PASS |
| J8 / B3+B4 人员 ID | 全部审计责任人字段 FK + `person.id` UUID CHECK（含三张 `*_status_history.changed_by`，QA 阶段 B 补强核验后补齐） | `merged_by` / `undone_by` / `changed_by` 为合法 `person.id` 或 NULL | 填姓名被 FK 拒绝（含三张状态历史表）；非法格式 `person.id` 被 `person.id` UUID CHECK 拒绝 | PASS |

> **合计 129 项断言全部 PASS、0 FAIL**。另按**文档原文 DDL** 做 B4 专项核验（QA 阶段 B 补强核验 S5-1 / S5-2）：静态确认 `person.id` UUID CHECK 与三张 `*_status_history.changed_by → person(id)` FK 全部存在，行为断言非法格式 `person.id` 被 `CHECK constraint failed` 拒绝（拒绝原因正确，非 FK / NOT NULL 假阳性），`r2_doc_compile.py` 输出 PASS。逐项「问题 → 决策 → DDL/约束 → 正向测试 → 反向测试 → 影响文档清单」见《Phase1.2_R2_架构评审整改记录.md》；边界声明与统计见《Phase1.2_R2_架构评审整改完成报告.md》。

---

## 9. 索引与唯一约束汇总

| 类型 | 对象 |
|---|---|
| 表内 UNIQUE / PK | 全部 75 张表的 `id`；`project_code`、`org_code`、`message_id_text`、各 `ref_no`、`config_key`、4 张 `project_*` 关联、`plan(plan_id,version_no)`、`baseline(plan_id,baseline_no)`、`baseline(plan_id,plan_version_id)`、`plan_activity(plan_id,code)`、`plan_activity_version(activity_id,plan_version_id)`、`*_version` 版本号、各 `*_link` 组合键 |
| 显式 UNIQUE INDEX | `uq_plan_code`、`uq_pab_active`（部分唯一，WHERE is_active=1）、`uq_pm`（COALESCE 表达式）、`uq_ei`（COALESCE 表达式）、`uq_dr`（COALESCE 表达式）、`idx_doc_sha`（部分唯一） |
| 普通索引 | `idx_person_org/dept`、`idx_pm_proj`、`idx_equip_sys/cat/mfr`、`idx_plan_proj`、`idx_activity_plan`、`idx_pav_ver/change`、`idx_bsl_plan`、`idx_bs_canonical`、`idx_issue_proj/status`、`idx_risk_proj`、`idx_task_proj`、`idx_am_risk/issue`、`idx_ol_left/right`、`idx_dl_ref`、`idx_el_ref`、`idx_sr_entity/source`、`idx_odt_obj/dim`、`idx_rd_queue`、`idx_rro_obj`、`idx_audit_target`、`idx_ei_lookup` |
| FTS | 24 张 trigram 虚表（§7.2） |

> **R2 新增唯一约束 / 索引（P1 / P7）**：
> - `plan_version UNIQUE(plan_id, id)`、`plan_activity UNIQUE(plan_id, id)`、`baseline_version UNIQUE(plan_id, id)` —— 3 个**复合外键父键**。SQLite 复合外键要求被引用列存在列数/顺序匹配的 UNIQUE / PRIMARY KEY，缺一即报 `foreign key mismatch`；已内存库实测（§8-J J1）。
> - `uq_bsm_active_from ON business_subject_merge(from_subject_id) WHERE is_active=1` —— 部分唯一索引，保证「一个主体只能有一个有效合并目标」（P7）。
> **R2 补充的显式外键（B3 / B4；非索引，不改变显式索引计数）**：`baseline_version.approved_by`、`plan_active_baseline.switched_by`、`baseline_switch_log.switched_by / audit_log_id / from_baseline_id / to_baseline_id`、`business_subject_merge.merged_by / undone_by`、三张 `*_status_history.changed_by` 全部指向 `person(id)` 或对应目标表；`review_decision.evidence_source_reference_id` 改为 `NOT NULL REFERENCES source_reference(id)`（P3）。SQLite **不自动**为 FK 建索引，故这些 FK 不增加显式索引数。另 `person.id` 补 `CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')`（B4 人员 ID 锚点，QA 阶段 B 补强核验 S5-2），属列级 CHECK，同样不改变索引计数。

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

## 11. 与其余 R2 文档的一致性锚点

> **R2 统一统计口径（全部文档共同引用 §0.2）**：实体表 **75**（46+29）／ FTS5 虚表 **24** ／ 触发器 **126** ／ 视图 **0**。任何文档不得再出现「触发器 96」或任何宣称整改已整体通过 / 全部闭环的 R1 口径与结论。

| 文档 | 必须一致的内容 |
|---|---|
| 核心实体数据字典 | 75 张表逐表字段、基线 A/B 标注、约束、索引；**P1 新增 2 列 / 3 复合唯一键、P2 属主语义、P3 证据 NOT NULL、P7 合并守卫、B3/B4 人员 FK** |
| 实体关系 ER 图 | 75 张表主要关系；复合 FK 的「同计划」语义、P7 有效合并链、**P4 Entity 与 BusinessSubject 双层分界** |
| 统一数据模型总体设计 | §0.2 数量、12 架构问题方案、检索路由（trigram + 双引号 + 短词回退）、**P2「恰好一个主属主 + 0..N 附加属主」/ P6 `check_polymorphic_refs` 措辞** |
| 数据来源与证据追溯规范 | `business_subject_source`、审核结果链、**P3 证据必填 / P4 双层追溯（Entity 经 `source_reference` 直接追溯）/ P6 完整自检映射** |
| 版本及历史管理规范 | `plan_active_baseline` / `baseline_switch_log` / `plan_activity_version`；**P1 同计划、P5 方案 A 重建、P7 撤销状态恢复** |
| 架构决策记录 | ADR-1~12（R1 修订）＋ **R2 新增 ADR-13~19**（P1~P7 / B1~B4 决策，其中 P2 / P3 / P5 / P7 为四条独立 ADR）＋「R2 整改对 ADR 的影响汇总」表 |
| 待确认事项清单 | N1~N10 ＋ **R2 新增 N11~N14**（实现边界收敛与遗留项） |
| 架构评审整改记录 / 完成报告（R1） | 开头加「R2 承接说明」，保留 R1 正文；被 R2 修订的结论标注「本结论已被 R2 修订，见 …」 |
| **R2 架构评审整改记录（新增）** | 逐项：问题 → 决策 → DDL/约束 → 正向测试 → 反向测试 → 影响文档清单 |
| **R2 架构评审整改完成报告（新增）** | 总览表、七项复核表、统计口径、验证依据、边界声明、遗留事项、待审核声明 |

---

## 12. R2 定向整改总表（7 项阻断 + 4 项实现边界）

> 本节为 R2 的**变更索引与决策摘要**；逐项完整记录（问题 → 决策 → DDL/约束 → 正向测试 → 反向测试 → 影响文档清单）见《Phase1.2_R2_架构评审整改记录.md》，边界与统计见《Phase1.2_R2_架构评审整改完成报告.md》。
> **全文 `§12-P1`～`§12-P7` 引用即指向下表对应编号行**（P1~P7 为本节锚点）；`§8-J` 为 R2 自检分组。

### 12.1 七项阻断（P1~P7）

| 编号 | 问题 | 架构决策（一句话） | 数据库级机制 | 统计影响 |
|---|---|---|---|---|
| **P1** | 4 类计划对象可跨计划拼装 | 用 `UNIQUE(plan_id,id)` 复合唯一键 + **共享 `plan_id` 的复合外键**，7 张子表全部同计划，不靠应用层 | 3 个父键 + 7 张子表复合 FK（§2） | 0 表 / 0 触发器；+3 唯一约束、+2 列 |
| **P2** | `action_measure` XOR 与报告「至少一个」/ link M:N 冲突；QA 补：`RISK_RESPONSE` 挂 `issue_id` 无语义 CHECK、`link.ref_id` 写不存在对象被接受 | 保留 XOR 作**唯一主属主**；`action_measure_link` 只做 **0..N 附加属主**；`measure_type` 与主属主强绑定；link 孤儿由 P6 `q7` 必然检出（**不伪装成硬 FK**） | 保留 XOR CHECK；**新增 `measure_type` 语义 CHECK**（§4）；职责边界自检 SQL（§7.6.3）；`q7` 全 23 类覆盖（§7.6.2） | 无 |
| **P3** | `review_decision` 证据可空，文档却称必填 | **不允许例外审核类型**，所有决定必须绑定来源证据 | `NOT NULL` + FK + `trg_rd_evidence_i/u`（拒绝软删证据）；事后软删由自检检出 | **+2 触发器** |
| **P4** | 追溯规范把 `plan_activity` / `entity` 写成 1:1 挂 `subject_id`；QA 追问 `object_type='ENTITY'` 合法性 | **保留双层结构**：Entity 经 `source_reference` 直接追溯；Issue/Risk/Task/Decision/KnowledgeItem 经 `business_subject` 归一；`review_result_object.ENTITY` **明确为合法多态类型**，纳入 P6 `q8` 映射（§7.6.2） | `business_subject.subject_kind` 不含 ENTITY / PLAN_ACTIVITY；`entity` 无 `subject_id`（不改 DDL、不加禁止 CHECK） | 无 |
| **P5** | 重建 SQL 带 `WHERE is_deleted=0` 与「软删保留 FTS 行」冲突；QA 补：§7.3 模板 `owner_biz_id` 恒 NULL 与 §7.2 矛盾、`UPDATE id` 后 FTS 残留旧 `biz_id` | 采用**方案 A**：重建同步全部记录（含软删）保留镜像；确立「业务主键 ID 不可变」；修复版本表 `owner_biz_id` 模板 / 重建变体 | 重建 SQL 去 `WHERE`（含版本表变体 §7.6.1 ⑥）；5 项一致性检查；§7.3 版本表模板变体；**24 个 ID/归属不可变触发器**（§7.7） | **+24 触发器** |
| **P6** | 自检只演示部分类型且 `sp_` 命名误导 | 改名 `check_polymorphic_refs`，明确为**应用层 SQL 自检语句集（非存储过程）**；给出 8 类 / 10 分支全类型映射 + IS NULL 反连接 + 双向验证 | §7.6.2 完整 SQL；统一大写 type 值 | 无 |
| **P7** | 可逆合并链无数据库级保护 | 有效合并链唯一性：**部分唯一索引 + 4 触发器**（守卫/联动/撤销）+ 事务；目标必须是有效根、禁止循环与多级链 | `uq_bsm_active_from` + `trg_bsm_guard_i / apply_i / guard_u / apply_u`（§4） | **+4 触发器**、+1 部分唯一索引 |

### 12.2 四项实现边界（B1~B4）

| 编号 | 结论 |
|---|---|
| **B1** | 24 张 FTS / 72 同步触发器 / 20 禁删除触发器不再只写「循环生成」：§7.7 给出**确定生成规则 + 24 行逐表字段映射表 + 生成结果核验 SQL**；内存库实测生成 24 虚表 / 116 模板化触发器、24 行字段比对 0 差异。 |
| **B2** | FTS5 虚表不支持 UNIQUE / `CREATE INDEX`；`biz_id` 唯一性由**主表 `id` 主键 + 三向同步触发器**保证，另给可执行重复 `biz_id` 检测语句（§7.6.1 ⑤），正常态 0 行。 |
| **B3** | 逐字段裁定：`baseline_switch_log.from_baseline_id / to_baseline_id / audit_log_id / switched_by`、`baseline_version.approved_by`、`plan_active_baseline.switched_by`、`business_subject_merge.merged_by / undone_by`、三张 `*_status_history.changed_by` 均属**遗漏 → 补 FK**（见 §12.3 与整改记录 B3 裁定表）；`audit_log.actor_id`（USER→person / AI→ai_analysis_run / SYSTEM→NULL）、`object_dimension_tag.value_id`、`ingestion_job.source_id`、`email.from_addr` 等属**有意保留的多态 / 自由文本**，给出分派规则并纳入 `check_polymorphic_refs`。 |
| **B4** | 统一人员 ID 口径：所有 `reviewer_person_id` / `switched_by` / `changed_by` / `merged_by` / `undone_by` / `approved_by` / `owner_person_id` / `assignee_person_id` / `sender_person_id` 一律为 **`person.id` 的 32 位小写 hex UUID**（`REFERENCES person(id)`），禁止姓名/自由文本；可空时 `NULL` = SYSTEM/AI 执行且必须写 `audit_log`。**QA 阶段 B 补强核验后补齐**：三张 `*_status_history.changed_by` 补 `REFERENCES person(id)`（S5-1）、`person.id` 补 UUID CHECK 作为锚点（S5-2），使 §9 / §8-J J8 的声明与 DDL 一致。 |

### 12.3 字段级变更清单（R1 → R2）

| 表 | 字段 / 对象 | R1 | R2 | 原因 |
|---|---|---|---|---|
| `plan_version` | `UNIQUE(plan_id,id)` | 无 | 新增 | P1 复合外键父键 |
| `plan_activity` | `UNIQUE(plan_id,id)`、`first_version_id` 复合 FK | 单列 FK | 新增父键 + 改复合 FK | P1 |
| `baseline_version` | `UNIQUE(plan_id,id)`、`plan_version_id` 复合 FK、`approved_by` | 单列 FK / 无 FK | 改复合 FK / 补 person FK | P1 / B3 / B4 |
| `plan_active_baseline` | `baseline_version_id` 复合 FK、`switched_by` | 单列 FK / 无 FK | 改复合 FK / 补 person FK | P1 / B3 / B4 |
| `baseline_switch_log` | `from/to_baseline_id` 复合 FK、`audit_log_id` FK、`switched_by` FK | 仅 to 有单列 FK | 全部补齐 | P1 / B3 / B4 |
| `plan_activity_version` | **新增 `plan_id NOT NULL`** + 2 复合 FK | 2 单列 FK | 复合 FK | P1 |
| `activity_dependency` | 3 复合 FK | 3 单列 FK | 复合 FK | P1 |
| `progress_record` | **新增 `plan_id NOT NULL`** + 2 复合 FK | 2 单列 FK | 复合 FK | P1 |
| `review_decision` | `evidence_source_reference_id` | 可空 FK | **`NOT NULL` + FK + 2 触发器** | P3 |
| `business_subject_merge` | `merged_by` / `undone_by` | `TEXT NOT NULL` / 无 FK | 可空 `REFERENCES person(id)` | B4 / P7 |
| `business_subject_merge` | `uq_bsm_active_from` + 4 触发器 | 仅 `CHECK(from<>to)` | 新增 | P7 |
| `person`（QA S5-2） | `id ... CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')` | `id TEXT PRIMARY KEY`（无 CHECK） | 补 UUID CHECK，人员 ID 锚点 | B4 |
| 三张 `*_status_history`（QA S5-1） | `changed_by TEXT REFERENCES person(id)` | `changed_by TEXT`（无 FK） | 补人员 FK（可空 = SYSTEM/AI） | B3 / B4 |
| `action_measure` | 注释口径 | 「至少一个」 | 「恰好一个主属主 + 0..N 附加属主」 | P2 |
| 24 张内容表 | `trg_<表>_id_immutable` | 无 | 新增 24 个 | P5 |
| 全文 | `sp_check_polymorphic_refs` | R1 名称 | `check_polymorphic_refs`（非存储过程） | P6 |

### 12.4 R2 新增 ADR（编号接续 R1 的 ADR-12）

R2 新增 7 条 ADR；按主理人要求，**P2 / P3 / P5 / P7 各为独立条目**，逐条给出「决策 / 备选方案 / 理由 / 影响文档」：

| ADR | 主题 | 独立条目 |
|---|---|---|
| `ADR-13` | P1 跨计划一致性（复合唯一键 + 复合外键） | — |
| `ADR-14` | **P2 `action_measure` 属主语义**（恰好一个主属主 + 0..N 附加属主；含 `measure_type` 语义 CHECK 与 link 孤儿） | ✅ |
| `ADR-15` | **P3 `review_decision` 证据必填**（无例外审核类型） | ✅ |
| `ADR-16` | P4 Entity / BusinessSubject 双层结构 + P6 自检语句集（含 ENTITY 合法类型定性） | — |
| `ADR-17` | **P5 FTS 方案 A 重建 + 业务主键不可变 + 版本表 `owner_biz_id` 变体** | ✅ |
| `ADR-18` | **P7 可逆合并链数据库级守卫** | ✅ |
| `ADR-19` | B1~B4 实现边界（24 行映射生成规则 / `biz_id` 唯一 / 多态与可选 FK 裁定 / 人员 ID 口径） | — |

详见《Phase1.2_架构决策记录.md》R2 章节。

### 12.5 边界声明与状态

- **未创建** `01_Data/migrations/001_init.sql` 或任何 `.sql` 迁移文件；**未对** `01_Data/epcs_intelligence.db` 执行任何 DDL/DML；空库保持（8192 bytes / 业务表 0）。
- **未导入**任何资料；**未接入**外部账号 / Ollama / DWG SDK；**未改动**旧知识库 `D:\ALLAN\个人知识库`；**未回改** `09_Archive/Phase1.2_R1_原稿/` 归档副本。
- 自检仅在操作系统临时目录以 Python `sqlite3.connect(':memory:')` 执行，脚本未写入项目目录；**未执行 git commit**（由主理人统一提交）。
- **当前状态：R2 定向整改完成，等待系统架构师再次审核**；Phase 1.3（幂等迁移 + 空库升级）需另行批准。
