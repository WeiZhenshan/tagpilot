"""确定性哈希向量，可替换为 BGE-M3。"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable
from functools import lru_cache
from threading import RLock

_model_load_lock=RLock()

@lru_cache(maxsize=2)
def _shared_embedding(path, fingerprint):
    from FlagEmbedding import BGEM3FlagModel
    return BGEM3FlagModel(path,use_fp16=False,devices=['cpu']),RLock()

@lru_cache(maxsize=2)
def _shared_reranker(path, fingerprint):
    from FlagEmbedding import FlagReranker
    return FlagReranker(path,use_fp16=False,devices=['cpu']),RLock()


class HashEmbedder:
    def __init__(self, dim: int = 64, model: str = "hash-v1") -> None:
        self.dim = dim
        self.model = model

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
    from pathlib import Path
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


class BGEEmbedder:
    model = 'BAAI/bge-m3'
    dim = 1024

    def __init__(self, path: str):
        self.model_hash = model_directory_hash(path)
        self.path = path
        from pathlib import Path
        with _model_load_lock:self._model,self._inference_lock=_shared_embedding(str(Path(path).resolve()),self.model_hash)

    def encode(self, texts):
        with self._inference_lock:
            return self._model.encode(list(texts), batch_size=8, max_length=2048)['dense_vecs'].tolist()


class BGEReranker:
    model = 'BAAI/bge-reranker-v2-m3'

    def __init__(self, path: str):
        self.model_hash = model_directory_hash(path)
        self.path = path
        from pathlib import Path
        with _model_load_lock:self._model,self._inference_lock=_shared_reranker(str(Path(path).resolve()),self.model_hash)

    def rerank(self, query, candidates, k=10, **options):
        return self.rerank_batch([(query,candidates)],k,**options)[0]

    def rerank_batch(self, batches, k=10, max_length=None, batch_size=None):
        pairs=[[query,c['doc'].get('body_text','')[:2000]+'\n[族] '+str(c['doc'].get('family_key') or '')]
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
