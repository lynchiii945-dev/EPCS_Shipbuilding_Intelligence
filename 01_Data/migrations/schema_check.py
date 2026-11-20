# -*- coding: utf-8 -*-
"""结构快照与差异。

比对口径：
- 列：``PRAGMA table_info`` 的列名、类型、notnull、默认值，以及列序和 pk
- 索引、触发器：``sqlite_master`` 中的名称、所属表、SQL
- FTS：``PRAGMA table_list`` 里 ``type='virtual'`` 的清单及其列
- 指纹：``ddl_fingerprint``

实体表数量只用 ``PRAGMA table_list`` 的
``type='table' AND name NOT LIKE 'sqlite_%'``，避免把 ``sqlite_schema``
与 ``sqlite_temp_schema`` 算进去。FTS 影子表在该视图中是 ``shadow``，
不计入实体表。
"""
import re
from dataclasses import dataclass

from migrations.fingerprint import ddl_fingerprint

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ENTITY_TABLE_SQL = (
    "SELECT name FROM pragma_table_list "
    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
    "ORDER BY name"
)


def quote_ident(name):
    if not _IDENT.fullmatch(name):
        raise ValueError("非法标识符: %r" % (name,))
    return '"' + name + '"'


def entity_table_names(conn):
    return tuple(row[0] for row in conn.execute(ENTITY_TABLE_SQL))


def fts_names(conn):
    return tuple(
        row[0]
        for row in conn.execute(
            "SELECT name FROM pragma_table_list WHERE type='virtual' ORDER BY name"
        )
    )


@dataclass(frozen=True)
class SchemaSnapshot:
    fingerprint: str
    tables: tuple
    columns: tuple
    indexes: tuple
    triggers: tuple
    fts: tuple
    views: tuple

    def is_blank(self):
        return not (
            self.tables or self.columns or self.indexes
            or self.triggers or self.fts or self.views
        )


def _columns(conn, name):
    rows = conn.execute("PRAGMA table_info(%s)" % quote_ident(name)).fetchall()
    return tuple(
        (row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows
    )


def snapshot(conn):
    tables = entity_table_names(conn)
    fts = fts_names(conn)
    columns = tuple(
        (name, _columns(conn, name)) for name in tuple(tables) + tuple(fts)
    )
    indexes = tuple(
        conn.execute(
            "SELECT name, tbl_name, sql FROM sqlite_master "
            "WHERE type='index' ORDER BY name"
        )
    )
    triggers = tuple(
        conn.execute(
            "SELECT name, tbl_name, sql FROM sqlite_master "
            "WHERE type='trigger' ORDER BY name"
        )
    )
    views = tuple(
        conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name"
        )
    )
    return SchemaSnapshot(
        fingerprint=ddl_fingerprint(conn),
        tables=tables,
        columns=columns,
        indexes=indexes,
        triggers=triggers,
        fts=fts,
        views=views,
    )


def _column_map(columns):
    return {name: cols for name, cols in columns}


def diff_snapshots(actual, expected):
    """返回人类可读的差异。空列表表示结构一致。"""
    diffs = []
    if actual.fingerprint != expected.fingerprint:
        diffs.append(
            "ddl_fingerprint: actual=%s expected=%s"
            % (actual.fingerprint, expected.fingerprint)
        )
    diffs.extend(_diff_names("table", actual.tables, expected.tables))
    diffs.extend(_diff_names("fts", actual.fts, expected.fts))
    diffs.extend(_diff_pairs("view", actual.views, expected.views))
    actual_cols = _column_map(actual.columns)
    expected_cols = _column_map(expected.columns)
    common_tables = [
        name for name in expected.tables if name in set(actual.tables)
    ]
    common_fts = [name for name in expected.fts if name in set(actual.fts)]
    for name in common_tables + common_fts:
        diffs.extend(
            _diff_columns(name, actual_cols.get(name, ()), expected_cols.get(name, ()))
        )
    for name in set(actual.tables) - set(expected.tables):
        diffs.append("table unexpected columns kept for %s" % name)
    diffs.extend(_diff_pairs("index", actual.indexes, expected.indexes))
    diffs.extend(_diff_pairs("trigger", actual.triggers, expected.triggers))
    return diffs


def _diff_names(kind, actual, expected):
    actual_set = set(actual)
    expected_set = set(expected)
    diffs = []
    for name in sorted(expected_set - actual_set):
        diffs.append("%s missing: %s" % (kind, name))
    for name in sorted(actual_set - expected_set):
        diffs.append("%s unexpected: %s" % (kind, name))
    return diffs


def _diff_pairs(kind, actual, expected):
    actual_map = {row[0]: row for row in actual}
    expected_map = {row[0]: row for row in expected}
    diffs = []
    for name in sorted(set(expected_map) - set(actual_map)):
        diffs.append("%s missing: %s" % (kind, name))
    for name in sorted(set(actual_map) - set(expected_map)):
        diffs.append("%s unexpected: %s" % (kind, name))
    for name in sorted(set(actual_map) & set(expected_map)):
        if actual_map[name] != expected_map[name]:
            diffs.append(
                "%s %s: actual=%r expected=%r"
                % (kind, name, actual_map[name], expected_map[name])
            )
    return diffs


def _diff_columns(table, actual, expected):
    diffs = []
    if len(actual) != len(expected):
        diffs.append(
            "columns %s: actual=%s expected=%s"
            % (table, [col[1] for col in actual], [col[1] for col in expected])
        )
    labels = ("cid", "name", "type", "notnull", "dflt_value", "pk")
    for index in range(min(len(actual), len(expected))):
        got = actual[index]
        exp = expected[index]
        if got == exp:
            continue
        column_name = exp[1] if exp[1] == got[1] else "%s/%s" % (got[1], exp[1])
        for label_index, label in enumerate(labels):
            if got[label_index] != exp[label_index]:
                diffs.append(
                    "column %s.%s.%s: actual=%r expected=%r"
                    % (table, column_name, label, got[label_index], exp[label_index])
                )
    return diffs
