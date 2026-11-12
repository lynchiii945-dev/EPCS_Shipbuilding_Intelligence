# Phase1.2 数据来源与证据追溯规范

> R1 整改同步：2026-11-12，以《Phase1.2_数据库表结构设计.md》(R1) 为唯一真值源
> 目标：落实 G2（来源可追溯）与 B.4（文件只读事实源，可被多事项引用）的统一机制，避免各表各自造"来源"字段。本规范定义 `SourceReference`、`Evidence`、`IngestionJob→ExtractionResult` 全链路追溯，以及"来源引用"的分层与去重。

---

## 1. 三层追溯模型

```
摄入来源层（原样）：email / email_attachment / document_version / drawing_version /
                    meeting / meeting_minutes / message  ← 原始载体，只读
        │  source_reference（统一来源桥）/ business_subject_source（事项↔来源证据 M:N）
        ▼
业务事实层：business_subject（统一事项主档）→ issue / risk / task / decision /
            plan_activity / knowledge_item / entity（具体事项 1:1 挂 subject_id）
        │  object_link（业务对象间引用）
        ▼
派生结论层：knowledge_item → 可再被引用

证据层：evidence（独立凭证）+ evidence_link（挂任意实体）
```

**规则**：
- 原始载体（邮件正文/文档正文/图纸）只读，只能软删/版本化，不可反向篡改（B.4）。
- 业务事实都必须能至少通过一条 **G2 追溯通道** 定位到来源：`source_reference`（通用来源桥）、`business_subject_source`（业务事项↔来源证据 M:N）、`review_result_object`（审核结果→正式对象稳定映射）；三类通道的覆盖率由自检 SQL 核验（《表结构设计》§8 / 《整改记录》§8 第 1 项）。
- 派生结论（knowledge）需要"证据链"支撑：`source_reference`（原文）+ `evidence_link`（凭证）+ `business_subject_merge`（事项合并判据）/ `business_subject_source`（事项来源证据）。
- **R1-4 更正**：`entity_relationship` 仅表达业务实体（设备/船舶/组织/专业…）之间的语义关系（同义、整机-部件），**不得**承载 Issue/Risk/Task 等业务事项的合并判据；事项合并一律走 `business_subject_merge`。

---

## 2. `source_reference` 设计要点

| 字段 | 语义 | 说明 |
|---|---|---|
| traced_entity_type / traced_entity_id | 被溯源对象 | 多态：issue/risk/task/decision/activity/knowledge/entity/business_subject… |
| source_type / source_id | 来源载体 | 多态：email/email_attachment/document(→version)/drawing(→version)/meeting(→minutes)/message/evidence |
| context_excerpt | 上下文摘录 | "引用了哪一段/哪张图"，便于回溯；可行时存剪贴内容 |
| locator | 定位 | 段落号/图号/pin/行号 |
| info_nature | 溯源关系事实级别 | 默认 SOURCE_FACT |
| confidence | 置信度 | AI 抽取时给出，人工确认可改为 1.0 |

**为什么要多态而非硬外键**：来源载体与被溯源实体分属不同表，且未来不断新增类型（如未来 DWG 图纸对象）；多态避免"新增来源类型就加一列外键"。代价是缺 FK 完整性，由应用层 + `AuditLog` + 摄入后校验兜底（ADR-6）。

**R1-6 补充：`sp_check_polymorphic_refs` 多态孤儿自检（可执行补偿，非硬 FK）**：
- 一组按 `type` 分派到目标表的 `UNION ALL` 查询（《表结构设计》§7.6），覆盖 `source_reference` / `object_link` / `evidence_link` / `decision_link` / `action_measure_link` / `review_result_object` / `business_subject_alias` / `object_dimension_tag` 八类多态引用，逐一查出指向不存在对象的孤儿行。
- **执行时机**：每个摄入作业（`ingestion_job`）完成后 + 定期维护；检出结果写入 `audit_log`。
- **已知取舍（不伪装成硬 FK）**：多态字段没有数据库硬外键，采用「应用层校验 + `sp_check_polymorphic_refs` 自检 + 审计留痕」三层补偿；这是明确的架构取舍，而非声称具备 FK 级完整性。

---

## 3. `evidence` 证据链（佐证业务事实）

- `evidence`：独立凭证（片段、附件、截图），`sha256` 去重。
- `evidence_link`：`evidence_id` ↔ 任意对象（`ref_type + ref_id`），带 `link_role`（佐证/反证/依据）与 `context_excerpt`。
- `business_subject_source`：业务事项 ↔ `source_reference` 的 M:N 证据桥，与 `evidence_link`（任意对象↔凭证）分工互补（R1-4）。
- 用途：问题验证、风险佐证、决策依据、知识支撑。

---

## 4. 摄入与抽取全链路（R1-5 四表审核链）

> **【原稿整段作废】** 原 §4 把 `review_queue` 描述为单表（自带 `decision` / `target_entity_id`，合并写 `entity_relationship(synonym/merge)` 并在 `extraction_result` 标记 merged/reject）。该流程与 R1-4 / R1-5 冲突：无法拆分/合并、无法指向多类型正式对象、无审核人/理由/证据、原始抽取可被覆盖。整段作废，以下为以《表结构设计》§6 为唯一真值源的 R1 整改版全链路。

```
原始载体(邮件/文件/会议)
        │  ingestion_job（source_type + source_id，re_runnable 幂等重跑）
        ▼
extraction_result（candidate_type / candidate_json / raw_text，info_nature=AI_INFERENCE，confidence）
        │  原始内容冻结：trg_extraction_immutable（《表结构设计》§6 中为
        │  trg_er_immutable_u / trg_er_immutable_d）——审核后不得删除、不得覆盖
        │  candidate_json / raw_text / ingestion_job_id
        ▼
review_extraction_link（审核任务 ↔ 抽取结果 M:N，UNIQUE(review_queue_id, extraction_result_id)）
        ▼
review_queue（纯审核任务表：review_type / status / candidate_summary / suggested_subject_id，
             info_nature=AI_INFERENCE；不再带 decision / target_entity_id）
        ▼
review_decision（一个任务可多条结果；decision ∈ ACCEPT_AS_NEW / MERGE_TO / REJECT；
                 reviewer_person_id / reviewed_at / reason / evidence_source_reference_id 必填，
                 info_nature=CONFIRMED_FACT）
        ▼
review_result_object（object_type ∈ ISSUE/RISK/TASK/DECISION/KNOWLEDGE_ITEM/ENTITY/BUSINESS_SUBJECT
                      + object_id + relation ∈ CREATED/MERGED_INTO/REJECTED，稳定映射到正式对象）
        ▼
正式对象（ISSUE / RISK / TASK / DECISION / KNOWLEDGE_ITEM / ENTITY / BUSINESS_SUBJECT）
```
> 注：`review_extraction_link` 为 `review_queue` ↔ `extraction_result` 的 M:N 桥表（FK 同时指向两表）；上图按「抽取结果 → 审核任务」的追溯阅读顺序列出。

**链路要点**：
- **一条抽取拆多个正式对象**：1 个 `review_decision` 下写多条 `review_result_object`（或拆成多条 decision），例如一条抽取同时生成 ISSUE 与 RISK（实测《表结构设计》§6.5 PASS）。
- **多条抽取合一对象**：`review_extraction_link` 多条 → 1 个 `review_queue` → 1 个 `MERGE_TO` decision → 1 条 `review_result_object` 指向同一 `object_id`。
- **`MERGE_TO`**：除写 `review_result_object(MERGED_INTO)` 外，**同时写 `business_subject_merge`（可逆合并链）——不是 `entity_relationship`**；`entity_relationship` 只管业务实体语义关系，不得承载事项合并。
- **`REJECT`**：不生成正式对象（写 `review_result_object(REJECTED)` 或仅留 decision），**亦需 `reason`**，且原始 `extraction_result` 完整保留供追溯。
- **G5 信息性质链**：`extraction_result=AI_INFERENCE` → `review_decision=CONFIRMED_FACT`（人工确认）→ 正式对象 `=CONFIRMED_FACT`；`review_result_object` 记录从 AI 推断到人工事实的落点，**不得自动升级**。
- **历史不丢**：四表均为只增/软删，`extraction_result` 原始字段冻结；任一候选被接受/合并/拒绝都在表中留痕，可完整回放（ADR-6 / ADR-7 修订）。

---

## 5. 去重与防重复（B.5，R1-3 / R1-4 修订）

> 原稿把候选检索与"合并"都落在 `entity` / `entity_relationship` 单表，结论作废；改为**业务实体 / 业务事项双层** + 两套 FTS + 四表审核链。

1. 摄入时 AI 抽取 → 经 `review_extraction_link` 进 `review_queue`，**未经人工确认绝不自动落正式对象**（杜绝污染）。
2. **双层候选检索**（系统实时提示"可能已存在"，写入 `review_queue.suggested_subject_id`）：
   - **业务实体层**：`entity_fts`（`name`）/ `entity_alias_fts`（`alias`）；
   - **业务事项层**：`business_subject_alias_fts`（`alias`） + `source_reference` 来源比对。
3. **短词与特殊字符规则（《表结构设计》§7.4 实测）**：
   - FTS5 `trigram` 以 3 字符滑窗建索引，**对 <3 字短词 `MATCH` 恒为 0**（单字/双字不命中）；查询词长度 <3 时自动降级为 **LIKE 回退**（`WHERE title LIKE '%x%' OR description_md LIKE '%x%'`，限定项目/候选集并加 `LIMIT`），并联合 `entity_alias` / `business_subject_alias` 别名表做**短词等值召回**。
   - 含 `-` / `/` 等 FTS5 语法字符的查询词**必须整体双引号包裹**（如 `"CMHI-001"`、`"FAT 11/5"`），查询构造器统一用 `'"' + term.replace('"','""') + '"'`，否则报语法错误。
4. **人工决策（三选一）**：
   - `ACCEPT_AS_NEW`：新建正式对象，写 `review_result_object(CREATED)`；
   - `MERGE_TO`：并入已存在事项，写 `review_result_object(MERGED_INTO)` + **`business_subject_merge`**（可逆）；撤销错误合并 = 置 `undone_at / undone_by / undo_reason`、`is_active=0`，并令 `from_subject.status` 由 `MERGED` 回 `ACTIVE`、`canonical_subject_id` 清空，**不物理删除任何记录**；
   - `REJECT`：不生成正式对象，保留原始抽取，须填 `reason`。
5. **硬兜底**：`issue/risk/task/decision.ref_no` 唯一、`entity_identifier` 表达式唯一索引（`entity_id, id_type, COALESCE(source_from,''), identifier`）、`business_subject_alias UNIQUE(subject_id, alias)`。
6. **职责边界**：`entity_relationship` 只管业务实体语义关系（同义/整机-部件），**不得承载事项合并**；事项合并只在 `business_subject_merge` 表达（R1-4）。

---

## 6. 审计与一致性

- 任何来源写入、合并、确认操作写 `audit_log`（actor_type=USER/AI，before/after）；§4 四表审核链的每次决策与结果映射均应写 `audit_log`。
- 摄入重跑：`ingestion_job.re_runnable` 幂等；同名来源经 `sha256`/`source_id` 判定并入不重复创建。
- 一致性由「摄入后 `sp_check_polymorphic_refs` 多态自检 + 软删除过滤 + 应用层权限 + 审计」四层保险，结果写 `audit_log`；本阶段不引入外键级联复杂化。

---

## 7. 待确认（本规范后续依赖）

- 邮箱正文授权的读取边界与脱敏粒度（D.2-1）。
- 外部企业编码/ERP 编号映射协议（D.2-4）——`entity_identifier.source_from` 的真实来源清单。
- 知识沉淀判定细则（D.2-6）。
- **R1 新增 N1~N10 见《架构评审整改记录》§10 / 《待确认事项清单》**（与本规范直接相关：N2 切换日志/审计留存期、N3 短词 LIKE 回退阈值、N4 软删 FTS 行取舍、N6 事项合并撤销后引用重指向、N7 枚举扩展流程）。

---

## R1 整改同步说明

本轮依据《Phase1.2_数据库表结构设计.md》(R1，唯一真值源) 与《Phase1.2_架构评审整改记录.md》(R1) 做定向修订：

- **统一统计口径**：实体表 **75**（业务主表 46 + 辅助 29）、FTS5 虚拟表 **24**、触发器 **96**、视图 **0**。
- **§4 整段作废重写**：由「`review_queue` 单表 + `entity_relationship` 合并」改为 R1-5 四表审核链（`review_queue` / `review_extraction_link` / `review_decision` / `review_result_object`）+ `extraction_result` 原始内容冻结 + `business_subject_merge` 可逆合并 + G5 信息性质链。
- **§5 重写**：候选检索改为业务实体/业务事项双层 FTS，补 trigram 短词 LIKE 回退、特殊字符双引号包裹、三种人工决策与 `entity_relationship` 职责边界。
- **§2 补充**：`sp_check_polymorphic_refs` 多态孤儿自检策略（覆盖 8 类引用、按 type 分派 UNION、摄入后 + 定期执行、结果写 `audit_log`），明确「应用层 + 自检 + 审计」三层补偿为已知取舍。
- **§1 更正**：G2 三类追溯通道（`source_reference` / `business_subject_source` / `review_result_object`）；`entity_relationship` 不再作为事项合并判据。
- **§3 / §6 / §7**：补 `business_subject_source`、四表链写审计、R1 新增待确认 N1~N10 的索引说明。
- **边界**：本阶段未创建/执行任何 SQL 迁移、未改数据库、未装 SDK、未接入外部渠道、未读取真实邮件或旧知识库数据；当前状态为等待系统架构师再次审核。
