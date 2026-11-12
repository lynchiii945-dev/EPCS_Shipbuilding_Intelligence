# Phase1.2 统一数据模型总体设计

> 系统：EPCS Shipbuilding Intelligence
> 阶段：Phase 1.2 统一数据模型与实体关系设计（纯架构设计，不建表/不迁移/不导入/不装 SDK）
> 角色：系统架构师（高见远）　日期：2026-11-12
> 上游输入：《Phase1.2_业务对象确认_PM.md》（产品确认书）+《Phase1.1_项目空间初始化报告》+《数据库初始化说明》（实测约束）
> 本文档定位：Phase 1.2 设计的总纲，回答 12 个架构问题；表级细节见《核心实体数据字典》《数据库表结构设计》，关系图见《实体关系ER图》，规则见《来源与证据追溯规范》《版本及历史管理规范》，决策记录见《架构决策记录》，未决项见《待确认事项清单》。
> R1 整改同步：2026-11-12，以《Phase1.2_数据库表结构设计.md》(R1) 为唯一真值源

---

## 1. 设计目标

1. 用**一份统一 SQLite 数据模型**承载 6 大核心数据域，作为后续所有 Phase（业务功能、解析、AI、DWG）的公共底座。
2. 严格落实产品确认书中的全局约束 **G1~G7** 与业务规则 **B.1~B.8**。
3. 对 7 个开放问题（OQ-1~7）与其本质反映的 12 个架构问题给出**明确推荐 + 备选 + 优缺点**，不回避未决项。
4. **第一期做到"够用 + 不封死"**：为后续 PostgreSQL 迁移、DWG、权限、外部渠道、业务功能预留接口，但**不引入第一期不必要的复杂设施**。

---

## 2. 设计原则（Phase 1.2 定案，写入验收）

| 原则 | 说明 |
|---|---|
| P1 锚定平面 | 一切业务对象先锚定到 `Project` 平面 + 多组织平面；不得内嵌单一船/项目/单位/专业的字面值（G1/G7）。 |
| P2 一个真相源 | 文本/版本/文件内容禁止多副本裸存；正文与解析分开，正文只读、解析可重跑（B.4）。 |
| P3 只增不改 | 业务事实只追加（历史表 + 版本容器），正式记录默认禁物理删除，历史可回放（G4 / 问题 9）。 |
| P4 来源即证据 | 一切业务事实通过 `SourceReference` + `Evidence` 统一追溯，各表**不再**各自造"来源"字段（G2 / 问题 6）。 |
| P5 全链路引用 | 任何一对实体间需要多对多时，优先走**通用引用/链接桥**，而非每个业务关系建一遍（B.3/B.4）。 |
| P6 中文可搜 | 所有承载内容的文本表挂 FTS5 **trigram** 索引；short/近义/同义召回靠 trigram + `EntityAlias` + Relation（G6 / OQ-7）。 |
| P7 AI 与人工分层 | 信息性质六层枚举(G5)作为**内容的事实级别**统一落库；AI 产出默认 `AI_INFERENCE` 进 `ReviewQueue`，人工确认后才升 `CONFIRMED_FACT`（B.5/B.8）。 |
| P8 正交维度 | EPCS 阶段（时间纵轴）与专业/区域/系统（横坐标）**正交、可并列**，用标签关联而非 status 枚举（B.2）。 |

---

## 3. 全局规则（全库通用）

### 3.1 主键标识
- 所有表 `id` 一律 **UUID（TEXT，32 位无连字符）**，跨表合并/引用统一（实测约束：唯一标识用 UUID）。

### 3.2 公共基字段（R1 双基线：逐表标注，SQL 与《核心实体数据字典》严格对应）

> 依据《Phase1.2_数据库表结构设计.md》(R1) §0.3：正式业务表用**基线 A**，辅助/关联/桥/历史/日志表用**基线 B**；不再表述为"每张表默认具备同一套字段"，而是逐表标注所用基线（详见《核心实体数据字典》§0）。

**基线 A（正式业务表）**
```
id            TEXT PRIMARY KEY CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')
project_id    TEXT REFERENCES project(id)   -- 范围表必填；全局/治理表可空
info_nature   TEXT NOT NULL DEFAULT 'CONFIRMED_FACT'  -- G5 六层 CHECK，见 3.3
created_at    TEXT NOT NULL                  -- ISO8601 UTC（系统）
updated_at    TEXT
created_by    TEXT REFERENCES person(id)    -- 可空（AI 为空）
updated_by    TEXT REFERENCES person(id)
is_deleted    INTEGER NOT NULL DEFAULT 0    -- 软删除标记
deleted_at    TEXT                          -- is_deleted=1 时填
del_status    TEXT NOT NULL DEFAULT 'ACTIVE'  -- ACTIVE / ARCHIVED / DELETED
```

**基线 B（辅助/关联/桥/历史/日志表）**
```
id            TEXT PRIMARY KEY CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')
created_at    TEXT NOT NULL
is_deleted    INTEGER NOT NULL DEFAULT 0
```

> **UUID 规则（R1 §0.3）**：统一 `uuid4().hex`（32 位小写十六进制）；DB 层 `CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')` 强制校验，应用层统一 `new_uuid()` 生成；**禁止**用文件名/姓名/项目名作主键（G7）。

### 3.3 信息性质枚举（G5，产品固定六层，可扩展）
| 枚举值 | 可自动产生 | 是否可直接作为正式事实 | 说明 |
|---|---|---|---|
| `SOURCE_FACT` | 是 | 是（忠实原文） | 原始来源内容原样落库（邮件/正文/原文） |
| `CONFIRMED_FACT` | 否 | 是 | 仅人工确认后 |
| `AI_INFERENCE` | 是 | 否（进 ReviewQueue） | AI 推断产出 |
| `PREDICTION` | 是 | 否 | AI/滚动预测 |
| `PROPOSAL` | 是 | 否 | AI/人工提案 |
| `DECISION` | 否 | 人工录入 | 人工/仲裁决策，可引 AI 依据 |

### 3.4 时间字段规范
- `event_time` 业务发生时刻 · `source_time` 来源载体时间 · `created_at/updated_at` 系统记录时间 · `valid_from/valid_to` 版本/任职/生效区间。
- 表属时间与业务发生时间**严格分离**，不混用。

### 3.5 删除语义（逻辑删除/归档/物理删除）
- `is_deleted`（软删，查询默认过滤）+ `del_status`（`ACTIVE`/`ARCHIVED`/`DELETED`）区分"归档"与"删除"。
- 正式记录默认**禁物理删除**——由触发器拦截 + 应用层拒绝 + `AuditLog` 记录（问题 9 / OQ-3 同套防御）。

### 3.6 检索路由（R1 定案）

- **FTS5 trigram**：中文内容检索的唯一事实（实测 unicode61 命中 0、trigram 命中 1）。
- **全库统一范式**：**普通内容表（contentful）FTS5 + `biz_id UNINDEXED` 显式业务 UUID 映射**，**不是外部内容表**。外部内容表的 `content_rowid` 必须是整数 rowid，原《核心实体数据字典》§7.2 的 `content_rowid='id'`（TEXT UUID）是致命错误（详见《架构决策记录》ADR-7 / ADR-7b R1 修订）。
- **24 张 FTS 一一对应**：每张承载文本的内容表对应 1 张 trigram 虚表，业务 UUID 由 `biz_id`（版本表另加 `owner_biz_id`）显式携带，查询返回稳定 UUID 再回表；**索引全部历史版本**（`document_version` / `drawing_version` / `meeting_minutes` / `knowledge_version` / `plan_activity_version` 等），主表另建元数据 FTS。
- **三向触发器同步**：每张内容表 `AFTER INSERT` / `AFTER UPDATE` / `AFTER DELETE` 三个触发器（24×3 = **72** 个）；UPDATE 采用"先 DELETE 旧 FTS 行再 INSERT 新行"避免 trigram 值漂移；**软删保留 FTS 行**，用 `is_deleted` 镜像置 1、查询统一带 `AND is_deleted=0` 并 JOIN 主表二次过滤；支持全量重建与 4 项一致性自检（活跃行数差 / `biz_id` 孤儿 / 软删镜像一致 / trigram 正向自检）。
- **双层别名召回**：`entity_alias_fts` + `business_subject_alias_fts` 双层别名召回（业务实体别名 / 业务事项别名），替代原 `EntityAlias` 与 `EntityRelationship` 的近义召回表述。
- **短词与特殊字符规则**：trigram 以 3 字符滑窗建索引，**<3 字短词 MATCH 恒为 0**，须降级 `LIKE` 回退（限定项目/候选集 + `LIMIT`）并联合别名表等值召回；**含 `-` `/` 等 FTS5 查询语法字符的查询词必须整体双引号包裹**（`'"' + term.replace('"','""') + '"'`），否则报语法错误。
- **路由策略**：业务查询（精确/关联）走关系表 + 索引；自然语言检索走 FTS trigram → 得到候选 `biz_id` → 再回业务表。ADR-7 结论已按 R1 修订为"普通内容表 + `biz_id` 映射"，详见《架构决策记录》ADR-7 / ADR-7b（R1 修订）。

---

## 4. 数据域总览

```
EPCS Shipbuilding Intelligence 统一数据模型（R1 同步）
├── 元信息                          schema_version（迁移版本登记 + ddl_fingerprint）
├── 域1 项目与组织（底座）          project / project_phase / organization / department / person /
│                                   project_member / discipline / area / system /
│                                   equipment / equipment_category + 项目×维度关联表
├── 域2 计划管理                    plan / plan_version / baseline_version /
│                                   plan_active_baseline / baseline_switch_log /
│                                   plan_activity / plan_activity_version /
│                                   activity_dependency / progress_record
├── 域3 信息与文件（来源域）        email / email_attachment / document(+version) /
│                                   drawing(+version) / drawing_object(预留) /
│                                   meeting / meeting_minutes / message /
│                                   source_reference / evidence(+link)
├── 域4 问题/风险/任务闭环          business_subject / business_subject_alias /
│                                   business_subject_merge / business_subject_source /
│                                   issue(+status_history) / risk(+status_history) /
│                                   task(+status_history) / action_measure /
│                                   decision(+link) / object_link(通用对象桥)
├── 域5 实体关系与知识              entity / entity_alias / entity_identifier /
│                                   entity_relationship / knowledge_item(+version) / knowledge_entity_link
└── 域6 AI处理与系统治理            ingestion_job / extraction_result /
                                    review_queue / review_extraction_link /
                                    review_decision / review_result_object /
                                    ai_analysis_run / audit_log / system_config /
                                    user / role / permission（Phase 后期字段预留）
```

> **统计口径（8 份文档一致，见《数据库表结构设计》§0.2）**：实体表 **75**（业务主表 46 + 辅助/关联/桥/历史/治理 29，含 `schema_version`）、FTS5 虚拟表 **24**、触发器 **96**（FTS 同步 72 + 基线冻结 2 + 抽取不可变 2 + 禁物理删除 20）、视图 **0**。

---

## 5. 12 个架构问题的方案概要（逐项解答，详版见 ADR）

| # | 架构问题 | 核心方案（推荐） | 关键词 |
|---|---|---|---|
| 1 | 项目/船舶/合同建模 | 项目承载"一艘主造对象"（`project.main_object_entity_id → entity`，R1 已显式建 FK）；合同**不强实体**，用 `project_member`（项目×组织×角色）+ 关联文档承载；`equipment.manufacturer_entity_id → entity` 亦已显式建 FK，`entity` 前置建表；多船/船队经 `project↔entity` 多对多扩展（不封闭） | ADR-1（R1 补充） |
| 2 | EPCS 阶段与专业/区域/系统 | 阶段=时间纵轴、专业/区域/系统=横坐标，**正交**；统一经 `object_dimension_tag` 多值标签表达，允许并列/跨阶段；`value_type` 增 `CHECK(REF/FREE_TEXT)` 与值互斥约束 | ADR-2 |
| 3 | 人员/组织/项目角色 | `organization→person` 1:N；`project_member` = 项目×组织×角色三维承载任职；同人可多项目多角色；唯一性改 `COALESCE(person_id,'')`/`COALESCE(valid_from,'')` 表达式唯一索引（修复 NULL 唯一性漏洞） | ADR-3 |
| 4 | 一问题多计划/邮件/会议/文件 | `object_link` 通用对象桥（M:N，统一命名）+ `source_reference`（来源桥）；一处登记全链路引用；多态引用纳入 `sp_check_polymorphic_refs` 自检 | ADR-4 |
| 5 | 一文件被多事项引用 | 文件只读事实源，`source_reference` 携带 `context_excerpt` + `locator`（引了哪段/哪图），M:N 不封闭；纳入 `sp_check_polymorphic_refs` 自检 | ADR-5 |
| 6 | 避免重复创建（全局实体标识+合并） | **业务实体 / 业务事项双层归一**：实体层 `entity`+`entity_alias`+`entity_identifier`+`entity_relationship` 只管设备/船舶/组织等；事项层 `business_subject`+`business_subject_alias`+`business_subject_merge`（**可逆合并链**）+`business_subject_source` 管 Issue/Risk/Task 等；摄入→审核四表链→人工合并/新建；**`entity_relationship` 不得承载业务事项合并** | ADR-6（R1 修订） |
| 7 | AI 推断与人工事实分离 | `info_nature` 六层全库强制（`CHECK`+`system_config` 双轨）；AI 产出默认 `AI_INFERENCE`→ReviewQueue→确认升 `CONFIRMED_FACT`，未经确认不落正式实体；FTS 统一**普通内容表 + `biz_id UNINDEXED` 显式映射**（非外部内容表，24 张一一对应 + 三向触发器，R1 结论） | ADR-7（R1 修订） |
| 8 | 计划版本/基线/滚动预测共存 | `plan_version`(含 `is_forecast`)+`baseline_version`(内容全字段冻结)；**状态分离**：`plan_active_baseline`(当前生效指针)+`baseline_switch_log`(切换授权审计)+`plan_activity_version` 逐版本快照；滚动=多版本发布非造表；无差别冻结触发器+应用层+审计四层防御 | ADR-8（R1 修订） |
| 9 | 业务数据完整历史 | 版本容器(内容 hash+快照)+状态历史表+软删除；新增 `plan_activity_version`(逐版本活动快照)与 `baseline_switch_log`(基线切换历史)两类历史；正式记录禁物理删除；历史可回放；业务事项版本由 `business_subject`+状态历史+可逆合并承载 | ADR-9 |
| 10 | DWG 预留 | `drawing`+`drawing_version`+`drawing_object`(对象结构预留)；**不装 SDK、不解析**，仅留关联字段与几何占位 | ADR-10 |
| 11 | 事项跨 E/P/C/S 跟踪 | 阶段标签多值关联，`阶段=不确定/跨阶段`可并列表达；对象生命周期跨阶段以 tag 记录而非改写 | ADR-11 |
| 12 | 避免旧库硬编码与固定目录 | 维度值全部入维度表/`system_config`（新增 `department` 部门表）；`02_Original_References` 只读归档；外部编号入 `entity_identifier`、`entity_identifier` 唯一范围收敛为 (entity_id, id_type, COALESCE(source_from,''), identifier)、`drawing_no` 唯一范围按 `COALESCE(project_id,'')` 约束；不复制旧结构（G3） | ADR-12（R1 补充） |

---

## 6. 已确定 vs 待确认（速览）

- **已定（直接采用）**：6 域对象清单、对象间关系、B.1~B.8、G1~G7、状态机、基线只读、信息性质六层（详见《待确认事项清单》§1）。
- **需人工/后续确认**：6 项（D.2）——邮件正文授权与脱敏、角色清单、设备分类树标准、外部编码映射协议、计划 L1~L4 规范、知识沉淀判定。建模已留有接口，**未封死**。
- **R1 整改新增待确认**：10 项 **N1~N10**（基线切换授权角色与审批流、切换日志/审计留存期、短词 LIKE 回退阈值与二期物化表、软删 FTS 行策略、全部历史版本入 FTS 存储放大、合并撤销后引用重指向、枚举扩展流程、`department` 与 `organization.parent_id` 职责边界、公共字段基线 A/B 裁剪、工作量单位与进度口径），见《架构评审整改记录》§10 与《待确认事项清单》。

---

## 7. 迁移策略（本阶段只写迁移脚本草案，不执行）

- 本阶段（Phase 1.2 纯架构）**不建表、不执行迁移**；产出 `migrations/001_init.sql` 之**草案**（见《数据库表结构设计》§10）。
- **幂等性 ≠ `IF NOT EXISTS`**（R1 §10.1 完整要求）：单事务执行、失败整体回滚；`schema_version` 登记版本号 + `ddl_fingerprint`（对 `sqlite_master.sql` 排序拼接后 sha256）；用 `PRAGMA table_info(<table>)` **逐列比对**列名/类型/notnull/默认值，`sqlite_master` 比对索引清单、触发器清单、FTS 虚表清单，与 `ddl_fingerprint` 不符即中止报警；FTS 重建与 4 项一致性自检（活跃行数差 / `biz_id` 孤儿 / 软删镜像一致 / trigram 正向自检）+ 多态孤儿自检；已存在且结构一致 → 跳过，结构不一致 → **拒绝执行**（不静默 ALTER）。
- **`PRAGMA foreign_keys=ON` 必须每个连接单独执行**（实测按连接生效：连接 A 开启后，新连接 B 仍 `foreign_keys=0` 且外键失效）；这是应用层连接工厂的强制职责，**不能只写在迁移脚本首行**。`PRAGMA journal_mode=WAL` 为库级持久化设置。
- 表结构按**基线 A / 基线 B** 逐表标注（见 §3.2）；FTS5 trigram 建在内容表之后，24 张虚表与内容表一一对应、三向触发器 72 个。
- 数据库仍为 `01_Data/epcs_intelligence.db`，schema 变更永远走 migrations，不手工改库。
- 兼容 PostgreSQL 迁移：`01_Data/migrations/` 下预留 DDL，UUID 采用 TEXT 存 `char(32)`，时间用 ISO8601 文本；FTS5 trigram → `pg_trgm`+GIN、`RAISE(ABORT)` → PL/pgSQL `RAISE EXCEPTION`、部分/表达式唯一索引语法基本一致、FK 引用后置表须按依赖拓扑重排（详见《数据库表结构设计》§10.3）。

---

## 8. 本文档引用关系

- 全部表级字段定义 →《Phase1.2_核心实体数据字典.md》
- ER 图（Mermaid） →《Phase1.2_实体关系ER图.md》
- 完整 CREATE TABLE 草案 →《Phase1.2_数据库表结构设计.md》
- 来源/证据机制 →《Phase1.2_数据来源与证据追溯规范.md》
- 版本/历史/软删/基线 →《Phase1.2_版本及历史管理规范.md》
- 12 问题 + OQ-1~7 决策 →《Phase1.2_架构决策记录.md》
- 未决事项与责任归属 →《Phase1.2_待确认事项清单.md》

---

## R1 整改同步说明（2026-11-12）

本次为 R1 定向整改同步，以《Phase1.2_数据库表结构设计.md》(R1) 为唯一真值源、以《Phase1.2_架构评审整改记录.md》为决策依据；仅同步与 R1 冲突的表述，其余原稿内容全部保留。

| # | 章节 | 改动点 |
|---|---|---|
| 1 | 顶部元信息 | 追加「R1 整改同步」标注行 |
| 2 | §3.2 公共基字段 | 单基线改为 R1 §0.3 **基线 A / 基线 B 双基线**（A 正式业务表 10 字段 / B 辅助·关联·桥·历史·日志表 3 字段），补 UUID `CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')` 与 `uuid4().hex` 生成规则 |
| 3 | §3.6 检索路由 | 别名召回改为 `entity_alias_fts` + `business_subject_alias_fts` 双层；明确**普通内容表 FTS5 + `biz_id UNINDEXED` 显式映射**（非外部内容表）、24 张一一对应、索引全部历史版本、三向触发器 72 个、软删 `is_deleted` 镜像过滤、<3 字短词 LIKE 回退、`-`/`/` 等特殊字符整体双引号包裹；ADR-7 引用改为 R1 结论 |
| 4 | §4 数据域总览树 | 域1 增 `department`；域2 增 `plan_active_baseline` / `baseline_switch_log` / `plan_activity_version`；域4 `issue_link`→`object_link` 并增 `business_subject` / `business_subject_alias` / `business_subject_merge` / `business_subject_source`；域6 `review_queue` 展开为四表；补 `schema_version`；补 8 份文档统一统计口径（实体表 75 / FTS5 24 / 触发器 96 / 视图 0） |
| 5 | §5 问题表 | #1 补两处显式 FK 与建表顺序前置；#2/#3 补值约束与表达式唯一索引；#4 `issue_link`→`object_link`；#6 改业务实体/业务事项双层归一 + 可逆合并链 `business_subject_merge`，删除"合并记为 relation"；#7 补普通内容表 FTS 范式；#8 改状态分离四表/机制；#9 补 `plan_activity_version` 与 `baseline_switch_log`；#12 补 `entity_identifier`/`drawing_no` 唯一范围收敛与 `department` |
| 6 | §6 速览 | 补 R1 新增 10 项待确认 N1~N10（见《架构评审整改记录》§10 与《待确认事项清单》） |
| 7 | §7 迁移策略 | 幂等性扩充为 R1 §10.1 完整要求（`PRAGMA table_info` 逐列比对 / 索引·触发器·FTS 清单比对 / `schema_version` 登记 / 单事务回滚 / FTS 重建与一致性自检），补 `PRAGMA foreign_keys=ON` 每连接单独执行（实测按连接生效） |