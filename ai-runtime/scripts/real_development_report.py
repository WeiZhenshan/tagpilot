"""同一 SQL 合成试点、20 条开发题上的真实 BGE / reranker 对照；不读取封存题。"""
import argparse
import json
import tempfile
import time
from pathlib import Path
from tag_semantic.tests.test_pipeline import _pilot_bundle
from tag_semantic.eval.gold import GOLD_DEV
from tag_semantic.eval.acceptance import evaluate
from tag_semantic.index.builder import build_index
from tag_semantic.index.embedder import BGEEmbedder, BGEReranker
from tag_semantic.retrieve.service import RetrieveService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--embedding', required=True)
    parser.add_argument('--reranker', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    embedding, reranker = BGEEmbedder(args.embedding), BGEReranker(args.reranker)
    with tempfile.TemporaryDirectory(prefix='real-semantic-dev-') as folder:
        root = Path(folder)
        baseline, catalog, _ = _pilot_bundle(root)
        cases = []
        for row in GOLD_DEV:
            condition = {'accept_tag_ids': row['accept_tag_ids']}
            families = {catalog.tags[tid]['family_key'] for tid in row['accept_tag_ids']}
            if len(families) == 1:
                condition['family_key'] = next(iter(families))
            case = {'id': row['id'], 'query': row['query'], 'eligible_tag_ids': list(catalog.tags),
                    'atomic_conditions': [condition], 'must_clarify': row.get('must_clarify', False)}
            if row.get('inexpressible_approx'):
                case.update(inexpressible=True, must_clarify=False)
            if row.get('accept_code'):
                case.update(expected_codes=[row['accept_code']], expected_code_tag_id=row['accept_tag_ids'][0])
            cases.append(case)
        results = []
        for name in ['HASH_BASELINE', 'BGE_WITHOUT_RERANKER', 'BGE_WITH_RERANKER']:
            step = time.monotonic()
            if name == 'HASH_BASELINE':
                svc = baseline
                manifest = json.loads((root / 'b1/manifest.json').read_text())
            elif name == 'BGE_WITHOUT_RERANKER':
                built = build_index(catalog, root / 'bge', 'bge-dev', 'LOCAL', embedding)
                svc = RetrieveService(catalog, built['store'], built['alias_index'], embedding)
                manifest = built['manifest']
            else:
                # 同一语料、向量和召回配置；仅加入真实 reranker。
                svc = RetrieveService(catalog, built['store'], built['alias_index'], embedding, reranker)
                manifest = {**built['manifest'], 'build_id': 'bge-rerank-dev',
                            'reranker_model': reranker.model, 'reranker_model_hash': reranker.model_hash}
            report = evaluate(svc, cases, manifest, scope='DEVELOPMENT_SYNTHETIC_PILOT')
            report.update(experiment=name, seconds=time.monotonic() - step)
            results.append(report)
            print(json.dumps({'experiment': name, 'seconds': report['seconds'], 'failures': report['failures']}), flush=True)
        args.output.write_text(json.dumps({'scope': 'REAL_MODEL_DEVELOPMENT_AB', 'production_acceptance': False,
            'tag_count': len(catalog.tags), 'case_count': len(cases), 'total_seconds': time.monotonic() - started,
            'limitations': ['SQL 合成试点与开发题，不是独立业务 Gold；未达到 969/969 全库发布验收。'],
            'experiments': results}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
