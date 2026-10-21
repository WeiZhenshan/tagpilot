"""跑 L1 语义层（确定性、免费）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tagpilot_bench import l1  # noqa: E402
from tagpilot_bench.runner import Runtime, _token  # noqa: E402
from tagpilot_bench.semantic import SemanticClient  # noqa: E402


def main(suite: str = 'cases/core', snapshot_id: str = 'L107-20260928-006', variant: str = 'l1'):
    rt = Runtime().load(snapshot_id)
    cases = [json.loads(l) for l in (ROOT / suite / 'cases.jsonl').read_text().splitlines() if l.strip()]
    client = SemanticClient('http://127.0.0.1:8091', _token())
    out = l1.run_l1(cases, rt['build_id'], rt['library_id'], rt['eligible_tag_ids'], client)
    dest = ROOT / 'runs' / Path(suite).name / variant
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'l1-summary.json').write_text(json.dumps(out['summary'], ensure_ascii=False, indent=1))
    (dest / 'l1-results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in out['results']))
    print(json.dumps(out['summary'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:])
