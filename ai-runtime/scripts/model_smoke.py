"""真实模型本地小批 A/B；通用合成探针，不代表业务 Gold 或全库准确率。"""
import argparse
import json
import resource
import time
from pathlib import Path
import numpy as np
from tag_semantic.index.embedder import BGEEmbedder, BGEReranker, HashEmbedder, cosine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--embedding', required=True)
    parser.add_argument('--reranker', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    embedding, reranker = BGEEmbedder(args.embedding), BGEReranker(args.reranker)
    load_seconds = time.monotonic() - started
    documents = ['性别为女性的客户，女客户，性别代码 F。', '近30天跨行转入金额，最近一个月从其他银行转入的资金总额。',
                 '客户当前年龄，按出生日期计算的周岁数。', '银行卡开卡日期，客户办理该卡的日期。']
    queries = [('女客户', 0), ('最近一个月其他银行转进来的钱', 1), ('今年多大岁数', 2)]
    candidates = [{'doc': {'doc_id': str(i), 'body_text': value}} for i, value in enumerate(documents)]
    results = []
    for model in [HashEmbedder(), embedding]:
        start = time.monotonic()
        vectors = model.encode(documents)
        assert np.asarray(vectors).shape == (4, model.dim) and np.isfinite(vectors).all()
        scores = []
        for query, expected in queries:
            vector = model.encode([query])[0]
            ranked = sorted(range(4), key=lambda i: cosine(vector, vectors[i]), reverse=True)
            scores.append({'expected_doc': expected, 'ranked_doc_ids': ranked, 'hit_top1': ranked[0] == expected})
        results.append({'model': model.model, 'seconds': time.monotonic() - start, 'results': scores})
    start = time.monotonic()
    reranked = []
    for query, expected in queries:
        rows = reranker.rerank(query, candidates, k=4)
        assert len(rows) == 4 and all(np.isfinite(r['rerank_score']) for r in rows)
        reranked.append({'expected_doc': expected, 'ranked_doc_ids': [int(r['doc']['doc_id']) for r in rows],
                         'scores': [r['rerank_score'] for r in rows], 'hit_top1': int(rows[0]['doc']['doc_id']) == expected})
    report = {'scope': 'REAL_MODELS_SYNTHETIC_SANITY', 'production_acceptance': False,
              'business_gold_cases': 0, 'load_seconds': load_seconds,
              'embedding_model_hash': embedding.model_hash, 'reranker_model_hash': reranker.model_hash,
              'embedding_dim': embedding.dim, 'embedding_ab': results, 'reranker_results': reranked,
              'reranker_seconds': time.monotonic() - start, 'total_seconds': time.monotonic() - started,
              'peak_rss_platform_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'limitations': ['4 条通用合成文档、3 个探针，仅验证模型加载、数值和基础排序。',
                              '不是 600 条封存评测，不证明 969 标签覆盖，不是生产容量验收。']}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'seconds': report['total_seconds'], 'production_acceptance': False}))


if __name__ == '__main__':
    main()
