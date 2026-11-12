# Phase1.2 统一数据模型总体设计

> 系统：EPCS Shipbuilding Intelligence
> 阶段：Phase 1.2 统一数据模型与实体关系设计（纯架构设计，不建表/不迁移/不导入/不装 SDK）
> 角色：系统架构师（高见远）　日期：2026-11-12
> 上游输入：《Phase1.2_业务对象确认_PM.md》（产品确认书）+《Phase1.1_项目空间初始化报告》+《数据库初始化说明》（实测约束）
> 本文档定位：Phase 1.2 设计的总纲，回答 12 个架构问题；表级细节见《核心实体数据字典》《数据库表结构设计》，关系图见《实体关系ER图》，规则见《来源与证据追溯规范》《版本及历史管理规范》，决策记录见《架构决策记录》，未决项见《待确认事项清单》。

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

### 3.2 公共基字段（每张业务表默认具备，除非注明）
```
id            UUID PK
project_id    UUID FK → project       -- 项目范围表必填；全局/治理表可空
info_nature   TEXT ENUM(G5)           -- 信息性质，见 3.3
created_at    TEXT ISO8601 UTC        -- 记录创建时间（系统）
updated_at    TEXT ISO8601 UTC        -- 上次更新时间（系统）
created_by    UUID FK → person        -- 创建人（可空，AI 为空）
updated_by    UUID FK → person        -- 更新人（可空）
is_deleted    INTEGER(0/1) default 0  -- 软删除标记
deleted_at    TEXT                    -- 软删除时间（is_deleted=1 时填）
```

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

### 3.6 检索路由
- **FTS5 trigram**：中文内容检索的唯一事实（实测 unicode61 命中 0、trigram 命中 1）。
- 命中规则：trigram 需要≥3 字符连续串；别名/近义召回靠 `EntityAlias` 与 `EntityRelationship` 补偿（OQ-7）。
- 路由策略：业务查询（精确/关联）走关系表 + 索引；自然语言检索走 FTS trigram → 得到候选 `id` → 再回业务表。详见《架构决策记录》ADR-7。

---

## 4. 数据域总览

```
EPCS Shipbuilding Intelligence 统一数据模型
├── 域1 项目与组织（底座）        project / project_phase / organization / person /
│                                 project_member / discipline / area / system /
│                                 equipment / equipment_category + 项目×维度关联表
├── 域2 计划管理                  plan / plan_version / baseline_version /
│                                 plan_activity / activity_dependency / progress_record
├── 域3 信息与文件（来源域）      email / email_attachment / document(+version) /
│                                 drawing(+version) / drawing_object(预留) /
│                                 meeting / meeting_minutes / message /
│                                 source_reference / evidence(+link)
├── 域4 问题/风险/任务闭环         issue(+status_history) / risk(+status_history) /
│                                 task(+status_history) / action_measure /
│                                 decision(+link) / issue_link(通用对象桥)
├── 域5 实体关系与知识            entity / entity_alias / entity_identifier /
│                                 entity_relationship / knowledge_item(+version) / knowledge_entity_link
└── 域6 AI处理与系统治理          ingestion_job / extraction_result / review_queue /
                                  ai_analysis_run / audit_log / system_config /
                                  user / role / permission（Phase 后期字段预留）
```

---

## 5. 12 个架构问题的方案概要（逐项解答，详版见 ADR）

| # | 架构问题 | 核心方案（推荐） | 关键词 |
|---|---|---|---|
| 1 | 项目/船舶/合同建模 | 项目承载"一艘主造对象"（`project.main_object_entity_id → entity`）；合同**不强实体**，用 `project_member`（项目×组织×角色）+ 关联文档承载；多船/船队经 `project↔entity` 多对多扩展（不封闭） | ADR-1 |
| 2 | EPCS 阶段与专业/区域/系统 | 阶段=时间纵轴、专业/区域/系统=横坐标，**正交**；统一经 `object_dimension_tag` 多值标签表达，允许并列/跨阶段 | ADR-2 |
| 3 | 人员/组织/项目角色 | `organization→person` 1:N；`project_member` = 项目×组织×角色三维承载任职；同人可多项目多角色 | ADR-3 |
| 4 | 一问题多计划/邮件/会议/文件 | `issue_link` 通用对象桥（M:N）+ `source_reference`（来源桥）；一处登记全链路引用 | ADR-4 |
| 5 | 一文件被多事项引用 | 文件只读事实源，`source_reference` 携带 `context_excerpt` + `locator`（引了哪段/哪图），M:N 不封闭 | ADR-5 |
| 6 | 避免重复创建（全局实体标识+合并） | 摄入→`extraction_result`→`review_queue`(候选检索 trigram+别名)→人工"合并/新建"→实体；合并记为 relation，链不丢 | ADR-6 |
| 7 | AI 推断与人工事实分离 | `info_nature` 六层全库强制；AI 产出默认 `AI_INFERENCE`→ReviewQueue→确认升 `CONFIRMED_FACT`；未经确认不落正式实体 | ADR-7 |
| 8 | 计划版本/基线/滚动预测共存 | `plan_version`(含 `is_forecast`)+`baseline_version`(只读)；滚动=多版本发布非造表；基线只读触发器+应用层+审计 | ADR-8 |
| 9 | 业务数据完整历史 | 版本容器(内容 hash+快照)+状态历史表+软删除；正式记录禁物理删除；历史可回放 | ADR-9 |
| 10 | DWG 预留 | `drawing`+`drawing_version`+`drawing_object`(对象结构预留)；**不装 SDK、不解析**，仅留关联字段与几何占位 | ADR-10 |
| 11 | 事项跨 E/P/C/S 跟踪 | 阶段标签多值关联，`阶段=不确定/跨阶段`可并列表达；对象生命周期跨阶段以 tag 记录而非改写 | ADR-11 |
| 12 | 避免旧库硬编码与固定目录 | 维度值全部入维度表/`system_config`；`02_Original_References` 只读归档；外部编号入 `entity_identifier`；不复制旧结构（G3） | ADR-12 |

---

## 6. 已确定 vs 待确认（速览）

- **已定（直接采用）**：6 域对象清单、对象间关系、B.1~B.8、G1~G7、状态机、基线只读、信息性质六层（详见《待确认事项清单》§1）。
- **需人工/后续确认**：6 项（D.2）——邮件正文授权与脱敏、角色清单、设备分类树标准、外部编码映射协议、计划 L1~L4 规范、知识沉淀判定。建模已留有接口，**未封死**。

---

## 7. 迁移策略（本阶段只写迁移脚本草案，不执行）

- 本阶段（Phase 1.2 纯架构）**不建表、不执行迁移**；产出 `migrations/001_init.sql` 之**草案**（见《数据库表结构设计》）。
- 迁移脚本要求：幂等（`IF NOT EXISTS`/存在性检查）、表结构全部含 `created_at` 等基线字段、FTS5 trigram 建在内容表之后。
- 数据库仍为 `01_Data/epcs_intelligence.db`，schema 变更永远走 migrations，不手工改库。
- 兼容 PostgreSQL 迁移：`01_Data/migrations/` 下预留 DDL，UUID 采用 TEXT 存 `char(32)`，时间用 ISO8601 文本，为迁 Pg 保留转换面。

---

## 8. 本文档引用关系

- 全部表级字段定义 →《Phase1.2_核心实体数据字典.md》
- ER 图（Mermaid） →《Phase1.2_实体关系ER图.md》
- 完整 CREATE TABLE 草案 →《Phase1.2_数据库表结构设计.md》
- 来源/证据机制 →《Phase1.2_数据来源与证据追溯规范.md》
- 版本/历史/软删/基线 →《Phase1.2_版本及历史管理规范.md》
- 12 问题 + OQ-1~7 决策 →《Phase1.2_架构决策记录.md》
- 未决事项与责任归属 →《Phase1.2_待确认事项清单.md》