# Phase1.2 核心实体数据字典

> 表名/字段名全英文 snake_case；说明文字中文。公共基字段已在《总体设计》§3.2 定义，本文每表列出其**特定字段** + 关键公共字段（id/created_at/is_deleted 等不再逐表重复，见 §1 约定）。
> 与《数据库表结构设计》的 CREATE TABLE 一一对应。

## 0. 通用字段约定

- `id`：每表主键，UUID，`char(32)` 无连字符。`created_at/updated_at` 为 ISO8601 UTC 文本。
- `project_id`：业务对象锚定项目的外键（全局/治理表可空）。
- `info_nature`：信息性质枚举 G5（SOURCE_FACT/CONFIRMED_FACT/AI_INFERENCE/PREDICTION/PROPOSAL/DECISION）。
- `is_deleted` + `del_status`：软删除/归档语义（`ACTIVE`/`ARCHIVED`/`DELETED`）。
- 所有"值类"枚举（维度、性质、状态）一律用 `dimension`/`check`/`system_config` 归口，**禁止硬编码字面值**（G7）。

---

## 1. 域1 —— 项目与组织（底座）

### 1.1 `project` 项目
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_code | text | Y | — | 项目编码（外部编号，去重唯一 UNIQUE） |
| name | text | Y | — | 项目名称 |
| main_object_entity_id | char(32) | N | — | FK→entity；承载"一艘主造对象"（船/平台型） |
| contract_summary | text | N | — | 合同事实摘要（不强合同表时承载描述） |
| status | text | Y | 'ACTIVE' | 项目状态（system_config 归口） |
| started_at / planned_end_at / ended_at | text | N | — | 时间字段 |
| **索引/约束** | | | | UNIQUE(project_code)；FK main_object_entity_id |

### 1.2 `project_phase` 项目阶段实例（EPCS 实例）
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_id | char(32) | Y | — | FK→project |
| phase_code | text | Y | — | E/P/C/S 之一（dimension 归口）；同一项目可多实例（多轮工程迭代） |
| name | text | N | — | 实例名（如"第一次建造"） |
| seq_no | integer | Y | 0 | 同 project 下实例排序 |
| status | text | Y | 'ACTIVE' | 状态 |
| valid_from/valid_to | text | N | — | 生效区间 |
| **约束** | | | | UNIQUE(project_id, phase_code, seq_no) |

### 1.3 `organization` 组织
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| org_code | text | Y | — | 组织编码 UNIQUE |
| name | text | Y | — | 组织名（船东/船厂/设计院/分包/供应商/监理…） |
| org_type | text | Y | — | 组织类型（dimension 归口） |
| parent_id | char(32) | N | — | 自关联上级组织 |

### 1.4 `person` 人员
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| organization_id | char(32) | Y | — | FK→organization |
| name | text | Y | — | 姓名 |
| email | text | N | — | 联系邮箱（去重弱索引） |
| **索引** | | | | idx_person_org(organization_id) |

### 1.5 `project_member` 项目成员任职（项目×组织×角色 三维）
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_id | char(32) | Y | — | FK→project |
| organization_id | char(32) | Y | — | FK→organization |
| person_id | char(32) | N | — | FK→person（可空：组织级角色）
| role_name | text | Y | — | 角色（如设计主管/监理） |
| role_kind | text | N | — | 角色类型（dimension 归口，如项目角色/合同角色） |
| valid_from/valid_to | text | N | — | 任职区间 |
| is_contract_carrier | integer | N | 0 | =1 表示该任职承载**合同事实**（B.1 弱合同载体） |
| **约束** | | | | UNIQUE(project_id, organization_id, person_id, role_name, valid_from) |

### 1.6 `discipline` / `area` / `system` 维度目录（全局，跨项目共享）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| code | text | Y | 编码（UNIQUE） |
| name | text | Y | 名称（船体/轮机/电气/…；分段/舱室/机舱/…；压载/消防/电力/…） |
| parent_id | char(32) | N | 自关联父节点（分类树） |
| is_standard | integer | N | =1 标准件/通用项（跨项目共享） |

- **三表结构同构**，仅领域语义不同；不合并为一张"维度表"以保留 FK 纯粹性与字段扩展空间（沿 product 原有对象划分）。

### 1.7 `equipment_category` 设备分类树
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| code | text | Y | 分类编码 UNIQUE |
| name | text | Y | 分类名 |
| parent_id | char(32) | N | 自关联（分类树；层级标准见 D.2-3 未定） |

### 1.8 `equipment` 设备
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| name | text | Y | — | 设备名（主机/发电机/泵/阀/控制台…） |
| category_id | char(32) | N | — | FK→equipment_category |
| system_id | char(32) | N | — | FK→system（可先于系统定型为空） |
| manufacturer_entity_id | char(32) | N | — | FK→entity（厂商名归一） |
| equip_type | text | N | — | 内部分类位 |
| **索引** | | | | idx_equip_sys(system_id), idx_equip_cat(category_id) |

### 1.9 项目×维度 关联表（三维正交底座）
- `project_discipline(project_id, discipline_id)`、`project_area(project_id, area_id)`、`project_system(project_id, system_id)`、`project_equipment(project_id, equipment_id)`
- 每表：`id` PK，`project_id` FK，`discipline_id/area_id/system_id/equipment_id` FK，UNIQUE(project_id, 维度_id)。
- 说明：维度目录全局共享，项目横向施加（G1）；设备可跨项目共享（标准件目录）故用关联而非设备内嵌项目。

---

## 2. 域2 —— 计划管理

### 2.1 `plan` 计划
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_id | char(32) | Y | — | FK→project |
| name | text | Y | — | 计划名（L1 总计划 ~ L4 周计划，勿锁死为专用表，字段通用） |
| plan_code | text | N | — | 计划编码 |
| level | text | N | — | L1..L4（system_config 归口；L 级规范见 D.2-5 未定） |
| status | text | Y | 'DRAFT' | 状态 |
| **索引** | | | | idx_plan_proj(project_id) |

### 2.2 `plan_version` 计划版本
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| plan_id | char(32) | Y | — | FK→plan |
| version_no | text | Y | — | 版本号 |
| content_hash | text | N | — | 版本内容 hash（版本化防伪） |
| is_forecast | integer | Y | 0 | =1 滚动预测版（AI 产出，info_nature=PREDICTION） |
| snapshot_json | text | N | — | 快照（活动集精简，渐进策略，见 ADR-9） |
| status | text | Y | 'DRAFT' | PUBLISHED/RECALLED 等 |
| **约束** | | | | UNIQUE(plan_id, version_no) |

### 2.3 `baseline_version` 基线版本
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| plan_id | char(32) | Y | — | FK→plan |
| plan_version_id | char(32) | Y | — | FK→plan_version（基线的实质内容） |
| baseline_no | text | Y | — | 基线编号 |
| approved_at | text | Y | — | 批准时间 |
| approved_by | char(32) | N | — | 批准人 person_id |
| is_active | integer | Y | 0 | 同一 plan 仅 0/1 个"当前生效基线"（应用层/触发器保证） |
| is_readonly | integer | Y | 1 | =1 受保护只读（触发器强拦写，OQ-3） |
| **约束** | | | | UNIQUE(plan_id, baseline_no)；UNIQUE(plan_id, is_active) 部分索引(WHERE is_active=1) |

### 2.4 `plan_activity` 计划活动/里程碑
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| plan_id | char(32) | Y | — | FK→plan |
| code | text | N | — | 活动编码（如 WBS） |
| name | text | Y | — | 活动名 |
| is_milestone | integer | Y | 0 | =1 里程碑（子类型标记，不重复建模） |
| discipline_id/area_id/system_id | char(32) | N | — | 快捷维度（主维度；副维度走 object_dimension_tag） |
| planned_start/planned_end | text | N | — | 计划时间 |
| status | text | Y | 'PLANNED' | 状态 |
| **索引** | | | | idx_activity_plan(plan_id), idx_activity_milestone(is_milestone) |

### 2.5 `activity_dependency` 活动依赖（自关联 M:N）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| plan_id | char(32) | Y | FK→plan（作用域） |
| predecessor_id | char(32) | Y | FK→plan_activity（前置） |
| successor_id | char(32) | Y | FK→plan_activity（后置） |
| relation_type | text | Y | FS/SS/FF/SF（check） |
| lag_days | integer | N | 滞后天数 |
| **约束** | | | | CHECK(predecessor<>successor)；UNIQUE(plan_id, predecessor_id, successor_id, relation_type) |

### 2.6 `progress_record` 进度记录
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| plan_activity_id | char(32) | Y | — | FK→plan_activity |
| record_at | text | Y | — | 时点 |
| progress_pct | real | Y | 0 | 完成百分比 0~100 |
| actual_start/actual_end | text | N | — | 实际时间 |
| note | text | N | — | 备注 |
| **约束** | | | | CHECK(progress_pct BETWEEN 0 AND 100)；UNIQUE(plan_activity_id, record_at) |

---

## 3. 域3 —— 信息与文件（来源域）

### 3.1 `email` 邮件
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| message_id_text | text | N | 外部 message-id（去重） |
| from_addr/to_addrs/cc_addrs | text | N | 地址（to/cc 存 JSON 文本） |
| subject | text | Y | 主题 |
| body_markdown | text | N | 正文（**按隔离边界授权处理**，见 D.2-1） |
| source_time | text | Y | 邮件时间 |
| **索引** | | | idx::fts 见 FTS 章节；UNIQUE(message_id_text) |

### 3.2 `email_attachment` 邮件附件
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| email_id | char(32) | Y | FK→email |
| filename | text | Y | 文件名 |
| file_kind | text | N | 类型（可升级为 Document） |
| sha256 | text | N | 内容指纹（去重/版本） |

### 3.3 `document` / `document_version` 文档及其版本
- `document`：id, project_id, name, doc_code, doc_type, parent_document_id(自关联或为版本根), is_readonly=1, sha256, created_at…
- `document_version`：id, document_id FK, version_no, file_path, sha256, snapshot/notes

### 3.4 `drawing` / `drawing_version` 图纸及其版本
- `drawing`：id, project_id, drawing_no(图号), name, doc_type='DRAWING', is_readonly=1
- `drawing_version`：id, drawing_id FK, revision, file_path, sha256
- `drawing_object`（**DWG 对象预留，不装 SDK/不解析**）：id, drawing_id FK, obj_type(类名如『设备对象』), ref_entity_id FK→entity, ref_area_id/ref_system_id, geometry_json(占位), reserved_data(占位)

### 3.5 `meeting` / `meeting_minutes` 会议及其纪要
- `meeting`：id, project_id, title, held_at, organizer_person_id, participant_ids(JSON), transcript_ptr, source_time
- `meeting_minutes`：id, meeting_id FK, version_no, content_md, is_final, source_time

### 3.6 `message` 消息（微信/即时消息）
- id, project_id, sender_person_id, content_md, sent_at, channel, source_time

### 3.7 `source_reference` 来源引用（统一来源桥 —— 泛化来源载体→任意实体）
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| traced_entity_type | text | Y | — | 被溯源对象类型（issue/entity/knowledge_item/…） |
| traced_entity_id | char(32) | Y | — | 被溯源对象 id（不设硬 FK，应用层保证，见 ADR-6） |
| source_type | text | Y | — | 来源载体类型（email/email_attachment/document/drawing/meeting_minutes/message/evidence） |
| source_id | char(32) | Y | — | 来源载体 id（不设硬 FK） |
| context_excerpt | text | N | — | 上下文摘录（引了哪段） |
| locator | text | N | — | 定位（图号/段落/pin） |
| info_nature | text | Y | 'SOURCE_FACT' | 溯源关系本身的事实级别 |
| confidence | real | N | — | 置信度 |
| source_time | text | N | — | 来源时间 |
| **索引** | | | | idx_sr_entity(traced_entity_type, traced_entity_id)；idx_sr_source(source_type, source_id) |

### 3.8 `evidence` / `evidence_link` 证据
- `evidence`：id, project_id, title, body/path, evidence_kind(片段/附件/截图), sha256
- `evidence_link`：id, evidence_id FK, ref_type, ref_id, link_role(佐证/反证/依据), context_excerpt

---

## 4. 域4 —— 问题/风险/任务闭环

### 4.1 `issue` 问题
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| project_id | char(32) | Y | — | FK→project |
| ref_no | text | Y | — | 问题编号（去重 UNIQUE，可跨域引用） |
| title | text | Y | — | 标题 |
| description_md | text | N | — | 描述 |
| status | text | Y | 'NEW' | 状态机值（见 4.2），product 已锁定 |
| severity/priority | text | N | — | 严重度/优先级（enum 归口） |
| info_nature | text | Y | 'CONFIRMED_FACT' | 问题的事实级别 |
| **索引** | | | | idx_issue_proj(project_id), idx_issue_status(status) |

### 4.2 `issue_status_history` 状态历史（B.6 状态机）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| issue_id | char(32) | Y | FK→issue |
| old_status / new_status | text | Y | 流转前/后 |
| transition | text | N | 转移名（含退回/重开分支） |
| changed_by | char(32) | N | 操作人 person_id |
| changed_at | text | Y | 时间 |
| reason | text | N | 退回/重开原因 |
| reopen_count | integer | N | 重开次数（重开时+1） |
| info_nature, source_reference_id | — | N | 溯源挂接 |
| **约束** | | | | CHECK(new_status IN 状态机)；合法转移由应用层校验 |

### 4.3 `risk` / `risk_status_history`
- `risk`：id, project_id, ref_no, title, description, probability, impact, exposure, status, strategy(规避/转移/缓解/接受), info_nature
- `risk_status_history`：同 issue 历史结构，绑定 risk_id

### 4.4 `task` / `task_status_history`
- `task`：id, project_id, ref_no, title, description, assignee_person_id, due_at, priority, status, info_nature
- `task_status_history`：同结构，绑定 task_id

### 4.5 `action_measure` 行动措施（风险应对 & 问题整改 共用）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| ref_no | text | Y | 编号 |
| name | text | Y | 措施名 |
| measure_type | text | Y | 类型（RISK_RESPONSE / ISSUE_REMEDY，dimension 归口） |
| source_owner_type/id | — | N | 所属对象（risk 或 issue，泛化） |
| due_at, status, info_nature | — | N | — |

### 4.6 `decision` 决策记录
- id, project_id, ref_no, title, conclusion, decided_by_person_id, decided_at, status, info_nature='DECISION'
- `decision_link`：id, decision_id FK, ref_type, ref_id, link_role(依据/被决策对象)，灵话关联方案/文件/问题

### 4.7 `object_link` 通用对象桥（M:N 全链路引用 —— issue↔activity/email/document/drawing/meeting/task/risk/knowledge…）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| link_role | text | Y | 角色（issue_activity/issue_document/issue_email/decision_basis/evidence_support/…，dimension 归口） |
| left_type / left_id | text/char | Y | 左侧对象（多态） |
| right_type / right_id | text/char | Y | 右侧对象（多态） |
| context_excerpt | text | N | 上下文摘录 |
| info_nature, created_at | — | N | — |
| **索引** | | | idx_ol_left(left_type,left_id)；idx_ol_right(right_type,right_id)；UNIQUE(left,right,link_role,context_excerpt) 近似 |

> 设计说明：`object_link` 承载 B.3/B.4 与 A.4 的一切业务对象间多对多，避免为每对关系建独立表（ADR-4/ADR-5）。

---

## 5. 域5 —— 实体关系与知识

### 5.1 `entity` 实体（归一化业务实体，含全局唯一标识）
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID（**全局实体标识**，B.5 核心） |
| name | text | Y | — | 规范名 |
| entity_kind | text | Y | — | 船/设备/部位/厂商/专业…（dimension 归口） |
| canonical_source_id | char(32) | N | — | 与 entity 自关联：本规范名对应的规范实体（合并/主实体的本质，见 ADR-6） |
| status | text | N | 'ACTIVE' | ACTIVE/MERGED/SUPERSEDED |
| info_nature | text | Y | 'CONFIRMED_FACT' | 实体事实级别 |
| **索引** | | | | idx_entity_name(name)；FTS trigram(@name) |

### 5.2 `entity_alias` 实体别名
- id, entity_id FK, alias, alias_type(简称/大小写/译名/近义), source_reference_id(来源), confirm_status(已确认/待确认/拒绝)
- 检索用到：trigram 命中→别名映射→规范实体。

### 5.3 `entity_identifier` 外部编号
- id, entity_id FK, id_type(设备号/船号/图号, source_from), identifier, source_reference_id, effective_from
- 对应 D.2-4 外部映射协议（未定，先留结构）。

### 5.4 `entity_relationship` 实体间语义关系（M:N，含合并链）
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| left_entity_id | char(32) | Y | FK→entity |
| right_entity_id | char(32) | Y | FK→entity |
| relation_type | text | Y | synonym/merge/holonym(整机-部件)/superclass/替換/… |
| confirm_status | text | N | 已确认/待确认/拒绝 |
| source_reference_id | char(32) | N | 合并判据来源证据 |
| **约束** | | | | CHECK(left<>right)；UNIQUE(left,right,relation_type) |

### 5.5 `knowledge_item` / `knowledge_version` / `knowledge_entity_link`
- `knowledge_item`：id, project_id, title, summary, info_nature, status
- `knowledge_version`：id, knowledge_item_id FK, version_no, content_md, sha256, snapshot_json
- `knowledge_entity_link`：id, knowledge_version_id FK, entity_id FK（知识涉及的实体，M:N）

---

## 6. 域6 —— AI 处理与系统治理

### 6.1 `ingestion_job` 摄入作业
- id, project_id, source_type(邮件/文件/会议/消息), source_id, channel, status(ingesting/success/failed), started_at/finished_at, run_meta(JSON), re_runnable

### 6.2 `extraction_result` 抽取结果（AI 候选，未审核）
- id, ingestion_job_id FK, ai_analysis_run_id FK, candidate_type(实体/问题/风险/分类…), candidate_json, raw_text, info_nature='AI_INFERENCE', confidence, status(pending/merged/rejected/accepted)

### 6.3 `review_queue` 人工审核队列
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | char(32) | Y | UUID |
| extraction_result_id | char(32) | N | FK→extraction_result |
| reviewer_person_id | char(32) | N | 审核人 |
| review_type | text | Y | 实体确认/问题确认/分类确认… |
| candidate_summary | text | N | 候选摘要（含译名/别名提示） |
| suggested_entity_id | char(32) | N | 系统候选同名实体（trigram 近义召回） |
| decision | text | N | ACCEPT_AS_NEW / MERGE_TO / REJECT |
| target_entity_id | char(32) | N | 合并目标（MERGED 时） |
| reviewed_at | text | N | 复核时间 |
| **索引** | | | idx_rq_status(decision), idx_rq_suggest(suggested_entity_id) |

### 6.4 `ai_analysis_run` AI 分析运行日志
- id, project_id, run_type(摘要/归类/关系推断/滚动预测), model, input_ref, output_summary, status, started_at/finished_at

### 6.5 `audit_log` 审计日志
- id, project_id, actor_type(USER/AI), actor_id, action_code, target_type/target_id, before_json/after_json, created_at
- **一切对基线/正式记录的写操作必须记录至此**（OQ-3）。

### 6.6 `system_config` 系统配置（非硬编码枚举归口）
- id, config_key UNIQUE, config_value, description, config_group, is_active

### 6.7 `user`/`role`/`permission`（Phase 后期启用，字段预留）
- `user`：id, person_id FK, username, password_hash, status
- `role`：id, role_code, name
- `permission`：id, permission_code, name
- `user_role`(M:N)，`role_permission`(M:N)
- 本阶段仅表结构预留骨架，角色清单见 D.2-2 未定。

---

## 7. 共享关联表（域间桥梁）

### 7.1 `object_dimension_tag` 对象×维度 多值标签（EPCS 阶段|专业|区域|系统 正交，OQ-5 统一表）
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| id | char(32) | Y | — | UUID |
| tagged_object_type | text | Y | — | 被打标签对象类型（issue/document/activity/…） |
| tagged_object_id | char(32) | Y | — | 对象 id（多态） |
| dimension | text | Y | — | EPCS_PHASE / DISCIPLINE / AREA / SYSTEM |
| value_type | text | N | — | REF(指向维度表) 或 FREE_TEXT |
| value_id | char(32) | N | — | 指向 discipline/area/system/… 的 id |
| value_text | text | N | — | 自由值（如"阶段不确定/跨阶段"，B.2） |
| **索引** | | | | idx_odt_obj(tagged_object_type,tagged_object_id)；idx_odt_dim(dimension, value_id) |

> 该表承载 B.2"阶段+专业/区域/系统可同时多打、可并列/跨阶段"，并兼容"阶段不确定/自由文本"——避免 status 枚举锁死。

### 7.2 FTS5 trigram 索引（各内容表）
- 对 `email(subject, body_markdown)`、`document_version(snapshot/notes)`、`meeting_minutes(content_md)`、`message(content_md)`、`issue(title, description_md)`、`risk`、`task`、`knowledge_version(content_md)`、`entity(name)`、`entity_alias(alias)`、`drawing(name)` 建 FTS5 **trigram** 虚拟表，命名为 `<table>_fts`，与主表同名 id 关联。
- 官方示例：`CREATE VIRTUAL TABLE issue_fts USING fts5(title, description_md, content='issue', content_rowid='id', tokenize='trigram');`
- 检索路由见《总体设计》§3.6 &&《架构决策记录》ADR-7。