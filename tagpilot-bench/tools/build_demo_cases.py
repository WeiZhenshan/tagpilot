"""把 P3 的 100 Demo 案例转成 bench 案例（DM-*）。

**oracle 从当前库重算**（MYSQL_RECOUNT），不用 P3 冻结值——实测 P3 的 100 个 oracle 中
有 12/76 与当前库差 1~4 人（P3 之后库或口径有变）；当前库才是 Java 实际执行的真值。
若重算值与 P3 不同，记入 manifest 的 drift 列表（不静默）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tagpilot_bench import db, oracle  # noqa: E402
from tagpilot_bench.schema import Case, Expected, Tree, Turn  # noqa: E402

SRC = ROOT / 'cases/_source/demo-100'


def main():
    cases = [json.loads(l) for l in (SRC / 'cases.jsonl').read_text().splitlines() if l.strip()]
    p3 = {json.loads(l)['case_id']: json.loads(l)
          for l in (SRC / 'oracle-results.jsonl').read_text().splitlines() if l.strip()}

    fields = set()
    for c in cases:
        t = c['expected'].get('tree')
        if t:
            fields |= oracle.fields(t)
    rows = db.load_rows(sorted(fields))
    print(f'loaded {len(rows)} rows, {len(fields)} fields')

    from tagpilot_bench.facts import load as load_facts, align_data_kind
    _facts = load_facts()

    out_cases, out_oracle, errors, drift = [], [], [], []
    for c in cases:
        try:
            exp = c['expected']
            align_data_kind(exp.get('tree'), _facts)
            for t in c.get('turns') or []:
                align_data_kind(t.get('expected', {}).get('tree'), _facts)
            tree = Tree.model_validate(exp['tree']) if exp.get('tree') else None
            turns = [Turn(user_message=t['user_message'], expected=Expected(
                outcomes=t['expected']['outcomes'],
                tree=Tree.model_validate(t['expected']['tree']) if t['expected'].get('tree') else None,
                clarify_slots=t['expected'].get('required_slots', []), gap_codes=t['expected'].get('gap_codes', [])))
                for t in c.get('turns') or []]
            expected = Expected(outcomes=exp['outcomes'], tree=tree,
                                clarify_slots=exp.get('required_slots', []), gap_codes=exp.get('gap_codes', []))
            cid = f"DM-{c['case_id'].split('-')[-1]}"
            case = Case(case_id=cid, suite='core', source='demo-100', scenario=c.get('scenario') or 'demo',
                        tags=[c.get('scenario') or 'demo', c.get('category', '?')], difficulty='直达',
                        requirement=c['requirement'], turns=turns,
                        reference_date=c.get('reference_date', '2026-09-18'), timezone=c.get('timezone', 'Asia/Shanghai'),
                        expected=expected, oracle_ref=cid,
                        provenance={'authoring': 'P3_DEMO', 'oracle': 'MYSQL_RECOUNT', 'verified': True})
            out_cases.append(case.model_dump(exclude_none=True))
            if tree is not None:
                res = oracle.fixture_result(tree.model_dump(exclude_none=True), rows)
                out_oracle.append({'case_id': cid, 'count': res['count'], 'ids': res['ids'], 'ids_sha256': res['ids_sha256']})
                p3c = p3.get(c['case_id'], {}).get('count')
                if p3c is not None and p3c != res['count']:
                    drift.append({'case_id': cid, 'p3': p3c, 'recount': res['count']})
        except Exception as exc:  # noqa: BLE001
            errors.append({'case_id': c.get('case_id'), 'error': f'{type(exc).__name__}: {exc}'[:200]})

    out = ROOT / 'cases/core'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'demo_cases.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in out_cases))
    (out / 'demo_oracle.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in out_oracle))
    (out / 'demo_drift.json').write_text(json.dumps(drift, ensure_ascii=False, indent=1))
    print(f'demo cases: {len(out_cases)}, oracles: {len(out_oracle)}, errors: {len(errors)}, drift vs P3: {len(drift)}')
    for e in errors[:8]:
        print('  err', e)


if __name__ == '__main__':
    main()
