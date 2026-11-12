# Phase1.2 版本及历史管理规范

> R1 整改同步：2026-11-12，以《Phase1.2_数据库表结构设计.md》(R1) 为唯一真值源
> 落实 G4（版本化）、B.7（基线只读）、问题 9（完整历史）。本规范定义：版本容器、只读基线、软删除/归档/物理删除三层语义、状态机历史、历史回放。

---

## 1. 三类可版本化对象与策略（R1 补齐）

| 对象 | 版本机制 | 内容防伪 | 唯一键 | R1 变更 |
|---|---|---|---|---|
| Document 文档 | `document_version` | sha256 | (document_id, version_no) | **索引全部历史版本**（`document_version_fts`） |
| Drawing 图纸 | `drawing_version` | sha256 + revision | (drawing_id, revision) | **索引全部历史版本**（`drawing_version_fts`） |
| Meeting 会议纪要 | `meeting_minutes`（可多版） | —（时间戳） | (meeting_id, version_no) | **R1 补齐版本对象；全部历史版本入 `meeting_minutes_fts`** |
| Plan 计划（含滚动预测） | `plan_version`(is_forecast) + `baseline_version` | content_hash | (plan_id, version_no) | `baseline_version.plan_version_id` 指向完整计划版本 |
| 计划活动 | `plan_activity`（稳定主实体）+ **`plan_activity_version`** | content_hash | (activity_id, plan_version_id) | **R1-2 新增：每版本活动属性快照，`change_type` ∈ ADDED/MODIFIED/UNCHANGED/REMOVED** |
| 基线状态切换 | **`plan_active_baseline`** + **`baseline_switch_log`** | —（授权 + 审计） | plan_id（PK / 部分唯一） | **R1-1 新增：状态分离 + 切换全历史** |
| Knowledge 知识 | `knowledge_version` | sha256 | (knowledge_item_id, version_no) | **索引全部历史版本**（`knowledge_version_fts`） |
| 状态机（issue/risk/task） | `*_status_history`（追加） | —（时间戳） | — | — |

**统一原则**：每类对象一张"主表 + 一张版本/历史表"，版本号序列在对象内递增。

**「文件/计划版本」与「业务事项版本」区分（R1-2 / 补充 ADR-9）**：
- **文件/计划版本**：`document_version` / `drawing_version` / `plan_version` / `plan_activity_version` / `knowledge_version` / `meeting_minutes` 六类，以「主表 + 版本快照表」逐版本留存，`version_no` 递增、只增不改；**FTS 索引全部历史版本**（每个版本一行，`biz_id`=版本 UUID、`owner_biz_id`=主表 UUID），**不是仅当前版本**（对应 24 张 FTS 中的历史版本表，见《表结构设计》§7.2）。
- **业务事项版本**：Issue/Risk/Task/Decision/KnowledgeItem 不另设版本表，其"版本/历史"由 `business_subject`（统一事项主档 + `canonical_subject_id` 指针）+ `*_status_history`（状态历史）+ `business_subject_merge`（**可逆合并**，`undone_at / undone_by / undo_reason / is_active=0`）三者共同承载。
- **基线切换历史**：`baseline_switch_log` 记录每次 from/to、授权人、时间、理由、`audit_log_id`；`plan_active_baseline` 为当前生效指针。

## 1. 版本化统一原则（精要）

- **主表**只存当前/权威态；**版本表**存历史快照（`version_no + sha256 + snapshot_json`）。
- 版本一旦发布即**不可改写**；变更 = 新增一个新版本，而非覆盖历史版本（只增不改 P3）。
- 内容 hash（sha256/content_hash）用于去重与防伪；snapshot_json 渐进承载（先记录`assets/`文件，全量快照可后续按需补，ADR-9 权衡）。
- 版本记录与来源 `source_reference` 关联，保证"哪个版本来自哪个来源"。
- `plan_activity_version` 除属性快照外带 `change_type`，用于活动增删改历史与 V1/V2 差异对比（R1-2）。

---

## 2. 基线只读（B.7 / OQ-3，R1-1 整段重写）

> **【原结论作废】** 原 §2 只写「`baseline_version.is_readonly` 触发器 + `is_active` 字段 + 三重防御」。该设计含四条致命缺陷（《整改记录》§1.2）：`UNIQUE(plan_id,is_active)` 使一个计划最多 2 条基线；状态与内容同表，改 `is_active` 即绕过内容只读；触发器条件只拦"is_active 未变"的更新、等于放行所有含 is_active 变更的更新；切换无授权人/审计。整段作废，以下为 R1 整改版。

### 2.1 状态与内容彻底分离
- **删除** `UNIQUE(plan_id, is_active)` 约束与 `baseline_version.is_active` 字段（同一计划可保留多条历史批准基线）。
- 新增 **`plan_active_baseline`**（`plan_id` 为主键 + `baseline_version_id` + `switched_at / switched_by / authorization_ref / reason`），作为「当前生效基线」指针；部分唯一索引 `uq_pab_active ON plan_active_baseline(plan_id) WHERE is_active=1` 保证「同一计划最多一个当前生效基线」。
- 新增 **`baseline_switch_log`**：记录每次切换的 `from_baseline_id / to_baseline_id`、`switched_by`、`switched_at`、`authorization_ref`、`reason`、`audit_log_id`，构成切换全历史。

### 2.2 `baseline_version` 全字段冻结（无差别拦截）
- `trg_bl_freeze_u BEFORE UPDATE ON baseline_version WHEN OLD.is_readonly=1 → RAISE(ABORT, 'baseline frozen: content immutable')`
- `trg_bl_freeze_d BEFORE DELETE ON baseline_version WHEN OLD.is_readonly=1 → RAISE(ABORT, 'baseline frozen: physical delete disabled')`
- 两个触发器 **不判断任何字段**，对 `baseline_version` 的 UPDATE / DELETE **无差别**拦截；`is_readonly` 恒为 1（`CHECK(is_readonly=1)`），`is_active` 字段已整体移除，**不允许通过改状态字段绕过内容只读**。
- `baseline_version.plan_version_id` 明确指向一个完整计划版本（含完整活动集）；批准基线时其 plan_version 须拥有 ≥1 条 `plan_activity_version` 且活动集无 `REMOVED`（迁移后自检 SQL 校验）。

### 2.3 切换流程（应用层单事务）
1. 校验目标基线属于该 `plan` 且已批准（`approved_at` 非空）；
2. 写 `baseline_switch_log` + `audit_log`（`actor_type='USER'`、授权引用）；
3. `UPSERT plan_active_baseline`（更新当前生效指针）；
4. **全程不触碰 `baseline_version` 任何行**——状态变更与内容存储彻底解耦。

### 2.4 AI / 自动化写入边界（G5 / OQ-3 四层防御）
- AI/自动化 **仅允许 INSERT `plan_version(is_forecast=1)`**（滚动预测，`info_nature=PREDICTION/PROPOSAL`，由 CHECK 强制）；**禁止改写**任何已批准基线。
- `baseline_version` 的 INSERT 与切换操作要求 `actor_type='USER'` 且 `authorization_ref` 非空，并写 `audit_log`。
- 四层防御：状态分离 + `baseline_version` 无差别冻结触发器 + 应用层写入白名单 + AuditLog 授权审计（原「触发器 + 应用层 + 审计」三重防御细化，修订 ADR-8）。
- 一切偏差以 `progress_record`（实际）对照基线表达，而非改基线。

### 2.5 基线只读 6 个测试案例（实测全 PASS，《表结构设计》§2.4）
| # | 案例 | 结果 |
|---|---|---|
| 1 | 同一 plan 插入两条历史批准基线 B1/B2（不同 baseline_no、不同 plan_version_id） | PASS（2 行共存） |
| 2 | 第二条基线 B2 生效（写 `baseline_switch_log` + UPSERT `plan_active_baseline`，不触碰 `baseline_version`） | PASS（生效 = B2） |
| 3 | 第一条基线 B1 内容不可改（`UPDATE ... SET content_hash='HACK'` / 改 `approved_at`） | PASS（`baseline frozen: content immutable`） |
| 4 | 任何基线物理删除被阻止（`DELETE FROM baseline_version`） | PASS（`physical delete disabled`） |
| 5 | 同计划不能有两个生效基线（再插一条 `plan_active_baseline(P1, ...)`） | PASS（UNIQUE 约束拦截） |
| 6 | 不同计划各有一个生效基线（P1/B2、P2/B3，B3 可复用同 `baseline_no='BL-01'`） | PASS（2 行） |

### 2.6 计划版本回放、差异对比与当前预测对比
- **历史批准计划回放**：`baseline_version → plan_version → plan_activity_version`（按 `change_type <> 'REMOVED'` 取完整活动集）。
- **V1/V2 差异对比**：对 `plan_activity_version` 按 `activity_id` 做**全外连接**（SQLite 以 LEFT JOIN + 反向 UNION 模拟）属性比对，叠加 `change_type` 定位增删改。
- **当前滚动预测 vs 批准基线**：`plan_version(is_forecast=1)` 预测版 与 `plan_active_baseline` 指向的批准版本对比。
- **活动增删改历史**：按 `(plan_version_id, change_type)` 聚合 `plan_activity_version`。

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

### 3.1 FTS 索引的删除语义（R1-3 补充）
- **软删保留 FTS 行**：软删时同步触发器只把 FTS 行的 `is_deleted` 镜像置 1，**不物理删除 FTS 行**（避免误删历史版本索引）；所有检索统一带 `AND is_deleted=0` 并 JOIN 业务表二次过滤。
- **归档（ARCHIVED）不改动 FTS**：归档仅改业务表 `del_status`，FTS 行保持 `is_deleted=0`，仍可被检索。
- **正式表禁物理删除触发器覆盖 20 张**：`project, project_phase, organization, person, plan, plan_version, email, document, drawing, meeting, message, issue, risk, task, decision, action_measure, entity, business_subject, knowledge_item, evidence`；`baseline_version` 与 `extraction_result` 各用**专用保护触发器**（`trg_bl_freeze_d` / `trg_er_immutable_d`），不重复计入。正式表物理删除被拦截时，`AFTER DELETE` FTS 同步触发器不会触发。
- 软删 FTS 行「保留 + 过滤」的最终取舍仍列为待确认 N4。

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
- 跨阶段（E/P/C/S）跟踪（问题 11）：对象生命周期以 `object_dimension_tag`(EPCS_PHASE) 随进展**追加标签**表达，不覆盖历史阶段；"阶段不确定/跨阶段"以 `value_text` 自由值并列表达（B.2）。R1-6 已为 `object_dimension_tag` 增加 `value_type` 强约束（`REF` 须有 `value_id` 且 `value_text` 为空；`FREE_TEXT` 反之）。
- 计划版本级回放见 §2.6。

---

## 6. 待确认

- 计划 L1~L4 规范与周期（D.2-5）。
- 知识沉淀判定（D.2-6）。
- 快照粒度（全量 vs 增量资产）——ADR-9 已给推荐，仍需人工确认成本边界。
- **R1 新增待确认（《架构评审整改记录》§10 / 《待确认事项清单》§2）**：
  - **N1 / N2**：基线切换的授权角色与审批流（依赖 D.2-2 角色清单）、切换日志/审计留存期。
  - **N3**：短词检索 LIKE 回退的性能阈值与候选集范围；二期是否物化 `short_term_index`。
  - **N4**：软删 FTS 行「保留 + 过滤」vs「移除」的最终取舍（本轮定保留，需实测容量后确认）。
  - **N5**：全部历史版本入 FTS 的存储放大评估。
  - **N10**：`plan_activity_version` 工作量单位（`workload_qty / workload_unit`）与进度口径（`progress_measure`）标准。

---

## R1 整改同步说明

本轮依据《Phase1.2_数据库表结构设计.md》(R1，唯一真值源) 与《Phase1.2_架构评审整改记录.md》(R1) 做定向修订：

- **统一统计口径**：实体表 **75**（业务主表 46 + 辅助 29）、FTS5 虚拟表 **24**、触发器 **96**、视图 **0**。
- **§1 补齐版本对象表**：新增 `plan_activity_version`（`change_type` ADDED/MODIFIED/UNCHANGED/REMOVED）、`meeting_minutes` 版本、`baseline_switch_log`；明确 `document_version` / `drawing_version` / `knowledge_version` 等**索引全部历史版本**（非仅当前版本）；区分「文件/计划版本」与「业务事项版本」（后者由 `business_subject` + 状态历史 + 可逆合并承载）。
- **§2 整段作废重写（R1-1/R1-2）**：删除 `UNIQUE(plan_id,is_active)` 与 `is_active` 字段；新增 `plan_active_baseline` 状态分离 + `baseline_switch_log` 切换全历史；`trg_bl_freeze_u/d` 无差别全字段冻结；切换为应用层单事务、全程不触碰 `baseline_version`；AI 仅允许 INSERT `plan_version(is_forecast=1)`；补六个基线测试案例（全 PASS）与 `baseline → plan_version → plan_activity_version` 回放、V1/V2 差异对比。
- **§3 补充**：FTS 软删规则（保留 FTS 行、仅置 `is_deleted` 镜像、`AND is_deleted=0` + JOIN 二次过滤；归档不改动 FTS）、正式表禁物理删除触发器覆盖 20 张（`baseline_version` / `extraction_result` 各用专用触发器）。
- **§6 补充**：R1 新增待确认 N1/N2、N3~N5、N10 的索引说明。
- **边界**：本阶段未创建/执行任何 SQL 迁移、未改数据库、未装 SDK、未接入外部渠道、未读取真实邮件或旧知识库数据；当前状态为等待系统架构师再次审核。
