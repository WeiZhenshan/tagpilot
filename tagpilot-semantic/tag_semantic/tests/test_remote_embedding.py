import hashlib
import json
import os
import sys

import httpx
import pytest

from tag_semantic.index.embedder import (
    FORBIDDEN_REMOTE_BUILD_IDS,
    MODEL_CHANGED,
    OpenAICompatibleEmbedder,
    HttpReranker,
    HashEmbedder,
    canonical_base_url,
    create_embedder,
    create_reranker,
    pack_rerank_document,
    remote_embedding_model_hash,
    remote_reranker_model_hash,
    restore_embedder,
    _http_timeout,
)
from tag_semantic.index.builder import build_index, load_index
from tag_semantic.tests.test_pipeline import _pilot_bundle


BASE = 'https://api.siliconflow.cn/v1'
DIM = 4  # short vectors in unit tests; production bge-m3 is 1024


def _vec(seed):
    return [float(seed + i) for i in range(DIM)]


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_canonical_base_url_strips_slash_and_lowercases_host():
    assert canonical_base_url('https://API.SiliconFlow.CN/v1/') == 'https://api.siliconflow.cn/v1'
    assert canonical_base_url('https://api.siliconflow.cn/v1') == 'https://api.siliconflow.cn/v1'


def test_remote_model_hash_formula_does_not_include_api_key():
    embedding_hash = remote_embedding_model_hash(BASE + '/', 'BAAI/bge-m3', 1024)
    assert embedding_hash == hashlib.sha256(b'remote|https://api.siliconflow.cn/v1|BAAI/bge-m3|1024|v1').hexdigest()
    rerank_hash = remote_reranker_model_hash('https://API.siliconflow.cn/v1', 'BAAI/bge-reranker-v2-m3')
    assert rerank_hash == hashlib.sha256(b'remote|https://api.siliconflow.cn/v1|BAAI/bge-reranker-v2-m3|v1').hexdigest()
    left = OpenAICompatibleEmbedder(BASE, 'BAAI/bge-m3', 'sk-one', dim=1024)
    right = OpenAICompatibleEmbedder(BASE, 'BAAI/bge-m3', 'sk-two', dim=1024)
    try:
        assert left.model_hash == right.model_hash == embedding_hash
        assert left.path is None and right.path is None
    finally:
        left.close()
        right.close()


def test_openai_compatible_embedder_encode_and_empty_input():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        payload = json.loads(request.content.decode())
        assert payload['model'] == 'BAAI/bge-m3'
        assert request.headers['authorization'] == 'Bearer sk-test'
        rows = [{'index': i, 'embedding': _vec(i + 1)} for i in range(len(payload['input']))]
        rows.reverse()
        return httpx.Response(200, json={'data': rows})

    embedder = OpenAICompatibleEmbedder(BASE, 'BAAI/bge-m3', 'sk-test', dim=DIM, client=_client(handler))
    assert embedder.encode([]) == []
    assert seen == []
    vectors = embedder.encode(['a', 'b'])
    assert vectors == [_vec(1), _vec(2)]
    assert seen == [BASE + '/embeddings']


def test_encode_does_not_double_v1_and_retries_then_succeeds():
    calls = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        assert str(request.url) == 'https://api.siliconflow.cn/v1/embeddings'
        if calls['n'] < 3:
            return httpx.Response(503, json={'error': 'busy'})
        return httpx.Response(200, json={'data': [{'index': 0, 'embedding': _vec(9)}]})

    embedder = OpenAICompatibleEmbedder(
        'https://api.siliconflow.cn/v1', 'BAAI/bge-m3', 'sk-test', dim=DIM,
        max_retries=3, retry_backoff_s=0, client=_client(handler))
    assert embedder.encode(['only']) == [_vec(9)]
    assert calls['n'] == 3


def test_encode_failure_after_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={'error': 'no'})

    embedder = OpenAICompatibleEmbedder(
        BASE, 'BAAI/bge-m3', 'sk-test', dim=DIM, max_retries=1, retry_backoff_s=0, client=_client(handler))
    with pytest.raises(ValueError, match=r'远程 HTTP 500 https://api.siliconflow.cn/v1/embeddings') as caught:
        embedder.encode(['x'])
    assert 'authorization' not in str(caught.value).lower()
    assert 'Bearer' not in str(caught.value)


def test_client_errors_do_not_retry_or_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr('tag_semantic.index.embedder.time.sleep', lambda seconds: slept.append(seconds))
    for status in (400, 401):
        calls = {'n': 0}

        def handler(request: httpx.Request, status=status) -> httpx.Response:
            calls['n'] += 1
            return httpx.Response(status, headers={'Authorization': 'Bearer leaked'}, json={'error': 'no'})

        embedder = OpenAICompatibleEmbedder(
            BASE, 'BAAI/bge-m3', 'sk-test', dim=DIM, max_retries=3, retry_backoff_s=1, client=_client(handler))
        with pytest.raises(ValueError, match=rf'远程 HTTP {status} {BASE}/embeddings') as caught:
            embedder.encode(['x'])
        assert calls['n'] == 1
        assert slept == []
        message = str(caught.value)
        assert 'authorization' not in message.lower()
        assert 'Bearer' not in message
        assert 'leaked' not in message


def test_http_reranker_packs_like_bge_and_sorts_by_score_then_doc_id():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured['url'] = str(request.url)
        captured['body'] = json.loads(request.content.decode())
        return httpx.Response(200, json={'results': [
            {'index': 0, 'relevance_score': 0.2},
            {'index': 1, 'relevance_score': 0.9},
            {'index': 2, 'relevance_score': 0.9},
        ]})

    reranker = HttpReranker(BASE, 'BAAI/bge-reranker-v2-m3', 'sk-test', retry_backoff_s=0, client=_client(handler))
    candidates = [
        {'doc': {'doc_id': 'tag:c', 'body_text': '正文C', 'family_key': 'fam'}},
        {'doc': {'doc_id': 'tag:b', 'body_text': '正文B', 'family_key': 'fam'}},
        {'doc': {'doc_id': 'tag:a', 'body_text': '正文A', 'family_key': 'fam'}},
    ]
    ranked = reranker.rerank('查询', candidates, k=2)
    assert captured['url'] == BASE + '/rerank'
    assert captured['body']['documents'] == [pack_rerank_document(c) for c in candidates]
    assert pack_rerank_document(candidates[0]) == '正文C\n[族] fam'
    assert [item['doc']['doc_id'] for item in ranked] == ['tag:a', 'tag:b']
    assert ranked[0]['rerank_score'] == 0.9
    assert reranker.rerank('查询', [], k=3) == []
    assert reranker.path is None


def test_rerank_truncates_candidates_to_50():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert len(body['documents']) == 50
        assert body['top_n'] == 50
        return httpx.Response(200, json={'results': [{'index': i, 'relevance_score': 1.0 - i * 0.001} for i in range(50)]})

    reranker = HttpReranker(BASE, 'BAAI/bge-reranker-v2-m3', 'sk-test', retry_backoff_s=0, client=_client(handler))
    candidates = [{'doc': {'doc_id': f'tag:{i:03d}', 'body_text': 'x', 'family_key': ''}} for i in range(80)]
    ranked = reranker.rerank('q', candidates, k=3)
    assert len(ranked) == 3
    assert ranked[0]['doc']['doc_id'] == 'tag:000'


def _rerank_candidates():
    return [
        {'doc': {'doc_id': 'tag:c', 'body_text': '正文C', 'family_key': 'fam'}},
        {'doc': {'doc_id': 'tag:b', 'body_text': '正文B', 'family_key': 'fam'}},
        {'doc': {'doc_id': 'tag:a', 'body_text': '正文A', 'family_key': 'fam'}},
    ]


def test_rerank_raises_when_index_missing_or_results_short():
    def missing_index(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'results': [
            {'index': 0, 'relevance_score': 0.1},
            {'relevance_score': 0.2},
            {'index': 2, 'relevance_score': 0.3},
        ]})

    reranker = HttpReranker(BASE, 'BAAI/bge-reranker-v2-m3', 'sk-test', retry_backoff_s=0, client=_client(missing_index))
    with pytest.raises(ValueError, match='缺少 index'):
        reranker.rerank('q', _rerank_candidates(), k=3)

    def short_results(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'results': [
            {'index': 0, 'relevance_score': 0.1},
            {'index': 2, 'relevance_score': 0.3},
        ]})

    reranker = HttpReranker(BASE, 'BAAI/bge-reranker-v2-m3', 'sk-test', retry_backoff_s=0, client=_client(short_results))
    with pytest.raises(ValueError, match='条数与输入不一致'):
        reranker.rerank('q', _rerank_candidates(), k=3)


def test_http_timeout_splits_connect_and_read():
    timeout = _http_timeout(60)
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 10.0
    assert timeout.read == 60.0
    assert timeout.write == 60.0
    short = _http_timeout(5)
    assert short.connect == 5.0 and short.read == 5.0
    embedder = OpenAICompatibleEmbedder(BASE, 'BAAI/bge-m3', 'sk-test', dim=DIM, timeout_s=60)
    try:
        assert embedder._timeout.connect == 10.0 and embedder._timeout.read == 60.0
    finally:
        embedder.close()


def test_remote_embedder_does_not_import_flagembedding():
    sys.modules.pop('FlagEmbedding', None)
    embedder = OpenAICompatibleEmbedder(BASE, 'BAAI/bge-m3', 'sk-test', dim=DIM)
    try:
        assert embedder.backend == 'remote'
        assert 'FlagEmbedding' not in sys.modules
    finally:
        embedder.close()


def test_factory_remote_and_missing_key(monkeypatch):
    monkeypatch.setenv('TAG_ALLOW_HASH_BASELINE', 'false')
    monkeypatch.setenv('TAG_EMBEDDING_BACKEND', 'local')
    with pytest.raises(ValueError, match='真实 Embedding 未配置'):
        create_embedder()
    monkeypatch.setenv('TAG_EMBEDDING_BACKEND', 'remote')
    with pytest.raises(ValueError, match='远程模式需要 API Key'):
        create_embedder()
    monkeypatch.setenv('TAG_EMBEDDING_API_KEY', 'sk-test')
    embedder = create_embedder()
    reranker = create_reranker()
    extra = None
    try:
        assert isinstance(embedder, OpenAICompatibleEmbedder)
        assert embedder.model == 'BAAI/bge-m3' and embedder.dim == 1024
        assert embedder.max_retries == 3
        assert isinstance(reranker, HttpReranker)
        assert reranker.model == 'BAAI/bge-reranker-v2-m3'
        monkeypatch.setenv('TAG_EMBEDDING_MAX_RETRIES', '7')
        extra = create_embedder()
        assert extra.max_retries == 7
        monkeypatch.setenv('TAG_RERANK_BACKEND', 'none')
        assert create_reranker() is None
    finally:
        embedder.close()
        reranker.close()
        if extra is not None:
            extra.close()


def test_factory_reads_dot_config_without_logging_keys(monkeypatch, tmp_path):
    cfg = tmp_path / 'dot-config'
    cfg.write_text('TAG_EMBEDDING_BACKEND=remote\nTAG_EMBEDDING_API_KEY=sk-from-file\nTAG_RERANK_BACKEND=none\n')
    monkeypatch.setenv('TAG_ALLOW_HASH_BASELINE', 'false')
    monkeypatch.setattr('tag_semantic.index.embedder.load_embedding_dot_config', lambda: {
        'TAG_EMBEDDING_BACKEND': 'remote',
        'TAG_EMBEDDING_API_KEY': 'sk-from-file',
        'TAG_RERANK_BACKEND': 'none',
    })
    embedder = create_embedder()
    try:
        assert isinstance(embedder, OpenAICompatibleEmbedder)
        assert 'sk-from-file' not in repr(embedder)
        assert create_reranker() is None
    finally:
        embedder.close()


def test_build_manifest_records_backend_fields(tmp_path):
    _, _, _ = _pilot_bundle(tmp_path)
    manifest = json.loads((tmp_path / 'b1' / 'manifest.json').read_text())
    assert manifest['embedding_backend'] == 'hash'
    assert manifest['embedding_model'] == 'hash-v1'
    assert manifest['embedding_base_url'] is None
    assert manifest['reranker_backend'] is None
    loaded = load_index(tmp_path / 'b1')
    assert isinstance(loaded['embedder'], HashEmbedder)


def test_load_refuses_old_local_index_under_remote(tmp_path, monkeypatch):
    _pilot_bundle(tmp_path)
    path = tmp_path / 'b1' / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['build_id'] = next(iter(FORBIDDEN_REMOTE_BUILD_IDS))
    manifest['embedding_backend'] = 'local'
    manifest['embedding_model'] = 'BAAI/bge-m3'
    manifest['embedding_path'] = '/tmp/local-bge-m3'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    monkeypatch.setenv('TAG_EMBEDDING_BACKEND', 'remote')
    monkeypatch.setenv('TAG_EMBEDDING_API_KEY', 'sk-test')
    with pytest.raises(ValueError, match=MODEL_CHANGED):
        load_index(tmp_path / 'b1')


def test_load_refuses_forbidden_build_even_if_manifest_claims_remote(tmp_path, monkeypatch):
    _pilot_bundle(tmp_path)
    path = tmp_path / 'b1' / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['build_id'] = 'bge-m3-l107-20260919-002-r3'
    manifest['embedding_backend'] = 'remote'
    manifest['embedding_model'] = 'BAAI/bge-m3'
    manifest['embedding_base_url'] = BASE
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    monkeypatch.setenv('TAG_EMBEDDING_BACKEND', 'remote')
    monkeypatch.setenv('TAG_EMBEDDING_API_KEY', 'sk-test')
    with pytest.raises(ValueError, match=MODEL_CHANGED):
        restore_embedder(manifest)


def test_hash_baseline_factory_when_allowed(monkeypatch):
    monkeypatch.setenv('TAG_ALLOW_HASH_BASELINE', 'true')
    assert isinstance(create_embedder(), HashEmbedder)
    monkeypatch.setenv('TAG_EMBEDDING_BACKEND', 'hash')
    monkeypatch.setenv('TAG_ALLOW_HASH_BASELINE', 'false')
    assert isinstance(create_embedder(), HashEmbedder)


@pytest.mark.live_embedding
@pytest.mark.skipif(os.getenv('TAG_EMBEDDING_LIVE_TEST') != '1', reason='默认跳过真实 API')
def test_live_siliconflow_optional():
    embedder = create_embedder()
    vectors = embedder.encode(['测试'])
    assert len(vectors) == 1 and len(vectors[0]) == embedder.dim
