# -*- coding: utf-8 -*-
"""
EPCS Shipbuilding Intelligence — 01_Data 初始化

1. 确保 epcs_intelligence.db 存在（文件不入库）
2. 交给迁移运行器建立本切片表结构。结构一致则跳过；被改过则拒绝
3. 校验 SQLite / FTS5 trigram，并用 PRAGMA table_list 报告实体表

用法：
    python 01_Data/scripts/init_db.py
    python 01_Data/scripts/init_db.py --check
    python 01_Data/scripts/init_db.py --db /tmp/epcs.db
"""
import os
import sqlite3
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.dirname(_HERE)
if _DATA not in sys.path:
    sys.path.insert(0, _DATA)

from migrations.connection import connect
from migrations.runner import SchemaMismatchError, inspect_schema, migrate
from migrations.schema_check import entity_table_names

DB_PATH = os.path.join(_DATA, "epcs_intelligence.db")


def _db_from_argv(argv):
    if "--db" in argv:
        index = argv.index("--db")
        return argv[index + 1]
    return None


def check(db_path=None):
    print("=" * 60)
    print("[check] EPCS 数据库初始化自检")
    path = db_path or DB_PATH
    if not os.path.exists(path):
        print("[FAIL] 数据库文件不存在:", path)
        return False
    print("[OK]   SQLite 版本:", sqlite3.sqlite_version)
    probe = connect(":memory:")
    try:
        probe.execute("CREATE VIRTUAL TABLE _t USING fts5(content, tokenize='trigram')")
        probe.execute("INSERT INTO _t VALUES('铺缆船集控台')")
        hit = probe.execute("SELECT count(*) FROM _t WHERE _t MATCH '集控台'").fetchone()[0]
    finally:
        probe.close()
    print("[OK]   FTS5(trigram) 中文检索「集控台」: 命中=%d" % hit)
    if hit != 1:
        print("[FAIL] FTS5 trigram 未命中「集控台」")
        return False
    conn = connect(path, readonly=True)
    try:
        status, _expected, diffs = inspect_schema(conn)
        names = entity_table_names(conn)
        print(
            "[OK]   实体表数量: %d（PRAGMA table_list, type='table' AND name NOT LIKE 'sqlite_%%'）"
            % len(names)
        )
        if status == "blank":
            print("[INFO] 尚未迁移。执行 init 会建立统一入口切片的表。")
        elif status == "consistent":
            print("[OK]   迁移结构一致: %s" % ", ".join(names))
        else:
            print("[FAIL] 结构与迁移定义不一致，已拒绝修改")
            for line in diffs[:20]:
                print("       ", line)
            return False
    finally:
        conn.close()
    print("=" * 60)
    return True


def init(db_path=None):
    path = db_path or DB_PATH
    try:
        result = migrate(path)
    except SchemaMismatchError as exc:
        print("[FAIL] 迁移被拒绝:", exc)
        return False
    print("[OK]   迁移状态: %s" % result.status)
    print("[OK]   ddl_fingerprint: %s" % result.fingerprint)
    print("[OK]   实体表: %s" % ", ".join(result.tables))
    return check(path)


if __name__ == "__main__":
    chosen = _db_from_argv(sys.argv)
    if "--check" in sys.argv:
        sys.exit(0 if check(chosen) else 1)
    sys.exit(0 if init(chosen) else 1)
