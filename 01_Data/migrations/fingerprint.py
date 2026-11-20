# -*- coding: utf-8 -*-
"""DDL 指纹。

算法（设计真值源 §10.1）：取出 ``sqlite_master.sql`` 中非空语句，
按 SQL 文本排序后用换行拼接，再计算 SHA256，得到 64 位小写十六进制。

``sql IS NULL`` 的 ``sqlite_autoindex_*`` 不进入拼接。指纹只覆盖结构
语句，不覆盖表中的行，因此写入 ``schema_version.ddl_fingerprint`` 不会
改变指纹本身。
"""
import hashlib


def ddl_fingerprint(conn):
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY sql"
    ).fetchall()
    payload = "\n".join(row[0] for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
