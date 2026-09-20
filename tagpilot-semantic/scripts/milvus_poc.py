"""外部 Milvus 合约 PoC；只创建并删除本次 UUID 测试 Collection/alias。"""
import argparse
import json
import platform
import resource
import statistics
import tempfile
import time
import uuid
from pathlib import Path
from importlib.metadata import version
from tag_semantic.index.builder import build_index, load_index
from tag_semantic.snapshot.canonicalize import content_hash, dumps_jsonl
from tag_semantic.snapshot.loader import load_catalog
from tag_semantic.retrieve.service import RetrieveService
from tag_semantic.index.embedder import BGEEmbedder, BGEReranker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--embedding')
    parser.add_argument('--reranker')
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.snapshot.read_text().splitlines()]
    library_id = int(time.time() * 1000)
    for row in rows:
        if 'library_id' in row:
            row['library_id'] = library_id
    meta = next(r for r in rows if r['kind'] == 'meta')
    meta['snapshot_id'] = 'POC-' + uuid.uuid4().hex[:16]
    meta['content_hash'] = content_hash(rows)
    report = {'scope': 'ISOLATED_CONTRACT_FIXTURE', 'production_quality_accepted': False, 'python': platform.python_version(), 'architecture': platform.machine(), 'pymilvus': version('pymilvus')}
    with tempfile.TemporaryDirectory(prefix='tag-milvus-poc-') as temp:
        root = Path(temp)
        snapshot = root / 'snapshot.jsonl'
        snapshot.write_text(dumps_jsonl(rows))
        catalog = load_catalog(snapshot)
        built = None
        try:
            started = time.perf_counter()
            built = build_index(catalog, root / 'b1', 'poc-' + uuid.uuid4().hex[:20], 'MILVUS',
                                BGEEmbedder(args.embedding) if args.embedding else None,
                                BGEReranker(args.reranker) if args.reranker else None)
            report['build_seconds'] = time.perf_counter() - started
            store = built['store']
            report['server_version'] = store.client.get_server_version()
            report['analyzer_tokens'] = store.client.run_analyzer(texts=['近30天异名跨行转入'], analyzer_params={'tokenizer': {'type': 'jieba'}})
            report['analyzer_tokens'] = str(report['analyzer_tokens'])
            report['stats'] = store.stats()
            service = RetrieveService(catalog, store, built['alias_index'], built['embedder'], built['reranker'])
            report['embedding_model'] = built['manifest']['embedding_model']
            report['embedding_model_hash'] = built['manifest']['embedding_model_hash']
            report['reranker_model_hash'] = built['manifest']['reranker_model_hash']
            assert not service.retrieve('女性', set())['candidates']
            visible = set(catalog.tags)
            timings = []
            for _ in range(20):
                start = time.perf_counter()
                result = service.retrieve('女性', visible | set(range(100000, 103000)))
                timings.append((time.perf_counter() - start) * 1000)
                assert all(c['doc'].get('tag_id', -1) in visible or c['doc']['doc_type'] == 'concept' for c in result['candidates'])
            report['whitelist_3000_p95_ms'] = sorted(timings)[18]
            report['empty_whitelist_passed'] = True
            store.activate(built['manifest']['build_id'])
            alias = f'tag_docs_active_l{library_id}'
            assert alias in store.client.list_aliases(store.collection).get('aliases', [])
            report['alias_switch_passed'] = True
            assert store.deactivate() is True
            assert store.deactivate() is False
            assert alias not in store.client.list_aliases(store.collection).get('aliases', [])
            report['first_activation_alias_compensation_passed'] = True
            store.activate(built['manifest']['build_id'])
            restored = load_index(root / 'b1')
            assert restored['store'].stats()['doc_id_hash'] == built['manifest']['doc_id_hash']
            report['reload_id_hash_passed'] = True
            report['peak_python_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            report['not_measured'] = ['真实模型600封存召回', '969/1723全量', '服务端内存峰值', '生产进程崩溃', '生产4核16GB容量', '自定义词典']
        finally:
            if built:
                store = built['store']
                alias = f'tag_docs_active_l{library_id}'
                if alias in store.client.list_aliases(store.collection).get('aliases', []):
                    store.client.drop_alias(alias)
                store.drop(built['manifest']['build_id'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
