"""标签事实：tag_id → 字段名/类型/单位，供 adapter 把 Agent 计划翻译成评测侧条件树。

只读 tl_tag / ts_tag_semantic；不连业务库、不执行查询。事实以 (library_id, 快照/build) 为准，
复跑时先固定版本再取事实。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .db import DEFAULT, _connect

LIBRARY_ID = 107


def _data_kind(tag_type: str) -> str:
    if tag_type == '日期型':
        return 'DATE'
    if tag_type in ('文本型', '选项型'):
        return 'STRING'
    return 'NUMBER'  # 数值型 / 布尔型


@lru_cache(maxsize=4)
def load(library_id: int = LIBRARY_ID, args_key: str | None = None) -> dict:
    """返回 {tag_id: {field_name, tag_name, tag_type, data_kind, unit}}。"""
    args = {**DEFAULT}
    conn = _connect({**args, 'database': 'ry'})
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT t.tag_id, t.field_name, t.tag_name, t.tag_type, s.unit '
                'FROM tl_tag t LEFT JOIN ts_tag_semantic s ON s.tag_id = t.tag_id '
                'WHERE t.library_id = %s AND t.status = 2', (library_id,))
            facts = {}
            for tag_id, field_name, tag_name, tag_type, unit in cur.fetchall():
                facts[int(tag_id)] = {
                    'tag_id': int(tag_id), 'field_name': field_name, 'tag_name': tag_name,
                    'tag_type': tag_type, 'data_kind': _data_kind(tag_type), 'unit': unit or 'NONE',
                }
            return facts
    finally:
        conn.close()


def field_of(tag_id: int, facts: dict | None = None) -> str:
    facts = facts if facts is not None else load()
    fact = facts.get(int(tag_id))
    if not fact:
        raise KeyError(f'标签不在事实包: {tag_id}')
    return fact['field_name']


def align_data_kind(tree, facts: dict):
    """把树的每个 TAG 叶子的 data_kind 对齐到 facts（同一字段由 facts 唯一定义）。

    作者手写的 STRING vs facts 的 NUMBER 会造成伪不等价，且因排序键含 data_kind 而错位。
    """
    if not tree:
        return tree
    if tree.get('kind') == 'GROUP':
        for child in tree.get('children') or []:
            align_data_kind(child, facts)
    elif tree.get('kind') == 'PREDICATE':
        expr = tree.get('expression') or {}
        if expr.get('kind') == 'TAG' and int(expr.get('tag_id') or 0) in facts:
            tree['data_kind'] = facts[int(expr['tag_id'])]['data_kind']
    return tree


def from_snapshot(path: str | Path) -> dict:
    """从语义快照 JSONL 取事实（离线、不连库）。仅取 kind=tag 行。"""
    facts = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get('kind') != 'tag':
            continue
        tag_id = int(row['tag_id'])
        tag_type = row.get('tag_type') or ''
        facts[tag_id] = {
            'tag_id': tag_id, 'field_name': row.get('field_name'), 'tag_name': row.get('tag_name'),
            'tag_type': tag_type, 'data_kind': _data_kind(tag_type),
            'unit': (row.get('published_semantics') or {}).get('unit', 'NONE'),
        }
    return facts
