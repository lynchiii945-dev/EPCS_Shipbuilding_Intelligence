# Phase1.2 设计阶段完成报告

> 项目：EPCS Shipbuilding Intelligence
> 阶段：Phase 1.2 — 统一数据模型与实体关系设计
> 日期：2026-11-12 　交付负责人：齐活林（软件团队主理人）
> 前置：Phase 0 环境审计通过 → Phase 1.1 项目空间初始化完成 → 本阶段基于产品经理《业务对象确认书》与架构师《统一数据模型设计》8 份文档产出。

---

## 1. 设计成果清单

| # | 文档 | 路径 | 说明 |
|---|---|---|---|
| 输入 | 业务对象确认书 | `08_Documentation/Phase1.2_业务对象确认_PM.md` | 产品经理许清楚产出（6 数据域 + 8 业务规则 + OQ1~7 + D2） |
| 1 | 统一数据模型总体设计 | `08_Documentation/Phase1.2_统一数据模型总体设计.md` | 8 条设计原则 + 全局规则 + 12 架构问题解答 |
| 2 | 核心实体数据字典 | `08_Documentation/Phase1.2_核心实体数据字典.md` | ~50 张表：用途/主键/外键/字段/索引/约束 |
| 3 | 实体关系 ER 图 | `08_Documentation/Phase1.2_实体关系ER图.md` | Mermaid ER，明确 1:1/1:N/M:N |
| 4 | 数据库表结构设计 | `08_Documentation/Phase1.2_数据库表结构设计.md` | 完整 CREATE TABLE 草案 + FTS5 trigram + 触发器 |
| 5 | 数据来源与证据追溯规范 | `08_Documentation/Phase1.2_数据来源与证据追溯规范.md` | 统一来源引用 `source_reference` + `evidence` |
| 6 | 版本及历史管理规范 | `08_Documentation/Phase1.2_版本及历史管理规范.md` | 基线只读、三态删除、状态历史 |
| 7 | 架构决策记录 | `08_Documentation/Phase1.2_架构决策记录.md` | OQ-1~7 + 12 问题 ADR + 类图/时序图 |
| 8 | 待确认事项清单 | `08_Documentation/Phase1.2_待确认事项清单.md` | 已定 12 项 / 未定 9 项 / 风险 3 项 |

## 2. 核心设计决策

- **全局规则**：主键 UUID；公共基字段含 `info_nature`(六层信息性质) + 软删三态(ACTIVE/ARCHIVED/DELETED)；时间区分 event/source/created/updated/valid；正式记录禁物理删除（触发器）。全文表 FTS5 trigram（实测中文必需）。
- **六大数据域**：项目与组织 / 计划管理 / 信息与文件 / 问题·风险·任务闭环 / 实体关系与知识 / AI 处理与治理。
- **关键 ADR**：
  - ADR-1 合同不强实体（`project.main_object_entity_id` + `project_member.is_contract_carrier`）
  - ADR-2 EPCS 阶段与专业/区域/系统正交、`object_dimension_tag` 标签化
  - ADR-6 全局实体标识 + `extraction_result→review_queue→entity` 合并链防重复
  - ADR-7 AI 与人工分层（AI_INFERENCE→ReviewQueue→人工→CONFIRMED_FACT）
  - ADR-8 基线只读：`is_active` 部分唯一索引 + 触发器/应用层/审计三重防御
  - ADR-10 DWG 预留 `drawing_object`（不装 SDK、不解析）

## 3. 一致性检查结果（按任务书完成）

| 检查项 | 结果 |
|---|---|
| 文档间一致性 | ✅ 8 份文档表名/字段名统一（core 表 4/4 一致） |
| 实体/字段命名冲突 | ✅ 统一 snake_case，单数表名，无冲突 |
| 重复实体/多余表 | ✅ 依托 ER 图核验无冗余（Milestone 作 PlanActivity 子类型，不重复建表） |
| 多项目+EPCS 全阶段支持 | ✅ 全局 G1~G7 + 阶段正交标签化 |
| 关键记录可追溯来源 | ✅ 统一 `source_reference` + `evidence` 全链路 |
| 检索中文可用 | ✅ FTS5 trigram（实测命中，基于 Phase 0 结论） |

## 4. 已定 vs 未定

- **已定（12 项）**：6 数据域、基数、合同不强实体、阶段正交、多对多走引用桥、实体合并机制、问题状态机、基线只读、信息性质六层、G1~G7、trigram 检索、范围外事项。→ 见 `待确认事项清单` §1。
- **未定（9 项）**：邮件正文授权/脱敏、角色清单、设备分类树标准、外部编码/ERP 映射、计划 L1~L4 规范、知识沉淀判定、快照粒度、FTS 同步策略、业务管理功能时机。→ 见 `待确认事项清单` §2。

## 5. 关键风险提示（未隐瞒）

1. **多态引用完整性**：`object_link`/`source_reference` 用 type+id 非硬 FK，需应用层+自检+审计兜底。
2. **基线只读联动**：需补 `plan_version` 侧只读联动校验。
3. **SQLite→PostgreSQL**：已留转换面（char(32) UUID + ISO8601），Pg 侧 trigram 需 pg_trgm 适配。

## 6. Git 提交记录

- 本阶段提交了 10 个 Phase1.2 文档（8 份设计 + 1 业务确认 + 1 任务书）。
- 未建表、未迁移、未导入任何数据；`01_Data/epcs_intelligence.db` 保持空库。

## 7. 边界与下一步

- 本阶段**只做架构设计**，未执行建表/迁移/导入，未安装任何 SDK，未连接外部账号，未修改旧库。
- 下一步：本报告及 8 份文档经**系统架构师审核批准**后，交由工程侧实现 `migrations/001_init.sql`（幂等）+ 空库升级（不含业务数据），再进入后续 Phase。

> 依据任务书 §七 停止条件，Phase 1.2 设计阶段在此**停止**，不自动进入 Phase 1.3 或执行任何数据库建表。