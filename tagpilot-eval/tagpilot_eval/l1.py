"""L1 检索与消歧跑批：对每个原子条件做检索召回检查，并核对详情口径。

判定独立于被测 Agent：直接用本地语义检索服务的 /retrieve_batch 与 /evidence，
按标准树的每个原子条件构造自然语言短语，检查目标标签是否进入 top-K、口径是否一致。
"""
import json
from collections import Counter
from pathlib import Path

from .io import digest, fresh_directory, read_jsonl, write_json, write_jsonl
from .oracle import references
from .runtime import SemanticClient, runtime_token  # noqa: F401  (令牌缺失时尽早失败)

_OP_WORD = {'>=': '至少', '>': '超过', '<': '低于', '<=': '不超过', '=': '等于',
            '!=': '不等于', 'between': '介于', 'contains': '包含'}


def _fmt_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number) and abs(number) >= 10000:
        return f'{number / 10000:g}万元'
    if 0 < number < 1:
        return f'{number * 100:g}%'
    return f'{number:g}'


def _phrase(fact, node):
    name = fact['name']
    operator = node['operator']
    values = node['values']
    if operator in {'is_null', 'is_not_null'}:
        return f'{name}{"为空" if operator == "is_null" else "不为空"}'
    if operator in {'in', 'not_in'}:
        definitions = {c['code']: c['definition'] for c in fact['codes']}
        joined = '、'.join(definitions.get(v, v) for v in values)
        return f'{name}属于{joined}' if operator == 'in' else f'{name}不属于{joined}'
    if operator == 'between':
        return f'{name}在{values[0]}到{values[1]}之间'
    if operator == 'contains':
        return f'{name}包含{values[0]}'
    if node['data_kind'] == 'STRING':
        definitions = {c['code']: c['definition'] for c in fact['codes']}
        return f'{name}{"是" if operator == "=" else "不是"}{definitions.get(values[0], values[0])}'
    word = _OP_WORD.get(operator, operator)
    rendered = [_fmt_number(v) for v in values]
    if operator == '=':
        return f'{name}等于{rendered[0]}'
    if operator == '!=':
        return f'{name}不等于{rendered[0]}'
    return f'{name}{word}{rendered[0]}'


def _leaves(tree):
    if not tree:
        return []
    if tree['kind'] == 'GROUP':
        return [leaf for child in tree['children'] for leaf in _leaves(child)]
    if tree['kind'] == 'PREDICATE':
        return [tree]
    return []


def _chunks(items, size=8):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def run_l1(p0, calibration, output, k=20, limit=None, splits=None, build_id=None):
    p0, calibration, output = Path(p0), Path(calibration), Path(output)
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    cases = read_jsonl(calibration / 'cases.jsonl')
    if splits:
        # 留出集只在候选版本验收时运行：默认跑法不碰它，避免一看失败就把它转成开发资产。
        cases = [case for case in cases if case['split'] in set(splits)]
    if limit:
        cases = cases[:limit]
    client = SemanticClient()
    active = build_id or json.loads((p0 / 'manifest.json').read_text())['active_build']['build_id']
    bundle = client.bundle(active)
    fresh_directory(output)
    write_json(output / 'bundle.json', bundle)
    results = []
    for case in cases:
        tree = case['expected'].get('tree')
        leaves = [leaf for leaf in _leaves(tree) if leaf['expression']['kind'] == 'TAG']
        if not leaves:
            continue
        phrases = [_phrase(facts[leaf['expression']['tag_id']], leaf) for leaf in leaves]
        recalled, ranks = [], []
        for offset,batch in enumerate(_chunks(phrases)):
            response = client.retrieve_batch(batch, bundle['build_id'], case['eligible_tag_ids'], k=k)
            for phrase, leaf, result in zip(batch, leaves[offset*8:], response['results']):
                target = leaf['expression']['tag_id']
                ids = [c['tag_id'] for c in result.get('candidates') or []]
                rank = ids.index(target) + 1 if target in ids else None
                recalled.append(rank is not None)
                ranks.append(rank)
        coverage = all(recalled)
        results.append({'case_id': case['case_id'], 'category': case['category'],
                        'conditions': len(leaves),
                        'phrases': phrases,
                        'recalled': recalled,
                        'ranks': ranks,
                        'all_conditions_covered': coverage,
                        'atomic_recall': sum(recalled) / len(recalled)})
    by_category = {}
    for category in sorted({r['category'] for r in results}):
        rows = [r for r in results if r['category'] == category]
        by_category[category] = {
            'cases': len(rows),
            'all_covered': sum(r['all_conditions_covered'] for r in rows),
            'atomic_recall': round(sum(r['atomic_recall'] for r in rows) / len(rows), 4)}
    summary = {'layer': 'L1', 'k': k, 'bundle': bundle, 'cases': len(results),
               'conditions': sum(r['conditions'] for r in results),
               'atomic_recall_at_k': round(
                   sum(sum(r['recalled']) for r in results) / sum(r['conditions'] for r in results), 4) if results else None,
               'case_macro_atomic_recall':round(sum(r['atomic_recall'] for r in results)/len(results),4) if results else None,
               'all_conditions_covered_at_k': sum(r['all_conditions_covered'] for r in results),
               'by_category': by_category,
               'failures': [r['case_id'] for r in results if not r['all_conditions_covered']],
               'splits': sorted({case['split'] for case in cases}),
               'holdout_excluded': not any(case['split'] == 'HOLDOUT' for case in cases),
               'mode': 'fast(no-rerank) deterministic'}
    write_jsonl(output / 'l1-results.jsonl', results)
    write_json(output / 'l1-summary.json', summary)
    return summary
