"""收尾第 1/4 项：独立复核与人工抽检的机制测试。"""
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from tagpilot_eval.human_review import build_page, import_decisions, stratified_queue
from tagpilot_eval.io import read_jsonl
from tagpilot_eval.review import (_core, _name_rebound, apply_reviews, build_packet,
                                  load_reviews, mechanical, summarize)
from tagpilot_eval.validation import validate_package

PACKAGE = Path(__file__).resolve().parents[1]
P0 = PACKAGE / 'data/p0-v2'
CAL = PACKAGE / 'data/calibration-v2'
CAL_V1 = PACKAGE / 'data/calibration-v1'
REVIEWS = PACKAGE / 'reviews/independent-review-v1.jsonl'


@pytest.fixture(scope='module')
def facts():
    return {r['tag_id']: r for r in read_jsonl(P0 / 'facts.jsonl')}


def test_packet_covers_all_mothers_and_flags_only_known_cases(facts):
    packet = build_packet(P0, CAL_V1)
    assert len(packet) == 200
    summary = summarize(packet)
    assert summary['flag_codes'] == {'FIXTURE_LITERAL_IN_UTTERANCE': 6, 'REQUIREMENT_TEXT_REUSED': 8}
    # 交付的 v2 已改写重复话术；仅保留已明确接受为 Demo 约定的模拟字面量提示。
    assert summarize(build_packet(P0, CAL))['flag_codes'] == {'FIXTURE_LITERAL_IN_UTTERANCE': 6}


def test_mechanical_review_has_no_binding_or_caliber_defects(facts):
    findings = mechanical(facts, read_jsonl(CAL_V1 / 'cases.jsonl'))
    codes = Counter(f['code'] for row in findings for f in row['flags'])
    for severe in ('FIELD_BINDING', 'UNIT_BINDING', 'CALIBER_MISMATCH', 'UNSUPPORTED_OPERATOR',
                   'CODE_NOT_IN_MAP', 'ELIGIBILITY_LEAK', 'READY_ON_UNRESOLVED', 'NAME_NOT_REBOUND',
                   'FORBIDDEN_IN_TREE', 'THRESHOLD_NOT_IN_UTTERANCE'):
        assert codes.get(severe, 0) == 0, severe


def test_name_rebinding_is_tolerant_but_catches_a_wrong_tag():
    assert _name_rebound('当前持有理财标志', '当前没有持有理财，未知状态不算没有持有。')
    assert _name_rebound('历史品质生活订单最近一次下单金额', '帮我找历史品质生活订单最近一次下单金额至少10万元的客户。')
    assert not _name_rebound('当前持有理财标志', '帮我找近30天异名跨行转入至少50万元的客户。')
    assert _core('勿扰客户（企微标签）') == '勿扰客户'


def test_reviews_cover_every_mother_with_required_fields():
    reviews = load_reviews(REVIEWS)
    assert len(reviews) == 200
    verdicts = Counter(r['verdict'] for r in reviews.values())
    assert verdicts == {'ACCEPT': 192, 'REVISE': 8}
    for review in reviews.values():
        assert review['reviewer'] and review['reviewed_at'] and review['reason']


def test_revise_must_supply_patch(tmp_path):
    rows = read_jsonl(REVIEWS)
    rows[0].update(verdict='REVISE', patch=None)
    path = tmp_path / 'bad.jsonl'
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n')
    with pytest.raises(ValueError, match='patch'):
        load_reviews(path)


def test_apply_reviews_rejects_truth_layer_patch(tmp_path):
    rows = read_jsonl(REVIEWS)
    rows[0].update(verdict='REVISE', patch={'expected': {'outcomes': ['READY']}})
    path = tmp_path / 'bad.jsonl'
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n')
    with pytest.raises(ValueError, match='表达层'):
        apply_reviews(P0, CAL_V1, path, tmp_path / 'out')


def test_apply_reviews_reproduces_delivered_v2(tmp_path):
    """同输入同代码应重现同一交付版本（cases.jsonl 逐字节一致）。"""
    apply_reviews(P0, CAL_V1, REVIEWS, tmp_path / 'v2')
    assert (tmp_path / 'v2/cases.jsonl').read_bytes() == (CAL / 'cases.jsonl').read_bytes()
    assert validate_package(P0, tmp_path / 'v2')['passed']


def test_delivered_v2_is_valid_and_marks_review_complete():
    result = validate_package(P0, CAL)
    assert result['passed'] and result['case_count'] == 200
    manifest = json.loads((CAL / 'manifest.json').read_text())
    assert manifest['independent_model_review'] == 'COMPLETED'
    assert manifest['human_review'] == 'PENDING'
    assert len(manifest['revised_cases']) == 8


def test_stratified_queue_is_reproducible_and_sized():
    cases = read_jsonl(CAL / 'cases.jsonl')
    queue = stratified_queue(cases)
    assert len(queue) == 40
    assert Counter(c['category'] for c in queue) == {'SINGLE': 8, 'COMPOSITION': 8,
                                                     'CLARIFICATION': 8, 'BOUNDARY': 6,
                                                     'MULTITURN': 5, 'GAP': 5}
    assert [c['case_id'] for c in queue] == [c['case_id'] for c in stratified_queue(cases)]


def test_human_page_builds_and_import_enforces_completeness(tmp_path):
    page = build_page(P0, CAL, REVIEWS, tmp_path / 'page')
    assert page['queued'] == 40
    assert (tmp_path / 'page/human-review.html').exists()
    queue = tmp_path / 'page/queue.json'
    cids = json.loads(queue.read_text())['cases']
    partial = tmp_path / 'decisions.json'
    partial.write_text(json.dumps([{'case_id': cids[0], 'decision': 'REJECT', 'comment': '理由'}]))
    with pytest.raises(ValueError, match='未覆盖'):
        import_decisions(queue, partial, tmp_path / 'ledger.jsonl')
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps([{'case_id': cid, 'decision': 'REJECT', 'comment': ''} for cid in cids]))
    with pytest.raises(ValueError, match='原因'):
        import_decisions(queue, bad, tmp_path / 'ledger.jsonl')
    good = tmp_path / 'good.json'
    good.write_text(json.dumps([{'case_id': cid, 'decision': 'ACCEPT', 'comment': None} for cid in cids]))
    assert import_decisions(queue, good, tmp_path / 'ledger.jsonl')['imported'] == 40
