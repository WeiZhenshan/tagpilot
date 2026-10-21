"""把被测 Agent 的 AudiencePlan 翻译成评测侧标准 Tree —— 本包唯一知道 Agent 协议的模块。

翻译是单向、独立的：不依赖 Agent 的 `valid` / `plan_status` / 解析结果来证明正确。
结构比对时刻意剥离 caliber（Agent 的口径表达形状与发布快照不保证逐键一致），
口径另做独立检查（见 grade.caliber_check）。

**Agent 改协议时，只需改本文件。** 案例集、oracle、grade、report 都不引用 Agent 词表。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


class AdapterError(ValueError):
    pass


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
    kind = node.get('kind')
    if kind == 'TAG':
        fact = facts.get(int(node['tag_id']))
        if not fact:
            raise AdapterError(f"标签不在事实包: {node.get('tag_id')}")
        return {'kind': 'TAG', 'tag_id': fact['tag_id'], 'field_name': fact['field_name'], 'unit': fact['unit']}
    if kind == 'CONST':
        return {'kind': 'CONST', 'value': _as_value(node['value'], 'NUMBER')}
    if kind == 'COUNT_POSITIVE':
        return {'kind': 'COUNT_POSITIVE', 'unit': 'COUNT', 'args': [_expression(a, facts) for a in node['args']]}
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
        fact = facts.get(int(node.get('tag_id')))
        if not fact:
            raise AdapterError(f"标签不在事实包: {node.get('tag_id')}")
        data_kind = fact['data_kind']
        expression = {'kind': 'TAG', 'tag_id': fact['tag_id'], 'field_name': fact['field_name'], 'unit': fact['unit']}
        operator = node.get('operator')
        values = [_as_value(v, data_kind, node.get('value_scale')) for v in (node.get('values') or [])]
    elif kind == 'DERIVED_PREDICATE':
        expression = _expression(node.get('expression'), facts)
        operator = node.get('operator')
        data_kind = 'NUMBER'
        values = [_as_value(v, data_kind) for v in (node.get('values') or [])]
    else:
        raise AdapterError('未知叶子: ' + str(kind))
    if node.get('unknown_policy') not in {None, 'EXCLUDE'}:
        raise AdapterError('unknown_policy 必须为 EXCLUDE')
    return {'kind': 'PREDICATE', 'expression': expression, 'operator': operator,
            'values': values, 'data_kind': data_kind, 'caliber': {}, 'null_policy': 'EXCLUDE'}


def to_eval_tree(plan_tree, facts):
    if not isinstance(plan_tree, dict):
        raise AdapterError('缺少计划树')
    result = _to_eval_tree_inner(plan_tree, facts)
    # 用评测侧 schema 兜底校验：畸形叶子（如比较操作符无取值）在此判为不可读计划
    from .schema import Tree
    try:
        Tree.model_validate(result)
    except Exception as exc:  # noqa: BLE001
        raise AdapterError(f'计划结构非法: {exc}') from exc
    return result


def _to_eval_tree_inner(plan_tree, facts):
    if 'logic' in plan_tree:
        children = [_to_eval_tree_inner(child, facts) for child in plan_tree.get('children') or []]
        if not children:
            raise AdapterError('空分组')
        return {'kind': 'GROUP', 'logic': plan_tree['logic'], 'children': children}
    return _leaf(plan_tree, facts)


def declared_predicates(plan_tree):
    """产出 (tag_id, value_unit, expected_caliber, time_constraint) 供口径独立检查。"""
    found = []

    def visit(node):
        if not isinstance(node, dict):
            return
        if 'logic' in node:
            for child in node.get('children') or []:
                visit(child)
        elif node.get('kind') == 'TAG_PREDICATE' and node.get('tag_id'):
            found.append({'tag_id': int(node['tag_id']), 'value_unit': node.get('value_unit'),
                          'expected_caliber': node.get('expected_caliber') or {},
                          'time_constraint': node.get('time_constraint')})
        elif node.get('kind') == 'DERIVED_PREDICATE':
            for key in ('expression', 'compare_expression'):
                visit(node.get(key))
    visit(plan_tree)
    return found


def declared_outcome(result):
    """从 Agent 结果取终态；本包不为 Agent 枚举命名，直接透传其字符串。"""
    outcome = (result.get('outcome') or {})
    return outcome.get('outcome')


def declared_questions(result):
    return result.get('questions') or (result.get('plan') or {}).get('questions') or []


def declared_gaps(result):
    return (result.get('outcome') or {}).get('gaps') or []


def declared_tree(result):
    return (result.get('plan') or {}).get('tree')


# ── 以下均为 Agent 协议知识（问题原因词表、缺口词表）——改 Agent 只改这里 ──

_SLOT_REASONS = {
    'threshold': {'THRESHOLD_MISSING'},
    'time_scope': {'DEFINITION_MISSING', 'MULTIPLE_PUBLISHED_DEFINITIONS', 'CONFLICTING_INTERPRETATIONS'},
    'business_scope': {'DEFINITION_MISSING', 'MULTIPLE_PUBLISHED_DEFINITIONS', 'CONFLICTING_INTERPRETATIONS'},
}
_GAP_REASONS = {
    'METADATA_INCOMPLETE': {'METADATA_INCOMPLETE'},
    'NO_PUBLISHED_CAPABILITY': {'NO_CAPABILITY', 'NO_PUBLISHED_TAG'},
    'CALIBER_UNAVAILABLE': {'CALIBER_UNAVAILABLE', 'NO_CAPABILITY'},
    'NULL_OPERATOR_UNAVAILABLE': {'CALIBER_UNAVAILABLE', 'NO_CAPABILITY'},
    'NO_ELIGIBLE_TAG': {'NO_PUBLISHED_TAG', 'NO_CAPABILITY'},
}


def _combined_threshold_question(question) -> bool:
    """合并口径/阈值问句的窄证据规则：明说阈值且提供至少两种数值边界。"""
    import re
    import unicodedata
    if question.get('reason') not in _SLOT_REASONS['business_scope']:
        return False
    if not re.search(r'阈值|门槛', question.get('prompt') or ''):
        return False
    boundaries = set()
    for option in question.get('options') or []:
        if not isinstance(option, str):
            continue
        text = unicodedata.normalize('NFKC', option)
        boundaries.update(re.findall(
            r'(不低于|不高于|不超过|至少|最多|大于|小于|>=|<=|>|<|=|≥|≤)\s*([0-9]+(?:\.[0-9]+)?)\s*(亿元|万元|元|天|次|笔|户|家)', text))
    return len(boundaries) >= 2


def slots_satisfied(required_slots, questions) -> bool:
    questions = questions or []
    reasons = {q.get('reason') for q in questions}
    return all(bool(reasons & _SLOT_REASONS.get(slot, set())) or
               (slot == 'threshold' and any(_combined_threshold_question(q) for q in questions))
               for slot in required_slots)


def gaps_satisfied(codes, gaps) -> bool:
    reasons = {g.get('reason') for g in gaps or []}
    return bool(reasons) and all(reasons & _GAP_REASONS.get(code, set()) for code in codes)


_TIME_CALIBER_KEYS = ('time_anchor_type', 'time_window_unit', 'time_window_value', 'time_offset_months',
                      'time_offset_years', 'calendar_mode', 'period_edge', 'statistic', 'month_of_year')


def caliber_problems(plan_tree, facts) -> tuple[list, bool]:
    """口径独立检查：只判「显式矛盾」，不因代理未复述口径而失败。返回 (problems, declared_any)。

    本包比对 value_unit；结构化时间口径比对需快照 caliber_struct——若标签事实未带
    caliber 则不判冲突（避免伪冲突，见 JUDGE-AUDIT F4）。
    """
    problems, declared_any = [], False
    for declared in declared_predicates(plan_tree):
        fact = facts.get(declared['tag_id'])
        if not fact:
            continue
        if declared['value_unit'] not in {None, fact['unit']}:
            problems.append({'tag_id': fact['tag_id'], 'code': 'VALUE_UNIT',
                             'declared': declared['value_unit'], 'expected': fact['unit']})
        given = {k: v for k, v in (declared['expected_caliber'] or {}).items() if v is not None}
        if given:
            declared_any = True
        expected = {k: v for k, v in (fact.get('caliber') or {}).items() if v is not None}
        for key, value in given.items():
            if key in _TIME_CALIBER_KEYS and key in expected and value != expected[key]:
                problems.append({'tag_id': fact['tag_id'], 'code': 'TIME_CALIBER_CONFLICT',
                                 'field': key, 'declared': value, 'expected': expected[key]})
    return problems, declared_any
