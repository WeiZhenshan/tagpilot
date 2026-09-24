"""启动本地假网关，通过真实 SDK/CLI 运行金标 A01 全量客户。"""
import asyncio
import json
import os
from pathlib import Path
import socket
import threading
import time
import uvicorn
from tests.fake_anthropic_gateway import create_gateway
from tests.test_sdk_smoke import Evidence, ALL
from tests.test_workbench import REQ
from tagpilot_agent.runtime.claude_runner import ClaudeRunner
from tagpilot_agent.runtime.run_context import RunContext
from tagpilot_agent.agent.context_builder import build_context

def main():
    gateway=create_gateway([[('mcp__tagpilot__submit_result',{'outcome':'READY','plan':ALL,'summary':'全部客户'})],[]])
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(gateway,log_level='error'))
    worker=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);worker.start()
    os.environ.update(ANTHROPIC_BASE_URL=f'http://127.0.0.1:{port}',ANTHROPIC_API_KEY='local-fake-key',ANTHROPIC_MODEL='fake-model')
    async def run():
        ctx=RunContext({**REQ,'requirement':'全部客户'},Evidence())
        await ClaudeRunner().run(ctx,await build_context(ctx))
        assert ctx.accepted and ctx.accepted['plan']['valid'],ctx.stats
        for req in gateway.state.requests:
            assert all(t['name'].startswith('mcp__tagpilot__') for t in req.get('tools',[])),[t['name'] for t in req.get('tools',[])]
        output={'case':'A01','mode':'real_sdk_fake_gateway','accepted':ctx.accepted['outcome'],'stats':ctx.stats,'requests':len(gateway.state.requests)}
        out=Path('out/sdk-gateway-smoke.json');out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(output,ensure_ascii=False,indent=2))
        print(json.dumps(output,ensure_ascii=False))
    try:asyncio.run(run())
    finally:server.should_exit=True;worker.join(timeout=5);sock.close()
if __name__=='__main__':main()
