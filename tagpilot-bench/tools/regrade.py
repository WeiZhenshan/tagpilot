"""离线重判：用当前判定器重算 results.jsonl 的 grade/dims，不重新调用模型。

判定逻辑改动后用它刷新结果，避免重跑花钱。**就地更新 results.jsonl**（保留运行元数据），
这样 report/compare 读到的一定是当前判定器的结论。另存 regrade.jsonl 供对照。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tagpilot_bench import db, oracle  # noqa: E402
from tagpilot_bench.facts import load as load_facts  # noqa: E402
from tagpilot_bench.grade import grade_states  # noqa: E402


def load_cases() -> dict:
    cases = {}
    for suite in ('core', 'guard', 'smoke'):
        p = ROOT / f'cases/{suite}/cases.jsonl'
        if p.exists():
            cases.update({json.loads(l)['case_id']: json.loads(l) for l in p.read_text().splitlines() if l.strip()})
    return cases


def main(run_dir: str):
    run = Path(run_dir)
    if not run.is_absolute():
        run = ROOT / run
    cases = load_cases()
    facts = load_facts()
    rows_cache = {}

    def rows_for(expected):
        tree = expected.get('tree') if isinstance(expected, dict) else None
        key = tuple(sorted(oracle.fields(tree))) if tree else ()
        if key not in rows_cache:
            rows_cache[key] = db.load_rows(list(key))  # 空字段集也加载全部 CUST_ID
        return rows_cache[key]

    results_path = run / 'results.jsonl'
    rows = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()]
    for row in rows:
        cid = row['case_id']
        trace_path = run / 'traces' / f"{cid}_r{row['rep']}.json"
        if not trace_path.exists():
            continue
        trace = json.loads(trace_path.read_text())
        states = [x['state'] for x in trace if isinstance(x, dict) and 'state' in x]
        graded = grade_states(cases[cid], states, facts, rows_for)
        row['grade'] = graded['pass']
        row['dims'] = graded['dims']
        row['verdict'] = graded['status']
        row['failures'] = graded['failures']
        row['first_turn'] = graded.get('first_turn')
        row['final_turn'] = graded.get('final_turn')
    results_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    n = sum(1 for r in rows if r['grade'] is True)
    print(f'{len(rows)} rows re-graded in place, {n} pass')


if __name__ == '__main__':
    main(sys.argv[1])
