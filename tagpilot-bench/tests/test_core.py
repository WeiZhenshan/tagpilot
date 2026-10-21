"""核心单元测试：树规范化等价类、判定验收套件、schema 校验。"""
import pytest

from tagpilot_bench.grade import acceptance_suite, grade_case
from tagpilot_bench.oracle import boundary_rows, evaluate, fixture_result, grade_tree, normalized
from tagpilot_bench.schema import Tree


def pred(op='>=', values=None, kind='NUMBER', field='AMT', tid=1):
    return {'kind': 'PREDICATE', 'expression': {'kind': 'TAG', 'tag_id': tid, 'field_name': field, 'unit': 'CNY'},
            'operator': op, 'values': values if values is not None else ['500000'],
            'data_kind': kind, 'caliber': {}}


ROWS = [{'CUST_ID': 'SIM2026091800001', 'AMT': '500000'},
        {'CUST_ID': 'SIM2026091800002', 'AMT': '499999'},
        {'CUST_ID': 'SIM2026091800003', 'AMT': '600000'}]


def test_normalized_equivalent_rewrites():
    # 数值格式等价
    assert normalized(pred('>=', ['500000'])) == normalized(pred('>=', ['500000.00']))
    # = x ≡ in[x]
    assert normalized(pred('=', ['5'])) == normalized(pred('in', ['5']))
    # != x ≡ not_in[x]
    assert normalized(pred('!=', ['5'])) == normalized(pred('not_in', ['5']))
    # 码值集合排序
    assert normalized(pred('in', ['C3', 'C1'], kind='STRING')) == normalized(pred('in', ['C1', 'C3'], kind='STRING'))


def test_normalized_between_expands():
    a = normalized(pred('between', ['10', '20']))
    b = normalized({'kind': 'GROUP', 'logic': 'AND', 'children': [pred('>=', ['10']), pred('<=', ['20'])]})
    assert a == b


def test_normalized_does_not_guess():
    # 不同阈值不判等价
    assert normalized(pred('>=', ['500000'])) != normalized(pred('>=', ['500001']))
    # AND/OR 改变不判等价
    g_and = {'kind': 'GROUP', 'logic': 'AND', 'children': [pred('>=', ['1']), pred('<=', ['9'])]}
    g_or = {'kind': 'GROUP', 'logic': 'OR', 'children': [pred('>=', ['1']), pred('<=', ['9'])]}
    assert normalized(g_and) != normalized(g_or)


def test_fixture_result_and_idset():
    t = pred('>=', ['500000'])
    res = fixture_result(t, ROWS)
    assert res['count'] == 2
    assert res['ids'] == ['SIM2026091800001', 'SIM2026091800003']


def test_normalized_ignores_expression_unit():
    # 单位属口径维度，不参与结构相等（否则作者 unit 与 facts unit 不一致会伪失败）
    a = pred('>=', ['500000'])
    b = pred('>=', ['500000'])
    b['expression'] = {**b['expression'], 'unit': 'NONE'}
    assert normalized(a) == normalized(b)


def test_grade_states_multiturn_requires_both_turns():
    # 多轮：首轮与末轮各自期望都要满足（曾用首轮期望判末轮，致 45 条假失败）
    from tagpilot_bench.grade import grade_states
    facts = {1: {'tag_id': 1, 'field_name': 'AMT', 'tag_name': '金额', 'tag_type': '数值型',
                 'data_kind': 'NUMBER', 'unit': 'CNY'}}
    rows = [{'CUST_ID': 'SIM2026091800001', 'AMT': '500000'}]
    case = {'expected': {'outcomes': ['NEEDS_USER_INPUT'], 'clarify_slots': ['threshold']},
            'turns': [{'expected': {'outcomes': ['READY'], 'tree': pred('>=', ['500000'])}}]}
    first_ok = {'status': 'WAITING', 'result': {'outcome': {'outcome': 'NEEDS_USER_INPUT'},
                                                'questions': [{'reason': 'THRESHOLD_MISSING', 'prompt': '阈值？'}]}}
    final_ok = {'status': 'COMPLETED', 'result': {'outcome': {'outcome': 'READY'},
                                                  'plan': {'tree': {'kind': 'TAG_PREDICATE', 'tag_id': 1, 'operator': '>=',
                                                                    'values': [500000], 'value_unit': 'CNY'}}}}
    final_bad = {'status': 'COMPLETED', 'result': {'outcome': {'outcome': 'NEEDS_USER_INPUT'}, 'questions': []}}
    rf = lambda exp: rows
    assert grade_states(case, [first_ok, final_ok], facts, rf)['pass'] is True
    assert grade_states(case, [first_ok, final_bad], facts, rf)['pass'] is False


def test_align_data_kind_fixes_flag_mismatch():
    # 布尔标志：作者手写 STRING vs facts 的 NUMBER 会造成伪不等价（且排序错位）
    from tagpilot_bench.facts import align_data_kind
    facts = {1: {'tag_id': 1, 'data_kind': 'NUMBER'}}
    t = pred('=', ['0'], kind='STRING')
    align_data_kind(t, facts)
    assert t['data_kind'] == 'NUMBER'


def test_grade_tree_boundary_detects_endpoint_shift():
    a, b = pred('>=', ['500000']), pred('>', ['500000'])
    graded = grade_tree(a, b, ROWS)
    assert graded['status'] == 'FAIL'  # 边界探针在 500000 处不同


def test_boundary_rows_nonempty():
    assert len(boundary_rows(pred('>=', ['500000']))) >= 1


def test_grader_acceptance_suite():
    for case in acceptance_suite():
        assert case['verdict'] == case['want'], case['name']


def test_schema_rejects_bad_between():
    with pytest.raises(ValueError):
        Tree.model_validate(pred('between', ['20', '10']))  # 端点倒置


def test_schema_rejects_is_null_with_value():
    with pytest.raises(ValueError):
        Tree.model_validate(pred('is_null', ['1'], kind='STRING'))


def test_scope_all_matches_every_row():
    # 全集必须命中所有行；调用方须加载全部 CUST_ID（空字段集不等于空行集）
    rows = ROWS + [{'CUST_ID': 'SIM2026091800009', 'AMT': None}]
    assert fixture_result({'kind': 'SCOPE_ALL'}, rows)['count'] == len(rows)


def test_l1_phrase_renders_operators():
    from tagpilot_bench import l1
    fact = {'tag_name': '当前时点AUM'}
    assert l1._phrase(fact, pred('>=', ['1000000'])) == '当前时点AUM至少100万元'
    assert l1._phrase(fact, pred('in', ['C3', 'C4'], kind='STRING')) == '当前时点AUM属于C3、C4'
    assert l1._phrase(fact, pred('is_null', [], kind='STRING')) == '当前时点AUM为空'
