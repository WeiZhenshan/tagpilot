"""验收器自身的反作弊/口径回归，合成测试绝不作为业务 Gold。"""
import copy
import hashlib
import json
from types import SimpleNamespace
import pytest
from tag_semantic.eval.acceptance import evaluate, load_gold, validate_cases
from tag_semantic.retrieve.service import visible_candidates


def case(identity='q1'):
    return {'id': identity, 'query': identity, 'eligible_tag_ids': [1, 2],
            'atomic_conditions': [{'accept_tag_ids': [1], 'family_key': 'F1'}]}


def service(response):
    catalog = SimpleNamespace(meta={'scope': 'PARTIAL'}, tags={
        1: {'tag_id': 1, 'family_key': 'F1', 'concept_id': 'C'},
        2: {'tag_id': 2, 'family_key': 'F2', 'concept_id': 'C'}})
    return SimpleNamespace(catalog=catalog, retrieve=lambda *args: copy.deepcopy(response))


def hit(tid):
    return {'doc': {'doc_type': 'tag', 'doc_id': 'tag:' + str(tid), 'tag_id': tid}}


MANIFEST = {'build_id': 'test', 'snapshot_id': 'test', 'retrieval_config_hash': 'test', 'embedding_model': 'hash-v1'}


def response():
    return {'candidates': [hit(1)], 'recall_candidates': [hit(1)], 'decision': 'CANDIDATES_ONLY', 'auto_execute': False}


@pytest.mark.parametrize('change', [
    {'atomic_conditions': []}, {'query': ''}, {'eligible_tag_ids': ['1']},
    {'atomic_conditions': [{'accept_tag_ids': []}]},
    {'atomic_conditions': [{'accept_tag_ids': [3]}]},
    {'expected_codes': [1], 'expected_code_tag_id': 1},
    {'must_clarify': 'false'}, {'must_clarify': True, 'inexpressible': True}])
def test_invalid_gold_is_rejected(change):
    row = case(); row.update(change)
    with pytest.raises(ValueError):
        validate_cases([row])


def test_600_empty_answers_cannot_pass(tmp_path):
    rows = [dict(case(str(i)), atomic_conditions=[]) for i in range(600)]
    path = tmp_path / 'gold.json'
    path.write_text(json.dumps({'status': 'SEALED', 'sealed': True, 'queries': rows}))
    with pytest.raises(ValueError, match='非空'):
        load_gold(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_duplicate_questions_and_missing_provenance_rejected(tmp_path):
    rows = [case(str(i)) for i in range(600)]
    rows[-1]['query'] = rows[0]['query']
    with pytest.raises(ValueError, match='重复表达'):
        validate_cases(rows, sealed=True)
    rows[-1]['query'] = 'last'
    path = tmp_path / 'gold.json'
    path.write_text(json.dumps({'status': 'SEALED', 'sealed': True, 'queries': rows}))
    with pytest.raises(ValueError, match='证据'):
        load_gold(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_atomic_denominator_and_required_fields():
    row = case()
    row['atomic_conditions'].append({'accept_tag_ids': [2], 'family_key': 'F2'})
    report = evaluate(service(response()), [row], MANIFEST)
    assert report['metrics']['hit_at_20']['rate'] == .5
    assert report['metrics']['complete_conditions_at_20']['rate'] == 0
    row['atomic_conditions'] = [{'accept_tag_ids': [1], 'required_tag_ids': [1, 2]}]
    assert evaluate(service(response()), [row], MANIFEST)['metrics']['hit_at_20']['rate'] == 0


def test_recall_and_rerank_are_separate():
    output = response(); output['candidates'] = [hit(2)]
    report = evaluate(service(output), [case()], MANIFEST)
    assert report['metrics']['hit_at_20']['rate'] == 1
    assert report['metrics']['final_hit_at_10']['rate'] == 0


def test_clarification_excluded_from_answerable_denominator():
    row = dict(case(), must_clarify=True)
    output = response(); output['decision'] = 'CLARIFY'
    report = evaluate(service(output), [row], MANIFEST)
    assert report['metrics']['hit_at_20']['denominator'] == 0
    assert report['metrics']['clarification_correct']['rate'] == 1
    assert not report['acceptance_passed']


def test_wrong_code_extra_code_and_wrong_owner_fail():
    row = dict(case(), expected_codes=['01', '02'], expected_code_tag_id=1)
    for codes, tid in [(['1', '02'], 1), (['01', '02', '03'], 1), (['01', '02'], 2)]:
        output = dict(response(), code_selection={'expressible': True, 'codes': codes}, family={'selected': {'tag_id': tid}})
        assert evaluate(service(output), [row], MANIFEST)['metrics']['code_set_exact']['rate'] == 0


def test_raw_unauthorized_and_auto_execution_not_hidden_by_projection():
    output = response(); output['candidates'].append(hit(99)); output['auto_execute'] = True
    report = evaluate(service(output), [case()], MANIFEST)
    assert report['metrics']['unauthorized_references']['numerator'] == 1
    assert report['metrics']['incorrect_auto_execution']['numerator'] == 1
    assert not report['acceptance_passed']


def test_hash_pilot_with_600_correct_answers_still_fails():
    report = evaluate(service(response()), [case(str(i)) for i in range(600)], MANIFEST, scope='SEALED')
    assert report['metrics']['hit_at_20']['rate'] == 1
    assert not report['gates']['full_969_snapshot']
    assert not report['gates']['real_embedding']
    assert not report['gates']['real_reranker']
    assert not report['acceptance_passed']
    assert 'query' not in report['traces'][0]


def test_concept_expansion_matches_http_qualification_and_topk():
    catalog = service(response()).catalog
    concept = {'doc': {'doc_type': 'concept', 'concept_id': 'C'}}
    assert [r['tag_id'] for r in visible_candidates([concept], catalog, {2}, 20)] == [2]
    assert len(visible_candidates([concept, hit(1)], catalog, {1, 2}, 1)) == 1
