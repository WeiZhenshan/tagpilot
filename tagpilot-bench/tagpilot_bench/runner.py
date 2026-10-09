"""Runner：驱动真实 Agent 跑案例、按 reps 重复、逐案例落盘、判定、可断点续跑。

设计要点（教训来自旧体系）：
- 复跑必须换 run_id（Agent 对同 run_id 幂等，会造成假 100% 稳定）。
- 多轮：WAITING → resume(answer)；其余新用户消息 → 新 run 携带 previous_plan（见 JUDGE-AUDIT F7）。
- per-case 硬超时独立于流活性；超时进 errors.jsonl，不占语义位。
- 429/5xx 抖动退避；失败尝试也计费。
- 先固定 (snapshot,build,artifact_hash,eligible) 再跑；结束核对。

用法：
  python -m tagpilot_bench.runner --suite cases/smoke --reps 3 --variant smoke-1 --budget-usd 15
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .grade import grade_case, grade_states
from . import facts as facts_mod

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT.parent / 'tagpilot-semantic/out/full-20260919/snapshots'
BUILD_DIR = ROOT.parent / 'tagpilot-semantic/out/full-20260919/indexes'
TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED', 'WAITING'}


def _token() -> str:
    import os
    tok = os.environ.get('TAG_RUNTIME_TOKEN')
    if tok:
        return tok
    path = ROOT.parent / '.tag-runtime-token'
    if path.exists():
        return path.read_text().strip()
    raise RuntimeError('缺少 TAG_RUNTIME_TOKEN（或仓库根 .tag-runtime-token）')


class AgentClient:
    def __init__(self, base_url: str, token: str, timeout: float = 180.0):
        self.base = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout

    def _call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={'Authorization': f'Bearer {self.token}',
                                              'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise AgentError(exc.code, exc.read().decode()[:500]) from exc

    def start(self, request: dict):
        return self._call('POST', '/agent/v2/runs', request)

    def get(self, run_id: str, owner_id: str, after: int | None = None):
        q = f'?owner_id={owner_id}' + (f'&after={after}' if after is not None else '')
        return self._call('GET', f'/agent/v2/runs/{run_id}{q}')

    def resume(self, run_id: str, owner_id: str, answer, eligible=None):
        body = {'owner_id': owner_id, 'answer': answer}
        if eligible:
            body['eligible_tag_ids'] = eligible
        return self._call('POST', f'/agent/v2/runs/{run_id}/resume', body)


class AgentError(RuntimeError):
    def __init__(self, code, body):
        super().__init__(f'HTTP {code}: {body}')
        self.code = code
        self.body = body


class Runtime:
    """固定的运行环境三元组 + 资格。"""

    def __init__(self, snapshot_dir=SNAPSHOT_DIR, build_dir=BUILD_DIR):
        self.snapshot_dir = Path(snapshot_dir)
        self.build_dir = Path(build_dir)

    def load(self, snapshot_id: str) -> dict:
        manifests = list(self.build_dir.glob('*/manifest.json'))
        manifest_path = next((m for m in manifests if json.loads(m.read_text()).get('snapshot_id') == snapshot_id), None)
        if manifest_path is None:
            raise RuntimeError(f'找不到 snapshot {snapshot_id} 的 build manifest')
        manifest = json.loads(manifest_path.read_text())
        snap_file = self.snapshot_dir / f'{snapshot_id}.jsonl'
        eligible = [json.loads(l)['tag_id'] for l in snap_file.read_text().splitlines()
                    if l.strip() and json.loads(l).get('kind') == 'tag']
        import hashlib
        return {
            'library_id': manifest['library_id'], 'build_id': manifest['build_id'],
            'snapshot_id': manifest['snapshot_id'],
            'artifact_hash': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'eligible_tag_ids': eligible, '_manifest_path': str(manifest_path),
        }


def _post_until_terminal(client: AgentClient, run_id: str, owner_id: str, ceiling_s: float) -> dict:
    deadline = time.monotonic() + ceiling_s
    after = None
    while time.monotonic() < deadline:
        state = client.get(run_id, owner_id, after)
        if state.get('status') in TERMINAL:
            return state
        events = state.get('events') or []
        if events:
            after = events[-1].get('seq', after)
        time.sleep(0.5)
    raise TimeoutError(f'{run_id} 超过 {ceiling_s}s 未终结')


def run_case(client: AgentClient, case: dict, base: dict, owner_id: str,
             ceiling_s: float, retries: int = 2) -> dict:
    case_id = case['case_id']
    run_id = f'bench-{case_id}-{uuid.uuid4().hex[:8]}'
    thread_id = run_id
    request = {**base, 'run_id': run_id, 'thread_id': thread_id, 'owner_id': owner_id,
               'requirement': case['requirement'], 'reference_date': case.get('reference_date', '2026-09-18'),
               'timezone': case.get('timezone', 'Asia/Shanghai'), 'previous_plan': {}, 'history': []}
    request.pop('_manifest_path', None)

    attempts, last_err = 0, None
    while attempts <= retries:
        attempts += 1
        try:
            client.start(request)
            state = _post_until_terminal(client, run_id, owner_id, ceiling_s)
            break
        except (AgentError, TimeoutError, OSError) as exc:
            last_err = exc
            transient = isinstance(exc, OSError) or (isinstance(exc, AgentError) and exc.code in (429, 500, 502, 503, 504))
            if attempts > retries or not transient:
                raise
            time.sleep((2 ** attempts) * 0.3 * (0.5 + random.random()))
    else:  # pragma: no cover
        raise last_err

    turns_trace = [{'role': 'user', 'content': case['requirement']}, {'state': state}]
    # 多轮：WAITING→resume；否则新 run 携带 previous_plan（JUDGE-AUDIT F7）
    for turn in case.get('turns') or []:
        prev_plan = (state.get('result') or {}).get('plan') or {}
        msg = turn['user_message']
        if state.get('status') == 'WAITING':
            client.resume(run_id, owner_id, msg, base.get('eligible_tag_ids'))
            state = _post_until_terminal(client, run_id, owner_id, ceiling_s)
        else:
            run_id = f'bench-{case_id}-{uuid.uuid4().hex[:8]}'
            request = {**base, 'run_id': run_id, 'thread_id': thread_id, 'owner_id': owner_id,
                       'requirement': msg, 'reference_date': case.get('reference_date', '2026-09-18'),
                       'timezone': case.get('timezone', 'Asia/Shanghai'),
                       'previous_plan': prev_plan, 'continuation_of': request['run_id']}
            request.pop('_manifest_path', None)
            client.start(request)
            state = _post_until_terminal(client, run_id, owner_id, ceiling_s)
        turns_trace.append({'role': 'user', 'content': msg})
        turns_trace.append({'state': state})

    result = state.get('result') or {}
    result['status'] = state.get('status')
    return {'case_id': case_id, 'run_id': run_id, 'attempts': attempts, 'state': state,
            'result': result, 'trace': turns_trace}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--suite', required=True, help='案例目录，如 cases/smoke 或 cases/core')
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--variant', required=True)
    ap.add_argument('--budget-usd', type=float, required=True)
    ap.add_argument('--agent-url', default='http://127.0.0.1:8092')
    ap.add_argument('--snapshot-id', default='L107-20260928-006')
    ap.add_argument('--ceiling-s', type=float, default=180.0)
    ap.add_argument('--limit', type=int, default=0, help='只跑前 N 个案例（试跑）')
    ap.add_argument('--concurrency', type=int, default=2, help='并发上限（Agent 服务为 2/用户）')
    ap.add_argument('--owner', default='bench')
    args = ap.parse_args()

    suite = Path(args.suite)
    if not suite.is_absolute():
        suite = ROOT / suite
    cases = [json.loads(l) for l in (suite / 'cases.jsonl').read_text().splitlines() if l.strip()]
    if args.limit:
        cases = cases[:args.limit]
    out_dir = ROOT / 'runs' / Path(args.suite).name / args.variant
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'traces').mkdir(exist_ok=True)
    results_path = out_dir / 'results.jsonl'
    errors_path = out_dir / 'errors.jsonl'

    runtime = Runtime().load(args.snapshot_id)
    manifest = {'snapshot_id': runtime['snapshot_id'], 'build_id': runtime['build_id'],
                'artifact_hash': runtime['artifact_hash'], 'library_id': runtime['library_id'],
                'eligible_count': len(runtime['eligible_tag_ids']), 'agent_url': args.agent_url,
                'reps': args.reps, 'ceiling_s': args.ceiling_s}
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))

    done = set()
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r['case_id'], r['rep']))

    client = AgentClient(args.agent_url, _token(), timeout=args.ceiling_s + 30)
    tag_facts = facts_mod.load()
    rows_cache = {}

    def rows_for_expected(expected):
        from .oracle import fields
        tree = expected.get('tree') if isinstance(expected, dict) else None
        want = tuple(sorted(fields(tree))) if tree else ()
        if want not in rows_cache:
            from . import db
            rows_cache[want] = db.load_rows(list(want))  # 空字段集（SCOPE_ALL/无树）也加载全部 CUST_ID
        return rows_cache[want]

    lock = threading.Lock()
    state = {'spent': 0.0, 'stopped': False}

    def one(case, rep):
        if state['stopped']:
            return
        with lock:
            if state['spent'] >= args.budget_usd:
                state['stopped'] = True
                return
        started = time.monotonic()
        try:
            outcome = run_case(client, case, runtime, args.owner, args.ceiling_s)
            elapsed = time.monotonic() - started
            stats = (outcome['result'].get('outcome') or {}).get('stats') or {}
            states = [x['state'] for x in outcome['trace'] if isinstance(x, dict) and 'state' in x]
            graded = grade_states(case, states, tag_facts, rows_for_expected)
            row = {'case_id': case['case_id'], 'rep': rep, 'run_id': outcome['run_id'],
                   'status': outcome['result'].get('status'), 'attempts': outcome['attempts'],
                   'elapsed_s': round(elapsed, 2), 'cost_usd': stats.get('sdk_cost_estimate_usd'),
                   'usage': stats.get('usage'), 'degraded': stats.get('degraded'),
                   'grade': graded['pass'], 'dims': graded['dims'], 'verdict': graded['status'],
                   'failures': graded['failures'], 'first_turn': graded.get('first_turn'),
                   'final_turn': graded.get('final_turn'),
                   'snapshot_id': runtime['snapshot_id'], 'build_id': runtime['build_id']}
            (out_dir / 'traces' / f"{case['case_id']}_r{rep}.json").write_text(
                json.dumps(outcome['trace'], ensure_ascii=False, indent=1))
            with lock:
                state['spent'] += float(stats.get('sdk_cost_estimate_usd') or 0)
                _append(results_path, row)
            print(f"{case['case_id']} r{rep} {graded['status']:11} pass={graded['pass']} {elapsed:.0f}s")
        except TimeoutError as exc:
            with lock:
                _append(errors_path, {'case_id': case['case_id'], 'rep': rep, 'failure': 'timeout', 'reason': str(exc)})
            print(f"{case['case_id']} r{rep} TIMEOUT")
        except Exception as exc:  # noqa: BLE001 一个坏案例不得杀死整个跑批
            with lock:
                _append(errors_path, {'case_id': case['case_id'], 'rep': rep, 'failure': 'error', 'reason': str(exc)[:300]})
            print(f"{case['case_id']} r{rep} ERROR {str(exc)[:100]}")

    tasks = [(case, rep) for case in cases for rep in range(args.reps)
             if (case['case_id'], rep) not in done]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        list(pool.map(lambda t: one(*t), tasks))
    print(f'完成；累计约 ${state["spent"]:.2f}')


def _append(path: Path, row: dict):
    with open(path, 'a') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
