"""Guard 单测：冻结/授权、字面量、提交接受矩阵与结构边界。"""
import asyncio
import copy
import json

import pytest

from tagpilot_agent.guards.diagnostics import PlanError
from tagpilot_agent.guards.guard import check
from tagpilot_agent.guards.ledger import frozen_errors
from tagpilot_agent.guards.literals import check_literals, literal_warnings
from tagpilot_agent.guards.plan_validator import leaves, validate_plan
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.tools.registry import dispatch
from tests.test_sdk_smoke import Evidence
from tests.test_workbench import REQ, TAG

REQUIREMENT = '转入超过50万'


def ctx_for(**overrides):
    return RunContext({**REQ, **overrides}, Evidence())


def payload(result):
    return json.loads(result['content'][0]['text'])


def bound_plan(values=None):
    return {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': REQUIREMENT,
                     'tag_id': 1, 'operator': '>', 'values': values or ['500000']}}


def submit(ctx, outcome='READY', plan=None, **extra):
    args = {'outcome': outcome, 'plan': plan if plan is not None else bound_plan(), 'summary': '测试提交'}
    args.update(extra)
    return dispatch(ctx, 'submit_result', copy.deepcopy(args))


def test_ready_submission_requires_zero_blockers_and_all_bound():
    ctx = ctx_for()
    result = asyncio.run(submit(ctx))
    assert not result['is_error'], payload(result)
    assert ctx.accepted['outcome'] == 'READY'
    assert ctx.accepted['plan']['plan_status'] == 'READY'


def test_ready_rejected_when_gap_or_question_present():
    ctx = ctx_for()
    plan = bound_plan()
    plan['tree']['gap_reason'] = 'NO_PUBLISHED_TAG'
    result = asyncio.run(submit(ctx, plan=plan))
    assert result['is_error']
    assert any('READY 须零阻断' in e for e in payload(result)['errors'])
    assert not ctx.accepted

    ctx2 = ctx_for()
    result = asyncio.run(submit(ctx2, questions=[{'requirement_id': 'a', 'prompt': '采用哪个定义？',
                                                  'options': ['定义A', '定义B'], 'reason': 'DEFINITION_MISSING'}]))
    assert result['is_error']
    assert any('READY 不能包含问题或缺口' in e for e in payload(result)['errors'])


def test_question_requires_verification_trail_before_asking():
    question = {'requirement_id': 'a', 'clause_id': 'a', 'prompt': '是否包含未知码值客户？',
                'options': ['包含', '排除'], 'reason': 'DEFINITION_MISSING'}
    ctx = ctx_for()
    result = asyncio.run(submit(ctx, 'NEEDS_USER_INPUT', questions=[question]))
    assert result['is_error']
    assert any('请先查证该需求' in e for e in payload(result)['errors'])

    asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'a'}], 'depth': 'quick'}))
    result = asyncio.run(submit(ctx, 'NEEDS_USER_INPUT', questions=[question]))
    assert not result['is_error'], payload(result)
    assert ctx.accepted['outcome'] == 'NEEDS_USER_INPUT'
    assert ctx.accepted['plan']['plan_status'] == 'NEEDS_DECISION'
    assert ctx.accepted['questions'][0]['prompt'] == question['prompt']


def test_goal_unclear_may_ask_without_search_but_not_leak_technical_fields():
    ctx = ctx_for()
    result = asyncio.run(submit(ctx, 'NEEDS_USER_INPUT', questions=[
        {'requirement_id': 'a', 'prompt': '目标人群是哪些？', 'options': ['全部', '部分'], 'reason': 'GOAL_UNCLEAR'}]))
    assert not result['is_error'], payload(result)

    ctx2 = ctx_for()
    result = asyncio.run(submit(ctx2, 'NEEDS_USER_INPUT', questions=[
        {'requirement_id': 'a', 'prompt': '请选择 tag_id 1 还是 2？', 'options': ['1', '2'], 'reason': 'GOAL_UNCLEAR'}]))
    assert result['is_error']
    assert any('技术字段' in e for e in payload(result)['errors'])

    ctx3 = ctx_for()
    result = asyncio.run(submit(ctx3, 'NEEDS_USER_INPUT', questions=[
        {'requirement_id': 'zzz', 'prompt': '目标人群是哪些？', 'options': ['全部', '部分'], 'reason': 'GOAL_UNCLEAR'}]))
    assert result['is_error']
    assert any('问题必须对应需求' in e for e in payload(result)['errors'])


def test_capability_gap_requires_deep_or_capability_search():
    gap = {'requirement_id': 'a', 'reason': 'NO_CAPABILITY', 'nearest_tag_ids': [1]}
    ctx = ctx_for()
    result = asyncio.run(submit(ctx, 'CAPABILITY_GAP', gaps=[gap]))
    assert result['is_error']
    assert any('缺口须先做 deep 或能力检索' in e for e in payload(result)['errors'])

    asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'a'}], 'depth': 'deep'}))
    result = asyncio.run(submit(ctx, 'CAPABILITY_GAP', gaps=[gap]))
    assert not result['is_error'], payload(result)
    assert ctx.accepted['outcome'] == 'CAPABILITY_GAP'
    assert ctx.accepted['plan']['plan_status'] == 'CAPABILITY_GAP'


def test_capability_gap_must_list_gaps_and_known_candidates():
    ctx = ctx_for()
    result = asyncio.run(submit(ctx, 'CAPABILITY_GAP'))
    assert result['is_error']
    assert any('能力缺口必须列明 gaps' in e for e in payload(result)['errors'])

    plan = bound_plan()
    plan['tree']['gap_reason'] = 'NO_PUBLISHED_TAG'
    result = asyncio.run(submit(ctx, 'PARTIAL', plan=plan))
    assert result['is_error']
    assert any('已声明的业务缺口必须逐项列明' in e for e in payload(result)['errors'])

    ctx2 = ctx_for()
    asyncio.run(dispatch(ctx2, 'find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'a'}], 'depth': 'deep'}))
    result = asyncio.run(submit(ctx2, 'CAPABILITY_GAP', gaps=[
        {'requirement_id': 'a', 'reason': 'NO_CAPABILITY', 'nearest_tag_ids': [99]}]))
    assert result['is_error']
    assert any('最近候选必须来自已检索证据' in e for e in payload(result)['errors'])


def test_submit_forced_partial_after_three_rejections():
    ctx = ctx_for()
    plan = bound_plan(values=['600000'])
    for _ in range(3):
        result = asyncio.run(submit(ctx, plan=plan))
        assert result['is_error']
    assert ctx.stats['submit_rejections'] == 3
    result = asyncio.run(submit(ctx, plan=plan))
    assert not result['is_error'], payload(result)
    assert payload(result)['outcome'] == 'PARTIAL'
    assert ctx.stats['forced_partial'] is True
    assert ctx.accepted['outcome'] == 'PARTIAL'
    assert ctx.accepted['plan']['plan_status'] == 'DRAFT'


def test_modify_requires_verbatim_current_utterance():
    old = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'c', 'source_span': '金额50万',
                    'tag_id': 1, 'operator': '>', 'values': ['500000']}}
    new = copy.deepcopy(old)
    new['tree']['values'] = ['600000']
    assert any(e['code'] == 'FROZEN_CLAUSE_CHANGED' for e in frozen_errors(old, new, '请继续'))
    new['intent_changes'] = [{'operation': 'MODIFY', 'clause_ids': ['c'], 'source_span': '改为60万'}]
    assert any(e['code'] == 'FROZEN_CLAUSE_CHANGED' for e in frozen_errors(old, new, '请继续'))
    assert not frozen_errors(old, new, '金额改为60万')


def test_remove_requires_removal_wording_and_current_utterance():
    old = {'tree': {'logic': 'AND', 'children': [
        {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '金额50万', 'tag_id': 1, 'operator': '>', 'values': ['500000']},
        {'kind': 'TAG_PREDICATE', 'clause_id': 'b', 'source_span': '年龄35岁', 'tag_id': 2, 'operator': '>', 'values': ['35']}]},
        'intent_plan': {'original_request': 'x', 'requirements': [
            {'requirement_id': 'a', 'source_spans': ['金额50万'], 'business_meaning': '金额'},
            {'requirement_id': 'b', 'source_spans': ['年龄35岁'], 'business_meaning': '年龄'}],
            'logic_tree': {'logic': 'AND', 'children': [{'requirement_id': 'a'}, {'requirement_id': 'b'}]}, 'assumptions': []}}
    new = copy.deepcopy(old)
    new['tree'] = {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '金额50万',
                   'tag_id': 1, 'operator': '>', 'values': ['500000']}
    new['intent_plan'] = {'original_request': 'x', 'requirements': [
        {'requirement_id': 'a', 'source_spans': ['金额50万'], 'business_meaning': '金额'}],
        'logic_tree': {'requirement_id': 'a'}, 'assumptions': []}
    new['intent_changes'] = [{'operation': 'REMOVE', 'clause_ids': ['b'], 'source_span': '不要年龄限制'}]
    errors = frozen_errors(old, new, '去掉年龄限制')
    assert errors and all(e['code'] in {'FROZEN_CLAUSE_CHANGED', 'REQUIREMENT_MISSING'} for e in errors)
    assert any(e['code'] == 'REQUIREMENT_MISSING' for e in errors)
    assert not frozen_errors(old, new, '不要年龄限制')


def test_logic_change_needs_explicit_authorization():
    old = {'tree': {'logic': 'AND', 'children': [
        {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '金额50万', 'tag_id': 1, 'operator': '>', 'values': ['500000']},
        {'kind': 'TAG_PREDICATE', 'clause_id': 'b', 'source_span': '年龄35岁', 'tag_id': 2, 'operator': '>', 'values': ['35']}]},
        'intent_plan': {'original_request': 'x', 'requirements': [
            {'requirement_id': 'a', 'source_spans': ['金额50万'], 'business_meaning': '金额'},
            {'requirement_id': 'b', 'source_spans': ['年龄35岁'], 'business_meaning': '年龄'}],
            'logic_tree': {'logic': 'AND', 'children': [{'requirement_id': 'a'}, {'requirement_id': 'b'}]}, 'assumptions': []}}
    new = copy.deepcopy(old)
    new['tree'] = {'logic': 'OR', 'children': copy.deepcopy(old['tree']['children'])}
    assert any(e['code'] == 'LOGIC_CHANGED' for e in frozen_errors(old, new, '请继续'))
    new['intent_changes'] = [{'operation': 'MODIFY', 'clause_ids': ['a'], 'source_span': '条件改成或关系'}]
    assert not [e for e in frozen_errors(old, new, '条件改成或关系') if e['code'] == 'LOGIC_CHANGED']


def test_literals_cover_scale_percent_time_and_code_bounds():
    tags = {1: TAG}
    plan = bound_plan()
    assert check_literals(plan, {'requirement': REQUIREMENT}, tags) == []
    drifted = copy.deepcopy(plan)
    drifted['tree']['values'] = ['600000']
    assert any(e['code'] == 'LITERAL_DRIFT' for e in check_literals(drifted, {'requirement': REQUIREMENT}, tags))
    invented = copy.deepcopy(plan)
    invented['tree']['source_span'] = '资产达标'
    assert any(e['message'] == '条件来源必须逐字引用用户原话' for e in check_literals(invented, {'requirement': REQUIREMENT}, tags))

    scaled = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '50万元以上',
                       'tag_id': 1, 'operator': '>', 'values': ['50'], 'value_scale': '10000'}}
    assert check_literals(scaled, {'requirement': '50万元以上'}, tags) == []
    timed = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '近30天转入',
                      'tag_id': 1, 'operator': '>', 'values': ['1'], 'expected_caliber': {'time_window_value': 30}}}
    assert check_literals(timed, {'requirement': '近30天转入'}, tags) == []
    percent = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '占比80%',
                        'tag_id': 1, 'operator': '>', 'values': ['0.8']}}
    assert check_literals(percent, {'requirement': '占比80%'}, tags) == []
    code_plan = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'r', 'source_span': '风评C3',
                          'tag_id': 1, 'operator': 'in', 'values': ['C3'],
                          'code_options': [{'code': 'C3', 'lower_bound': '3', 'upper_bound': '4'}]}}
    assert check_literals(code_plan, {'requirement': '风评C3'}, tags) == []


def test_literals_cannot_drop_another_number_and_warn_only():
    plan = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '金融资产50万元以上',
                     'tag_id': 1, 'operator': '>', 'values': ['500000']}}
    errors = check_literals(plan, {'requirement': '35岁以上，金融资产50万元以上'}, {})
    assert any(e['message'] == '方案遗漏原始需求中的数值' and e.get('expected') == '35' for e in errors)

    warnings = literal_warnings(plan, {'requirement': '不要保险客户，并且金融资产50万元以上'})
    assert {w['code'] for w in warnings} == {'NEGATION_COVERAGE', 'CONNECTOR_COVERAGE'}
    assert any('不要' in w['markers'] for w in warnings)


def test_guard_schema_invalid_falls_back_without_tree():
    ctx = ctx_for()
    plan = bound_plan()
    plan['tree']['status'] = 'BOUND'
    result = asyncio.run(check(plan, ctx))
    assert not result['valid'] and 'tree' not in result
    assert result['diagnostics'][0]['code'] == 'SCHEMA_INVALID'
    assert result['diagnostics'][0]['hint']


def test_condition_limits_are_enforced():
    leaf = {'kind': 'TAG_PREDICATE', 'clause_id': 'leaf', 'source_span': 'x', 'tag_id': 1, 'operator': '>', 'values': ['1']}
    tree = copy.deepcopy(leaf)
    for _ in range(9):
        tree = {'logic': 'AND', 'children': [tree]}
    with pytest.raises(PlanError):
        leaves(tree)
    dup = {'tree': {'logic': 'AND', 'children': [copy.deepcopy(leaf), copy.deepcopy(leaf)]}}
    with pytest.raises(PlanError):
        validate_plan(dup, {1: TAG}, [], {1})


def test_ineligible_and_unknown_tags_are_explicit_diagnostics():
    ctx = ctx_for()
    plan = bound_plan()
    plan['tree']['tag_id'] = 2
    result = asyncio.run(check(plan, ctx))
    assert any(d['code'] == 'INELIGIBLE_TAG' for d in result['diagnostics'])

    ctx2 = ctx_for(eligible_tag_ids=[1, 99])
    plan2 = bound_plan()
    plan2['tree']['tag_id'] = 99
    result = asyncio.run(check(plan2, ctx2))
    assert any(d['code'] == 'UNKNOWN_TAG' for d in result['diagnostics'])


def test_coverage_follows_requirement_ledger():
    leaf_a = {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '转入超过50万',
              'tag_id': 1, 'operator': '>', 'values': ['500000'], 'requirement_ids': ['R1']}
    leaf_b = {**copy.deepcopy(leaf_a), 'clause_id': 'b', 'source_span': '年龄35岁', 'values': ['35'], 'requirement_ids': ['R2']}
    plan = {'tree': {'logic': 'AND', 'children': [leaf_a, leaf_b]},
            'intent_plan': {'original_request': 'x', 'requirements': [
                {'requirement_id': 'R1', 'source_spans': ['转入超过50万'], 'business_meaning': '金额'}],
                'logic_tree': {'logic': 'AND', 'children': [{'requirement_id': 'R1'}, {'requirement_id': 'R2'}]}, 'assumptions': []}}
    ctx = ctx_for(requirement='转入超过50万，年龄35岁')
    result = asyncio.run(check(plan, ctx))
    assert {d['code'] for d in result['diagnostics']} == {'INTENT_COVERAGE'}
    assert any(d['message'] == '新增执行条件缺少业务要求来源' for d in result['diagnostics'])

    plan2 = copy.deepcopy(plan)
    plan2['tree'] = {'logic': 'AND', 'children': [copy.deepcopy(leaf_a)]}
    plan2['intent_plan']['requirements'].append(
        {'requirement_id': 'R2', 'source_spans': ['年龄35岁'], 'business_meaning': '年龄'})
    result2 = asyncio.run(check(plan2, ctx))
    assert any(d['requirement_id'] == 'R2' and '方案遗漏' in d['message'] for d in result2['diagnostics'])


def test_manual_edit_skips_drift_and_freeze_but_keeps_contract():
    plan = bound_plan(values=['600000'])
    ctx = ctx_for()
    result = asyncio.run(check(plan, ctx))
    assert not result['valid']
    assert any(d['code'] == 'LITERAL_DRIFT' for d in result['diagnostics'])

    manual = ctx_for(_manual_edit=True)
    result = asyncio.run(check(plan, manual, trusted=True))
    assert result['valid'], result['diagnostics']
