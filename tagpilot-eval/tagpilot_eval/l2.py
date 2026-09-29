"""L2 Agent 跑批：驱动真实 Agent（含多轮 resume），保存 EvalRun 与 EvalVerdict。

默认指向隔离的评测实例端口（TAG_AGENT_EVAL_URL，缺省 127.0.0.1:8093），
不打扰用户正在使用的 8092 开发实例。判定由 judge 独立完成，不采信 Agent 自述。
"""
import json
import time
from collections import Counter
from pathlib import Path

from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .judge import grade_case
from .runtime import AGENT_URL, AgentClient, SemanticClient
from .sources import load_ddl, load_fixture

EVAL_AGENT_URL = 'http://127.0.0.1:8093'
OWNER = 'eval-p1'
ROOT = Path(__file__).resolve().parents[2]


def _fixture_rows(p0_manifest):
    ddl = ROOT / p0_manifest['sources']['ddl']['path']
    fixture = ROOT / p0_manifest['sources']['fixture']['path']
    return load_fixture(fixture, load_ddl(ddl))


def _stages(case):
    return [case['expected']] + [t['expected'] for t in case['turns']]


def _terminal_result(state):
    result = state.get('result') or {}
    return {**result, 'status': state.get('status'), 'error': state.get('error'),
            'cancelled_by_harness': bool(state.get('cancelled_by_harness'))}


def _no_result_verdict(agent_status, result, stats):
    """没有产出任何终态：无法判定，记 RUN_INVALID 并保留可归因的终止信息。"""
    return {'status': 'RUN_INVALID', 'checks': {}, 'failures': ['NO_RESULT'],
            'evidence': {'agent_status': agent_status, 'error': result.get('error'),
                         'stop_reason': stats.get('stop_reason'),
                         'sdk_result': stats.get('sdk_result'),
                         'agent_failure': stats.get('agent_failure')}}


def _turn_evidence(state):
    """保存每一轮的终态证据，使多轮判定可在不重跑模型的情况下复现。"""
    result = state.get('result') or {}
    return {'status': state.get('status'),
            'outcome': (result.get('outcome') or {}).get('outcome'),
            'plan': result.get('plan'), 'questions': result.get('questions'),
            'interrupt_id': result.get('interrupt_id')}


def _reconstruct_first(run):
    """从保存的每轮证据还原首轮裁判输入；旧记录没有该字段时返回 None。"""
    turns = (run.get('output') or {}).get('turns') or []
    if len(turns) < 2:
        return None
    head = turns[0]
    return {'status': 'COMPLETED' if head.get('outcome') else (head.get('status') or 'FAILED'),
            'outcome': {'outcome': head['outcome']} if head.get('outcome') else None,
            'plan': head.get('plan') or {}, 'questions': head.get('questions'),
            'interrupt_id': head.get('interrupt_id')}


def _reconstruct(run):
    """从已保存的 EvalRun 还原裁判输入，用于不重新调用模型的再判定。"""
    output = run.get('output') or {}
    outcome = run.get('outcome')
    status = 'COMPLETED' if outcome else ('RUN_INVALID' if run.get('status') == 'RUN_INVALID'
                                          else 'FAILED')
    return {'status': status,
            'outcome': {'outcome': outcome, 'gaps': output.get('gaps')} if outcome else None,
            'plan': output.get('plan') or {}, 'questions': output.get('questions'),
            'interrupt_id': output.get('interrupt_id'), 'error': output.get('error')}


def _base_request(case, bundle, run_id, thread_id, requirement):
    return {'run_id': run_id, 'thread_id': thread_id, 'owner_id': OWNER, 'library_id': 107,
            'build_id': bundle['build_id'], 'snapshot_id': bundle['snapshot_id'],
            'artifact_hash': bundle['artifact_hash'],
            'eligible_tag_ids': case['eligible_tag_ids'], 'requirement': requirement,
            'reference_date': case['reference_date'], 'timezone': case['timezone']}


def _drive_case(agent, case, bundle, base_run_id, max_seconds):
    """按被测系统的多轮契约驱动：WAITING 用 resume 答澄清；否则每条新消息开新 run。

    新 run 携带 previous_plan 与 history，与 Java 客户端一致（不是复用同一 run 续问）。
    """
    thread_id = base_run_id
    request = _base_request(case, bundle, base_run_id, thread_id, case['requirement'])
    state, events = agent.run_to_terminal(request, deadline_seconds=max_seconds)
    states = [state]
    messages = [{'id': f'{base_run_id}-u0', 'role': 'user', 'text': case['requirement'],
                 'run_id': base_run_id}]
    for index, turn in enumerate(case.get('turns') or [], start=1):
        text = turn['user_message']
        if state.get('status') == 'WAITING':
            state, more = agent.resume(base_run_id, OWNER, text, case['eligible_tag_ids'],
                                       deadline_seconds=max_seconds)
        else:
            run_id = f'{base_run_id}-t{index}'
            previous = ((state.get('result') or {}).get('plan')) or {}
            request = _base_request(case, bundle, run_id, thread_id, text)
            request['previous_plan'] = previous
            request['history'] = messages[-12:]
            state, more = agent.run_to_terminal(request, deadline_seconds=max_seconds)
        events += more
        messages.append({'id': f'{base_run_id}-u{index}', 'role': 'user', 'text': text,
                         'run_id': state.get('run_id', base_run_id)})
        states.append(state)
    return states, events


def regrade(p0, calibration, output):
    """按当前裁判逻辑重判已保存的 runs.jsonl（不调用模型，不产生费用）。"""
    p0, calibration, output = Path(p0), Path(calibration), Path(output)
    runs = read_jsonl(output / 'runs.jsonl')
    cases = {c['case_id']: c for c in read_jsonl(calibration / 'cases.jsonl')}
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    rows = _fixture_rows(json.loads((p0 / 'manifest.json').read_text()))
    verdicts = []
    for run in runs:
        case = cases[run['case_id']]
        result = _reconstruct(run)
        stats = run.get('stats') or {}
        stages = _stages(case)
        if result.get('outcome'):
            verdict = grade_case(case, stages[-1], result, facts, rows)
            if len(stages) > 1:
                first = _reconstruct_first(run)
                if first is None:
                    verdict = _merge_multiturn(verdict, {'status': 'RUN_INVALID', 'failures': []}, result)
                else:
                    verdict = _merge_multiturn(verdict,
                                               grade_case(case, stages[0], first, facts, rows), result)
        else:
            verdict = _no_result_verdict(result.get('status'), result, stats)
        verdicts.append({'schema_version': 'eval-verdict.v1', 'case_id': run['case_id'],
                         'status': verdict['status'], 'checks': verdict.get('checks', {}),
                         'failures': verdict.get('failures', []), 'evidence': verdict.get('evidence', {})})
    (output / 'verdicts.jsonl').write_text(
        ''.join(json.dumps(v, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n'
                for v in verdicts))
    bundle = _json_optional(output / 'bundle.json') or {}
    summary = _summarize(bundle, runs, verdicts, {c['case_id']: c['category'] for c in cases.values()})
    summary['regraded'] = True
    (output / 'l2-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    return summary


def _json_optional(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def run_l2(p0, calibration, output, limit=None, base=EVAL_AGENT_URL, max_seconds=240):
    p0, calibration, output = Path(p0), Path(calibration), Path(output)
    cases = read_jsonl(calibration / 'cases.jsonl')
    if limit:
        cases = cases[:limit]
    facts = {r['tag_id']: r for r in read_jsonl(p0 / 'facts.jsonl')}
    p0_manifest = json.loads((p0 / 'manifest.json').read_text())
    rows = _fixture_rows(p0_manifest)
    semantic = SemanticClient()
    active = p0_manifest['active_build']['build_id']
    bundle = semantic.bundle(active)
    agent = AgentClient(base)
    # 断点续跑：已完成的 run 直接跳过，结果按行追加，长跑中断不丢进度。
    done = set()
    if (output / 'runs.jsonl').exists():
        done = {r['case_id'] for r in read_jsonl(output / 'runs.jsonl')}
    else:
        fresh_directory(output)
    runs = []
    verdicts = []
    if not (output / 'bundle.json').exists():
        write_json(output / 'bundle.json', bundle)

    for case in cases:
        if case['case_id'] in done:
            continue
        started = time.monotonic()
        run_id = f"eval-{case['case_id'].lower()}"
        stats = {}
        try:
            states, events = _drive_case(agent, case, bundle, run_id, max_seconds)
            state = states[-1]
            turn_evidence = [_turn_evidence(item) for item in states]
            result = _terminal_result(state)
            stats = ((result.get('outcome') or {}) or {}).get('stats') or {}
            stages = _stages(case)
            if result.get('outcome'):
                verdict = grade_case(case, stages[-1], result, facts, rows)
                if result.get('cancelled_by_harness'):
                    verdict['evidence'] = {**verdict.get('evidence', {}),
                                           'note': '运行超过单题时限，已取消并取回最佳草案'}
                if len(stages) > 1:
                    first = grade_case(case, stages[0], _terminal_result(states[0]), facts, rows)
                    verdict = _merge_multiturn(verdict, first, result)
            else:
                verdict = _no_result_verdict(state.get('status'), result, stats)
        except Exception as exc:  # 网络/服务异常记 RUN_INVALID，不当作失败
            result = {'status': 'RUN_INVALID', 'error': str(exc)[:300]}
            stats = {}
            verdict = {'status': 'RUN_INVALID', 'checks': {}, 'failures': ['EXCEPTION'],
                       'evidence': {'error': str(exc)[:300]}}
        elapsed = round((time.monotonic() - started) * 1000)
        stats = stats if isinstance(stats, dict) else {}
        run = {'schema_version': 'eval-run.v1', 'run_id': run_id, 'case_id': case['case_id'],
               'dataset_sha256': file_hash(calibration / 'cases.jsonl'),
               'source_revision': bundle['build_id'],
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
                          'turns': turn_evidence},
               'evidence_paths': [], 'elapsed_ms': elapsed,
               'input_tokens': (stats.get('usage') or {}).get('input_tokens', 0),
               'output_tokens': (stats.get('usage') or {}).get('output_tokens', 0),
               'actual_cost': stats.get('sdk_cost_estimate_usd'), 'stats': stats}
        runs.append(run)
        verdicts.append({'schema_version': 'eval-verdict.v1', 'case_id': case['case_id'],
                         'status': verdict['status'], 'checks': verdict.get('checks', {}),
                         'failures': verdict.get('failures', []), 'evidence': verdict.get('evidence', {})})
        _append(output / 'runs.jsonl', run)
        _append(output / 'verdicts.jsonl', verdicts[-1])
        print(f"{case['case_id']} {run['status']:10s} {str(run['outcome']):17s} {verdict['status']:11s} "
              f"{elapsed/1000:5.1f}s {','.join(verdict.get('failures', []))[:60]}", flush=True)
    all_runs = read_jsonl(output / 'runs.jsonl')
    all_verdicts = read_jsonl(output / 'verdicts.jsonl')
    summary = _summarize(bundle, all_runs, all_verdicts, {c['case_id']: c['category'] for c in cases})
    (output / 'l2-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    return summary


def _append(path, row):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')


def _status(agent_status, result, stats):
    """运行状态标签：有效环境下跑失败记 AGENT_*，不计入 RUN_INVALID。"""
    if result.get('status') == 'RUN_INVALID':
        return 'RUN_INVALID'
    if result.get('timeout'):
        return 'AGENT_TIMEOUT'
    if result.get('outcome'):
        return 'COMPLETED'
    if agent_status in {'FAILED', 'CANCELLED', 'INTERRUPTED', 'RUNNING'}:
        return 'AGENT_FAILED' if stats.get('agent_failure') else 'RUN_INVALID'
    return 'RUN_INVALID'


def _merge_multiturn(verdict, first, result):
    """多轮：首轮终态与最终终态都要与案例定义一致；首轮不匹配即失败。"""
    merged = dict(verdict)
    merged['checks'] = {**verdict.get('checks', {}), 'first_turn_expectation': first['status'] == 'PASS',
                        'final_turn_expectation': verdict['status'] == 'PASS'}
    merged['failures'] = sorted(set(verdict.get('failures', []))
                                | ({'FIRST_TURN'} if first['status'] != 'PASS' else set()))
    merged['evidence'] = {**verdict.get('evidence', {}), 'first_turn': first.get('evidence', {})}
    merged['status'] = ('RUN_INVALID' if 'RUN_INVALID' in {verdict['status'],first['status']}
                        else 'PASS' if all(merged['checks'].values()) else 'FAIL')
    return merged


def _summarize(bundle, runs, verdicts, category_of):
    by_category = {}
    for category in sorted(set(category_of.values())):
        ids = [cid for cid, value in category_of.items() if value == category]
        rows = [v for v in verdicts if v['case_id'] in ids]
        if rows:
            by_category[category] = {'cases': len(rows),
                                     'pass': sum(v['status'] == 'PASS' for v in rows),
                                     'fail': sum(v['status'] == 'FAIL' for v in rows),
                                     'run_invalid': sum(v['status'] == 'RUN_INVALID' for v in rows)}
    return {'layer': 'L2', 'bundle': bundle, 'cases': len(runs),
            'agent_states': dict(Counter(r['status'] for r in runs)),
            'outcomes': dict(Counter(str(r['outcome']) for r in runs)),
            'verdicts': dict(Counter(v['status'] for v in verdicts)),
            'failure_reasons': dict(Counter(f.split(':')[0] for v in verdicts for f in v['failures'])),
            'by_category': by_category,
            'cost_usd_estimate': round(sum(float(r['actual_cost'] or 0) for r in runs), 4),
            'elapsed_seconds': round(sum(r['elapsed_ms'] for r in runs) / 1000, 1)}
