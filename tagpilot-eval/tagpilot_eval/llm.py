"""付费调用客户端：标准库 HTTP 调 OpenAI 兼容端点，按 token 记账并执行显式预算闸门。

不用 `claude_agent_sdk`：既绕开在 Desktop 会话里继承宿主 `ANTHROPIC_*` 导致 401 的那类缺陷，
也能拿到 provider 报的真实 token 数。密钥只从仓库根 `.tag-llm-config` **读取**，
绝不写入任何 manifest、报告或日志。

预算有两个口径，都记在账本里：
- `sdk_equivalent_usd`：把同一批 token 套在**钉死的 Claude 价目表**上，与 P1 报的 $26.92 同口径，
  用户选择的 $150 上限按这个口径执行；
- `declared_usd`：套在钉死的 DeepSeek 价目表上，代表真实花费量级。
两张价目表都是**声明的假设**，随 manifest 记录，便于换算与更正。
"""
import http.client
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HTTP_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0

PRICE_TABLES = {
    'sdk_equivalent_claude': {'input_per_million': 3.0, 'output_per_million': 15.0},
    'declared_deepseek': {'input_per_million': 0.28, 'output_per_million': 0.42},
}
CONFIG_KEYS = ('TAG_LLM_BASE_URL', 'TAG_LLM_MODEL', 'TAG_LLM_API_KEY')


class BudgetExceeded(RuntimeError):
    pass


def load_config(root):
    """只取需要的三个键；调用方不得回显或落盘其内容。"""
    config = {}
    path = Path(root) / '.tag-llm-config'
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            config[key.strip()] = value.strip()
    return {key: os.environ.get(key) or config.get(key) for key in CONFIG_KEYS}


def _cost(usage, table):
    return (usage.get('prompt_tokens', 0) / 1_000_000) * table['input_per_million'] \
        + (usage.get('completion_tokens', 0) / 1_000_000) * table['output_per_million']


class Budget:
    """追加式账本：崩溃不丢已记账的花费，闸门跨重启依然有效。"""

    def __init__(self, ledger_path, sdk_cap_usd, token_cap=None, call_cap=None):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.sdk_cap_usd = sdk_cap_usd
        self.token_cap = token_cap
        self.call_cap = call_cap

    def _rows(self):
        if not self.ledger_path.exists():
            return []
        return [json.loads(line) for line in self.ledger_path.read_text().splitlines() if line.strip()]

    def totals(self):
        rows = self._rows()
        usage = {'prompt_tokens': sum(r.get('prompt_tokens', 0) for r in rows),
                 'completion_tokens': sum(r.get('completion_tokens', 0) for r in rows)}
        return {'calls': len(rows),
                'failed_calls': sum(1 for r in rows if not r.get('ok')),
                'prompt_tokens': usage['prompt_tokens'],
                'completion_tokens': usage['completion_tokens'],
                'total_tokens': usage['prompt_tokens'] + usage['completion_tokens'],
                'sdk_equivalent_usd': round(_cost(usage, PRICE_TABLES['sdk_equivalent_claude']), 6),
                'declared_usd': round(_cost(usage, PRICE_TABLES['declared_deepseek']), 6)}

    def stop_reason(self):
        totals = self.totals()
        if totals['sdk_equivalent_usd'] >= self.sdk_cap_usd:
            return 'SDK_BUDGET_CAP'
        if self.token_cap is not None and totals['total_tokens'] >= self.token_cap:
            return 'TOKEN_CAP'
        if self.call_cap is not None and totals['calls'] >= self.call_cap:
            return 'CALL_CAP'
        return None

    def assert_within(self):
        reason = self.stop_reason()
        if reason:
            raise BudgetExceeded(f'预算闸门触发：{reason}；累计 {json.dumps(self.totals(), ensure_ascii=False)}')

    def record(self, purpose, model, usage, ok=True, error=None):
        prompt = int(usage.get('prompt_tokens') or 0)
        completion = int(usage.get('completion_tokens') or 0)
        details = usage.get('completion_tokens_details') or {}
        row = {'occurred_at': datetime.now(timezone.utc).isoformat(), 'purpose': purpose,
               'model': model, 'prompt_tokens': prompt, 'completion_tokens': completion,
               'reasoning_tokens': int(details.get('reasoning_tokens') or 0), 'ok': ok}
        if error:
            row['error'] = str(error)[:300]
        with self.ledger_path.open('a') as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        return row


class LlmClient:
    def __init__(self, config, budget, timeout=90):
        missing = [key for key in ('TAG_LLM_BASE_URL', 'TAG_LLM_MODEL', 'TAG_LLM_API_KEY') if not config.get(key)]
        if missing:
            raise ValueError(f'.tag-llm-config 缺少 {missing}')
        self.base_url = config['TAG_LLM_BASE_URL'].rstrip('/')
        if self.base_url.endswith('/anthropic'):
            self.base_url = self.base_url[: -len('/anthropic')]
        self.model = config['TAG_LLM_MODEL']
        self._api_key = config['TAG_LLM_API_KEY']
        self.budget = budget
        self.timeout = timeout

    def complete(self, purpose, system, user, temperature=0.2, max_tokens=1200, extra=None):
        self.budget.assert_within()
        payload = {'model': self.model, 'stream': False, 'temperature': temperature,
                   'max_tokens': max_tokens,
                   'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
        if extra:
            payload.update(extra)
        request = urllib.request.Request(
            f'{self.base_url}/chat/completions',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json',
                     'Authorization': f'Bearer {self._api_key}'})
        data = self._post(request, purpose)
        usage = data.get('usage') or {}
        self.budget.record(purpose, self.model, usage, ok=True)
        choices = data.get('choices') or []
        if not choices:
            raise ValueError('模型返回没有 choices')
        return {'text': choices[0]['message']['content'], 'finish_reason': choices[0].get('finish_reason'),
                'usage': usage}

    def _post(self, request, purpose):
        """带重试的投递：响应被截断、连接中断、5xx/429 都是瞬时故障，不该掀掉整批。"""
        last_error = None
        for attempt in range(HTTP_ATTEMPTS):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                body = error.read().decode('utf-8', 'replace')[:300]
                last_error = f'HTTP {error.code}: {body}'
                if error.code < 500 and error.code != 429:
                    self.budget.record(purpose, self.model, {}, ok=False, error=last_error)
                    raise
            except (urllib.error.URLError, http.client.IncompleteRead, http.client.HTTPException,
                    TimeoutError, ConnectionError) as error:
                last_error = f'{type(error).__name__}: {error}'
            if attempt + 1 < HTTP_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
        self.budget.record(purpose, self.model, {}, ok=False, error=str(last_error))
        raise ConnectionError(f'调用在 {HTTP_ATTEMPTS} 次尝试后仍失败：{last_error}')
