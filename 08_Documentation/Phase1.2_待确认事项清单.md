# Phase1.2 待确认事项清单

> R1 整改同步：2026-11-12，以《Phase1.2_数据库表结构设计.md》(R1) 为唯一真值源
> 明确哪些设计**已定**（本阶段可直接采用）、哪些**未定**（建模已留接口，需人工/后续确认）。不隐瞒未决项。

## 1. 已确定项（产品既定 + 架构定案，可直接作为实现依据）

| # | 事项 | 来源 | 决策要点 |
|---|---|---|---|
| 1 | 6 大核心数据域及对象清单 | A 节 | 域与对象表已列 |
| 2 | 对象间基数 | A 节 | 见 ER 图 |
| 3 | 项目承载一艘主造对象、多合同不强实体 | B.1/ADR-1 | `project.main_object_entity_id` + `project_member.is_contract_carrier` |
| 4 | EPCS 阶段为时间纵轴、与专业/区域/系统正交且标签化 | B.2/ADR-2 | `object_dimension_tag` |
| 5 | 各类 M:N 多对多（问题↔多来源；一文件被多事项引用） | B.3/B.4/ADR-4/5 | `object_link` + `source_reference` |
| 6 | **业务实体 / 业务事项双层归一 + `business_subject` + 可逆 `business_subject_merge` + AI 先入 ReviewQueue 四表链** | B.5/ADR-6（R1-4/R1-5 修订） | `entity`/`entity_alias`/`entity_identifier`/`entity_relationship` 只管业务实体；`business_subject` + `business_subject_alias` + `business_subject_merge` + `business_subject_source` 管事项；审核链为 `review_queue` / `review_extraction_link` / `review_decision` / `review_result_object` 四表；**`entity_relationship` 不再承担事项合并**（原结论作废） |
| 7 | 问题状态机（含退回/重开） | B.6 | 状态历史表 + 应用层校验 |
| 8 | **批准基线状态分离只读：`plan_active_baseline` + `baseline_switch_log` + 无差别冻结 + `plan_activity_version` 逐版本快照** | B.7/ADR-8（R1-1/R1-2 修订） | 删除 `UNIQUE(plan_id,is_active)` 与 `is_active` 字段；`trg_bl_freeze_u/d` 无差别冻结 `baseline_version`；切换走应用层单事务、全程不触碰基线行；`plan_activity_version` 每版本属性快照 + `change_type` |
| 9 | 信息性质六层枚举与自动/人工边界 | B.8/ADR-7 | `info_nature` + `system_config` 双轨 |
| 10 | G1~G7 全局约束 | 全局 | 已落实到表设计与索引策略 |
| 11 | **SQLite FTS5 trigram + 统一普通内容表 + `biz_id UNINDEXED` 显式映射 + 24 张 FTS 三向触发器 + 短词 LIKE 回退** | 实测/ADR-7b（R1-3 修订） | 全库不再用外部内容表；索引全部历史版本；软删保留 FTS 行 + `is_deleted` 镜像；含 `-`/`/` 查询词须整体双引号包裹；<3 字短词 MATCH 恒 0 → LIKE 回退 + 别名表短词等值召回（原「外部内容表 + 触发器同步」结论作废） |
| 12 | 范围外（本阶段不做） | 任务书/隔离说明 | 业务功能/迁移/SDK/接入/权限功能——后续 Phase |
| 13 | **R1 六项整改定案** | R1-1~R1-6 | ① 基线状态分离（R1-1）② 计划活动版本化（R1-2）③ FTS 统一范式（R1-3）④ Entity/业务事项分层（R1-4）⑤ ReviewQueue 四表审核链（R1-5）⑥ 数据字典/ER/SQL 三方一致（R1-6）；详见《架构评审整改记录》§1~§6 |
| 14 | **统一对象数量统计口径** | 《表结构设计》§0.2 | 实体表 **75**（业务主表 46 + 辅助 29）、FTS5 虚拟表 **24**、触发器 **96**（FTS 同步 72 + 基线冻结 2 + 抽取不可变 2 + 禁物理删除 20）、视图 **0**；8 份文档一律引用同一统计表 |
| 15 | **公共字段基线 A/B** | R1-6 / 《表结构设计》§0.3 | 基线 A（正式业务表）：`id, project_id, info_nature, created_at, updated_at, created_by, updated_by, is_deleted, deleted_at, del_status`；基线 B（辅助/关联/桥/历史/日志表）：`id, created_at, is_deleted`；逐表标注，SQL 与数据字典严格对应 |
| 16 | **`sp_check_polymorphic_refs` 多态引用孤儿自检** | R1-6 / 《表结构设计》§7.6 | 按 `type` 分派 UNION 查询，覆盖 `source_reference`/`object_link`/`evidence_link`/`decision_link`/`action_measure_link`/`review_result_object`/`business_subject_alias`/`object_dimension_tag` 八类；摄入作业后 + 定期维护执行，结果写 `audit_log`；已知取舍，非硬 FK |
| 17 | **`PRAGMA foreign_keys=ON` 按连接生效** | 《表结构设计》§0.1 / 《整改记录》§8 第 7 项 | SQLite 该 PRAGMA 按连接生效（实测：连接 A 开启后，新连接 B 仍为 0 且外键失效）；Python `sqlite3.connect()` 后必须逐连接执行，写入连接工厂规范与迁移脚本首行 |

## 2. 未定项（已备接口，需人工/后续确认）

| # | 事项 | 现状 | 建模已留接口 / 决策影响 | 责任归属 | 来源 |
|---|---|---|---|---|---|
| 1 | 授权的真实邮件正文读取边界与脱敏粒度 | D.2-1 | `email.body_markdown` 按隔离边界授权写；脱敏粒度待定 | 数据合规/接入 Phase | D.2-1 |
| 2 | 用户/角色/权限具体角色清单 | D.2-2 | `user/role/permission` 表骨架预留；启用 Phase 定清单 | 产品/Phase 后期 | D.2-2 |
| 3 | 设备分类树（Equipment taxonomy）层级标准 | D.2-3 | `equipment_category` 自引用树；船级社 vs 自建未锁 | 领域专家 | D.2-3 |
| 4 | 外部企业编码/ERP 编号映射协议 | D.2-4 | `entity_identifier(id_type/source_from)` 真实来源清单 | 集成 Phase | D.2-4 |
| 5 | 计划粒度 L1~L4 字段规范与周期 | D.2-5 | `plan.level` 通用，无 L 专用表 | 计划管理 Phase | D.2-5 |
| 6 | 知识沉淀判定细则 | D.2-6 | `knowledge_item`+`version` 可沉淀可版本；判定规则后补 | 知识管理 Phase | D.2-6 |
| 7 | 快照粒度（全量 vs 增量资产） | ADR-9 | `snapshot_json` 渐进；成本边界待定 | 架构/实现评审 | ADR-9 |
| 8 | FTS 同步策略（触发器 vs 定时重建） | ADR-7b | 一期触发器；二期摄入高频时切换 | 架构/实现 | ADR-7b |
| 9 | 计划/风险/问题业务管理功能何时开发 | 任务书§五 | 后续 Phase | 产品 | 任务书§五 |
| N1 | 基线切换的授权角色与审批流（依赖 D.2-2 角色清单） | R1 新增 | `plan_active_baseline.authorization_ref` / `baseline_switch_log.switched_by` 已留授权与审计字段 | 产品/权限 Phase | R1-1 |
| N2 | 切换日志/审计留存期 | R1 新增 | `baseline_switch_log` / `audit_log` 已留全量记录 | 架构 | R1-1 |
| N3 | 短词检索 LIKE 回退的性能阈值与候选集范围；二期是否物化 `short_term_index` | R1 新增 | 一期已定 LIKE 回退 + 别名表短词召回；阈值与二期物化表待评估 | 架构/实现 | R1-3 |
| N4 | 软删 FTS 行「保留+过滤」vs「移除」的最终取舍（本轮定保留，需实测容量后确认） | R1 新增 | 本轮定「保留 + `is_deleted` 镜像 + 查询过滤」，容量实测后确认 | 架构 | R1-3 |
| N5 | 全部历史版本入 FTS 的存储放大评估 | R1 新增 | 24 张 FTS 中版本类索引全部历史版本，存储放大待评估 | 实现评审 | R1-3 |
| N6 | `business_subject_merge` 撤销后历史引用重指向策略 | R1 新增 | 撤销字段 `undone_at/undone_by/undo_reason/is_active` 已留；历史引用重指向策略待定 | 产品/架构 | R1-4 |
| N7 | `subject_kind` / `review_result_object.object_type` 枚举扩展流程 | R1 新增 | 两处 `CHECK` 枚举已定；扩展流程待定 | 架构 | R1-4/R1-5 |
| N8 | `department` 与 `organization.parent_id` 的职责边界（部门 vs 上下级单位） | R1 新增 | `department` 已建表并与 `organization.parent_id` 职责分离；边界细则待定 | 领域专家 | R1-6 |
| N9 | 公共字段基线 A/B 的最终裁剪清单 | R1 新增 | 基线 A/B 已逐表标注；最终裁剪清单待定 | 实现评审 | R1-6 |
| N10 | `plan_activity_version` 工作量单位与进度口径标准 | R1 新增 | `workload_qty/workload_unit/progress_measure` 字段已留；单位与口径待定 | 计划管理 Phase | R1-2 |

## 3. 未决风险提示（不隐瞒，R1 修订）

- **多态引用完整性**：`object_link` / `source_reference` 等 8 类多态字段用 `type+id` 而非硬 FK，数据库缺外键保障。R1-6 已新增 `sp_check_polymorphic_refs`（按 type 分派 UNION 查孤儿，摄入后 + 定期运行，结果写 `audit_log`），形成「`sp_check_polymorphic_refs` 可执行自检 + 应用层校验 + 审计留痕」三层补偿；**仍非数据库硬约束，此为已知取舍**，不伪装成 FK 级完整性。
- **基线只读联动**：原「触发器仅拦 `baseline_version` 单表，若未来经 `plan_version` 改基线内容需补联动」的风险，**已由状态分离（`plan_active_baseline` + `baseline_switch_log`）+ `baseline_version` 无差别全字段冻结（`trg_bl_freeze_u/d`）+ `baseline_version.plan_version_id` 明确指向完整计划版本（含 `plan_activity_version` 活动集）解决**；切换全程不触碰 `baseline_version`，六个基线测试案例实测全 PASS。ADR-8 已修订，原提示作废。
- **SQLite→PostgreSQL 适配（R1《整改记录》§8 第 10 项 / 《表结构设计》§10.3 清单要点）**：
  - `FTS5 trigram` → `pg_trgm` + GIN 索引 / `tsvector` 生成列（检索层需重写）；`biz_id/owner_biz_id/is_deleted UNINDEXED` 改普通列 + 触发器维护 tsvector。
  - `RAISE(ABORT, ...)` → PL/pgSQL `RAISE EXCEPTION`（20+2+2 个触发器改写为 trigger function）。
  - 部分唯一索引 `WHERE` / 表达式唯一索引 `COALESCE` → Pg 语法基本一致；`UNINDEXED` 列语义等价。
  - `PRAGMA journal_mode=WAL` / `PRAGMA foreign_keys=ON` 在 Pg **不适用**（Pg 用 MVCC、外键默认强制，无需逐连接设置）；一期仍统一 `char(32)` UUID + ISO8601 文本时间，为迁移保留转换面（`TEXT char(32)+CHECK`→`uuid`、ISO8601→`timestamptz`、`INTEGER 0/1`→`boolean`）。
  - **外键建表顺序需拓扑排序**：SQLite 允许 FK 引用后置表（实测 PASS），Pg DDL 立即校验目标表存在，迁移时须按依赖重排。

## 4. 建议的下一步（R1 整改后）

1. **当前状态：R1 整改完成，等待系统架构师再次审核**。本轮已按初审六项建表阻断问题完成定向整改（《架构评审整改记录》R1-1~R1-6），整改结论以《Phase1.2_数据库表结构设计.md》(R1) 为唯一真值源。
2. §1 已确定项（含 R1 新增 #13~#17 定案）经产品/架构归档为**锁定基线**；§2 未定项（D.2 原 9 项 + R1 新增 N1~N10）逐项挂责任人跟踪。
3. **审核通过后**，才由工程实现 `migrations/001_init.sql`（**幂等**：不只 `IF NOT EXISTS`，还含 `PRAGMA table_info` 逐列比对、索引/触发器/FTS 清单比对、`schema_version.ddl_fingerprint` 结构一致性检查、单事务失败回滚、FTS 重建与一致性自检）+ 空库升级（`01_Data/epcs_intelligence.db`，**不含业务数据**）。
4. **本阶段严格边界（已确认）**：未创建/执行任何迁移 SQL、未改数据库、未装 SDK、未接入外部渠道、未读取真实邮件或旧知识库数据；Phase 1.3（幂等迁移 + 空库升级 / 业务功能 / SDK 选型）需另行批准。

---

## R1 整改同步说明

本轮依据《Phase1.2_数据库表结构设计.md》(R1，唯一真值源) 与《Phase1.2_架构评审整改记录.md》(R1) 做定向修订：

- **统一统计口径**：实体表 **75**（业务主表 46 + 辅助 29）、FTS5 虚拟表 **24**、触发器 **96**、视图 **0**。
- **§1 已确定项**：改写 #6（双层归一 + `business_subject` + 可逆合并 + 四表审核链，`entity_relationship` 不再承担事项合并）、#8（基线状态分离只读）、#11（FTS5 统一普通内容表 + `biz_id` 显式映射 + 24 张 FTS + 短词回退）；新增 #13~#17（R1 六项整改定案、统一统计、公共字段基线 A/B、`sp_check_polymorphic_refs` 自检、`PRAGMA foreign_keys=ON` 按连接生效）。
- **§2 未定项**：新增 N1~N10 十行（事项/责任照抄《整改记录》§10），新增「来源」列标注 R1-1~R1-6。
- **§3 未决风险**：多态引用风险改为「自检 + 应用层 + 审计三层补偿，已知取舍、非硬约束」；基线只读风险改为「状态分离 + 无差别冻结 + 指向完整版本，已解决，原提示作废」；SQLite→PostgreSQL 补 §10.3 适配清单要点。
- **§4 下一步**：明确「R1 整改完成、等待系统架构师再次审核」；审核通过后才实现幂等 `migrations/001_init.sql` + 空库升级（不含业务数据）；强调本阶段未创建/执行任何迁移、未改数据库、未装 SDK、未接入外部渠道。
- **边界**：本阶段未执行任何 git 操作（由主理人统一提交）、未触碰 `01_Data/epcs_intelligence.db`。
