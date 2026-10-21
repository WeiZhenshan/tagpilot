"""语义引擎客户端（:8091）：只读调用 /retrieve_batch 等。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class SemanticError(RuntimeError):
    pass


class SemanticClient:
    def __init__(self, base_url: str, token: str, timeout: float = 60.0):
        self.base = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout

    def _call(self, path: str, body: dict):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method='POST',
                                     headers={'Authorization': f'Bearer {self.token}',
                                              'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise SemanticError(f'HTTP {exc.code}: {exc.read().decode()[:300]}') from exc

    def retrieve_batch(self, queries, build_id: str, library_id: int, eligible_tag_ids, k: int = 20, mode: str = 'fast'):
        return self._call('/retrieve_batch', {
            'requirement': queries[0], 'queries': list(queries), 'library_id': library_id,
            'build_id': build_id, 'eligible_tag_ids': list(eligible_tag_ids), 'k': k, 'mode': mode})
