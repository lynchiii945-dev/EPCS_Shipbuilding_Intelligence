# Phase1.2 数据来源与证据追溯规范

> 目标：落实 G2（来源可追溯）与 B.4（文件只读事实源，可被多事项引用）的统一机制，避免各表各自造"来源"字段。本规范定义 `SourceReference`、`Evidence`、`IngestionJob→ExtractionResult` 全链路追溯，以及"来源引用"的分层与去重。

---

## 1. 三层追溯模型

```
摄入来源层（原样）：email / email_attachment / document_version / drawing_version /
                    meeting / meeting_minutes / message  ← 原始载体，只读
        │  source_reference（统一来源桥）
        ▼
业务事实层：issue / risk / task / decision / plan_activity / knowledge_item / entity
        │  object_link（业务对象间引用）
        ▼
派生结论层：knowledge_item → 可再被引用

证据层：evidence（独立凭证）+ evidence_link（挂任意实体）
```

**规则**：
- 原始载体（邮件正文/文档正文/图纸）只读，只能软删/版本化，不可反向篡改（B.4）。
- 业务事实都必须能至少通过 `source_reference` 定位到一条来源（G2）。
- 派生结论（knowledge）需要"证据链"支撑：`source_reference`（原文）+ `evidence_link`（凭证）+ `entity_relationship`（合并判据）。

---

## 2. `source_reference` 设计要点

| 字段 | 语义 | 说明 |
|---|---|---|
| traced_entity_type / traced_entity_id | 被溯源对象 | 多态：issue/risk/task/decision/activity/knowledge/entity… |
| source_type / source_id | 来源载体 | 多态：email/email_attachment/document(→version)/drawing(→version)/meeting(→minutes)/message/evidence |
| context_excerpt | 上下文摘录 | "引用了哪一段/哪张图"，便于回溯；可行时存剪贴内容 |
| locator | 定位 | 段落号/图号/pin/行号 |
| info_nature | 溯源关系事实级别 | 默认 SOURCE_FACT |
| confidence | 置信度 | AI 抽取时给出，人工确认可改为 1.0 |

**为什么要多态而非硬外键**：来源载体与被溯源实体分属不同表，且未来不断新增类型（如未来 DWG 图纸对象）；多态避免"新增来源类型就加一列外键"。代价是缺 FK 完整性，由应用层 + `AuditLog` + 摄入后校验兜底（ADR-6）。

---

## 3. `evidence` 证据链（佐证业务事实）

- `evidence`：独立凭证（片段、附件、截图），`sha256` 去重。
- `evidence_link`：`evidence_id` ↔ 任意对象（`ref_type + ref_id`），带 `link_role`（佐证/反证/依据）与 `context_excerpt`。
- 用途：问题验证、风险佐证、决策依据、知识支撑。

---

## 4. 摄入与抽取全链路（OQ-2 合并链不丢历史）

```
原始载体(邮件/文件/会议)
   │  ingestion_job.source_type + source_id (可重跑)
   ▼
extraction_result(candidate_type, candidate_json, info_nature=AI_INFERENCE, confidence)
   │
   ▼
review_queue
   ├─ decision=ACCEPT_AS_NEW → 新建 issue/entity/risk…
   ├─ decision=MERGE_TO(target_entity_id) → 写入 entity_relationship(synonym/merge,
   │     confirm_status, source_reference_id=合并判据) + 在 extraction_result 标记 merged
   └─ decision=REJECT → extraction_result.status=REJECT，保留（供追溯）
```

**合并链不丢**：`review_queue.extraction_result_id → extraction_result.id` 与 `review_queue.target_entity_id` 联合 `entity_relationship.source_reference_id` 构成完整可回放链；任一候选被合并/拒绝都在表中留痕，历史可溯源（ADR-2）。

---

## 5. 去重与防重复（B.5）

1. 摄入时 AI 抽取 → 进 `review_queue`，**未经确认绝不自动落正式实体**（杜绝污染）。
2. 人工确认时系统实时候选检索：`entity_alias_fts`/`entity_fts`(trigram) + 同名/近义 → `review_queue.suggested_entity_id` 提示"可能已存在"。
3. 人工选"合并"→ 并入已有实体，记 `entity_relationship`；新建则走 ACCEPT_AS_NEW。
4. `issue.ref_no` / `entity_identifier(id_type,identifier)` 唯一约束提供硬兜底。

---

## 6. 审计与一致性

- 任何来源写入、合并、确认操作写 `audit_log`（actor_type=USER/AI，before/after）。
- 摄入重跑：`ingestion_job.re_runnable` 幂等；同名来源经 `sha256`/`source_id` 判定并入不重复创建。
- 一致性由 "摄入后自检脚本 + 软删除过滤 + 应用层权限" 三保险，本阶段不引入外键级联复杂化。

---

## 7. 待确认（本规范后续依赖）

- 邮箱正文授权的读取边界与脱敏粒度（D.2-1）。
- 外部企业编码/ERP 编号映射协议（D.2-4）——`entity_identifier.source_from` 的真实来源清单。
- 知识沉淀判定细则（D.2-6）。