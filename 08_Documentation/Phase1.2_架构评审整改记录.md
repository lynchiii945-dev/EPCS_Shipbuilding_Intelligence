# Phase1.2 架构评审整改记录（R1）

> 项目：EPCS Shipbuilding Intelligence
> 任务：基于系统架构师初审意见（六项建表阻断问题 + 一致性问题）对 Phase 1.2 设计做**定向整改**
> 日期：2026-11-12
> 前置：Phase 1.2 八份设计文档（Git `cc3168d`）→ 初审「总体方向认可、六项阻断」→ 本轮整改
> 边界：**只修改设计文档**；未创建 `migrations/001_init.sql`、未执行任何 CREATE TABLE、未修改 `epcs_intelligence.db`、未导入数据、未安装 SDK、未连接外部账号

---

## 0. 整改总览

| # | 评审问题 | 原设计缺陷（摘要） | 整改方案（摘要） | 影响 ADR | 新增待确认 |
|---|---|---|---|---|---|
| R1-1 | 批准基线只读保护 | `UNIQUE(plan_id,is_active)` 错误约束（一个计划最多 2 条基线）；`is_active` 与内容同表；触发器允许改 is_active 即绕过内容只读；无切换授权/审计 | 删除错误约束；新增 `plan_active_baseline` 状态分离表 + `baseline_switch_log` 授权审计；`baseline_version` 全字段冻结（BEFORE UPDATE/DELETE 无差别拦截）；部分唯一索引落在状态表 | **修订 ADR-8** | 切换授权角色、切换审计留存期 |
| R1-2 | 计划活动版本化 | `plan_activity` 只挂 `plan`，无版本快照，历史无法回放 | `plan_activity` 降为稳定主实体；新增 `plan_activity_version`（每版本属性快照）；`activity_dependency` 增 `plan_version_id`；`baseline_version` 明确指向完整计划版本 | **修订 ADR-8 / 补充 ADR-9** | 工作量口径、依赖版本化粒度 |
| R1-3 | FTS5 trigram 统一 | 混用外部内容表与普通内容表；数据字典 `content_rowid='id'` 用 TEXT UUID（致命错误）；`document_fts(name,snapshot_json)` 等索引了业务表中不存在的列；无短词方案 | 统一**普通内容表 + biz_id UNINDEXED 显式映射**范式；一一对应内容表；索引全部历史版本；三向触发器；软删保留+查询过滤；重建与一致性检查 SQL；短词 LIKE 回退 + alias 补充 | **修订 ADR-7 / ADR-7b** | 软删 FTS 行策略、短词召回口径、存储放大评估 |
| R1-4 | Entity 与业务事项归一 | 原 ADR-6 把「同一问题」的合并交给 `entity_relationship`，业务实体与业务事项混淆；Issue 无别名、无可逆合并 | 新增 `business_subject` 统一事项主档 + `business_subject_alias` + `business_subject_merge`（可逆合并）+ `business_subject_source`；`entity_relationship` 仅管业务实体 | **修订 ADR-6**（原结论作废） | 撤销后引用重指向、subject_kind 扩展流程 |
| R1-5 | ReviewQueue 审核结果链 | 单 `extraction_result_id`/单 `decision`/单 `target_entity_id`，无法拆分、合并、多类型目标；无审核人/理由/证据；原抽取记录可被覆盖 | 拆为 `review_queue`（任务）+ `review_extraction_link`(M:N) + `review_decision`（结果明细，含审核人/时间/理由/证据）+ `review_result_object`（→正式对象稳定映射）；`extraction_result` 原始字段冻结触发器 | **修订 ADR-6 / ADR-7** | 审核对象类型枚举扩展流程 |
| R1-6 | 字典/ER/SQL 一致性 | `department` 表缺失；两处 FK 未建；`project_member` NULL 唯一性漏洞；`action_measure` 无完整性；`object_dimension_tag` 无值约束；`entity_identifier`/`drawing_no` 唯一范围过宽；多态引用无自检；公共字段不齐；数量描述不一致 | 逐项整改 DDL；新增 `sp_check_polymorphic_refs` 自检策略；公共字段基线 A/B 逐表标注；重新统计并统一 8 份文档数量 | **修订 ADR-1/2/3/4/5/12** | department 与 organization 职责边界、公共字段裁剪 |

**额外架构检查（任务书 §三）10 项**逐项结论见 §8；**质量验收 10 项**逐项结论见 §9。

---

## 1. R1-1 批准基线只读保护

### 1.1 原设计
```sql
CREATE TABLE baseline_version (
  ..., is_active INTEGER NOT NULL DEFAULT 0, is_readonly INTEGER NOT NULL DEFAULT 1,
  UNIQUE(plan_id, baseline_no),
  UNIQUE(plan_id, is_active));                    -- 错误：一个 plan 最多 2 条基线
CREATE UNIQUE INDEX idx_baseline_active ON baseline_version(plan_id) WHERE is_active=1;

CREATE TRIGGER trg_baseline_ro_update BEFORE UPDATE ON baseline_version
WHEN OLD.is_readonly = 1 AND (NEW.is_active <> OLD.is_active) IS 0   -- 只看 is_active 是否变化
BEGIN SELECT RAISE(ABORT, 'baseline is read-only'); END;
```

### 1.2 评审问题（四条致命）
1. `UNIQUE(plan_id,is_active)`：is_active 只有 0/1，一个计划**最多 2 条基线**，直接违反「多个历史批准基线」；且与后面的部分唯一索引语义重复。
2. **状态与内容同表**：要切换当前基线就必须 `UPDATE baseline_version SET is_active=...`，触发器一旦放行这个 UPDATE，就无法阻止同一语句顺带改 `plan_version_id`/`approved_at` 等内容字段 —— 评审明确指出的「允许修改 is_active 就能绕过内容只读保护」。
3. 触发器条件 `(NEW.is_active <> OLD.is_active) IS 0` 语义诡异（NULL 参与比较时行为不确定），且只拦截"is_active 未变"的更新，等于**放行所有含 is_active 变更的更新**。
4. 基线切换无独立机制、无授权人、无审计记录；AI 与人工写入没有约束边界。

### 1.3 修改方案（方案对比）
| 方案 | 做法 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| A 状态分离（推荐） | 当前生效指针移到独立表 `plan_active_baseline`，`baseline_version` 完全无可变字段 | 内容与状态彻底解耦；基线表可无差别全字段冻结；切换天然带授权/审计 | 多一张表、切换需事务 | ✅ 采用 |
| B 保留 is_active + 列级触发器 | 触发器逐字段比对，只允许改 is_active | 表少 | 列多易漏；新增字段即破防；仍属"放行 UPDATE" | ❌ 不采用 |
| C 纯应用层 | 不使用触发器 | 灵活 | 无数据库层强约束，违反 OQ-3 三重防御 | ❌ 不采用 |

### 1.4 修改后的设计（要点，DDL 全文见《数据库表结构设计》§2）
- 删除 `UNIQUE(plan_id, is_active)` 与 `baseline_version.is_active` 字段。
- `baseline_version` 保留 `UNIQUE(plan_id,baseline_no)`，新增 `UNIQUE(plan_id,plan_version_id)`、`approved_at/approved_by/content_hash`、`is_readonly=1 CHECK(is_readonly=1)`。
- 新增 `plan_active_baseline(plan_id PK, baseline_version_id FK, is_active=1, switched_at, switched_by, authorization_ref, reason)`；**部分唯一索引** `CREATE UNIQUE INDEX uq_pab_active ON plan_active_baseline(plan_id) WHERE is_active=1;` 保证「同一计划最多一个当前生效基线」，`plan_id` 为 PK 亦保证之。
- 新增 `baseline_switch_log`（切换全历史：from/to、授权人、时间、理由、audit_log_id），每次切换必写。
- 触发器（无差别、不看任何字段）：
  - `trg_baseline_freeze_update BEFORE UPDATE ON baseline_version WHEN OLD.is_readonly=1 → RAISE(ABORT)`
  - `trg_baseline_freeze_delete BEFORE DELETE ON baseline_version WHEN OLD.is_readonly=1 → RAISE(ABORT)`
- 切换流程（应用层单事务）：校验目标基线属于该 plan 且已批准 → 写 `baseline_switch_log` + `audit_log` → UPSERT `plan_active_baseline`；**全程不触碰 baseline_version 任何行**。
- AI/自动化约束：仅允许 INSERT `plan_version(is_forecast=1)`；`baseline_version` 的 INSERT/切换操作要求 `actor_type='USER'` 且 `authorization_ref` 非空，写入 `audit_log`。

### 1.5 六个测试案例
详见《数据库表结构设计》§2.4（含可运行 SQL 与实测结果）：①插两条历史批准基线 ②第二条生效 ③第一条内容仍不可改 ④任何基线物理删除被阻止 ⑤同计划不能有两个生效基线 ⑥不同计划各有一个生效基线。

### 1.6 ADR 影响
**修订 ADR-8**：原「`is_active` 部分唯一索引 + 只读触发器」表述作废，改为「状态分离 + 切换日志 + 无差别冻结 + 三重防御」。`OQ-3` 结论从「触发器+应用层+审计」细化为四层（含状态分离）。

---

## 2. R1-2 计划版本与活动版本关联

### 2.1 原设计
`plan_activity(id, plan_id, code, name, ... planned_start/end, status)` 只挂 `plan`；`activity_dependency` 也只挂 `plan`；`baseline_version.plan_version_id` 指向的 `plan_version` 只有 `snapshot_json`（无结构化活动集）→ **V1/V2 无法对比、历史批准计划无法回放**。

### 2.2 评审问题
- 无 `plan_version_id`，活动属性随版本变更被覆盖（违反 G4 / P3 只增不改）。
- `baseline_version` 不能明确指向「一个完整的计划版本」（活动集缺失）。
- 缺活动新增/删除/修改历史。

### 2.3 修改方案（方案对比）
| 方案 | 做法 | 结论 |
|---|---|---|
| A 主实体+版本快照（推荐） | `plan_activity` 稳定主实体；`plan_activity_version` 存每版本属性快照 | ✅ 采用（评审优先评估项） |
| B 活动直接挂版本 | 每版本复制全部活动行，无稳定 id | ❌ 跨版本同一活动无法追踪 |
| C 全量 JSON 快照 | 只扩 `snapshot_json` | ❌ 无法 SQL 对比与索引 |

### 2.4 修改后的设计
- `plan_activity`：稳定主实体（id, plan_id, code, created_at, is_deleted）；不再存版本可变属性。
- `plan_activity_version`：**每版本活动属性快照**
  - `id, activity_id FK→plan_activity, plan_version_id FK→plan_version`
  - 名称/编码、责任组织 `owner_org_id`、责任人 `owner_person_id`、专业/区域/系统 `discipline_id/area_id/system_id`
  - 计划起止 `planned_start/planned_end`、前置关系（见下）、工作量 `workload_qty/workload_unit`、进度口径 `progress_measure`
  - `is_milestone, change_type(ADDED/MODIFIED/UNCHANGED/REMOVED), content_hash, snapshot_json, created_at`
  - `UNIQUE(activity_id, plan_version_id)`；索引 `(plan_version_id)`、`(plan_version_id, change_type)`
- `activity_dependency`：增 `plan_version_id FK→plan_version`，`UNIQUE(plan_version_id, predecessor_id, successor_id, relation_type)`；版本内前后置。
- `baseline_version.plan_version_id` 明确指向完整计划版本；新增**一致性约束检查**：批准基线时，其 plan_version 必须拥有 ≥1 条 `plan_activity_version` 且 all `change_type != 'REMOVED'` 的活动集完整（由迁移后自检 SQL 校验）。
- 能力：V1/V2 差异对比（`change_type` + 全外连接属性比对）、历史批准计划回放（按 baseline→plan_version→plan_activity_version）、当前滚动预测 vs 批准基线对比、活动增删改历史（change_type 序列）。
- `progress_record` 增 `plan_version_id`（可选）以明确进度所对照的版本口径。

### 2.5 ADR 影响
**修订 ADR-8**（基线明确指向完整版本）；**补充 ADR-9**（版本容器纳入 `plan_activity_version`，并明确"业务事项版本"由 `business_subject` 与状态历史承载，与"文件/计划版本"区分）。

---

## 3. R1-3 FTS5 trigram 统一设计

### 3.1 原设计缺陷（逐条）
1. **混用两种范式且未说明同步**：`issue_fts` 用外部内容表 `content='issue', content_rowid='rowid'`，其余 11 张用普通内容表，却只给了 `issue` 的触发器示例。
2. **致命错误**：《核心实体数据字典》§7.2 写 `content_rowid='id'`，而 `id` 是 TEXT UUID —— SQLite FTS5 外部内容表的 `content_rowid` **必须是整数 rowid**，`content='issue', content_rowid='id'` 建表即失败。
3. **索引列错配**：`document_fts(name, snapshot_json)` 中 `snapshot_json` 属于 `document_version` 不属于 `document`；`meeting_fts(title, content_md)` 的 `content_md` 属于 `meeting_minutes`；`knowledge_fts(title, content_md)` 的 `content_md` 属于 `knowledge_version`；`drawing_fts` 未覆盖 `drawing_version`。外部内容表要求列名与主表严格对应，原草案根本无法建。
4. 未定义：rowid↔UUID 映射、索引当前/全部版本、同步机制、软删处理、重建/一致性检查、查询如何返回稳定业务 ID。
5. 无中文检索测试；trigram 对 1~2 字短词的行为未验证、无补充方案。

### 3.2 修改方案（范式定案）
**统一采用「普通内容表（contentful FTS5）+ biz_id 显式映射」**，全库不再使用外部内容表（消除 `content_rowid` 整数约束与 `'delete'` 命令同步的复杂度，且避免混用）。

```sql
-- 统一范式（每张 FTS 表相同结构）
CREATE VIRTUAL TABLE issue_fts USING fts5(
    biz_id UNINDEXED,          -- TEXT UUID：稳定业务对象 ID（不参与分词）
    owner_biz_id UNINDEXED,    -- 版本表专用：指向主表 UUID
    is_deleted UNINDEXED,      -- 软删镜像，查询过滤用
    title, description_md,
    tokenize = 'trigram');
```
- **FTS rowid 与 UUID 映射方式**：不再用 `content_rowid` 做映射；FTS 表自身 rowid 为整数自增，业务 UUID 通过 `biz_id UNINDEXED` 列显式携带。同步触发器用 `WHERE biz_id = old.id` 定位（普通内容表可直接 DELETE/UPDATE 行），无需维护 rowid↔UUID 映射表。
- **查询返回稳定业务对象 ID**：`SELECT biz_id, owner_biz_id, snippet(...) FROM x_fts WHERE x_fts MATCH ? AND is_deleted=0`，再按 `biz_id` 回业务表取完整对象。版本类 FTS 另返回 `owner_biz_id` 聚合到主对象。

### 3.3 内容表 ↔ FTS 表一一对应（全量清单，含「索引全部历史版本」决策）
| # | 业务表（承载文本的表） | FTS 表 | 索引列 | 索引范围 |
|---|---|---|---|---|
| 1 | `email` | `email_fts` | subject, body_markdown | 当前记录 |
| 2 | `email_attachment` | `email_attachment_fts` | filename | 当前记录 |
| 3 | `document` | `document_fts` | name, doc_code | 主表元数据 |
| 4 | `document_version` | `document_version_fts` | extracted_text, notes, snapshot_json | **全部历史版本** |
| 5 | `drawing` | `drawing_fts` | name, drawing_no | 主表元数据 |
| 6 | `drawing_version` | `drawing_version_fts` | revision, extracted_text, notes | **全部历史版本** |
| 7 | `meeting` | `meeting_fts` | title, transcript_text | 当前记录 |
| 8 | `meeting_minutes` | `meeting_minutes_fts` | version_no, content_md | **全部历史版本** |
| 9 | `message` | `message_fts` | content_md | 当前记录 |
| 10 | `evidence` | `evidence_fts` | title, body | 当前记录 |
| 11 | `source_reference` | `source_reference_fts` | context_excerpt, locator | 当前记录 |
| 12 | `issue` | `issue_fts` | ref_no, title, description_md | 当前记录 |
| 13 | `risk` | `risk_fts` | ref_no, title, description_md | 当前记录 |
| 14 | `task` | `task_fts` | ref_no, title, description_md | 当前记录 |
| 15 | `decision` | `decision_fts` | ref_no, title, conclusion_md | 当前记录 |
| 16 | `action_measure` | `action_measure_fts` | ref_no, name, description | 当前记录 |
| 17 | `entity` | `entity_fts` | name | 当前记录 |
| 18 | `entity_alias` | `entity_alias_fts` | alias | 当前记录 |
| 19 | `business_subject_alias` | `business_subject_alias_fts` | alias | 当前记录 |
| 20 | `knowledge_item` | `knowledge_item_fts` | title, summary | 主表元数据 |
| 21 | `knowledge_version` | `knowledge_version_fts` | version_no, content_md | **全部历史版本** |
| 22 | `plan_activity_version` | `plan_activity_version_fts` | name, code | **全部历史版本** |
| 23 | `extraction_result` | `extraction_result_fts` | candidate_json, raw_text | 当前记录 |
| 24 | `review_decision` | `review_decision_fts` | reason | 当前记录 |

> 决策：**索引全部历史版本**（每条版本记录一行 FTS 行，`biz_id`=版本 UUID、`owner_biz_id`=主表 UUID），满足评审「历史版本检索」测试；主表另建元数据 FTS，避免把名称重复写进每个版本行。

### 3.4 同步 / 软删 / 重建 / 一致性（7 点要求逐条回应）
1. **每个 FTS 表索引哪个业务表** → §3.3 一一对应表。
2. **当前版本 or 全部历史版本** → 全部历史版本（版本类）+ 主表元数据；不索引"仅当前版本"。
3. **FTS rowid 与 UUID 映射** → 不依赖整数 rowid 映射；`biz_id UNINDEXED` 显式携带业务 UUID；`owner_biz_id` 指向主对象。
4. **INSERT/UPDATE/DELETE 同步** → 每张内容表 3 个触发器（`AFTER INSERT` / `AFTER UPDATE WHEN 文本字段变化` / `AFTER DELETE`）；UPDATE 采用「先 DELETE 旧 FTS 行再 INSERT 新行」避免 trigram 下的值漂移；软删用 `UPDATE ... SET is_deleted=1` 镜像（见下）。
5. **软删除后如何处理索引** → **保留 FTS 行**，`is_deleted` 置 1；查询统一带 `AND is_deleted=0` 并 JOIN 主表二次过滤；不物理删 FTS 行（避免误删历史版本）。归档（ARCHIVED）不改动 FTS。
6. **索引重建与一致性检查** → 重建 `DELETE FROM x_fts; INSERT INTO x_fts(...) SELECT ... FROM 业务表 WHERE is_deleted=0;`；一致性检查 SQL：①活跃业务行数 vs FTS 活跃行数差 ②`biz_id` 孤儿检查 ③`is_deleted` 镜像一致性 ④trigram 正向自检（已知样本必须命中，防止核验脚本自身失效）。
7. **FTS 查询如何返回稳定业务对象 ID** → 返回 `biz_id`（+`owner_biz_id`），再回表；禁止把 TEXT UUID 用作 `content_rowid`。

### 3.5 中文检索测试与短词补充
- 测试矩阵（单字/双字/三字/长中文词/中文标点/英文编号/中英混合/特殊字符/历史版本）与逐项命中数见《数据库表结构设计》§7.4（实测）。
- **trigram 短词结论**：trigram 以 3 字符滑窗建索引，1~2 字查询词无法形成有效 token，`MATCH` 不命中（实测）。
- **补充检索方案（第一期够用）**：查询词长度 < 3 时自动降级为 **LIKE 回退**（`WHERE title LIKE '%x%' OR description_md LIKE '%x%'`，限定在候选集/项目范围内并加 `LIMIT`），并联合 `entity_alias` / `business_subject_alias` 别名表做短词等值召回；不新增 ngram 索引表（避免过度设计）。若二期短词检索成为高频，再评估 `short_term_index` 物化表（列入待确认）。

### 3.6 ADR 影响
**修订 ADR-7 / ADR-7b**：原「外部内容表 + 触发器同步」结论作废，改为「统一普通内容表 + biz_id 显式映射 + 三向触发器 + 软删镜像 + LIKE 短词回退」；OQ-7 重新关闭为该结论。

---

## 4. R1-4 Entity 与 Issue/Risk/Task 等业务事项的关系

### 4.1 原设计缺陷
- `entity` 定义为「船/设备/部位/厂商/专业…」等**业务实体**，但 ADR-6 与 ER 图注 4 却把「同一问题在邮件/会议/任务重复出现」也交给 `entity_relationship(synonym/merge)` 归一，并明确写「`issue` 本身不直接自引用合并，一律经 `entity` 归一」。
- 混淆两类语义：`entity_relationship` 表达的是**实体间的语义关系**（同义、整机-部件），不是**两个业务事项其实是同一件事**；用它代替 Issue 合并会导致：Issue 无别名、无来源证据链、无法撤销错误合并、合并后原记录语义丢失。

### 4.2 修改方案（明确分层）
| 层 | 对象 | 表 | 归一机制 |
|---|---|---|---|
| 业务实体（名词） | 设备/船舶/区域/组织/供应商/专业 | `entity` + `entity_alias` + `entity_identifier` + `entity_relationship` | 实体语义关系与别名（**仅此层**） |
| 业务事项（事件） | Issue/Risk/Task/Decision/KnowledgeItem | `business_subject`（统一事项主档）+ 各具体表 `subject_id` | 事项合并/别名/证据（**独立层**） |

### 4.3 修改后的设计
- `business_subject`：`id, project_id, subject_kind(ISSUE/RISK/TASK/DECISION/KNOWLEDGE_ITEM), canonical_subject_id FK→business_subject(id), status(ACTIVE/MERGED/SUPERSEDED), info_nature, created_at...`
- `issue/risk/task/decision/knowledge_item` 各增 `subject_id TEXT NOT NULL UNIQUE REFERENCES business_subject(id)`（1:1）。
- `business_subject_alias`：`subject_id, alias, alias_type, source_reference_id, confirm_status`，UNIQUE(subject_id, alias) → **一个 Issue 多个别名**。
- `business_subject_merge`（**可逆合并链**）：`from_subject_id, to_subject_id, merged_at, merged_by, reason, source_reference_id, undone_at, undone_by, undo_reason, is_active`；撤销错误合并 = 置 `undone_at/undone_by/undo_reason`、`is_active=0`，**不物理删除任何记录**；`from_subject.status` 由 MERGED 回 ACTIVE，`canonical_subject_id` 清空。
- `business_subject_source`：`subject_id, source_reference_id`（事项↔来源证据 M:N，保留每一次出现位置）。
- **同一个问题跨邮件/会议/文件被识别**：`extraction_result`(candidate_json 含归一特征) → `review_extraction_link` → `review_queue` 候选检索（`business_subject_alias_fts` trigram 短词回退 + `source_reference` 来源比对）→ 人工 `MERGE_TO` 或 `ACCEPT_AS_NEW`。
- **多个抽取结果归一到同一 Issue**：多条 `extraction_result` 经 `review_result_object` 指向同一 `object_id`（见 R1-5）。
- **合并后原业务记录保留**：`from_subject` 及其 `issue` 行**不删除、不覆盖**，仅标 `status=MERGED` 并保留 `canonical_subject_id` 指针；查询经 canonical 链解析到目标，历史引用全部可回放。
- **明确写入**：`entity_relationship` 不得承载业务事项合并；事项合并只在 `business_subject_merge` 表达。

### 4.4 ADR 影响
**修订 ADR-6**：原「一律经 entity 归一，issue 不直接自引用合并」结论**作废**，替换为「业务实体 / 业务事项双层归一 + 可逆事项合并链 + 来源证据」。ER 图注 4 同步改写。

---

## 5. R1-5 ReviewQueue 完整审核结果链

### 5.1 原设计缺陷
`review_queue(id, extraction_result_id, reviewer_person_id, review_type, candidate_summary, suggested_entity_id, decision, target_entity_id, reviewed_at)`：
- 一条审核项只能挂 1 条抽取结果 → **无法支持"多条抽取结果合并到一个业务对象"**；
- 一条审核项只有 1 个 decision、1 个 `target_entity_id`（且只能指 entity） → **无法支持"一条抽取结果拆分成多个业务对象"**、无法指向 Issue/Risk/Task/Decision/KnowledgeItem；
- 无审核理由、无证据引用、无审核结果与正式对象的稳定关联；
- 原抽取记录可被 UPDATE/DELETE 覆盖，审核链不完整。

### 5.2 修改后的设计（四表拆分）
| 表 | 作用 | 关键字段 |
|---|---|---|
| `review_queue` | 审核**任务** | id, review_type, status, candidate_summary, suggested_subject_id, created_at |
| `review_extraction_link` | 审核任务 ↔ 抽取结果 **M:N** | review_queue_id FK, extraction_result_id FK, UNIQUE(两者) |
| `review_decision` | 审核**结果明细**（一个任务可多条结果） | id, review_queue_id FK, `decision CHECK IN ('ACCEPT_AS_NEW','MERGE_TO','REJECT')`, reviewer_person_id, reviewed_at, reason, evidence_source_reference_id, info_nature=CONFIRMED_FACT, created_at |
| `review_result_object` | 审核结果 → **正式对象稳定映射** | id, review_decision_id FK, `object_type CHECK IN ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ENTITY','BUSINESS_SUBJECT')`, object_id, relation(CREATED/MERGED_INTO/REJECTED), created_at |

- 三种决策齐全：`ACCEPT_AS_NEW`（新建，写 1 条 result_object/CREATED）、`MERGE_TO`（并入，写 result_object/MERGED_INTO + `business_subject_merge`）、`REJECT`（不生成正式对象，写 result_object/REJECTED 或仅留 decision）。
- **一条抽取拆多个对象**：1 个 review_decision 下多条 `review_result_object`（或拆成多条 decision），实测见《数据库表结构设计》§6.5。
- **多条抽取合一对象**：`review_extraction_link` 多条 → 1 个 review_queue → 1 个 `MERGE_TO` decision → 1 条 result_object 指同一 `object_id`。
- **审核人/时间/理由/证据**：`reviewer_person_id / reviewed_at / reason / evidence_source_reference_id` 必填（REJECT 亦需理由）。
- **审核后不得删除或覆盖原始抽取记录**：`extraction_result` 增触发器 `trg_extraction_immutable`（BEFORE UPDATE 校验 `candidate_json`/`raw_text`/`ingestion_job_id` 未变，否则 ABORT；BEFORE DELETE 无条件 ABORT）；审核结论只写新表，不回写覆盖候选内容。
- **G5 一致性**：`extraction_result.info_nature='AI_INFERENCE'` → `review_decision.info_nature='CONFIRMED_FACT'`（人工确认结果）→ 正式对象 `info_nature='CONFIRMED_FACT'`；`review_result_object` 记录从 AI 推断到人工事实的落点。

### 5.3 ADR 影响
**修订 ADR-6 / ADR-7**：合并链从「extraction→review_queue→entity」细化到四表完整链；`review_queue` 不再是单一扁平表。

---

## 6. R1-6 数据字典 / ER 图 / SQL 一致性

### 6.1 逐项整改（任务书 §二.6 特别检查项）
| # | 检查项 | 原状 | 整改 |
|---|---|---|---|
| 1 | `Department` 是否建表 | 产品确认书 A.1 列有 `departments`，SQL 无此表（仅 `organization.parent_id`） | **新增 `department`**（organization_id FK, code, name, parent_id 自关联, UNIQUE(organization_id,code)）；`person` 增可空 `department_id FK`；与 `organization.parent_id`（上下级单位）职责分离 |
| 2 | `project.main_object_entity_id` FK | 未建（注释"表后置，动态"） | **显式 `REFERENCES entity(id)`**；调整建表顺序：把 `entity` 等基础表前置到域1 之前（SQLite DDL 不校验后置表，但顺序前移可读性/可移植性更好） |
| 3 | `equipment.manufacturer_entity_id` FK | 未建 | **显式 `REFERENCES entity(id)`** |
| 4 | `project_member` NULL 唯一性 | `UNIQUE(project_id,organization_id,person_id,role_name,valid_from)` 中 person_id/valid_from 可 NULL → SQLite UNIQUE 视 NULL 互不相等，**重复行可插入** | 删除表内 UNIQUE，改**表达式唯一索引** `UNIQUE INDEX ON project_member(project_id, organization_id, COALESCE(person_id,''), role_name, COALESCE(valid_from,''))`（实测重复被拦截） |
| 5 | `action_measure` 业务关联 | `source_owner_type/id` 多态无完整性 | 增 `risk_id`/`issue_id` 两个可空 FK + `CHECK((risk_id IS NOT NULL)+(issue_id IS NOT NULL)>=1)`；另设 `action_measure_link` 支持一个措施挂多个属主（M:N），并纳入多态自检 |
| 6 | `object_dimension_tag` 值类型约束 | 仅 `dimension` CHECK，`value_type` 无约束、REF/FREE_TEXT 可乱填 | `CHECK(value_type IN ('REF','FREE_TEXT'))` + `CHECK((value_type='REF' AND value_id IS NOT NULL AND value_text IS NULL) OR (value_type='FREE_TEXT' AND value_text IS NOT NULL AND value_id IS NULL))` |
| 7 | `entity_identifier` 唯一范围 | `UNIQUE(id_type,identifier)` 全局唯一，不同来源系统同号即冲突 | 改 `UNIQUE(entity_id, id_type, COALESCE(source_from,''), identifier)`（同一实体/类型/来源下唯一），另建 `(id_type,identifier)` 非唯一检索索引；跨实体同号由业务校验 |
| 8 | `drawing_no` 唯一范围 | 全局 `UNIQUE(drawing_no)`，不同项目同图号冲突 | 改 `UNIQUE(project_id, drawing_no)`；project_id 可空时用 `COALESCE(project_id,'')` 表达式唯一索引，保证「按项目约束」 |
| 9 | 多态引用完整性策略 | 仅文字说明「应用层兜底」，无可执行检查 | 新增 `sp_check_polymorphic_refs` 自检策略（一组 UNION 查询，覆盖 `source_reference`/`object_link`/`evidence_link`/`decision_link`/`action_measure_link`/`review_result_object`/`business_subject_alias`/`object_dimension_tag`），按 type 分派到目标表查孤儿；定义摄入后 + 定期运行，结果写 `audit_log` |
| 10 | 公共字段规范 | 各表不齐（多数表缺 `updated_at/created_by/updated_by/info_nature/del_status`） | 定义**基线 A（完整，正式业务表）**：`id, project_id, info_nature, created_at, updated_at, created_by, updated_by, is_deleted, deleted_at, del_status`；**基线 B（精简，辅助/日志/关联表）**：`id, created_at, is_deleted`；逐表在《核心实体数据字典》§0 标注所用基线，SQL 严格对应 |

### 6.2 三方一致性规则（写入验收）
- **SQL 中每张表必须在数据字典中有对应说明；数据字典中每张表必须在 SQL 中有对应定义**（本轮以脚本比对双向清单，见 §9）。
- ER 图必须覆盖所有正式表之间的主要关系（含新增 10 张表）。
- 表名统一 snake_case 单数（`project` 而非 `projects`）；消除旧稿中 `issue_link`（总体设计 §4）与 `object_link`（SQL）不一致、`document_fts(name,snapshot_json)` 等列错配。
- **重新统计并统一数量**：见《数据库表结构设计》§0.2 与《核心实体数据字典》§0，8 份文档一律引用同一统计表。

### 6.3 ADR 影响
**修订 ADR-1/2/3/4/5/12**：分别补充 FK 与建表顺序、维度值约束、表达式唯一索引、多态自检策略、外部编号唯一范围、维度化归口。

---

## 7. 实测验证结果

> 由主理人独立内存库复跑 + 两个独立技术验证任务在 Python `sqlite3` 的 `:memory:` 内存库执行（SQLite 3.53.1），未触碰 `01_Data/epcs_intelligence.db`、未创建 `migrations/001_init.sql`、未安装任何依赖。结果原文收录于《数据库表结构设计》§2.4 / §2.5 / §6.5 / §7.4 / **§8（8-A~8-H 分组 + G1~G10）** 及本记录。
> **汇总：A~F 六组专项 + G1~G10 额外检查，全部 PASS，0 FAIL。**

### 7.1 六项阻断整改的实测结论

| 整改项 | 验证内容 | 结果 |
|---|---|---|
| R1-1 基线只读 | §8-C 六案例：两条历史基线共存 / 第二条生效 / 第一条内容不可改 / 物理删除被阻止 / 同计划不可有两个生效基线 / 不同计划各有一个生效基线；改任一内容字段均被无差别 `BEFORE UPDATE` 拦截；切换全程不触碰 `baseline_version` | **6/6 PASS** |
| R1-2 计划活动版本化 | §8-D：V1/V2 差异 3 行（MODIFIED / REMOVED / ADDED）、V1 回放 3 个活动、四种 `change_type` 齐全、`baseline → plan_version → plan_activity_version` 回放链成立、滚动预测 vs 批准基线可对比 | **PASS** |
| R1-3 FTS5 trigram | §8-A/B：外部内容表 `content_rowid='id'`（TEXT UUID）不可行、外部内容表 `count(*)` 不反映索引且幽灵行只能由 `integrity-check` 发现；统一普通内容表 + `biz_id` 显式映射 PASS；中文矩阵三字以上命中、1~2 字 MATCH 恒 0 走 LIKE 回退、`CMHI-001` / `FAT 11/5` 未转义报错而双引号包裹后各命中 1、历史版本可检索 | **PASS** |
| R1-4 Entity / 事项分层 | §8-E E9/E10：双层归一、一个事项多别名、跨邮件 / 会议 / 文件证据链、可逆合并（合并→撤销）、原业务记录不删除不覆盖；把 `business_subject.id` 写入 `entity_relationship` 被 FK 拦截，印证该表不得承载事项合并 | **PASS** |
| R1-5 审核结果链 | §8-E E1~E8：四表建表与 FK、一条抽取拆多对象、多条抽取合一对象、审核人 / 时间 / 理由 / 证据约束、7 类 `object_type`、G5 三级链、原始抽取不得覆盖、不得删除 | **8/8 PASS** |
| R1-6 一致性十项 | §8-F：`department` 与两处显式 FK、`project_member` COALESCE 唯一索引拦截重复 NULL、`action_measure` 双 FK+CHECK、`object_dimension_tag` 值互斥、`entity_identifier` 唯一范围收敛、`drawing_no` 按项目唯一、多态孤儿自检、公共字段基线 A/B、表名统一 | **10/10 PASS** |

### 7.2 额外架构检查实测 G1~G10

全部 PASS：G1 trigram 可用 / G2 短词回退 / G3 软删镜像与重建一致性 / G4 值类型 CHECK 拦截 / G5 `info_nature` CHECK / G6 AI 预测版信息性质约束 / G7 多态孤儿自检能查出孤儿 / G8 UUID CHECK 拦截非法 ID / G9 `PRAGMA foreign_keys` **按连接生效**（连接 A 开启后新连接 B 仍为 0 且可插违规 FK）/ G10 SQLite 允许 FK 引用后置表。逐项见《数据库表结构设计》§8-G。

### 7.3 独立验证任务的补充发现（仅作佐证，不改写设计）

- 两个后台验证任务各自构造的简化模型（约 30 表 / 3 视图）与 R1 全库设计（75 表 / 0 视图）**不是同一口径**，其统计数字不作为文档依据；但两者在业务事项可逆合并、审核四表链拆分 / 合并、多态引用即时校验、表达式唯一索引、按项目图号唯一、trigram 短词等场景的结论与 R1 一致，构成独立佐证。
- AI 预测版本（`is_forecast=1`, `info_nature=PREDICTION`）不能成为批准基线，已由 §8-C 追加实测确认。
- **统计口径实测踩坑**：必须用 `PRAGMA table_list` 区分 `table/virtual/shadow/view` 并排除 `sqlite_schema`；FTS5 影子表与 `sqlite_autoindex_*` 自动索引属内部对象，不计入表数 / 显式索引数；用 `sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'` 会误计影子表、漏计自动索引。
- **FK 不可后补**：SQLite 不支持 `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`（实测报 `near "FOREIGN": syntax error`），FK 必须在 `CREATE TABLE` 内联声明；连接建立后建议追加 `PRAGMA foreign_key_check` 启动自检。两个验证任务均独立复现该结论。
- **实现期建议（未纳入本轮 DDL）**：为 `business_subject_merge` 增加合并守卫触发器（禁止自合并 / 目标不存在 / 合并到已合并主体），并为权威根解析提供视图；独立验证任务实测该守卫能拦截非法合并链。本轮为避免改变 §0.2 的「触发器 96 / 视图 0」统计口径未纳入，列入后续实现评审。

### 7.4 验证边界

所有验证只在内存库进行；正式库 `01_Data/epcs_intelligence.db` 全程保持空库（8192 bytes，业务表 0），未执行任何 DDL/DML，未导入业务数据。

### 7.5 全量 DDL 编译验证（最终自检）

直接从《表结构设计》提取全部 SQL 代码块，剥离整行注释后按「先 75 张表 → 再 FTS 范式模板 → 再索引 / 触发器」的依赖顺序在 `:memory:` 内存库编译，验证「文档即 DDL」而非仅纸面描述（详见《表结构设计》§8-I）。

| 项目 | 结果 |
|---|---|
| 提取 `CREATE TABLE` | **75**（与 §0.4 声明清单零差异） |
| 提取 `CREATE VIRTUAL TABLE`（范式模板） | 1 |
| 提取 `CREATE INDEX / UNIQUE INDEX / TRIGGER` | 44 |
| **执行失败** | **0** |
| 内存库普通表 / FTS 虚表 / 影子表 | **75** / 1 / 5 |
| 触发器 / 显式索引 / 自动索引 | 8 / 36 / 120（自动索引 `sql IS NULL`，不计入显式索引） |
| `PRAGMA foreign_key_check` | 无违规 |
| `PRAGMA integrity_check` | `ok` |

> 该验证只编译文档中给出的模板与显式对象，故 FTS 虚表 1、触发器 8 与 §0.2 的 24 / 96 不同（后者为迁移脚本按 §7.2 清单循环生成后的数量）。结果同时印证统计口径：须用 `pragma_table_list` 区分 `shadow` 影子表与 `sql IS NULL` 自动索引，否则会误计。
> 附带发现（核验脚本陷阱，非 DDL 缺陷）：保留整行 SQL 注释会使「注释 + `CREATE TABLE`」合并成一条语句，导致 21 张表被漏分类、索引因表不存在报错；剥离整行注释后全量通过。

---

## 8. 额外架构检查（任务书 §三，10 项）

| # | 检查项 | 结论 |
|---|---|---|
| 1 | G2 来源追溯是否适用于所有正式业务对象 | ✅ 已明确「正式业务对象清单」及三类追溯通道（`source_reference` / `business_subject_source` / `review_result_object`）；附覆盖率自检 SQL（§9） |
| 2 | G4 版本管理是否覆盖完整历史 | ✅ document/drawing/plan/plan_activity/knowledge/meeting_minutes 六类版本 + issue/risk/task 状态历史 + baseline 切换历史；「业务事项版本」由 `business_subject` + 状态历史 + 可逆合并承载 |
| 3 | G5 六层信息性质一致性 | ✅ 明确各表默认 `info_nature`：`source_reference`=SOURCE_FACT、`extraction_result`=AI_INFERENCE、`plan_version(is_forecast=1)`=PREDICTION、AI 提案=PROPOSAL、`review_decision`/正式对象=CONFIRMED_FACT、`decision`=DECISION；转换只允许人工确认 |
| 4 | G6 是否覆盖全部承载内容文本表 | ✅ §3.3 24 张 FTS 一一对应；无遗漏的文本表在《数据字典》§0 列出「不建 FTS」理由（纯数值/JSON 元数据表） |
| 5 | 软删除/归档/物理删除一致规则 | ✅ 三态（ACTIVE/ARCHIVED/DELETED）+ `is_deleted`/`deleted_at`；正式表禁物理删除触发器清单；仅临时/缓存表允许物理删除；FTS 软删镜像规则见 §3.4 |
| 6 | 外键约束是否完整 | ✅ 硬 FK 全部显式；新增 department、entity 两处 FK；多态字段以 `sp_check_polymorphic_refs` 自检 + 应用层 + 审计补偿（并明确这是**已知取舍**，不伪装成硬约束） |
| 7 | `PRAGMA foreign_keys` 每个连接启用 | ✅ 实测确认：SQLite 该 PRAGMA **按连接生效**，Python `sqlite3.connect()` 后必须逐连接执行；写入连接规范与迁移脚本首行（详见《数据库表结构设计》§0） |
| 8 | UUID 统一生成与校验 | ✅ `uuid4().hex`（32 位小写十六进制）；DB 层 `CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')`；应用层统一 `new_uuid()`；禁止用文件名/姓名/项目名作主键 |
| 9 | 迁移幂等性含结构一致性检查 | ✅ 不只 `IF NOT EXISTS`：还需 `PRAGMA table_info` 逐列比对、索引/触发器清单比对、`schema_version` 登记、单事务失败回滚、FTS 重建与一致性自检 |
| 10 | SQLite→PostgreSQL 适配 | ✅ 适配清单见《数据库表结构设计》§10：UUID TEXT→`uuid`、ISO8601 文本→`timestamptz`、INTEGER 布尔→`boolean`、部分索引/表达式索引→Pg 部分索引、FTS5 trigram→`pg_trgm`+GIN、`RAISE(ABORT)`→PL/pgSQL `RAISE EXCEPTION`、WAL/PRAGMA→不适用、`CHECK` 与 `UNINDEXED` 列→生成列/tsvector |

---

## 9. 质量验收逐项核验（任务书 §五）

| # | 验收项 | 结果 | 证据位置 |
|---|---|---|---|
| 1 | 基线历史版本与当前基线逻辑正确 | ✅ | 《表结构设计》§2.4 六案例 |
| 2 | 计划活动支持版本化 | ✅ | §2.3 / 《数据字典》§2 |
| 3 | FTS5 所有内容表对应正确 | ✅ | §3.3 对应表 / 《表结构设计》§7 |
| 4 | FTS 同步和重建策略完整 | ✅ | §3.4 / 《表结构设计》§7.3、§7.5 |
| 5 | Entity 与 Issue 等事项归一关系完整 | ✅ | §4 / 《表结构设计》§5、§6 |
| 6 | ReviewQueue 审核结果链完整 | ✅ | §5 / 《表结构设计》§6.5 |
| 7 | 数据字典与 SQL 一一对应 | ✅ | 《表结构设计》§0.4 双向清单比对（75 张 SQL 表 ↔ A46+B29，零差异）+ §8-I 全量编译 |
| 8 | ER 图与实际关系一致 | ✅ | 《实体关系ER图》全表覆盖 |
| 9 | 表数量和文档统计一致 | ✅ | 《表结构设计》§0.2 统一统计表 |
| 10 | 无明显外键/唯一索引/触发器逻辑错误 | ✅ | §6.1 逐项 + 实测 |

---

## 10. 新增待确认事项（不隐瞒）

| # | 事项 | 来源 | 责任 |
|---|---|---|---|
| N1 | 基线切换的授权角色与审批流（依赖 D.2-2 角色清单） | R1-1 | 产品/权限 Phase |
| N2 | 切换日志/审计留存期 | R1-1 | 架构 |
| N3 | 短词检索 LIKE 回退的性能阈值与候选集范围；二期是否物化 `short_term_index` | R1-3 | 架构/实现 |
| N4 | 软删 FTS 行「保留+过滤」vs「移除」的最终取舍（本轮定保留，需实测容量后确认） | R1-3 | 架构 |
| N5 | 全部历史版本入 FTS 的存储放大评估 | R1-3 | 实现评审 |
| N6 | `business_subject_merge` 撤销后历史引用重指向策略 | R1-4 | 产品/架构 |
| N7 | `subject_kind` / `review_result_object.object_type` 枚举扩展流程 | R1-4/5 | 架构 |
| N8 | `department` 与 `organization.parent_id` 的职责边界（部门 vs 上下级单位） | R1-6 | 领域专家 |
| N9 | 公共字段基线 A/B 的最终裁剪清单 | R1-6 | 实现评审 |
| N10 | `plan_activity_version` 工作量单位与进度口径标准 | R1-2 | 计划管理 Phase |

---

## 11. 停止边界确认

- 本轮**只修改设计文档**；未创建/执行 `migrations/001_init.sql`，未对 `epcs_intelligence.db` 执行任何 DDL/DML，未导入业务数据，未装 SDK，未连外部账号，未使用 Ollama。
- Git 提交记录见《设计阶段完成报告》与本轮提交输出。
- 完成后**立即停止**，等待系统架构师再次审核；Phase 1.3（幂等迁移 + 空库升级）需另行批准。
