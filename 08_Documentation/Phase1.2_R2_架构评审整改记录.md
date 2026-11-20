# Phase1.2 R2 架构评审整改记录（定向整改逐项闭环）

> 版本：**R2**（Phase 1.2 复审「数据模型完整性与证据追溯」定向整改）｜日期：2026-11-12｜角色：系统架构师（高见远）
> **本轮定位**：系统架构师对 R1（18 份文档）复审结论为「**暂不通过，继续定向整改**」，认可六项原始阻断问题已有实质整改，但发现 **7 项「文档声称已解决、SQL 实际未闭环」问题（P1~P7）+ 4 项实现边界（B1~B4）**。R2 **只针对这 11 项**修改设计文档，不全面重做 Phase 1.2；R1 六项整改结论继续有效，被 R2 修订的结论已在对应文档逐处标注。
> **唯一真值源**：《Phase1.2_数据库表结构设计.md》(**R2**)。本记录中的 DDL / 约束 / SQL 均摘自该真值源，已在 SQLite 3.53.1 `:memory:` 内存库编译与行为验证；如与本记录有任何出入，以真值源为准。
> **统一统计口径（R2）**：实体表 **75**（46 基线A + 29 基线B）／ FTS5 虚表 **24** ／ 触发器 **126** ／ 视图 **0**。触发器由 R1 的 96 → 126（**+30**：业务主键/归属不可变 24 + 审核证据校验 2 + 可逆合并链守卫与联动 4）；实体表 / FTS 虚表 / 视图数量不变，仅新增 2 个非空列 `plan_activity_version.plan_id` 与 `progress_record.plan_id`。
> **命名声明（P6）**：`check_polymorphic_refs` 是**应用层执行的一组 SQL 自检语句集**，SQLite **没有原生存储过程**、不能 `CALL`；R1 的存储过程式旧名已全文废弃，全文统一为新名。
> **工作边界（铁律）**：只改 `08_Documentation/` 下的设计文档；**未创建** `01_Data/migrations/001_init.sql` 或任何 `.sql` 迁移文件；**未对** `01_Data/epcs_intelligence.db` 执行任何 DDL/DML（空库保持）；**未导入**任何资料；**未接入**外部账号 / Ollama / DWG SDK；**未改动**旧知识库 `D:\ALLAN\个人知识库`；**未回改** `09_Archive/Phase1.2_R1_原稿/` 归档副本；**未执行 git commit**（由主理人统一提交）。自检脚本仅置于操作系统临时目录，未写入项目目录。

---

## 1. 复审基线与 QA 阶段 A 实测现象

### 1.1 复审结论与整改范围

| 维度 | R1 复审结论 | R2 处置 |
|---|---|---|
| 六项原始建表阻断问题 | 已有实质整改 | 结论继续有效，仅同步统计口径与命名 |
| 7 项「文档声称已解决、SQL 实际未闭环」 | **暂不通过，继续定向整改** | 逐项给出数据库级约束 + 正/反向用例（本文 §2） |
| 4 项实现边界 | 进入迁移阶段前必须明确 | 逐项给出确定结论 / 生成规则 / 裁定表（本文 §3） |
| 整体状态 | **未宣告整体 PASS** | R2 定向整改完成，**等待系统架构师再次审核**；QA 阶段 B 已用同一套用例换 R2 DDL 复跑（结果与本文预期一致、无复跑不一致，正式结论以主理人汇编为准） |

### 1.2 QA 阶段 A 实测：R1 基线编译与 12 条非法数据

QA（严过关）在内存 SQLite 3.53.1 复现，结论如下：

| 项目 | R1 实测结果 |
|---|---|
| 抽取 `CREATE TABLE` / FTS 虚表 / 索引 / 触发器 | **75 / 1 / 36 / 8**，执行失败 **0**、`PRAGMA foreign_key_check` 无违规、`integrity_check = ok` |
| 对象统计（QA 实测 E5） | `pragma_table_list` 中 `type='table'` 的系统目录表有 **两张**（`sqlite_schema` + `sqlite_temp_schema`）；只排除前者会得 **76** 而非 75，须用 `name NOT LIKE 'sqlite_%'` |
| 非法数据接受情况 | **12 条非法数据被 R1 直接接受**：跨计划写入 **4/4** 未拒绝；审核证据为空未拒绝；FTS 重建丢软删行且 drift 自检返回 0（**静默丢失**）；多态孤儿 **4 类漏报**；可逆合并链 **5/5** 未拒绝 |

> 「文档显式 DDL」与「迁移生成后对象」是**两个口径**，不得混为一谈：R1 文档显式 DDL 为 1 张 FTS 虚表 / 8 触发器，迁移脚本按清单生成后为 24 张 FTS / 96 触发器。R2 显式 DDL 增至 2 张 FTS / 19 触发器（新增版本表变体示例与专用触发器），生成后为 24 / **126**。详见真值源 §8-I 双口径对照表。

### 1.3 R2 不整改范围（明确留白，避免误读）

- 不全面重做 Phase 1.2；不新增 / 删除实体表、FTS 虚表、视图；不改写 75 张表的业务字段语义。
- 不创建 `001_init.sql`、不执行任何迁移、不导入资料；不接入外部账号 / Ollama / DWG SDK。
- 不修改 `09_Archive/Phase1.2_R1_原稿/` 归档副本；不改动历史阶段文档《Phase1.2_数据模型设计任务书.md》《Phase1.2_设计阶段完成报告.md》正文。
- 不把多态引用伪装成数据库硬 FK：沿用 ADR-4 / ADR-5「应用层校验 + `check_polymorphic_refs` 自检 + 审计留痕」三层补偿的**已知取舍**。

---

## 2. 七项阻断逐项闭环（P1~P7）

> 每项固定 6 段：**问题与 R1 实测现象 → 架构决策 → DDL / 数据库级约束 → 正向测试（预期通过）→ 反向测试（预期被拒绝 / 被检出）→ 影响文档清单**。
> 全部 DDL 均要求 `PRAGMA foreign_keys=ON` **按连接单独执行**；复合外键的被引用列必须有匹配的 `UNIQUE` / `PRIMARY KEY` 索引，否则 SQLite 编译失败（本轮已在内存库实测）。

### 2.1 P1 跨计划一致性（ADR-13）

**问题与 R1 实测现象**：`plan_activity_version`（真值源 R1 L254）分别引用 `plan_activity(id)` 与 `plan_version(id)` 两个独立 FK，未保证同 `plan_id`；`activity_dependency`（L274）引用 `plan_version` + 两个活动 ID，未保证三者同计划；`baseline_version`（L204）的 `plan_id` 与 `plan_version_id` 是两个独立 FK；`plan_active_baseline`（L217）的 `plan_id` 与 `baseline_version_id` 未保证对应。QA 实测 **4/4 跨计划写入被接受**，可写出「计划 A 的批准基线指向计划 B 的版本」。

**架构决策**：采用**复合唯一键 + 共享 `plan_id` 的复合外键**（数据库级机制），7 张子表全部同计划，**不依赖应用层约定**。不采用「仅触发器比对」或「新增中间表」方案（理由见 ADR-13 备选方案）。

**DDL / 数据库级约束**（摘自真值源 §2，已在内存库编译通过）：
```sql
-- ① 父表补匹配的复合 UNIQUE（复合 FK 的前置条件）
CREATE TABLE plan_version (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    version_no TEXT NOT NULL, /* ... 其余列见真值源 §2 ... */
    UNIQUE(plan_id, version_no), UNIQUE(plan_id, id));
CREATE TABLE plan_activity (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    code TEXT NOT NULL, /* ... */
    UNIQUE(plan_id, code), UNIQUE(plan_id, id));
CREATE TABLE baseline_version (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    plan_version_id TEXT NOT NULL, /* ... */
    UNIQUE(plan_id, baseline_no), UNIQUE(plan_id, plan_version_id), UNIQUE(plan_id, id),
    FOREIGN KEY(plan_id, plan_version_id) REFERENCES plan_version(plan_id, id));
-- ② 子表用共享 plan_id 的复合 FK（示例：活动版本 / 依赖 / 生效基线 / 切换日志）
CREATE TABLE plan_activity_version (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    activity_id TEXT NOT NULL, plan_version_id TEXT NOT NULL, /* ... */
    UNIQUE(activity_id, plan_version_id),
    FOREIGN KEY(plan_id, activity_id)     REFERENCES plan_activity(plan_id, id),
    FOREIGN KEY(plan_id, plan_version_id) REFERENCES plan_version(plan_id, id));
CREATE TABLE activity_dependency (
    id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id),
    plan_version_id TEXT NOT NULL, predecessor_id TEXT NOT NULL, successor_id TEXT NOT NULL,
    /* ... */
    FOREIGN KEY(plan_id, plan_version_id) REFERENCES plan_version(plan_id, id),
    FOREIGN KEY(plan_id, predecessor_id)  REFERENCES plan_activity(plan_id, id),
    FOREIGN KEY(plan_id, successor_id)    REFERENCES plan_activity(plan_id, id));
CREATE TABLE plan_active_baseline (
    plan_id TEXT PRIMARY KEY REFERENCES plan(id),
    baseline_version_id TEXT NOT NULL, /* ... */
    FOREIGN KEY(plan_id, baseline_version_id) REFERENCES baseline_version(plan_id, id));
-- ③ progress_record / baseline_switch_log / plan_activity.first_version_id 同理
--    并新增非空列 plan_activity_version.plan_id、progress_record.plan_id（实体表仅此 2 列变更）
```

**正向测试（预期通过）**：6 类同计划对象各插入 1 条——`plan_activity_version`、`activity_dependency`、`plan_active_baseline`、`progress_record`、`baseline_switch_log`、`plan_activity.first_version_id`，全部插入成功；两个计划各有一个生效基线且 `baseline_no` 可复用。

**反向测试（预期被拒绝）**：7 项跨计划写入全部报 `FOREIGN KEY constraint failed`：
1. 「把 A 计划活动挂到 B 计划版本」（`plan_activity_version`）；
2. 「A 计划活动的 `first_version_id` 指向 B 计划版本」；
3. 「**A 计划基线指向 B 计划版本**」（`baseline_version`）；
4. 「A 计划的生效基线指向 B 计划的基线」（`plan_active_baseline`）；
5. 依赖的 `successor_id` 跨计划；
6. `progress_record.plan_version_id` 跨计划；
7. `baseline_switch_log.from_baseline_id` 跨计划。

**影响文档清单**：真值源 §2 / §0.2 / §8-J J1 / §12.1 / §12.3；《核心实体数据字典》§2；《实体关系ER图》计划域关系 + §关系注 R2-P1 补充；《版本及历史管理规范》§2 / R2 对齐小节；《统一数据模型总体设计》§4 / R2 对齐小节；《架构决策记录》ADR-13 / ADR-8 补充；本文 §5。

### 2.2 P2 `action_measure` 语义冲突（ADR-14，独立条目）

**问题与 R1 实测现象**：SQL（R1 L529-538）是 `CHECK((risk_id IS NOT NULL AND issue_id IS NULL) OR (issue_id IS NOT NULL AND risk_id IS NULL))`，即「**恰好一个非空**」；但 R1 整改报告写「至少一个非空」，新增的 `action_measure_link`（L541）又宣称「一个措施挂多个属主 M:N」，三者矛盾。QA 追加实证两点：`measure_type='RISK_RESPONSE'` 却挂 `issue_id` **被接受**（无语义 CHECK）；`action_measure_link.ref_id` 写入不存在的对象（孤儿）**被接受**。

**架构决策**（明确写入 ADR-14）：
1. **保留 XOR CHECK 作为「唯一主属主」语义**——恰好一个主属主非空，禁止双非空与零属主；
2. `action_measure_link` 只承载 **0..N 附加属主**，不得重复登记主属主（由 §7.6.3 职责边界自检检出）；
3. **新增 `measure_type` 语义 CHECK**，把措施类型与唯一主属主强绑定，杜绝 QA 实测的错挂；
4. `action_measure_link.ref_id` 明确为**多态引用、无硬 FK**；孤儿由 P6 `q7` 分支（23 类 `target` 全集 + `IS NULL` 反连接）**必然检出**，配合应用层校验与 `audit_log` 三层补偿，**不伪装成硬 FK**；
5. 全文统一措辞为「**恰好一个主属主 + 0..N 附加属主**」。

> 备选方案与否决理由（「直接列允许双非空」/「给 link 加硬 FK」/「删除 link 表」）见《架构决策记录》ADR-14「备选方案」。

**DDL / 数据库级约束**（真值源 §4）：
```sql
CREATE TABLE action_measure (
    id TEXT PRIMARY KEY, /* ... */
    measure_type TEXT NOT NULL CHECK(measure_type IN ('RISK_RESPONSE','ISSUE_REMEDY')),
    risk_id TEXT REFERENCES risk(id), issue_id TEXT REFERENCES issue(id),
    /* R2-P2：XOR = 恰好一个主属主 */
    CHECK((risk_id IS NOT NULL AND issue_id IS NULL) OR (issue_id IS NOT NULL AND risk_id IS NULL)),
    /* R2-P2（QA 补充）：measure_type 必须与唯一主属主一致，蕴含并强化 XOR */
    CHECK((measure_type='RISK_RESPONSE' AND risk_id  IS NOT NULL AND issue_id IS NULL)
       OR (measure_type='ISSUE_REMEDY'  AND issue_id IS NOT NULL AND risk_id  IS NULL)));
-- action_measure_link：0..N 附加属主；ref_id 多态，孤儿由 check_polymorphic_refs 的 q7 检出
CREATE TABLE action_measure_link (
    id TEXT PRIMARY KEY, action_measure_id TEXT NOT NULL REFERENCES action_measure(id),
    ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, link_role TEXT, /* ... */);
-- 职责边界自检（真值源 §7.6.3）：link 不得重复登记主属主
SELECT l.id FROM action_measure_link l JOIN action_measure am ON am.id = l.action_measure_id
WHERE (UPPER(l.ref_type)='RISK'  AND l.ref_id = am.risk_id)
   OR (UPPER(l.ref_type)='ISSUE' AND l.ref_id = am.issue_id);
```

**正向测试（预期通过）**：`RISK_RESPONSE` + `risk_id`、`ISSUE_REMEDY` + `issue_id` 各 1 条写入成功；同一措施挂 2 条合法附加属主 link 成功；职责边界自检正常态返回 **0 行**；`q7` 分支对合法 `ref_id` 返回 **0 行**。

**反向测试（预期被拒绝 / 被检出）**：
- 双主属主（`risk_id` + `issue_id` 同时非空）→ `CHECK constraint failed`；
- 零主属主 → `CHECK constraint failed`；
- **`RISK_RESPONSE` 挂 `issue_id`** → `CHECK constraint failed`（R1 会接受）；
- **`ISSUE_REMEDY` 挂 `risk_id`** → `CHECK constraint failed`（R1 会接受）；
- **`action_measure_link.ref_id` 指向不存在的对象** → 被 `q7` 的 `IS NULL` 反连接检出（非硬 FK，走自检 + 审计）；
- link 重复登记主属主 → 被职责边界自检检出。

**影响文档清单**：真值源 §4 / §7.6.2 `q7` / §7.6.3 P2 / §8-J J2 / §12.1 / §12.3；《核心实体数据字典》§4.5；《实体关系ER图》关系注第 5 条；《统一数据模型总体设计》§4 / R2 对齐小节；《数据来源与证据追溯规范》§2 对齐段；R1《架构评审整改记录》§5 第 5 项标注「本结论已被 R2 修订」；《架构决策记录》ADR-14；本文 §4 / §5。

### 2.3 P3 `ReviewDecision` 证据可为空（ADR-15，独立条目）

**问题与 R1 实测现象**：`review_decision`（R1 L678-683）中 `evidence_source_reference_id TEXT REFERENCES source_reference(id)` **无 `NOT NULL`**；但《数据来源与证据追溯规范》与 R1 整改报告均称证据必填，真值源 R1 L726 的验证表甚至写「审核人/时间/理由/证据 … **PASS（约束强制）**」——属文档与 SQL 不一致的不实结论。QA 实测「审核证据为空」未拒绝。

**架构决策**：**不允许例外审核类型**——所有审核决定（含 `REJECT`）一律绑定来源证据：`NOT NULL` + FK + 2 个触发器校验证据存在且未软删；事后软删由一致性自检检出。同步修正真值源 §6.5 验证表与 §8-E E4 的「PASS（约束强制）」不实结论。

**DDL / 数据库级约束**（真值源 §6）：
```sql
CREATE TABLE review_decision (
    id TEXT PRIMARY KEY, /* ... */
    reviewer_person_id TEXT NOT NULL REFERENCES person(id),
    reviewed_at TEXT NOT NULL, reason TEXT NOT NULL,
    evidence_source_reference_id TEXT NOT NULL REFERENCES source_reference(id),
    /* ... */);
CREATE TRIGGER trg_rd_evidence_i BEFORE INSERT ON review_decision
WHEN (SELECT is_deleted FROM source_reference WHERE id = NEW.evidence_source_reference_id) <> 0
BEGIN SELECT RAISE(ABORT,'review evidence: source_reference is soft-deleted'); END;
CREATE TRIGGER trg_rd_evidence_u BEFORE UPDATE OF evidence_source_reference_id ON review_decision
WHEN (SELECT is_deleted FROM source_reference WHERE id = NEW.evidence_source_reference_id) <> 0
BEGIN SELECT RAISE(ABORT,'review evidence: source_reference is soft-deleted'); END;
-- 事后软删自检（真值源 §7.6.3）
SELECT rd.id FROM review_decision rd
JOIN source_reference sr ON sr.id = rd.evidence_source_reference_id
WHERE sr.is_deleted <> 0 AND rd.is_deleted = 0;
```
> 新增 **2 个触发器**，计入 §0.2 的 126。

**正向测试（预期通过）**：绑定有效且未软删的 `source_reference` 的 `ACCEPT_AS_NEW` 决定写入成功；`REJECT` 亦需理由与证据，写入成功。

**反向测试（预期被拒绝 / 被检出）**：空证据 → `NOT NULL constraint failed`；不存在的证据 id → `FOREIGN KEY constraint failed`；已软删证据 → 触发器 `RAISE(ABORT)`；`UPDATE` 换绑已软删证据 → 触发器拒绝；决定写入后其证据被软删 → 一致性自检检出该决定，结果写 `audit_log`。

**影响文档清单**：真值源 §6 / §6.5 验证表 / §7.6.3 P3 / §8-E E4 / §8-J J3 / §12.1；《核心实体数据字典》§6 `review_decision`；《数据来源与证据追溯规范》§1 审核链通道 / §2 对齐段；《实体关系ER图》关系注第 8 条；R1《架构评审整改完成报告》「PASS（约束强制）」类结论标注；《架构决策记录》ADR-15；本文 §5。

### 2.4 P4 Entity 与 BusinessSubject 概念冲突（ADR-16）

**问题与 R1 实测现象**：R1 已正确把 `entity`（船舶/设备/区域/组织）与 `business_subject`（ISSUE/RISK/TASK/DECISION/KNOWLEDGE_ITEM，真值源 R1 L439-441）分层；但《数据来源与证据追溯规范》§1 仍写「`plan_activity` / `knowledge_item` / `entity` 等具体事项 **1:1 挂 `subject_id`**」。SQL 里 `business_subject.subject_kind` 不含 `ENTITY` / `PLAN_ACTIVITY`、`entity` 无 `subject_id`。QA 追加追问：`review_result_object(object_type='ENTITY')` 在 R1 可写入，是否合法？

**架构决策**：
1. **保留双层结构，不把 Entity 变成 BusinessSubject**：Entity 经 `source_reference` 直接追溯来源；Issue/Risk/Task/Decision/KnowledgeItem 经 `business_subject` 归一（1:1 挂 `subject_id`）；`plan_activity` / `entity` 不挂 `subject_id`，**不改 DDL**；
2. **`review_result_object(object_type='ENTITY')` 明确为合法多态类型**（§6 `object_type CHECK` 的 7 类之一），**不加禁止 CHECK、不改 DDL**，显式纳入 P6 `q8` 分支与 `target` 全集；
3. 重写追溯规范 §1 文字与 Mermaid 流程图，消除所有 1:1 误述；ER 图 / 数据字典 / 总体设计与之对齐。

**DDL / 数据库级约束**：**本项不新增 DDL**（结构本身正确，问题只在文档）。相关既有约束：`business_subject.subject_kind CHECK` 不含 `ENTITY` / `PLAN_ACTIVITY`；`review_result_object.object_type CHECK(... 'ENTITY' ...)`；`entity` 表无 `subject_id` 列。P6 `q8` 分支的合法性由映射清单登记：
```sql
-- q8：ENTITY 为合法类型；正常 ENTITY 引用不被误报，ENTITY 孤儿被检出
SELECT 'review_result_object' AS src, r.id, r.object_type, r.object_id
FROM review_result_object r
LEFT JOIN target t ON t.typ = UPPER(r.object_type) AND t.id = r.object_id
WHERE t.id IS NULL OR UPPER(r.object_type) NOT IN
  ('ISSUE','RISK','TASK','DECISION','KNOWLEDGE_ITEM','ENTITY','BUSINESS_SUBJECT');
```

**正向测试（预期通过）**：`source_reference.traced_entity_type='ENTITY'` + 真实 `entity.id` 正常追溯；`review_result_object('ENTITY', 真实 entity.id)` 写入成功且 `q8` 返回 **0 行**；Issue/Risk/Task/Decision/KnowledgeItem 各自 1:1 挂 `subject_id` 成功。

**反向测试（预期被拒绝 / 被检出）**：`review_result_object('ENTITY', 'ORPHAN-ENTITY')` → 被 `q8` 检出；非法 `object_type` 值 → 被 `q8` 检出；若尝试把 `ENTITY` 写进 `business_subject.subject_kind` → 被 CHECK 拒绝。

**影响文档清单**：《数据来源与证据追溯规范》§1（重写）/ §2；《实体关系ER图》关系注第 8 条；《核心实体数据字典》§0 / §5；真值源 §1 / §5 / §6 / §7.6.2 `q8` / §12.1；《统一数据模型总体设计》R2 对齐小节；《架构决策记录》ADR-16；本文 §5。

### 2.5 P5 FTS 软删规则与重建规则冲突（ADR-17，独立条目）

**问题与 R1 实测现象**：R1 规定「软删后保留 FTS 行并将 `is_deleted` 镜像置 1、查询过滤 `is_deleted=0`」，但 §7.6 重建 SQL（R1 L848）是 `DELETE FROM issue_fts; INSERT ... SELECT ... FROM issue WHERE is_deleted=0;`，会把软删记录从 FTS 清除。QA 实测：重建丢软删行且 **drift 自检返回 0（静默丢失）**。QA 追加实证：§7.3 同步触发器模板 `VALUES(new.id, NULL, ...)` 令 `owner_biz_id` **恒为 NULL**，与 §7.2「版本类 FTS 的 `owner_biz_id` = 主表 UUID」直接矛盾；`UPDATE issue SET id=新UUID` 后 FTS 残留旧 `biz_id` 且新 id 无 FTS 行。

**架构决策**：
1. **方案 A（审核人倾向方案）**：重建同步**全部记录（含软删）**，`INSERT ... SELECT` 不带 `WHERE is_deleted=0`，保留 `is_deleted` 镜像；一致性检查由「活跃行数差」改为**全量行数差**并扩为 **5 项**；R1 旧 SQL 明确作废；
2. **版本表 `owner_biz_id` 变体**：`NULL` 仅适用于 19 张非版本表；5 张版本表按 §7.7 的 24 行映射表取归属外键列，同步触发器模板与方案 A 重建 SQL 均给出可执行变体；
3. **业务主键 ID 不可变（数据库级）**：24 张内容表统一 `BEFORE UPDATE OF id ... WHEN old.id IS NOT new.id → RAISE(ABORT)`；版本表同时覆盖归属外键列；共 **24 个触发器**；
4. 三向同步触发器 `WHEN` 补 `old.id IS NOT new.id`（及版本表归属外键变化）作为**纵深防御**。

**DDL / 数据库级约束**（真值源 §7.3 / §7.6.1 / §7.7）：
```sql
-- ① 方案 A 重建（普通内容表；无 WHERE）
DELETE FROM issue_fts;
INSERT INTO issue_fts(biz_id, owner_biz_id, is_deleted, ref_no, title, description_md)
  SELECT id, NULL, is_deleted, ref_no, title, description_md FROM issue;
-- ② 方案 A 版本表变体：owner_biz_id 取归属外键，绝不为 NULL
DELETE FROM document_version_fts;
INSERT INTO document_version_fts(biz_id, owner_biz_id, is_deleted, extracted_text, notes, snapshot_json)
  SELECT id, document_id, is_deleted, extracted_text, notes, snapshot_json FROM document_version;
-- ③ 版本表同步触发器（owner = new.document_id；WHEN 纳入 id 与归属变化）
CREATE TRIGGER trg_document_version_fts_ai AFTER INSERT ON document_version BEGIN
  INSERT INTO document_version_fts(biz_id,owner_biz_id,is_deleted,extracted_text,notes,snapshot_json)
  VALUES(new.id,new.document_id,new.is_deleted,new.extracted_text,new.notes,new.snapshot_json);
END;
-- ④ 业务主键 / 归属不可变（24 张表按 §7.7 映射表生成）
CREATE TRIGGER trg_issue_id_immutable BEFORE UPDATE OF id ON issue
WHEN old.id IS NOT new.id
BEGIN SELECT RAISE(ABORT,'business primary key id immutable'); END;
CREATE TRIGGER trg_document_version_id_immutable
BEFORE UPDATE OF id, document_id ON document_version
WHEN old.id IS NOT new.id OR old.document_id IS NOT new.document_id
BEGIN SELECT RAISE(ABORT,'business primary key id immutable'); END;
-- ⑤ 一致性检查 5 项（节选）：全量行数差 / biz_id 孤儿 / 软删镜像逐行比对 / trigram 正向 / 重复 biz_id
SELECT (SELECT count(*) FROM issue) - (SELECT count(*) FROM issue_fts) AS drift;
SELECT f.biz_id FROM issue_fts f LEFT JOIN issue t ON t.id=f.biz_id WHERE t.id IS NULL;
SELECT biz_id, count(*) AS n FROM issue_fts GROUP BY biz_id HAVING count(*) > 1;
```

**正向测试（预期通过）**：方案 A 重建前后 FTS **3 行 / 1 条软删镜像一致**；版本表 `owner_biz_id` 恒等于归属主表 UUID、`owner_biz_id IS NULL` 行数为 **0**；重复 `biz_id` 检测正常态返回 **0 行**；trigram 已知样本命中。

**反向测试（预期被拒绝 / 被检出 / 被证明不一致）**：复现 R1 旧 SQL（带 `WHERE is_deleted=0`）重建后**仅 2 行**，证明状态不一致；`UPDATE issue SET id=新UUID` → `business primary key id immutable` ABORT；`UPDATE document_version SET document_id=...` → ABORT；人为插入重复 `biz_id` → 检测语句检出；§7.3 恒 `NULL` 旧模板被判定为缺陷并由变体取代。

**影响文档清单**：真值源 §7.2 / §7.3 / §7.5 / §7.6.1 / §7.7 / §8-G G3 / §8-J J4 / §12.1 / §0.2；《核心实体数据字典》§7.3；《版本及历史管理规范》§3 / R2 对齐小节；《统一数据模型总体设计》§5 / §7 / R2 对齐小节；R1《架构评审整改记录》§6 第 6 项标注「本 SQL 已被 R2 修订」；《架构决策记录》ADR-17；本文 §4 / §5。

### 2.6 P6 多态自检覆盖不完整 + 命名误导（ADR-16）

**问题与 R1 实测现象**：R1 的存储过程式命名自检（R1 L854 起，旧名已在真值源标注废弃）只演示部分类型：`object_link` / `source_reference` 仅 `issue` / `email`；`evidence_link` / `decision_link` / `action_measure_link` 仅 `issue`；`review_result_object` 仅 `ISSUE`。**未证明** `document_version` / `drawing_version` / `meeting_minutes` / `message` / `risk` / `task` / `knowledge_item` 等合法类型可检查。QA 实测 **4 类多态孤儿漏报**；且 `sp_` 前缀在 10 份 R1 文档出现 **30 次**，全文「存储过程 / 无原生 / 不支持存储过程」关键词命中 **0 处**，会让后续开发人员误以为可直接 `CALL`。

**架构决策**：
1. 明确定义为「**应用层执行的一组 SQL 自检语句集**」，改名 `check_polymorphic_refs`，**不是存储过程、不能 `CALL`**；全文统一替换，10 份 R2 文档头部均加醒目声明；
2. 给出完整的「引用字段 → 合法 type 值 → 目标表 → 自检 SQL」映射清单，覆盖**全部 8 类多态引用 / 10 个检测分支**：`object_link` 左右两侧、`source_reference` 的 traced / source、`evidence_link`、`decision_link`、`action_measure_link`、`review_result_object`、`business_subject_alias`、`object_dimension_tag`；`target` **23 类全集**；统一大写 type 值 + `UPPER(type)` 归一；`IS NULL` 反连接（不是 `NOT IN`）；非法 type 同样检出；
3. 每类声明「正常数据 → **0 行**；孤儿 / 非法 type → 必被检出且 `src` 为对应分支」的**双向验证**要求；执行时机为摄入作业完成后 + 定期维护 + 每次迁移 / 重建后，结果写 `audit_log`。

**DDL / 数据库级约束**：本项不新增 DDL（自检语句集属应用层补偿）。核心 SQL 见真值源 §7.6.2（`WITH target AS (...) ... LEFT JOIN ... WHERE t.id IS NULL`），扩展一致性检查见 §7.6.3（P2 / P3 / P7 / B4）。真值源保留 3 处 R1 旧名仅作「已废弃」说明语境，其余文档全部统一为新名。

**正向测试（预期通过）**：为 23 类合法 type 各写入至少 1 条真实目标数据 + 8 类引用字段的正常引用，自检 **10 个分支合计 0 行**；trigram / 映射正向控制有效（命中 0 时结果不可采信）。

**反向测试（预期被检出）**：注入 10 行孤儿 / 非法 type（`object_link` 左右、`source_reference` traced / source、`evidence_link`、`decision_link`、`action_measure_link`、`review_result_object`、`business_subject_alias`、`object_dimension_tag`）后 **10 个分支全部检出**；`ENTITY` 正常引用不误报、`ENTITY` 孤儿被 `q8` 检出。

**影响文档清单**：真值源 §7.6.2 / §7.6.3 / §8-G G7 / §8-J J5 / §12.1 / §12.3；《数据来源与证据追溯规范》§2 / §7；《核心实体数据字典》§0 / §7.3；《实体关系ER图》关系注第 9 条；《统一数据模型总体设计》§4 / R2 对齐小节；《待确认事项清单》#16；《架构决策记录》ADR-16；**全部 10 份 R2 文档头部命名声明**；本文 §4 / §5。

### 2.7 P7 可逆合并链缺少数据库级保护（ADR-18，独立条目）

**问题与 R1 实测现象**：`business_subject_merge`（R1 L458）只有 `CHECK(from_subject_id <> to_subject_id)`，无法阻止 A→B 且 B→A 循环、A 同时多个有效合并目标、A 合并到已合并的 B、`canonical_subject_id` 与有效合并关系不一致；R1 整改报告承认「合并守卫尚未纳入本轮」。QA 实测 **5/5 非法合并被接受**，并追加实证：撤销合并后 `from_subject.canonical_subject_id` 仍指向已撤销的规范主体、`status` 仍为 `MERGED`，**无触发器恢复**。

**架构决策**：**部分唯一索引 + 4 个触发器 + 事务**共同实现有效合并链唯一性（等价于 `WHERE is_undone=0` 的部分唯一索引语义，R1 无 `is_undone` 字段，沿用 `is_active`）：
1. `uq_bsm_active_from ... WHERE is_active=1`：一个来源主体同时最多一条有效合并；
2. `trg_bsm_guard_i`：目标必须是 `ACTIVE` 有效根、禁止目标已被合并、禁止多级链与循环；
3. `trg_bsm_apply_i`：合并时由数据库联动写 `from_subject.status='MERGED'` 与 `canonical_subject_id`；
4. `trg_bsm_guard_u`：撤销必须填齐撤销三字段、禁止篡改 `from/to`、禁止复活已撤销行、存在下游有效合并时禁止撤销；
5. `trg_bsm_apply_u`：撤销时由数据库联动**原子恢复** `status='ACTIVE'` 与 `canonical_subject_id=NULL`；
6. `canonical_subject_id` / `status` 与有效合并关系的一致性由 §7.6.3 P7 自检兜底检出。

**DDL / 数据库级约束**（以下为约束等价摘要；完整定义含 `updated_at` 联动列，以**真值源 §4** 为准，阶段 B 复跑请按真值源全文建表）：
```sql
CREATE UNIQUE INDEX uq_bsm_active_from
  ON business_subject_merge(from_subject_id) WHERE is_active = 1;

CREATE TRIGGER trg_bsm_guard_i BEFORE INSERT ON business_subject_merge
WHEN NEW.is_active = 1 AND (
       EXISTS(SELECT 1 FROM business_subject_merge m
              WHERE m.from_subject_id = NEW.to_subject_id AND m.is_active = 1)
    OR EXISTS(SELECT 1 FROM business_subject_merge m
              WHERE m.to_subject_id = NEW.from_subject_id AND m.is_active = 1)
    OR (SELECT status FROM business_subject WHERE id = NEW.to_subject_id) <> 'ACTIVE')
BEGIN SELECT RAISE(ABORT,'invalid merge: target must be an active root; no cycle / no multi-level chain'); END;

CREATE TRIGGER trg_bsm_apply_i AFTER INSERT ON business_subject_merge
WHEN NEW.is_active = 1
BEGIN
  UPDATE business_subject SET status='MERGED', canonical_subject_id=NEW.to_subject_id, updated_at=NEW.merged_at
   WHERE id = NEW.from_subject_id;
END;

CREATE TRIGGER trg_bsm_guard_u BEFORE UPDATE ON business_subject_merge
WHEN (OLD.from_subject_id IS NOT NEW.from_subject_id
   OR OLD.to_subject_id   IS NOT NEW.to_subject_id
   OR (OLD.is_active = 0 AND NEW.is_active = 1))
   OR (OLD.is_active = 1 AND NEW.is_active = 0 AND (
          NEW.undone_at IS NULL OR NEW.undone_by IS NULL OR NEW.undo_reason IS NULL
       OR EXISTS(SELECT 1 FROM business_subject_merge m
                 WHERE m.to_subject_id = OLD.from_subject_id AND m.is_active = 1 AND m.id <> OLD.id)))
BEGIN SELECT RAISE(ABORT,'invalid merge update/undo: chain would become inconsistent'); END;

CREATE TRIGGER trg_bsm_apply_u AFTER UPDATE OF is_active ON business_subject_merge
WHEN OLD.is_active = 1 AND NEW.is_active = 0
BEGIN
  UPDATE business_subject SET status='ACTIVE', canonical_subject_id=NULL, updated_at=NEW.undone_at
   WHERE id = NEW.from_subject_id
     AND NOT EXISTS(SELECT 1 FROM business_subject_merge m
                    WHERE m.from_subject_id = NEW.from_subject_id AND m.is_active = 1);
END;
-- 一致性自检（真值源 §7.6.3）：撤销后状态 / canonical 与有效合并关系不一致可被检出
SELECT bs.id FROM business_subject bs
LEFT JOIN business_subject_merge m ON m.from_subject_id = bs.id AND m.is_active = 1
WHERE (m.id IS NOT NULL AND (bs.status <> 'MERGED' OR bs.canonical_subject_id IS NOT m.to_subject_id))
   OR (m.id IS NULL AND (bs.status = 'MERGED' OR bs.canonical_subject_id IS NOT NULL));
```
> 新增 **4 个触发器 + 1 个部分唯一索引**，触发器计入 §0.2 的 126。

**正向测试（预期通过）**：合法链 A→B（A 变 MERGED 且 canonical=B）；合法链 C→B（多源合一）；先撤销下游 C→B 再撤销根链 A→B，每次撤销后对应主体 `status='ACTIVE'` 且 `canonical_subject_id=NULL`；撤销后可重新合法合并 A→B。

**反向测试（预期被拒绝 / 被检出）**：循环 B→A（A 非有效根）→ ABORT；合并到已合并的 A（非根）→ ABORT；A 同时多个有效目标 → `UNIQUE constraint failed`；自合并 → `CHECK constraint failed`；撤销缺 `undo_reason` → ABORT；篡改 `from` / `to` → ABORT；复活已撤销行 → ABORT；人为制造「撤销后 `status` / `canonical_subject_id` 不一致」→ 被一致性自检检出。

**影响文档清单**：真值源 §4 / §7.6.3 P7 / §8-J J6 / §12.1 / §0.2；《核心实体数据字典》§4 `business_subject_merge`；《版本及历史管理规范》§1 / R2 对齐小节；《实体关系ER图》关系注 R2-P7 补充；《统一数据模型总体设计》R2 对齐小节；R1《架构评审整改记录》§7 与《架构评审整改完成报告》实现期建议均标注「本结论已被 R2 修订」；《架构决策记录》ADR-18；本文 §4 / §5。

---

## 3. 四项实现边界结论（B1~B4，ADR-19）

### 3.1 B1 FTS / 触发器生成规则（不再只写「循环生成」）

**R1 实测现象**：只给出 1 张 FTS 虚表 + 3 个同步触发器的完整 DDL，其余 23 张 / 69 个只有清单，QA 阶段 A **无法逐表验证**。

**R2 结论**（真值源 §7.7，内存库实测可执行）：
1. **确定生成规则（6 条，无歧义）**：输入为 24 行映射；`biz_id` 恒取业务表 `id`、`is_deleted` 恒取业务表 `is_deleted`、`owner_biz_id` 对版本表取归属外键列 / 非版本表固定 `NULL`；FTS 虚表固定列序 `[biz_id UNINDEXED, owner_biz_id UNINDEXED, is_deleted UNINDEXED, <文本列...>, tokenize='trigram']`；每行生成 1 张虚表 + 3 个同步触发器 + 1 个不可变触发器；禁物理删除 20 张按 §8-H 清单生成 `trg_<表>_no_delete`；**禁止**任何凭空补列 / 猜列逻辑。
2. **24 行逐表字段映射表**（真值源 §7.7）：逐行给出「业务表 / FTS 表 / `biz_id` / `owner_biz_id` / `is_deleted` / 文本列清单 / 是否版本表」。5 张版本表为 `document_version`（`document_id`）、`drawing_version`（`drawing_id`）、`meeting_minutes`（`meeting_id`）、`knowledge_version`（`knowledge_item_id`）、`plan_activity_version`（`activity_id`）。
3. **生成结果核验方法**（可执行 SQL）：对象计数（`PRAGMA table_list` + `name NOT LIKE 'sqlite_%'`）、命名分组计数（`%_fts_ai` / `_au` / `_ad` / `_id_immutable` / `_no_delete` 分别期望 24 / 24 / 24 / 24 / 20）、逐表 `PRAGMA table_info(<fts表>)` 列序比对、`PRAGMA foreign_key_check` / `integrity_check`、方案 A 重建 + 5 项一致性 + `check_polymorphic_refs`。
4. **实测结果**：生成 24 虚表 / 72 同步 / 24 不可变 / 20 禁删除 = **116** 个模板化触发器，加 10 个专用触发器（基线冻结 2 + 抽取不可变 2 + 审核证据 2 + 合并链 4）= **126**；24 行字段映射逐表比对 **0 差异**。
5. **双口径与 E5**：统计表区分「文档显式 DDL（2 虚表 / 19 触发器）」与「迁移生成后对象（24 / 126）」；普通表计数须用 `PRAGMA table_list WHERE type='table' AND name NOT LIKE 'sqlite_%'`，一次排除 `sqlite_schema` 与 `sqlite_temp_schema` 两张系统目录表（只排除前者得 76 而非 75，QA 实测 E5）。

### 3.2 B2 `biz_id` 无唯一约束

**R2 结论**：FTS5 虚表**不支持** UNIQUE / `CREATE INDEX`；`biz_id` 唯一性由「主表 `id` 主键（`uuid4().hex` + UUID CHECK）＋ 三向同步触发器（INSERT 一次 / UPDATE 先删后插 / DELETE 删除）」共同保证；另给可执行重复 `biz_id` 检测语句（真值源 §7.6.1 ⑤ `GROUP BY biz_id HAVING count(*) > 1`），正常态 0 行、人为插入重复行可检出（§8-J 实测）。

### 3.3 B3 缺完整 FK 字段逐字段裁定

| 字段 | 裁定 | R2 处置 |
|---|---|---|
| `baseline_switch_log.from_baseline_id` / `to_baseline_id` | **遗漏** | 补共享 `plan_id` 的复合 FK 指向 `baseline_version(plan_id, id)`；`from` 可空（首次切换） |
| `baseline_switch_log.audit_log_id` | **遗漏** | 补 `REFERENCES audit_log(id)` |
| `baseline_switch_log.switched_by`、`baseline_version.approved_by`、`plan_active_baseline.switched_by` | **遗漏** | 补 `REFERENCES person(id)`（B4 口径） |
| `business_subject_merge.merged_by` / `undone_by` | **遗漏** | 补 `REFERENCES person(id)`（B4 口径） |
| 三张 `*_status_history.changed_by` | **遗漏** | 补 `REFERENCES person(id)`（B4 口径）；**QA 阶段 B 补强核验 S5-1 曾实测未落地，架构侧已补 DDL 闭环** |
| `audit_log.actor_id` | **有意保留的多态** | 按 `actor_type` 分派：USER→`person.id` / AI→`ai_analysis_run.id` / SYSTEM→`NULL`；纳入 `check_polymorphic_refs` 分派规则 |
| `object_dimension_tag.value_id`、`ingestion_job.source_id`、`email.from_addr` | **有意保留的多态 / 可选 / 自由文本** | 按 `value_type` / `source_type` 分派并纳入自检；自由文本字段不做 FK |

### 3.4 B4 人员 ID 口径统一

**R2 结论**：`reviewer_person_id` / `switched_by` / `changed_by` / `merged_by` / `undone_by` / `approved_by` / `owner_person_id` / `assignee_person_id` / `sender_person_id` 一律为 **`person.id` 的 32 位小写 hex UUID**（`REFERENCES person(id)` + `CHECK(length(id)=32 AND id NOT GLOB '*[^0-9a-f]*')`），禁止姓名 / 自由文本；可空时 `NULL` = SYSTEM/AI 执行且必须写 `audit_log`；格式规范性由 §7.6.3 B4 自检兜底。

**正 / 反向测试**：正向——合法 `person.id` 写入 `merged_by` / `changed_by` 成功，`NULL` 表示 SYSTEM/AI；反向——填姓名被 FK 拒绝、非法格式 `person.id` 被 UUID CHECK 拒绝。

**QA 阶段 B 补强核验（S5-1 / S5-2）**：曾实测三张 `*_status_history.changed_by` 无 FK、`person.id` 无 UUID CHECK，导致上述两类反向用例被 ACCEPTED（首轮未 seed 完整时甚至因 `issue_id` / `organization_id` 指向不存在行而假阳性 REJECTED）。架构侧决策选「**补 DDL**」而非「改文档迁就弱约束」：三张表补 `REFERENCES person(id)`、`person.id` 补 UUID CHECK，并同步真值源 §0.3 / §9 / §12.2 / §12.3 / §8-J J8、数据字典、ADR-19 与本文档；由 `r2_doc_compile.py` 按文档原文编译 + 行为断言验证，**B4 专项回归由 QA 另行执行，不与本次七项复跑混计轮次**。

---

## 4. QA 阶段 A 追加冲突的处置（超出复审原文但影响决策）

| # | QA 发现 | R2 处置 | 落点 |
|---|---|---|---|
| Q1 | `measure_type='RISK_RESPONSE'` 挂 `issue_id` 被接受；`action_measure_link.ref_id` 孤儿被接受 | 新增 `measure_type` 语义 CHECK；link 孤儿由 `q7` 必然检出（非硬 FK） | 本文 §2.2 / ADR-14 |
| Q2 | §7.3 模板 `owner_biz_id` 恒 NULL 与 §7.2 矛盾 | `NULL` 仅限 19 张非版本表；5 张版本表按映射表取归属列，给出模板 / 重建变体 | 本文 §2.5 / ADR-17 |
| Q3 | `UPDATE issue SET id=新UUID` 后 FTS 残留旧 `biz_id` | 24 个 `BEFORE UPDATE OF id ... RAISE(ABORT)` + 同步触发器 `WHEN` 补 `old.id IS NOT new.id` | 本文 §2.5 / ADR-17 |
| Q4 | 撤销合并后 `canonical_subject_id` / `status` 不恢复 | `trg_bsm_apply_u` 原子恢复；`trg_bsm_guard_u` 约束撤销事务；一致性自检兜底 | 本文 §2.7 / ADR-18 |
| Q5 | `review_result_object('ENTITY')` 合法性未定义 | 明确为合法类型，纳入 P6 `q8`；不加禁止 CHECK、不改 DDL | 本文 §2.4 / ADR-16 |
| Q6 | `sp_` 旧名 30 次、全文 0 处「存储过程」声明 | 改名 `check_polymorphic_refs`；10 份 R2 文档头部统一醒目声明 | 本文 §2.6 / ADR-16 |
| Q7 | 只有 1 张 FTS + 3 触发器完整 DDL，23 张 / 69 个无法逐表验证 | §7.7 给出 24 行映射 + 确定生成规则 + 生成结果核验 SQL | 本文 §3.1 / ADR-19 |
| Q8 | E5：只排除 `sqlite_schema` 会得 76 而非 75 | 统一 `name NOT LIKE 'sqlite_%'` 口径；统计表区分显式 / 生成后对象 | 本文 §3.1 / 真值源 §0.2 / §8-I |

---

## 5. 文档同步清单

| # | 文档 | R2 处置 |
|---|---|---|
| 1 | `Phase1.2_数据库表结构设计.md`（唯一真值源） | §0~§8 / §12 全面修订：7 项约束、方案 A、24 行映射、完整自检、统计 126、§8-I 双口径、§8-J 自检汇总 |
| 2 | `Phase1.2_核心实体数据字典.md` | 统计 126；P1 复合 FK / P2 属主与语义 CHECK / P3 证据 / P5 版本表变体与不可变触发器 / P7 合并守卫 / B3·B4 人员 FK；R2 对齐修订表 |
| 3 | `Phase1.2_实体关系ER图.md` | 统计 126；P1 复合 FK 关系补充；P2 附加属主；P3 证据必填；P4 ENTITY 合法；P6 全类型映射；P7 合并守卫；命名声明 |
| 4 | `Phase1.2_架构决策记录.md` | **新增 R2 章节 ADR-13~19**，其中 P2 / P3 / P5 / P7 为四条独立条目（决策 / 备选方案 / 理由 / 影响文档 / 正反向测试 / 状态）；新增「R2 整改对 ADR 的影响汇总」表 |
| 5 | `Phase1.2_数据来源与证据追溯规范.md` | §1 重写（P4 双层结构 + Mermaid）；P3 证据必填；P6 完整映射与非存储过程声明；P2 对齐段；统计 126 |
| 6 | `Phase1.2_版本及历史管理规范.md` | 统计 126；P7 撤销守卫与状态恢复；P5 不可变触发器；追加 R2 对齐小节 |
| 7 | `Phase1.2_统一数据模型总体设计.md` | 统计 126；P5 方案 A 与 5 项一致性（替换 R1 的 4 项 / 活跃行数差）；N 项收敛说明；追加 R2 对齐小节 |
| 8 | `Phase1.2_待确认事项清单.md` | 统计 126；当前状态改 R2；#16 自检描述改 R2；N6 标注 R2 部分收敛；迁移策略补方案 A / 5 项 |
| 9 | `Phase1.2_架构评审整改记录.md`（R1） | 开头加「R2 承接说明」，**保留 R1 正文**；重建 SQL / 属主表述 / 合并守卫 / 编译统计四处标注「本结论已被 R2 修订」 |
| 10 | `Phase1.2_架构评审整改完成报告.md`（R1） | 开头加「R2 承接说明」，保留 R1 正文；状态行 / 统计表 / 触发器行 / 实现期建议四处标注「本结论已被 R2 修订」 |
| 11 | `Phase1.2_R2_架构评审整改记录.md`（新增） | 本文 |
| 12 | `Phase1.2_R2_架构评审整改完成报告.md`（新增） | 总览 / 七项复核表 / 统计 / 验证依据 / 边界声明 / 遗留事项 / 待审核声明 |
| — | `09_Archive/Phase1.2_R1_原稿/`（归档副本） | **不修改**；按 `.gitignore` 不入库 |
| — | `Phase1.2_数据模型设计任务书.md`、`Phase1.2_设计阶段完成报告.md`（历史阶段文档） | **不改正文**；数字仅描述其当时版本，口径声明见 R2 完成报告 |
| — | `Phase1.2_数据来源与证据追溯规范.zip`（18 份 R1 文档，未跟踪） | **不提交、不声称入库** |

> 全文统一 **R2 标记与统计口径 75 / 24 / 126 / 视图 0**；不得出现任何宣称整改已整体通过 / 全部闭环的结论（与复审结论冲突）。R1 正文中保留的「96」「已作废」等历史数字均带明确「R1 口径 / 本结论已被 R2 修订」标注。

---

## 6. 正 / 反向测试用例总表

| 分组 | 覆盖 | 正向（预期通过） | 反向（预期被拒绝 / 被检出） |
|---|---|---|---|
| J1 / P1 | 3 个 `UNIQUE(plan_id,id)` 父键 + 7 张子表复合 FK | 6 类同计划对象插入成功 | 7 项跨计划写入全部被 `FOREIGN KEY constraint failed` 拒绝 |
| J2 / P2 | XOR + `measure_type` 语义 CHECK + link + `q7` | 恰好 1 主属主且类型匹配 + 2 条合法附加属主 | 双 / 零主属主、两类错挂被 CHECK 拒绝；link 孤儿被 `q7` 检出；主属主重复登记被自检检出 |
| J3 / P3 | `NOT NULL` + FK + 2 触发器 | 有效证据写入成功 | 空证据 / 证据不存在 / 证据已软删 / UPDATE 换软删证据 / 事后软删自检 |
| J4 / P5 | 方案 A 全量重建（含版本表变体）+ 5 项一致性 + 24 不可变触发器 | 重建前后 3 行 / 1 软删镜像一致；版本表 `owner_biz_id` = 归属 UUID；重复 `biz_id` 检测 0 行 | 复现 R1 旧 SQL 重建后仅 2 行；`UPDATE id` / 归属变更被 ABORT；恒 NULL 旧模板被取代 |
| J5 / P6 | 23 类 `target` 全集 + 8 类引用 / 10 分支 | 正常数据 10 分支合计 0 行；`ENTITY` 正常引用不误报 | 注入 10 行孤儿 / 非法 type 后 10 分支全部检出；`ENTITY` 孤儿被 `q8` 检出 |
| J6 / P7 | 部分唯一索引 + 4 触发器 | 合法链 A→B / C→B、撤销联动状态恢复、撤销后重新合并 | 循环 / 合并到非根 / 多目标 / 自合并 / 撤销缺字段 / 篡改 from-to / 复活已撤销 / 状态不一致 |
| J7 / B1 | 24 行映射 + 确定规则 + 核验 SQL | 生成 24 虚表 / 72 同步 / 24 不可变 / 20 禁删除 = 116，加 10 专用 = 126；字段映射 0 差异 | — |
| J8 / B3+B4 | 全部审计责任人 FK + `person.id` UUID CHECK（含三张 `*_status_history.changed_by`，QA 补强核验后补齐） | `merged_by` / `undone_by` / `changed_by` 为合法 `person.id` 或 NULL | 填姓名被 FK 拒绝（含三张状态历史表）；非法格式 `person.id` 被 UUID CHECK 拒绝 |
| J9 / E5 | `PRAGMA table_list` 统计口径 | `name NOT LIKE 'sqlite_%'` 一次排除两张系统目录表 | 只排除 `sqlite_schema` 会多计 1 张（76 而非 75） |

> 每项问题**至少 1 个正向 + 1 个反向用例**；预期「被拒绝」的用例均由数据库约束 / 触发器 / 可执行自检 SQL 实现，不依赖应用层约定。

---

## 7. 内存库自检结果

| 项目 | 结果 |
|---|---|
| 环境 | Python 3.13 / `sqlite3.connect(':memory:')` / **SQLite 3.53.1**；每连接单独 `PRAGMA foreign_keys=ON` |
| 行为自检（编译 + 正向 + 反向 + QA 追加 + E5） | **129 项 PASS / 0 FAIL** |
| 按真值源 SQL 代码块提取的 `CREATE` 语句 | **133** 条全部编译通过，执行失败 **0**（75 `CREATE TABLE` + 2 FTS 虚表 + 19 显式触发器 + 37 显式索引） |
| 完整自检 SQL / 方案 A 重建 SQL | 单独执行通过；正常态返回 0 行 |
| 按 §7.7 生成规则循环生成 | 24 张 FTS 虚表 / 116 模板化触发器 + 10 专用 = **126**；24 行字段映射比对 **0 差异** |
| `PRAGMA foreign_key_check` / `integrity_check` | 无违规 / `ok` |
| B4 专项核验（QA 阶段 B 补强核验 S5-1 / S5-2） | 按**文档原文 DDL** 静态确认 `person.id` UUID CHECK 与三张 `*_status_history.changed_by → person(id)` FK 全部存在；行为断言非法格式 `person.id` 被 `CHECK constraint failed: length(id)=32 AND id NOT GLOB '*[^0-9a-f]*'` 拒绝（拒绝原因正确）；`r2_doc_compile.py` 输出 **PASS** |
| 脚本位置 | 仅操作系统临时目录（`r2_selfcheck.py` / `r2_doc_compile.py` / `r2_sync_docs*.py` / `r2_b4_fix.py`），**未写入项目目录** |

---

## 8. 边界声明与状态

- **未创建** `01_Data/migrations/001_init.sql` 或任何 `.sql` 迁移文件；**未对** `01_Data/epcs_intelligence.db` 执行任何 DDL/DML；**空库保持**（业务表 0）。
- **未导入**任何资料；**未接入**外部账号 / Ollama / DWG SDK；**未改动**旧知识库；**未回改**归档副本；**未执行 git commit**。
- **R1 原稿** = Git commit `7ac25c3` + 本地 `09_Archive/Phase1.2_R1_原稿/`（按 `.gitignore` 不入库）；R2 **只做新提交、不 amend / 不 force push**。
- **当前状态：R2 定向整改完成，等待系统架构师再次审核**；QA 阶段 B 已用同一套用例换 R2 DDL 复跑，据 QA 回传与本文 129 项预期全部对表一致、无复跑不一致（正式结论以主理人汇编为准）；Phase 1.3（幂等迁移 + 空库升级）需另行批准。
- 总览、七项复核表、统计口径、验证依据、遗留事项与待审核声明见《Phase1.2_R2_架构评审整改完成报告.md》。
