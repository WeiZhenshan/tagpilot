import pytest


_ISOLATED_ENV = (
    'TAG_EMBEDDING_BACKEND', 'TAG_RERANK_BACKEND',
    'TAG_EMBEDDING_API_KEY', 'TAG_RERANK_API_KEY', 'SILICONFLOW_API_KEY',
    'TAG_EMBEDDING_BASE_URL', 'TAG_EMBEDDING_MODEL', 'TAG_EMBEDDING_DIM',
    'TAG_RERANK_BASE_URL', 'TAG_RERANK_MODEL',
    'TAG_EMBEDDING_PATH', 'TAG_RERANKER_PATH',
    'TAG_EMBEDDING_TIMEOUT_S', 'TAG_EMBEDDING_BATCH_SIZE',
    'TAG_EMBEDDING_CONFIG',
)


@pytest.fixture(autouse=True)
def isolate_embedding_runtime(monkeypatch, request):
    """单元测试不得读取本机 .tag-embedding-config 或真实密钥。"""
    if request.node.get_closest_marker('live_embedding'):
        return
    for key in _ISOLATED_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('TAG_ALLOW_HASH_BASELINE', 'true')
    monkeypatch.setattr('tag_semantic.index.embedder.load_embedding_dot_config', lambda: {})
