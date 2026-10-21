"""Java 权威链客户端：编译 Agent 计划 + 执行 COUNT。

登录受验证码保护，不在此处绕过：从环境变量 `TAGPILOT_JAVA_TOKEN` 取已登录令牌
（由调用方以合规方式取得），未提供则调用方应回退到本地 oracle。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

BASE = os.environ.get('TAGPILOT_JAVA_URL', 'http://127.0.0.1:8080')


class JavaError(RuntimeError):
    pass


class JavaClient:
    def __init__(self, base: str = BASE, token: str | None = None):
        if urlparse(base).hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise JavaError('仅允许本机 Java')
        self.base = base.rstrip('/')
        self.token = token or os.environ.get('TAGPILOT_JAVA_TOKEN')

    @property
    def available(self) -> bool:
        return bool(self.token)

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 180):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json',
                                              **({'Authorization': 'Bearer ' + self.token} if self.token else {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.load(resp)
        except urllib.error.HTTPError as exc:
            raise JavaError(f'HTTP {exc.code}: {exc.read().decode()[:300]}') from exc
        if result.get('code') != 200:
            raise JavaError(f'Java {path}: {result.get("code")} {result.get("msg")}')
        return result.get('data', result)

    def compile_plan(self, library_id: int, plan: dict):
        return self.call('POST', '/taglibrary/agent/plan/compile', {'library_id': library_id, 'plan': plan})

    def run_group(self, library_id: int, rule: dict):
        return self.call('POST', '/objectgroup/group/run', {'libraryId': library_id, 'rule': rule})

    def login(self, username: str | None = None, password: str | None = None) -> str:
        """登录取令牌。仅当本机验证码已关闭时可用（不在此处绕过验证码）。"""
        username = username or os.environ.get('TAGPILOT_EVAL_USER', 'admin')
        password = password or os.environ.get('TAGPILOT_EVAL_PASSWORD', 'admin123')
        req = urllib.request.Request(self.base + '/login', method='POST',
                                     data=json.dumps({'username': username, 'password': password}).encode(),
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.load(resp)
        if result.get('code') != 200 or not result.get('token'):
            raise JavaError(f"登录失败: {result.get('code')} {result.get('msg')}")
        self.token = result['token']
        return self.token
