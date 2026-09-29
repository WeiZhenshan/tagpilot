"""P2 母案例与分区的不变量：配额、唯一性、隔离键、污染检查。"""
import json
from collections import Counter
from pathlib import Path

import pytest

from tagpilot_eval.contracts import EvalCase
from tagpilot_eval.io import read_jsonl
from tagpilot_eval.p2_mothers import QUOTAS
from tagpilot_eval.p2_partition import (assign_splits, cross_partition_checks, template_signature)
from tagpilot_eval.validation import validate_package

PACKAGE = Path(__file__).resolve().parents[1]
P0 = PACKAGE / 'data/p0-v2'
MOTHERS = PACKAGE / 'data/p2-mothers-v1'
SPLIT = PACKAGE / 'data/p2-split-v1'
P1 = PACKAGE / 'data/calibration-v2'


@pytest.fixture(scope='module')
def mothers():
    return read_jsonl(MOTHERS / 'cases.jsonl')


@pytest.fixture(scope='module')
def split_cases():
    return read_jsonl(SPLIT / 'cases.jsonl')


def test_mothers_shape_and_quotas(mothers):
    assert len(mothers) == 500
    counts = Counter(c['category'] for c in mothers)
    assert dict(counts) == QUOTAS
    assert len({c['case_id'] for c in mothers}) == 500
    assert len({c['mother_id'] for c in mothers}) == 500
    assert all(c['phase'] == 'P2' and c['split'] == 'UNPARTITIONED' for c in mothers)
    assert all(c['variant_index'] == 0 and c['variant_mode'] == 'TEMPLATE' for c in mothers)
    for case in mothers:
        EvalCase.model_validate(case)


def test_mothers_validate_without_errors():
    result = validate_package(P0, MOTHERS)
    assert result['passed'] and result['errors'] == []
    assert result['case_count'] == 500 and result['phase'] == 'P2'


def test_p2_case_ids_do_not_collide_with_p1(mothers):
    p1_ids = {c['case_id'] for c in read_jsonl(P1 / 'cases.jsonl')}
    assert not (p1_ids & {c['case_id'] for c in mothers})


def test_expected_terminal_states_are_actionable(mothers):
    for case in mothers:
        expected = case['expected']
        outcome = expected['outcomes'][0]
        if outcome == 'READY':
            assert expected.get('tree') and not case['unresolved_fact_ids']
        elif outcome == 'NEEDS_USER_INPUT':
            assert expected['required_slots']
        else:
            assert expected['gap_codes']
            assert case['l3_status'] == 'NOT_APPLICABLE'


def test_partition_covers_every_case_and_has_no_key_leak(split_cases):
    assert len(split_cases) == 500
    assert {c['split'] for c in split_cases} == {'DEV', 'REGRESSION', 'HOLDOUT'}
    assert validate_package(P0, SPLIT)['passed']
    partition = json.loads((SPLIT / 'partition.json').read_text())
    assert partition['cross_partition_key_leaks'] == []
    assert partition['cases_by_split'] == {'DEV': 350, 'REGRESSION': 101, 'HOLDOUT': 49}


def test_partition_keeps_a_regression_floor(split_cases):
    mothers = {c['mother_id']: c for c in split_cases}
    assert sum(1 for c in mothers.values() if c['split'] == 'REGRESSION') >= 100


def test_partition_does_not_change_truth(mothers, split_cases):
    before = {c['case_id']: c for c in mothers}
    for case in split_cases:
        original = dict(before[case['case_id']])
        original['split'] = case['split']
        assert original == case


def test_assign_splits_is_deterministic_and_exact():
    keys = {f'k{i}' for i in range(1000)}
    first = assign_splits(keys)
    assert first == assign_splits(keys)
    counts = Counter(first.values())
    assert counts['DEV'] + counts['REGRESSION'] + counts['HOLDOUT'] == 1000
    assert counts['REGRESSION'] >= 200 and counts['HOLDOUT'] > 0


def test_template_signature_masks_names_numbers_and_quantifiers():
    names = {721: '当前时点AUM', 601: '当前持有理财标志'}
    left = {'requirement': '当前时点AUM至少50万元，并且当前持有理财标志为否。', 'turns': [],
            'target_tag_ids': [721, 601], 'forbidden_tag_ids': []}
    right = {'requirement': '当前时点AUM恰好80万元，并且当前持有理财标志为是。', 'turns': [],
             'target_tag_ids': [721, 601], 'forbidden_tag_ids': []}
    assert template_signature(left, names) == template_signature(right, names)


def test_cross_partition_checks_flags_key_leak():
    names = {526: '性别'}
    base = {'lineage_group': 'LIN-a', 'target_tag_ids': [526], 'forbidden_tag_ids': [], 'turns': []}
    left = {**base, 'case_id': 'A', 'split': 'DEV', 'requirement': '性别为男的客户。'}
    right = {**base, 'case_id': 'B', 'split': 'HOLDOUT', 'requirement': '性别为男的客户。'}
    keys = {c['case_id']: (c['lineage_group'], template_signature(c, names)) for c in (left, right)}
    assert len(cross_partition_checks([left, right], keys)['cross_partition_key_leaks']) == 1
