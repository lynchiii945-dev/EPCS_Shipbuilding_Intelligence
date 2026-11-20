# -*- coding: utf-8 -*-
"""数据库连接工厂。

Phase1.2 设计真值源 §0.1：``PRAGMA foreign_keys`` 不跨连接持久化，
每个新连接都必须由工厂打开。``journal_mode=WAL`` 是库级设置，可以持久化。
"""
import os
import sqlite3


def connect(database, *, readonly=False):
    """打开连接，并强制 ``foreign_keys=ON``。

    可写连接同时执行 ``PRAGMA journal_mode=WAL``。内存库接受该设置，
    但 SQLite 仍会保持 ``memory`` 日志模式；文件库必须得到 ``wal``。
    """
    if not isinstance(database, str) or database.strip() == "":
        raise ValueError("database path is required")
    if database == ":memory:":
        if readonly:
            raise ValueError("内存库不支持只读打开")
        conn = sqlite3.connect(":memory:", isolation_level=None)
    else:
        path = os.path.abspath(database)
        if readonly and not os.path.exists(path):
            raise FileNotFoundError(path)
        if not readonly:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        mode = "ro" if readonly else "rwc"
        uri = "file:" + path.replace("\\", "/") + "?mode=" + mode
        conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    if conn.isolation_level is not None:
        conn.isolation_level = None
    _enforce_connection_pragmas(conn, database, readonly=readonly)
    return conn


def _enforce_connection_pragmas(conn, database, *, readonly):
    conn.execute("PRAGMA foreign_keys=ON")
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    if fk != 1:
        conn.close()
        raise RuntimeError("连接工厂未能打开 foreign_keys")
    if readonly:
        return
    journal = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if database != ":memory:" and str(journal).lower() != "wal":
        conn.close()
        raise RuntimeError("未能设置 journal_mode=WAL，实际为 %s" % journal)
