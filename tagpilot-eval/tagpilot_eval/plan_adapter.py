"""把被测 Agent 的 AudiencePlan(schema_version=3) 翻译成评测侧标准 Tree。

翻译是单向、独立的：不依赖 Agent 的解析结果、Guard 或 `valid` 字段来证明正确。
结构比对时刻意剥离 `caliber`（Agent 的口径表达形状与发布快照不保证逐键一致），
口径另做独立检查，见 judge.caliber_declared。
"""
from decimal import Decimal, InvalidOperation
from typing import Any


class AdapterError(ValueError):
    pass


def _data_kind(fact):
    if fact['codes'] or fact['tag_type'] == '文本型':
        return 'STRING'
    if fact['tag_type'] == '日期型':
        return 'DATE'
    return 'NUMBER'


def _as_value(value, data_kind, scale=None):
    if isinstance(value, bool):
        raise AdapterError('布尔字面量非法')
    if isinstance(value, (int, float)) or (isinstance(value, str) and data_kind == 'NUMBER'):
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise AdapterError('数值字面量非法') from exc
        if scale not in (None, '', 1, '1', 1.0, '1.0'):
            try:
                number *= Decimal(str(scale))
            except InvalidOperation as exc:
                raise AdapterError('value_scale 非法') from exc
        if data_kind == 'NUMBER':
            return format(number.normalize(), 'f')
        return str(value)
    return str(value)


def _expression(node, facts):
    """Agent 表达式 → 标准表达式。CAPABILITY/CONST 之外的组合保持结构。"""
    kind = node.get('kind')
    if kind == 'TAG':
        fact = facts.get(node['tag_id'])
        if not fact:
            raise AdapterError(f"标签不在事实包: {node.get('tag_id')}")
        return {'kind': 'TAG', 'tag_id': fact['tag_id'],
                'field_name': fact['field_name'], 'unit': fact['published_semantics']['unit']}
    if kind == 'CONST':
        return {'kind': 'CONST', 'value': _as_value(node['value'], 'NUMBER')}
    if kind == 'COUNT_POSITIVE':
        return {'kind': 'COUNT_POSITIVE', 'unit': 'COUNT',
                'args': [_expression(a, facts) for a in node['args']]}
    if kind in {'ADD', 'SUB', 'MUL', 'DIV'}:
        args = [_expression(a, facts) for a in node['args']]
        unit = 'RATIO' if kind == 'DIV' else (node.get('unit') or 'NONE')
        return {'kind': kind, 'unit': unit, 'args': args}
    if kind == 'CAPABILITY':
        raise AdapterError('能力引用不能作为可执行表达式参与结构比对')
    raise AdapterError('未知表达式: ' + str(kind))


def _leaf(node, facts):
    kind = node.get('kind')
    if kind == 'SCOPE_ALL':
        return {'kind': 'SCOPE_ALL'}
    if kind == 'TAG_PREDICATE':
        fact = facts.get(node.get('tag_id'))
        if not fact:
            raise AdapterError(f"标签不在事实包: {node.get('tag_id')}")
        data_kind = _data_kind(fact)
        expression = _expression({'kind': 'TAG', 'tag_id': fact['tag_id']}, facts)
        operator = node.get('operator')
        values = [_as_value(v, data_kind, node.get('value_scale')) for v in (node.get('values') or [])]
    elif kind == 'DERIVED_PREDICATE':
        expression = _expression(node.get('expression'), facts)
        operator = node.get('operator')
        data_kind = 'NUMBER'
        values = [_as_value(v, data_kind) for v in (node.get('values') or [])]
    else:
        raise AdapterError('未知叶子: ' + str(kind))
    # unknown_policy=INCLUDE 表示把未知当作满足，与评测的显式 NULL 排除规则冲突。
    if node.get('unknown_policy') not in {None, 'EXCLUDE'}:
        raise AdapterError('unknown_policy 必须为 EXCLUDE')
    return {'kind': 'PREDICATE', 'expression': expression, 'operator': operator,
            'values': values, 'data_kind': data_kind, 'caliber': {},
            'null_policy': 'EXCLUDE'}


def to_eval_tree(plan_tree, facts):
    if not isinstance(plan_tree, dict):
        raise AdapterError('缺少计划树')
    if 'logic' in plan_tree:
        children = [to_eval_tree(child, facts) for child in plan_tree.get('children') or []]
        if not children:
            raise AdapterError('空分组')
        return {'kind': 'GROUP', 'logic': plan_tree['logic'], 'children': children}
    return _leaf(plan_tree, facts)


def declared_predicates(plan_tree):
    """产出 (tag_id, value_unit, expected_caliber) 供口径独立检查。"""
    found = []
    def visit(node):
        if not isinstance(node, dict):
            return
        if 'logic' in node:
            for child in node.get('children') or []:
                visit(child)
        elif node.get('kind') == 'TAG_PREDICATE' and node.get('tag_id'):
            found.append({'tag_id': node['tag_id'], 'value_unit': node.get('value_unit'),
                          'expected_caliber': node.get('expected_caliber') or {},
                          'time_constraint': node.get('time_constraint')})
        elif node.get('kind') == 'DERIVED_PREDICATE':
            for key in ('expression', 'compare_expression'):
                visit(node.get(key))
    visit(plan_tree)
    return found
