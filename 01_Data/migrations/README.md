# 迁移

运行器在 `runner.py`。每个连接由 `connection.connect` 执行 `PRAGMA foreign_keys=ON`；可写连接同时设置 `journal_mode=WAL`。

`ddl_fingerprint` 是 `sqlite_master.sql` 里非空语句按文本排序、换行拼接后的 SHA256。空库在一个事务里建表并登记 `schema_version`。再次执行时，列（`PRAGMA table_info` 的列名、类型、notnull、默认值、主键）、索引、触发器和指纹都一致才跳过。不一致就拒绝，不改已有表。

本切片创建 19 张表：`schema_version`、`entity`、`project`、`organization`、`department`、`person`、`document`、`document_version`、`source_reference`、`business_subject`、`knowledge_item`、`knowledge_version`、`ingestion_job`、`ai_analysis_run`、`extraction_result`、`review_queue`、`review_extraction_link`、`review_decision`、`review_result_object`。

其中 `entity`、`department`、`business_subject`、`ai_analysis_run` 只因为 SQLite 在外键为空时仍要求父表存在。流水线不向这四张表写业务行。不建其余域 1 表，不建 FTS 虚表。

触发器 4 个：`trg_er_immutable_u`、`trg_er_immutable_d`、`trg_rd_evidence_i`、`trg_rd_evidence_u`。

数据库级 UUID CHECK 目前只在本切片的 `project.id`、`person.id`、`entity.id` 上。`document.id` 等没有该 CHECK。应用层仍用 32 位小写十六进制。

测试：

```text
python -m unittest discover -s 07_Tests -p 'test_phase13_*.py'
```
