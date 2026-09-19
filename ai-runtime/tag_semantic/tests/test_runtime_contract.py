import copy
import json
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tag_semantic.server import create_app
from tag_semantic.index import builder
from tag_semantic.index.builder import build_index, load_index
from tag_semantic.index.local_store import LocalStore
from tag_semantic.snapshot.canonicalize import content_hash
from tag_semantic.snapshot.loader import load_catalog
from tag_semantic.snapshot.schema import validate_catalog
from tag_semantic.tests.test_pipeline import _pilot_bundle


def test_http_pinned_build_auth_empty_partial_and_library(tmp_path):
    _, catalog, _ = _pilot_bundle(tmp_path)
    app = create_app(tmp_path, tmp_path, 'test-service-token')
    client = TestClient(app)
    request = {'requirement': '女性', 'library_id': 107, 'build_id': 'b1', 'eligible_tag_ids': []}
    assert client.post('/retrieve', json=request).status_code == 401
    headers = {'Authorization': 'Bearer test-service-token'}
    empty = client.post('/retrieve', json=request, headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json()['candidates'] == []
    request['eligible_tag_ids'] = [526]
    result = client.post('/retrieve', json=request, headers=headers).json()
    assert result['build_id'] == 'b1'
    assert result['store_type'] == 'LOCAL'
    assert {c['tag_id'] for c in result['candidates']} <= {526}
    assert all('doc' not in c and 'dense' not in c for c in result['candidates'])
    request['library_id'] = 108
    assert client.post('/retrieve', json=request, headers=headers).status_code == 409
    request['library_id'] = 107
    del request['eligible_tag_ids']
    assert client.post('/retrieve', json=request, headers=headers).status_code == 422
    request['eligible_tag_ids'] = []
    request['build_id'] = 'missing'
    assert client.post('/retrieve', json=request, headers=headers).status_code == 503
    assert client.get('/stats?build_id=../../escape', headers=headers).status_code == 422


def test_artifacts_immutable_reload_and_corruption(tmp_path):
    _, catalog, _ = _pilot_bundle(tmp_path)
    loaded = load_index(tmp_path / 'b1')
    assert loaded['manifest']['content_hash'] == content_hash(catalog.rows)
    with pytest.raises(FileExistsError):
        build_index(catalog, tmp_path / 'b1', 'b1')
    with pytest.raises(ValueError):
        build_index(catalog, tmp_path / 'unsupported', 'unsupported', 'OTHER')
    (tmp_path / 'b1' / 'emb.npy').write_bytes(b'broken')
    with pytest.raises(ValueError, match='校验失败'):
        load_index(tmp_path / 'b1')


def test_old_relative_model_path_resolves_from_runtime_root(tmp_path, monkeypatch):
    runtime_root = tmp_path / 'ai-runtime'
    module_file = runtime_root / 'tag_semantic' / 'index' / 'builder.py'
    model = runtime_root / 'out' / 'models' / 'bge-m3'
    model.mkdir(parents=True)
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(builder, '__file__', str(module_file))
    assert builder._resolved_model_path('out/models/bge-m3') == str(model.resolve())


def test_filter_before_topk_prevents_starvation():
    docs = [{'doc_id': f'tag:{i}', 'doc_type': 'tag', 'tag_id': i, 'name_text': '客户 客户' if i < 100 else '客户', 'body_text': '客户'} for i in range(101)]
    store = LocalStore()
    store.build(docs)
    hits = store.search('bm25_name', '客户', {'eligible_tag_ids': {100}}, 1)
    assert hits[0]['doc']['tag_id'] == 100


def test_schema_rejects_dangling_duplicate_alias_and_inconsistent_pair(tmp_path):
    _, catalog, _ = _pilot_bundle(tmp_path)
    rows = copy.deepcopy(catalog.rows)
    rows.append(copy.deepcopy(next(r for r in rows if r['kind'] == 'tag')))
    with pytest.raises(ValueError, match='重复行'):
        validate_catalog(rows)
    rows = copy.deepcopy(catalog.rows)
    tag = next(r for r in rows if r['kind'] == 'tag')
    tag['concept_id'] = 'missing'
    with pytest.raises(ValueError, match='悬空概念'):
        validate_catalog(rows)
    rows = copy.deepcopy(catalog.rows)
    tag = next(r for r in rows if r['kind'] == 'tag')
    tag['aliases'] = [{'target_type': 'TAG', 'target_id': '9999999', 'review_status': 'REVIEWED'}]
    with pytest.raises(ValueError, match='悬空目标'):
        validate_catalog(rows)


def test_nested_business_status_affects_hash():
    rows = [{'kind': 'meta', 'snapshot_id': 'first'}, {'kind': 'tag', 'tag_id': 1, 'status': '2', 'nested': {'snapshot_id': 'business', 'status': 'ON'}}]
    original = content_hash(rows)
    rows[0]['snapshot_id'] = 'second'
    assert content_hash(rows) == original
    rows[1]['status'] = '0'
    assert content_hash(rows) != original
    rows[1]['status'] = '2'
    rows[1]['nested']['snapshot_id'] = 'changed'
    assert content_hash(rows) != original


def test_java_generated_snapshot_contract():
    import os
    path = os.getenv('TAG_JAVA_CONTRACT')
    if not path:
        pytest.skip('通过验证脚本提供 Maven 实际导出的文件')
    catalog = load_catalog(Path(path))
    assert catalog.tags and catalog.concepts and catalog.code_values and catalog.terms and catalog.aliases
    assert catalog.code_values[0]['code'] == '01'
    assert catalog.meta['content_hash'] == content_hash(catalog.rows)


def test_interval_exact_union_gaps_leading_zero_and_null():
    from tag_semantic.retrieve.family import interval_covers
    rows = [{'code': '01', 'lower_bound': '1000000', 'upper_bound': '3000000', 'lower_inclusive': 1, 'upper_inclusive': 0},
            {'code': '02', 'lower_bound': '3000000', 'upper_bound': None, 'lower_inclusive': 1, 'upper_inclusive': 0}]
    assert interval_covers(rows, 1000000, None, '>=') == {'expressible': True, 'codes': ['01', '02']}
    assert not interval_covers(rows, 1000000, None, '>')['expressible']
    assert not interval_covers(rows, 1200000, None, '>=')['expressible']
    rows[1]['lower_bound'] = '4000000'
    assert not interval_covers(rows, 1000000, None, '>=')['expressible']


def test_low_sample_profiles_and_feedback_isolation():
    from tag_semantic.profile.aggregator import aggregate_profile
    from tag_semantic.bootstrap.feedback_mining import mine_feedback
    tag = {'tag_id': 1, 'semantic_type': 'ENUM_NOMINAL', 'sensitivity': 'LOW', 'reviewed_codes': ['01']}
    result = aggregate_profile(tag, ['01'] * 25 + ['rare'] * 3, '2026-09-19')
    assert result['top_values'] == [{'code': '01', 'count': 25}]
    assert aggregate_profile(tag, ['01'] * 3, '2026-09-19')['top_values'] is None
    feedback = [{'trace_id': str(i), 'user_id': 1, 'query_hash': 'hash', 'final_tag_id': 1, 'action': 'ACCEPT', 'sanitized_text': '女性', 'text_review_status': 'REVIEWED'} for i in range(5)]
    assert mine_feedback(feedback, {'hash'}) == []
    assert mine_feedback(feedback, set())[0]['review_status'] == 'DRAFT'
    assert mine_feedback(feedback[:1] * 5, set()) == []


def test_sealed_placeholder_cannot_pass_acceptance(tmp_path):
    from tag_semantic.eval.acceptance import load_gold
    path = tmp_path / 'sealed.json'
    path.write_text(json.dumps({'sealed': True, 'status': 'PLACEHOLDER', 'queries': []}))
    with pytest.raises(ValueError, match='600'):
        load_gold(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_cleanup_invalidates_other_worker_cache_and_backup_rebuild(tmp_path):
    from tag_semantic.index.maintenance import backup, rebuild
    _pilot_bundle(tmp_path)
    headers = {'Authorization': 'Bearer test'}
    first = TestClient(create_app(tmp_path, tmp_path, 'test'))
    second = TestClient(create_app(tmp_path, tmp_path, 'test'))
    assert second.get('/stats?build_id=b1', headers=headers).status_code == 200
    result = backup(tmp_path / 'b1', tmp_path / 'archive.tar.gz')
    assert result['scope'] == 'ARTIFACTS_ONLY'
    with pytest.raises(FileExistsError):
        backup(tmp_path / 'b1', tmp_path / 'archive.tar.gz')
    request = {'library_id': 107, 'snapshot_id': 'L107-TEST-001', 'store_type': 'LOCAL', 'build_id': 'b1'}
    assert first.post('/drop', json=request, headers=headers).json()['status'] == 'PURGED'
    assert second.get('/stats?build_id=b1', headers=headers).status_code == 503
    assert first.post('/drop', json=request, headers=headers).status_code == 200
    assert rebuild(tmp_path / 'b1', tmp_path / 'recovered', 'recovered')['reconciled']


def test_duplicate_alias_evidence_does_not_inflate_rrf():
    from tag_semantic.retrieve.fusion import rrf
    hit = {'doc': {'doc_id': 'tag:1'}, 'rank': 1, 'channel': 'alias'}
    assert rrf([[hit, hit]]) == rrf([[hit]])


def test_deactivate_only_removes_alias_owned_by_this_build():
    from unittest.mock import Mock
    from tag_semantic.index.milvus_store import MilvusStore
    store = MilvusStore(client=Mock(), library_id=107, collection='isolated_build')
    store.client.list_aliases.return_value = {'aliases': ['tag_docs_active_l107']}
    assert store.deactivate() is True
    store.client.drop_alias.assert_called_once_with(alias='tag_docs_active_l107')
    store.client.reset_mock()
    store.client.list_aliases.return_value = {'aliases': []}
    assert store.deactivate() is False
    store.client.drop_alias.assert_not_called()


def test_deactivate_endpoint_requires_matching_identity(tmp_path):
    _pilot_bundle(tmp_path)
    client = TestClient(create_app(tmp_path, tmp_path, 'test'))
    body = {'library_id': 107, 'snapshot_id': 'L107-TEST-001', 'store_type': 'LOCAL', 'build_id': 'b1'}
    assert client.post('/deactivate', json=body).status_code == 401
    headers = {'Authorization': 'Bearer test'}
    assert client.post('/deactivate', json=body, headers=headers).json()['alias_removed'] is False
    body['library_id'] = 108
    assert client.post('/deactivate', json=body, headers=headers).status_code == 409


def test_single_member_family_cannot_bypass_explicit_time():
    from tag_semantic.retrieve.family import resolve_family
    member = {'tag_id': 1, 'caliber_struct': {'time_anchor_type': 'WINDOW', 'time_window_value': 7, 'time_window_unit': 'DAY'}}
    assert resolve_family([member], {'time_anchor_type': 'WINDOW', 'time_window_value': 60, 'time_window_unit': 'DAY'})['status'] == 'clarify_time'
    assert resolve_family([member], {'time_anchor_type': 'WINDOW', 'time_window_value': 7, 'time_window_unit': 'DAY'})['status'] == 'selected'
    assert resolve_family([member], {'time_anchor_type': 'NONE'})['status'] == 'selected'
