"""显式外部封存集验收。仅输出 ID 和指标；不生成或传播测试题。"""
import hashlib
import json
import math
from pathlib import Path
from tag_semantic.retrieve.service import visible_candidates
from tag_semantic.agent.dsl import validate_dsl
from tag_semantic.agent.graph import ExactEvidenceSelector


def wilson(success, total):
    if not total:
        return None
    z = 1.96
    p = success / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0, center - half), min(1, center + half)]


def validate_cases(cases, sealed=False):
    if not isinstance(cases, list) or not cases or (sealed and len(cases) < 600):
        raise ValueError('封存验收需要至少 600 条独立题目')
    ids, expressions = set(), set()
    for case in cases:
        required = {'id', 'query', 'eligible_tag_ids', 'atomic_conditions'}
        if not isinstance(case, dict) or required - case.keys():
            raise ValueError('评测题缺少必填字段')
        if not isinstance(case['id'], str) or not case['id'].strip() or case['id'] in ids:
            raise ValueError('评测 ID 为空或重复')
        ids.add(case['id'])
        if not isinstance(case['query'], str) or not case['query'].strip():
            raise ValueError('评测表达不能为空')
        eligible = case['eligible_tag_ids']
        if not isinstance(eligible, list) or any(type(t) is not int or t <= 0 for t in eligible) or len(set(eligible)) != len(eligible):
            raise ValueError('资格必须为无重复正整数数组')
        signature = (' '.join(case['query'].split()), tuple(sorted(eligible)))
        if sealed and signature in expressions:
            raise ValueError('重复表达和资格上下文不能充当独立封存样本')
        expressions.add(signature)
        for key in ('must_clarify', 'inexpressible', 'hard_negative'):
            if key in case and type(case[key]) is not bool:
                raise ValueError('处置标记必须是布尔值')
        special = case.get('must_clarify') or case.get('inexpressible')
        if case.get('must_clarify') and case.get('inexpressible'):
            raise ValueError('预期处置相互冲突')
        if not isinstance(case['atomic_conditions'], list) or (not case['atomic_conditions'] and not special):
            raise ValueError('可回答题必须提供非空原子条件')
        for condition in case['atomic_conditions']:
            values = condition.get('accept_tag_ids') if isinstance(condition, dict) else None
            if not isinstance(values, list) or not values or any(type(v) is not int for v in values) or not set(values) <= set(eligible):
                raise ValueError('可接受答案为空或超出资格')
            required_tags = condition.get('required_tag_ids', [])
            if not isinstance(required_tags, list) or any(type(t) is not int for t in required_tags) or not set(required_tags) <= set(eligible):
                raise ValueError('必需标签集非法')
            if sealed and not special and (not isinstance(condition.get('family_key'), str) or not condition['family_key'].strip()):
                raise ValueError('可回答封存题缺少族级标注')
        if 'expected_codes' in case:
            codes = case['expected_codes']
            if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes) or len(codes) != len(set(codes)):
                raise ValueError('期望码值必须为无重复字符串数组，保留前导零')
            if type(case.get('expected_code_tag_id')) is not int or case['expected_code_tag_id'] not in eligible:
                raise ValueError('期望码值缺少有资格的所属标签')


def load_gold(path: Path, expected_sha256: str):
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError('封存集哈希不符')
    gold = json.loads(payload)
    if gold.get('status') != 'SEALED' or gold.get('sealed') is not True or len(gold.get('queries', [])) < 600:
        raise ValueError('缺少已封存的至少 600 条业务复核题；禁止用开发集替代')
    validate_cases(gold['queries'], sealed=True)
    provenance = gold.get('provenance') or {}
    for key in ('reviewed_by', 'reviewed_at', 'source_ref', 'isolation_ref'):
        if not isinstance(provenance.get(key), str) or not provenance[key].strip():
            raise ValueError('封存集缺少业务复核或隔离证据: ' + key)
    return gold


def evaluate(service, cases, manifest, *, scope='DEVELOPMENT'):
    validate_cases(cases, sealed=scope == 'SEALED')
    counters = {key: [0, 0] for key in ('hit_at_20', 'final_hit_at_10', 'complete_conditions_at_20', 'family_at_10',
                'hard_negative_top1_family', 'code_set_exact', 'clarification_correct', 'inexpressible_correct',
                'high_confidence_precision', 'high_confidence_coverage', 'query_exact_match', 'dsl_schema_legal',
                'hallucinated_references', 'unauthorized_references', 'incorrect_auto_execution')}
    failures, traces = [], []
    multi_cases = 0
    selector = ExactEvidenceSelector()

    def record(metric, passed, identity):
        counters[metric][0] += int(passed)
        counters[metric][1] += 1
        if not passed:
            failures.append({'id': identity, 'metric': metric})

    for case in cases:
        eligible = set(case['eligible_tag_ids'])
        result = service.retrieve(case['query'], eligible, 20)
        recall = result.get('recall_candidates')
        recall_rows = visible_candidates(recall or [], service.catalog, eligible, 20)
        final_rows = visible_candidates(result['candidates'], service.catalog, eligible, 20)
        tags = {r['tag_id'] for r in recall_rows}
        final_tags = {r['tag_id'] for r in final_rows[:10]}
        families = {r.get('family_key') for r in final_rows[:10]}
        conditions = case['atomic_conditions']
        if not (case.get('must_clarify') or case.get('inexpressible')):
            hits = []
            for condition in conditions:
                required = set(condition.get('required_tag_ids', []))
                hit = bool(tags & set(condition['accept_tag_ids'])) and required <= tags
                hits.append(hit)
                record('hit_at_20', hit, case['id'])
                record('final_hit_at_10', bool(final_tags & set(condition['accept_tag_ids'])) and required <= final_tags, case['id'])
                if condition.get('family_key'):
                    record('family_at_10', condition['family_key'] in families, case['id'])
            record('complete_conditions_at_20', all(hits), case['id'])
            final_complete = all(bool(final_tags & set(condition['accept_tag_ids']))
                                 and set(condition.get('required_tag_ids', [])) <= final_tags for condition in conditions)
            record('query_exact_match', final_complete, case['id'])
            proposal = selector.select(case['query'], final_rows, service.catalog)
            high_confidence = proposal if proposal and float(proposal.get('confidence') or 0) >= .99 else None
            record('high_confidence_coverage', high_confidence is not None, case['id'])
            if high_confidence:
                expected = {tag for condition in conditions for tag in condition['accept_tag_ids']}
                recommended = set(high_confidence.get('recommended_tag_ids') or [])
                record('high_confidence_precision', bool(recommended) and recommended <= expected, case['id'])
                if high_confidence.get('dsl'):
                    try:
                        validate_dsl(high_confidence['dsl'], service.catalog, eligible)
                        record('dsl_schema_legal', True, case['id'])
                    except Exception:
                        record('dsl_schema_legal', False, case['id'])
            multi_cases += int(len(conditions) > 1 or any(c.get('required_tag_ids') for c in conditions))
            if case.get('hard_negative'):
                expected = {c['family_key'] for c in conditions if c.get('family_key')}
                record('hard_negative_top1_family', bool(final_rows) and final_rows[0].get('family_key') in expected, case['id'])
        family = result.get('family') or {}
        if case.get('must_clarify'):
            record('clarification_correct', result.get('decision') == 'CLARIFY', case['id'])
        if case.get('inexpressible'):
            record('inexpressible_correct', result.get('decision') == 'INEXPRESSIBLE', case['id'])
        if 'expected_codes' in case:
            selection = result.get('code_selection') or {}
            record('code_set_exact', selection.get('expressible') is True and isinstance(selection.get('codes'), list)
                   and set(selection['codes']) == set(case['expected_codes'])
                   and (family.get('selected') or {}).get('tag_id') == case['expected_code_tag_id'], case['id'])
        # 审计未过滤输出，不能靠先丢弃非法引用制造“零越权”。
        references = {c['doc']['tag_id'] for c in (recall or []) + result['candidates']
                      if c['doc'].get('doc_type') != 'concept' and c['doc'].get('tag_id')}
        for member in [family.get('selected') or {}] + (family.get('confusable_shown') or []):
            if member.get('tag_id'):
                references.add(member['tag_id'])
        unauthorized = len(references - eligible)
        hallucinated = len(references - set(service.catalog.tags))
        counters['hallucinated_references'][0] += hallucinated
        counters['hallucinated_references'][1] += len(references)
        if hallucinated:
            failures.append({'id': case['id'], 'metric': 'hallucinated_references'})
        counters['unauthorized_references'][0] += unauthorized
        counters['unauthorized_references'][1] += len(references)
        if unauthorized:
            failures.append({'id': case['id'], 'metric': 'unauthorized_references'})
        counters['incorrect_auto_execution'][0] += int(result.get('auto_execute') is True)
        counters['incorrect_auto_execution'][1] += 1
        if result.get('auto_execute') is True:
            failures.append({'id': case['id'], 'metric': 'incorrect_auto_execution'})
        if recall is None:
            failures.append({'id': case['id'], 'metric': 'missing_recall_stage'})
        traces.append({'id': case['id'], 'eligible_sha256': hashlib.sha256(json.dumps(sorted(eligible)).encode()).hexdigest(),
                       'recall_tag_ids': [r['tag_id'] for r in recall_rows], 'final_tag_ids': [r['tag_id'] for r in final_rows[:10]],
                       'decision': result.get('decision')})
    metrics = {key: {'numerator': a, 'denominator': b, 'rate': a / b if b else None, 'ci95': wilson(a, b)} for key, (a, b) in counters.items()}
    thresholds = {'hit_at_20': .995, 'family_at_10': .99, 'hard_negative_top1_family': .95,
                  'high_confidence_precision': .99, 'high_confidence_coverage': .60, 'query_exact_match': .90,
                  'dsl_schema_legal': 1,
                  'code_set_exact': 1, 'clarification_correct': 1, 'inexpressible_correct': 1}
    gates = {key: metrics[key]['denominator'] > 0 and metrics[key]['rate'] >= threshold for key, threshold in thresholds.items()}
    tags = list(service.catalog.tags.values())
    gates.update(sealed_scope=scope == 'SEALED' and len(cases) >= 600,
                 full_969_snapshot=len(tags) == 969 and service.catalog.meta.get('scope') == 'FULL',
                 reviewed_tags=bool(tags) and all(t.get('review_status') == 'REVIEWED' for t in tags),
                 real_embedding=manifest.get('embedding_model') == 'BAAI/bge-m3' and bool(manifest.get('embedding_model_hash')),
                 real_reranker=manifest.get('reranker_model') == 'BAAI/bge-reranker-v2-m3' and bool(manifest.get('reranker_model_hash')),
                 multi_condition_cases=multi_cases > 0,
                 no_hallucinated_references=counters['hallucinated_references'][0] == 0,
                 no_unauthorized_references=counters['unauthorized_references'][0] == 0,
                 no_automatic_execution=counters['incorrect_auto_execution'][0] == 0,
                 recall_stage_present=not any(f['metric'] == 'missing_recall_stage' for f in failures))
    return {'scope': scope, 'build_id': manifest['build_id'], 'snapshot_id': manifest['snapshot_id'],
            'retrieval_config_hash': manifest['retrieval_config_hash'], 'case_ids': [c['id'] for c in cases],
            'fingerprints': {key: manifest.get(key) for key in ('content_hash', 'doc_id_hash', 'doc_template_version',
                'embedding_model_hash', 'reranker_model_hash', 'retrieval_config_hash', 'analyzer_version', 'store_type')},
            'metrics': metrics, 'failures': failures, 'traces': traces, 'multi_condition_cases': multi_cases,
            'gates': gates, 'acceptance_passed': all(gates.values()), 'production_acceptance': False,
            'limitations': ['仅为检索质量验收；业务签字、角色、容量与恢复验收需要独立证据。']}


def main():
    import argparse
    from tag_semantic.index.builder import load_index
    from tag_semantic.retrieve.service import RetrieveService
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--sealed', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.sealed.resolve():
        parser.error('报告不能覆盖封存题')
    gold = load_gold(args.sealed, args.sha256)
    built = load_index(args.build_dir)
    service = RetrieveService(built['catalog'], built['store'], built['alias_index'], built['embedder'], built['reranker'], built['manifest']['retrieval_config'])
    report = evaluate(service, gold['queries'], built['manifest'], scope='SEALED')
    report['sealed_sha256'] = args.sha256
    report['provenance'] = gold['provenance']
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if report['acceptance_passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
