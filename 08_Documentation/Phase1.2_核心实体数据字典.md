# Phase1.2 核心实体数据字典

> 版本：R1（架构评审整改后）｜日期：2026-11-12
> R1 整改同步：2026-11-12，以《Phase1.2_数据库表结构设计.md》(R1) 为唯一真值源
> 表名/字段名全英文 snake_case；说明文字中文。公共字段基线 A/B 见 §0.2，下文逐表标注所用基线；与《数据库表结构设计》的 CREATE TABLE 一一对应。
> 所有"值类"枚举（维度、性质、状态）一律用 `dimension` / `CHECK` / `system_config` 归口，禁止硬编码字面值（G7）。

---

## 0. 统一口径与全表索引（R1 定稿，与《表结构设计》§0.2 / §0.3 / §0.4 严格一致）

### 0.1 统一对象数量统计（8 份文档共同引用）

| 类别 | 数量 | 说明 |
|---|---|---|
| 实体表（业务主表，清单 A） | **46** | 见 §0.3 清单 A |
| 实体表（辅助 / 关联 / 桥 / 历史 / 治理，清单 B） | **29** | 含 `schema_version` 元信息表 1 张 |
| 实体表合计 | **75** | `CREATE TABLE`，不含 `CREATE VIRTUAL TABLE` |
| FTS5 虚拟表 | **24** | `tokenize='trigram'`，一一对应见 §7.2 |
| 触发器 | **96** | FTS 同步 72 + 基线冻结 2 + 抽取不可变 2 + 禁物理删除 20 |
| 视图 | **0** | 第一期不引入 |

> 统计口径：实体表 = `CREATE TABLE`；FTS 表 = `CREATE VIRTUAL TABLE ... USING fts5`；触发器 = `CREATE TRIGGER`（FTS 同步触发器按 24×3 计入）。唯一索引 / 普通索引清单见《表结构设计》§9。

### 0.2 公共字段基线 A / B（逐表标注，SQL 与数据字典严格对应）

```
-- 基线 A（正式业务表，完整公共字段集）
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

-- 基线 B（辅助 / 关联 / 桥 / 历史 / 日志表，精简公共字段集）
id            TEXT PRIMARY KEY CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')
created_at    TEXT NOT NULL
is_deleted    INTEGER NOT NULL DEFAULT 0
```

- **UUID 规则**：`uuid4().hex`（32 位小写十六进制），DB 层 `CHECK` 实测生效；禁止用文件名 / 姓名 / 项目名作主键。
- **时间字段**：`event_time` / `source_time` / `created_at` / `updated_at` / `valid_from` / `valid_to` 严格区分，均为 ISO8601 UTC 文本。
- **逐表标注**：下文每张表标题后的 `［基线A］` / `［基线B］` 即该表所用公共字段集，与《表结构设计》各 DDL 行尾 `-- 基线A` / `-- 基线B` 注释一一对应。
- **两个维度须分清**：§0.3 的「清单 A / 清单 B」是**对象分类**（业务主表 / 辅助·关联·桥·历史·治理表）；§0.2 的「基线 A / 基线 B」是**公共字段集合**，二者是不同维度。例如 `review_queue` / `review_decision` / `review_result_object` / `object_dimension_tag` / `progress_record` 属清单 B 分类，但 DDL 用基线 A 字段集；`email_attachment` / `drawing_object` / `ingestion_job` / `ai_analysis_run` / `extraction_result` 属清单 A 分类，但 DDL 用基线 B 字段集。一律以 SQL DDL 实测标注为准。
- `schema_version` 为**独立元信息表**：主键 `version INTEGER PRIMARY KEY`，仅 `applied_at` / `description` / `ddl_fingerprint`，不套用 A/B 基线（无 `id` / `is_deleted` / 审计字段）。
- 轻量维度目录表（`discipline` / `area` / `system` / `equipment_category`）与 Phase 后期骨架表（`user` / `role` / `permission` / `user_role` / `role_permission`）DDL 未显式标注基线，字段形态为基线 B 精简集，见各表说明。

### 0.3 全表清单（A 业务主表 46 / B 辅助表 29）

**A 业务主表（46）**
`project, project_phase, organization, department, person, discipline, area, system, equipment_category, equipment, plan, plan_version, baseline_version, plan_active_baseline, plan_activity, plan_activity_version, email, email_attachment, document, document_version, drawing, drawing_version, drawing_object, meeting, meeting_minutes, message, source_reference, evidence, issue, risk, task, action_measure, decision, object_link, entity, entity_alias, entity_identifier, entity_relationship, business_subject, business_subject_alias, business_subject_merge, knowledge_item, knowledge_version, ingestion_job, ai_analysis_run, extraction_result`

**B 辅助 / 关联 / 桥 / 历史 / 治理表（29，含 `schema_version`）**
`schema_version, project_member, project_discipline, project_area, project_system, project_equipment, baseline_switch_log, activity_dependency, progress_record, issue_status_history, risk_status_history, task_status_history, action_measure_link, decision_link, evidence_link, business_subject_source, review_queue, review_extraction_link, review_decision, review_result_object, knowledge_entity_link, object_dimension_tag, audit_log, system_config, user, role, permission, user_role, role_permission`

> 合计 46 + 29 = **75 张实体表**，与 §0.1 及《表结构设计》§0.4 一致。

### 0.4 SQL ↔ 数据字典双向对应核对表

**双向声明（R1 验收项 7）**：
1. 《数据库表结构设计》§1~§7 中每一条 `CREATE TABLE` 都在本文有逐表说明（小节号见下表）；
2. 本文列出的每一张表都在《数据库表结构设计》有对应 `CREATE TABLE` 定义；
3. 表名统一 snake_case 单数；旧稿 `issue_link`（总体设计 §4）与 `object_link`（SQL）不一致、`document_fts(name, snapshot_json)` 等索引列错配均已消除；
4. 逐表 `info_nature` 默认值、基线标注、FTS 对应关系与 §0.2 / §7.2 /《表结构设计》§10.2 三方一致。

| 域 | 表数 | 表（按本文说明归域，共 75 张） | 本文小节 | SQL 位置 | 其中建 FTS |
|---|---|---|---|---|---|
| 1 项目与组织 | 15 | `project, project_phase, organization, department, person, project_member, discipline, area, system, equipment_category, equipment, project_discipline, project_area, project_system, project_equipment` | §1.1~§1.10 | §1 | 0 |
| 2 计划管理 | 9 | `plan, plan_version, baseline_version, plan_active_baseline, baseline_switch_log, plan_activity, plan_activity_version, activity_dependency, progress_record` | §2.1~§2.9 | §2 | 1（`plan_activity_version`） |
| 3 信息与文件 | 13 | `email, email_attachment, document, document_version, drawing, drawing_version, drawing_object, meeting, meeting_minutes, message, source_reference, evidence, evidence_link` | §3.1~§3.8 | §3 | 11 |
| 4 问题/风险/任务闭环 | 15 | `business_subject, business_subject_alias, business_subject_merge, business_subject_source, issue, issue_status_history, risk, risk_status_history, task, task_status_history, action_measure, action_measure_link, decision, decision_link, object_link` | §4.1~§4.6 | §4 | 6（含 `business_subject_alias`） |
| 5 实体关系与知识 | 7 | `entity, entity_alias, entity_identifier, entity_relationship, knowledge_item, knowledge_version, knowledge_entity_link` | §5.1~§5.5 | §5（`entity` DDL 前置在 §1） | 4 |
| 6 AI 处理与系统治理 | 15 | `ingestion_job, ai_analysis_run, extraction_result, schema_version, review_queue, review_extraction_link, review_decision, review_result_object, audit_log, system_config, user, role, permission, user_role, role_permission` | §6.1~§6.11 | §6 | 2 |
| 7 共享桥表 | 1 | `object_dimension_tag` | §7.1 | §7.1 | 0 |
| 合计 | **75** | 与 §0.3 清单 A+B 完全对齐 | 逐表说明见各节 | §1~§7 | **24**（§7.2） |

> 分域仅为书写归口，不影响双向对应：`entity` 在《表结构设计》§1 前置定义（域 1 代码块内），本字典说明列于 §5.1；`business_subject_alias` 属 §0.3 清单 A，本字典按语义并入 §4.1 分层说明。一律以表名为准，不受书写域顺序影响。

**不建 FTS 的纯数值 / JSON 元数据表（及理由）**：以下表虽有文本 / JSON 字段，但性质为纯数值、编码、枚举或结构化元数据，无自由文本全文检索价值，R1 明确不建 FTS（短枚举走 `system_config` 归口 / 精确索引 / LIKE 回退，不进 trigram）：

| 类别 | 代表表 | 代表性字段 | 不建 FTS 理由 |
|---|---|---|---|
| 结构一致性 / 指纹 / 哈希 | `schema_version`、`plan_version`、`baseline_version`、`document`、`drawing`、`document_version`、`drawing_version`、`email_attachment` | `ddl_fingerprint`、`content_hash`、`sha256`、`snapshot_json` | 哈希 / 指纹 / JSON 快照为机器比对用，非自然语言检索对象；`plan_version.snapshot_json` 的活动集已由 `plan_activity_version_fts` 覆盖 |
| 授权与切换审计 | `plan_active_baseline`、`baseline_switch_log`、`audit_log` | `authorization_ref`、`reason`、`before_json` / `after_json` | 审计 / 授权字段短且按 `target_type+target_id` 精确查询，走普通索引 `idx_audit_target` / `idx_bsl_plan` |
| 纯 FK 组合 / 关联桥 | `project_member`、`project_discipline` / `project_area` / `project_system` / `project_equipment`、`activity_dependency`、`evidence_link` / `decision_link` / `action_measure_link` / `knowledge_entity_link` / `business_subject_source` / `review_extraction_link` / `user_role` / `role_permission` | 纯 `*_id` 组合 + `relation_type` / `link_role` | 无自由文本；完整性由 `UNIQUE` / 硬 FK / `sp_check_polymorphic_refs` 自检保证 |
| 数值 / 状态历史 | `progress_record`、`issue_status_history` / `risk_status_history` / `task_status_history` | `progress_pct`、`old_status` / `new_status` / `transition`、`reopen_count` | 数值与状态机枚举，按时间线精确查询；`reason` 短文本由应用层展示，不进全文索引 |
| 维度 / 标签 / 占位 | `object_dimension_tag`、`drawing_object`、`discipline` / `area` / `system` / `equipment_category` | `dimension` / `value_id` / `value_text`、`geometry_json` / `reserved_data`、`code` / `name` | 维度值由 `CHECK` + 精确索引 `idx_odt_obj/dim` 查询；`drawing_object` 为 ADR-10 预留占位不解析 |
| 运行日志 / 配置 / 骨架 | `ingestion_job`、`ai_analysis_run`、`system_config`、`user` / `role` / `permission` | `run_meta`、`output_summary`、`config_key` / `config_value`、`username` / `role_code` | 运行态日志与配置项按 key / 状态精确查询，无全文检索需求 |
| 审核链其余三表 | `review_queue`、`review_result_object`、`object_link`、`business_subject` / `business_subject_merge` / `entity_relationship` / `entity_identifier` | `candidate_summary`、`object_id`、`context_excerpt`、`canonical_subject_id` | 审核结果链靠外键与 `object_type+object_id` 精确映射（§6.5）；候选召回由 `business_subject_alias_fts` + `extraction_result_fts` 覆盖；本类表不单独建 FTS |

---

## 1. 域1 —— 项目与组织（底座）

### 1.1 `project` 项目 ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_code | text | Y | — | 项目编码（外部编号，UNIQUE） |
| name | text | Y | — | 项目名称 |
| main_object_entity_id | char(32) | N | — | FK→entity；承载"一艘主造对象"（船/平台型） |
| contract_summary | text | N | — | 合同事实摘要 |
| status | text | Y | 'ACTIVE' | 项目状态（system_config 归口） |
| started_at / planned_end_at / ended_at | text | N | — | 时间字段 |
| **索引/约束** | | | | `UNIQUE(project_code)` |

> **R1-6 整改（原结论作废）**：`main_object_entity_id` 已**显式** `REFERENCES entity(id)` 建立硬 FK；原稿「entity 表后置、动态引用、不建 FK」的说法**作废**。SQLite 允许 FK 引用后置创建的表（实测 §8 G10 PASS），`entity` 已在《表结构设计》§1 前置定义。
> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建；禁物理删除触发器：是（§8 20 张之一）。

### 1.2 `project_phase` 项目阶段实例（EPCS 实例） ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_id | char(32) | Y | — | FK→project |
| phase_code | text | Y | — | E/P/C/S 之一（dimension 归口）；同一项目可多实例（多轮工程迭代） |
| name | text | N | — | 实例名（如"第一次建造"） |
| seq_no | integer | Y | 0 | 同 project 下实例排序 |
| status | text | Y | 'ACTIVE' | 状态 |
| valid_from / valid_to | text | N | — | 生效区间 |
| **约束** | | | | `UNIQUE(project_id, phase_code, seq_no)` |

> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建；禁物理删除触发器：是。

### 1.3 `organization` 组织 ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| org_code | text | Y | — | 组织编码 UNIQUE |
| name | text | Y | — | 组织名（船东/船厂/设计院/分包/供应商/监理…） |
| org_type | text | Y | — | 组织类型（dimension 归口） |
| parent_id | char(32) | N | — | 自关联上级组织（**上下级单位**：母/子公司、总分包） |

> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建；禁物理删除触发器：是。
> **职责边界**：`organization.parent_id` = 单位间层级；单位内部部门另见 `department`（§1.4）。

### 1.4 `department` 部门 ［基线A］（R1-6 新增，原稿缺失补齐）
| 项 | 内容 |
|---|---|
| 用途 | 单位**内部**部门（产品确认书 A.1 `departments`，R1 前 SQL 缺失）；与 `organization.parent_id`（上下级单位）职责分离 |
| 主键 | `id`（TEXT UUID，CHECK 32 位小写 hex） |
| 外键 | `organization_id TEXT NOT NULL REFERENCES organization(id)`；`parent_id TEXT REFERENCES department(id)`（部门内部层级，自关联） |
| 关键字段 | `code`、`name`（均 NOT NULL） |
| 唯一约束/索引 | `UNIQUE(organization_id, code)` |
| info_nature 默认 | `CONFIRMED_FACT`（基线 A 定义） |
| 公共字段基线 | **基线 A**（id / project_id 无 / info_nature / created_at / updated_at / created_by / updated_by / is_deleted / deleted_at / del_status；本表 DDL 为基线 A 字段集，`project_id` 不适用故省略） |
| FTS | 不建（编码 / 名称短，按 `UNIQUE(organization_id, code)` 精确查询） |
| 关联 | `person.department_id` 可空 FK 指向本表 |

> DDL 原文见《表结构设计》§1；`person` 增可空 `department_id FK`（§1.5）。

### 1.5 `person` 人员 ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| organization_id | char(32) | Y | — | FK→organization |
| department_id | char(32) | N | — | FK→department（R1-6 新增，可空） |
| name | text | Y | — | 姓名 |
| email | text | N | — | 联系邮箱 |
| **索引** | | | | `idx_person_org(organization_id)`、`idx_person_dept(department_id)` |

> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建；禁物理删除触发器：是。

### 1.6 `project_member` 项目成员任职（项目×组织×角色 三维） ［基线B］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_id | char(32) | Y | — | FK→project |
| organization_id | char(32) | Y | — | FK→organization |
| person_id | char(32) | N | — | FK→person（可空：组织级角色） |
| role_name | text | Y | — | 角色（如设计主管/监理） |
| role_kind | text | N | — | 角色类型（dimension 归口，如项目角色/合同角色） |
| valid_from / valid_to | text | N | — | 任职区间 |
| is_contract_carrier | integer | N | 0 | =1 表示该任职承载**合同事实**（B.1 弱合同载体） |

> **R1-6 整改（原结论作废）**：原稿表内 `UNIQUE(project_id, organization_id, person_id, role_name, valid_from)` **作废** —— `person_id` / `valid_from` 可空，SQLite 的 `UNIQUE` 视 NULL 互不相等，重复行可插入。改为删除表内 `UNIQUE`，使用**表达式唯一索引**：
> ```sql
> CREATE UNIQUE INDEX IF NOT EXISTS uq_pm
>     ON project_member(project_id, organization_id, COALESCE(person_id,''), role_name, COALESCE(valid_from,''));
> CREATE INDEX IF NOT EXISTS idx_pm_proj ON project_member(project_id);
> ```
> 基线 B（精简公共字段集）；`info_nature`：本表无该列（基线 B 不含 info_nature）；FTS：不建；禁物理删除触发器：否。

### 1.7 `discipline` / `area` / `system` 维度目录（全局，跨项目共享） ［基线B 精简，DDL 未显式标注］
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| code | text | Y | 编码（UNIQUE） |
| name | text | Y | 名称（船体/轮机/电气/…；分段/舱室/机舱/…；压载/消防/电力/…） |
| parent_id | char(32) | N | 自关联父节点（分类树） |
| is_standard | integer | N | =1 标准件/通用项（跨项目共享） |

- **三表结构同构**，仅领域语义不同；不合并为一张"维度表"以保留 FK 纯粹性与字段扩展空间。
- 基线 B 精简字段集（仅 `id` / `code` / `name` / `parent_id` / `is_standard` / `created_at`，无 `info_nature` / `is_deleted` 全套）；FTS：不建；禁物理删除触发器：否。

### 1.8 `equipment_category` 设备分类树 ［基线B 精简，DDL 未显式标注］
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| code | text | Y | 分类编码 UNIQUE |
| name | text | Y | 分类名 |
| parent_id | char(32) | N | 自关联（分类树；层级标准见 D.2-3 未定） |

> 基线 B 精简字段集；FTS：不建；禁物理删除触发器：否。

### 1.9 `equipment` 设备 ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_id | char(32) | N | — | 范围锚点（可空：标准件目录跨项目共享） |
| name | text | Y | — | 设备名（主机/发电机/泵/阀/控制台…） |
| category_id | char(32) | N | — | FK→equipment_category |
| system_id | char(32) | N | — | FK→system（可先于系统定型为空） |
| manufacturer_entity_id | char(32) | N | — | FK→entity（厂商名归一） |
| equip_type | text | N | — | 内部分类位 |
| **索引** | | | | `idx_equip_sys(system_id)`、`idx_equip_cat(category_id)`、`idx_equip_mfr(manufacturer_entity_id)` |

> **R1-6 整改（原结论作废）**：`manufacturer_entity_id` 已**显式** `REFERENCES entity(id)` 建立硬 FK；原稿「表后置、动态、不建 FK」的说法**作废**。
> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建；禁物理删除触发器：否。

### 1.10 项目×维度 关联表（三维正交底座） ［基线B］
- `project_discipline(project_id, discipline_id)`、`project_area(project_id, area_id)`、`project_system(project_id, system_id)`、`project_equipment(project_id, equipment_id)`
- 每表：`id` PK，`project_id` FK，`discipline_id` / `area_id` / `system_id` / `equipment_id` FK，`UNIQUE(project_id, 维度_id)`；基线 B 精简字段集；FTS：不建。
- 说明：维度目录全局共享，项目横向施加（G1）；设备可跨项目共享（标准件目录）故用关联而非设备内嵌项目。

---

## 2. 域2 —— 计划管理（R1-1 基线只读 + R1-2 活动版本化）

### 2.1 `plan` 计划 ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_id | char(32) | Y | — | FK→project |
| name | text | Y | — | 计划名（L1 总计划 ~ L4 周计划，勿锁死为专用表，字段通用） |
| plan_code | text | N | — | 计划编码 |
| level | text | N | — | L1..L4（system_config 归口；L 级规范见 D.2-5 未定） |
| status | text | Y | 'DRAFT' | 状态 |
| **索引/约束** | | | | `idx_plan_proj(project_id)`；`uq_plan_code` = `CREATE UNIQUE INDEX ... ON plan(project_id, plan_code) WHERE plan_code IS NOT NULL`（部分唯一索引） |

> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建；禁物理删除触发器：是。

### 2.2 `plan_version` 计划版本 ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| plan_id | char(32) | Y | — | FK→plan |
| version_no | text | Y | — | 版本号 |
| content_hash | text | N | — | 版本内容 hash（版本化防伪） |
| is_forecast | integer | Y | 0 | =1 滚动预测版（AI 产出，info_nature=PREDICTION） |
| snapshot_json | text | N | — | 快照（活动集精简，渐进策略，见 ADR-9）；结构化活动集见 `plan_activity_version` |
| status | text | Y | 'DRAFT' | PUBLISHED / RECALLED 等 |
| **约束** | | | | `UNIQUE(plan_id, version_no)`；`CHECK((is_forecast=1 AND info_nature IN ('PREDICTION','PROPOSAL')) OR is_forecast=0)` |

> `info_nature` 默认 **`PREDICTION`**（基线 A 的 `CONFIRMED_FACT` 被本表覆盖）；基线 A；FTS：不建（结构化活动集文本由 `plan_activity_version_fts` 覆盖）；禁物理删除触发器：是。
> AI 只能创建预测版本：`is_forecast=1 → info_nature IN (PREDICTION, PROPOSAL)` + 应用层写入白名单 + `audit_log` 三重保证。

### 2.3 `baseline_version` 基线版本 ［基线A，全字段冻结］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| plan_id | char(32) | Y | — | FK→plan |
| plan_version_id | char(32) | Y | — | FK→plan_version（明确指向**一个完整计划版本**） |
| baseline_no | text | Y | — | 基线编号 |
| approved_at | text | Y | — | 批准时间 |
| approved_by | char(32) | N | — | 批准人 person_id |
| content_hash | text | Y | — | 基线内容指纹（NOT NULL） |
| is_readonly | integer | Y | 1 | `CHECK(is_readonly=1)`，恒为只读 |

> **R1-1 整改（原结论作废）**：原稿的 `is_active` 字段、`UNIQUE(plan_id, is_active)` 部分索引、"改 `is_active` 即切换当前基线"以及"触发器 `WHEN ... is_active` 强拦"表述**全部作废**。理由：`is_active` 只有 0/1，`UNIQUE(plan_id,is_active)` 会把一个计划的基线数限死为 2 条，且状态与内容同表，触发器一旦放行含 `is_active` 变更的 UPDATE 就无法阻止同语句顺带改内容字段。
> **R1 定稿**：
> - **删除** `is_active` 字段与 `UNIQUE(plan_id, is_active)`；
> - **保留** `UNIQUE(plan_id, baseline_no)`，另增 `UNIQUE(plan_id, plan_version_id)`、`content_hash NOT NULL`、`is_readonly=1 CHECK(is_readonly=1)`；
> - 当前生效状态外移到 `plan_active_baseline`（§2.4），切换全历史外移到 `baseline_switch_log`（§2.5）；
> - **无差别 BEFORE UPDATE/DELETE 冻结触发器**（不判断任何字段，杜绝"改某字段绕过"）：
>   ```sql
>   CREATE TRIGGER trg_bl_freeze_u BEFORE UPDATE ON baseline_version
>   WHEN OLD.is_readonly = 1
>   BEGIN SELECT RAISE(ABORT,'baseline frozen: content immutable'); END;
>   CREATE TRIGGER trg_bl_freeze_d BEFORE DELETE ON baseline_version
>   WHEN OLD.is_readonly = 1
>   BEGIN SELECT RAISE(ABORT,'baseline frozen: physical delete disabled'); END;
>   ```
> - 切换流程（应用层单事务）：写 `baseline_switch_log` + `audit_log` + UPSERT `plan_active_baseline`，**全程不触碰 `baseline_version` 任何行**；要求 `authorization_ref` 非空。
> `info_nature` 默认 **`DECISION`**；基线 A；FTS：不建；专用冻结触发器 2 个（不再计入 §8 的 20 张禁物理删除表）。

### 2.4 `plan_active_baseline` 当前生效基线指针 ［基线B］（R1-1 新增，原稿缺失补齐）
| 项 | 内容 |
|---|---|
| 用途 | 状态分离：把"当前生效基线"从 `baseline_version` 剥离出来，一个计划最多一行 |
| 主键 | `plan_id TEXT PRIMARY KEY REFERENCES plan(id)`（PK 天然保证唯一） |
| 外键 | `baseline_version_id TEXT NOT NULL REFERENCES baseline_version(id)` |
| 关键字段 | `is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active=1)`、`switched_at TEXT NOT NULL`、`switched_by`、`authorization_ref TEXT NOT NULL`（切换授权）、`reason` |
| 唯一约束/索引 | `plan_id` PK；另 `CREATE UNIQUE INDEX uq_pab_active ON plan_active_baseline(plan_id) WHERE is_active=1`（评审要求的部分唯一索引） |
| info_nature 默认 | 无该列（基线 B 不含 info_nature） |
| 公共字段基线 | **基线 B**（id 由 `plan_id` 充当 / created_at / is_deleted） |
| FTS | 不建（状态 / 授权元数据，精确查询） |
| 禁物理删除 | 否（状态表可 UPSERT 切换） |

> 实测：同一计划插第二条生效基线被 `UNIQUE constraint failed: plan_active_baseline.plan_id` 拦截（§2.4 案例 5）。

### 2.5 `baseline_switch_log` 基线切换授权审计 ［基线B］（R1-1 新增，原稿缺失补齐）
| 项 | 内容 |
|---|---|
| 用途 | 记录每一次基线切换的**全历史**（来源、目标、授权人、时间、理由、审计挂接） |
| 主键 | `id`（TEXT UUID，CHECK 32 位小写 hex） |
| 外键 | `plan_id TEXT NOT NULL REFERENCES plan(id)`、`to_baseline_id TEXT NOT NULL REFERENCES baseline_version(id)`；`from_baseline_id` 可空（首次切换）；`audit_log_id` 无硬 FK（回指 `audit_log`） |
| 关键字段 | `switched_at TEXT NOT NULL`、`switched_by TEXT NOT NULL`、`authorization_ref TEXT NOT NULL`、`reason` |
| 唯一约束/索引 | `idx_bsl_plan(plan_id, switched_at)`（普通索引，按时间线回放） |
| info_nature 默认 | 无该列（基线 B） |
| 公共字段基线 | **基线 B** |
| FTS | 不建（审计字段按 `plan_id + switched_at` 精确查询） |
| 禁物理删除 | 否 |

### 2.6 `plan_activity` 计划活动 / 里程碑（**稳定主实体**） ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| plan_id | char(32) | Y | — | FK→plan |
| code | text | Y | — | 活动编码（如 WBS） |
| first_version_id | char(32) | N | — | FK→plan_version（首次出现的版本） |
| **约束** | | | | `UNIQUE(plan_id, code)`；`idx_activity_plan(plan_id)` |

> **R1-2 整改（原结论作废）**：原稿把 `name` / `is_milestone` / `discipline_id` / `planned_start` / `planned_end` / `status` 等**版本可变属性**直接放在 `plan_activity` 上，会被后续版本覆盖，无法回放历史 —— 该设计**作废**。`plan_activity` 降为**稳定主实体**（仅 id / plan_id / code / first_version_id / 公共字段），跨版本身份不变；所有版本可变属性迁入 `plan_activity_version`（§2.7）。
> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建；禁物理删除触发器：否。

### 2.7 `plan_activity_version` 每版本活动属性快照 ［基线A］（R1-2 新增，原稿缺失补齐）
| 项 | 内容 |
|---|---|
| 用途 | 存每个计划版本下活动的**完整属性快照**，支撑 V1/V2 差异对比、历史批准计划回放、活动增删改历史 |
| 主键 | `id`（TEXT UUID，CHECK 32 位小写 hex） |
| 外键 | `activity_id TEXT NOT NULL REFERENCES plan_activity(id)`、`plan_version_id TEXT NOT NULL REFERENCES plan_version(id)`；`owner_org_id→organization`、`owner_person_id→person`、`discipline_id→discipline`、`area_id→area`、`system_id→system` |
| 关键字段 | `name TEXT NOT NULL`、`code`、责任组织/人、`planned_start` / `planned_end`、`dependency_json`（版本内前置关系快照）、`workload_qty` / `workload_unit` / `progress_measure`、`is_milestone`、`content_hash`、`snapshot_json` |
| change_type | `TEXT NOT NULL CHECK(change_type IN ('ADDED','MODIFIED','UNCHANGED','REMOVED'))` —— 四值活动增删改历史 |
| 唯一约束/索引 | `UNIQUE(activity_id, plan_version_id)`；`idx_pav_ver(plan_version_id)`；`idx_pav_change(plan_version_id, change_type)` |
| info_nature 默认 | `CONFIRMED_FACT` |
| 公共字段基线 | **基线 A** |
| FTS | **建** `plan_activity_version_fts`（§7.2 #22，索引 `name, code`，**全部历史版本**，`owner_biz_id` = `activity_id`） |
| 禁物理删除 | 否 |

> 回放路径：`baseline_version → plan_version → plan_activity_version`（`WHERE change_type <> 'REMOVED'`），见《表结构设计》§2.5。

### 2.8 `activity_dependency` 活动依赖（版本化） ［基线B］
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| plan_id | char(32) | Y | FK→plan（作用域） |
| plan_version_id | char(32) | Y | **R1-2 新增** FK→plan_version（依赖按版本生效） |
| predecessor_id | char(32) | Y | FK→plan_activity（前置） |
| successor_id | char(32) | Y | FK→plan_activity（后置） |
| relation_type | text | Y | `CHECK(relation_type IN ('FS','SS','FF','SF'))` |
| lag_days | integer | N | 滞后天数 |
| **约束** | | | | `CHECK(predecessor_id <> successor_id)`；`UNIQUE(plan_version_id, predecessor_id, successor_id, relation_type)` |

> **R1-2 整改**：原稿 `UNIQUE(plan_id, predecessor_id, successor_id, relation_type)` **作废**，唯一范围改为按 `plan_version_id`（版本内前后置）；新增 `plan_version_id` 硬 FK。
> 基线 B；`info_nature`：无该列；FTS：不建；禁物理删除触发器：否。

### 2.9 `progress_record` 进度记录 ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| plan_activity_id | char(32) | Y | — | FK→plan_activity |
| plan_version_id | char(32) | N | — | **R1-2 新增** FK→plan_version（进度所对照的版本口径） |
| record_at | text | Y | — | 时点 |
| progress_pct | real | Y | 0 | 完成百分比 0~100 |
| actual_start / actual_end | text | N | — | 实际时间 |
| note | text | N | — | 备注 |
| **约束** | | | | `CHECK(progress_pct BETWEEN 0 AND 100)`；`UNIQUE(plan_activity_id, record_at)` |

> `info_nature` 默认 `CONFIRMED_FACT`；基线 A（本表属清单 B 分类但 DDL 用基线 A 字段集，见 §0.2 说明）；FTS：不建；禁物理删除触发器：否。

---

## 3. 域3 —— 信息与文件（来源域）

### 3.1 `email` 邮件 ［基线A］
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| message_id_text | text | N | 外部 message-id（UNIQUE 去重） |
| from_addr / to_addrs / cc_addrs | text | N | 地址（to/cc 存 JSON 文本） |
| subject | text | Y | 主题 |
| body_markdown | text | N | 正文（**按隔离边界授权处理**，见 D.2-1） |
| source_time / event_time | text | Y / N | 来源时间 / 事件时间 |
| **索引/约束** | | | `UNIQUE(message_id_text)`；FTS `email_fts`（§7.2 #1） |

> `info_nature` 默认 **`SOURCE_FACT`**；基线 A；FTS：`email_fts`（subject, body_markdown / 当前）；禁物理删除触发器：是。

### 3.2 `email_attachment` 邮件附件 ［基线B］
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| email_id | char(32) | Y | FK→email |
| filename | text | Y | 文件名 |
| file_kind | text | N | 类型（可升级为 Document） |
| sha256 | text | N | 内容指纹（去重/版本） |

> 基线 B（本表属清单 A 分类但 DDL 用基线 B 字段集，见 §0.2）；`info_nature`：无该列；FTS：`email_attachment_fts`（§7.2 #2，filename / 当前）；禁物理删除触发器：否。

### 3.3 `document` / `document_version` 文档及其版本
- `document` ［基线A］：id, project_id, name, doc_code, doc_type, `is_readonly=1`, sha256, `info_nature='SOURCE_FACT'`；`idx_doc_sha = CREATE UNIQUE INDEX ... ON document(sha256) WHERE sha256 IS NOT NULL`（部分唯一索引）；FTS `document_fts`（§7.2 #3，name / doc_code，主表元数据）；禁物理删除触发器：是。
- `document_version` ［基线A］：id, `document_id FK`, version_no, file_path, sha256, `extracted_text`, `notes`, `snapshot_json`, `info_nature='SOURCE_FACT'`；`UNIQUE(document_id, version_no)`；FTS `document_version_fts`（§7.2 #4，extracted_text / notes / snapshot_json，**全部历史版本**，`owner_biz_id = document_id`）。
- **R1-3 更正**：旧稿 `document_fts(name, snapshot_json)` 把属于 `document_version` 的 `snapshot_json` 错配到主表，外部内容表要求列名与被索引表严格对应 —— 该写法**作废**（见 §7.2）。

### 3.4 `drawing` / `drawing_version` / `drawing_object` 图纸及其版本
- `drawing` ［基线A］：id, project_id, drawing_no(图号), name, `doc_type='DRAWING'`, `is_readonly=1`, `info_nature='SOURCE_FACT'`；FTS `drawing_fts`（§7.2 #5，name / drawing_no，主表元数据）；禁物理删除触发器：是。
  - **R1-6 整改（原结论作废）**：`drawing_no` 由**全局唯一**改为**按项目唯一**，原稿「全局 UNIQUE(drawing_no)」**作废**：
    ```sql
    CREATE UNIQUE INDEX IF NOT EXISTS uq_dr ON drawing(COALESCE(project_id,''), drawing_no);
    ```
    `COALESCE(project_id,'')` 处理 `project_id` 可空情形，保证不同项目可同图号、同项目图号不重复。
- `drawing_version` ［基线A］：id, `drawing_id FK`, revision, file_path, sha256, `extracted_text`, `notes`, `info_nature='SOURCE_FACT'`；`UNIQUE(drawing_id, revision)`；FTS `drawing_version_fts`（§7.2 #6，revision / extracted_text / notes，**全部历史版本**，`owner_biz_id = drawing_id`）。
- `drawing_object` ［基线B］（**DWG 对象预留，不装 SDK/不解析**，ADR-10）：id, `drawing_id FK`, `drawing_version_id FK`, obj_type, `ref_entity_id FK→entity`, `ref_area_id` / `ref_system_id`, `geometry_json` / `reserved_data` 占位；FTS：不建（占位不解析）；`info_nature`：无该列。

### 3.5 `meeting` / `meeting_minutes` 会议及其纪要
- `meeting` ［基线A］：id, project_id, title, held_at, `organizer_person_id FK`, `participant_ids`(JSON), `transcript_ptr`, `transcript_text`, `source_time`, `info_nature='SOURCE_FACT'`；FTS `meeting_fts`（§7.2 #7，title / transcript_text / 当前）；禁物理删除触发器：是。
- `meeting_minutes` ［基线A，可多版］：id, `meeting_id FK`, version_no, `content_md`, `is_final`, `source_time`, `info_nature='SOURCE_FACT'`；`UNIQUE(meeting_id, version_no)`；FTS `meeting_minutes_fts`（§7.2 #8，version_no / content_md，**全部历史版本**，`owner_biz_id = meeting_id`）。
- **R1-3 更正**：旧稿 `meeting_fts(title, content_md)` 把属于 `meeting_minutes` 的 `content_md` 错配到主表，写法**作废**（见 §7.2）。

### 3.6 `message` 消息（微信 / 即时消息） ［基线A］
- id, project_id, `sender_person_id FK`, `content_md`, `sent_at`, `channel`, `source_time`, `info_nature='SOURCE_FACT'`；FTS `message_fts`（§7.2 #9，content_md / 当前）；禁物理删除触发器：是。

### 3.7 `source_reference` 来源引用（统一来源桥 —— 泛化来源载体→任意实体） ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| traced_entity_type | text | Y | — | 被溯源对象类型（issue / entity / knowledge_item / …） |
| traced_entity_id | char(32) | Y | — | 被溯源对象 id（**多态，无硬 FK**） |
| source_type | text | Y | — | 来源载体类型（email / email_attachment / document / drawing / meeting_minutes / message / evidence） |
| source_id | char(32) | Y | — | 来源载体 id（**多态，无硬 FK**） |
| context_excerpt | text | N | — | 上下文摘录（引了哪段） |
| locator | text | N | — | 定位（图号/段落/pin） |
| info_nature | text | Y | 'SOURCE_FACT' | 溯源关系本身的事实级别 |
| confidence | real | N | — | 置信度 |
| source_time | text | N | — | 来源时间 |
| **索引** | | | | `idx_sr_entity(traced_entity_type, traced_entity_id)`；`idx_sr_source(source_type, source_id)` |

> 基线 A；FTS：`source_reference_fts`（§7.2 #11，context_excerpt / locator / 当前）；禁物理删除触发器：否。
> **已知取舍**：`type + id` 多态无硬 FK，完整性由 `sp_check_polymorphic_refs` 自检 + 应用层 + 审计三层补偿（《表结构设计》§7.6），不伪装成数据库硬约束。

### 3.8 `evidence` / `evidence_link` 证据
- `evidence` ［基线A］：id, project_id, title, `body`, `evidence_kind`(片段/附件/截图), sha256, `info_nature='SOURCE_FACT'`；FTS `evidence_fts`（§7.2 #10，title / body / 当前）；禁物理删除触发器：是。
- `evidence_link` ［基线B］：id, `evidence_id FK`, `ref_type` / `ref_id`（多态，无硬 FK）, `link_role`(佐证/反证/依据), `context_excerpt`；`idx_el_ref(ref_type, ref_id)`；FTS：不建；纳入 `sp_check_polymorphic_refs` 自检。

---

## 4. 域4 —— 问题 / 风险 / 任务闭环（R1-4 business_subject 分层）

> **R1-4 分层定案**：业务实体（名词：设备/船舶/区域/厂商/专业）与业务事项（事件：Issue/Risk/Task/Decision/KnowledgeItem）严格分层。`issue` / `risk` / `task` / `decision` / `knowledge_item` 各增 `subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id)`（1:1）挂到统一事项主档；事项的别名、可逆合并、来源证据全部由 §4.1 四表承载。
> **明确写入**：`entity_relationship` **仅表达业务实体间的语义关系（同义 / 整机-部件），不得承载 Issue/Risk/Task 等业务事项的合并；事项合并只由 `business_subject_merge` 表达**（见 §5.4）。

### 4.1 统一事项主档四表（R1-4 新增，原稿缺失补齐）

#### 4.1.1 `business_subject` 业务事项主档 ［基线A］
| 项 | 内容 |
|---|---|
| 用途 | 统一承载所有业务事项的**身份、类型、归一目标与状态**，是事项合并 / 别名 / 来源的锚点 |
| 主键 | `id`（TEXT UUID，CHECK 32 位小写 hex） |
| 外键 | `project_id TEXT NOT NULL REFERENCES project(id)`；`canonical_subject_id TEXT REFERENCES business_subject(id)`（自关联，指向合并后的规范事项） |
| 关键字段 | `subject_kind TEXT NOT NULL CHECK(subject_kind IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM'))`、`status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','MERGED','SUPERSEDED'))` |
| 唯一约束/索引 | `idx_bs_canonical(canonical_subject_id)`（普通索引）；`subject_id` 在具体事项表侧为 `UNIQUE`，保证 1:1 |
| info_nature 默认 | `CONFIRMED_FACT` |
| 公共字段基线 | **基线 A** |
| FTS | 不建（无自由文本；别名由 `business_subject_alias_fts` 覆盖） |
| 禁物理删除 | **是**（§8 20 张之一） |

#### 4.1.2 `business_subject_alias` 事项别名 ［基线A］
| 项 | 内容 |
|---|---|
| 用途 | **一个事项多个别名**；短词 / 译名 / 近义召回，供审核候选检索 |
| 主键 | `id`（TEXT UUID） |
| 外键 | `subject_id TEXT NOT NULL REFERENCES business_subject(id)`；`source_reference_id TEXT REFERENCES source_reference(id)` |
| 关键字段 | `alias TEXT NOT NULL`、`alias_type`、`confirm_status TEXT NOT NULL DEFAULT 'PENDING'` |
| 唯一约束/索引 | `UNIQUE(subject_id, alias)` |
| info_nature 默认 | `CONFIRMED_FACT` |
| 公共字段基线 | **基线 A** |
| FTS | **建** `business_subject_alias_fts`（§7.2 #19，alias / 当前）；与 `entity_alias_fts` 一起作为 trigram 短词 LIKE 回退的别名召回源 |
| 禁物理删除 | 否；纳入 `sp_check_polymorphic_refs` 自检 |

#### 4.1.3 `business_subject_merge` 可逆事项合并链 ［基线A］
| 项 | 内容 |
|---|---|
| 用途 | **业务事项合并的唯一表达**（Issue→Issue 等）；支持撤销错误合并，不物理删除任何记录 |
| 主键 | `id`（TEXT UUID） |
| 外键 | `from_subject_id TEXT NOT NULL REFERENCES business_subject(id)`、`to_subject_id TEXT NOT NULL REFERENCES business_subject(id)`；`source_reference_id TEXT REFERENCES source_reference(id)` |
| 关键字段 | `merged_at TEXT NOT NULL`、`merged_by TEXT NOT NULL`、`reason`；**撤销四字段** `undone_at` / `undone_by` / `undo_reason` / `is_active INTEGER NOT NULL DEFAULT 1` |
| 唯一约束/索引 | `CHECK(from_subject_id <> to_subject_id)` |
| info_nature 默认 | `CONFIRMED_FACT` |
| 公共字段基线 | **基线 A** |
| FTS | 不建 |
| 禁物理删除 | 否 |

> **合并 / 撤销语义**：合并时 `from_subject` 及其 `issue` 行**不删除、不覆盖**，仅标 `status='MERGED'` 并保留 `canonical_subject_id` 指向 `to_subject`；撤销时置 `undone_at` / `undone_by` / `undo_reason`、`is_active=0`，`from_subject.status` 由 MERGED 回 ACTIVE、`canonical_subject_id` 清空。历史引用全部可回放。

#### 4.1.4 `business_subject_source` 事项↔来源证据 M:N ［基线B］
| 项 | 内容 |
|---|---|
| 用途 | 保留同一事项**每一次出现位置**（跨邮件 / 会议 / 文件）的来源证据链 |
| 主键 | `id`（TEXT UUID） |
| 外键 | `subject_id TEXT NOT NULL REFERENCES business_subject(id)`；`source_reference_id TEXT NOT NULL REFERENCES source_reference(id)` |
| 关键字段 | 纯关联（无额外业务列） |
| 唯一约束/索引 | `UNIQUE(subject_id, source_reference_id)` |
| info_nature 默认 | 无该列（基线 B 不含 info_nature） |
| 公共字段基线 | **基线 B** |
| FTS | 不建 |
| 禁物理删除 | 否 |

### 4.2 `issue` 问题 / `issue_status_history` 状态历史
- `issue` ［基线A］：id, `project_id FK`, **`subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id)`（R1-4 新增）**, `ref_no UNIQUE`, title, description_md, status('NEW'), severity, priority, `info_nature='CONFIRMED_FACT'`；`idx_issue_proj(project_id)`、`idx_issue_status(status)`；FTS `issue_fts`（§7.2 #12，ref_no / title / description_md / 当前）；禁物理删除触发器：是。
- `issue_status_history` ［基线B］：id, `issue_id FK`, old_status / new_status / transition, changed_by, changed_at, reason, reopen_count, info_nature, `source_reference_id FK`；FTS：不建；`info_nature` 本列为可空文本（R1 DDL 未设默认值，由应用层填写）。
- 合法状态转移由应用层校验；状态机值见 B.6。

### 4.3 `risk` / `risk_status_history`
- `risk` ［基线A］：id, `project_id FK`, **`subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id)`**, `ref_no UNIQUE`, title, description_md, probability / impact / exposure, status('NEW'), strategy(规避/转移/缓解/接受), `info_nature='CONFIRMED_FACT'`；`idx_risk_proj(project_id)`；FTS `risk_fts`（§7.2 #13）；禁物理删除触发器：是。
- `risk_status_history` ［基线B］：同 issue 历史结构，绑定 `risk_id FK`；FTS：不建。

### 4.4 `task` / `task_status_history`
- `task` ［基线A］：id, `project_id FK`, **`subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id)`**, `ref_no UNIQUE`, title, description_md, `assignee_person_id FK`, due_at, completed_at, priority, status('NEW'), `info_nature='CONFIRMED_FACT'`；`idx_task_proj(project_id)`；FTS `task_fts`（§7.2 #14）；禁物理删除触发器：是。
- `task_status_history` ［基线B］：同结构，绑定 `task_id FK`；FTS：不建。

### 4.5 `action_measure` 行动措施（风险应对 & 问题整改 共用） ［基线A］
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| project_id | char(32) | Y | FK→project |
| ref_no | text | Y | 编号（UNIQUE） |
| name | text | Y | 措施名 |
| measure_type | text | Y | `CHECK(measure_type IN ('RISK_RESPONSE','ISSUE_REMEDY'))` |
| risk_id | char(32) | N | **R1-6 新增可空硬 FK** `REFERENCES risk(id)` |
| issue_id | char(32) | N | **R1-6 新增可空硬 FK** `REFERENCES issue(id)` |
| due_at / status / info_nature | — | — | 状态默认 'OPEN'；info_nature 默认 `CONFIRMED_FACT` |

> **R1-6 整改（原结论作废）**：原稿 `source_owner_type / source_owner_id` 多态无完整性、`measure_type` 无 CHECK 的说法**作废**。改为两个可空硬 FK + 属主完整性 CHECK：
> ```sql
> risk_id  TEXT REFERENCES risk(id),
> issue_id TEXT REFERENCES issue(id),
> CHECK((risk_id IS NOT NULL AND issue_id IS NULL) OR (issue_id IS NOT NULL AND risk_id IS NULL))
> ```
> 该 CHECK 落实评审「`CHECK((risk_id IS NOT NULL)+(issue_id IS NOT NULL)>=1)` 至少一个属主」的要求，并额外**禁止同时挂两个硬 FK**（多属主走 `action_measure_link` M:N）；索引 `idx_am_risk(risk_id)` / `idx_am_issue(issue_id)`。
> 基线 A；FTS：`action_measure_fts`（§7.2 #16，ref_no / name / description / 当前）；禁物理删除触发器：是。
- `action_measure_link` ［基线B］：id, `action_measure_id FK`, `ref_type` / `ref_id`（多态）, `link_role`；支持**一个措施挂多个属主（M:N）**；FTS：不建；纳入 `sp_check_polymorphic_refs` 自检。

### 4.6 `decision` 决策 / `decision_link` / `object_link`
- `decision` ［基线A］：id, `project_id FK`, **`subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id)`**, `ref_no UNIQUE`, title, `conclusion_md`, `decided_by_person_id FK`, decided_at, status('OPEN'), **`info_nature='DECISION'`**；FTS `decision_fts`（§7.2 #15，ref_no / title / conclusion_md / 当前）；禁物理删除触发器：是。
- `decision_link` ［基线B］：id, `decision_id FK`, `ref_type` / `ref_id`（多态）, `link_role`(依据/被决策对象), `context_excerpt`；`idx_dl_ref(ref_type, ref_id)`；FTS：不建；纳入多态自检。
- `object_link` 通用对象桥（M:N 全链路引用 —— issue↔activity/email/document/drawing/meeting/task/risk/knowledge…） ［基线A］：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| link_role | text | Y | 角色（issue_activity / issue_document / issue_email / decision_basis / evidence_support / …，dimension 归口） |
| left_type / left_id | text / char | Y | 左侧对象（多态，无硬 FK） |
| right_type / right_id | text / char | Y | 右侧对象（多态，无硬 FK） |
| context_excerpt | text | N | 上下文摘录 |

> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建；`idx_ol_left(left_type, left_id)`、`idx_ol_right(right_type, right_id)`；纳入 `sp_check_polymorphic_refs` 自检。
> 设计说明：`object_link` 承载 B.3/B.4 与 A.4 的一切业务对象间多对多，避免为每对关系建独立表（ADR-4/ADR-5）。

---

## 5. 域5 —— 实体关系与知识（`entity` 见《表结构设计》§1 前置定义）

### 5.1 `entity` 实体（归一化业务实体，含全局唯一标识） ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID（**全局实体标识**，B.5 核心） |
| name | text | Y | — | 规范名 |
| entity_kind | text | Y | — | 船/设备/部位/厂商/专业…（dimension 归口） |
| canonical_source_id | char(32) | N | — | 自关联：本规范名对应的规范实体（**仅限业务实体**的合并/主实体，见 §5.4） |
| status | text | Y | 'ACTIVE' | `CHECK(status IN ('ACTIVE','MERGED','SUPERSEDED'))` |
| info_nature | text | Y | 'CONFIRMED_FACT' | 实体事实级别 |

> 基线 A；FTS：`entity_fts`（§7.2 #17，name / 当前）；禁物理删除触发器：是。
> **范围限定**：`entity` + `canonical_source_id` 的归一**仅用于业务实体**；业务事项的归一走 `business_subject`（§4.1）。

### 5.2 `entity_alias` 实体别名 ［基线A］
- id, `entity_id FK`, alias, alias_type(简称/大小写/译名/近义), `source_reference_id FK`, `confirm_status DEFAULT 'PENDING'`, `info_nature='CONFIRMED_FACT'`；`UNIQUE(entity_id, alias)`。
- 检索用到：trigram 命中→别名映射→规范实体；FTS `entity_alias_fts`（§7.2 #18，alias / 当前）；基线 A；FTS：建。

### 5.3 `entity_identifier` 外部编号 ［基线A］
- id, `entity_id FK`, id_type(设备号/船号/图号), `source_from`, identifier, `source_reference_id FK`, effective_from, `info_nature='CONFIRMED_FACT'`。
> **R1-6 整改（原结论作废）**：唯一范围由全局 `UNIQUE(id_type, identifier)`（不同来源系统同号即冲突）**作废**，改为按 `(entity_id, id_type, source_from, identifier)` 收敛，并另建非唯一检索索引：
> ```sql
> CREATE UNIQUE INDEX IF NOT EXISTS uq_ei
>     ON entity_identifier(entity_id, id_type, COALESCE(source_from,''), identifier);
> CREATE INDEX IF NOT EXISTS idx_ei_lookup ON entity_identifier(id_type, identifier);
> ```
> 跨实体同号由业务校验处理。基线 A；FTS：不建。

### 5.4 `entity_relationship` 实体间语义关系（M:N） ［基线A］
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| left_entity_id | char(32) | Y | FK→entity |
| right_entity_id | char(32) | Y | FK→entity |
| relation_type | text | Y | synonym / holonym(整机-部件) / superclass / …（**业务实体语义关系**） |
| confirm_status | text | Y | 默认 'PENDING' |
| source_reference_id | char(32) | N | 来源证据 |
| **约束** | | | | `CHECK(left_entity_id <> right_entity_id)`；`UNIQUE(left_entity_id, right_entity_id, relation_type)` |

> **R1-4 整改（原结论作废）**：原稿标题「含合并链」、`relation_type` 含 `merge`、以及「Issue→Issue 合并落到 `entity_relationship(synonym/merge)`」的说法**全部作废**。
> **明确写入**：`entity_relationship` **仅表达业务实体间的语义关系（同义 / 整机-部件），不得承载 Issue/Risk/Task 等业务事项的合并；事项合并只由 `business_subject_merge`（§4.1.3）表达**。`entity` 自关联 `canonical_source_id` 与 `ENTITY ||--o{ ENTITY : "canonical merge N:1"` 亦**仅限业务实体**。
> 基线 A；`info_nature` 默认 `CONFIRMED_FACT`；FTS：不建。

### 5.5 `knowledge_item` / `knowledge_version` / `knowledge_entity_link`
- `knowledge_item` ［基线A］：id, project_id, **`subject_id TEXT UNIQUE REFERENCES business_subject(id)`（R1-4 新增；本表 DDL 为可空，非 NOT NULL）**, `ref_no UNIQUE`, title, summary, status('PUBLISHED'), `info_nature='CONFIRMED_FACT'`；FTS `knowledge_item_fts`（§7.2 #20，title / summary，主表元数据）；禁物理删除触发器：是。
- `knowledge_version` ［基线A］：id, `knowledge_item_id FK`, version_no, `content_md`, sha256, `snapshot_json`, `info_nature='CONFIRMED_FACT'`；`UNIQUE(knowledge_item_id, version_no)`；FTS `knowledge_version_fts`（§7.2 #21，version_no / content_md，**全部历史版本**，`owner_biz_id = knowledge_item_id`）。
- `knowledge_entity_link` ［基线B］：id, `knowledge_version_id FK`, `entity_id FK`（知识涉及的实体，M:N）；`UNIQUE(knowledge_version_id, entity_id)`；FTS：不建。
- **R1-3 更正**：旧稿 `knowledge_fts(title, content_md)` 把属于 `knowledge_version` 的 `content_md` 错配到主表，写法**作废**（见 §7.2）。

---

## 6. 域6 —— AI 处理与系统治理（R1-5 审核链）

### 6.1 `ingestion_job` 摄入作业 ［基线B］
- id, project_id, `source_type NOT NULL`, source_id, channel, `status DEFAULT 'INGESTING'`, started_at / finished_at, `run_meta`(JSON), `re_runnable DEFAULT 1`。
- 基线 B（本表属清单 A 分类但 DDL 用基线 B 字段集）；`info_nature`：无该列；FTS：不建（run_meta 为 JSON 元数据）；禁物理删除触发器：否。

### 6.2 `ai_analysis_run` AI 分析运行日志 ［基线B］
- id, project_id, `run_type NOT NULL`, model, input_ref, output_summary, `status DEFAULT 'RUNNING'`, started_at / finished_at。
- 基线 B；FTS：不建（日志型文本按状态精确查询）；禁物理删除触发器：否。

### 6.3 `extraction_result` 抽取结果（AI 候选，未审核） ［基线B］
- id, `ingestion_job_id FK`, `ai_analysis_run_id FK`, `candidate_type NOT NULL`, `candidate_json`, `raw_text`, **`info_nature='AI_INFERENCE' CHECK(info_nature IN ('AI_INFERENCE','PREDICTION','PROPOSAL'))`**, confidence, `status DEFAULT 'PENDING'`。
> **R1-5 整改（补充）**：由 `trg_extraction_immutable` 两个触发器保护 —— `trg_er_immutable_u`（BEFORE UPDATE，当 `candidate_json` / `raw_text` 变化时 `RAISE(ABORT,'extraction original content immutable')`）、`trg_er_immutable_d`（BEFORE DELETE，无条件 `RAISE(ABORT,'extraction records cannot be deleted')`）。**审核后不得删除或覆盖原始抽取记录**；审核结论只写 §6.4~§6.7 新表，不回写覆盖候选内容（实测 §8 E7/E8 PASS）。
> 基线 B；FTS：`extraction_result_fts`（§7.2 #23，candidate_json / raw_text / 当前）；专用不可变触发器 2 个（不计入 §8 的 20 张禁物理删除表）。

### 6.4 `review_queue` 人工审核队列（**审核任务**） ［基线A］（R1-5 重写，原稿扁平表作废）
| 项 | 内容 |
|---|---|
| 用途 | 审核**任务**本身（不再是"单抽取 + 单 decision + 单 target_entity_id"的扁平表） |
| 主键 | `id`（TEXT UUID，CHECK 32 位小写 hex） |
| 外键 | `suggested_subject_id TEXT REFERENCES business_subject(id)`（系统候选同名事项） |
| 关键字段 | `project_id`、`review_type TEXT NOT NULL`、`status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','IN_REVIEW','DONE'))`、`candidate_summary` |
| 唯一约束/索引 | 无额外唯一索引（多对多经 `review_extraction_link`） |
| info_nature 默认 | **`AI_INFERENCE`**（审核任务仍属 AI 推断阶段；人工确认后升级在 `review_decision`） |
| 公共字段基线 | **基线 A** |
| FTS | 不建（候选召回由 `business_subject_alias_fts` + `extraction_result_fts` 覆盖） |
| 禁物理删除 | 否 |

> **R1-5 整改（原结论作废）**：原稿 `review_queue(id, extraction_result_id, reviewer_person_id, decision, target_entity_id, reviewed_at)` 单抽取 / 单决策 / 单目标设计**作废** —— 无法支持"一条抽取拆成多个业务对象"、"多条抽取合一对象"、无审核人/理由/证据、且目标只能指 `entity`。改为 §6.4~§6.7 四表完整链。

### 6.5 `review_extraction_link` 审核任务↔抽取结果 M:N ［基线B］（R1-5 新增，原稿缺失补齐）
| 项 | 内容 |
|---|---|
| 用途 | 打通"**多条抽取结果 → 一个审核任务**"与"一条抽取结果可进多个任务"的 M:N |
| 主键 | `id`（TEXT UUID） |
| 外键 | `review_queue_id TEXT NOT NULL REFERENCES review_queue(id)`；`extraction_result_id TEXT NOT NULL REFERENCES extraction_result(id)` |
| 关键字段 | 纯关联（无额外业务列） |
| 唯一约束/索引 | `UNIQUE(review_queue_id, extraction_result_id)` |
| info_nature 默认 | 无该列（基线 B） |
| 公共字段基线 | **基线 B** |
| FTS | 不建 |
| 禁物理删除 | 否 |

### 6.6 `review_decision` 审核结果明细 ［基线A］（R1-5 新增，原稿缺失补齐）
| 项 | 内容 |
|---|---|
| 用途 | 一个审核任务可产出**多条结果明细**，含审核人 / 时间 / 理由 / 证据 |
| 主键 | `id`（TEXT UUID） |
| 外键 | `review_queue_id TEXT NOT NULL REFERENCES review_queue(id)`；`reviewer_person_id TEXT NOT NULL REFERENCES person(id)`；`evidence_source_reference_id TEXT REFERENCES source_reference(id)` |
| 关键字段 | `decision TEXT NOT NULL CHECK(decision IN ('ACCEPT_AS_NEW','MERGE_TO','REJECT'))`、`reviewed_at TEXT NOT NULL`、`reason TEXT NOT NULL`（REJECT 亦需理由） |
| 唯一约束/索引 | `idx_rd_queue(review_queue_id)`（普通索引） |
| info_nature 默认 | **`CONFIRMED_FACT`**（人工确认结果，G5 升级落点） |
| 公共字段基线 | **基线 A** |
| FTS | **建** `review_decision_fts`（§7.2 #24，reason / 当前） |
| 禁物理删除 | 否 |

### 6.7 `review_result_object` 结果→正式对象稳定映射 ［基线A］（R1-5 新增，原稿缺失补齐）
| 项 | 内容 |
|---|---|
| 用途 | 审核结果 → **正式对象稳定映射**；支持一条结果拆多个对象、多条结果指向同一对象 |
| 主键 | `id`（TEXT UUID） |
| 外键 | `review_decision_id TEXT NOT NULL REFERENCES review_decision(id)`；`object_id TEXT NOT NULL`（**多态，无硬 FK**） |
| 关键字段 | `object_type TEXT NOT NULL CHECK(object_type IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ENTITY','BUSINESS_SUBJECT'))`、`relation TEXT NOT NULL CHECK(relation IN ('CREATED','MERGED_INTO','REJECTED'))` |
| 唯一约束/索引 | `idx_rro_obj(object_type, object_id)`（普通索引） |
| info_nature 默认 | `CONFIRMED_FACT` |
| 公共字段基线 | **基线 A** |
| FTS | 不建（按 `object_type + object_id` 精确映射） |
| 禁物理删除 | 否；纳入 `sp_check_polymorphic_refs` 自检 |

> 约束补充：「REJECT 却生成 CREATED 对象」由应用层校验；G5 链路 `AI_INFERENCE → review_queue → review_decision(CONFIRMED_FACT) → 正式对象(CONFIRMED_FACT)`，**不得自动升级**。

### 6.8 `audit_log` 审计日志 ［基线B］
- id, project_id, `actor_type NOT NULL CHECK(actor_type IN ('USER','AI','SYSTEM'))`, actor_id, `action_code NOT NULL`, target_type / target_id, before_json / after_json, `authorization_ref`；`idx_audit_target(target_type, target_id)`；**只增不改**。
- **一切对基线 / 正式记录的写操作必须记录至此**（OQ-3 四层防御之一）。基线 B；FTS：不建（JSON 审计字段按 target 精确查询）。

### 6.9 `system_config` 系统配置（非硬编码枚举归口） ［基线B］
- id, `config_key UNIQUE`, config_value, description, config_group, `is_active DEFAULT 1`；基线 B；FTS：不建（配置项按 key 精确查询）。

### 6.10 `user` / `role` / `permission` / `user_role` / `role_permission`（Phase 后期启用，骨架 D.2-2） ［基线B 精简，DDL 未显式标注］
- `user`：id, `person_id FK`, `username UNIQUE`, password_hash, status；`role`：id, `role_code UNIQUE`, name；`permission`：id, `permission_code UNIQUE`, name。
- `user_role`（M:N）：`UNIQUE(user_id, role_id)`；`role_permission`（M:N）：`UNIQUE(role_id, permission_id)`。
- 本阶段仅表结构预留骨架，角色清单见 D.2-2 未定；基线 B 精简字段集；FTS：均不建。

### 6.11 `schema_version` 结构版本元信息（R1 补齐，原稿缺失） ［独立元信息表，不套用 A/B 基线］
| 项 | 内容 |
|---|---|
| 用途 | 登记迁移版本号与 DDL 指纹，供幂等迁移的**结构一致性校验**（《表结构设计》§10.1） |
| 主键 | `version INTEGER PRIMARY KEY`（非 TEXT UUID，是本表唯一例外） |
| 外键 | 无（独立元信息表，不参与任何业务关系） |
| 关键字段 | `applied_at TEXT NOT NULL`、`description`、`ddl_fingerprint TEXT` —— `CHECK(length(ddl_fingerprint)=64 OR ddl_fingerprint IS NULL)`（对 `sqlite_master.sql` 排序拼接后 sha256） |
| 唯一约束/索引 | `version` PK |
| info_nature 默认 | 无该列 |
| 公共字段基线 | **不适用**（独立元信息表：无 `id` / `is_deleted` / 审计字段；见 §0.2） |
| FTS | 不建（纯指纹 / 版本元数据） |
| 禁物理删除 | 否 |

---

## 7. 共享桥表、FTS5 trigram 统一设计（R1-3）

### 7.1 `object_dimension_tag` 对象×维度 多值标签 ［基线A］
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| tagged_object_type | text | Y | — | 被打标签对象类型（issue/document/activity/…）（多态，无硬 FK） |
| tagged_object_id | char(32) | Y | — | 对象 id（多态，无硬 FK） |
| dimension | text | Y | — | `CHECK(dimension IN ('EPCS_PHASE','DISCIPLINE','AREA','SYSTEM'))` |
| value_type | text | Y | — | `CHECK(value_type IN ('REF','FREE_TEXT'))` —— **R1-6 新增约束** |
| value_id | char(32) | N | — | REF 时指向 discipline/area/system/… 的 id |
| value_text | text | N | — | FREE_TEXT 时自由值（如"阶段不确定/跨阶段"，B.2） |
| **索引** | | | | `idx_odt_obj(tagged_object_type, tagged_object_id)`；`idx_odt_dim(dimension, value_id)` |

> **R1-6 整改（原结论作废）**：原稿 `value_type` 无 CHECK、`value_id` / `value_text` 可乱填的说法**作废**。新增 `value_type` 枚举约束与 **REF / FREE_TEXT 互斥约束**（实测拦截非法行 §8 G4）：
> ```sql
> CHECK((value_type='REF'       AND value_id IS NOT NULL   AND value_text IS NULL)
>    OR (value_type='FREE_TEXT' AND value_text IS NOT NULL AND value_id IS NULL))
> ```
> 即 **REF 用 `value_id`、FREE_TEXT 用 `value_text`，二者互斥且不得为空**。
> `info_nature` 默认 `CONFIRMED_FACT`；基线 A；FTS：不建（维度枚举精确查询）；纳入 `sp_check_polymorphic_refs` 自检。
> 该表承载 B.2"阶段+专业/区域/系统可同时多打、可并列/跨阶段"，并兼容"阶段不确定/自由文本"。

### 7.2 FTS5 统一范式与一一对应清单（24 张）—— **原结论作废，本节整体改写**

> **【原结论作废声明】** 原稿 §7.2 写：
> ```sql
> CREATE VIRTUAL TABLE issue_fts USING fts5(title, description_md, content='issue', content_rowid='id', tokenize='trigram');
> ```
> 即「外部内容表（external content）+ `content_rowid='id'`」范式，**整段作废**。原因：`id` 是 **TEXT UUID**，而 SQLite FTS5 外部内容表的 `content_rowid` **必须是整数 rowid**；用 TEXT UUID 作 `content_rowid` 会导致无法映射（实测所有行被压成 rowid 0），建表 / 查询均不可靠。此外旧稿 `document_fts(name, snapshot_json)` / `meeting_fts(title, content_md)` / `knowledge_fts(title, content_md)` 索引了**被索引表中根本不存在的列**，外部内容表要求列名与主表严格对应，原草案根本无法建。

**R1 统一范式（普通内容表 contentful + `biz_id UNINDEXED` 显式映射）**：

```sql
-- 统一模板（每张 FTS 表结构相同，文本列按内容表调整；全库不再使用外部内容表）
CREATE VIRTUAL TABLE IF NOT EXISTS x_fts USING fts5(
    biz_id UNINDEXED,          -- TEXT UUID：稳定业务对象 ID，显式携带
    owner_biz_id UNINDEXED,    -- 版本类 FTS：主表 UUID（非版本表填空）
    is_deleted UNINDEXED,      -- 软删镜像，查询过滤
    <文本列...>,              -- 如 ref_no, title, description_md
    tokenize = 'trigram');

-- 示例（issue）
CREATE VIRTUAL TABLE IF NOT EXISTS issue_fts USING fts5(
    biz_id UNINDEXED, owner_biz_id UNINDEXED, is_deleted UNINDEXED,
    ref_no, title, description_md, tokenize='trigram');
```

- **业务 UUID 映射**：不再依赖整数 `content_rowid`；FTS 表自身 rowid 为整数自增，业务 UUID 由 `biz_id UNINDEXED` **显式携带**；版本表另用 `owner_biz_id` 指向主对象。同步触发器用 `WHERE biz_id = old.id` 定位。**禁止把 TEXT UUID 用作 `content_rowid`**。
- **查询**：`SELECT biz_id, owner_biz_id, snippet(...) FROM x_fts WHERE x_fts MATCH ? AND is_deleted=0`，再按 `biz_id` 回业务表；版本类按 `owner_biz_id` 聚合到主对象。
- **补充：外部内容表的两个陷阱（即便不用也应知悉）**：
  1. 外部内容表 `count(*)` 读的是 **content 表**而非 FTS 索引本身，当索引与 content 表不同步时计数**不反映索引真实内容**；
  2. 校验外部内容表索引一致性 `INSERT INTO x_fts(x_fts) VALUES('integrity-check')` 才可靠，`SELECT count(*)` 不足以判定。R1 改用普通内容表后可直接用 `count(*)` 与业务表活跃行数比对 + `biz_id` 孤儿检查做一致性核验（§7.3）。

**24 张业务表 ↔ FTS 表一一对应清单（照抄《表结构设计》§7.2）**：

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

> 版本类 FTS（#4/#6/#8/#21/#22）每条版本一行：`biz_id` = 版本 UUID、`owner_biz_id` = 主表 UUID，满足「历史版本检索」；主表另建元数据 FTS，避免把名称重复写进每个版本行。不建 FTS 的纯数值 / JSON 元数据表及理由见 §0.4。

### 7.3 同步 / 软删 / 一致性要点（详见《表结构设计》§7.3~§7.6）
- **三向同步触发器**：每张内容表 `AFTER INSERT` / `AFTER UPDATE WHEN 文本或 is_deleted 变化` / `AFTER DELETE` 共 3 个，24×3 = **72** 个；UPDATE 采用「先 `DELETE FROM x_fts WHERE biz_id=old.id` 再 INSERT」避免 trigram 值漂移。
- **软删**：保留 FTS 行，把 `is_deleted` 镜像置 1；查询统一带 `AND is_deleted=0` 并 JOIN 业务表二次过滤；归档（ARCHIVED）不改动 FTS。
- **重建 / 一致性**：`DELETE FROM x_fts; INSERT INTO x_fts(...) SELECT ... FROM 业务表 WHERE is_deleted=0;`；检查 ①活跃行数差 ②`biz_id` 孤儿 ③软删镜像一致 ④trigram 正向自检（命中 0 时结果不可采信）。
- **中文检索规则**：trigram 以 3 字符滑窗建索引，1~2 字查询词 `MATCH` 恒为 0 → 自动降级 LIKE 回退（限定候选集 + `LIMIT`），并联合 `entity_alias` / `business_subject_alias` 别名召回；含 `-` / `/` 等 FTS5 语法字符的查询词必须整体双引号包裹（`'"' + term.replace('"','""') + '"'`）。测试矩阵见《表结构设计》§7.4。
- **触发器总数核对**：FTS 同步 72 + 基线冻结 2（§2.3）+ 抽取不可变 2（§6.3）+ 禁物理删除 20（§8）= **96**，与 §0.1 一致。

---

## 8. R1 整改同步说明（本次改动点）

| # | 改动点 | 位置 | 对应整改项 |
|---|---|---|---|
| 1 | 顶部追加「R1 整改同步」元信息行，声明唯一真值源 | 文首 | 全局 |
| 2 | 新增 §0「统一口径与全表索引」：统一数量统计（75 / 24 / 96 / 视图 0）、公共字段基线 A/B 定义与逐表标注、75 张表 A(46)/B(29) 清单、SQL↔字典双向对应核对表、不建 FTS 的纯数值/JSON 元数据表清单及理由 | §0.1~§0.4 | R1-6 / 统计统一 |
| 3 | §7.2 FTS 章节**整体改写并标注原结论作废**：废弃 `content='issue', content_rowid='id'`（TEXT UUID 不能作整数 rowid，实测压成 rowid 0）；改为普通内容表 + `biz_id` / `owner_biz_id` / `is_deleted UNINDEXED`；补充外部内容表 `count(*)` 与 `integrity-check` 两个陷阱；照抄 24 张一一对应清单 | §7.2 | R1-3 |
| 4 | 补齐原稿一笔带过 / 缺失的 13 张表逐项说明（用途/主键/外键/关键字段/唯一约束与索引/info_nature 默认/基线 A/B/是否建 FTS）：`department`、`plan_active_baseline`、`baseline_switch_log`、`plan_activity_version`、`business_subject`、`business_subject_alias`、`business_subject_merge`、`business_subject_source`、`review_queue`、`review_extraction_link`、`review_decision`、`review_result_object`、`schema_version` | §1.4 / §2.4 / §2.5 / §2.7 / §4.1 / §6.4~§6.7 / §6.11 | R1-1/2/4/5/6 |
| 5 | 修正约束表述：`project.main_object_entity_id` 与 `equipment.manufacturer_entity_id` 已显式 `REFERENCES entity(id)`（原「表后置/动态/不建 FK」作废） | §1.1 / §1.9 | R1-6 |
| 6 | `project_member` 删除表内 UNIQUE，改表达式唯一索引 `uq_pm(... COALESCE(person_id,'') ... COALESCE(valid_from,''))`（原 UNIQUE 因可空列放行重复 NULL 组合） | §1.6 | R1-6 |
| 7 | `entity_identifier` 唯一范围由全局 `UNIQUE(id_type,identifier)` 改为 `UNIQUE(entity_id,id_type,COALESCE(source_from,''),identifier)` + `(id_type,identifier)` 非唯一检索索引 | §5.3 | R1-6 |
| 8 | `drawing.drawing_no` 由全局唯一改为按项目 `uq_dr(COALESCE(project_id,''), drawing_no)` | §3.4 | R1-6 |
| 9 | `action_measure` 增可空 `risk_id` / `issue_id` 两个硬 FK + 属主完整性 CHECK（落实评审 `(risk_id IS NOT NULL)+(issue_id IS NOT NULL)>=1`，SQL 另禁止同时挂两个硬 FK），另设 `action_measure_link` 支持 M:N | §4.5 | R1-6 |
| 10 | `object_dimension_tag` 增 `CHECK(value_type IN ('REF','FREE_TEXT'))` 及 REF 用 `value_id` / FREE_TEXT 用 `value_text` 的互斥约束 | §7.1 | R1-6 |
| 11 | `baseline_version` 删除 `is_active` 字段与 `UNIQUE(plan_id,is_active)`；保留 `UNIQUE(plan_id,baseline_no)`、新增 `UNIQUE(plan_id,plan_version_id)`、`is_readonly=1 CHECK`、`content_hash NOT NULL`；写明无差别 BEFORE UPDATE/DELETE 冻结触发器；状态外移到 `plan_active_baseline` + `baseline_switch_log` | §2.3 / §2.4 / §2.5 | R1-1 |
| 12 | `plan_activity` 降为稳定主实体，`plan_activity_version` 为每版本属性快照（`change_type` 四值、`UNIQUE(activity_id,plan_version_id)`）；`activity_dependency` / `progress_record` 增 `plan_version_id` | §2.6~§2.9 | R1-2 |
| 13 | `issue` / `risk` / `task` / `decision` / `knowledge_item` 各增 `subject_id`（`TEXT NOT NULL UNIQUE REFERENCES business_subject(id)`，knowledge_item 为可空 UNIQUE） | §4.2~§4.4 / §4.6 / §5.5 | R1-4 |
| 14 | `extraction_result` 由 `trg_extraction_immutable`（`trg_er_immutable_u/d`）保护，审核后不得删除或覆盖原始抽取 | §6.3 | R1-5 |
| 15 | 明确写出「`entity_relationship` 仅表达业务实体间语义关系（同义 / 整机-部件），**不得承载** Issue/Risk/Task 等业务事项的合并；事项合并只由 `business_subject_merge` 表达」；`entity_relationship` 原「含合并链 / merge」表述作废 | §4 引言 / §5.4 | R1-4 |
| 16 | `review_queue` 扁平表作废，改为审核链四表完整说明（任务 / M:N 链接 / 结果明细 / 正式对象映射） | §6.4~§6.7 | R1-5 |

> 本文所有表名、字段、约束、触发器、索引、FTS 对应关系、数量统计均以《Phase1.2_数据库表结构设计.md》(R1) 为唯一真值源；本轮未创建 / 执行任何 SQL 文件，未触碰 `01_Data/epcs_intelligence.db`。
