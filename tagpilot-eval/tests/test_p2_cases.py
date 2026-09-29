"""P2 物化：REVISE 只许改表达，QUARANTINE 从正式集剔除但必须留档。"""
import json
import shutil
from pathlib import Path

import pytest

from tagpilot_eval.io import read_jsonl
from tagpilot_eval.p2_cases import case_fields, materialize

PACKAGE = Path(__file__).resolve().parents[1]
SPLIT = PACKAGE / 'data/p2-split-v1'


def _copy_package(tmp_path):
    target = tmp_path / 'cases'
    shutil.copytree(SPLIT, target)
    return target


def _write_reviews(tmp_path, cases, overrides):
    rows = []
    for case in cases:
        row = {'case_id': case['case_id'], 'reviewer': 'test', 'reviewed_at': '2026-09-27',
               'verdict': 'ACCEPT', 'reason': 'ok', 'faithful': True, 'natural': True}
        row.update(overrides.get(case['case_id'], {}))
        rows.append(row)
    (tmp_path / 'reviews.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))


def test_case_fields_strip_intermediate_diagnostics():
    assert case_fields({'case_id': 'CAL-1001', 'back_translation': 'PASS', 'requirement': 'x'}) == \
        {'case_id': 'CAL-1001', 'requirement': 'x'}


def test_materialize_keeps_revises_and_quarantines(tmp_path):
    package = _copy_package(tmp_path)
    cases = read_jsonl(SPLIT / 'cases.jsonl')
    revised_id, quarantined_id = cases[0]['case_id'], cases[1]['case_id']
    _write_reviews(tmp_path, cases, {
        revised_id: {'verdict': 'REVISE', 'patch': {'requirement': '改写后的原话。'}},
        quarantined_id: {'verdict': 'QUARANTINE', 'reason': '严重错误'},
    })
    result = materialize(package, tmp_path / 'reviews.jsonl', tmp_path / 'out',
                         {'authorized_by': 'USER'})
    assert result['cases'] == len(cases) - 1
    assert result['revised'] == 1 and result['quarantined'] == 1
    kept = {case['case_id']: case for case in read_jsonl(tmp_path / 'out/cases.jsonl')}
    assert quarantined_id not in kept
    assert kept[revised_id]['requirement'] == '改写后的原话。'
    manifest = json.loads((tmp_path / 'out/manifest.json').read_text())
    assert manifest['quarantined_cases'][0]['case_id'] == quarantined_id
    assert manifest['independent_model_review'] == 'COMPLETED'


def test_materialize_rejects_revise_beyond_expression(tmp_path):
    package = _copy_package(tmp_path)
    cases = read_jsonl(SPLIT / 'cases.jsonl')
    _write_reviews(tmp_path, cases, {
        cases[0]['case_id']: {'verdict': 'REVISE', 'patch': {'target_tag_ids': [1]}},
    })
    with pytest.raises(ValueError, match='超出表达范围'):
        materialize(package, tmp_path / 'reviews.jsonl', tmp_path / 'out', {})


def test_revise_without_patch_is_flagged_not_silently_accepted(tmp_path):
    """回归：复核员要求改但没给具体改法时，不能当作已通过悄悄放行。"""
    package = _copy_package(tmp_path)
    cases = read_jsonl(SPLIT / 'cases.jsonl')
    _write_reviews(tmp_path, cases, {cases[0]['case_id']: {'verdict': 'REVISE'}})
    result = materialize(package, tmp_path / 'reviews.jsonl', tmp_path / 'out', {})
    assert result['flagged_without_patch'] == 1 and result['revised'] == 0
    assert result['cases'] == len(cases)
    manifest = json.loads((tmp_path / 'out/manifest.json').read_text())
    assert manifest['flagged_without_patch'][0]['case_id'] == cases[0]['case_id']


def test_materialize_requires_full_review_coverage(tmp_path):
    package = _copy_package(tmp_path)
    cases = read_jsonl(SPLIT / 'cases.jsonl')[:10]
    _write_reviews(tmp_path, cases, {})
    with pytest.raises(ValueError, match='未覆盖全部案例'):
        materialize(package, tmp_path / 'reviews.jsonl', tmp_path / 'out', {})
