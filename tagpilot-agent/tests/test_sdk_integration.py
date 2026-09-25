"""真实 SDK/CLI + 本地假网关的异常、取消、超时与并发集成测。"""
import asyncio
import json
import socket
import threading

import pytest
import uvicorn

from tagpilot_agent.runtime.run_manager import RunManager
from tagpilot_agent.runtime.run_store import RunStore
from tagpilot_agent.tools.registry import dispatch
from tests.fake_anthropic_gateway import create_gateway
from tests.test_sdk_smoke import Evidence
from tests.test_workbench import REQ

PLAN = {'tree': {'kind': 'TAG_PREDICATE', 'clause_id': 'a', 'source_span': '转入超过50万',
                 'tag_id': 1, 'operator': '>', 'values': ['500000']}}
ALL_PLAN = {'tree': {'kind': 'SCOPE_ALL', 'clause_id': 'all', 'source_span': '全部客户'}}


@pytest.fixture
def gateway(monkeypatch):
    started = []

    def start(script):
        app = create_gateway(script)
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', timeout_graceful_shutdown=1))
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        thread.start()
        monkeypatch.setenv('ANTHROPIC_BASE_URL', f'http://127.0.0.1:{port}')
        monkeypatch.setenv('ANTHROPIC_API_KEY', 'local-fake-key')
        monkeypatch.setenv('ANTHROPIC_MODEL', 'fake-model')
        started.append((server, thread, sock))
        return app

    monkeypatch.setenv('TAG_AGENT_HARD_TIMEOUT', '20')
    monkeypatch.setenv('TAG_AGENT_SOFT_TIMEOUT', '10')
    monkeypatch.setenv('TAG_AGENT_MAX_CONCURRENCY', '2')
    monkeypatch.setenv('TAG_AGENT_QUEUE_MAX', '24')
    monkeypatch.setenv('TAG_AGENT_QUEUE_TIMEOUT', '20')
    monkeypatch.setenv('TAG_AGENT_MAX_RSS_MB', '600')
    yield start
    for server, thread, sock in started:
        server.should_exit = True
        server.force_exit = True
        thread.join(timeout=5)
        sock.close()


def manager_for(tmp_path, runner=None):
    store = RunStore(str(tmp_path / 'runs.sqlite'), 'integration-secret')
    return store, RunManager(store, lambda library, build: Evidence(), runner)


def request_for(rid, **overrides):
    return {**REQ, 'run_id': rid, 'thread_id': 'thread-' + rid, **overrides}


def test_multi_turn_loop_terminates_on_submit(tmp_path, gateway):
    app = gateway([
        [('mcp__tagpilot__find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'a'}], 'depth': 'deep'}),
         ('mcp__tagpilot__get_tag_details', {'tag_ids': [1]})],
        [('mcp__tagpilot__check_plan', {'plan': PLAN})],
        [('mcp__tagpilot__submit_result', {'outcome': 'READY', 'plan': PLAN, 'summary': '完成'})],
        []])
    store, manager = manager_for(tmp_path)

    async def scenario():
        request = request_for('r-a')
        assert store.create('r-a', request)
        await manager.execute('r-a', request)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-a', '7')
    assert row['status'] == 'COMPLETED', row
    assert row['result']['outcome']['outcome'] == 'READY'
    assert row['result']['plan']['valid'] is True
    stats = row['result']['outcome']['stats']
    assert stats['deep'] == 1 and stats['tools'] >= 3 and stats['llm_turns'] >= 3
    assert stats['cli_start_ms'] >= 0 and stats['cli_peak_rss_mb'] > 0
    assert len(app.state.requests) == 3, len(app.state.requests)
    assert all(t['name'].startswith('mcp__tagpilot__') for t in app.state.requests[0]['tools'])
    completed = [e['tool'] for e in store.events('r-a') if e['type'] == 'tool.completed']
    assert sorted(completed) == ['check_plan', 'find_tags', 'get_tag_details', 'submit_result']
    store.db.close()


def test_ask_outcome_returns_waiting_with_interrupt(tmp_path, gateway):
    gateway([[('mcp__tagpilot__find_tags', {'queries': [{'text': '风评', 'requirement_id': 'a'}], 'depth': 'quick'})],
             [('mcp__tagpilot__submit_result', {'outcome': 'NEEDS_USER_INPUT', 'plan': PLAN, 'questions': [
                 {'requirement_id': 'a', 'clause_id': 'a', 'prompt': '是否包含未知码值客户？',
                  'options': ['包含', '排除'], 'reason': 'DEFINITION_MISSING'}]})],
             []])
    store, manager = manager_for(tmp_path)

    async def scenario():
        request = request_for('r-c')
        assert store.create('r-c', request)
        await manager.execute('r-c', request)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-c', '7')
    assert row['status'] == 'WAITING', row
    assert row['result']['interrupt_id'] == 'r-c-0'
    assert row['result']['plan']['plan_status'] == 'NEEDS_DECISION'
    assert len(row['result']['questions'][0]['options']) == 2
    store.db.close()


def test_rejected_submit_is_fixed_within_loop(tmp_path, gateway):
    bad = json.loads(json.dumps(PLAN))
    bad['tree']['operator'] = 'INVALID'
    app = gateway([[('mcp__tagpilot__find_tags', {'queries': [{'text': '转入金额', 'requirement_id': 'a'}], 'depth': 'deep'})],
                   [('mcp__tagpilot__submit_result', {'outcome': 'READY', 'plan': bad, 'summary': '第一次'})],
                   [('mcp__tagpilot__submit_result', {'outcome': 'READY', 'plan': PLAN, 'summary': '修正后'})],
                   []])
    store, manager = manager_for(tmp_path)

    async def scenario():
        request = request_for('r-d')
        assert store.create('r-d', request)
        await manager.execute('r-d', request)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-d', '7')
    assert row['status'] == 'COMPLETED', row
    assert row['result']['outcome']['outcome'] == 'READY'
    assert row['result']['outcome']['stats']['submit_rejections'] == 1
    assert len(app.state.requests) == 3
    store.db.close()


def test_cancel_mid_run_keeps_draft(tmp_path, gateway):
    gateway([[('mcp__tagpilot__check_plan', {'plan': PLAN})], 'stall'])
    store, manager = manager_for(tmp_path)

    async def scenario():
        request = request_for('r-e')
        assert store.create('r-e', request)
        task = asyncio.create_task(manager.execute('r-e', request))
        for _ in range(200):
            if any(event['type'] == 'plan.observed' for event in store.events('r-e')):
                break
            await asyncio.sleep(.05)
        store.cancel('r-e', '7')
        await manager.cancel('r-e')
        await asyncio.wait_for(task, 15)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-e', '7')
    assert row['status'] == 'CANCELLED', row
    assert row['result']['plan']['tree']['clause_id'] == 'a'
    store.db.close()


def test_hard_timeout_returns_best_draft(tmp_path, gateway, monkeypatch):
    monkeypatch.setenv('TAG_AGENT_HARD_TIMEOUT', '2')
    gateway([[('mcp__tagpilot__check_plan', {'plan': PLAN})], 'stall'])
    store, manager = manager_for(tmp_path)

    async def scenario():
        request = request_for('r-f')
        assert store.create('r-f', request)
        await asyncio.wait_for(manager.execute('r-f', request), 20)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-f', '7')
    assert row['status'] == 'FAILED'
    assert '运行资源或时间预算已耗尽' in row['error']
    assert row['result']['plan']['plan_status'] == 'RETRYABLE_FAILURE'
    assert row['result']['plan']['tree']['clause_id'] == 'a'
    assert row['result']['outcome']['stats']['stop_reason'] == 'timeout'
    store.db.close()


def test_hard_timeout_without_draft_returns_retryable_partial(tmp_path, gateway, monkeypatch):
    monkeypatch.setenv('TAG_AGENT_HARD_TIMEOUT', '2')
    gateway(['stall'])
    store, manager = manager_for(tmp_path)

    async def scenario():
        request = request_for('r-g')
        assert store.create('r-g', request)
        await asyncio.wait_for(manager.execute('r-g', request), 20)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-g', '7')
    assert row['status'] == 'FAILED'
    assert row['result']['plan']['plan_status'] == 'RETRYABLE_FAILURE'
    assert row['result']['plan']['tree']['clause_id'] == 'pending'
    assert row['result']['outcome']['outcome'] == 'PARTIAL'
    store.db.close()


def test_persistent_gateway_failure_degrades_without_hang(tmp_path, gateway, monkeypatch):
    monkeypatch.setenv('TAG_AGENT_HARD_TIMEOUT', '3')
    app = gateway(['error'])
    store, manager = manager_for(tmp_path)

    async def scenario():
        request = request_for('r-h')
        assert store.create('r-h', request)
        await asyncio.wait_for(manager.execute('r-h', request), 20)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-h', '7')
    assert row['status'] == 'FAILED'
    assert '运行资源或时间预算已耗尽' in row['error']
    stats = row['result']['outcome']['stats']
    assert row['result']['plan']['plan_status'] == 'RETRYABLE_FAILURE'
    assert stats['agent_failure'] is True and stats['stop_reason'] == 'timeout'
    assert stats['llm_turns'] >= 1 and len(app.state.requests) >= 2
    store.db.close()


class FlakyRunner:
    def __init__(self):
        self.calls = 0

    async def run(self, ctx, prompt):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError('cli crashed')
        await dispatch(ctx, 'submit_result', {'outcome': 'READY', 'plan': ALL_PLAN, 'summary': '完成'})


def test_runner_crash_retries_once_then_succeeds(tmp_path):
    runner = FlakyRunner()
    store, manager = manager_for(tmp_path, runner)

    async def scenario():
        request = request_for('r-h2', requirement='全部客户')
        assert store.create('r-h2', request)
        await manager.execute('r-h2', request)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-h2', '7')
    assert row['status'] == 'COMPLETED', row
    assert row['result']['outcome']['stats']['cli_retries'] == 1
    assert runner.calls == 2
    store.db.close()


def test_memory_circuit_breaker_interrupts(tmp_path, gateway, monkeypatch):
    monkeypatch.setenv('TAG_AGENT_MAX_RSS_MB', '1')
    gateway(['stall'])
    store, manager = manager_for(tmp_path)

    async def scenario():
        request = request_for('r-i')
        assert store.create('r-i', request)
        await asyncio.wait_for(manager.execute('r-i', request), 20)
        await manager.close()

    asyncio.run(scenario())
    row = store.get('r-i', '7')
    assert row['status'] == 'FAILED'
    assert row['result']['outcome']['stats']['stop_reason'] == 'memory_limit'
    assert row['result']['outcome']['stats']['cli_peak_rss_mb'] > 1
    store.db.close()


class SlowRunner:
    def __init__(self, delay):
        self.delay = delay
        self.active = 0
        self.peak = 0

    async def run(self, ctx, prompt):
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(self.delay)
            await dispatch(ctx, 'submit_result', {'outcome': 'READY', 'plan': ALL_PLAN, 'summary': '完成'})
        finally:
            self.active -= 1


def test_global_limit_queues_second_run(tmp_path, monkeypatch):
    monkeypatch.setenv('TAG_AGENT_MAX_CONCURRENCY', '1')
    monkeypatch.setenv('TAG_AGENT_QUEUE_TIMEOUT', '20')
    runner = SlowRunner(.6)
    store, manager = manager_for(tmp_path, runner)

    async def scenario():
        first, second = request_for('r-j1', requirement='全部客户'), request_for('r-j2', requirement='全部客户')
        store.create('r-j1', first)
        store.create('r-j2', second)
        await asyncio.gather(manager.execute('r-j1', first), manager.execute('r-j2', second))
        await manager.close()

    asyncio.run(scenario())
    assert runner.peak == 1
    assert store.get('r-j1', '7')['status'] == 'COMPLETED'
    assert store.get('r-j2', '7')['status'] == 'COMPLETED'
    queued = [e for e in store.events('r-j2') if e['type'] == 'run.queued']
    assert queued and '排队中' in queued[0]['message']
    store.db.close()


def test_per_user_limit_queues_own_runs(tmp_path, monkeypatch):
    monkeypatch.setenv('TAG_AGENT_MAX_CONCURRENCY', '2')
    monkeypatch.setenv('TAG_AGENT_PER_USER_MAX', '1')
    runner = SlowRunner(.5)
    store, manager = manager_for(tmp_path, runner)

    async def scenario():
        first, second = request_for('r-k1', requirement='全部客户'), request_for('r-k2', requirement='全部客户')
        store.create('r-k1', first)
        store.create('r-k2', second)
        await asyncio.gather(manager.execute('r-k1', first), manager.execute('r-k2', second))
        await manager.close()

    asyncio.run(scenario())
    assert runner.peak == 1
    assert any(e['type'] == 'run.queued' for e in store.events('r-k2'))
    store.db.close()


def test_queue_timeout_fails_with_saved_progress(tmp_path, monkeypatch):
    monkeypatch.setenv('TAG_AGENT_MAX_CONCURRENCY', '1')
    monkeypatch.setenv('TAG_AGENT_QUEUE_TIMEOUT', '0.3')
    runner = SlowRunner(2)
    store, manager = manager_for(tmp_path, runner)

    async def scenario():
        first, second = request_for('r-l1', requirement='全部客户'), request_for('r-l2', requirement='全部客户')
        store.create('r-l1', first)
        store.create('r-l2', second)
        await asyncio.gather(manager.execute('r-l1', first), manager.execute('r-l2', second))
        await manager.close()

    asyncio.run(scenario())
    assert store.get('r-l1', '7')['status'] == 'COMPLETED'
    row = store.get('r-l2', '7')
    assert row['status'] == 'FAILED'
    assert row['error'] == '处理暂未完成，已保存进度供重试'
    store.db.close()
