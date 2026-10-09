"""从 results.jsonl 汇总 summary.json：主指标 ± Wilson 95% CI、六维分解、分组统计、成本与延迟。

主指标 = pass 率（grade 为 True 的比例），按案例聚合（同一案例的 reps 取多数/均值），
并给出去重超时/错误后的有效分母。
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from .grade import DIMS


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _pct(values, q):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, round(q * (len(values) - 1))))
    return values[idx]


def summarize(run_dir: Path, cases_index: dict | None = None) -> dict:
    results_path = run_dir / 'results.jsonl'
    rows = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()] if results_path.exists() else []
    errors_path = run_dir / 'errors.jsonl'
    errors = [json.loads(l) for l in errors_path.read_text().splitlines() if l.strip()] if errors_path.exists() else []

    # 按案例聚合（默认严格：任一 rep 未通过则案例未通过；同时报 reps 一致率）
    by_case = defaultdict(list)
    for r in rows:
        by_case[r['case_id']].append(r)
    case_pass, case_any, consistent = {}, {}, {}
    for cid, rs in by_case.items():
        vals = [r['grade'] is True for r in rs]
        case_pass[cid] = all(vals)          # 严格：全 reps 通过
        case_any[cid] = any(vals)
        consistent[cid] = len(set(vals)) == 1

    n_cases = len(by_case)
    strict_pass = sum(case_pass.values())
    any_pass = sum(case_any.values())
    lo, hi = wilson(strict_pass, n_cases)

    dims = {d: {'pass': 0, 'total': 0} for d in DIMS}
    for r in rows:
        for d, ok in (r.get('dims') or {}).items():
            dims.setdefault(d, {'pass': 0, 'total': 0})
            dims[d]['total'] += 1
            dims[d]['pass'] += 1 if ok else 0

    def group(key):
        g = defaultdict(lambda: {'cases': 0, 'pass': 0})
        for cid, rs in by_case.items():
            k = (cases_index or {}).get(cid, {}).get(key, '?')
            g[k]['cases'] += 1
            g[k]['pass'] += 1 if case_pass[cid] else 0
        return {k: {**v, 'rate': round(v['pass'] / v['cases'], 4) if v['cases'] else None}
                for k, v in sorted(g.items())}

    lat = [r['elapsed_s'] for r in rows if r.get('elapsed_s') is not None]
    costs = [float(r['cost_usd']) for r in rows if r.get('cost_usd') is not None]
    timeout = sum(1 for e in errors if e.get('failure') == 'timeout')
    layers = {}
    for name in ('l1-summary.json', 'l3-summary.json'):
        p = run_dir / name
        if p.exists():
            layers[name.split('-')[0]] = json.loads(p.read_text())
    return {
        'variant': run_dir.name,
        'cases': n_cases,
        'runs': len(rows),
        'strict_pass_cases': strict_pass,
        'strict_pass_rate': round(strict_pass / n_cases, 4) if n_cases else None,
        'strict_pass_ci95': [round(lo, 4), round(hi, 4)],
        'any_pass_cases': any_pass,
        'rep_consistency_rate': round(sum(consistent.values()) / n_cases, 4) if n_cases else None,
        'dims': {d: (round(v['pass'] / v['total'], 4) if v['total'] else None) for d, v in dims.items()},
        'errors': {'total': len(errors), 'timeout': timeout},
        'latency_s': {'p50': _pct(lat, .5), 'p95': _pct(lat, .95), 'max': max(lat) if lat else None},
        'cost_usd': {'total': round(sum(costs), 2), 'mean': round(sum(costs) / len(costs), 4) if costs else None},
        'by_difficulty': group('difficulty'),
        'by_scenario': group('scenario'),
        'layers': layers,
    }


def build_index(cases_path: Path) -> dict:
    idx = {}
    for line in Path(cases_path).read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            idx[c['case_id']] = c
    return idx


def main(run_dir: str, cases_path: str | None = None):
    run = Path(run_dir)
    index = build_index(Path(cases_path)) if cases_path else None
    summary = summarize(run, index)
    (run / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    import sys
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
