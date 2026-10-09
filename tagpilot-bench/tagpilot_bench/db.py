"""只读访问 indiv_cust 宽表，供 oracle 实算客户 ID 集。

刻意只读：不建群、不改客户数据（沿用旧体系约束）。用 PyMySQL 驱动以获得正确的
NULL 语义；可用环境变量覆盖连接。
"""
from __future__ import annotations

import os

TABLE = 'L_INDVCST_LABEL'
DEFAULT = {
    'host': os.environ.get('BENCH_DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('BENCH_DB_PORT', '3306')),
    'user': os.environ.get('BENCH_DB_USER', 'root'),
    'password': os.environ.get('BENCH_DB_PASSWORD', '123456'),
    'database': os.environ.get('BENCH_DB_NAME', 'indiv_cust'),
}


class DbError(RuntimeError):
    pass


def _connect(args: dict):
    try:
        import pymysql
    except ImportError as exc:  # pragma: no cover
        raise DbError('需要 PyMySQL（pip install pymysql）') from exc
    return pymysql.connect(charset='utf8mb4', cursorclass=pymysql.cursors.Cursor, **args)


def load_rows(columns, where: str | None = None, args: dict | None = None) -> list[dict]:
    """读取 CUST_ID + 指定列，返回 list[dict]，值为 str 或 None。"""
    args = {**DEFAULT, **(args or {})}
    cols = ['CUST_ID'] + [c for c in dict.fromkeys(columns) if c != 'CUST_ID']
    select = ', '.join(f'`{c}`' for c in cols)
    query = f'SELECT {select} FROM {TABLE}'
    if where:
        query += f' WHERE {where}'
    conn = _connect(args)
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = []
            for record in cur.fetchall():
                rows.append({c: (None if v is None else str(v)) for c, v in zip(cols, record)})
            return rows
    finally:
        conn.close()


def count(query_where: str | None = None, args: dict | None = None) -> int:
    args = {**DEFAULT, **(args or {})}
    query = f'SELECT COUNT(*) FROM {TABLE}'
    if query_where:
        query += f' WHERE {query_where}'
    conn = _connect(args)
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def total(args: dict | None = None) -> int:
    return count(None, args)


def raw_ids(sql: str, args: dict | None = None) -> list[str]:
    """执行只读投影 SQL（单列）取 ID 集；仅用于 L3 换投影。"""
    args = {**DEFAULT, **(args or {})}
    conn = _connect(args)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [str(row[0]) for row in cur.fetchall() if row[0] is not None]
    finally:
        conn.close()
