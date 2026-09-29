"""收尾第 2 项：裁判与数据解析审计的反例测试。

审计结论：
- 树级裁判不会把错答判对：PASS 要求 normalized 结构相等，而 normalized 完全由标准树决定，
  结构相等即语义相等，因此不存在"结构不同却判过"的假通过；代价是对等价但形状不同的
  表示偏严（假失败），属保守方向。
- 真正的假通过面在终态层（此前根本没有人判 READY/澄清/缺口），已由 judge.py 补齐。
- 解析器靠分母校验兜底（969/970/2000/1723），未知字面量一律抛错，绝不猜测。
"""
import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest

from tagpilot_eval.io import read_jsonl
from tagpilot_eval.judge import acceptance_suite, caliber_declared, grade_case
from tagpilot_eval.oracle import boundary_rows, grade_tree
from tagpilot_eval.plan_adapter import AdapterError, to_eval_tree
from tagpilot_eval.sources import load_code_maps, parse_values

PACKAGE = Path(__file__).resolve().parents[1]
P0 = PACKAGE / 'data/p0-v2'


def p(op='>=', values=None, kind='NUMBER', field='AMT', tid=1):
    return {'kind': 'PREDICATE', 'expression': {'kind': 'TAG', 'tag_id': tid,
            'field_name': field, 'unit': 'CNY'}, 'operator': op,
            'values': values if values is not None else ['500000'], 'data_kind': kind,
            'caliber': {}}


# --- 树级裁判：不存在假通过 -------------------------------------------------

def test_acceptance_suite_matches_required_verdicts():
    for case in acceptance_suite():
        assert case['verdict'] == case['want'], case['name']


@pytest.mark.parametrize('mutate', [
    lambda t: t.update(operator='>'),
    lambda t: t['values'].__setitem__(0, '500001'),
    lambda t: t['values'].__setitem__(0, '499999'),
    lambda t: t['expression'].update(field_name='OTHER'),
    lambda t: t['expression'].update(tag_id=2),
])
def test_any_semantic_perturbation_fails(mutate):
    expected = p()
    actual = deepcopy(expected)
    mutate(actual)
    assert grade_tree(expected, actual)['status'] == 'FAIL'


def test_structural_equality_implies_semantic_equality():
    """normalized 相等即结构相同，故 tree_equal 不可能对语义不同的两棵树判真。"""
    from tagpilot_eval.oracle import normalized
    a = {'kind': 'GROUP', 'logic': 'AND', 'children': [p('>='), p('<=', ['900000'])]}
    b = {'kind': 'GROUP', 'logic': 'AND', 'children': [p('<=', ['900000']), p('>=')]}
    assert normalized(a) == normalized(b)
    assert grade_tree(a, b)['status'] == 'PASS'


def test_proven_equivalents_normalize_to_same_form():
    """已证明等价：between[a,b] ≡ (>=a 且 <=b)；单子分组 ≡ 其子；= ≡ in[x]；!= ≡ not_in[x]。"""
    between = p('between', ['2026-09-19', '2026-09-25'], 'DATE')
    pair = {'kind': 'GROUP', 'logic': 'AND',
            'children': [p('>=', ['2026-09-19'], 'DATE'), p('<=', ['2026-09-25'], 'DATE')]}
    assert grade_tree(between, pair)['status'] == 'PASS'
    assert grade_tree({'kind': 'GROUP', 'logic': 'AND', 'children': [p()]}, p())['status'] == 'PASS'
    assert grade_tree(p('=', ['5']), p('in', ['5']))['status'] == 'PASS'
    assert grade_tree(p('!=', ['5']), p('not_in', ['5']))['status'] == 'PASS'
    # 只展开一半、端点调换都不是等价，必须失败。
    assert grade_tree(between, p('>=', ['2026-09-19'], 'DATE'))['status'] == 'FAIL'
    assert grade_tree(between, p('between', ['2026-09-25', '2026-09-19'], 'DATE'))['status'] == 'FAIL'


def test_boundary_probe_cap_is_bounded_not_silent():
    """宽树的探针数有上限；这是覆盖度限制，须可见而非静默。"""
    children = [p('>=', [str(i)]) for i in range(1, 8)]
    probes = boundary_rows({'kind': 'GROUP', 'logic': 'AND', 'children': children})
    assert 1 < len(probes) <= 4096


# --- 终态裁判：假通过与证据缺失 ---------------------------------------------

def test_outcome_mismatch_is_labelled_failure():
    facts = {1: {'tag_id': 1, 'field_name': 'AMT', 'tag_type': '数值型', 'codes': [],
                 'published_semantics': {'unit': 'CNY', 'caliber_struct': {}}}}
    expected = {'outcomes': ['READY'], 'tree': p()}
    result = {'status': 'COMPLETED', 'outcome': {'outcome': 'PARTIAL'}, 'plan': {}}
    verdict = grade_case({'case_id': 'X'}, expected, result, facts)
    assert verdict['status'] == 'FAIL'
    assert 'OUTCOME' in verdict['failures']


def test_ready_without_plan_is_failure_not_pass():
    facts = {1: {'tag_id': 1, 'field_name': 'AMT', 'tag_type': '数值型', 'codes': [],
                 'published_semantics': {'unit': 'CNY', 'caliber_struct': {}}}}
    expected = {'outcomes': ['READY'], 'tree': p()}
    result = {'status': 'COMPLETED', 'outcome': {'outcome': 'READY'}, 'plan': {}}
    verdict = grade_case({'case_id': 'X'}, expected, result, facts)
    assert verdict['status'] == 'FAIL' and 'NO_TREE' in verdict['failures']


def test_capability_gap_without_matching_reason_fails():
    facts = {}
    expected = {'outcomes': ['CAPABILITY_GAP'], 'gap_codes': ['METADATA_INCOMPLETE']}
    result = {'status': 'COMPLETED', 'outcome': {'outcome': 'CAPABILITY_GAP', 'gaps': []}, 'plan': {}}
    assert grade_case({'case_id': 'X'}, expected, result, facts)['status'] == 'FAIL'


def test_capability_gap_with_expected_reason_passes():
    facts = {}
    expected = {'outcomes': ['CAPABILITY_GAP'], 'gap_codes': ['METADATA_INCOMPLETE']}
    result = {'status': 'COMPLETED',
              'outcome': {'outcome': 'CAPABILITY_GAP', 'gaps': [{'reason': 'METADATA_INCOMPLETE'}]},
              'plan': {}}
    assert grade_case({'case_id': 'X'}, expected, result, facts)['status'] == 'PASS'


def test_clarification_slot_must_be_asked():
    facts = {}
    expected = {'outcomes': ['NEEDS_USER_INPUT'], 'required_slots': ['threshold']}
    good = {'status': 'WAITING', 'outcome': {'outcome': 'NEEDS_USER_INPUT'},
            'questions': [{'reason': 'THRESHOLD_MISSING'}], 'interrupt_id': 'r-1'}
    bad = {'status': 'WAITING', 'outcome': {'outcome': 'NEEDS_USER_INPUT'}, 'questions': []}
    assert grade_case({'case_id': 'X'}, expected, good, facts)['status'] == 'PASS'
    assert grade_case({'case_id': 'X'}, expected, bad, facts)['status'] == 'FAIL'


# --- 计划翻译器 --------------------------------------------------------------

FACTS = {1009: {'tag_id': 1009, 'field_name': 'F', 'tag_type': '数值型', 'codes': [],
                'published_semantics': {'unit': 'CNY', 'caliber_struct': {}}}}


def test_value_scale_is_applied():
    plan = {'kind': 'TAG_PREDICATE', 'tag_id': 1009, 'operator': '>=',
            'values': ['10'], 'value_unit': 'CNY', 'value_scale': 10000}
    assert to_eval_tree(plan, FACTS)['values'] == ['100000']


def test_already_normalised_value_is_not_rescaled():
    plan = {'kind': 'TAG_PREDICATE', 'tag_id': 1009, 'operator': '>=',
            'values': ['500000'], 'value_unit': 'CNY'}
    assert to_eval_tree(plan, FACTS)['values'] == ['500000']


def test_unknown_tag_is_unreadable_not_silently_passed():
    plan = {'kind': 'TAG_PREDICATE', 'tag_id': 999999, 'operator': '>=', 'values': ['1']}
    with pytest.raises(AdapterError):
        to_eval_tree(plan, FACTS)


def test_unknown_policy_include_is_rejected():
    plan = {'kind': 'TAG_PREDICATE', 'tag_id': 1009, 'operator': '>=', 'values': ['1'],
            'unknown_policy': 'INCLUDE'}
    with pytest.raises(AdapterError):
        to_eval_tree(plan, FACTS)


def test_caliber_only_conflict_fails_not_omission():
    facts = {1009: {'tag_id': 1009, 'field_name': 'F', 'tag_type': '数值型', 'codes': [],
                    'published_semantics': {'unit': 'CNY', 'caliber_struct': {
                        'time_anchor_type': 'WINDOW', 'time_window_value': 30}}}}
    silent = {'kind': 'TAG_PREDICATE', 'tag_id': 1009, 'operator': '>=', 'values': ['1']}
    conflicting = {**silent, 'expected_caliber': {'time_window_value': 7}}
    assert caliber_declared(silent, facts)[0] == []
    assert caliber_declared(conflicting, facts)[0]


def test_caliber_label_only_difference_is_not_a_conflict():
    """展示文案（time_anchor_label）不同不是口径冲突：实测 Agent 写“当前”、快照写“当前时点”。"""
    facts = {721: {'tag_id': 721, 'field_name': 'CUR_POINT_AUM', 'tag_type': '数值型', 'codes': [],
                   'published_semantics': {'unit': 'CNY', 'caliber_struct': {
                       'time_anchor_type': 'CURRENT', 'time_anchor_label': '当前时点',
                       'statistic': 'EOP'}}}}
    plan = {'kind': 'TAG_PREDICATE', 'tag_id': 721, 'operator': '>=', 'values': ['200000'],
            'value_unit': 'CNY', 'value_scale': 10000,
            'expected_caliber': {'time_anchor_label': '当前', 'time_anchor_type': 'CURRENT'}}
    assert caliber_declared(plan, facts)[0] == []
    wrong = {**plan, 'expected_caliber': {'time_anchor_type': 'WINDOW', 'time_window_value': 7}}
    assert caliber_declared(wrong, facts)[0]


# --- 解析器 ------------------------------------------------------------------

@pytest.mark.parametrize('value', ['NOW()', '1); DROP TABLE x', 'NaN', 'true', '1e5', '+1', '0x1f'])
def test_parser_refuses_unknown_literals(value):
    with pytest.raises(ValueError):
        parse_values(value)


def test_parser_preserves_leading_zeros_and_null_words():
    assert parse_values("'03',NULL,'NULL',0.05,'a,b','O''Brien'") == \
        ['03', None, 'NULL', '0.05', 'a,b', "O'Brien"]


def test_source_denominators_are_enforced():
    """工作树码值分母（含来源冲突处置）与冻结事实包分母必须分别成立。"""
    root = PACKAGE.parent
    code_maps = load_code_maps([root / 'sql/indiv_cust' / n for n in
                                ['03_insert_L_INDVCST_LABEL_CODE_MAP_BOOL.sql',
                                 '04_insert_L_INDVCST_LABEL_CODE_MAP_OPTION.sql',
                                 '05_insert_L_INDVCST_LABEL_CODE_MAP_BRANCH.sql']])
    assert len(code_maps) == 178 and sum(map(len, code_maps.values())) == 1725
    summary = json.loads((P0 / 'summary.json').read_text())
    assert summary['code_fields'] == 177 and summary['code_values'] == 1723
    assert summary['snapshot_counts']['code_value'] == 1723


def test_frozen_source_tampering_is_detected(tmp_path):
    from tagpilot_eval.validation import verify_package
    (tmp_path / 'sources').mkdir()
    payload = gzip.compress(b'altered')
    (tmp_path / 'sources/snapshot.gz').write_bytes(payload)
    (tmp_path / 'manifest.json').write_text(json.dumps(
        {'files': {}, 'sources': {'snapshot': {'frozen_copy': 'sources/snapshot.gz', 'sha256': '0' * 64}}}))
    with pytest.raises(ValueError, match='hash'):
        verify_package(tmp_path)


def test_p0_v2_facts_identical_to_v1():
    """p0-v2 只新增处置标注，事实逐字节不变。"""
    v1 = {r['tag_id']: r for r in read_jsonl(PACKAGE / 'data/p0-v1/facts.jsonl')}
    v2 = {r['tag_id']: r for r in read_jsonl(P0 / 'facts.jsonl')}
    assert v1 == v2
