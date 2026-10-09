"""独立解释器与数学规范化。

不导入被测 Agent、Guard 或 Java 编译器；不执行模型生成的 SQL。
只做有数学依据的等价变换，不猜测等价——等价类清单见 docs/legacy/JUDGE-AUDIT.md。

已证明等价：同级 AND/OR 扁平化与子节点排序、码值集合排序、数值格式统一、
单子节点分组 ≡ 其子、between[a,b] ≡ (>=a 且 <=b)、= x ≡ in[x]、!= x ≡ not_in[x]；
AND 内相同表达式/单位/数据类型/口径/NULL 策略的同向数值边界只保留更严格的一侧。
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from itertools import product

from .schema import Tree


class EvidenceError(ValueError):
    """证据缺失或损坏——不得当作 NULL 或失败。"""


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def number(value):
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise EvidenceError('数值数据非法') from exc
    if not result.is_finite():
        raise EvidenceError('非有限数据')
    return result


def expression(expr, row):
    kind = expr['kind']
    if kind == 'TAG':
        if expr['field_name'] not in row:
            raise EvidenceError('证据字段缺失，不等于 NULL')
        return row[expr['field_name']]
    if kind == 'CONST':
        return number(expr['value'])
    args = [number(expression(a, row)) for a in expr['args']]
    if any(a is None for a in args):
        return None
    if kind == 'COUNT_POSITIVE':
        return Decimal(sum(a > 0 for a in args))
    a, b = args
    if kind == 'DIV':
        return None if b == 0 else a / b
    if kind == 'ADD':
        return a + b
    if kind == 'SUB':
        return a - b
    if kind == 'MUL':
        return a * b
    raise EvidenceError('表达式不支持')


def evaluate(tree, row) -> bool:
    kind = tree['kind']
    if kind == 'SCOPE_ALL':
        return True
    if kind == 'GROUP':
        # 先求全部条件，不用短路隐藏缺失/损坏证据。
        values = [evaluate(child, row) for child in tree['children']]
        return all(values) if tree['logic'] == 'AND' else any(values)
    value = expression(tree['expression'], row)
    op = tree['operator']
    if op == 'is_null':
        return value is None
    if op == 'is_not_null':
        return value is not None
    if value is None:
        return False
    kind = tree['data_kind']
    convert = number if kind == 'NUMBER' else date.fromisoformat if kind == 'DATE' else str
    try:
        value = convert(value)
        values = [convert(v) for v in tree['values']]
    except (TypeError, ValueError) as exc:
        raise EvidenceError('日期或字面量证据非法') from exc
    if op == 'in':
        return value in values
    if op == 'not_in':
        return value not in values
    if op == 'contains':
        return bool(values) and values[0] in value
    if op == 'between':
        return len(values) == 2 and values[0] <= value <= values[1]
    if not values:
        raise EvidenceError('比较操作符缺少取值')
    right = values[0]
    return {'=': lambda: value == right, '!=': lambda: value != right,
            '>': lambda: value > right, '>=': lambda: value >= right,
            '<': lambda: value < right, '<=': lambda: value <= right}[op]()


def normalized(tree) -> dict:
    """规范化到可证明等价的形状；只做有数学依据的变换。

    刻意剥离表达式里的 `unit`：单位属口径维度（由 caliber 检查单独判），不参与结构相等——
    否则作者手写的 unit 与 facts 的 unit 不一致会造成伪失败，并因排序键含 unit 而错位。
    """
    result = Tree.model_validate(tree).model_dump(exclude_none=True)

    def strip_unit(node):
        if isinstance(node, dict):
            if node.get('kind') in {'TAG', 'CONST', 'ADD', 'SUB', 'MUL', 'DIV', 'COUNT_POSITIVE'} and 'unit' in node:
                node.pop('unit')
            for value in node.values():
                strip_unit(value)
        elif isinstance(node, list):
            for value in node:
                strip_unit(value)
        return node

    result = strip_unit(result)

    def visit(node):
        if node['kind'] == 'GROUP':
            children = []
            for child in node['children']:
                child = visit(child)
                if child['kind'] == 'GROUP' and child['logic'] == node['logic']:
                    children.extend(child['children'])
                else:
                    children.append(child)
            if node['logic'] == 'AND':
                bounds = {}
                others = []
                for child in children:
                    op = child.get('operator')
                    if child['kind'] != 'PREDICATE' or child.get('data_kind') != 'NUMBER' or op not in {'>', '>=', '<', '<='}:
                        others.append(child)
                        continue
                    identity = digest({k: v for k, v in child.items() if k not in {'operator', 'values'}})
                    direction = 'lower' if op in {'>', '>='} else 'upper'
                    key = (identity, direction)
                    rank = (number(child['values'][0]), op == '>' if direction == 'lower' else op == '<=')
                    prior = bounds.get(key)
                    if prior is None or (rank > prior[0] if direction == 'lower' else rank < prior[0]):
                        bounds[key] = (rank, child)
                children = others + [child for _rank, child in bounds.values()]
            if len(children) == 1:
                return children[0]
            node['children'] = sorted(children, key=digest)
            return node
        if node['kind'] == 'PREDICATE':
            if node['data_kind'] == 'NUMBER':
                node['values'] = [format(number(v).normalize(), 'f') for v in node['values']]
            if node['operator'] in {'in', 'not_in'}:
                node['values'] = sorted(node['values'])
            if node['operator'] == 'between':
                base = {k: v for k, v in node.items() if k not in ('operator', 'values')}
                low, high = node['values']
                rewritten = {'kind': 'GROUP', 'logic': 'AND', 'children': [
                    {**base, 'operator': '>=', 'values': [low]},
                    {**base, 'operator': '<=', 'values': [high]}]}
                # 经模型回环取得规范形状（补齐默认字段）；再剥一次 unit（回环会补默认 unit）。
                return visit(strip_unit(Tree.model_validate(rewritten).model_dump(exclude_none=True)))
            if node['operator'] == '=':
                node['operator'], node['values'] = 'in', [node['values'][0]]
            elif node['operator'] == '!=':
                node['operator'], node['values'] = 'not_in', [node['values'][0]]
            return node
        return node

    return visit(result)


def references(tree) -> set:
    if tree is None:
        return set()

    def scan(value):
        found = set()
        if isinstance(value, dict):
            if value.get('kind') == 'TAG':
                found.add(value['tag_id'])
            for item in value.values():
                found |= scan(item)
        elif isinstance(value, list):
            for item in value:
                found |= scan(item)
        return found
    return scan(tree)


def fields(tree) -> set:
    """树引用的物理字段名——用于只拉取所需列。"""
    if tree is None:
        return set()

    def scan(value):
        found = set()
        if isinstance(value, dict):
            if value.get('kind') == 'TAG' and value.get('field_name'):
                found.add(value['field_name'])
            for item in value.values():
                found |= scan(item)
        elif isinstance(value, list):
            for item in value:
                found |= scan(item)
        return found
    return scan(tree)


def fixture_result(tree, rows) -> dict:
    ids = sorted(r['CUST_ID'] for r in rows if evaluate(tree, r))
    return {'count': len(ids), 'ids_sha256': digest(ids), 'ids': ids}


def boundary_rows(tree) -> list:
    """一元扰动 + 有限全组合；只构造校验探针（见 JUDGE-AUDIT F2：>4096 退化为单字段扰动）。"""
    pools = {}
    direct_fields = set()

    def expr_fields(expr):
        if expr['kind'] == 'TAG':
            pools.setdefault(expr['field_name'], [None, '0', '1', '-1', '100'])
        for child in expr.get('args', []):
            expr_fields(child)

    def scan(node):
        if node['kind'] == 'GROUP':
            for child in node['children']:
                scan(child)
        elif node['kind'] == 'PREDICATE':
            expr = node['expression']
            expr_fields(expr)
            if expr['kind'] != 'TAG':
                return
            field = expr['field_name']
            values = node['values']
            if node['data_kind'] == 'NUMBER':
                pool = [None, '0', '-1']
                for value in values:
                    n = number(value)
                    pool.extend(format(n + d, 'f') for d in [Decimal('-.01'), Decimal('0'), Decimal('.01')])
            elif node['data_kind'] == 'DATE':
                pool = [None]
                for value in values:
                    d = date.fromisoformat(value)
                    pool.extend((d + timedelta(days=delta)).isoformat() for delta in [-1, 0, 1])
            else:
                pool = [None, '__UNKNOWN__', *values]
            previous = pools[field] if field in direct_fields else []
            pools[field] = list(dict.fromkeys(previous + pool))
            direct_fields.add(field)

    scan(tree)
    if not pools:
        return [{}]
    size = 1
    for values in pools.values():
        size *= len(values)
    if size <= 4096:
        return [dict(zip(pools, vals)) for vals in product(*pools.values())]
    baseline = {field: next((v for v in values if v is not None), '0') for field, values in pools.items()}
    return [{**baseline, field: v} for field, values in pools.items() for v in values]


def grade_tree(expected, actual, rows=None) -> dict:
    """结构层判定：规范化相等 + 字段绑定相等 + 边界探针相等（+ 完整 ID 集相等）。"""
    try:
        a, b = normalized(expected), normalized(actual)
        checks = {'normalized_tree_equal': a == b}

        def bindings(value):
            if isinstance(value, dict):
                found = {(value['tag_id'], value['field_name'])} if value.get('kind') == 'TAG' else set()
                for v in value.values():
                    found |= bindings(v)
                return found
            if isinstance(value, list):
                result = set()
                for v in value:
                    result |= bindings(v)
                return result
            return set()

        if bindings(a) != bindings(b):
            return {'status': 'FAIL', 'checks': {**checks, 'field_bindings_equal': False},
                    'failures': ['FIELD_BINDING_MISMATCH'], 'evidence': {}}
        probes = boundary_rows(a)
        checks['boundary_equal'] = references(a) == references(b) and all(evaluate(a, r) == evaluate(b, r) for r in probes)
        evidence = {'boundary_rows': len(probes)}
        if rows is not None:
            er, ar = fixture_result(a, rows), fixture_result(b, rows)
            checks['full_id_set_equal'] = er['ids'] == ar['ids']
            evidence.update(expected_count=er['count'], actual_count=ar['count'],
                            expected_ids_sha256=er['ids_sha256'], actual_ids_sha256=ar['ids_sha256'])
        return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
                'failures': [k for k, v in checks.items() if not v], 'evidence': evidence}
    except EvidenceError as exc:
        return {'status': 'RUN_INVALID', 'checks': {}, 'failures': ['EVIDENCE_INVALID'], 'evidence': {'reason': str(exc)}}
    except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
        return {'status': 'FAIL', 'checks': {}, 'failures': ['INVALID_PLAN'], 'evidence': {'reason': type(exc).__name__}}
