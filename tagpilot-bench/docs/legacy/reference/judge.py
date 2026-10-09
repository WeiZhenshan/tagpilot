"""终态级裁判：对真实运行输出做独立判定，不采信 Agent 的 valid / 解析字段。

判定分两层：
- 结构层：把 AudiencePlan 翻译成标准树后做严格标准化、边界探针与完整 ID 集比对；
- 业务层：终态是否符合预期、澄清槽位是否被问到、能力缺口原因是否对得上、口径是否显式声明。
任一层失败即判 FAIL；证据不足以判断记 RUN_INVALID，绝不当作通过。
"""
import re
import unicodedata
from .io import digest
from .oracle import EvidenceError, grade_tree, normalized, fixture_result
from .plan_adapter import AdapterError, to_eval_tree, declared_predicates

_SLOT_REASONS = {
    'threshold': {'THRESHOLD_MISSING'},
    'time_scope': {'DEFINITION_MISSING', 'MULTIPLE_PUBLISHED_DEFINITIONS',
                   'CONFLICTING_INTERPRETATIONS'},
    'business_scope': {'DEFINITION_MISSING','MULTIPLE_PUBLISHED_DEFINITIONS','CONFLICTING_INTERPRETATIONS'},
}
_GAP_REASONS = {
    'METADATA_INCOMPLETE': {'METADATA_INCOMPLETE'},
    'NO_PUBLISHED_CAPABILITY': {'NO_CAPABILITY', 'NO_PUBLISHED_TAG'},
    'CALIBER_UNAVAILABLE': {'CALIBER_UNAVAILABLE', 'NO_CAPABILITY'},
    'NULL_OPERATOR_UNAVAILABLE': {'CALIBER_UNAVAILABLE', 'NO_CAPABILITY'},
    'NO_ELIGIBLE_TAG': {'NO_PUBLISHED_TAG', 'NO_CAPABILITY'},
}
_FAILURE_LABEL = {
    'run_terminal': 'RUN_NOT_TERMINAL', 'outcome_expected': 'OUTCOME',
    'tree_present': 'NO_TREE', 'tree_equal': 'TREE', 'full_id_set_equal': 'FULL_ID_SET',
    'caliber_consistent': 'CALIBER', 'no_open_questions': 'UNEXPECTED_QUESTIONS',
    'slots_asked': 'SLOTS', 'interrupt_issued': 'NO_INTERRUPT', 'gap_reasons': 'GAP_REASON',
    'first_turn_expectation': 'FIRST_TURN',
}


def strip_caliber(tree):
    if tree is None:
        return None
    if tree['kind'] == 'GROUP':
        return {**tree, 'children': [strip_caliber(c) for c in tree['children']]}
    if tree['kind'] == 'PREDICATE':
        return {**tree, 'caliber': {}}
    return dict(tree)


def _time_caliber(fact):
    """只取结构化时间/统计口径用于比对；time_anchor_label 是展示文案，参与比对会产生伪冲突。"""
    caliber = fact['published_semantics']['caliber_struct'] or {}
    return {k: caliber.get(k) for k in
            ('time_anchor_type', 'time_window_unit', 'time_window_value',
             'time_offset_months', 'time_offset_years', 'calendar_mode', 'period_edge',
             'statistic', 'month_of_year')
            if caliber.get(k) is not None}


def caliber_declared(plan_tree, facts):
    """口径独立检查：只判「显式矛盾」，不因代理未复述口径而失败。

    标签身份本身已确定口径；代理若额外声明了与发布快照冲突的非空时间/单位值，才判失败。
    """
    problems, declared_any = [], False
    for declared in declared_predicates(plan_tree):
        fact = facts.get(declared['tag_id'])
        if not fact:
            continue
        semantics = fact['published_semantics']
        if declared['value_unit'] not in {None, semantics['unit']}:
            problems.append({'tag_id': fact['tag_id'], 'code': 'VALUE_UNIT',
                             'declared': declared['value_unit'], 'expected': semantics['unit']})
        given = {k: v for k, v in (declared['expected_caliber'] or {}).items() if v is not None}
        if given:
            declared_any = True
        for key, value in given.items():
            expected = _time_caliber(fact)
            if key in expected and value != expected[key]:
                problems.append({'tag_id': fact['tag_id'], 'code': 'TIME_CALIBER_CONFLICT',
                                 'field': key, 'declared': value, 'expected': expected[key]})
    return problems, declared_any


def _combined_threshold_question(question):
    """合并口径/阈值问句的窄证据规则：明说阈值且提供至少两种数值边界。

    单纯窗口选项、不同问题中的数字、重复同一边界均不能补足阈值槽位。
    不进行模型自由评分，也不改写案例所需槽位。
    """
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
            r'(不低于|不高于|不超过|至少|最多|大于|小于|>=|<=|>|<|=|≥|≤)\s*'
            r'([0-9]+(?:\.[0-9]+)?)\s*(亿元|万元|元|天|次|笔|户|家)', text))
    return len(boundaries) >= 2


def _slots_satisfied(required_slots, questions):
    questions = questions or []
    reasons = {q.get('reason') for q in questions}
    return all(bool(reasons & _SLOT_REASONS.get(slot, set())) or
               (slot == 'threshold' and any(_combined_threshold_question(q) for q in questions))
               for slot in required_slots)


def _gaps_satisfied(codes, gaps):
    reasons = {g.get('reason') for g in gaps or []}
    return bool(reasons) and all(reasons & _GAP_REASONS.get(code, set()) for code in codes)


def grade_case(case, expected, result, facts, rows=None):
    """result 为 Agent 的 GET 响应（含 status/result），此处传 result 字段本身。"""
    checks, failures, evidence = {}, [], {}
    status = result.get('status')
    if status not in {'COMPLETED', 'WAITING'}:
        return {'status': 'RUN_INVALID', 'checks': {}, 'failures': ['RUN_NOT_TERMINAL:' + str(status)],
                'evidence': {'status': status}}
    outcome = (result.get('outcome') or {}).get('outcome')
    plan = result.get('plan') or {}
    checks['run_terminal'] = True
    if not outcome:
        return {'status': 'RUN_INVALID', 'checks': checks, 'failures': ['MISSING_OUTCOME'],
                'evidence': {}}
    checks['outcome_expected'] = outcome in expected['outcomes']
    evidence['outcome'] = outcome
    evidence['expected_outcomes'] = expected['outcomes']
    # 只有 READY 才要求可执行的标准树；澄清/缺口题允许未绑定叶子，不得因此判无效。
    actual_tree = None
    if outcome == 'READY' and plan.get('tree'):
        try:
            actual_tree = to_eval_tree(plan.get('tree'), facts)
        except AdapterError as exc:
            return {'status': 'RUN_INVALID', 'checks': checks,
                    'failures': ['PLAN_UNREADABLE:' + str(exc)], 'evidence': evidence}
    if outcome == 'READY':
        checks['tree_present'] = actual_tree is not None
        if actual_tree is not None and expected.get('tree') is not None:
            graded = grade_tree(strip_caliber(expected['tree']), actual_tree, rows)
            checks['tree_equal'] = graded['status'] == 'PASS'
            evidence['tree'] = graded['evidence']
            if graded['status'] != 'PASS':
                failures.append('TREE:' + ','.join(graded['failures']))
            if rows is not None:
                try:
                    expected_ids = fixture_result(expected['tree'], rows)['ids']
                    actual_ids = fixture_result(actual_tree, rows)['ids']
                except EvidenceError as exc:
                    return {'status': 'RUN_INVALID', 'checks': checks,
                            'failures': ['EVIDENCE_INVALID:' + str(exc)], 'evidence': evidence}
                checks['full_id_set_equal'] = expected_ids == actual_ids
                evidence['id_set'] = {'expected_count': len(expected_ids), 'actual_count': len(actual_ids),
                                      'expected_sha256': digest(expected_ids)}
        problems, declared_any = caliber_declared(plan.get('tree'), facts)
        checks['caliber_consistent'] = not problems
        evidence['caliber_problems'] = problems
        evidence['caliber_declared'] = declared_any
        checks['no_open_questions'] = not (plan.get('questions') or result.get('questions'))
    elif outcome == 'NEEDS_USER_INPUT':
        questions = result.get('questions') or []
        checks['slots_asked'] = _slots_satisfied(expected.get('required_slots') or [], questions)
        evidence['questions'] = questions
        checks['interrupt_issued'] = bool(result.get('interrupt_id'))
    elif outcome == 'CAPABILITY_GAP':
        gaps = (result.get('outcome') or {}).get('gaps') or []
        checks['gap_reasons'] = _gaps_satisfied(expected.get('gap_codes') or [], gaps)
        evidence['gaps'] = gaps
    checks = {k: bool(v) for k, v in checks.items()}
    failures = sorted(set(failures) | {_FAILURE_LABEL[k] for k, v in checks.items()
                                       if not v and k in _FAILURE_LABEL})
    status_out = 'PASS' if all(checks.values()) else 'FAIL'
    return {'status': status_out, 'checks': checks, 'failures': failures, 'evidence': evidence}


def acceptance_suite():
    """裁判验收用例：已知正确/等价/已知错误/漏条件/伪造通过/证据缺失。"""
    def pred(op='>=', values=None, kind='NUMBER', field='AMT', tid=1):
        return {'kind': 'PREDICATE', 'expression': {'kind': 'TAG', 'tag_id': tid,
                'field_name': field, 'unit': 'CNY'}, 'operator': op,
                'values': values if values is not None else ['500000'], 'data_kind': kind,
                'caliber': {}}
    facts = {1: {'tag_id': 1, 'field_name': 'AMT', 'tag_type': '数值型', 'codes': [],
                 'published_semantics': {'unit': 'CNY', 'caliber_struct': {}}}}
    plan = lambda leaf: {'tree': leaf}
    cases = []
    def add(name, expected, result, rows, want):
        case = {'case_id': 'ACC', 'expected': expected}
        cases.append({'name': name, 'verdict': grade_case(case, expected, result, facts, rows)['status'],
                      'want': want})
    ready = {'outcomes': ['READY'], 'tree': pred()}
    rows = [{'CUST_ID': 'SIM2026091800001', 'AMT': '500000'},
            {'CUST_ID': 'SIM2026091800002', 'AMT': '499999'}]
    add('known_correct', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=',
                           'values': [500000], 'value_unit': 'CNY',
                           'expected_caliber': {}}}}, rows, 'PASS')
    add('equivalent_rewrite', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=',
                           'values': ['500000.00'], 'value_unit': 'CNY',
                           'expected_caliber': {}}}}, rows, 'PASS')
    add('wrong_threshold', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=',
                           'values': [500001], 'value_unit': 'CNY',
                           'expected_caliber': {}}}}, rows, 'FAIL')
    add('forged_valid_flag', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>',
                           'values': [500000], 'value_unit': 'CNY', 'valid': True,
                           'expected_caliber': {}}}}, rows, 'FAIL')
    add('ready_without_tree', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'}, 'plan': {}}, rows, 'FAIL')
    add('missing_fixture_column', ready,
        {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'},
         'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=',
                           'values': [500000], 'value_unit': 'CNY',
                           'expected_caliber': {}}}}, [{'CUST_ID': 'SIM2026091800001'}], 'RUN_INVALID')
    add('non_terminal', ready, {'status': 'RUNNING'}, rows, 'RUN_INVALID')
    return cases
