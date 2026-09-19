"""不可变构建、持久化与恢复。加载绝不重新计算向量或覆盖 manifest。"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
import numpy as np
from tag_semantic.docs.templates import TEMPLATE_VERSION, render_documents
from tag_semantic.index.alias_index import AliasIndex
from tag_semantic.index.embedder import HashEmbedder, BGEEmbedder, BGEReranker
from tag_semantic.index.local_store import LocalStore
from tag_semantic.index.milvus_store import MilvusStore, id_hash
from tag_semantic.snapshot.canonicalize import dumps_jsonl, content_hash
from tag_semantic.snapshot.loader import load_catalog, write_graph_sqlite


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_index(catalog, out_dir: Path, build_id: str, store_type='LOCAL', embedder=None, reranker=None, config=None):
    if store_type not in ('LOCAL', 'MILVUS'):
        raise ValueError('不支持的存储模式，禁止自动降级')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', build_id):
        raise ValueError('build_id 格式错误')
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise FileExistsError('构建目录已存在；请分配新 build_id')
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.building-', dir=out_dir.parent))
    embedder = embedder or HashEmbedder()
    config = {'channel_k': 30, 'rrf_k': 60, 'rerank_k': 50, 'domain_prior_weight': 0.002, **(config or {})}
    docs = render_documents(list(catalog.tags.values()), list(catalog.concepts.values()), catalog.code_values)
    if not docs:
        raise ValueError('空快照不得构建')
    dense = embedder.encode(d['dense_text'] for d in docs)
    for doc, vec in zip(docs, dense):
        doc['dense'] = vec
    with (temp / 'docs.jsonl').open('w', encoding='utf-8') as stream:
        for doc in docs:
            stream.write(json.dumps({k: v for k, v in doc.items() if k != 'dense'}, ensure_ascii=False) + '\n')
    np.save(temp / 'emb.npy', np.asarray(dense, dtype=np.float32), allow_pickle=False)
    (temp / 'snapshot.jsonl').write_text(dumps_jsonl(catalog.rows), encoding='utf-8')
    write_graph_sqlite(catalog, temp / 'graph.sqlite')
    aliases = AliasIndex()
    aliases.build(catalog.aliases)
    aliases.save(temp / 'alias_automaton.json')
    collection = 'tag_docs_' + hashlib.sha256((str(catalog.meta.get('library_id')) + ':' + build_id).encode()).hexdigest()[:32]
    store = LocalStore() if store_type == 'LOCAL' else MilvusStore(collection=collection, library_id=catalog.meta['library_id'], embedder=embedder)
    stats = store.build(docs)
    manifest = {'build_id': build_id, 'snapshot_id': catalog.meta.get('snapshot_id'), 'library_id': catalog.meta['library_id'],
                'content_hash': content_hash(catalog.rows), 'doc_template_version': TEMPLATE_VERSION,
                'embedding_model': embedder.model, 'embedding_dim': embedder.dim,
                'embedding_model_hash': getattr(embedder, 'model_hash', hashlib.sha256(b'hash-v1:64').hexdigest()),
                'embedding_path': getattr(embedder, 'path', None), 'reranker_path': getattr(reranker, 'path', None),
                'reranker_model': getattr(reranker, 'model', None), 'reranker_model_hash': getattr(reranker, 'model_hash', None),
                'retrieval_config': config, 'retrieval_config_hash': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                'analyzer_version': 'jieba-default' if store_type == 'MILVUS' else 'local-char-v1',
                'eval_summary': {'status': 'NOT_EVALUATED'}, 'store_type': store_type, 'doc_count': len(docs),
                'doc_id_hash': id_hash(d['doc_id'] for d in docs), 'status': 'READY', **stats}
    manifest['files'] = {p.name: sha(p) for p in sorted(temp.iterdir()) if p.is_file()}
    (temp / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    os.rename(temp, out_dir)
    return {'manifest': manifest, 'docs': docs, 'store': store, 'alias_index': aliases, 'embedder': embedder, 'reranker': reranker}


def load_index(out_dir: Path):
    root = Path(out_dir)
    manifest = json.loads((root / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if Path(name).name != name or sha(root / name) != expected:
            raise ValueError(f'构建文件校验失败: {name}')
    catalog = load_catalog(root / 'snapshot.jsonl', manifest['content_hash'])
    if catalog.meta.get('snapshot_id') != manifest['snapshot_id'] or catalog.meta['library_id'] != manifest['library_id']:
        raise ValueError('manifest 与快照身份不一致')
    embedder = BGEEmbedder(manifest['embedding_path']) if manifest['embedding_path'] else HashEmbedder()
    if getattr(embedder, 'model_hash', hashlib.sha256(b'hash-v1:64').hexdigest()) != manifest['embedding_model_hash']:
        raise ValueError('Embedding 模型已变化，必须新建 build')
    reranker = BGEReranker(manifest['reranker_path']) if manifest.get('reranker_path') else None
    if reranker and reranker.model_hash != manifest['reranker_model_hash']:
        raise ValueError('Reranker 模型已变化，必须新建 build')
    docs = [json.loads(line) for line in (root / 'docs.jsonl').read_text().splitlines()]
    vectors = np.load(root / 'emb.npy', allow_pickle=False)
    if vectors.shape != (len(docs), manifest['embedding_dim']) or not np.isfinite(vectors).all():
        raise ValueError('向量形状或数值不合法')
    if len(docs) != manifest['doc_count'] or id_hash(d['doc_id'] for d in docs) != manifest['doc_id_hash']:
        raise ValueError('文档行集与 manifest 不一致')
    for doc, vec in zip(docs, vectors):
        doc['dense'] = vec.tolist()
    if manifest['store_type'] == 'LOCAL':
        store = LocalStore()
        store.build(docs)
    elif manifest['store_type'] == 'MILVUS':
        store = MilvusStore(collection=manifest['milvus_collection'], library_id=manifest['library_id'], embedder=embedder)
        store.docs = docs
    else:
        raise ValueError('不支持的存储模式')
    return {'manifest': manifest, 'catalog': catalog, 'store': store, 'alias_index': AliasIndex.load(root / 'alias_automaton.json'), 'embedder': embedder, 'reranker': reranker}
