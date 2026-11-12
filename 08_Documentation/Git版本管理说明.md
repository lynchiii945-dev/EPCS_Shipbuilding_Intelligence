# Git 版本管理说明

> EPCS Shipbuilding Intelligence — Git 基础（Phase 1.1 确立）
> 更新：2026-11-12

---

## 1. 仓库信息

| 项 | 值 |
|---|---|
| Git 版本 | 2.55.0.windows.3 |
| 仓库路径 | `D:\ALLAN\EPCS_Shipbuilding_Intelligence` |
| 默认分支 | `main`（`git init -b main`） |
| 首次提交时间 | 2026-11-12（Phase 1.1） |

## 2. .gitignore 规则（入库边界）

原则：**DB / 日志 / 临时 / 备份 / 敏感原始资料一律不入库**，只提交项目说明、目录说明、初始化脚本。

| 忽略项 | 匹配 |
|---|---|
| 数据库 | `*.db` `*.db-wal` `*.db-shm` `*.sqlite*` `*.bak*` |
| 日志 | `05_Logs/` `*.log` |
| 临时 | `*.tmp` `__pycache__/` `*.pyc` `.venv/` |
| 备份/归档 | `06_Backups/` `09_Archive/` |
| 敏感原始资料 | `02_Original_References/` `*.eml` `*.pst` `*.ost` `*.dwg` |
| 密钥/配置 | `*.env` `config.local.json` `secrets*.json` |

## 3. 提交边界确认

首次提交**只包含**：
- `.gitignore`
- `00_Vault/项目首页.md`、`00_Vault/系统说明.md`
- `01_Data/scripts/init_db.py`
- `08_Documentation/` 下 6 份阶段文档

**不包含**：`epcs_intelligence.db`、任何日志、备份、真实资料、`02_Original_References/`（空目录 Git 不跟踪）。

## 4. 分支与提交规范（建议）

- 主分支 `main` 保持可发布状态。
- 功能/阶段开发在分支 `feature/phase-1.2-data-model` 之类进行。
- 提交信息使用 `<动词>: <主题>`（如 `docs: Phase1.1 初始化文档`）。
- 数据库文件永远不进 Git；schema 变更走 `01_Data/migrations/` 脚本 + 版本化。

## 5. 回滚能力

仓库为全新空库，Git 提供脚本与文档的版本回滚；数据库回滚依赖 `migrations/` 设计（Phase 1.2 落地）。