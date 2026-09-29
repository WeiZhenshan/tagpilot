"""P2 分层 L2 的抽样与稳定性：不碰 HOLDOUT、复跑 run_id 必须互异。"""
from collections import Counter
from pathlib import Path

import pytest

from tagpilot_eval.io import read_jsonl
from tagpilot_eval.p2_l2 import (STABILITY_REPEATS, run_id_for, stability_report,
                                 stability_selection, stratified_sample)

PACKAGE = Path(__file__).resolve().parents[1]
CASES = read_jsonl(PACKAGE / 'data/p2-split-v1/cases.jsonl')


def test_sample_excludes_holdout_and_hits_target():
    sample = stratified_sample(CASES, target=100)
    assert len(sample) == 100
    assert {case['split'] for case in sample} <= {'DEV', 'REGRESSION'}
    assert not any(case['split'] == 'HOLDOUT' for case in sample)


def test_sample_is_deterministic_and_stratified():
    first = stratified_sample(CASES, target=120)
    assert [c['case_id'] for c in first] == [c['case_id'] for c in stratified_sample(CASES, target=120)]
    categories = Counter(c['category'] for c in first)
    assert len(categories) == len({c['category'] for c in CASES}), '每个类别都应有样本'


def test_sample_raises_when_the_pool_is_too_small():
    with pytest.raises(ValueError, match='可用案例不足'):
        stratified_sample(CASES, target=10_000)


def test_stability_selection_comes_from_regression_and_prefers_unsampled():
    sample = stratified_sample(CASES, target=120)
    sampled_ids = {c['case_id'] for c in sample}
    chosen = stability_selection(CASES, sampled_ids, count=40)
    assert len(chosen) == 40
    assert all(case['split'] == 'REGRESSION' for case in chosen)
    assert not ({case['case_id'] for case in chosen} & sampled_ids)


def test_repeat_run_ids_are_distinct_per_repeat():
    """回归：三次复跑若共用一个 run_id，Agent 会幂等返回同一份结果，稳定性就成了假象。"""
    ids = {run_id_for('a' * 64, 'CAL-1001', repeat) for repeat in range(1, STABILITY_REPEATS + 1)}
    assert len(ids) == STABILITY_REPEATS
    assert all(identifier.startswith('eval-aaaaaaaa-cal-1001-r') for identifier in ids)
    assert run_id_for('b' * 64, 'CAL-1001', 1) != run_id_for('a' * 64, 'CAL-1001', 1)


def _run(case_id, repeat, tree):
    return {'case_id': case_id, 'repeat': repeat, 'run_id': run_id_for('c' * 64, case_id, repeat),
            'outcome': 'READY', 'output': {'plan': {'tree': tree}, 'questions': []}}


def test_stability_report_counts_semantic_consistency():
    tree = {'kind': 'PREDICATE', 'operator': '>=', 'values': ['100'],
            'data_kind': 'NUMBER', 'expression': {'kind': 'TAG', 'tag_id': 721}}
    # 复跑编号是 1..N；repeat 0 是 500 样本那次基线运行，不参与稳定性统计。
    consistent = [_run('CAL-1001', repeat, tree) for repeat in range(1, STABILITY_REPEATS + 1)]
    other = [*consistent[:-1], _run('CAL-1001', STABILITY_REPEATS, {**tree, 'values': ['200']})]
    report = stability_report(consistent)
    assert report['cases'] == 1 and report['consistent'] == 1 and report['consistency_rate'] == 1.0
    assert len(set(report['detail'][0]['run_ids'])) == STABILITY_REPEATS
    assert stability_report(other)['consistent'] == 0


def test_stability_report_treats_missing_repeats_as_inconsistent():
    report = stability_report([_run('CAL-1002', 1, None)])
    assert report['consistent'] == 0 and report['consistency_rate'] == 0.0
    assert report['detail'][0]['reason'] == '复跑次数不足'
