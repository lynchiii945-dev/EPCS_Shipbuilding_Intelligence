# Phase1.2 版本及历史管理规范

> 落实 G4（版本化）、B.7（基线只读）、问题 9（完整历史）。本规范定义：版本容器、只读基线、软删除/归档/物理删除三层语义、状态机历史、历史回放。

---

## 1. 三类可版本化对象与策略

| 对象 | 版本机制 | 内容防伪 | 唯一键 |
|---|---|---|---|
| Document 文档 | `document_version` | sha256 | (document_id, version_no) |
| Drawing 图纸 | `drawing_version` | sha256 + revision | (drawing_id, revision) |
| Plan 计划（含滚动预测） | `plan_version`(is_forecast) + `baseline_version` | content_hash | (plan_id, version_no) |
| Knowledge 知识 | `knowledge_version` | sha256 | (knowledge_item_id, version_no) |
| 状态机（issue/risk/task） | `*_status_history`（追加） | —（时间戳） | — |

**统一原则**：每类对象一张"主表 + 一张版本/历史表"，版本号序列在对象内递增。

## 1. 版本化统一原则（精要）

- **主表**只存当前/权威态；**版本表**存历史快照（`version_no + sha256 + snapshot_json`）。
- 版本一旦发布即**不可改写**；变更 = 新增一个新版本，而非覆盖历史版本（只增不改 P3）。
- 内容 hash（sha256/content_hash）用于去重与防伪；snapshot_json 渐进承载（先记录`assets/`文件，全量快照可后续按需补，ADR-9 权衡）。
- 版本记录与来源 `source_reference` 关联，保证"哪个版本来自哪个来源"。

---

## 2. 基线只读（B.7 / OQ-3）

- `baseline_version.approved_at` 填充即视为**已批准只读**：`is_readonly=1`。
- 三重防御：**BEFORE UPDATE/DELETE 触发器**（`RAISE(ABORT)`）+ **应用层拦截** + **AuditLog 记录强制/受权操作**。
- AI/自动化**只可新增**新的 `plan_version`（is_forecast=1 的滚动预测），**禁止改写**已批准基线。
- 一切偏差以 `progress_record`（实际）vs 基线表达，而非改基线。
- 基线变更仅允许**人工权力操作**：走 AuditLog + 变更授权（D.2 角色清单落定前由应用层白名单控制）。

---

## 3. 软删除 / 归档 / 物理删除 三层语义

| 状态 | `is_deleted` | `del_status` | 查询可见 | 说明 |
|---|---|---|---|---|
| 正常 | 0 | ACTIVE | 可见 | — |
| 归档 | 0 | ARCHIVED | 仅归档视图 | 不参与日常业务，可还原 |
| 软删除 | 1 | DELETED | 默认隐藏 | `deleted_at` 记录；可还原（审计） |
| 物理删除 | — | — | — | **仅对临时/草稿/摄入缓存表允许**；正式表由触发器禁止 |

- 数据库实现多采用 `is_deleted`（布尔）+ `del_status`（枚举）双列，查询 `WHERE is_deleted=0`。
- 软删除非简单删行：需在 `audit_log` 记 before/after，Front 默认过滤。
- 正式记录（issue/risk/task/decision/document/drawing/knowledge_item/entity/baseline/plan）**默认禁物理删除**（触发器拦截）。

---

## 4. 状态机历史（B.6 落地）

- issue/risk/task 各配 `*_status_history`：`old_status→new_status`、`transition`、`changed_by/at`、`reason`、`reopen_count`。
- 合法转移（产品已锁定）：
  - `NEW → TRIAGING → CONFIRMED → ASSIGNED → IN_PROGRESS → PENDING_VERIFICATION → CLOSED`
  - 退回：`TRIAGING→NEW`（证据不足）、`PENDING_VERIFICATION→IN_PROGRESS`（验证不通过）
  - 重开：`CLOSED→ASSIGNED/IN_PROGRESS`，`reopen_count+1`，记录 reason
- 非法转移由应用层拒绝；历史表只追加、不覆盖。每次流转写 `source_reference` 指向证据（如验证证据）。

---

## 5. 历史回放

- 任一业务对象当前态 = 最新版本/最新状态；历史 = 版本表/历史表按时间序列。
- 跨阶段（E/P/C/S）跟踪（问题 11）：对象生命周期以 `object_dimension_tag`(EPCS_PHASE) 随进展**追加标签**表达，不覆盖历史阶段；"阶段不确定/跨阶段"以 `value_text` 自由值并列表达（B.2）。

---

## 6. 待确认

- 计划 L1~L4 规范与周期（D.2-5）。
- 知识沉淀判定（D.2-6）。
- 快照粒度（全量 vs 增量资产）——ADR-9 已给推荐，仍需人工确认成本边界。