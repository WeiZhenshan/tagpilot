"""纯语义表达式检查。只处理发布证据，不访问业务库、不生成 SQL。"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from tagpilot_agent.guards.diagnostics import PlanError

TIME_KEYS = ('calendar_mode', 'time_anchor_type', 'time_window_unit', 'time_window_value',
             'time_anchor_label', 'time_offset_years', 'time_offset_months', 'period_edge')
ARITHMETIC = {'ADD', 'SUB', 'MUL', 'DIV', 'COUNT_POSITIVE'}


def finite(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or len(str(value)) > 80 or abs(number.as_tuple().exponent) > 30 or abs(number) > Decimal('1e30'):
            raise ValueError()
        return number
    except (ValueError, InvalidOperation):
        raise PlanError('FORMAT_ERROR', '数值必须是有限且合理范围内的十进制数', actions=['repair_plan'])


def tag_identifier(value):
    try:
        result = int(str(value))
        return result if result > 0 else None
    except (ValueError, TypeError):
        return None


def references(expr, depth=0):
    if not isinstance(expr, dict) or depth > 8:
        return set()
    tid = tag_identifier(expr.get('tag_id'))
    result = {tid} if expr.get('kind') == 'TAG' and tid else set()
    args = expr.get('args')
    for child in args[:64] if isinstance(args, list) else []:
        result |= references(child, depth+1)
    return result


def plan_tag_ids(nodes):
    ids = set()
    for node in nodes:
        tid = tag_identifier(node.get('tag_id'))
        if tid:
            ids.add(tid)
        ids |= references(node.get('expression')) | references(node.get('compare_expression'))
    return ids


def caliber_value(key, value, actual):
    # 仅规范化已知同义标签，结构化时点、边界与统计方式必须一致。
    if key == 'time_anchor_label' and value in {'当前', '当前时点'} and actual.get('time_anchor_type') == 'POINT' and actual.get('period_edge') == 'END' and actual.get('statistic') == 'EOP':
        return 'CURRENT_POINT'
    return str(value)


def time_signature(caliber):
    return tuple((k, caliber_value(k, caliber[k], caliber)) for k in TIME_KEYS if caliber.get(k) is not None)


def check_caliber(node, tag):
    expected = node.get('expected_caliber') or {}
    actual = tag.get('caliber_struct') or {}
    if node.get('time_constraint') and not expected:
        raise PlanError('FORMAT_ERROR', '正在补全这项条件的时间解释', actions=['repair_time_parse'])
    if not isinstance(expected, dict):
        raise PlanError('FORMAT_ERROR', '时间解释格式需要修正', actions=['repair_time_parse'])
    missing = {k: v for k, v in expected.items() if v is not None and actual.get(k) is None}
    if missing:
        raise PlanError('METADATA_INCOMPLETE', '候选指标缺少可核验的口径信息', expected=missing,
                        actual=actual, actions=['get_tag_details', 'search_capabilities'])
    mismatch = {k: v for k, v in expected.items() if v is not None and caliber_value(k, actual.get(k), actual) != caliber_value(k, v, actual)}
    if mismatch:
        raise PlanError('CALIBER_CONFLICT', '候选指标的时间或统计范围与要求不同，正在查找匹配口径',
                        expected=mismatch, actual={k: actual.get(k) for k in mismatch},
                        actions=['search_tags', 'search_capabilities'], retryable=True)


def inspect_expression(expr, tags, eligible, capabilities=None, depth=0, budget=None):
    budget = budget if budget is not None else [0]
    budget[0] += 1
    if depth > 8 or budget[0] > 64 or not isinstance(expr, dict):
        raise PlanError('FORMAT_ERROR', '计算表达式过深、过大或格式错误')
    if any(k in expr for k in ('sql', 'field_name', 'table', 'function', 'column')):
        raise PlanError('FORMAT_ERROR', '计算表达式不能指定物理字段或 SQL')
    kind = expr.get('kind')
    if kind == 'TAG':
        tid = int(expr.get('tag_id') or 0)
        if tid not in eligible or tid not in tags:
            raise PlanError('BINDING_MISMATCH', '计算需要可用的已发布指标', actions=['search_tags'])
        tag = tags[tid]
        if not str(tag.get('semantic_type', '')).startswith('NUM_'):
            raise PlanError('FORMAT_ERROR', '计算仅接受数值指标')
        check_caliber(expr, tag)
        scale = finite(tag.get('unit_scale') or 1)
        if scale <= 0:
            raise PlanError('METADATA_INCOMPLETE', '指标单位倍率无效')
        caliber = tag.get('caliber_struct') or {}
        expr.update(name=tag.get('name'), unit=tag.get('unit') or 'NONE', unit_scale=str(scale))
        return {'unit': expr['unit'], 'time': time_signature(caliber),
                'grain': tag.get('grain') or 'CUSTOMER', 'tags': {tid}}
    if kind == 'CONST':
        finite(expr.get('value'))
        return {'unit': expr.get('unit') or 'NONE', 'time': (), 'grain': None, 'tags': set()}
    if kind == 'CAPABILITY':
        key = str(expr.get('capability_id') or '')
        cap = (capabilities or {}).get(key)
        if not cap or str(cap.get('version')) != str(expr.get('version')):
            raise PlanError('CAPABILITY_UNAVAILABLE', '所需计算能力尚未发布或版本不可用', actions=['search_capabilities'])
        deps = set(cap.get('input_tag_ids') or [])
        if not deps <= eligible:
            raise PlanError('PERMISSION_DENIED', '当前不能使用这项计算能力')
        if cap.get('capability_type') not in {'DERIVED_METRIC', 'AGGREGATION_TEMPLATE'}:
            raise PlanError('FORMAT_ERROR', '该业务定义不是数值计算能力')
        check_caliber(expr, cap)
        return {'unit': cap.get('unit') or 'NONE', 'time': time_signature(cap.get('caliber_struct') or {}),
                'grain': cap.get('grain') or 'CUSTOMER', 'tags': deps}
    args = expr.get('args')
    if kind not in ARITHMETIC or not isinstance(args, list) or not (1 <= len(args) <= 12 if kind == 'COUNT_POSITIVE' else len(args) == 2):
        raise PlanError('FORMAT_ERROR', '仅支持登记的算子及正确数量的参数')
    items = [inspect_expression(a, tags, eligible, capabilities, depth + 1, budget) for a in args]
    grains = {x['grain'] for x in items if x['grain']}
    if len(grains) > 1:
        raise PlanError('CALIBER_CONFLICT', '计算输入的客户粒度不同')
    times = {x['time'] for x in items if x['tags']}
    # 跨期只能在逐项具有明确口径证据时显式声明；禁止借此略过输入校验。
    if len(times) > 1 and not (expr.get('time_alignment') == 'EXPLICIT_PERIODS' and
                             all(a.get('expected_caliber') for a, x in zip(args, items) if x['tags'])):
        raise PlanError('CALIBER_CONFLICT', '计算输入的时间口径不同，请核验跨期关系', actions=['get_tag_details', 'repair_plan'])
    units = [x['unit'] for x in items]
    if kind in {'ADD', 'SUB', 'COUNT_POSITIVE'}:
        if len(set(units)) != 1:
            raise PlanError('CALIBER_CONFLICT', '参与计算的指标单位不一致')
        unit = 'COUNT' if kind == 'COUNT_POSITIVE' else units[0]
        if kind == 'COUNT_POSITIVE' and len({frozenset(x['tags']) for x in items}) != len(args):
            raise PlanError('FORMAT_ERROR', '类别计数不能重复计算同一输入')
    elif kind == 'DIV':
        if units[0] == units[1]:
            unit = 'RATIO'
        elif units[1] in {'NONE', 'RATIO'}:
            unit = units[0]
        else:
            raise PlanError('CALIBER_CONFLICT', '不支持这种单位的除法')
    else:
        if units[0] in {'NONE', 'RATIO'}:
            unit = units[1]
        elif units[1] in {'NONE', 'RATIO'}:
            unit = units[0]
        else:
            raise PlanError('CALIBER_CONFLICT', '乘法需要一个无量纲倍率')
    expr.update(unit=unit, null_policy='PROPAGATE')
    return {'unit': unit, 'time': next((x['time'] for x in items if x['tags']), ()), 'grain': next(iter(grains), None),
            'tags': set().union(*(x['tags'] for x in items))}
