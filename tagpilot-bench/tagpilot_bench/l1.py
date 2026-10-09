"""L1 语义层：把标准树的每个原子条件渲染成中文短语，查 /retrieve_batch，看目标标签是否进 top-K。

确定性、免费；只跑「标准树」——不涉及被测 Agent。用于每次语义/索引改动后的必跑回归。
"""
from __future__ import annotations

from pathlib import Path

from .facts import load as load_facts
from .oracle import references
from .semantic import SemanticClient

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


def _phrase(fact, node) -> str:
    name = fact['tag_name']
    op, values = node['operator'], node['values']
    if op in {'is_null', 'is_not_null'}:
        return f'{name}{"为空" if op == "is_null" else "不为空"}'
    if op in {'in', 'not_in'}:
        joined = '、'.join(values)
        return f'{name}{"属于" if op == "in" else "不属于"}{joined}'
    if op == 'between':
        return f'{name}在{values[0]}到{values[1]}之间'
    if op == 'contains':
        return f'{name}包含{values[0]}'
    if node['data_kind'] == 'STRING':
        return f'{name}{"是" if op == "=" else "不是"}{values[0]}'
    word = _OP_WORD.get(op, op)
    rendered = _fmt_number(values[0])
    if op == '=':
        return f'{name}等于{rendered}'
    if op == '!=':
        return f'{name}不等于{rendered}'
    return f'{name}{word}{rendered}'


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


def run_l1(cases, build_id: str, library_id: int, eligible_tag_ids, client: SemanticClient,
           k: int = 20, facts: dict | None = None) -> dict:
    facts = facts if facts is not None else load_facts()
    results = []
    for case in cases:
        tree = case['expected'].get('tree')
        leaves = [leaf for leaf in _leaves(tree) if leaf['expression']['kind'] == 'TAG']
        if not leaves:
            continue
        phrases, recalled, ranks = [], [], []
        for offset, batch in enumerate(_chunks([_phrase(facts[leaf['expression']['tag_id']], leaf) for leaf in leaves])):
            phrases.extend(batch)
            response = client.retrieve_batch(batch, build_id, library_id, eligible_tag_ids, k=k)
            for leaf, result in zip(leaves[offset * 8:], response['results']):
                target = leaf['expression']['tag_id']
                ids = [c['tag_id'] for c in (result.get('candidates') or [])]
                rank = ids.index(target) + 1 if target in ids else None
                recalled.append(rank is not None)
                ranks.append(rank)
        results.append({'case_id': case['case_id'], 'conditions': len(leaves), 'phrases': phrases,
                        'recalled': recalled, 'ranks': ranks,
                        'all_conditions_covered': all(recalled),
                        'atomic_recall': sum(recalled) / len(recalled)})
    total_conditions = sum(r['conditions'] for r in results)
    summary = {
        'layer': 'L1', 'k': k, 'build_id': build_id, 'cases': len(results),
        'conditions': total_conditions,
        'atomic_recall_at_k': round(sum(sum(r['recalled']) for r in results) / total_conditions, 4) if total_conditions else None,
        'case_macro_atomic_recall': round(sum(r['atomic_recall'] for r in results) / len(results), 4) if results else None,
        'all_conditions_covered_at_k': sum(r['all_conditions_covered'] for r in results),
        'failures': [r['case_id'] for r in results if not r['all_conditions_covered']],
        'mode': 'fast(no-rerank) deterministic',
    }
    return {'summary': summary, 'results': results}
