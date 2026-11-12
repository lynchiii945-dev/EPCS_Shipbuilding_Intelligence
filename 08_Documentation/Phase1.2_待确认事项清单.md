# Phase1.2 待确认事项清单

> 明确哪些设计**已定**（本阶段可直接采用）、哪些**未定**（建模已留接口，需人工/后续确认）。不隐瞒未决项。

## 1. 已确定项（产品既定 + 架构定案，可直接作为实现依据）

| # | 事项 | 来源 | 决策要点 |
|---|---|---|---|
| 1 | 6 大核心数据域及对象清单 | A 节 | 域与对象表已列 |
| 2 | 对象间基数 | A 节 | 见 ER 图 |
| 3 | 项目承载一艘主造对象、多合同不强实体 | B.1/ADR-1 | `project.main_object_entity_id` + `project_member.is_contract_carrier` |
| 4 | EPCS 阶段为时间纵轴、与专业/区域/系统正交且标签化 | B.2/ADR-2 | `object_dimension_tag` |
| 5 | 各类 M:N 多对多（问题↔多来源；一文件被多事项引用） | B.3/B.4/ADR-4/5 | `object_link` + `source_reference` |
| 6 | 全局实体标识 + 合并机制 + AI 先入 ReviewQueue | B.5/ADR-6 | `entity` + `entity_relationship` + 合并链 |
| 7 | 问题状态机（含退回/重开） | B.6 | 状态历史表 + 应用层校验 |
| 8 | 批准基线只读、AI 禁改 | B.7/ADR-8 | `baseline_version` + 触发器/应用层/审计 |
| 9 | 信息性质六层枚举与自动/人工边界 | B.8/ADR-7 | `info_nature` + `system_config` 双轨 |
| 10 | G1~G7 全局约束 | 全局 | 已落实到表设计与索引策略 |
| 11 | SQLite/FTS5 trigram 中文检索 | 实测/ADR-7b | 全文本表 trigram + 触发器同步 |
| 12 | 范围外（本阶段不做） | 任务书/隔离说明 | 业务功能/迁移/SDK/接入/权限功能——后续 Phase |

## 2. 未定项（已备接口，需人工/后续确认）

| # | 事项 | 现状（D.2 原条） | 建模已留接口 / 决策影响 | 责任归属 |
|---|---|---|---|---|
| 1 | 授权的真实邮件正文读取边界与脱敏粒度 | D.2-1 | `email.body_markdown` 按隔离边界授权写；脱敏粒度待定 | 数据合规/接入 Phase |
| 2 | 用户/角色/权限具体角色清单 | D.2-2 | `user/role/permission` 表骨架预留；启用 Phase 定清单 | 产品/Phase 后期 |
| 3 | 设备分类树（Equipment taxonomy）层级标准 | D.2-3 | `equipment_category` 自引用树；船级社 vs 自建未锁 | 领域专家 |
| 4 | 外部企业编码/ERP 编号映射协议 | D.2-4 | `entity_identifier(id_type/source_from)` 真实来源清单 | 集成 Phase |
| 5 | 计划粒度 L1~L4 字段规范与周期 | D.2-5 | `plan.level` 通用，无 L 专用表 | 计划管理 Phase |
| 6 | 知识沉淀判定细则 | D.2-6 | `knowledge_item`+`version` 可沉淀可版本；判定规则后补 | 知识管理 Phase |
| 7 | 快照粒度（全量 vs 增量资产） | ADR-9 | `snapshot_json` 渐进；成本边界待定 | 架构/实现评审 |
| 8 | FTS 同步策略（触发器 vs 定时重建） | ADR-7b | 一期触发器；二期摄入高频时切换 | 架构/实现 |
| 9 | 计划/风险/问题业务管理功能何时开发 | 任务书§五 | 后续 Phase | 产品 |

## 3. 未决风险提示（不隐瞒）

- **多态引用完整性**：`object_link`/`source_reference` 用 `type+id` 而非硬 FK，数据库缺外键保障；一期以应用层 + 摄入后自检 + 审计兜底。若后续量大，可加"引用完整性校验脚本"定期跑。
- **基线只读触发器**：`trigger` 仅拦截 `baseline_version` 单表；若未来经 `plan_version` 改基线内容，需补充 `plan_version` 的只读联动——ADR-8 已提示，实现时校验。
- **SQLite→PostgreSQL**：一期统一 `char(32)` UUID + ISO8601 文本时间，为迁移保留转换面；`system_config`/FTS 语义在 Pg 侧需适配（trigram 由 pg_trgm 提供）。

## 4. 建议的下一步（Phase 1.2 落地）

1. 本清单 §1 经产品归档为**锁定基线**；§2 逐项挂责任人跟踪。
2. 8 份文档经系统架构师 + 产品评审；批准后由工程实现 `migrations/001_init.sql`（幂等）+ 空库升级（`01_Data/epcs_intelligence.db`，**不含业务数据**）。
3. 评审通过后关闭 Phase 1.2，进入 Phase 1.3+（业务功能/SDK 选型另行审批）。