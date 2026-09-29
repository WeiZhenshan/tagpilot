"""P2 根因归因：超时/无效运行必须与语义失败分开，证据不足不得硬凑原因。"""
from pathlib import Path

from tagpilot_eval.io import read_jsonl
from tagpilot_eval.p2_diagnose import _l1_hits, classify

PACKAGE = Path(__file__).resolve().parents[1]
FACTS = {r['tag_id']: r for r in read_jsonl(PACKAGE / 'data/p0-v2/facts.jsonl')}


def _fact(**overrides):
    fact = {'case_id': 'CAL-1001', 'target_tag_ids': [721], 'unresolved_fact_ids': [],
            'domains': ['客户价值'], 'split': 'DEV', 'category': 'SINGLE',
            'expected': {'tree': {'kind': 'PREDICATE', 'operator': '>=', 'values': ['200000'],
                                  'data_kind': 'NUMBER', 'caliber': {},
                                  'expression': {'kind': 'TAG', 'tag_id': 721}}}}
    fact.update(overrides)
    return fact


def _verdict(failures, **evidence):
    return {'status': 'FAIL', 'failures': failures, 'evidence': evidence}


def test_invalid_run_and_timeout_are_separated_from_semantics():
    assert classify(_fact(), _verdict([]), {'status': 'RUN_INVALID'}, None, FACTS) == 'RUN_INVALID'
    assert classify(_fact(), _verdict([]), {'status': 'AGENT_TIMEOUT'}, None, FACTS) == 'TIMEOUT'
    cancelled = _verdict([], cancelled_by_harness=True)
    assert classify(_fact(), cancelled, {'status': 'COMPLETED'}, None, FACTS) == 'TIMEOUT'
    noted = _verdict([], note='运行超过单题时限，已取消并取回最佳草案')
    assert classify(_fact(), noted, {'status': 'COMPLETED'}, None, FACTS) == 'TIMEOUT'


def test_unresolved_source_fact_is_attributed_to_the_source():
    fact = _fact(target_tag_ids=[1291], unresolved_fact_ids=['TAG:1291'])
    assert classify(fact, _verdict(['OUTCOME']), {'status': 'COMPLETED'}, None, FACTS) == 'SOURCE_FACT'


def test_retrieval_miss_requires_l1_evidence():
    """None = 该题没有 L1 结果（不得判未命中）；空集合 = L1 跑了但没召回（正是未命中）。"""
    assert classify(_fact(), _verdict(['TREE']), {'status': 'COMPLETED'}, None, FACTS) != 'RETRIEVAL_MISS'
    assert classify(_fact(), _verdict(['TREE']), {'status': 'COMPLETED'}, set(), FACTS) == 'RETRIEVAL_MISS'
    assert classify(_fact(), _verdict(['TREE']), {'status': 'COMPLETED'}, {721}, FACTS) != 'RETRIEVAL_MISS'
    assert classify(_fact(), _verdict(['TREE']), {'status': 'COMPLETED'}, {999}, FACTS) == 'RETRIEVAL_MISS'


def test_behavior_failures_are_named_by_their_evidence():
    assert classify(_fact(), _verdict(['SLOTS']), {'status': 'COMPLETED'}, None, FACTS) == 'CLARIFICATION_BEHAVIOR'
    assert classify(_fact(), _verdict(['NO_INTERRUPT']), {'status': 'COMPLETED'}, None, FACTS) == 'CLARIFICATION_BEHAVIOR'
    assert classify(_fact(), _verdict(['GAP_REASON']), {'status': 'COMPLETED'}, None, FACTS) == 'GAP_BEHAVIOR'
    assert classify(_fact(), _verdict(['OUTCOME']), {'status': 'COMPLETED'}, None, FACTS) == 'OUTCOME'
    assert classify(_fact(), _verdict(['FULL_ID_SET']), {'status': 'COMPLETED'}, None, FACTS) == 'AGENT_GUARD'


def test_tree_failures_split_by_operator_and_binding():
    same_tags_wrong_operator = {'status': 'COMPLETED', 'output': {'plan': {'tree': {
        'kind': 'PREDICATE', 'operator': '>', 'values': ['200000'], 'data_kind': 'NUMBER',
        'caliber': {}, 'expression': {'kind': 'TAG', 'tag_id': 721}}}}}
    different_tag = {'status': 'COMPLETED', 'output': {'plan': {'tree': {
        'kind': 'PREDICATE', 'operator': '>=', 'values': ['200000'], 'data_kind': 'NUMBER',
        'caliber': {}, 'expression': {'kind': 'TAG', 'tag_id': 735}}}}}
    assert classify(_fact(), _verdict(['TREE']), same_tags_wrong_operator, None, FACTS) == 'LOGIC'
    assert classify(_fact(), _verdict(['TREE']), different_tag, None, FACTS) == 'DISAMBIGUATION'
    assert classify(_fact(), _verdict(['TREE']), {'status': 'COMPLETED', 'output': {}}, None, FACTS) == 'AGENT_GUARD'


def test_missing_evidence_stays_unattributed():
    assert classify(_fact(), _verdict([]), {'status': 'COMPLETED'}, None, FACTS) == 'UNATTRIBUTED'


def test_l1_hits_align_leaves_with_recalled_flags(tmp_path):
    case = read_jsonl(PACKAGE / 'data/calibration-v2/cases.jsonl')
    multi = next(c for c in case if len(c['target_tag_ids']) >= 2 and c['expected'].get('tree'))
    l1_dir = tmp_path / 'l1'
    l1_dir.mkdir()
    (l1_dir / 'l1-results.jsonl').write_text(
        '{"case_id": "%s", "recalled": [true, false]}\n' % multi['case_id'])
    hits, available = _l1_hits(l1_dir, {multi['case_id']: multi})
    assert available is True
    assert len(hits[multi['case_id']]) == 1
    assert _l1_hits(tmp_path / 'missing', {})[1] is False
