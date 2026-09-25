"""把评测产出的 READY 方案经运行中的 Java 权威编译并用模拟库实测人数，与案例文档金标准对齐。

只读评测报告与案例文档；通过 Java 工作台接口执行 count/preview，不建群、不改数据。
用法：PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python tagpilot-agent/scripts/java_count_alignment.py \
  --report <评测报告>.json --output <对齐报告>.json [--limit N]
"""
import argparse
import hashlib
import json
import random
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

JAVA = 'http://127.0.0.1:8080'
CASES = 'sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md'


def request(method, path, token=None, body=None, timeout=180):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    call = urllib.request.Request(JAVA + path, data=data, method=method)
    call.add_header('Content-Type', 'application/json')
    if token:
        call.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(call, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return {'http_error': exc.code, 'body': exc.read().decode()[:400]}


def login():
    captcha = request('GET', '/captchaImage')
    uuid = captcha['uuid']
    code = subprocess.check_output(['redis-cli', 'get', 'captcha_codes:' + uuid], text=True).strip().strip('"')
    payload = request('POST', '/login', body={'username': 'admin', 'password': 'admin123', 'code': code, 'uuid': uuid})
    if payload.get('code') != 200:
        raise SystemExit('登录失败: %s' % json.dumps(payload, ensure_ascii=False)[:300])
    return payload['token']


def gold_counts(path):
    counts = {}
    for line in Path(path).read_text().splitlines():
        match = re.match(r'^\| ([A-K]\d\d) \|', line)
        if not match:
            continue
        cells = [cell.strip() for cell in line.split('|')]
        counts[match.group(1)] = int(cells[4])
    return counts


def wait_thread(token, thread, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = request('GET', '/taglibrary/agent/threads/' + thread, token)
        state = payload.get('data') or {}
        if state.get('status') != 'RUNNING':
            return state
        time.sleep(.5)
    return {'status': 'TIMEOUT'}


def run_case(token, case, plan):
    created = request('POST', '/taglibrary/agent/threads', token, {'library_id': 107})
    if created.get('code') != 200:
        return {'case': case, 'stage': 'create_thread', 'error': created}
    thread = created['data']['thread_id']
    client = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=24))
    started = request('POST', f'/taglibrary/agent/threads/{thread}/runs', token,
                      {'client_request_id': client, 'base_revision': created['data']['revision'],
                       'message': '编辑圈选条件', 'plan': plan})
    if started.get('code') != 200:
        return {'case': case, 'stage': 'start', 'error': started}
    state = wait_thread(token, thread)
    result = {'case': case, 'thread': thread, 'status': state.get('status'),
              'plan_valid': bool((state.get('plan') or {}).get('valid')),
              'plan_status': (state.get('plan') or {}).get('plan_status'),
              'diagnostics': (state.get('plan') or {}).get('diagnostics')}
    if state.get('status') != 'COMPLETED' or not result['plan_valid']:
        return result
    plan_hash = (state.get('plan') or {}).get('hash')
    counted = request('POST', f'/taglibrary/agent/threads/{thread}/count', token,
                      {'base_revision': state.get('revision'), 'plan_hash': plan_hash})
    if counted.get('code') != 200:
        result['stage'] = 'count'
        result['error'] = counted
        return result
    count_map = (counted.get('data') or {}).get('count') or {}
    result['count'] = count_map.get('value')
    preview = request('POST', f'/taglibrary/agent/threads/{thread}/preview', token,
                      {'base_revision': state.get('revision'), 'plan_hash': plan_hash})
    rows = (preview.get('data') or {}).get('rows') if preview.get('code') == 200 else None
    if isinstance(rows, list):
        ids = sorted(str(row.get('cust_id') or row.get('CUST_ID') or row) for row in rows)
        result['preview_rows'] = len(rows)
        result['preview_id_sha256'] = hashlib.sha256('\n'.join(ids).encode()).hexdigest()[:16]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text())
    gold = gold_counts(CASES)
    ready = []
    seen = set()
    for item in report['results']:
        plan = item.get('plan') or {}
        outcome = (item.get('outcome') or {}).get('outcome')
        if item['case'] in seen or not plan.get('valid') or outcome != 'READY':
            continue
        seen.add(item['case'])
        ready.append((item['case'], plan))
    if args.limit:
        ready = ready[:args.limit]
    output_path = Path(args.output)
    output = {'mode': 'java_authority_compile_and_count', 'library_id': 107, 'ready_cases': [case for case, _ in ready],
              'results': [], 'started_at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    done = set()
    if output_path.exists():
        output = json.loads(output_path.read_text())
        done = {row['case'] for row in output['results']}
    token = login()
    for case, plan in ready:
        if case in done:
            continue
        row = run_case(token, case, plan)
        row['gold_count'] = gold.get(case)
        if 'count' in row and row['count'] is not None:
            row['match'] = int(row['count']) == int(gold.get(case, -1))
        output['results'].append(row)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({key: row.get(key) for key in ('case', 'status', 'plan_valid', 'count', 'gold_count', 'match', 'error')}, ensure_ascii=False), flush=True)
    matched = sum(1 for row in output['results'] if row.get('match'))
    counted = sum(1 for row in output['results'] if 'count' in row)
    output['summary'] = {'ready': len(ready), 'processed': len(output['results']), 'counted': counted, 'matched': matched,
                         'java_rejected': sum(1 for row in output['results'] if not row.get('plan_valid'))}
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(output['summary'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
