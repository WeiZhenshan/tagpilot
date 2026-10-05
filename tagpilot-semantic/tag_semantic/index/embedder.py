"""确定性哈希向量，可替换为本地 BGE-M3 或 SiliconFlow 远程 Embedding。"""

from __future__ import annotations

import hashlib
import math
import os
import time
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

import httpx

_model_load_lock = RLock()

# 远程 model_hash 使用稳定 api_version=v1；变更该串必须新建 build。
REMOTE_API_VERSION = 'v1'
DEFAULT_EMBEDDING_BASE_URL = 'https://api.siliconflow.cn/v1'
DEFAULT_EMBEDDING_MODEL = 'BAAI/bge-m3'
DEFAULT_EMBEDDING_DIM = 1024
DEFAULT_RERANK_MODEL = 'BAAI/bge-reranker-v2-m3'
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_BATCH_SIZE = 32
DEFAULT_MAX_RETRIES = 3
CONFIG_FILENAME = '.tag-embedding-config'
FORBIDDEN_REMOTE_BUILD_IDS = frozenset({'bge-m3-l107-20260919-002-r3'})
MODEL_CHANGED = '模型已变化，必须新建 build'
MISSING_REAL_EMBEDDING = '真实 Embedding 未配置；基线须显式开启 TAG_ALLOW_HASH_BASELINE'
MISSING_REMOTE_KEY = '真实 Embedding 未配置；远程模式需要 API Key'
MISSING_REMOTE_RERANK_KEY = '真实 Rerank 未配置；远程模式需要 API Key'


@lru_cache(maxsize=2)
def _shared_embedding(path, fingerprint):
    from FlagEmbedding import BGEM3FlagModel
    return BGEM3FlagModel(path,use_fp16=False,devices=['cpu']),RLock()

@lru_cache(maxsize=2)
def _shared_reranker(path, fingerprint):
    from FlagEmbedding import FlagReranker
    return FlagReranker(path,use_fp16=False,devices=['cpu']),RLock()


class HashEmbedder:
    backend = 'hash'
    path = None

    def __init__(self, dim: int = 64, model: str = "hash-v1") -> None:
        self.dim = dim
        self.model = model
        self.model_hash = hashlib.sha256(f"{model}:{dim}".encode("utf-8")).hexdigest()

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = list(text or "")
        for i, ch in enumerate(tokens):
            digest = hashlib.sha256(f"{ch}:{i}".encode("utf-8")).digest()
            idx = digest[0] % self.dim
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def model_directory_hash(path):
    """模型使用已下载目录；权重/配置逐文件哈希，避免仅记录可漂移名称。"""
    root = Path(path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('模型必须是本地目录')
    digest = hashlib.sha256()
    files = sorted(p for p in root.rglob('*') if p.is_file() and not any(part in {'.cache', '.git'} for part in p.relative_to(root).parts))
    if not files:
        raise ValueError('模型目录为空')
    for file in files:
        digest.update(str(file.relative_to(root)).encode())
        with file.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
    return digest.hexdigest()


def pack_rerank_document(candidate: dict) -> str:
    """与 BGEReranker 相同的文档拼装：正文截断 + 族键。"""
    doc = candidate['doc']
    return doc.get('body_text', '')[:2000] + '\n[族] ' + str(doc.get('family_key') or '')


class BGEEmbedder:
    backend = 'local'
    model = 'BAAI/bge-m3'
    dim = 1024

    def __init__(self, path: str):
        self.model_hash = model_directory_hash(path)
        self.path = path
        from pathlib import Path as _Path
        with _model_load_lock:self._model,self._inference_lock=_shared_embedding(str(_Path(path).resolve()),self.model_hash)

    def encode(self, texts):
        with self._inference_lock:
            return self._model.encode(list(texts), batch_size=8, max_length=2048)['dense_vecs'].tolist()


class BGEReranker:
    backend = 'local'
    model = 'BAAI/bge-reranker-v2-m3'

    def __init__(self, path: str):
        self.model_hash = model_directory_hash(path)
        self.path = path
        from pathlib import Path as _Path
        with _model_load_lock:self._model,self._inference_lock=_shared_reranker(str(_Path(path).resolve()),self.model_hash)

    def rerank(self, query, candidates, k=10, **options):
        return self.rerank_batch([(query,candidates)],k,**options)[0]

    def rerank_batch(self, batches, k=10, max_length=None, batch_size=None):
        pairs=[[query,pack_rerank_document(c)]
               for query,candidates in batches for c in candidates[:50]]
        if not pairs:return [[] for _ in batches]
        options={key:value for key,value in [('max_length',max_length),('batch_size',batch_size)] if value is not None}
        with self._inference_lock:scores=self._model.compute_score(pairs,normalize=True,**options)
        if isinstance(scores,(int,float)):scores=[scores]
        offset=0;results=[]
        for query,candidates in batches:
            candidates=candidates[:50]
            items=[dict(c,rerank_score=float(score)) for c,score in zip(candidates,scores[offset:offset+len(candidates)])]
            results.append(sorted(items,key=lambda x:(-x['rerank_score'],x['doc']['doc_id']))[:k]);offset+=len(candidates)
        return results


def canonical_base_url(url: str) -> str:
    """去尾斜杠；scheme/host 小写。不把 API Key 编入 URL 或 hash。"""
    parsed = urlsplit((url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return (url or '').strip().rstrip('/')
    path = parsed.path.rstrip('/')
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, '', ''))


def remote_embedding_model_hash(base_url: str, model: str, dim: int) -> str:
    return hashlib.sha256(
        f"remote|{canonical_base_url(base_url)}|{model}|{int(dim)}|{REMOTE_API_VERSION}".encode('utf-8')
    ).hexdigest()


def remote_reranker_model_hash(base_url: str, model: str) -> str:
    return hashlib.sha256(
        f"remote|{canonical_base_url(base_url)}|{model}|{REMOTE_API_VERSION}".encode('utf-8')
    ).hexdigest()


def _join_endpoint(base_url: str, name: str) -> str:
    return (base_url or '').strip().rstrip('/') + '/' + name


def _post_json(client: httpx.Client, url: str, payload: dict, api_key: str,
               timeout_s: float, max_retries: int, retry_backoff_s: float) -> dict:
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    last_error: Exception | None = None
    attempts = max(0, int(max_retries)) + 1
    for attempt in range(attempts):
        try:
            response = client.post(url, json=payload, headers=headers, timeout=timeout_s)
            if response.status_code in (408, 429, 500, 502, 503, 504) and attempt + 1 < attempts:
                last_error = httpx.HTTPStatusError(
                    f'HTTP {response.status_code}', request=response.request, response=response)
                time.sleep(retry_backoff_s * (attempt + 1))
                continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('远程接口返回格式错误')
            return data
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise
            time.sleep(retry_backoff_s * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError('远程请求失败')


class OpenAICompatibleEmbedder:
    backend = 'remote'
    path = None

    def __init__(self, base_url: str, model: str, api_key: str, dim: int = DEFAULT_EMBEDDING_DIM,
                 timeout_s: float = DEFAULT_TIMEOUT_S, batch_size: int = DEFAULT_BATCH_SIZE,
                 max_retries: int = DEFAULT_MAX_RETRIES, retry_backoff_s: float = 0.5,
                 client: httpx.Client | None = None):
        if not api_key:
            raise ValueError(MISSING_REMOTE_KEY)
        self.base_url = (base_url or DEFAULT_EMBEDDING_BASE_URL).strip().rstrip('/')
        self.model = model
        self.dim = int(dim)
        self.timeout_s = float(timeout_s)
        self.batch_size = max(1, int(batch_size))
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_s = float(retry_backoff_s)
        self.model_hash = remote_embedding_model_hash(self.base_url, self.model, self.dim)
        self._api_key = api_key
        self._client = client or httpx.Client()
        self._owns_client = client is None

    def __repr__(self) -> str:
        return f'OpenAICompatibleEmbedder(model={self.model!r}, dim={self.dim}, base_url={self.base_url!r})'

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(items), self.batch_size):
            vectors.extend(self._encode_batch(items[start:start + self.batch_size]))
        return vectors

    def _encode_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {'model': self.model, 'input': texts}
        data = _post_json(self._client, _join_endpoint(self.base_url, 'embeddings'), payload,
                          self._api_key, self.timeout_s, self.max_retries, self.retry_backoff_s)
        rows = list(data.get('data') or [])
        rows.sort(key=lambda row: int(row.get('index', 0)))
        if len(rows) != len(texts):
            raise ValueError('远程 Embedding 返回条数与输入不一致')
        vectors = []
        for row in rows:
            embedding = row.get('embedding')
            if not isinstance(embedding, list) or len(embedding) != self.dim:
                raise ValueError('远程 Embedding 维度与配置不一致')
            vectors.append([float(x) for x in embedding])
        return vectors


class HttpReranker:
    backend = 'remote'
    path = None

    def __init__(self, base_url: str, model: str, api_key: str,
                 timeout_s: float = DEFAULT_TIMEOUT_S, max_retries: int = DEFAULT_MAX_RETRIES,
                 retry_backoff_s: float = 0.5, client: httpx.Client | None = None):
        if not api_key:
            raise ValueError(MISSING_REMOTE_RERANK_KEY)
        self.base_url = (base_url or DEFAULT_EMBEDDING_BASE_URL).strip().rstrip('/')
        self.model = model
        self.timeout_s = float(timeout_s)
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_s = float(retry_backoff_s)
        self.model_hash = remote_reranker_model_hash(self.base_url, self.model)
        self._api_key = api_key
        self._client = client or httpx.Client()
        self._owns_client = client is None

    def __repr__(self) -> str:
        return f'HttpReranker(model={self.model!r}, base_url={self.base_url!r})'

    def rerank(self, query, candidates, k=10, **options):
        return self.rerank_batch([(query, candidates)], k, **options)[0]

    def rerank_batch(self, batches, k=10, max_length=None, batch_size=None):
        del max_length, batch_size
        return [self._rerank_one(query, candidates, k) for query, candidates in batches]

    def _rerank_one(self, query, candidates, k):
        candidates = list(candidates or [])[:50]
        if not candidates:
            return []
        documents = [pack_rerank_document(item) for item in candidates]
        payload = {'model': self.model, 'query': query, 'documents': documents, 'top_n': len(documents)}
        data = _post_json(self._client, _join_endpoint(self.base_url, 'rerank'), payload,
                          self._api_key, self.timeout_s, self.max_retries, self.retry_backoff_s)
        scores = {}
        for row in data.get('results') or []:
            try:
                index = int(row.get('index'))
            except (TypeError, ValueError):
                continue
            scores[index] = float(row.get('relevance_score') or 0.0)
        items = [dict(item, rerank_score=float(scores.get(i, 0.0))) for i, item in enumerate(candidates)]
        return sorted(items, key=lambda x: (-x['rerank_score'], x['doc']['doc_id']))[:k]


def load_embedding_dot_config() -> dict[str, str]:
    """读取仓库根 `.tag-embedding-config`（KEY=VAL）。调用方不得回显密钥。"""
    override = os.getenv('TAG_EMBEDDING_CONFIG')
    paths = []
    if override:
        paths.append(Path(override))
    else:
        here = Path(__file__).resolve()
        cwd = Path.cwd()
        ordered = [cwd, *cwd.parents, *here.parents]
        seen: set[Path] = set()
        for root in ordered:
            if root in seen:
                continue
            seen.add(root)
            paths.append(root / CONFIG_FILENAME)
    for path in paths:
        if path.is_file():
            return _parse_dot_config(path)
    return {}


def _parse_dot_config(path: Path) -> dict[str, str]:
    config: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        config[key.strip()] = value.strip().strip('"').strip("'")
    return config


def _cfg(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value not in (None, ''):
        return value
    loaded = load_embedding_dot_config().get(key)
    if loaded not in (None, ''):
        return loaded
    return default


def _first_cfg(*keys: str) -> str | None:
    for key in keys:
        value = _cfg(key)
        if value:
            return value
    return None


def _create_remote_embedder() -> OpenAICompatibleEmbedder:
    key = _first_cfg('TAG_EMBEDDING_API_KEY', 'SILICONFLOW_API_KEY')
    if not key:
        raise ValueError(MISSING_REMOTE_KEY)
    return OpenAICompatibleEmbedder(
        base_url=_cfg('TAG_EMBEDDING_BASE_URL', DEFAULT_EMBEDDING_BASE_URL) or DEFAULT_EMBEDDING_BASE_URL,
        model=_cfg('TAG_EMBEDDING_MODEL', DEFAULT_EMBEDDING_MODEL) or DEFAULT_EMBEDDING_MODEL,
        api_key=key,
        dim=int(_cfg('TAG_EMBEDDING_DIM', str(DEFAULT_EMBEDDING_DIM)) or DEFAULT_EMBEDDING_DIM),
        timeout_s=float(_cfg('TAG_EMBEDDING_TIMEOUT_S', str(DEFAULT_TIMEOUT_S)) or DEFAULT_TIMEOUT_S),
        batch_size=int(_cfg('TAG_EMBEDDING_BATCH_SIZE', str(DEFAULT_BATCH_SIZE)) or DEFAULT_BATCH_SIZE),
    )


def _create_remote_reranker() -> HttpReranker:
    key = _first_cfg('TAG_RERANK_API_KEY', 'TAG_EMBEDDING_API_KEY', 'SILICONFLOW_API_KEY')
    if not key:
        raise ValueError(MISSING_REMOTE_RERANK_KEY)
    base = _cfg('TAG_RERANK_BASE_URL') or _cfg('TAG_EMBEDDING_BASE_URL', DEFAULT_EMBEDDING_BASE_URL) or DEFAULT_EMBEDDING_BASE_URL
    return HttpReranker(
        base_url=base,
        model=_cfg('TAG_RERANK_MODEL', DEFAULT_RERANK_MODEL) or DEFAULT_RERANK_MODEL,
        api_key=key,
        timeout_s=float(_cfg('TAG_EMBEDDING_TIMEOUT_S', str(DEFAULT_TIMEOUT_S)) or DEFAULT_TIMEOUT_S),
    )


def create_embedder() -> HashEmbedder | BGEEmbedder | OpenAICompatibleEmbedder:
    """按 TAG_EMBEDDING_BACKEND 选择实现。unset 时保持 local（需路径或 TAG_ALLOW_HASH_BASELINE）。
    remote 的默认 URL/模型/维度为 SiliconFlow BAAI/bge-m3 dim=1024；缺 Key 直接失败。"""
    backend = (_cfg('TAG_EMBEDDING_BACKEND', 'local') or 'local').strip().lower()
    if backend == 'remote':
        return _create_remote_embedder()
    if backend == 'hash':
        return HashEmbedder()
    if backend == 'local':
        path = _cfg('TAG_EMBEDDING_PATH')
        if path:
            return BGEEmbedder(path)
        if (_cfg('TAG_ALLOW_HASH_BASELINE') or '').strip().lower() == 'true':
            return HashEmbedder()
        raise ValueError(MISSING_REAL_EMBEDDING)
    raise ValueError(f'不支持的 TAG_EMBEDDING_BACKEND: {backend}')


def create_reranker() -> BGEReranker | HttpReranker | None:
    backend = (_cfg('TAG_RERANK_BACKEND', 'local') or 'local').strip().lower()
    if backend in {'none', 'off', 'false'}:
        return None
    if backend == 'remote':
        return _create_remote_reranker()
    if backend == 'local':
        path = _cfg('TAG_RERANKER_PATH')
        return BGEReranker(path) if path else None
    raise ValueError(f'不支持的 TAG_RERANK_BACKEND: {backend}')


def infer_embedding_backend(manifest: dict) -> str:
    stored = manifest.get('embedding_backend')
    if stored:
        return str(stored)
    if manifest.get('embedding_path'):
        return 'local'
    return 'hash'


def infer_reranker_backend(manifest: dict) -> str | None:
    stored = manifest.get('reranker_backend')
    if stored:
        return str(stored)
    if manifest.get('reranker_path'):
        return 'local'
    if manifest.get('reranker_model') or manifest.get('reranker_model_hash'):
        return 'local'
    return None


def _requested_embedding_backend() -> str:
    return (_cfg('TAG_EMBEDDING_BACKEND') or '').strip().lower()


def _requested_rerank_backend() -> str:
    return (_cfg('TAG_RERANK_BACKEND') or '').strip().lower()


def restore_embedder(manifest: dict, resolved_path: str | None = None):
    """按产物 backend 重建 embedder；路径解析由调用方完成。"""
    assert_load_compatible(manifest)
    stored = infer_embedding_backend(manifest)
    if stored == 'remote':
        return _create_remote_embedder()
    if stored == 'local':
        if not resolved_path:
            raise ValueError(MODEL_CHANGED)
        return BGEEmbedder(resolved_path)
    return HashEmbedder()


def restore_reranker(manifest: dict, resolved_path: str | None = None):
    stored = infer_reranker_backend(manifest)
    if stored == 'remote':
        return _create_remote_reranker()
    if stored == 'local':
        if not resolved_path:
            raise ValueError(MODEL_CHANGED)
        return BGEReranker(resolved_path)
    return None


def assert_load_compatible(manifest: dict) -> None:
    """运行时 backend 与产物不一致则拒绝加载；远程禁止挂载旧本地索引。"""
    stored = infer_embedding_backend(manifest)
    requested = _requested_embedding_backend()
    if manifest.get('build_id') in FORBIDDEN_REMOTE_BUILD_IDS and (requested == 'remote' or stored == 'remote'):
        raise ValueError(MODEL_CHANGED)
    if requested and requested != stored:
        raise ValueError(MODEL_CHANGED)
    if stored == 'remote' and requested not in ('', 'remote'):
        raise ValueError(MODEL_CHANGED)
    stored_r = infer_reranker_backend(manifest)
    requested_r = _requested_rerank_backend()
    if requested_r == 'remote' and stored_r != 'remote':
        raise ValueError(MODEL_CHANGED)
    if requested_r in {'none', 'off', 'false'} and stored_r:
        raise ValueError(MODEL_CHANGED)
    if requested_r and requested_r not in {'none', 'off', 'false'} and stored_r and requested_r != stored_r:
        raise ValueError(MODEL_CHANGED)


def assert_models_match_manifest(manifest: dict, embedder, reranker) -> None:
    if getattr(embedder, 'backend', None) != infer_embedding_backend(manifest):
        raise ValueError(MODEL_CHANGED)
    if embedder.model != manifest.get('embedding_model') or int(embedder.dim) != int(manifest.get('embedding_dim')):
        raise ValueError(MODEL_CHANGED)
    if getattr(embedder, 'model_hash', None) != manifest.get('embedding_model_hash'):
        raise ValueError(MODEL_CHANGED)
    if getattr(embedder, 'backend', None) == 'remote':
        stored_url = manifest.get('embedding_base_url')
        if stored_url and canonical_base_url(stored_url) != canonical_base_url(getattr(embedder, 'base_url', '') or ''):
            raise ValueError(MODEL_CHANGED)
    stored_r = infer_reranker_backend(manifest)
    runtime_r = getattr(reranker, 'backend', None) if reranker else None
    if stored_r != runtime_r:
        raise ValueError(MODEL_CHANGED)
    if reranker is None:
        return
    if reranker.model != manifest.get('reranker_model') or reranker.model_hash != manifest.get('reranker_model_hash'):
        raise ValueError(MODEL_CHANGED)
    if runtime_r == 'remote':
        stored_url = manifest.get('reranker_base_url')
        if stored_url and canonical_base_url(stored_url) != canonical_base_url(getattr(reranker, 'base_url', '') or ''):
            raise ValueError(MODEL_CHANGED)
