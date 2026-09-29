"""本机 P3 控制面。认证只保存在内存，SQL 限制为本机；不创建客群。"""
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]


def mysql(sql):
    import yaml
    config = yaml.safe_load((ROOT / 'ruoyi-admin/src/main/resources/application-druid.yml').read_text())
    master = config['spring']['datasource']['druid']['master']
    address = urlparse(master['url'].removeprefix('jdbc:'))
    if address.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('P3 自动操作仅允许本机数据库')
    result = subprocess.run(['mysql', '--protocol=TCP', '-h', address.hostname,
                             '-P', str(address.port or 3306), '-u', master['username'],
                             '--batch', '--raw', '--skip-column-names', '--default-character-set=utf8mb4',
                             address.path.strip('/')], input=sql, text=True, capture_output=True,
                            env={**os.environ, 'MYSQL_PWD': str(master['password'])}, timeout=120)
    if result.returncode:
        raise RuntimeError('本机 SQL 执行失败：' + result.stderr[:300])
    return result.stdout.strip().splitlines()


class JavaClient:
    def __init__(self, base='http://127.0.0.1:8080'):
        if urlparse(base).hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('仅允许本机 Java')
        self.base, self.token = base, None

    def call(self, method, path, body=None, timeout=180):
        request = Request(self.base + path, method=method,
                          data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json',
                                   **({'Authorization': 'Bearer ' + self.token} if self.token else {})})
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
        if result.get('code') != 200:
            raise RuntimeError(f'Java {path}: {result.get("code")} {result.get("msg")}')
        return result.get('data', result)

    def login(self, code='', uuid=None):
        """验证码由标准登录图片读取，调用方传入；禁止读取认证后端存储。"""
        response = self.call('POST', '/login', {
            'username': os.environ.get('TAGPILOT_EVAL_USER', 'admin'),
            'password': os.environ.get('TAGPILOT_EVAL_PASSWORD', 'admin123'),
            'code': code, 'uuid': uuid})
        self.token = response['token']
        return self
