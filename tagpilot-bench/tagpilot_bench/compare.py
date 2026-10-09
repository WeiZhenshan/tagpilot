"""差分：baseline 与各 variant 的逐案例对比（改善/回归/不变）+ 主指标差值 vs 噪声地板。"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .report import summarize, wilson


def _cases(run_dir: Path) -> dict:
    path = run_dir / 'results.jsonl'
    if not path.exists():
        return {}
    by_case = defaultdict(list)
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            by_case[r['case_id']].append(r['grade'] is True)
    return {cid: all(v) for cid, v in by_case.items()}


def compare(suite_dir: Path, baseline: str = 'baseline') -> dict:
    base = _cases(suite_dir / baseline)
    variants = {}
    for child in sorted(suite_dir.iterdir()):
        if not child.is_dir() or child.name == baseline or child.name.startswith('.'):
            continue
        if not (child.name == 'baseline' or child.name.startswith('v')):
            continue
        variants[child.name] = _cases(child)
    report = {'baseline': baseline, 'baseline_cases': len(base), 'variants': {}}
    for name, cases in variants.items():
        common = sorted(set(base) & set(cases))
        improved = [c for c in common if cases[c] and not base[c]]
        regressed = [c for c in common if base[c] and not cases[c]]
        base_rate = sum(base[c] for c in common) / len(common) if common else None
        var_rate = sum(cases[c] for c in common) / len(common) if common else None
        lo, hi = wilson(sum(cases[c] for c in common), len(common)) if common else (0, 1)
        report['variants'][name] = {
            'common_cases': len(common),
            'baseline_rate': round(base_rate, 4) if base_rate is not None else None,
            'variant_rate': round(var_rate, 4) if var_rate is not None else None,
            'delta': round(var_rate - base_rate, 4) if (var_rate is not None and base_rate is not None) else None,
            'ci95_half_width': round((hi - lo) / 2, 4) if common else None,
            'improved': improved, 'regressed': regressed,
        }
    return report


def main(suite_dir: str):
    report = compare(Path(suite_dir))
    (Path(suite_dir) / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
