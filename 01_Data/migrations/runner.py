# -*- coding: utf-8 -*-
"""幂等迁移运行器。

空库执行本切片 DDL，并在同一事务里登记 schema_version。
结构与指纹一致则跳过，不重复创建。
结构被改过，或登记的指纹对不上，则拒绝，不修改已有对象。
"""
from datetime import datetime, timezone

from migrations.connection import connect
from migrations.fingerprint import ddl_fingerprint
from migrations.schema_check import diff_snapshots, entity_table_names, fts_names, snapshot
from migrations.slice_ddl import STATEMENTS

VERSION = 1
DESCRIPTION = "Phase1.3 统一资料入口薄切片"


class SchemaMismatchError(RuntimeError):
    """现有结构与迁移定义不一致。运行器不会改表。"""


class MigrationResult(object):
    def __init__(self, status, version, fingerprint, tables, fts, triggers, indexes):
        self.status = status
        self.version = version
        self.fingerprint = fingerprint
        self.tables = tables
        self.fts = fts
        self.triggers = triggers
        self.indexes = indexes


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reference_snapshot():
    conn = connect(":memory:")
    try:
        for sql in STATEMENTS:
            conn.execute(sql)
        return snapshot(conn)
    finally:
        conn.close()


def registration_rows(conn):
    exists = conn.execute(
        "SELECT 1 FROM pragma_table_list WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if not exists:
        return []
    return conn.execute(
        "SELECT version, ddl_fingerprint FROM schema_version ORDER BY version"
    ).fetchall()


def apply_statements(conn, statements, *, version, description, expect=None):
    """在一个事务里执行语句并登记指纹。失败则整单回滚。"""
    if conn.in_transaction:
        raise RuntimeError("连接已在事务中")
    conn.execute("BEGIN")
    try:
        for index, sql in enumerate(statements):
            try:
                conn.execute(sql)
            except Exception as exc:
                preview = " ".join(sql.split())[:180]
                raise RuntimeError("迁移语句 %d 失败: %s" % (index, preview)) from exc
        fingerprint = ddl_fingerprint(conn)
        if len(fingerprint) != 64:
            raise RuntimeError("ddl_fingerprint 长度不是 64")
        if expect is not None:
            diffs = diff_snapshots(snapshot(conn), expect)
            if diffs or fingerprint != expect.fingerprint:
                detail = "\n".join(diffs[:40])
                raise RuntimeError("应用后的结构与参考快照不一致\n" + detail)
        conn.execute(
            "INSERT INTO schema_version(version, applied_at, description, ddl_fingerprint)"
            " VALUES (?,?,?,?)",
            (version, utcnow(), description, fingerprint),
        )
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError("foreign_key_check: %s" % (violations,))
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError("integrity_check: %s" % integrity)
        conn.execute("COMMIT")
        return fingerprint
    except Exception:
        conn.execute("ROLLBACK")
        raise


def migrate_conn(conn):
    expected = reference_snapshot()
    current = snapshot(conn)
    if current.is_blank():
        fingerprint = apply_statements(
            conn,
            STATEMENTS,
            version=VERSION,
            description=DESCRIPTION,
            expect=expected,
        )
        return _result(conn, "applied", fingerprint)
    diffs = diff_snapshots(current, expected)
    registered = registration_rows(conn)
    if not diffs and registered == [(VERSION, expected.fingerprint)]:
        return _result(conn, "skipped", expected.fingerprint)
    if not diffs:
        raise SchemaMismatchError(
            "schema_version 登记的版本或 ddl_fingerprint 与当前结构不一致，已拒绝修改"
        )
    shown = "\n".join(diffs[:80])
    extra = ""
    if len(diffs) > 80:
        extra = "\n... 另有 %d 条差异" % (len(diffs) - 80)
    raise SchemaMismatchError("结构与迁移定义不一致，已拒绝修改:\n" + shown + extra)


def migrate(database):
    if database == ":memory:":
        raise ValueError("内存库请使用 migrate_conn()，以免关闭连接后丢失")
    conn = connect(database)
    try:
        return migrate_conn(conn)
    finally:
        conn.close()


def inspect_schema(conn):
    """只读判断：blank / consistent / mismatch。不写库。"""
    expected = reference_snapshot()
    current = snapshot(conn)
    if current.is_blank():
        return "blank", expected, []
    diffs = diff_snapshots(current, expected)
    if not diffs and registration_rows(conn) == [(VERSION, expected.fingerprint)]:
        return "consistent", expected, []
    if not diffs:
        diffs = ["schema_version 登记与 ddl_fingerprint 不一致"]
    return "mismatch", expected, diffs


def _result(conn, status, fingerprint):
    triggers = tuple(
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name"
        )
    )
    indexes = tuple(
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
    )
    return MigrationResult(
        status=status,
        version=VERSION,
        fingerprint=fingerprint,
        tables=entity_table_names(conn),
        fts=fts_names(conn),
        triggers=triggers,
        indexes=indexes,
    )
