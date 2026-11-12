# Phase1.2 架构决策记录（ADR）

> 系统：EPCS Shipbuilding Intelligence　日期：2026-11-12　决策人：系统架构师（高见远）
> 本文档对本阶段开放问题 OQ-1~7 及 12 个架构问题给出**决策记录**（含方案对比与推荐），便于后续评审与变更跟踪。每个 ADR 格式：背景 / 方案 / 优缺点 / 推荐 / 状态。

---

## ADR-1 项目/船舶/合同建模（架构问题 1）

- **背景**：B.1 产品已定"项目承载一艘主造对象、多合同靠 组织×角色 + 关联文档 表达；不强合同表"。OQ-1 遗留是否引入独立 Contract 强实体。
- **方案A（推荐·弱实体）**：项目承载主造对象（`project.main_object_entity_id→entity`）；合同事实用 `project_member(is_contract_carrier=1)` + `source_reference` 关联文档承载；不建 `contract` 表。未来若需合同强实体，可新增表并入 `project` 而不破坏现有结构。
- **方案B（强合同实体）**：独立 `contract` 表（合同号、甲方/乙方、金额、签署）。
  - 优点：合同维度强表达、可独立查询/审计。
  - 缺点：违背"不强实体"产品倾向、一期增加复杂度、合同与角色关系需再建模。
- **优点（A）**：贴合产品倾向；组织×角色三维本就承载合同；动态可扩展。
- **缺点（A）**：合同级专属字段（金额/份数）暂无处放——一期用 `project.contract_summary` + 文档/evidence 承载。
- **推荐**：**方案A（弱实体）**，`project_member.is_contract_carrier` 备好升级位。多船/船队经 `project↔entity`(M:N) 扩展，不封闭。
- **状态**：定。

---

## ADR-2 EPCS 阶段与专业/区域/系统的关系（架构问题 2）

- **背景**：B.2 定 EPCS 为时间纵轴、专业/区域/系统为横坐标，正交、可并列，禁止 status 枚举锁死。OQ-5 问实现粒度（统一关联表 vs 分表）。
- **方案A（推荐·统一关联表）**：`object_dimension_tag` 一张表，`dimension ∈ {EPCS_PHASE, DISCIPLINE, AREA, SYSTEM}` + `value_id/value_text`。
  - 优点：统一接口、任意对象打任意多标签、自由值表达"阶段不确定/跨阶段"、FTS 命中统一；新增维度只加 dimension 枚举不动表。
  - 缺点：SQL 上对某一路维度查询需按 dimension 过滤；性能由 `idx_odt_dim(dimension,value_id)` 补偿。
- **方案B（分表）**：`issue_phase`/`issue_discipline`… 每对运行时建表。
  - 优点：查询直观。
  - 缺点：对象×维度无数组合、schema 爆炸、维护难。
- **推荐**：**方案A**。主维度允许放快捷列（如 `plan_activity.discipline_id`）提性能，副维度一律走 tag。
- **状态**：定（OQ-5 关闭为"统一关联表"）。

---

## ADR-3 人员/组织/项目角色关联（架构问题 3）

- **背景**：Organization→Person 1:N；人员跨项目承担角色须可表达且不重复定义。
- **方案（定）**：`organization→person` 1:N；`project_member` = project×organization×person×role×valid_from，`UNIQUE` 防重复，`is_contract_carrier` 承载合同事实（ADR-1）。同人多项目多角色由多次 `project_member` 表达。用户/账号体系（`user`）Phase 后期启用，与 `person` 关联预留。
- **推荐**：此方案。`person_id` 可空以支持"组织级角色"。
- **状态**：定。

---

## ADR-4 "一问题多计划活动/邮件/会议/文件"多对多（架构问题 4，B.3）

- **背景**：Issue↔PlanActivity/Email/Meeting(Minutes)/Document/Drawing/Message/Evidence 全部 M:N，统一经引用桥，实现一页纸问题看板。
- **方案A（推荐·对象桥）**：`object_link(left_type,left_id / right_type,right_id, role, context_excerpt)`，M:N；来源承载走 `source_reference`。
  - 优点：一个桥覆盖全部业务对象间 M:N，schema 不膨胀；新增对象类型不改表。
  - 缺点：多态引用无硬 FK，需应用层+审计+摄入校验兜底。
- **方案B（每对建关联表）**：issue_activity/issue_email/issue_document…。
  - 缺点：组合爆炸、维护成本高，且"一文件被多引用"（B.4）会裂成多张。
- **推荐**：**方案A（`object_link`）**，配合 OQ-2 的合并链（ADR-6）。
- **状态**：定。

---

## ADR-5 "一个文件被多事项引用"多对多（架构问题 5，B.4）

- **背景**：文件/图纸只读事实源，被多个（问题/任务/决策/活动/风险/知识）同时引用，且引用带上下文摘录。
- **方案（定）**：`source_reference` 已含 `traced_entity + source + context_excerpt + locator`，即一文件被 N 个`traced_entity`引用（N 行 source_reference，source 同一）；文件端只读（`document.is_readonly=1`）+版本化，不可反向篡改。检索时按 `source_id` 反查可得引用方列表。
- **补充**：引用上下文摘录 `context_excerpt` 满足"引了哪段/哪图"回溯（B.4）。
- **推荐**：直接采用，不另建表。
- **状态**：定。

---

## ADR-6 全局实体标识 + 合并机制防重复（架构问题 6，B.5 / OQ-2）

- **背景**：同一问题可能在邮件/会议/任务重复出现；需全局实体标识 + 别名 + 合并，且合并链不丢历史。
- **方案A（推荐）**：以 `entity` 作**全局实体标识**；摄入 AI → `extraction_result`(AI_INFERENCE) → `review_queue`（系统 trigram+alias 实时候选 `suggested_entity_id`）→ 人工 `ACCEPT_AS_NEW / MERGE_TO / REJECT`。合并写 `entity_relationship(relation_type=synonym/merge, confirm_status, source_reference_id)`，并在 `extraction_result.status` 标 merged，`review_queue.target_entity_id` 记目标。完整链可回放。
  - 优点：一处登记、全链路引用；合并链完整；防重复（未确认不落正式实体）。
  - 缺点：多态引用需校验（ADR-4）；合并判据靠 source_reference 证据留痕。
- **方案B（无统一标识，各表各自 ref_no）**：难跨来源去重，冗余风险高。**不采用**。
- **推荐**：**方案A**。
- **状态**：定（OQ-2 关闭）。`issue` 本身不直接自引用合并，一律经 `entity` 归一——保证"同一艘船/设备/部位"跨问题、跨文档归一。

---

## ADR-7 AI 推断与人工事实分离（架构问题 7，B.8 / OQ-7）

- **背景**：消息性质六层 G5 定案；AI 产出默认 `AI_INFERENCE` 进 ReviewQueue；FTS 中文检索须 trigram + 同/近义召回。
- **方案（确定）**：
  1. `info_nature` 六枚举**全库强制**作基字段；`AI_INFERENCE/PREDICTION/PROPOSAL` 不得自动升级为正式事实（火焰图见表结构）。
  2. G5 枚举存 `system_config` 归口（OQ-4）——固定但可扩展，不硬编码硬分隔。推荐：枚举值属性名放 `system_config`，**校验逻辑仍可用 `check` 硬枚举守住数据库层**（双轨，见"推荐"）。
  3. FTS：全部内容表 trigram；同/近义召回路由 = `entity_alias_fts`(trigram 模糊) → alias→entity → 与 source_reference/object_link 间链，再并入主检索。FTS 路由 vs 触发器同步在 ADR-7b（下）权衡。
- **推荐**：`info_nature` 用 **`CHECK` + `system_config` 双轨**；FTS 用**外部内容表 + 触发器同步**，查询量可控时改定时重建（见 ADR-7b）。
- **状态**：定（OQ-4/OQ-7 关闭为"双轨 + trigram + 外部内容表"）。

### ADR-7b FTS 同步策略
| 方案 | 说明 | 推荐 |
|---|---|---|
| 触发器即时同步 | 增删改实时同步 FTS，查询最新 | **一期默认**（写入量小） |
| 摄入批量重建 | 摄入完成后重建 FTS，避免每次写触发器 | 二期摄入高频时切换，接口 `rebuild_fts()` |
| 定时任务 | 依赖外部调度，一期不引 | 不做 |

推荐：**触发器即时同步**，一期写入频率低、成本可忽略。

---

## ADR-8 计划版本/批准基线/滚动预测共存（架构问题 8，B.7 / OQ-3）

- **背景**：Plan→PlanVersion 1:N；Plan→BaselineVersion 1:N，某一刻仅一个当前生效基线；滚动预测以多版本发布而非造表；基线只读受保护。
- **方案（确定）**：
  - `plan_version(is_forecast)` 承载滚动/AI 预测版本（info_nature=PREDICTION）。
  - `baseline_version` 引用 `plan_version`，`is_active` 部分唯一索引保证"一时一基线"；`is_readonly=1` 只读。
  - 只读强制：**BEFORE UPDATE/DELETE 触发器 + 应用层拦截 + AuditLog**（OQ-3 三重防御）；AI 只能新增 `plan_version`，禁改基线；偏差用 `progress_record` vs 基线表达。
- **推荐**：此方案。基线变更仅允许人工权力操作（走审计+授权）。
- **状态**：定（OQ-3 关闭）。

---

## ADR-9 业务数据完整历史（架构问题 9，G4）

- **背景**：版本化+软删+历史回放；正式记录禁物理删除；成本可控。
- **方案A（推荐）**：版本容器（`*_version` + 内容 hash + snapshot_json 渐进）＋状态历史表＋软删（is_deleted/del_status）＋正式表禁物理删除触发器。快照先记录 `assets/` 资产引用，全量快照按需补。
  - 优点：历史完整可回放；一期成本可控。
  - 缺点：snapshot_json 全量 vs 增量需定（D.2 待人工确认成本边界）。
- **方案B（全量快照每版）**：历史最全但存储成本高、一期过度。**不采用**。
- **推荐**：**方案A**。
- **状态**：定（快照粒度 D.2-6 待确认）。

---

## ADR-10 DWG 图纸对象预留（架构问题 10）

- **背景**：未来 DWG 解析涉及图纸↔设备/区域/系统/问题关联；本阶段**不装 SDK、不解析**，仅预留结构。
- **方案（定）**：`drawing(+drawing_version)` 已承载图纸与 revision；`drawing_object` 预留 DWG 对象表：`obj_type / ref_entity_id / ref_area_id / ref_system_id / geometry_json(占位) / reserved_data`。未来装 SDK 后只填字段，不改 schema。
- **关联预留**：`drawing` 已可经 `source_reference`/`object_link` 与 issue/equipment 等关联；`drawing_object.ref_entity_id→entity` 即设备/部位归一。
- **推荐**：直接采用；不引入 SDK、不引外部坐标格式假定。
- **状态**：定（DWG SDK 选型属后续 Phase，另行审批）。

---

## ADR-11 事项跨 E/P/C/S 阶段跟踪（架构问题 11，B.2）

- **背景**：一个对象（问题/风险/决策…）在建造推进中横跨多个 EPCS 阶段，且阶段可与专业/区域/系统并列，允许"阶段不确定/跨阶段"。
- **方案（定）**：对象挂 `object_dimension_tag(dimension=EPCS_PHASE, value_id 或 value_text="不确定/跨阶段")` **追加式**表达——对象生命周期跨阶段以标签累积呈现，而非把阶段做成会覆盖的 status。查询"当前处于哪些阶段"= 过滤该对象的最新 tag 集；历史跨阶段由 tag 时间戳回放。
- **补充**：`project_phase` 记录项目级 EPCS 实例，全局阶段目录由 `system_config`/dimension 归口，不硬编码。
- **推荐**：直接采用（与 ADR-2 同机制）。
- **状态**：定。

---

## ADR-12 避免旧库硬编码与固定目录（架构问题 12，G1/G3/G7）

- **背景**：旧库存在硬编码船名/项目/专业、固定目录问题；本系统全新建模，G3 严格隔离。
- **方案（定）**：
  - 一切维度值（船型/项目/专业/区域/系统/角色/枚举）入**维度表或 `system_config`**，ID 引用，杜绝字面值（G7）。
  - 外部自然编号统一入 `entity_identifier`（id_type/source_from/identifier）+ `EntityAlias`（简称/译名），不写死。
  - 原始资料 `02_Original_References` 只读归档，不复制旧结构、不引旧脚本/旧库（G3 表）。
  - 全库 Schema 由唯一 `migrations` 管理，永不经手工改库。
- **推荐**：此方案即"全链维度化 + 只读来源 + 唯一 schema 源"。
- **状态**：定。

---

## 类图与程序调用流（架构层）

### 类图（数据模型核心类）

```mermaid
classDiagram
    class Project {
      +id: UUID
      +project_code: str
      +main_object_entity_id: UUID
      +status: str
      +contract_summary: str
    }
    class ProjectPhase { +phase_code: str +seq_no: int }
    class Organization { +org_code: str +name: str }
    class Person { +name: str }
    class ProjectMember { +role_name: str +is_contract_carrier: bool }
    class Equipment { +name: str }
    class Plan { +name: str +level: str }
    class PlanVersion { +version_no: str +is_forecast: bool }
    class BaselineVersion { +baseline_no: str +is_active: bool +is_readonly: bool }
    class PlanActivity { +name: str +is_milestone: bool }
    class ProgressRecord { +progress_pct: float }
    class Issue { +ref_no: str +status: str }
    class IssueStatusHistory { +new_status: str +reopen_count: int }
    class Risk { +ref_no: str +strategy: str }
    class Task { +ref_no: str }
    class ActionMeasure { +measure_type: str }
    class Decision { +conclusion: str }
    class SourceReference { +traced_entity_type: str +source_type: str +context_excerpt: str }
    class Evidence { +title: str +sha256: str }
    class ObjectLink { +link_role: str +right_type: str }
    class ObjectDimensionTag { +dimension: str +value_text: str }
    class Entity { +name: str +entity_kind: str +status: str }
    class EntityAlias { +alias: str +confirm_status: str }
    class EntityIdentifier { +id_type: str +identifier: str }
    class EntityRelationship { +relation_type: str +confirm_status: str }
    class KnowledgeItem { +title: str }
    class KnowledgeVersion { +content_md: str }
    class IngestionJob { +source_type: str +status: str }
    class ExtractionResult { +candidate_type: str +confidence: float }
    class ReviewQueue { +decision: str +target_entity_id: UUID }
    class AuditLog { +actor_type: str +action_code: str }

    Project "1" --> "0..*" ProjectPhase
    Project "1" --> "0..*" ProjectMember
    Organization "1" --> "0..*" Person
    Organization "1" --> "0..*" ProjectMember
    Project "1" --> "0..*" Plan
    Plan "1" --> "0..*" PlanVersion
    Plan "1" --> "0..*" BaselineVersion
    Plan "1" --> "0..*" PlanActivity
    PlanActivity "1" --> "0..*" ProgressRecord
    Project "1" --> "0..*" Issue
    Issue "1" --> "0..*" IssueStatusHistory
    Project "1" --> "0..*" Risk
    Project "1" --> "0..*" Task
    Entity "1" ..> "0..*" EntityAlias : has
    Entity "1" ..> "0..*" EntityIdentifier : has
    Entity "1" --> "0..*" EntityRelationship : links
    Entity "0..1" --> "0..1" Entity : canonical_merge
    KnowledgeItem "1" --> "0..*" KnowledgeVersion
    IngestionJob "1" --> "0..*" ExtractionResult
    ExtractionResult "1" --> "0..*" ReviewQueue
    SourceReference ..> Entity : traces(M:N)
    ObjectLink ..> Entity : relates(M:N)
    ObjectDimensionTag ..> Entity : tags(M:N)
```

### 程序调用流（摄入→合并→进入业务）（核心流程）

```mermaid
sequenceDiagram
    participant UI as 人工审核UI
    participant RV as ReviewQueue
    participant AS as 应用服务
    participant FTS as FTS5 trigram
    participant EN as Entity
    participant SRC as SourceReference

    Note over UI,SRC: B.5 防重复 + OQ-2 合并链
    UI->>RV: 打开候选审核项
    RV->>FTS: 实时候选检索(entity_alias_fts + entity_fts)
    FTS-->>RV: suggested_entity_id(同名/近义)
    alt 人工选"合并"
        UI->>AS: MERGE_TO(target_entity_id)
        AS->>EN: 写 entity_relationship(synonym/merge, confirm_status)
        AS->>SRC: source_reference_id 记录合并判据
        AS->>RV: target_entity_id + decision= MERGE_TO; extraction_result.status=merged
    else 人工选"新建"
        UI->>AS: ACCEPT_AS_NEW
        AS->>EN: 建新 Entity
        AS->>SRC: source_reference(traced_entity=new)
        AS->>RV: decision=ACCEPT_AS_NEW
    else 拒绝
        UI->>AS: REJECT
        AS->>RV: decision=REJECT; extraction_result.status=REJECT(留痕)
    end
    AS-->>UI: 返回合并/新建/拒绝结果(均写 AuditLog)
```

---

## 未采纳备选与后续开关

- 独立 `contract` 表：一期不用，ADR-1 备升级位。
- 每对 M:N 独立关联表：不采用，统一 `object_link`（ADR-4）。
- G5 枚举纯 check 或纯 config：采用**双轨**（ADR-7）。
- DWG SDK：本阶段不装（ADR-10），后续 Phase 另行审批。