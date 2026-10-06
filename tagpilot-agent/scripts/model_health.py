"""TagPilot Agent 模型链路健康检查。

用 httpx 与浏览器型 UA 发起请求（裸 urllib 默认 UA 会被 Cloudflare 拦截并返回 1010），
断言上游响应不是 Cloudflare 1010，也不是 OpenCode 的 MissingSessionID。
取值优先级：命令行 > 环境变量 > 仓库根 .tag-llm-config；只输出判定结果，不输出密钥。

用法：
  tagpilot-agent/.venv/bin/python tagpilot-agent/scripts/model_health.py \
      [--service-url http://127.0.0.1:8092] [--base-url ...] [--output out.json]
"""
import argparse
import json
import os
from pathlib import Path
import sys

import httpx

BROWSER_UA=('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/126.0 Safari/537.36 TagPilot-HealthCheck/1.0')
SESSION_HEADER='x-opencode-session'
DEFAULT_SESSION='tagpilot-insight'
DEFAULT_CONFIG=Path(__file__).resolve().parents[2]/'.tag-llm-config'


def load_shell_config(path):
    """读取 KEY=VALUE / export KEY=VALUE 形式的简单配置文件。"""
    values={}
    try:
        text=Path(path).read_text(encoding='utf-8')
    except OSError:
        return values
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line=line[len('export '):].strip()
        name,sep,value=line.partition('=')
        if not sep:
            continue
        value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in '\'"':
            value=value[1:-1]
        values[name.strip()]=value
    return values


def resolve(config_path):
    file_values=load_shell_config(config_path) if config_path else {}

    def pick(name):
        return os.getenv(name) or file_values.get(name) or ''

    return {'base_url':pick('ANTHROPIC_BASE_URL') or pick('TAG_LLM_BASE_URL'),
            'api_key':pick('ANTHROPIC_API_KEY') or pick('ANTHROPIC_AUTH_TOKEN') or pick('TAG_LLM_API_KEY'),
            'model':pick('ANTHROPIC_MODEL') or pick('TAG_LLM_MODEL') or 'deepseek-chat',
            'custom_headers':pick('ANTHROPIC_CUSTOM_HEADERS')}


def parse_headers(raw):
    headers={}
    for line in (raw or '').splitlines():
        name,sep,value=line.partition(':')
        if sep and name.strip():
            headers[name.strip()]=value.strip()
    return headers


def check_service(url, timeout):
    try:
        with httpx.Client(timeout=timeout, headers={'user-agent':BROWSER_UA}) as client:
            response=client.get(url.rstrip('/')+'/health')
        payload=response.json() if response.status_code==200 else {}
        return {'ok':response.status_code==200 and payload.get('status')=='ok',
                'status':response.status_code,'body':payload}
    except httpx.HTTPError as exc:
        return {'ok':False,'error':type(exc).__name__,'message':str(exc)[:200]}


def check_upstream(base,key,model,headers,timeout):
    result={'url':base.rstrip('/')+'/v1/messages','model':model,
            'injected_headers':sorted(name.lower() for name in headers)}
    if not base or not key:
        return {**result,'ok':False,'error':'缺少 ANTHROPIC_BASE_URL 或模型密钥'}
    request_headers={'content-type':'application/json','anthropic-version':'2023-06-01',
                     'user-agent':BROWSER_UA,'x-api-key':key}
    request_headers.update(headers)
    try:
        with httpx.Client(timeout=timeout) as client:
            response=client.post(result['url'],json={'model':model,'max_tokens':1,
                                                     'messages':[{'role':'user','content':'ping'}]},headers=request_headers)
    except httpx.HTTPError as exc:
        return {**result,'ok':False,'error':type(exc).__name__,'message':str(exc)[:200]}
    body=response.text
    result.update(status=response.status_code,
                  cloudflare_1010='error code: 1010' in body.lower(),
                  missing_session_id='missingsessionid' in body.lower(),
                  body_head=body[:200])
    result['ok']=response.status_code==200 and not result['cloudflare_1010'] and not result['missing_session_id']
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='TagPilot Agent 模型链路健康检查')
    parser.add_argument('--config',default=str(DEFAULT_CONFIG),help='LLM 配置文件（默认仓库根 .tag-llm-config）')
    parser.add_argument('--service-url',default='http://127.0.0.1:8092')
    parser.add_argument('--base-url',default='')
    parser.add_argument('--api-key',default='')
    parser.add_argument('--model',default='')
    parser.add_argument('--header',action='append',default=[],metavar='"Name: Value"',help='追加请求头，可重复')
    parser.add_argument('--timeout',type=float,default=30.0)
    parser.add_argument('--output',default='',help='同时写入 JSON 结果文件')
    parser.add_argument('--skip-service',action='store_true',help='跳过本机 8092 探活')
    args=parser.parse_args(argv)

    resolved=resolve(Path(args.config))
    base=args.base_url or resolved['base_url']
    headers=parse_headers(resolved['custom_headers'])
    for item in args.header:
        name,sep,value=item.partition(':')
        if sep and name.strip():
            headers[name.strip()]=value.strip()
    if 'opencode.ai' in base and SESSION_HEADER not in {name.lower() for name in headers}:
        headers[SESSION_HEADER]=os.getenv('TAG_OPENCODE_SESSION') or DEFAULT_SESSION

    report={'service':None,'upstream':check_upstream(base,args.api_key or resolved['api_key'],
                                                      args.model or resolved['model'],headers,args.timeout)}
    if not args.skip_service:
        report['service']=check_service(args.service_url,args.timeout)
    report['ok']=(report['service'] is None or report['service']['ok']) and report['upstream']['ok']

    text=json.dumps(report,ensure_ascii=False,indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text+'\n',encoding='utf-8')
    return 0 if report['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
