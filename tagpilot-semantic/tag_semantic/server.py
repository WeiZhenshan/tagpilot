"""受控检索运行时。外部请求经 Java 认证/资格解析后传入固定 build。"""
from pathlib import Path
from threading import RLock
from typing import Literal
import hashlib
import hmac
import json
import os
import re
import uuid
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from tag_semantic.index.lease import build_lease
from tag_semantic.index.builder import build_index, load_index, sha
from tag_semantic.index.embedder import BGEEmbedder, BGEReranker
from tag_semantic.index.milvus_store import id_hash
from tag_semantic.retrieve.service import RetrieveService, selection_context, visible_candidates
from tag_semantic.snapshot.loader import load_catalog


class BuildRequest(BaseModel):
    build_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    snapshot_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,40}$')
    library_id: int = Field(gt=0)
    store_type: Literal['LOCAL', 'MILVUS']


class RetrieveRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=500)
    library_id: int = Field(gt=0)
    build_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,48}$')
    eligible_tag_ids: list[int] = Field(max_length=100000)
    k: int = Field(default=20, ge=1, le=50)


class EvidenceRequest(RetrieveRequest):
    tag_ids: list[int] = Field(default_factory=list, max_length=50)


class CapabilityRequest(RetrieveRequest):
    capability_ids: list[str] = Field(default_factory=list, max_length=20)


class ExpandFreezeRequest(BaseModel):
    jsonl: str = Field(min_length=1, max_length=20_000_000)


def create_app(artifact_root=None, snapshot_root=None, token=None):
    root = Path(artifact_root or os.getenv('TAG_INDEX_DIR', './data/tag-index')).resolve()
    snapshots = Path(snapshot_root or os.getenv('TAG_SNAPSHOT_DIR', './data/tag-snapshots')).resolve()
    secret = token if token is not None else os.getenv('TAG_RUNTIME_TOKEN', '')
    app = FastAPI(title='Tag semantic engine', docs_url=None, redoc_url=None)
    lock = RLock()
    cache = {}
    counters = {"retrieve_requests": 0, "retrieve_failures": 0, "activation_requests": 0, "cleanup_requests": 0}

    def authenticate(authorization: str = Header(default='')):
        if not secret:
            raise HTTPException(503, '运行时服务认证未配置')
        if not hmac.compare_digest(authorization, 'Bearer ' + secret):
            raise HTTPException(401, '服务认证失败')

    def bundle(build_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', build_id):
            raise HTTPException(422, 'build_id 格式错误')
        with lock:
            try:
                path = root / build_id
                if (path / 'purged.json').exists():
                    cache.pop(build_id, None)
                    raise ValueError('构建已清理')
                if build_id not in cache:
                    built = load_index(path)
                    if built['manifest']['build_id'] != build_id:
                        raise ValueError('构建目录身份不一致')
                    built['service'] = RetrieveService(built['catalog'], built['store'], built['alias_index'], built['embedder'], built['reranker'], built['manifest']['retrieval_config'])
                    built['artifact_hash'] = sha(path / 'manifest.json')
                    if len(cache) >= 3:
                        cache.pop(next(iter(cache)))
                    cache[build_id] = built
                return cache[build_id]
            except Exception as exc:
                raise HTTPException(503, '索引不可用或校验失败') from exc

    @app.get('/health')
    def health():
        return {'status': 'ok', 'configured': bool(secret)}

    @app.post('/bootstrap/expand', dependencies=[Depends(authenticate)])
    def bootstrap_expand(request: ExpandFreezeRequest):
        from tag_semantic.bootstrap.expand_full import importable_draft
        try:
            return importable_draft(request.jsonl)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post('/build', dependencies=[Depends(authenticate)])
    def build(request: BuildRequest):
        try:
            with lock:
                catalog = load_catalog(snapshots / (request.snapshot_id + '.jsonl'))
                if catalog.meta.get('snapshot_id') != request.snapshot_id or catalog.meta['library_id'] != request.library_id:
                    raise ValueError('快照与构建请求身份不一致')
                embedding_path = os.getenv('TAG_EMBEDDING_PATH')
                reranker_path = os.getenv('TAG_RERANKER_PATH')
                if not embedding_path and os.getenv('TAG_ALLOW_HASH_BASELINE') != 'true':
                    raise ValueError('真实 Embedding 未配置；基线须显式开启 TAG_ALLOW_HASH_BASELINE')
                built = build_index(catalog, root / request.build_id, request.build_id, request.store_type,
                                    BGEEmbedder(embedding_path) if embedding_path else None,
                                    BGEReranker(reranker_path) if reranker_path else None)
                return {**built['manifest'], 'artifact_uri': (root / request.build_id).as_uri(), 'artifact_hash': sha(root / request.build_id / 'manifest.json')}
        except Exception as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/retrieve', dependencies=[Depends(authenticate)])
    def retrieve(request: RetrieveRequest):
        built = bundle(request.build_id)
        manifest, catalog = built['manifest'], built['catalog']
        if manifest['library_id'] != request.library_id:
            raise HTTPException(409, '构建不属于请求标签库')
        eligible = set(request.eligible_tag_ids) & set(catalog.tags)
        try:
            with build_lease(root, request.build_id):
                counters['retrieve_requests'] += 1
                if (root / request.build_id / 'purged.json').exists():
                    raise ValueError('构建已清理')
                response = built['service'].retrieve(request.requirement, eligible, request.k)
        except Exception as exc:
            counters['retrieve_failures'] += 1
            raise HTTPException(503, '检索服务暂不可用；未降级') from exc
        # 返回可见候选和可观测特征；不回传向量或带隐藏成员的完整目录对象。
        candidates = visible_candidates(response['candidates'], catalog, eligible, request.k)
        family = response.get('family') or {}
        selected = family.get('selected') or {}
        scores = [float(c['rank_features'].get('rrf_score', 0)) for c in candidates]
        return {'trace_id': uuid.uuid4().hex, 'snapshot_id': manifest['snapshot_id'], 'build_id': request.build_id,
                'artifact_hash': built['artifact_hash'], 'store_type': manifest['store_type'], 'doc_template_version': manifest['doc_template_version'],
                'eligible_hash': id_hash(str(t) for t in eligible), 'candidates': candidates,
                'selection_context': selection_context(candidates, catalog),
                'decision': response.get('decision', 'CANDIDATES_ONLY'), 'code_selection': response.get('code_selection'), 'auto_execute': False,
                'facets': response['facets'], 'family': {'status': family.get('status'), 'tag_id': selected.get('tag_id')},
                'rank_features': {'margin': scores[0] - scores[1] if len(scores) > 1 else None,
                                  'family_resolved': family.get('status') == 'selected',
                                  'channel_agreement': len((response['candidates'][0].get('rank_features') or {})) / 4 if response['candidates'] else 0,
                                  'unresolved_fuzzy_terms': response['facets'].get('unresolved_fuzzy_terms', []),
                                  'retrieval_config_hash': manifest['retrieval_config_hash']}}

    @app.post('/evidence', dependencies=[Depends(authenticate)])
    def evidence(request: EvidenceRequest):
        with build_lease(root, request.build_id):
            built = bundle(request.build_id)
            if built['manifest']['library_id'] != request.library_id:
                raise HTTPException(409, '构建不属于请求标签库')
            eligible = set(request.eligible_tag_ids) & set(built['catalog'].tags)
            if not set(request.tag_ids) <= eligible:
                raise HTTPException(403, '标签不在当前资格范围')
            context = selection_context([{'tag_id': tid} for tid in request.tag_ids], built['catalog'])
            # 术语仅返回描述与默认策略，不透出可能指向资格外标签的映射。
            terms = [{k: term.get(k) for k in ('term', 'definition', 'default_policy', 'policy')}
                     for term in built['catalog'].terms if term.get('term') and term['term'] in request.requirement]
            return {**context, 'terms': terms, 'snapshot_id': built['manifest']['snapshot_id'],
                    'build_id': request.build_id, 'artifact_hash': built['artifact_hash']}

    @app.post('/capabilities', dependencies=[Depends(authenticate)])
    def capabilities(request: CapabilityRequest):
        from tag_semantic.retrieve.capabilities import search_capabilities
        with build_lease(root, request.build_id):
            built = bundle(request.build_id)
            if built['manifest']['library_id'] != request.library_id:
                raise HTTPException(409, '构建不属于请求标签库')
            catalog = built['catalog']
            eligible = set(request.eligible_tag_ids) & set(catalog.tags)
            caps = search_capabilities(catalog, request.requirement, eligible, request.capability_ids)
            inputs = sorted({tid for cap in caps for tid in cap.get('input_tag_ids', [])})
            context = selection_context([{'tag_id': tid} for tid in inputs], catalog)
            return {**context, 'capabilities': caps, 'trace_id': uuid.uuid4().hex,
                    'snapshot_id': built['manifest']['snapshot_id'], 'build_id': request.build_id,
                    'artifact_hash': built['artifact_hash']}

    @app.get('/stats', dependencies=[Depends(authenticate)])
    def stats(build_id: str):
        built = bundle(build_id)
        manifest = built['manifest']
        actual = built['store'].stats() if manifest['store_type'] == 'MILVUS' else {'doc_count': len(built['store'].docs), 'doc_id_hash': id_hash(d['doc_id'] for d in built['store'].docs)}
        return {**manifest, **actual, 'artifact_hash': built['artifact_hash'], 'id_reconciled': actual['doc_id_hash'] == manifest['doc_id_hash']}

    @app.post('/catalog-overview', dependencies=[Depends(authenticate)])
    def overview(request: RetrieveRequest):
        built = bundle(request.build_id)
        if built['manifest']['library_id'] != request.library_id:
            raise HTTPException(409, '构建不属于请求标签库')
        eligible = set(request.eligible_tag_ids)
        tags = [t for tid, t in built['catalog'].tags.items() if tid in eligible]
        concepts = {str(t.get('concept_id') or t.get('concept_code')) for t in tags}
        domains = {t['dir_path'][0] for t in tags if t.get('dir_path')}
        return {'build_id': request.build_id, 'tag_count': len(tags), 'concept_count': len(concepts), 'domain_count': len(domains)}

    @app.post('/activate', dependencies=[Depends(authenticate)])
    def activate(request: BuildRequest):
        built = bundle(request.build_id)
        manifest = built['manifest']
        if (request.library_id, request.snapshot_id, request.store_type) != (manifest['library_id'], manifest['snapshot_id'], manifest['store_type']):
            raise HTTPException(409, '激活身份不一致')
        current = stats(request.build_id)
        if not current['id_reconciled']:
            raise HTTPException(409, '行集对账失败')
        with lock, build_lease(root, request.build_id):
            counters['activation_requests'] += 1
            built['store'].activate(request.build_id)
        return {'build_id': request.build_id, 'status': 'PREPARED', 'store_type': manifest['store_type']}

    @app.get('/metrics', dependencies=[Depends(authenticate)])
    def metrics():
        return {**counters, 'cached_builds': len(cache), 'store_types': sorted({b['manifest']['store_type'] for b in cache.values()})}

    @app.post('/deactivate', dependencies=[Depends(authenticate)])
    def deactivate(request: BuildRequest):
        # Java 持有库锁并确认事务回滚/无 ACTIVE 后调用，不能据 alias 修改数据库。
        with lock, build_lease(root, request.build_id):
            built = bundle(request.build_id)
            manifest = built['manifest']
            if (request.library_id, request.snapshot_id, request.store_type) != (manifest['library_id'], manifest['snapshot_id'], manifest['store_type']):
                raise HTTPException(409, '撤销激活身份不一致')
            removed = built['store'].deactivate() if manifest['store_type'] == 'MILVUS' else False
            return {'build_id': request.build_id, 'alias_removed': removed, 'status': 'DEACTIVATED'}

    @app.post('/drop', dependencies=[Depends(authenticate)])
    def drop(request: BuildRequest):
        # 只有 Java 在库锁内确认 RETIRED 且不属于最近三个回滚点后调用。
        with lock, build_lease(root, request.build_id, exclusive=True):
            path = root / request.build_id
            if (path / 'purged.json').exists():
                return {'build_id': request.build_id, 'status': 'PURGED'}
            built = load_index(path)
            manifest = built['manifest']
            if (request.library_id, request.snapshot_id, request.store_type) != (manifest['library_id'], manifest['snapshot_id'], manifest['store_type']):
                raise HTTPException(409, '清理身份不一致')
            if manifest['store_type'] == 'MILVUS':
                store = built['store']
                if store.client.has_collection(store.collection):
                    if store.stats()['doc_id_hash'] != manifest['doc_id_hash']:
                        raise HTTPException(409, '清理前行集对账失败')
                    store.drop(request.build_id)
            # 保留快照、manifest、docs、词典和模型指纹供重建；仅移除派生 Collection。
            (path / 'purged.json').write_text(json.dumps({'status': 'PURGED', 'build_id': request.build_id}))
            cache.pop(request.build_id, None)
            counters['cleanup_requests'] += 1
            return {'build_id': request.build_id, 'status': 'PURGED'}

    return app


app = create_app()
