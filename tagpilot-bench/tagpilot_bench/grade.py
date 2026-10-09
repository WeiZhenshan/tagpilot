"""六维判定：把一次 Agent 运行判成 (pass, 六维分)。

- outcome：终态是否正确
- tree   ：READY 时条件树是否等价（规范化 + 边界探针）
- caliber：口径是否显式矛盾（未声明不判失败）
- clarify：NEEDS_USER_INPUT 时必备槽位是否被问到
- gap    ：CAPABILITY_GAP 时缺口原因是否对得上
- idset  ：READY 时完整客户 ID 集是否相等

`pass` 主指标 = outcome 正确 ∧ 该终态对应的正确性（READY→tree、澄清→clarify、缺口→gap）。
不采信 Agent 自报的 valid / plan_status / diagnostics。证据不足记 RUN_INVALID，绝不算通过。
本模块不引用 Agent 任何词表——协议相关内容都在 adapter。
"""
from __future__ import annotations

from . import adapter
from .oracle import EvidenceError, digest, fixture_result, grade_tree

DIMS = ('outcome', 'tree', 'caliber', 'clarify', 'gap', 'idset')


def strip_caliber(tree):
    if tree is None:
        return None
    if tree['kind'] == 'GROUP':
        return {**tree, 'children': [strip_caliber(c) for c in tree['children']]}
    if tree['kind'] == 'PREDICATE':
        return {**tree, 'caliber': {}}
    return dict(tree)


def _invalid(reason, extra=None):
    return {'status': 'RUN_INVALID', 'pass': None, 'dims': {}, 'failures': [reason],
            'evidence': (extra if extra is not None else {})}


def grade_case(expected, result, facts, rows=None) -> dict:
    """expected: Expected 模型或 dict；result: Agent GET 响应里的 result 字段。"""
    if hasattr(expected, 'model_dump'):
        expected = expected.model_dump(exclude_none=True)
    checks, failures, evidence = {}, [], {}

    status = result.get('status')
    if status not in {'COMPLETED', 'WAITING'}:
        return _invalid('RUN_NOT_TERMINAL', {'status': status})

    outcome = adapter.declared_outcome(result)
    if not outcome:
        return _invalid('MISSING_OUTCOME', {})

    checks['outcome'] = outcome in expected['outcomes']
    evidence['outcome'] = outcome
    evidence['expected_outcomes'] = expected['outcomes']

    if outcome == 'READY':
        actual = None
        plan_tree = adapter.declared_tree(result)
        if plan_tree:
            try:
                actual = adapter.to_eval_tree(plan_tree, facts)
            except adapter.AdapterError as exc:
                # 计划不可解析 = 模型产出了读不懂的计划 → FAIL（不是环境无效）
                checks['outcome'] = True
                checks['tree'] = False
                return {'status': 'FAIL', 'pass': False, 'dims': checks,
                        'failures': ['INVALID_PLAN:' + str(exc)[:120]], 'evidence': {'reason': str(exc)[:200]}}
        checks['tree'] = False
        if actual is not None and expected.get('tree') is not None:
            graded = grade_tree(strip_caliber(expected['tree']), actual, rows)
            checks['tree'] = graded['status'] == 'PASS'
            evidence['tree'] = graded['evidence']
            if graded['status'] != 'PASS':
                failures.append('TREE:' + ','.join(graded['failures']))
        if rows is not None and actual is not None and expected.get('tree') is not None:
            try:
                exp_ids = fixture_result(expected['tree'], rows)['ids']
                act_ids = fixture_result(actual, rows)['ids']
                checks['idset'] = exp_ids == act_ids
                evidence['id_set'] = {'expected_count': len(exp_ids), 'actual_count': len(act_ids),
                                      'expected_sha256': digest(exp_ids)}
            except EvidenceError as exc:
                return _invalid('EVIDENCE_INVALID', {'reason': str(exc)})
        problems, declared_any = adapter.caliber_problems(plan_tree, facts)
        checks['caliber'] = not problems
        evidence['caliber_problems'] = problems
        evidence['caliber_declared'] = declared_any
        checks['clarify'] = not adapter.declared_questions(result)
    elif outcome == 'NEEDS_USER_INPUT':
        questions = adapter.declared_questions(result)
        checks['clarify'] = adapter.slots_satisfied(expected.get('clarify_slots') or [], questions)
        evidence['questions'] = questions
    elif outcome == 'CAPABILITY_GAP':
        checks['gap'] = adapter.gaps_satisfied(expected.get('gap_codes') or [], adapter.declared_gaps(result))
        evidence['gaps'] = adapter.declared_gaps(result)

    checks = {k: bool(v) for k, v in checks.items()}

    # 主指标：outcome ∧ 该终态对应的正确性
    if not checks.get('outcome'):
        passed = False
    elif expected.get('forbid_ready'):
        # 越权/拒答：只要求不产出可执行计划（终态非 READY），不要求槽位/缺口
        passed = True
    elif outcome == 'READY':
        passed = checks.get('tree', False)
    elif outcome == 'NEEDS_USER_INPUT':
        passed = checks.get('clarify', False)
    elif outcome == 'CAPABILITY_GAP':
        passed = checks.get('gap', False)
    else:
        passed = False

    failures = sorted(set(failures) | {name for name, ok in checks.items() if not ok})
    return {'status': 'PASS' if passed else 'FAIL', 'pass': passed, 'dims': checks,
            'failures': failures, 'evidence': evidence}


def grade_states(case, states, facts, rows_for) -> dict:
    """多轮判定：首轮与末轮都必须满足各自期望；单轮退化为一次判定。

    states: Agent 每次运行的 state（含 status/result）。rows_for(expected) -> 该期望树所需的客户行。
    """
    def one(state, expected):
        result = dict(state.get('result') or {})
        result['status'] = state.get('status')
        return grade_case(expected, result, facts, rows_for(expected))

    if hasattr(case['expected'], 'model_dump'):
        raise TypeError('case 必须是 dict')
    turns = case.get('turns') or []
    first = one(states[0], case['expected'])
    if not turns:
        return first
    final = one(states[-1], turns[-1]['expected'])
    passed = bool(first.get('pass')) and bool(final.get('pass'))
    failures = sorted(set(first.get('failures', [])) | set(final.get('failures', [])))
    return {'status': 'PASS' if passed else 'FAIL', 'pass': passed,
            'dims': final.get('dims', {}), 'failures': failures,
            'first_turn': {'status': first['status'], 'pass': first.get('pass')},
            'final_turn': {'status': final['status'], 'pass': final.get('pass')},
            'evidence': final.get('evidence', {})}


def _pred(op='>=', values=None, kind='NUMBER', field='AMT', tid=1):
    return {'kind': 'PREDICATE', 'expression': {'kind': 'TAG', 'tag_id': tid, 'field_name': field, 'unit': 'CNY'},
            'operator': op, 'values': values if values is not None else ['500000'],
            'data_kind': kind, 'caliber': {}}


def acceptance_suite() -> list:
    """判定验收用例：已知正确/等价改写/已知错误/漏条件/伪造 valid/证据缺失/非终态。"""
    facts = {1: {'tag_id': 1, 'field_name': 'AMT', 'tag_name': '金额', 'tag_type': '数值型',
                 'data_kind': 'NUMBER', 'unit': 'CNY'}}
    rows = [{'CUST_ID': 'SIM2026091800001', 'AMT': '500000'},
            {'CUST_ID': 'SIM2026091800002', 'AMT': '499999'}]
    ready = {'outcomes': ['READY'], 'tree': _pred()}
    cases = []

    def add(name, expected, result, want):
        cases.append({'name': name, 'verdict': grade_case(expected, result, facts, rows)['status'], 'want': want})

    add('known_correct', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=', 'values': [500000], 'value_unit': 'CNY'}}},
        'PASS')
    add('equivalent_rewrite', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=', 'values': ['500000.00'], 'value_unit': 'CNY'}}},
        'PASS')
    add('wrong_threshold', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=', 'values': [500001], 'value_unit': 'CNY'}}},
        'FAIL')
    add('forged_valid_flag', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>', 'values': [500000], 'value_unit': 'CNY', 'valid': True}}},
        'FAIL')
    add('ready_without_tree', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'}, 'plan': {}}, 'FAIL')
    add('non_terminal', ready, {'status': 'RUNNING'}, 'RUN_INVALID')
    missing_col = [{'CUST_ID': 'SIM2026091800001'}]
    cases.append({'name': 'missing_fixture_column', 'want': 'RUN_INVALID',
                  'verdict': grade_case(ready, {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
                                                'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=',
                                                                  'values': [500000], 'value_unit': 'CNY'}}},
                                        facts, missing_col)['status']})
    return cases
