import pytest


_ISOLATED_ENV = (
    'TAG_EMBEDDING_BACKEND', 'TAG_RERANK_BACKEND',
    'TAG_EMBEDDING_API_KEY', 'TAG_RERANK_API_KEY', 'SILICONFLOW_API_KEY',
    'TAG_EMBEDDING_BASE_URL', 'TAG_EMBEDDING_MODEL', 'TAG_EMBEDDING_DIM',
    'TAG_RERANK_BASE_URL', 'TAG_RERANK_MODEL',
    'TAG_EMBEDDING_PATH', 'TAG_RERANKER_PATH',
    'TAG_EMBEDDING_TIMEOUT_S', 'TAG_EMBEDDING_BATCH_SIZE', 'TAG_EMBEDDING_MAX_RETRIES',
    'TAG_EMBEDDING_CONFIG', 'TAG_ALLOW_HASH_BASELINE',
)


@pytest.fixture(autouse=True)
def isolate_embedding_runtime(monkeypatch, request):
    """隔离本机 .tag-embedding-config 与密钥；不把 TAG_ALLOW_HASH_BASELINE 设为全局 true。"""
    if request.node.get_closest_marker('live_embedding'):
        return
    for key in _ISOLATED_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr('tag_semantic.index.embedder.load_embedding_dot_config', lambda: {})
