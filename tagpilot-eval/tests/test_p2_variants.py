"""P2 表达扩写的离线校验：边界词 lint、回译比较、派生案例的诚实降级。不发任何网络请求。"""
import json
from pathlib import Path

import pytest

from tagpilot_eval.io import read_jsonl
from tagpilot_eval.p2_variants import (_code_forms, _coerce_value, _is_boolean_flag, _name_stem,
                                       _number_forms, acceptance_problems, back_translate,
                                       back_translation_applicable, back_translation_verdict,
                                       boundary_lint, candidate_list, dedupe_variants, make_variant,
                                       reconstruct_tree, sibling_peers, slot_key, window_forms)

PACKAGE = Path(__file__).resolve().parents[1]
FACTS = {r['tag_id']: r for r in read_jsonl(PACKAGE / 'data/p0-v2/facts.jsonl')}
CASES = {c['case_id']: c for c in read_jsonl(PACKAGE / 'data/p2-split-v1/cases.jsonl')}


def _single_case():
    """一个「上年12月 保险购买金额 >= 100000」的单条件母案例。"""
    for case in CASES.values():
        if case['category'] == 'SINGLE' and case['expected']['tree']['operator'] == '>=' \
                and case['expected']['tree']['values'] == ['100000']:
            return case
    raise AssertionError('找不到用于测试的单条件母案例')


def test_number_forms_include_scaled_and_plain():
    forms = _number_forms('200000')
    assert '200000' in forms and '20万' in forms
    assert _number_forms('0.2') == {'0.2'}


def test_number_forms_include_percentage_for_ratio_unit():
    """回归：比例字段树里存 0.5，人话写 50%，两种形式都要接受。"""
    forms = _number_forms('0.5', 'RATIO')
    assert '50%' in forms and '0.5' in forms


def test_coerce_value_maps_code_definition_back_to_code():
    """回归：回译把「是」写回来时要映射成码值 '1'，否则规范树永远不相等。"""
    assert _coerce_value('是', 'STRING', FACTS[662]) == '1'
    assert _coerce_value('否', 'STRING', FACTS[662]) == '0'
    assert _coerce_value('1', 'STRING', FACTS[662]) == '1'


def test_code_forms_accept_the_chinese_meaning():
    forms = _code_forms('0', FACTS[601])
    assert '否' in forms


def test_lint_accepts_a_faithful_paraphrase():
    case = _single_case()
    assert boundary_lint(case, '请筛选上年12月保险购买金额在10万元及以上的客户。', FACTS) == []


def test_lint_does_not_flag_allowed_word_containing_a_forbidden_substring():
    """「不低于」含有「低于」，但它是合法表达，不能判成矛盾。"""
    case = _single_case()
    assert boundary_lint(case, '凡上年12月保险购买金额不低于10万元的客户，请筛选出来。', FACTS) == []


@pytest.mark.parametrize('utterance', [
    '凡上年12月保险购买金额达到或超过10万元的客户，请筛选出来。',
    '凡上年12月保险购买金额大于或等于10万元的客户，请筛选出来。',
])
def test_lint_accepts_disjunctive_ge_phrasings(utterance):
    """回归：「达到或超过」「大于或等于」是 >= 的合法说法，不是操作符矛盾。"""
    assert boundary_lint(_single_case(), utterance, FACTS) == []


def test_ratio_case_accepts_percentage_wording():
    """回归：占比题必须接受「达到或超过50%」这种写法。"""
    case = next(c for c in CASES.values()
                if c['category'] == 'SINGLE' and c['expected']['tree']['values'] == ['0.5']
                and c['expected']['tree']['expression'].get('unit') == 'RATIO')
    assert boundary_lint(case, '凡该指标达到或超过50%的客户，请筛选出来。', FACTS) == []


def test_back_translation_accepts_chinese_code_meaning():
    """回归：回译用「是」描述布尔码值时，应与码值 '1' 判为等价。"""
    case = next(c for c in CASES.values()
                if c['category'] == 'SINGLE' and c['expected']['tree']['operator'] == '='
                and c['expected']['tree']['values'] == ['1']
                and FACTS[c['expected']['tree']['expression']['tag_id']]['codes'])
    tag_id = case['expected']['tree']['expression']['tag_id']
    payload = {'logic': 'AND', 'conditions': [{'tag_id': tag_id, 'operator': '等于', 'values': ['是']}]}
    assert back_translation_verdict(case['expected']['tree'], payload, FACTS)['status'] == 'PASS'


def test_lint_flags_operator_flip():
    case = _single_case()
    codes = {item['code'] for item in boundary_lint(case, '请筛选上年12月保险购买金额超过10万元的客户。', FACTS)}
    assert 'OPERATOR_CONTRADICTION' in codes


def test_lint_flags_dropped_threshold_and_window():
    case = _single_case()
    codes = {item['code'] for item in boundary_lint(case, '帮我找保险购买金额较高的客户。', FACTS)}
    assert 'THRESHOLD_MISSING' in codes and 'WINDOW_MISSING' in codes


def test_lint_requires_an_uncertainty_signal_on_clarification_cases():
    case = next(c for c in CASES.values() if c['category'] == 'CLARIFICATION')
    assert boundary_lint(case, '帮我找AUM至少50万元的客户。', FACTS), '澄清题给出了确定门槛应当被拦下'


def test_reconstruct_tree_and_back_translation_verdict():
    case = _single_case()
    leaf = case['expected']['tree']
    tag_id, value = leaf['expression']['tag_id'], leaf['values'][0]
    correct = {'logic': 'AND', 'conditions': [
        {'tag_id': tag_id, 'operator': '大于等于', 'values': ['10万']}]}
    assert back_translation_verdict(leaf, correct, FACTS)['status'] == 'PASS'
    wrong = {'logic': 'AND', 'conditions': [
        {'tag_id': tag_id, 'operator': '大于', 'values': [value]}]}
    assert back_translation_verdict(leaf, wrong, FACTS)['status'] == 'FAIL'
    assert reconstruct_tree(correct, FACTS)['values'] == [value]


def test_derived_trees_are_honestly_marked_not_applicable():
    derived = next(c for c in CASES.values()
                   if c['category'] == 'COMPOSITION' and 'DIV' in json.dumps(c['expected']))
    verdict = back_translation_verdict(derived['expected']['tree'], {'conditions': []}, FACTS)
    assert verdict['status'] == 'BACK_TRANSLATION_NOT_APPLICABLE'


def test_candidate_list_includes_targets_and_distractors():
    case = _single_case()
    names = {tag_id: fact['name'] for tag_id, fact in FACTS.items()}
    candidates = candidate_list(case, FACTS, names)
    ids = [tag_id for tag_id, _ in candidates]
    assert set(case['target_tag_ids']) <= set(ids) and len(ids) > len(case['target_tag_ids'])


def test_make_variant_inherits_truth_and_sets_provenance():
    case = _single_case()
    variant = make_variant(case, '换个说法：上年12月保险购买金额10万元及以上的客户。', 2, {'status': 'PASS'})
    assert variant['variant_index'] == 2 and variant['variant_mode'] == 'MODEL_PARAPHRASE'
    assert variant['expected'] == case['expected'] and variant['target_tag_ids'] == case['target_tag_ids']
    assert variant['split'] == case['split'] and variant['mother_id'] == case['mother_id']
    assert variant['provenance']['authoring'] == 'MODEL_EXPRESSION_FROM_DETERMINISTIC_TRUTH'
    assert variant['case_id'] != case['case_id']


def test_failed_back_translation_is_never_accepted():
    """回归：回译 FAIL 但没有 lint 矛盾时，曾会被当成通过。"""
    problems = acceptance_problems('任意改写。', [], {'status': 'FAIL', 'reason': '规范树不一致'}, [])
    assert [problem['code'] for problem in problems] == ['BACK_TRANSLATION_FAILED']
    assert acceptance_problems('任意改写。', [], None, [])[0]['code'] == 'BACK_TRANSLATION_FAILED'
    assert acceptance_problems('任意改写。', [], {'status': 'PASS'}, []) == []
    assert acceptance_problems('任意改写。', [], {'status': 'BACK_TRANSLATION_NOT_APPLICABLE'}, []) == []


def test_sibling_near_duplicate_is_rejected():
    peers = ['凡上年12月保险购买金额不低于10万元的客户，请筛选出来。']
    problems = acceptance_problems(peers[0], [], {'status': 'PASS'}, peers)
    assert [problem['code'] for problem in problems] == ['SIBLING_TOO_SIMILAR']


def test_sibling_peers_exclude_the_mother_requirement():
    """回归：母案例原话曾被放进同族基准，导致忠实改写被误判雷同。"""
    rows = [{'mother_id': 'M-1001', 'requirement': '改写甲'}, {'mother_id': 'M-1002', 'requirement': '改写乙'}]
    peers = sibling_peers(rows)
    assert peers['M-1001'] == ['改写甲']
    # 与母案例原话相似不算雷同（peers 里没有原话），只有与已接受改写相似才算。
    assert acceptance_problems('帮我找上年12月保险购买金额至少10万元的客户。', [], {'status': 'PASS'}, []) == []


def test_number_forms_include_chinese_numerals_and_window_synonyms():
    """回归：避免「近三十天」「最近一个月」这类自然说法被判成缺失。"""
    assert '三' in _number_forms('3')
    assert '最近一个月' in window_forms('近30天')
    assert '去年12月' in window_forms('上年12月')
    assert '历史上' in window_forms('历史')


def test_lint_accepts_window_synonyms():
    case = next(c for c in CASES.values()
                if c['category'] == 'SINGLE'
                and c['expected']['tree'].get('caliber', {}).get('time_anchor_label') == '近30天')
    utterance = case['requirement'].replace('近30天', '最近一个月')
    assert boundary_lint(case, utterance, FACTS) == []


def test_slot_key_normalises_mother_and_case_ids():
    """回归：断点键曾用改写自己的 case_id，与跳过判断用的母案例编号永不相等，导致续跑重复生成。"""
    assert slot_key('CAL-1001', 1) == slot_key('M-1001', 1) == ('1001', 1)
    assert slot_key('CAL-1001', 1) != slot_key('CAL-1001', 2)


def test_dedupe_variants_keeps_first_and_archives_the_rest(tmp_path):
    rows = [
        {'case_id': 'CAL-3001', 'mother_id': 'M-1001', 'variant_index': 1, 'requirement': '甲'},
        {'case_id': 'CAL-3001', 'mother_id': 'M-1001', 'variant_index': 1, 'requirement': '甲重复'},
        {'case_id': 'CAL-3002', 'mother_id': 'M-1001', 'variant_index': 2, 'requirement': '乙'},
    ]
    (tmp_path / 'variants.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    result = dedupe_variants(tmp_path)
    assert result == {'rows': 3, 'kept': 2, 'duplicates': 1}
    kept = read_jsonl(tmp_path / 'variants.jsonl')
    assert [row['requirement'] for row in kept] == ['甲', '乙']
    archived = read_jsonl(tmp_path / 'quarantine-duplicate-slots.jsonl')
    assert archived[0]['violations'][0]['code'] == 'DUPLICATE_SLOT'


def _case_with_label_containing_operator_word():
    for case in CASES.values():
        tree = case['expected'].get('tree')
        if not tree or tree.get('kind') != 'PREDICATE' or tree.get('operator') != '=':
            continue
        for value in tree['values']:
            for code in FACTS[tree['expression']['tag_id']].get('codes') or []:
                if code['code'] == value and '以下' in str(code.get('definition') or ''):
                    return case, value, code['definition']
    raise AssertionError('找不到码值定义里含「以下」的案例')


def test_lint_ignores_operator_words_inside_code_labels():
    """回归：码值定义自带量词（「50万以下」「无经验(1年以下)」）不是操作符声明，不能判成矛盾。"""
    case, value, definition = _case_with_label_containing_operator_word()
    utterance = f'凡对应指标为“{definition}”的客户，请筛选出来。'
    assert boundary_lint(case, utterance, FACTS) == []


def test_unparseable_backtranslation_number_raises_value_error():
    """回归：非数字回译曾抛 decimal.InvalidOperation，绕过 (ValueError, KeyError) 掀掉整批。"""
    with pytest.raises(ValueError, match='无法解析'):
        _coerce_value('大约五十万', 'NUMBER', FACTS[721])


def test_lint_accepts_boolean_flag_expressed_as_tag_stem():
    """回归：「当前持有基金标志=0」写作「当前没有持有基金」时没有码值字面量，不该判缺失。"""
    case = next(c for c in CASES.values()
                if c['category'] == 'SINGLE' and c['expected']['tree']['operator'] == '='
                and _is_boolean_flag(FACTS[c['expected']['tree']['expression']['tag_id']]))
    stem = _name_stem(FACTS[case['expected']['tree']['expression']['tag_id']])
    assert boundary_lint(case, f'有没有当前没有{stem}的客户？', FACTS) == []


def test_reconstruct_tree_handles_nested_groups():
    """回归：模型自然给出嵌套结构（AND 套 OR），扁平化还原会 KeyError 并误判回译失败。"""
    case = next(c for c in CASES.values()
                if c['category'] == 'COMPOSITION' and c['expected']['tree']['kind'] == 'GROUP'
                and any(child['kind'] == 'GROUP' and child['logic'] == 'OR'
                        for child in c['expected']['tree']['children']))
    payload = {'logic': 'AND', 'conditions': [
        {'tag_id': 721, 'operator': '不小于', 'values': ['100万元']},
        {'logic': 'OR', 'conditions': [
            {'tag_id': 601, 'operator': '等于', 'values': ['1']},
            {'tag_id': 620, 'operator': '等于', 'values': ['1']}]}]}
    assert back_translation_verdict(case['expected']['tree'], payload, FACTS)['status'] == 'PASS'


def test_back_translation_unavailable_is_accepted_but_flagged():
    """回译拿不到比对结构时不算答错，但必须带标记（由覆盖全量的独立 AI 复核把关）。"""
    verdict = {'status': 'BACK_TRANSLATION_UNAVAILABLE', 'reason': '推理吃满 token'}
    assert acceptance_problems('任意改写。', [], verdict, []) == []
    assert acceptance_problems('任意改写。', [], {'status': 'FAIL'}, [])[0]['code'] == 'BACK_TRANSLATION_FAILED'


def test_verdict_without_mother_tree_is_not_applicable_not_a_crash():
    """回归：澄清/缺口题没有标准树，比较 None 曾抛 ValidationError 并丢掉整条改写。"""
    verdict = back_translation_verdict(None, {'conditions': []}, FACTS)
    assert verdict['status'] == 'BACK_TRANSLATION_NOT_APPLICABLE'


def test_invalid_reconstructed_structure_becomes_fail_not_crash():
    """回译给出不合法结构（空值判定带值）应算 FAIL，而不是让异常掀掉整批。"""
    case = _single_case()
    payload = {'conditions': [{'tag_id': case['expected']['tree']['expression']['tag_id'],
                               'operator': '为空', 'values': ['1']}]}
    verdict = back_translation_verdict(case['expected']['tree'], payload, FACTS)
    assert verdict['status'] == 'FAIL' and '无法规范化' in verdict['reason']


def test_scope_all_has_nothing_to_back_translate():
    """回归：全客群题（SCOPE_ALL）没有任何条件叶子，回译无从比对，不是失败。"""
    case = next(c for c in CASES.values() if c['expected'].get('tree', {}).get('kind') == 'SCOPE_ALL')
    verdict = back_translation_verdict(case['expected']['tree'], {'conditions': []}, FACTS)
    assert verdict['status'] == 'BACK_TRANSLATION_NOT_APPLICABLE'


def _gap_case():
    return next(c for c in CASES.values() if c['expected']['outcomes'] == ['CAPABILITY_GAP'])


def test_gap_signal_check_is_relative_to_the_mother():
    """回归：母案例本身是普通请求（用户并不知道做不到）时，不能要求改写补出缺口信号。"""
    case = _gap_case()
    plain = {**case, 'requirement': '按这个指标筛选客户。'}
    assert boundary_lint(plain, '按这个指标筛选客户。', FACTS) == []
    told = {**case, 'requirement': '这个指标口径有冲突，先确认再圈。'}
    assert boundary_lint(told, '这个指标口径有冲突，先确认再圈。', FACTS) == []
    assert [v['code'] for v in boundary_lint(told, '直接按这个指标筛选客户。', FACTS)] == ['GAP_SIGNAL_LOST']


def test_gap_cases_skip_structural_back_translation():
    """缺口题的标准树刻意不完整（冲突标签被排除），结构比对必然对不上，应判为不适用。"""
    gap_with_tree = next(c for c in CASES.values() if c['expected']['outcomes'] == ['CAPABILITY_GAP']
                         and c['expected'].get('tree'))
    assert back_translation_applicable(gap_with_tree) is False
    assert back_translation_applicable(_single_case()) is True
    clarification = next(c for c in CASES.values() if c['category'] == 'CLARIFICATION')
    assert back_translation_applicable(clarification) is False
    scope_all = next(c for c in CASES.values() if c['expected'].get('tree', {}).get('kind') == 'SCOPE_ALL')
    assert back_translation_applicable(scope_all) is False


def test_internal_tokens_must_not_appear_in_user_speech():
    """回归：用户话术里出现 CAPABILITY_GAP / COUNT_POSITIVE / is_null 这类内部记号必须拦下。"""
    case = _single_case()
    leaks = {v['token'] for v in boundary_lint(case, '终态为CAPABILITY_GAP，需满足 is_null。', FACTS)
             if v['code'] == 'INTERNAL_TOKEN_LEAK'}
    assert leaks == {'CAPABILITY_GAP', 'is_null'}


def test_recipe_requirements_match_their_target_tags():
    """粗筛：题面点名的业务词要能在目标标签名里找到（防「没有持有黄金」挂在个人养老金标签上）。"""
    from tagpilot_eval.p2_mothers import audit_requirements
    mothers = read_jsonl(PACKAGE / 'data/p2-mothers-v2/cases.jsonl')
    # GAP 题本来就没有可构建的目标标签，排除在粗筛之外。
    findings = [f for f in audit_requirements(mothers, FACTS)
                if not mothers_find_gap(mothers, f['case_id'])]
    assert findings == []


def mothers_find_gap(mothers, case_id):
    case = next(c for c in mothers if c['case_id'] == case_id)
    return case['expected']['outcomes'] == ['CAPABILITY_GAP']


def test_ratio_values_are_normalised_to_decimals():
    ratio_tag = next(t for t, f in FACTS.items()
                     if f['published_semantics']['unit'] == 'RATIO' and not f.get('codes'))
    assert _coerce_value('50%', 'NUMBER', FACTS[ratio_tag]) == '0.5'
    assert _coerce_value('50', 'NUMBER', FACTS[ratio_tag]) == '0.5'
    assert _coerce_value('0.5', 'NUMBER', FACTS[ratio_tag]) == '0.5'
    # 非比例字段不受影响
    assert _coerce_value('50', 'NUMBER', FACTS[721]) == '50'
    assert _coerce_value('20万', 'NUMBER', FACTS[721]) == '200000'
