"""真实运行链路客户端：本地语义检索(:8091) 与 Agent 编排(:8092)。

只使用标准库；令牌从环境变量或仓库根的 .tag-runtime-token 读取，绝不写入产物。
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_URL = os.environ.get('TAG_SEMANTIC_URL', 'http://127.0.0.1:8091')
AGENT_URL = os.environ.get('TAG_AGENT_URL', 'http://127.0.0.1:8092')


def runtime_token():
    token = os.environ.get('TAG_RUNTIME_TOKEN')
    if token:
        return token.strip()
    path = ROOT / '.tag-runtime-token'
    if not path.exists():
        raise RuntimeError('缺少 TAG_RUNTIME_TOKEN（环境变量或 .tag-runtime-token）')
    return path.read_text().strip()


class _Client:
    def __init__(self, base, timeout=120):
        self.base, self.timeout, self.token = base.rstrip('/'), timeout, runtime_token()

    def _call(self, method, path, body=None, params=None):
        url = self.base + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header('Authorization', 'Bearer ' + self.token)
        if data is not None:
            request.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'{method} {path} -> {exc.code}: {exc.read()[:400]!r}') from exc


class SemanticClient(_Client):
    def __init__(self, base=SEMANTIC_URL):
        super().__init__(base)

    def stats(self, build_id):
        return self._call('GET', '/stats', params={'build_id': build_id})

    def bundle(self, build_id):
        """当前活动 bundle 的身份三元组（评测必须逐次记录）。"""
        stats = self.stats(build_id)
        return {'build_id': stats['build_id'], 'snapshot_id': stats['snapshot_id'],
                'artifact_hash': stats['artifact_hash'],
                'retrieval_config_hash': stats.get('retrieval_config_hash'),
                'content_hash': stats.get('content_hash'),
                'doc_count': stats.get('doc_count'), 'id_reconciled': stats.get('id_reconciled'),
                'store_type': stats.get('store_type'),
                'embedding_model': stats.get('embedding_model'),
                'reranker_model': stats.get('reranker_model'),
                'doc_template_version': stats.get('doc_template_version')}

    def _body(self, requirement, build_id, eligible_tag_ids, library_id, **extra):
        return {'requirement': requirement, 'library_id': library_id, 'build_id': build_id,
                'eligible_tag_ids': list(eligible_tag_ids), **extra}

    def lookup(self, requirement, build_id, eligible_tag_ids, library_id=107, k=8):
        return self._call('POST', '/lookup',
                          self._body(requirement, build_id, eligible_tag_ids, library_id, k=k))

    def retrieve_batch(self, queries, build_id, eligible_tag_ids, library_id=107, k=20, mode='fast'):
        return self._call('POST', '/retrieve_batch',
                          self._body(queries[0], build_id, eligible_tag_ids, library_id,
                                     queries=list(queries), k=k, mode=mode))

    def evidence(self, requirement, tag_ids, build_id, eligible_tag_ids, library_id=107,
                 value_query=None, max_values=20):
        extra = {'tag_ids': list(tag_ids), 'max_values': max_values}
        if value_query is not None:
            extra['value_query'] = value_query
        return self._call('POST', '/evidence',
                          self._body(requirement, build_id, eligible_tag_ids, library_id, **extra))

    def capabilities(self, requirement, capability_ids, build_id, eligible_tag_ids, library_id=107):
        return self._call('POST', '/capabilities',
                          self._body(requirement, build_id, eligible_tag_ids, library_id,
                                     capability_ids=list(capability_ids)))



class AgentClient(_Client):
    def __init__(self, base=AGENT_URL):
        super().__init__(base)

    def health(self):
        return self._call('GET', '/health')

    def start(self, request):
        return self._call('POST', '/agent/v2/runs', request)['run_id']

    def poll(self, run_id, owner_id, after=0):
        return self._call('GET', f'/agent/v2/runs/{run_id}', params={'owner_id': owner_id,
                                                                     'after': after})

    def cancel(self, run_id, owner_id):
        """停止一个长时间无进展的运行，保留已完成条件的最佳草案。"""
        return self._call('POST', f'/agent/v2/runs/{run_id}/cancel',
                          {'owner_id': owner_id, 'answer': None, 'eligible_tag_ids': [],
                           'confirmed_clause_ids': []})

    def run_to_terminal(self, request, deadline_seconds=180, poll_seconds=1.0):
        """轮询到终态；超时先取消再取回最佳草案，避免单个卡死运行拖住整批。"""
        self.start(request)
        after, events, started = 0, [], time.monotonic()
        timed_out = False
        while True:
            state = self.poll(request['run_id'], request['owner_id'], after)
            for event in state.get('events') or []:
                events.append(event)
                after = max(after, event.get('seq', 0))
            if state.get('status') not in {'RUNNING', 'QUEUED'}:
                return {**state, 'events': events, 'cancelled_by_harness': timed_out}, events
            if not timed_out and time.monotonic() - started > deadline_seconds:
                timed_out = True
                try:
                    self.cancel(request['run_id'], request['owner_id'])
                except RuntimeError:
                    pass
            elif timed_out and time.monotonic() - started > deadline_seconds + 30:
                return {**state, 'timeout': True, 'events': events}, events
            time.sleep(poll_seconds)

    def resume(self, run_id, owner_id, answer, eligible_tag_ids, confirmed_clause_ids=None,
               deadline_seconds=180):
        self._call('POST', f'/agent/v2/runs/{run_id}/resume',
                   {'owner_id': owner_id, 'answer': answer,
                    'eligible_tag_ids': list(eligible_tag_ids),
                    'confirmed_clause_ids': list(confirmed_clause_ids or [])})
        after, events, started = 0, [], time.monotonic()
        timed_out = False
        while True:
            state = self.poll(run_id, owner_id, after)
            for event in state.get('events') or []:
                events.append(event)
                after = max(after, event.get('seq', 0))
            if state.get('status') not in {'RUNNING', 'QUEUED'}:
                return {**state, 'events': events}, events
            if not timed_out and time.monotonic() - started > deadline_seconds:
                timed_out = True
                try:
                    self.cancel(run_id, owner_id)
                except RuntimeError:
                    pass
            elif timed_out and time.monotonic() - started > deadline_seconds + 30:
                return {**state, 'timeout': True, 'events': events}, events
            time.sleep(1.0)
