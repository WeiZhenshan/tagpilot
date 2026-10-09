"""把 61 案例条件树物化为 cases.jsonl + oracle.jsonl，并用文档人数做硬校核。

条件树来自 `cases/_source/trees/*.json`（每个文件 {case_id: {"target": tree, "contrast": tree}}）。
人数、ID 集、哈希全部由本工具实算并与文档比对；实算人数 ≠ 文档人数即判错。

用法：
  python tools/build_cases_61.py --check     # 只校核，打印逐案例 want/got
  python tools/build_cases_61.py             # 校核通过后写 cases/core/{cases,oracle}.jsonl
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tagpilot_bench import db, oracle  # noqa: E402
from tagpilot_bench.schema import Case, Expected, Tree  # noqa: E402

PARSED = ROOT / 'cases/_source/scenario_61_parsed.json'
TREES_DIR = ROOT / 'cases/_source/trees'
NON_READY = ROOT / 'cases/_source/non_ready.json'


def load_trees() -> dict:
    trees = {}
    for path in sorted(TREES_DIR.glob('*.json')):
        try:
            trees.update(json.loads(path.read_text()))
        except json.JSONDecodeError as exc:
            print(f'[warn] skip {path.name}: {exc}')
    return trees


def doc_counts(expect: str) -> dict:
    nums = {}
    m = re.search(r'目标\s*\**\s*(\d+)', expect) or re.search(r'金标准\s*\**\s*(\d+)', expect)
    if m:
        nums['target'] = int(m.group(1))
    m = re.search(r'对照\s*\**\s*(\d+)', expect)
    if m:
        nums['contrast'] = int(m.group(1))
    m = re.search(r'前置(?:通过)?\s*\**\s*(\d+)', expect)
    if m:
        nums['prefix'] = int(m.group(1))
    return nums


def evaluate_all(trees: dict, parsed: dict, rows, non_ready: dict) -> list:
    results = []
    for cid in sorted(set(trees) | set(non_ready)):
        case = parsed[cid]
        if cid in non_ready:
            results.append({'case_id': cid, 'want': {}, 'prefix': None, 'got': {},
                            'mismatch': False, 'diff': {}, 'target': None, 'contrast': None,
                            'non_ready': non_ready[cid]})
            continue
        spec = trees[cid]
        tgt = Tree.model_validate(spec['target']).model_dump(exclude_none=True)
        target = oracle.fixture_result(tgt, rows)
        contrast = None
        if spec.get('contrast'):
            contrast = oracle.fixture_result(Tree.model_validate(spec['contrast']).model_dump(exclude_none=True), rows)
        want = doc_counts(case['expect'])
        got = {'target': target['count']}
        if contrast:
            got['contrast'] = contrast['count']
        # 只硬校核 target / contrast；prefix（前置通过）是共享后缀过滤，单独处理。
        want_cmp = {k: v for k, v in want.items() if k in ('target', 'contrast')}
        diff = {k: (want_cmp.get(k), got.get(k)) for k in want_cmp if want_cmp.get(k) != got.get(k)}
        results.append({'case_id': cid, 'want': want, 'prefix': want.get('prefix'), 'got': got,
                        'mismatch': bool(diff), 'diff': diff, 'target': target, 'contrast': contrast,
                        'non_ready': None})
    return results


def main():
    check_only = '--check' in sys.argv
    only = None
    for i, a in enumerate(sys.argv):
        if a == '--only' and i + 1 < len(sys.argv):
            only = set(sys.argv[i + 1].split(','))
    trees = load_trees()
    parsed = json.loads(PARSED.read_text())
    non_ready = json.loads(NON_READY.read_text()) if NON_READY.exists() else {}
    if only:
        trees = {k: v for k, v in trees.items() if k in only}
        non_ready = {k: v for k, v in non_ready.items() if k in only}
    # 期望树的 data_kind 对齐 facts（同一字段由 facts 唯一定义）
    from tagpilot_bench.facts import load as load_facts, align_data_kind
    _facts = load_facts()
    for spec in trees.values():
        align_data_kind(spec.get('target'), _facts)
        if spec.get('contrast'):
            align_data_kind(spec['contrast'], _facts)
    if not trees and not non_ready:
        print('no trees found under', TREES_DIR)
        raise SystemExit(2)
    fields = set()
    for cid, spec in trees.items():
        if cid in non_ready:
            continue
        fields |= oracle.fields(Tree.model_validate(spec['target']).model_dump(exclude_none=True))
        if spec.get('contrast'):
            fields |= oracle.fields(Tree.model_validate(spec['contrast']).model_dump(exclude_none=True))
    rows = db.load_rows(sorted(fields))
    print(f'cases={len(set(trees) | set(non_ready))} rows={len(rows)} fields={len(fields)} non_ready={len(non_ready)}')
    results = evaluate_all(trees, parsed, rows, non_ready)
    bad = [r for r in results if r['mismatch']]
    for r in results:
        if r['non_ready']:
            print(f"{r['case_id']:5} non_ready  (期望非 READY：{r['non_ready']['note']})")
        else:
            print(f"{r['case_id']:5} {'MISMATCH' if r['mismatch'] else 'ok':9} want={r['want']} got={r['got']}"
                  + (f"  << {r['diff']}" if r['mismatch'] else ''))
    print(f"\n{len(results) - len(bad)}/{len(results)} 人数对账通过")
    if bad or check_only:
        raise SystemExit(1 if bad else 0)

    # 写物化产物
    cases, oracles = [], []
    for r in results:
        cid = r['case_id']
        c = parsed[cid]
        if r['non_ready']:
            expected = Expected(outcomes=r['non_ready']['outcomes'], forbid_ready=True)
            case_obj = Case(
                case_id=f'SC-{cid}', suite='core', source='scenario-61', scenario=c['scenario'],
                tags=[f"{cid[0]}-组", c['difficulty'].split('·')[0]], difficulty=c['difficulty'].split('·')[0],
                requirement=c['main_input'], expected=expected, oracle_ref=None,
                provenance={'authoring': 'HUMAN_DOC_STRUCTURED', 'oracle': 'HUMAN', 'verified': True,
                            'note': r['non_ready']['note']},
            )
            cases.append(case_obj.model_dump(exclude_none=True))
            continue
        spec = trees[cid]
        tgt = Tree.model_validate(spec['target'])
        expected = Expected(outcomes=['READY'], tree=tgt,
                            counts={'target': r['target']['count'],
                                    'contrast': r['contrast']['count'] if r['contrast'] else None})
        case_obj = Case(
            case_id=f'SC-{cid}', suite='core', source='scenario-61', scenario=c['scenario'],
            tags=[f"{cid[0]}-组", c['difficulty'].split('·')[0]], difficulty=c['difficulty'].split('·')[0],
            requirement=c['main_input'], expected=expected, oracle_ref=f'SC-{cid}',
            provenance={'authoring': 'HUMAN_DOC_STRUCTURED', 'oracle': 'MYSQL_RECOUNT',
                        'verified': not r['mismatch']},
        )
        cases.append(case_obj.model_dump(exclude_none=True))
        oracles.append({'case_id': f'SC-{cid}', 'count': r['target']['count'], 'ids': r['target']['ids'],
                        'ids_sha256': r['target']['ids_sha256']})
    out = ROOT / 'cases/core'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'scenario_cases.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in cases))
    (out / 'scenario_oracle.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in oracles))
    print(f'wrote {out}/scenario_cases.jsonl ({len(cases)}) and scenario_oracle.jsonl ({len(oracles)})')


if __name__ == '__main__':
    main()
