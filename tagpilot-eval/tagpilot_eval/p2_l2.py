"""P2 分层 L2 基线与稳定性复跑。

与 P1 的 `run_l2` 的差别，都是复核查出来的必需项：
1. **不碰 HOLDOUT**：样本只从 DEV + REGRESSION 抽（方案 §四：留出集只在候选版本验收时运行）。
2. **复跑必须换 run_id**：Agent 对同一 `(run_id, owner, thread)` 的字节相同请求会幂等返回、
   根本不重跑（`run_store.py`）；沿用同一 run_id 的「三次复跑」只会拿到同一份结果，
   得出假的 100% 稳定性。这里 run_id 与 thread_id 都带 `-r{n}`，断点键也用 `(case_id, repeat)`。
3. **同 thread 的 WAITING 会 409**：换 thread 同时避免了后续复跑被上一个 WAITING 运行挡住。
"""
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .judge import grade_case
from .l2 import (EVAL_AGENT_URL, OWNER, _append, _drive_case, _merge_multiturn, _status,
                 _terminal_result, _turn_evidence, _fixture_rows, _stages)
from .oracle import normalized
from .runtime import AgentClient, SemanticClient

STABILITY_REPEATS = 3
STABILITY_CASES = 100


def run_id_for(dataset_sha, case_id, repeat):
    """复跑必须拿到互不相同的 run_id 与 thread_id。

    Agent 对同一 `(run_id, owner, thread)` 的字节相同请求会幂等返回、根本不重跑；
    若三次复跑共用一个 run_id，稳定性统计只会得到同一份结果的三个副本。
    """
    return f"eval-{dataset_sha[:8]}-{case_id.lower()}-r{repeat}"


def _largest_remainder(population, target):
    """按人口比例分配 target 个名额，用最大余数法凑够精确总数。"""
    total = sum(population.values())
    if total == 0:
        return {}
    exact = {key: target * count / total for key, count in population.items()}
    quotas = {key: min(int(value), population[key]) for key, value in exact.items()}
    remainder = sorted(population, key=lambda key: (-(exact[key] - int(exact[key])), key))
    index = 0
    while sum(quotas.values()) < target and index < len(remainder) * 8:
        key = remainder[index % len(remainder)]
        if quotas[key] < population[key]:
            quotas[key] += 1
        index += 1
    return quotas


def stratified_sample(cases, target=500, allowed_splits=('DEV', 'REGRESSION')):
    """按「类别 × 分区」分层抽样；同层内按 case_id 摘要排序，确定可复现。"""
    allowed = [case for case in cases if case['split'] in allowed_splits]
    if len(allowed) < target:
        raise ValueError(f'可用案例不足：需要 {target}，仅 {len(allowed)}')
    strata = defaultdict(list)
    for case in allowed:
        strata[(case['category'], case['split'])].append(case)
    quotas = _largest_remainder({key: len(rows) for key, rows in strata.items()}, target)
    chosen = []
    for key in sorted(strata):
        rows = sorted(strata[key], key=lambda case: digest(case['case_id']))
        chosen.extend(rows[:quotas[key]])
    return sorted(chosen, key=lambda case: digest(case['case_id']))


def stability_selection(cases, sample_ids, count=STABILITY_CASES):
    """稳定性复跑案例：从 REGRESSION 分层选固定案例，优先选未进入 500 样本的。"""
    regression = [case for case in cases if case['split'] == 'REGRESSION']
    remaining = [case for case in regression if case['case_id'] not in sample_ids]
    pool = remaining if len(remaining) >= count else regression
    strata = defaultdict(list)
    for case in pool:
        strata[case['category']].append(case)
    quotas = _largest_remainder({key: len(rows) for key, rows in strata.items()}, count)
    chosen = []
    for key in sorted(strata):
        rows = sorted(strata[key], key=lambda case: digest(case['case_id']))
        chosen.extend(rows[:quotas[key]])
    return sorted(chosen, key=lambda case: digest(case['case_id']))


def _plan_signature(run):
    """语义结果签名：终态 + 规范树的摘要。非 READY 只比终态。"""
    plan = ((run.get('output') or {}).get('plan') or {})
    tree = plan.get('tree') if isinstance(plan, dict) else None
    try:
        normalized_tree = normalized(tree) if tree else None
    except Exception:
        normalized_tree = {'unparsed': json.dumps(tree, ensure_ascii=False, sort_keys=True)[:500]}
    return digest({'outcome': run.get('outcome'),
                   'tree': normalized_tree,
                   'questions': len(((run.get('output') or {}).get('questions') or []))})


def stability_report(runs):
    """稳定性：同一案例三次运行的语义结果一致率。"""
    grouped = defaultdict(list)
    for run in runs:
        if run.get('repeat'):
            grouped[(run['case_id'], run.get('repeat'))] = run
    by_case = defaultdict(dict)
    for (case_id, repeat), run in grouped.items():
        by_case[case_id][repeat] = run
    consistent = 0
    detail = []
    for case_id, repeats in sorted(by_case.items()):
        if len(repeats) < STABILITY_REPEATS:
            detail.append({'case_id': case_id, 'repeats': len(repeats), 'consistent': False,
                           'reason': '复跑次数不足'})
            continue
        signatures = {_plan_signature(repeats[index]) for index in sorted(repeats)}
        ok = len(signatures) == 1
        consistent += ok
        detail.append({'case_id': case_id, 'repeats': len(repeats), 'consistent': ok,
                       'distinct_results': len(signatures),
                       'run_ids': [repeats[index]['run_id'] for index in sorted(repeats)]})
    total = len(by_case)
    return {'cases': total, 'consistent': consistent,
            'consistency_rate': round(consistent / total, 4) if total else None,
            'detail': detail}


def apply_agent_failure(verdict, result, stats):
    """Agent 在**有效环境**里没跑出终态（超时／自身失败）应记为运行失败，不是 RUN_INVALID。

    方案 §三.5：只有环境不可用、裁判崩溃、模型鉴权失败才算无效运行；耗尽预算属运行失败，
    不能从总体成功率里删掉。旧逻辑只按「状态非终态」就记 RUN_INVALID，会把失败洗成无效。
    """
    if verdict.get('status') != 'RUN_INVALID':
        return verdict
    non_terminal = any(str(f).startswith('RUN_NOT_TERMINAL') for f in verdict.get('failures') or [])
    if not non_terminal or not (stats or {}).get('agent_failure'):
        return verdict
    return {'status': 'FAIL', 'checks': dict(verdict.get('checks') or {}),
            'failures': sorted({*(verdict.get('failures') or ['RUN_NOT_TERMINAL']), 'AGENT_NOT_TERMINAL'}),
            'evidence': {**(verdict.get('evidence') or {}),
                         'stop_reason': (stats or {}).get('stop_reason'),
                         'note': 'Agent 未产出终态（超时或自身失败），按运行失败计入分母'}}


def regrade(output):
    """按当前判定逻辑重算已保存的 verdicts（不调用模型，不产生费用）。"""
    output = Path(output)
    verdicts = read_jsonl(output / 'verdicts.jsonl')
    runs = {(r['case_id'], r.get('repeat', 0)): r for r in read_jsonl(output / 'runs.jsonl')}
    updated = []
    for verdict in verdicts:
        run = runs.get((verdict['case_id'], verdict.get('repeat', 0)), {})
        fixed = apply_agent_failure(verdict, {}, run.get('stats') or {})
        updated.append({**verdict, 'status': fixed['status'], 'checks': fixed.get('checks') or {},
                        'failures': fixed.get('failures') or [],
                        'evidence': fixed.get('evidence') or {}})
    (output / 'verdicts.jsonl').write_text(
        ''.join(json.dumps(v, ensure_ascii=False, sort_keys=True) + '\n' for v in updated))
    # 判定改了，汇总也要跟着重算，否则报告里读到的还是旧口径。
    index = json.loads((output / 'case-index.json').read_text()) \
        if (output / 'case-index.json').exists() else {}
    sample = json.loads((output / 'sample.json').read_text()) \
        if (output / 'sample.json').exists() else {}
    summary = _summarize_p2(json.loads((output / 'bundle.json').read_text()), runs=read_jsonl(output / 'runs.jsonl'),
                            verdicts=updated, sample_ids=sample.get('sample_case_ids', []),
                            stability_ids=sample.get('stability_case_ids', []), index=index)
    summary['regraded'] = True
    (output / 'l2-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    # 判定与汇总都改了，清单哈希要跟着刷新，否则下游 verify_package 会认为工件被改动。
    previous = json.loads((output / 'manifest.json').read_text()) \
        if (output / 'manifest.json').exists() else {}
    (output / 'manifest.json').write_text(json.dumps({
        **{k: v for k, v in previous.items() if k != 'files'},
        'status': 'REGRADED',
        'runs': len(read_jsonl(output / 'runs.jsonl')),
        'files': {p.name: file_hash(p) for p in output.iterdir()
                  if p.is_file() and p.name != 'manifest.json'}}, ensure_ascii=False, indent=2) + '\n')
    return {'regraded': len(updated), 'statuses': dict(Counter(v['status'] for v in updated)),
            'sample_verdicts': summary.get('sample_verdicts')}


def run_p2_l2(p0, cases_dir, output, base=EVAL_AGENT_URL, max_seconds=240,
              sample_target=500, stability_cases=STABILITY_CASES, sdk_cap_usd=110.0, limit=None,
              authorization=None):
    """L2 分层基线 + 稳定性复跑；追加式、可续跑、按 SDK 等价估值硬停。"""
    p0, cases_dir, output = Path(p0), Path(cases_dir), Path(output)
    cases = read_jsonl(cases_dir / 'cases.jsonl')
    sample = stratified_sample(cases, sample_target)
    sample_ids = {case['case_id'] for case in sample}
    stability = stability_selection(cases, sample_ids, stability_cases)
    schedule = ([(case, 0) for case in sample]
                + [(case, repeat) for case in stability for repeat in range(1, STABILITY_REPEATS + 1)])
    if limit:
        schedule = schedule[:limit]

    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    p0_manifest = json.loads((p0 / 'manifest.json').read_text())
    rows = _fixture_rows(p0_manifest)
    bundle = SemanticClient().bundle(p0_manifest['active_build']['build_id'])
    agent = AgentClient(base)

    runs_path = output / 'runs.jsonl'
    if runs_path.exists():
        done = {(row['case_id'], row.get('repeat', 0)) for row in read_jsonl(runs_path)}
    else:
        fresh_directory(output)
        done = set()
    if not (output / 'bundle.json').exists():
        write_json(output / 'bundle.json', bundle)
    # 只在首次写出抽样与索引：续跑时这两份已存在，create-only 写入会直接报错。
    if not (output / 'sample.json').exists():
        write_json(output / 'sample.json', {
            'schema_version': 'p2-l2-sample.v1', 'requested': sample_target, 'selected': len(sample),
            'allowed_splits': ['DEV', 'REGRESSION'],
            'sample_by_split': dict(Counter(case['split'] for case in sample)),
            'sample_by_category': dict(Counter(case['category'] for case in sample)),
            'stability_cases': len(stability), 'stability_repeats': STABILITY_REPEATS,
            'stability_overlap_with_sample': len(sample_ids & {c['case_id'] for c in stability}),
            'sample_case_ids': [case['case_id'] for case in sample],
            'stability_case_ids': [case['case_id'] for case in stability]})
    index = {case['case_id']: {'split': case['split'], 'category': case['category']}
             for case in cases}
    if not (output / 'case-index.json').exists():
        write_json(output / 'case-index.json', index)

    dataset_sha = file_hash(cases_dir / 'cases.jsonl')
    existing_runs = read_jsonl(runs_path) if runs_path.exists() else []
    # 累计花费要在循环里**逐次更新**：只在批次开始时判定一次会让单批无限跑下去、突破上限。
    spent = sum(float(row.get('actual_cost') or 0) for row in existing_runs)
    executed, stopped = 0, None
    for case, repeat in schedule:
        if limit is not None and executed >= limit:
            stopped = 'LIMIT'
            break
        if spent >= sdk_cap_usd:
            stopped = 'SDK_BUDGET_CAP'
            break
        if (case['case_id'], repeat) in done:
            continue
        base_run_id = run_id_for(dataset_sha, case['case_id'], repeat)
        started = time.monotonic()
        stats = {}
        try:
            states, _ = _drive_case(agent, case, bundle, base_run_id, max_seconds)
            state = states[-1]
            result = _terminal_result(state)
            stats = ((result.get('outcome') or {}) or {}).get('stats') or {}
            stages = _stages(case)
            if result.get('outcome'):
                verdict = grade_case(case, stages[-1], result, facts, rows)
                if len(stages) > 1:
                    first = grade_case(case, stages[0], _terminal_result(states[0]), facts, rows)
                    verdict = _merge_multiturn(verdict, first, result)
            else:
                from .l2 import _no_result_verdict
                verdict = _no_result_verdict(state.get('status'), result, stats)
            # 有效环境里没跑出终态算运行失败（计入分母），不算无效运行。
            verdict = apply_agent_failure(verdict, result, stats)
        except Exception as exc:
            result = {'status': 'RUN_INVALID', 'error': str(exc)[:300]}
            stats = {}
            verdict = {'status': 'RUN_INVALID', 'checks': {}, 'failures': ['EXCEPTION'],
                       'evidence': {'error': str(exc)[:300]}}
        elapsed = round((time.monotonic() - started) * 1000)
        stats = stats if isinstance(stats, dict) else {}
        run = {'schema_version': 'eval-run.v1', 'run_id': base_run_id, 'case_id': case['case_id'],
               'repeat': repeat, 'dataset_sha256': dataset_sha, 'source_revision': bundle['build_id'],
               'model': stats.get('model'), 'prompt_sha256': None,
               'snapshot_id': bundle['snapshot_id'], 'build_id': bundle['build_id'],
               'artifact_hash': bundle['artifact_hash'],
               'eligible_sha256': digest(sorted(case['eligible_tag_ids'])),
               'reference_date': case['reference_date'],
               'status': _status(state.get('status'), result, stats),
               'outcome': (result.get('outcome') or {}).get('outcome'),
               'output': {'plan': result.get('plan'), 'questions': result.get('questions'),
                          'gaps': (result.get('outcome') or {}).get('gaps'),
                          'interrupt_id': result.get('interrupt_id'), 'error': result.get('error'),
                          'turns': [_turn_evidence(item) for item in states]},
               'evidence_paths': [], 'elapsed_ms': elapsed,
               'input_tokens': (stats.get('usage') or {}).get('input_tokens', 0),
               'output_tokens': (stats.get('usage') or {}).get('output_tokens', 0),
               'actual_cost': stats.get('sdk_cost_estimate_usd'), 'stats': stats}
        _append(runs_path, run)
        _append(output / 'verdicts.jsonl', {
            'schema_version': 'eval-verdict.v1', 'case_id': case['case_id'], 'repeat': repeat,
            'status': verdict['status'], 'checks': verdict.get('checks', {}),
            'failures': verdict.get('failures', []), 'evidence': verdict.get('evidence', {})})
        spent += float(run.get('actual_cost') or 0)
        executed += 1
        print(f"{case['case_id']} r{repeat} {run['status']:10s} {str(run['outcome']):17s} "
              f"{verdict['status']:11s} {elapsed/1000:5.1f}s", flush=True)

    all_runs = read_jsonl(runs_path)
    all_verdicts = read_jsonl(output / 'verdicts.jsonl')
    sample_ids = [case['case_id'] for case in sample]
    stability_ids = [case['case_id'] for case in stability]
    summary = _summarize_p2(bundle, all_runs, all_verdicts, sample_ids, stability_ids, index)
    summary['stopped'] = stopped
    summary['executed'] = executed
    summary['sdk_cap_usd'] = sdk_cap_usd
    (output / 'l2-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    # 清单每次重写（续跑会再写一次），但其内容只列其他工件的 hash，因此不影响校验。
    (output / 'manifest.json').write_text(json.dumps({
        'schema_version': 'p2-l2.v1', 'phase': 'P2', 'status': 'MEASURED',
        'runs': len(all_runs), 'sampled_cases': len(sample_ids),
        'stability_cases': len(stability_ids), 'stability_repeats': STABILITY_REPEATS,
        'sdk_cap_usd': sdk_cap_usd, 'stopped': stopped, 'dataset_sha256': dataset_sha,
        'agent_url': base, 'authorization': authorization,
        'files': {p.name: file_hash(p) for p in output.iterdir()
                  if p.is_file() and p.name != 'manifest.json'}}, ensure_ascii=False, indent=2) + '\n')
    return summary


def _summarize_p2(bundle, runs, verdicts, sample_ids, stability_ids, index):
    sample_verdicts = [v for v in verdicts if v['case_id'] in set(sample_ids) and not v.get('repeat')]
    by_category, by_split = {}, {}
    for group_key, title in (('category', by_category), ('split', by_split)):
        for name in sorted({index[v['case_id']][group_key] for v in sample_verdicts if v['case_id'] in index}):
            rows = [v for v in sample_verdicts if index.get(v['case_id'], {}).get(group_key) == name]
            if rows:
                title[name] = {'cases': len(rows),
                               'pass': sum(v['status'] == 'PASS' for v in rows),
                               'fail': sum(v['status'] == 'FAIL' for v in rows),
                               'run_invalid': sum(v['status'] == 'RUN_INVALID' for v in rows)}
    return {'layer': 'L2', 'bundle': bundle,
            'runs': len(runs), 'sampled_cases': len(sample_ids), 'stability_cases': len(stability_ids),
            'agent_states': dict(Counter(r['status'] for r in runs)),
            'outcomes': dict(Counter(str(r['outcome']) for r in runs)),
            'verdicts': dict(Counter(v['status'] for v in verdicts)),
            'sample_verdicts': dict(Counter(v['status'] for v in sample_verdicts)),
            'failure_reasons': dict(Counter(f.split(':')[0] for v in verdicts for f in v['failures'])),
            'by_category': by_category, 'by_split': by_split,
            'stability': stability_report(runs),
            'cost_usd_estimate': round(sum(float(r.get('actual_cost') or 0) for r in runs), 4),
            'elapsed_seconds': round(sum(r['elapsed_ms'] for r in runs) / 1000, 1)}
