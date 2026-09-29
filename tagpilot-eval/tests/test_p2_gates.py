"""P2 闸门与基准复核的单元测试：包形状来自包本身，漂移分类不做模糊结论。"""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from tagpilot_eval.contracts import EvalCase
from tagpilot_eval.io import file_hash, read_jsonl
from tagpilot_eval.p2_basis import observation_diff
from tagpilot_eval.validation import expected_shape, validate_cases

PACKAGE = Path(__file__).resolve().parents[1]
P0 = PACKAGE / 'data/p0-v1'
CAL = PACKAGE / 'data/calibration-v1'
CAL_MANIFEST = json.loads((CAL / 'manifest.json').read_text())


def _observation(tags=None, semantics=None, codes=None, observed_at='2026-09-27T00:00:00+00:00'):
    return {'observed_at': observed_at,
            'database': {'tags': tags or [], 'semantics': semantics or [], 'codes': codes or [],
                         'snapshots': [], 'builds': [], 'capabilities': [], 'customer_counts': []}}


def test_observation_diff_ignores_timestamp():
    first = _observation(tags=[{'tag_id': 1, 'version': 3}])
    second = deepcopy(first)
    second['observed_at'] = '2026-09-28T00:00:00+00:00'
    assert observation_diff(first, second)['idempotent_ignoring_timestamp'] is True


def test_observation_diff_records_code_addition_without_claiming_equality():
    first = _observation(codes=[{'field_name': 'F', 'code': '01'}])
    second = _observation(codes=[{'field_name': 'F', 'code': '01'}, {'field_name': 'F', 'code': '02'}])
    diff = observation_diff(first, second)
    assert diff['codes_added'] == [{'field_name': 'F', 'code': '02'}]
    assert diff['sections']['codes'] is False


def test_observation_diff_rejects_code_removal():
    first = _observation(codes=[{'field_name': 'F', 'code': '01'}, {'field_name': 'F', 'code': '02'}])
    second = _observation(codes=[{'field_name': 'F', 'code': '01'}])
    with pytest.raises(ValueError, match='码值被删除'):
        observation_diff(first, second)


def test_observation_diff_rejects_tag_set_change():
    with pytest.raises(ValueError, match='必须新出 P0 版本'):
        observation_diff(_observation(tags=[{'tag_id': 1, 'version': 3}]),
                         _observation(tags=[{'tag_id': 2, 'version': 3}]))


def test_observation_diff_records_tag_and_semantics_field_changes():
    diff = observation_diff(
        _observation(tags=[{'tag_id': 1, 'version': 3}], semantics=[{'tag_id': 1, 'unit': 'RATIO'}]),
        _observation(tags=[{'tag_id': 1, 'version': 4}], semantics=[{'tag_id': 1, 'unit': 'COUNT'}]))
    assert diff['tags_changed'] == [{'tag_id': 1, 'changed_fields': ['version'],
                                     'before': {'version': 3}, 'after': {'version': 4}}]
    assert diff['semantics_changed'][0]['changed_fields'] == ['unit']
    assert diff['sections']['tags'] is False


def test_expected_shape_comes_from_the_package_manifest():
    assert expected_shape(CAL_MANIFEST) == {
        'phase': 'P1', 'case_count': 200, 'mother_count': 200, 'formal_cases': 0,
        'allow_quota_shortfall': False,
        'quotas': {'SINGLE': 60, 'COMPOSITION': 50, 'CLARIFICATION': 30,
                   'BOUNDARY': 20, 'MULTITURN': 20, 'GAP': 20}}


def test_declared_shortfall_allows_under_target_but_not_overrun():
    facts = {r['tag_id']: r for r in read_jsonl(P0 / 'facts.jsonl')}
    cases = read_jsonl(CAL / 'cases.jsonl')
    shortfall = dict(expected_shape(CAL_MANIFEST), allow_quota_shortfall=True)
    shortfall['quotas'] = dict(shortfall['quotas'], SINGLE=80)
    assert validate_cases(cases, facts, file_hash(P0 / 'manifest.json'), shortfall)['passed']
    overrun = dict(expected_shape(CAL_MANIFEST), allow_quota_shortfall=True)
    overrun['quotas'] = dict(overrun['quotas'], SINGLE=10)
    with pytest.raises(ValueError, match='超出目标配额'):
        validate_cases(cases, facts, file_hash(P0 / 'manifest.json'), overrun)
    # 目标里漏掉一个类别时，该类别相对目标 0 即为超配，同样被拦下。
    missing = dict(expected_shape(CAL_MANIFEST), allow_quota_shortfall=True)
    missing['quotas'] = {name: quota for name, quota in missing['quotas'].items() if name != 'GAP'}
    with pytest.raises(ValueError, match='超出目标配额'):
        validate_cases(cases, facts, file_hash(P0 / 'manifest.json'), missing)


def test_validate_cases_rejects_count_mismatch_against_declared_shape():
    facts = {r['tag_id']: r for r in read_jsonl(P0 / 'facts.jsonl')}
    oversized = dict(expected_shape(CAL_MANIFEST), case_count=2000, mother_count=500)
    with pytest.raises(ValueError, match='必须恰好2000个案例'):
        validate_cases(read_jsonl(CAL / 'cases.jsonl'), facts, file_hash(P0 / 'manifest.json'), oversized)


def test_p2_case_identity_and_variant_fields():
    case = deepcopy(read_jsonl(CAL / 'cases.jsonl')[0])
    case.update({'case_id': 'CAL-1001', 'mother_id': 'M-1001', 'phase': 'P2', 'split': 'DEV',
                 'variant_index': 2, 'variant_mode': 'MODEL_PARAPHRASE'})
    dumped = EvalCase.model_validate(case).model_dump(exclude_none=True)
    assert dumped['case_id'] == 'CAL-1001' and dumped['variant_index'] == 2
    assert dumped['variant_mode'] == 'MODEL_PARAPHRASE' and dumped['split'] == 'DEV'


def test_p1_rows_do_not_gain_p2_fields():
    dumped = EvalCase.model_validate(read_jsonl(CAL / 'cases.jsonl')[0]).model_dump(exclude_none=True)
    assert 'variant_index' not in dumped and 'variant_mode' not in dumped
