"""容量探针：真实 SDK/CLI + 本地假网关，统计冷启动、峰值 RSS 与 12 并发总内存。

用法（在 tagpilot-agent/ 下）：PYTHONPATH=. .venv/bin/python scripts/capacity_probe.py
只走本地假网关，不产生真实模型调用。
"""
import asyncio
import json
import os
import socket
import statistics
import threading
import time
from pathlib import Path

import psutil
import uvicorn

from tests.fake_anthropic_gateway import create_gateway
from tests.test_sdk_smoke import Evidence
from tests.test_workbench import REQ
from tagpilot_agent.runtime.run_manager import RunManager
from tagpilot_agent.runtime.run_store import RunStore

PLAN = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '转入超过50万',
                 'tag_id': 1, 'operator': '>', 'values': ['500000']}}
ALL_PLAN = {'tree': {'kind': 'SCOPE_ALL', 'clause_id': 'all', 'source_span': '全部客户'}}


def scripts():
    return {
        'simple': [[('mcp__tagpilot__submit_result', {'outcome': 'READY', 'plan': ALL_PLAN, 'summary': '完成'})]],
        'medium': [[('mcp__tagpilot__find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'a'}], 'depth': 'deep'}),
                    ('mcp__tagpilot__get_tag_details', {'tag_ids': [1]})],
                   [('mcp__tagpilot__check_plan', {'plan': PLAN})],
                   [('mcp__tagpilot__submit_result', {'outcome': 'READY', 'plan': PLAN, 'summary': '完成'})]],
        'complex': [[('mcp__tagpilot__find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'a'}], 'depth': 'deep'}),
                     ('mcp__tagpilot__find_capabilities', {'query': '高价值', 'requirement_ids': ['a']})],
                    [('mcp__tagpilot__get_tag_details', {'tag_ids': [1]}),
                     ('mcp__tagpilot__check_plan', {'plan': PLAN})],
                    [('mcp__tagpilot__submit_result', {'outcome': 'READY', 'plan': PLAN, 'summary': '完成'})]],
        'full_turns': [[('mcp__tagpilot__find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'a'}], 'depth': 'quick'}),
                        ('mcp__tagpilot__check_plan', {'plan': PLAN})]],
    }


class Gateway:
    def __init__(self, script):
        self.app = create_gateway(script)
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        self.port = sock.getsockname()[1]
        self.server = uvicorn.Server(uvicorn.Config(self.app, log_level='error', timeout_graceful_shutdown=1))
        self.thread = threading.Thread(target=lambda: self.server.run(sockets=[sock]), daemon=True)
        self.sock = sock
        self.thread.start()

    def env(self):
        return {'ANTHROPIC_BASE_URL': f'http://127.0.0.1:{self.port}', 'ANTHROPIC_API_KEY': 'local-fake-key',
                'ANTHROPIC_MODEL': 'fake-model'}

    def close(self):
        self.server.should_exit = True
        self.server.force_exit = True
        self.thread.join(timeout=5)
        self.sock.close()


def _run_chunk(tmp, label, script, count, concurrency=None, node_options=None, all_scope=False):
    gateway = Gateway(script)
    os.environ.update(gateway.env())
    if concurrency:
        os.environ['TAG_AGENT_MAX_CONCURRENCY'] = str(concurrency)
        os.environ['TAG_AGENT_PER_USER_MAX'] = str(concurrency)
    if node_options is not None:
        os.environ['NODE_OPTIONS'] = node_options
    else:
        os.environ.pop('NODE_OPTIONS', None)
    store = RunStore(str(Path(tmp) / f'{label}-{time.time_ns()}.sqlite'), 'capacity-probe')
    manager = RunManager(store, lambda library, build: Evidence())
    samples = []
    stop = threading.Event()
    me = psutil.Process(os.getpid())

    def sample():
        while not stop.is_set():
            total = 0.0
            cpu = 0.0
            children = 0
            for child in me.children(recursive=True):
                try:
                    total += child.memory_info().rss
                    cpu += child.cpu_percent(interval=None)
                    children += 1
                except psutil.Error:
                    pass
            samples.append({'t': time.monotonic(), 'rss_mb': total / 1024 ** 2, 'cpu': cpu, 'children': children})
            time.sleep(.5)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.monotonic()
    rows = []

    async def scenario():
        async def one(index):
            rid = f'{label}-{index}'
            request = {**REQ, 'run_id': rid, 'thread_id': 'thread-' + rid, 'owner_id': f'owner-{index}',
                       'requirement': '全部客户' if all_scope else '转入超过50万'}
            store.create(rid, request)
            await asyncio.wait_for(manager.execute(rid, request), 300)
            return store.get(rid, f'owner-{index}')
        results = await asyncio.gather(*[one(index) for index in range(count)], return_exceptions=True)
        await manager.close()
        return results

    try:
        results = asyncio.run(scenario())
    finally:
        stop.set()
        sampler.join(timeout=5)
        gateway.close()
    for index, row in enumerate(results):
        if isinstance(row, Exception):
            rows.append({'index': index, 'error': repr(row)})
            continue
        stats = (row['result'] or {}).get('outcome', {}).get('stats', {})
        rows.append({'index': index, 'status': row['status'], 'cli_start_ms': stats.get('cli_start_ms'),
                     'cli_peak_rss_mb': stats.get('cli_peak_rss_mb'), 'llm_turns': stats.get('llm_turns'),
                     'stop_reason': stats.get('stop_reason')})
    peaks = [event['rss_mb'] for event in samples]
    child_counts = [event['children'] for event in samples]
    store.db.close()
    return {'profile': label, 'runs': rows, 'seconds': round(time.monotonic() - started, 2),
            'aggregate_rss_mb_peak': round(max(peaks), 1) if peaks else None,
            'aggregate_rss_mb_avg': round(statistics.fmean(peaks), 1) if peaks else None,
            'children_peak': max(child_counts) if child_counts else 0}


def run_batch(tmp, profile, script, count, concurrency=None, node_options=None, isolate=False, all_scope=False):
    chunks = [_run_chunk(tmp, f'{profile}-{index}' if isolate else profile, script,
                         1 if isolate else count, concurrency, node_options, all_scope)
              for index in range(count if isolate else 1)]
    rows = [row for chunk in chunks for row in chunk['runs']]
    peaks = [chunk['aggregate_rss_mb_peak'] for chunk in chunks if chunk['aggregate_rss_mb_peak'] is not None]
    averages = [chunk['aggregate_rss_mb_avg'] for chunk in chunks if chunk['aggregate_rss_mb_avg'] is not None]
    return {'profile': profile, 'runs': rows, 'seconds': round(sum(chunk['seconds'] for chunk in chunks), 2),
            'aggregate_rss_mb_peak': round(max(peaks), 1) if peaks else None,
            'aggregate_rss_mb_avg': round(statistics.fmean(averages), 1) if averages else None,
            'children_peak': max(chunk['children_peak'] for chunk in chunks)}


def percentile(values, fraction):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    index = min(len(values) - 1, max(0, round(fraction * (len(values) - 1))))
    return values[index]


def main():
    tmp = Path('out/capacity-probe')
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('TAG_AGENT_HARD_TIMEOUT', '120')
    os.environ.setdefault('TAG_AGENT_MAX_TURNS', '10')
    report = {'mode': 'real_sdk_fake_gateway', 'node_process': os.uname().machine, 'profiles': {}, 'concurrency': None}
    kinds = scripts()
    for profile in ('simple', 'medium', 'complex'):
        report['profiles'][profile] = run_batch(tmp, profile, kinds[profile], 10, isolate=True, all_scope=profile == 'simple')
        print(profile, report['profiles'][profile]['seconds'], 's', flush=True)
    report['profiles']['full_turns'] = run_batch(tmp, 'full_turns', kinds['full_turns'], 1)
    print('full_turns', report['profiles']['full_turns']['seconds'], 's', flush=True)
    report['concurrency'] = run_batch(tmp, 'concurrent12', kinds['full_turns'], 12, concurrency=12)
    print('concurrent12', report['concurrency']['seconds'], 's', flush=True)
    node_check = run_batch(tmp, 'node_options', kinds['simple'], 2, node_options='--max-old-space-size=64', isolate=True, all_scope=True)
    report['node_options'] = {'profile': node_check['profile'], 'runs': node_check['runs']}
    peaks = {'simple': [], 'medium': [], 'complex': [], 'full_turns': []}
    for profile in ('simple', 'medium', 'complex'):
        peaks[profile] = [row.get('cli_peak_rss_mb') for row in report['profiles'][profile]['runs']]
    peaks['full_turns'] = [row.get('cli_peak_rss_mb') for row in report['profiles']['full_turns']['runs']] + \
                          [row.get('cli_peak_rss_mb') for row in report['concurrency']['runs']]
    report['summary'] = {profile: {'n': len([v for v in values if v is not None]),
                                   'p50': percentile(values, .5), 'p95': percentile(values, .95),
                                   'p99': percentile(values, .99), 'max': max([v for v in values if v is not None], default=None),
                                   'cli_start_ms_p50': percentile([row.get('cli_start_ms') for row in
                                       (report['profiles'][profile]['runs'] if profile in report['profiles'] else report['concurrency']['runs'])], .5)}
                          for profile, values in peaks.items()}
    Path('out/capacity-20260924.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report['summary'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
