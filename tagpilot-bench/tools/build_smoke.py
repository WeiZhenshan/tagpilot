"""从 core + guard 抽取 smoke 子集（内环：改一次跑一次）。

覆盖每个难度与关键陷阱的代表；缺失的（尚未编写完）跳过并警告。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE_IDS = ['SC-A01', 'SC-A02', 'SC-B02', 'SC-B04', 'SC-C03', 'SC-D03', 'SC-E03',
             'SC-F03', 'SC-G02', 'SC-H01', 'SC-I01', 'SC-J04', 'GD-01']


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return {json.loads(l)['case_id']: json.loads(l) for l in path.read_text().splitlines() if l.strip()}


def main():
    pool = {}
    pool.update(_load(ROOT / 'cases/core/cases.jsonl'))
    pool.update(_load(ROOT / 'cases/guard/cases.jsonl'))
    picked, missing = [], []
    for cid in SMOKE_IDS:
        (picked if cid in pool else missing).append(pool.get(cid) or cid)
    out = ROOT / 'cases/smoke'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'cases.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in picked if isinstance(c, dict)))
    (out / 'manifest.json').write_text(json.dumps(
        {'case_count': len(picked), 'ids': SMOKE_IDS, 'missing': missing}, ensure_ascii=False, indent=1))
    print(f'smoke: {len(picked)}/{len(SMOKE_IDS)} present' + (f'; missing {missing}' if missing else ''))


if __name__ == '__main__':
    main()
