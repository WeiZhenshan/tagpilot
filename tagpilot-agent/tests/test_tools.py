"""工具单测：资格注入、越权/版本隔离、字节上限、缓存键与预算。"""
import asyncio
import json
from collections import Counter

import pytest

from tagpilot_agent.retrieval.cache import eligible_hash
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.tools.registry import MODELS, dispatch
from tests.test_sdk_smoke import Evidence
from tests.test_workbench import REQ, TAG


class CountingEvidence(Evidence):
    def __init__(self, payload=None):
        self.calls = Counter()
        self.payload = payload or {}

    def _wrap(self, key, data):
        self.calls[key] += 1
        return {**data, **self.payload}

    def lookup(self, *args):
        data = self._wrap('lookup', super().lookup(*args))
        data['candidates'] = [{'tag_id': 1, 'matched_by': 'EXACT_ALIAS'}]
        return data

    def retrieve_batch(self, queries, *args):
        self.calls['retrieve_batch'] += 1
        return [self._wrap('batch_item', super().lookup(query)) for query in queries]

    def evidence(self, ids, *args):
        return self._wrap('evidence', super().evidence(ids, *args))

    def capabilities(self, *args):
        return self._wrap('capabilities', super().capabilities(*args))


def ctx_for(retriever=None, **overrides):
    return RunContext({**REQ, **overrides}, retriever or CountingEvidence())


def payload(result):
    return json.loads(result['content'][0]['text'])


def test_tool_schemas_hide_identity_and_eligibility():
    assert set(MODELS) == {'find_tags', 'get_tag_details', 'find_capabilities', 'check_plan', 'submit_result'}
    for name, model in MODELS.items():
        schema = json.dumps(model.model_json_schema(), ensure_ascii=False)
        for forbidden in ('eligible', 'build_id', 'snapshot_id', 'artifact_hash', 'owner_id', 'library_id'):
            assert forbidden not in schema, (name, forbidden)


def test_get_tag_details_out_of_scope_and_unknown_ids_are_is_error():
    ctx = ctx_for()
    result = asyncio.run(dispatch(ctx, 'get_tag_details', {'tag_ids': [2]}))
    assert result['is_error'] and 'INELIGIBLE_TAG' in payload(result)['message']
    assert ctx.stats['details'] == 0 and not ctx.tags

    ctx2 = ctx_for(eligible_tag_ids=[1, 99])
    result = asyncio.run(dispatch(ctx2, 'get_tag_details', {'tag_ids': [99]}))
    assert result['is_error'] and 'UNKNOWN_TAG' in payload(result)['message']


def test_semantic_payload_out_of_scope_is_fatal_403():
    bad = CountingEvidence({'build_id': 'b1', 'snapshot_id': 's1', 'artifact_hash': 'h1',
                            'selection_context': {'tags': [{**TAG, 'tag_id': 2}], 'code_values': []}})
    ctx = ctx_for(bad)
    result = asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '客户'}]}))
    assert result['is_error'] and ctx.stats['fatal_status'] == 403
    assert not ctx.tags


def test_version_and_eligible_hash_mismatch_are_fatal_409():
    ctx = ctx_for(CountingEvidence({'build_id': 'b2'}))
    result = asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '客户'}]}))
    assert result['is_error'] and ctx.stats['fatal_status'] == 409

    ctx2 = ctx_for(CountingEvidence({'eligible_hash': 'mismatch'}))
    result = asyncio.run(dispatch(ctx2, 'find_tags', {'queries': [{'text': '客户'}]}))
    assert result['is_error'] and ctx2.stats['fatal_status'] == 409

    ctx3 = ctx_for(CountingEvidence({'eligible_hash': eligible_hash({1})}))
    result = asyncio.run(dispatch(ctx3, 'find_tags', {'queries': [{'text': '客户'}]}))
    assert not result['is_error'], payload(result)


def test_find_tags_cache_key_includes_eligible_and_marks_repeats():
    retriever = CountingEvidence()
    ctx = ctx_for(retriever)
    first = asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'R1'}], 'depth': 'quick'}))
    assert not first['is_error'] and retriever.calls['lookup'] == 1
    assert payload(first)['results'][0]['cached'] is False
    assert payload(first)['results'][0]['cards'][0]['matched_by'] == 'EXACT_ALIAS'
    assert ctx.searches['R1'] == {'quick'}

    ctx2 = ctx_for(retriever)
    second = asyncio.run(dispatch(ctx2, 'find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'R1'}], 'depth': 'quick'}))
    assert retriever.calls['lookup'] == 1
    assert payload(second)['results'][0]['cached'] is True

    ctx3 = ctx_for(retriever, eligible_tag_ids=[1, 99])
    third = asyncio.run(dispatch(ctx3, 'find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'R1'}], 'depth': 'quick'}))
    assert third['is_error'] is False
    assert retriever.calls['lookup'] == 2


def test_deep_and_tool_budgets_are_enforced(monkeypatch):
    monkeypatch.setenv('TAG_AGENT_MAX_DEEP', '1')
    ctx = ctx_for()
    first = asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'R1'}], 'depth': 'deep'}))
    assert not first['is_error'], payload(first)
    second = asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '金融资产', 'requirement_id': 'R2'}], 'depth': 'deep'}))
    assert second['is_error'] and '预算' in payload(second)['message']

    monkeypatch.setenv('TAG_AGENT_MAX_TOOLS', '2')
    ctx2 = ctx_for()
    assert not asyncio.run(dispatch(ctx2, 'find_tags', {'queries': [{'text': 'a'}]}))['is_error']
    assert not asyncio.run(dispatch(ctx2, 'find_tags', {'queries': [{'text': 'b'}]}))['is_error']
    blocked = asyncio.run(dispatch(ctx2, 'find_tags', {'queries': [{'text': 'c'}]}))
    assert blocked['is_error'] and '工具预算已用完' in payload(blocked)['message']
    accepted = asyncio.run(dispatch(ctx2, 'submit_result', {'outcome': 'PARTIAL',
        'plan': {'tree': {'kind': 'SCOPE_ALL', 'clause_id': 'all', 'source_span': '全部客户'}}}))
    assert not accepted['is_error'], payload(accepted)


def test_detail_budget_shared_with_guard_reads(monkeypatch):
    monkeypatch.setenv('TAG_AGENT_MAX_DETAILS', '2')
    ctx = ctx_for()
    assert not asyncio.run(dispatch(ctx, 'get_tag_details', {'tag_ids': [1]}))['is_error']
    assert not asyncio.run(dispatch(ctx, 'get_tag_details', {'tag_ids': [1]}))['is_error']
    third = asyncio.run(dispatch(ctx, 'get_tag_details', {'tag_ids': [1]}))
    assert third['is_error'] and '详情读取预算已用完' in payload(third)['message']


def test_observation_byte_cap_truncates_with_hint():
    big = CountingEvidence({'selection_context': {'tags': [{**TAG, 'definition_long': 'x' * 300} for _ in range(120)],
                                                   'code_values': []}})
    ctx = ctx_for(big)
    result = asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '客户'}]}))
    text = result['content'][0]['text']
    assert len(text.encode()) <= 6144
    data = json.loads(text)
    assert data['truncated'] is True and 'value_query' in data['hint']
    assert len(ctx.tags) == 1


def test_tool_argument_limits_are_contract_errors():
    ctx = ctx_for()
    nine = {'queries': [{'text': 'q%d' % i} for i in range(9)]}
    assert asyncio.run(dispatch(ctx, 'find_tags', nine))['is_error']
    assert asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': 'q'}], 'top_k': 9}))['is_error']
    assert asyncio.run(dispatch(ctx, 'get_tag_details', {'tag_ids': list(range(1, 12))}))['is_error']
    assert asyncio.run(dispatch(ctx, 'get_tag_details', {'tag_ids': [1], 'max_values': 31}))['is_error']


def test_check_plan_returns_diagnostics_clauses_and_repeat_hint():
    ctx = ctx_for()
    bad = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '转入超过50万',
                    'tag_id': 1, 'operator': 'INVALID', 'values': ['500000']}}
    first = asyncio.run(dispatch(ctx, 'check_plan', {'plan': bad}))
    assert first['is_error']
    first_data = payload(first)
    assert first_data['ok'] is False and first_data['hint'] is None
    assert first_data['clauses'][0]['clause_id'] == 'a'
    assert any(d['code'] == 'INVALID_OPERATOR' for d in first_data['diagnostics'])

    second = asyncio.run(dispatch(ctx, 'check_plan', {'plan': bad}))
    second_data = payload(second)
    assert second_data['hint'] == '无新进展，请换思路或提交 PARTIAL'
    assert ctx.diagnostic_repeats >= 1
    assert second_data['plan_hash'] == first_data['plan_hash']


def test_capabilities_records_trail_and_rejects_out_of_scope_inputs():
    ctx = ctx_for()
    result = asyncio.run(dispatch(ctx, 'find_capabilities', {'query': '高价值', 'requirement_ids': ['R1']}))
    assert not result['is_error'], payload(result)
    assert ctx.searches['R1'] == {'capabilities'}
    assert 'TAG CONST ADD SUB MUL DIV COUNT_POSITIVE CAPABILITY' in payload(result)['operators']

    bad = CountingEvidence({'capabilities': [{'capability_id': 'c1', 'version': 1, 'input_tag_ids': [99]}]})
    ctx2 = ctx_for(bad)
    result = asyncio.run(dispatch(ctx2, 'find_capabilities', {'query': 'x'}))
    assert result['is_error'] and ctx2.stats['fatal_status'] == 403


def test_working_set_keeps_details_and_codes_for_validation():
    ctx = ctx_for()
    asyncio.run(dispatch(ctx, 'get_tag_details', {'tag_ids': [1], 'value_query': '转入'}))
    assert 1 in ctx.details_loaded and 1 in ctx.tags
    assert ctx.stats['details'] == 1
