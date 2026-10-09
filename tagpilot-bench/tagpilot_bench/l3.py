"""L3 执行层：对 READY 案例比对**完整客户 ID 集**。

- 有 Java 令牌时：走权威链（编译计划 → 执行 COUNT → 用同一 Java SQL 换投影取完整 ID 集）。
- 无令牌时：回退本地 oracle（同一份库数据、同一棵树 → 同一 ID 集），标 `authority=LOCAL_ORACLE`。

两者都以 case 的 oracle（完整 ID 集）为准；COUNT 相同不充分，必须 ID 集相等。
"""
from __future__ import annotations

import json
from pathlib import Path

from . import adapter, db, oracle
from .facts import load as load_facts
from .grade import strip_caliber

ROOT = Path(__file__).resolve().parents[1]


def _agent_tree_from_trace(trace):
    states = [x['state'] for x in trace if isinstance(x, dict) and 'state' in x]
    if not states:
        return None, None, None
    result = states[-1].get('result') or {}
    plan = result.get('plan') or {}
    return (result.get('outcome') or {}).get('outcome'), plan.get('tree'), plan


def run_l3(cases: dict, run_dir: Path, facts: dict | None = None, java_client=None) -> dict:
    facts = facts if facts is not None else load_facts()
    oracles = {}
    opath = ROOT / 'cases/core/oracle.jsonl'
    if opath.exists():
        oracles = {json.loads(l)['case_id']: json.loads(l) for l in opath.read_text().splitlines() if l.strip()}
    rows_cache = {}

    def rows_for(tree):
        key = tuple(sorted(oracle.fields(tree)))
        if key not in rows_cache:
            # 空字段集（SCOPE_ALL）也要加载全部 CUST_ID，否则两边都空会空洞通过
            rows_cache[key] = db.load_rows(list(key))
        return rows_cache[key]

    results = []
    for trace_path in sorted((run_dir / 'traces').glob('*_r*.json')):
        cid, rep = trace_path.stem.rsplit('_r', 1)
        case = cases.get(cid)
        if not case or case['expected'].get('forbid_ready') or not case['expected'].get('tree'):
            continue
        oracle_rec = oracles.get(cid)
        if not oracle_rec:
            continue
        outcome, tree, plan = _agent_tree_from_trace(json.loads(trace_path.read_text()))
        # L3 只对 Agent 自报 READY 的运行有意义：非 READY 没有可执行计划，L2 已判负
        if outcome != 'READY':
            results.append({'case_id': cid, 'rep': int(rep), 'status': 'SKIP', 'reason': f'agent_outcome={outcome}'})
            continue
        if not tree:
            results.append({'case_id': cid, 'rep': int(rep), 'status': 'FAIL', 'reason': 'READY 但无计划树'})
            continue
        try:
            if java_client is not None and java_client.available:
                # 传完整计划（Java 编译器校验 build_id/snapshot_id/artifact_hash 信封）
                compiled = java_client.compile_plan(107, plan)
                actual = java_client.run_group(107, compiled['rule'])
                sql = compiled.get('count_sql', '')
                ids = []
                if sql.lower().startswith('select count(*) from'):
                    proj = 'select `CUST_ID`' + sql[len('select count(*)'):]
                    ids = sorted(db.raw_ids(proj))
                equal = ids == oracle_rec['ids'] and actual.get('count') == oracle_rec['count']
                results.append({'case_id': cid, 'rep': int(rep), 'status': 'PASS' if equal else 'FAIL',
                                'authority': 'JAVA', 'java_count': actual.get('count'),
                                'oracle_count': oracle_rec['count'], 'full_id_set_equal': ids == oracle_rec['ids']})
            else:
                act = adapter.to_eval_tree(tree, facts)
                res = oracle.fixture_result(act, rows_for(act))
                results.append({'case_id': cid, 'rep': int(rep),
                                'status': 'PASS' if res['ids'] == oracle_rec['ids'] else 'FAIL',
                                'authority': 'LOCAL_ORACLE', 'count': res['count'],
                                'oracle_count': oracle_rec['count'], 'full_id_set_equal': res['ids'] == oracle_rec['ids']})
        except Exception as exc:  # noqa: BLE001
            # 计划不可读/语义非法 = 模型问题 → FAIL；环境问题才 RUN_INVALID
            from .adapter import AdapterError
            status = 'FAIL' if isinstance(exc, AdapterError) else 'RUN_INVALID'
            results.append({'case_id': cid, 'rep': int(rep), 'status': status, 'error': str(exc)[:300]})

    n = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    summary = {'layer': 'L3', 'cases': n, 'pass': passed, 'rate': round(passed / n, 4) if n else None,
               'authority': 'JAVA' if (java_client and java_client.available) else 'LOCAL_ORACLE',
               'statuses': {s: sum(1 for r in results if r['status'] == s) for s in {r['status'] for r in results}}}
    (run_dir / 'l3-results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in results))
    (run_dir / 'l3-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return summary
