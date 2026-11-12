# -*- coding: utf-8 -*-
"""
EPCS Shipbuilding Intelligence — 01_Data 初始化脚本

用途：
  1. 创建独立的 epcs_intelligence.db（已由 Phase 1.1 手工创建，此脚本为可重复幂等初始化）
  2. 建立 SQLite 基础（本阶段不含任何业务表）
  3. 校验版本 / FTS5 / 读写权限

安全约束（Phase 1.1 严格禁令）：
  * 不建业务表（留给 Phase 1.2 数据模型设计）
  * 不导入任何旧数据、邮件、项目文件
  * 不连接旧生产数据库
  * 不启动 Ollama、不安装依赖

用法：
    python init_db.py            # 幂等初始化并自检
    python init_db.py --check    # 只检查不创建
"""
import os
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(_HERE), 'epcs_intelligence.db')  # ../epcs_intelligence.db → 01_Data/


def connect(ro=False):
    uri = 'file:' + DB_PATH.replace('\\', '/') + ('?mode=ro' if ro else '')
    return sqlite3.connect(uri, uri=True)


def check():
    print('=' * 60)
    print('[check] EPCS 数据库初始化自检')
    if not os.path.exists(DB_PATH):
        print('[FAIL] 数据库文件不存在:', DB_PATH)
        return False
    con = sqlite3.connect('file:' + DB_PATH.replace('\\', '/') + '?mode=ro', uri=True)
    print('[OK]   SQLite 版本:', sqlite3.sqlite_version)
    print('[OK]   Python sqlite3 模块:', sqlite3.version)
    # FTS5 用内存库验证（不给正式库添加任何对象）
    m = sqlite3.connect(':memory:')
    m.execute("CREATE VIRTUAL TABLE _t USING fts5(content, tokenize='trigram')")
    m.execute("INSERT INTO _t VALUES('铺缆船集控台')")
    hit = m.execute("SELECT count(*) FROM _t WHERE _t MATCH '集控台'").fetchone()[0]
    print('[OK]   FTS5(trigram) 中文检索: 命中=%d' % hit)
    m.close()
    # 空库检查：本阶段不应有业务表
    tables = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name NOT LIKE 'sqlite_%'").fetchall()
    print('[%s] 业务表数量: %d (应为 0)' % ('OK' if len(tables) == 0 else 'WARN', len(tables)))
    con.close()
    print('=' * 60)
    return True


def init():
    if os.path.exists(DB_PATH):
        print('数据库已存在，幂等跳过创建:', DB_PATH)
    else:
        con = sqlite3.connect(DB_PATH)
        con.close()
        print('已创建独立数据库:', DB_PATH)
    return check()


if __name__ == '__main__':
    import sys
    if '--check' in sys.argv:
        sys.exit(0 if check() else 1)
    sys.exit(0 if init() else 1)