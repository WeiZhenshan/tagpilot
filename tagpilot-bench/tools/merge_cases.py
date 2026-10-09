"""合并各来源案例为 cases/core/{cases.jsonl, oracle.jsonl, manifest.json}。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'cases/core'
SOURCES = ['scenario_cases.jsonl', 'demo_cases.jsonl']
ORACLES = ['scenario_oracle.jsonl', 'demo_oracle.jsonl']


def _read(paths):
    rows = []
    for name in paths:
        p = CORE / name
        if p.exists():
            rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return rows


def main():
    cases = _read(SOURCES)
    oracles = _read(ORACLES)
    ids = [c['case_id'] for c in cases]
    assert len(ids) == len(set(ids)), f'重复 case_id: {[i for i in ids if ids.count(i) > 1]}'
    (CORE / 'cases.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases))
    (CORE / 'oracle.jsonl').write_text(''.join(json.dumps(o, ensure_ascii=False) + '\n' for o in oracles))
    manifest = {
        'case_count': len(cases),
        'oracle_count': len(oracles),
        'by_source': {s: sum(1 for c in cases if c['source'] == s) for s in ('scenario-61', 'demo-100', 'patch', 'guard')},
        'by_difficulty': {d: sum(1 for c in cases if c['difficulty'] == d)
                          for d in sorted({c['difficulty'] for c in cases})},
        'cases_sha256': hashlib.sha256((CORE / 'cases.jsonl').read_bytes()).hexdigest(),
        'oracle_sha256': hashlib.sha256((CORE / 'oracle.jsonl').read_bytes()).hexdigest(),
    }
    (CORE / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
