"""L1/L2 跑批的离线单元测试（不发起网络调用）。"""
import json
from pathlib import Path

from tagpilot_eval.io import read_jsonl
from tagpilot_eval.l1 import _chunks, _leaves, _phrase
from tagpilot_eval.l2 import _fixture_rows, _merge_multiturn, _status

PACKAGE = Path(__file__).resolve().parents[1]
P0 = PACKAGE / 'data/p0-v2'


def _facts():
    return {r['tag_id']: r for r in read_jsonl(P0 / 'facts.jsonl')}


def test_phrase_renders_numbers_units_and_codes():
    facts = _facts()
    node = {'kind': 'PREDICATE', 'operator': '>=', 'values': ['200000'], 'data_kind': 'NUMBER',
            'expression': {'kind': 'TAG', 'tag_id': 721}}
    assert '20万' in _phrase(facts[721], node)
    code_node = {'kind': 'PREDICATE', 'operator': 'in', 'values': ['C3', 'C4'], 'data_kind': 'STRING',
                 'expression': {'kind': 'TAG', 'tag_id': 1466}}
    phrase = _phrase(facts[1466], code_node)
    assert 'C3' in phrase and 'C4' in phrase
    null_node = {'kind': 'PREDICATE', 'operator': 'is_null', 'values': [], 'data_kind': 'STRING',
                 'expression': {'kind': 'TAG', 'tag_id': 1466}}
    assert '为空' in _phrase(facts[1466], null_node)


def test_leaves_walks_groups_and_ignores_scope_all():
    tree = {'kind': 'GROUP', 'logic': 'AND', 'children': [
        {'kind': 'PREDICATE', 'expression': {'kind': 'TAG', 'tag_id': 1}, 'operator': '>=',
         'values': ['1'], 'data_kind': 'NUMBER'},
        {'kind': 'GROUP', 'logic': 'OR', 'children': [
            {'kind': 'PREDICATE', 'expression': {'kind': 'TAG', 'tag_id': 2}, 'operator': '=',
             'values': ['1'], 'data_kind': 'NUMBER'}]},
        {'kind': 'SCOPE_ALL'}]}
    assert len(_leaves(tree)) == 2
    assert _leaves({'kind': 'SCOPE_ALL'}) == []
    assert _leaves(None) == []


def test_chunks_respects_batch_limit():
    assert [len(c) for c in _chunks(list(range(20)), 8)] == [8, 8, 4]


def test_fixture_rows_loads_full_dataset():
    manifest = json.loads((P0 / 'manifest.json').read_text())
    rows = _fixture_rows(manifest)
    assert len(rows) == 2000
    assert all(r['CUST_ID'].startswith('SIM20260918') for r in rows)


def test_l2_status_mapping():
    assert _status('COMPLETED', {'outcome': {'outcome': 'READY'}}, {}) == 'COMPLETED'
    assert _status('RUNNING', {'status': 'RUN_INVALID'}, {}) == 'RUN_INVALID'
    assert _status(None, {'status': 'RUN_INVALID'}, {}) == 'RUN_INVALID'
    assert _status('RUNNING', {'timeout': True}, {}) == 'AGENT_TIMEOUT'
    assert _status('FAILED', {}, {'agent_failure': True}) == 'AGENT_FAILED'
    assert _status('FAILED', {}, {}) == 'RUN_INVALID'


def test_multiturn_merge_requires_first_turn_pass():
    final = {'status': 'PASS', 'checks': {'outcome_expected': True}, 'failures': [], 'evidence': {}}
    first_fail = {'status': 'FAIL', 'checks': {}, 'failures': ['OUTCOME'], 'evidence': {'x': 1}}
    merged = _merge_multiturn(final, first_fail, {})
    assert merged['status'] == 'FAIL' and 'FIRST_TURN' in merged['failures']
    first_pass = {'status': 'PASS', 'checks': {}, 'failures': [], 'evidence': {}}
    merged = _merge_multiturn(final, first_pass, {})
    assert merged['status'] == 'PASS'


class _StubAgent:
    def __init__(self, states):
        self._states = list(states)
        self.calls = []

    def run_to_terminal(self, request, deadline_seconds=0):
        self.calls.append({'kind': 'run', 'run_id': request['run_id'],
                           'requirement': request['requirement'],
                           'previous_plan': request.get('previous_plan'),
                           'history': len(request.get('history') or [])})
        return self._states.pop(0), []

    def resume(self, run_id, owner, answer, eligible, deadline_seconds=0):
        self.calls.append({'kind': 'resume', 'run_id': run_id, 'answer': answer})
        return self._states.pop(0), []


_CASE = {'case_id': 'CAL-161', 'requirement': '先找当前时点AUM至少20万元的客户。',
         'eligible_tag_ids': [721], 'reference_date': '2026-09-18', 'timezone': 'Asia/Shanghai',
         'turns': [{'user_message': '在刚才的基础上，再要求理财为否。'}]}
_BUNDLE = {'build_id': 'b', 'snapshot_id': 's', 'artifact_hash': 'a'}


def test_drive_case_opens_new_run_for_followup_message():
    """非 WAITING 时，新的用户消息必须开新 run 并带 previous_plan 与 history。"""
    from tagpilot_eval.l2 import _drive_case
    states = [{'status': 'COMPLETED', 'result': {'plan': {'tree': {'kind': 'SCOPE_ALL'}}}},
              {'status': 'COMPLETED', 'result': {'plan': {}}}]
    agent = _StubAgent(states)
    returned, _ = _drive_case(agent, _CASE, _BUNDLE, 'eval-cal-161', 10)
    assert [c['kind'] for c in agent.calls] == ['run', 'run']
    assert agent.calls[1]['run_id'] == 'eval-cal-161-t1'
    assert agent.calls[1]['previous_plan'] == {'tree': {'kind': 'SCOPE_ALL'}}
    assert agent.calls[1]['history'] == 1
    assert agent.calls[1]['requirement'] == '在刚才的基础上，再要求理财为否。'
    assert len(returned) == 2


def test_drive_case_uses_resume_when_waiting():
    from tagpilot_eval.l2 import _drive_case
    states = [{'status': 'WAITING', 'result': {'outcome': {'outcome': 'NEEDS_USER_INPUT'},
                                              'interrupt_id': 'x', 'questions': [], 'plan': {}}},
              {'status': 'COMPLETED', 'result': {'plan': {}}}]
    agent = _StubAgent(states)
    _drive_case(agent, _CASE, _BUNDLE, 'eval-cal-161', 10)
    assert [c['kind'] for c in agent.calls] == ['run', 'resume']
    assert agent.calls[1]['answer'] == '在刚才的基础上，再要求理财为否。'


def test_turn_evidence_and_first_turn_reconstruction():
    """每轮证据必须落盘，否则多轮判定在再判定时不可复现。"""
    from tagpilot_eval.l2 import _reconstruct_first, _turn_evidence
    waiting = {'status': 'WAITING', 'result': {'outcome': {'outcome': 'NEEDS_USER_INPUT'},
                                               'plan': {}, 'questions': [{'reason': 'THRESHOLD_MISSING'}],
                                               'interrupt_id': 'r-1'}}
    final = {'status': 'COMPLETED', 'result': {'outcome': {'outcome': 'READY'},
                                               'plan': {'tree': {'kind': 'SCOPE_ALL'}}}}
    run = {'output': {'turns': [_turn_evidence(waiting), _turn_evidence(final)]}}
    first = _reconstruct_first(run)
    assert first['status'] == 'COMPLETED'          # 有终态即可判定（澄清终态由 outcome 表达）
    assert first['outcome']['outcome'] == 'NEEDS_USER_INPUT'
    assert first['interrupt_id'] == 'r-1'
    # 旧记录没有 turns 字段时不得假装首轮通过。
    assert _reconstruct_first({'output': {'plan': {}}}) is None
