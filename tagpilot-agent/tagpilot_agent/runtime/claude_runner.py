"""SDK 薄适配：每次运行独立目录、禁用内置工具、结束即清理。"""
import asyncio
import contextlib
import os
from pathlib import Path
import tempfile
import time
import psutil
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, PermissionResultAllow, PermissionResultDeny, ResultMessage, AssistantMessage, HookMatcher
from tagpilot_agent.agent.system_prompt import SYSTEM_PROMPT
from tagpilot_agent.tools.registry import create_server, MODELS

DENIED=['Bash','Read','Write','Edit','Glob','Grep','WebFetch','WebSearch','Task','Agent','Skill','TodoWrite','AskUserQuestion','NotebookEdit']

async def allow_tool(name,args,context):
    if name in {'mcp__tagpilot__'+n for n in MODELS}:return PermissionResultAllow(updated_input=args)
    return PermissionResultDeny(message='仅允许圈选领域工具')

class ClaudeRunner:
    async def run(self,ctx,prompt):
        model=os.getenv('ANTHROPIC_MODEL') or os.getenv('TAG_LLM_MODEL','deepseek-chat')
        base=os.getenv('ANTHROPIC_BASE_URL','')
        key=os.getenv('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_AUTH_TOKEN') or os.getenv('TAG_LLM_API_KEY','')
        if not base or not key:raise RuntimeError('请配置 Anthropic 兼容端点及密钥')
        with tempfile.TemporaryDirectory(prefix='tagpilot-sdk-') as directory:
            env={'CLAUDE_CONFIG_DIR':directory,'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1','DISABLE_TELEMETRY':'1',
                 'ANTHROPIC_BASE_URL':base,'ANTHROPIC_API_KEY':key,'ANTHROPIC_AUTH_TOKEN':key,
                 'ANTHROPIC_MODEL':model,'ANTHROPIC_SMALL_FAST_MODEL':model,'CLAUDECODE':'',
                 'API_TIMEOUT_MS':'60000','ANTHROPIC_MAX_RETRIES':'0','CLAUDE_CODE_DISABLE_AUTO_MEMORY':'1','CLAUDE_CODE_DISABLE_BACKGROUND_TASKS':'1'}
            async def after_tool(hook_input,tool_use_id,context):
                return {'continue_':False,'stopReason':'圈选结果已提交'} if ctx.accepted else {}
            options=ClaudeAgentOptions(tools=[],allowed_tools=['mcp__tagpilot__'+n for n in MODELS],disallowed_tools=DENIED,
                mcp_servers={'tagpilot':create_server(ctx)},hooks={'PostToolUse':[HookMatcher(matcher='mcp__tagpilot__submit_result',hooks=[after_tool])]},can_use_tool=allow_tool,setting_sources=[],cwd=directory,env=env,
                extra_args={'strict-mcp-config':None,'no-session-persistence':None},system_prompt=SYSTEM_PROMPT,
                model=model,max_turns=int(os.getenv('TAG_AGENT_MAX_TURNS','10')),
                max_budget_usd=float(os.getenv('TAG_AGENT_MAX_BUDGET_USD','1')),thinking={'type':'disabled'},
                enable_file_checkpointing=False,stderr=lambda _:None)
            started=time.monotonic()
            # connect/disconnect 必须在同一协程，避免 AnyIO cancel-scope 跨任务。
            async with ClaudeSDKClient(options=options) as client:
                ctx.stats['cli_start_ms']=round((time.monotonic()-started)*1000)
                monitor=asyncio.create_task(self.watch(client,ctx))
                try:
                    await client.query(prompt)
                    async for message in client.receive_response():
                        if isinstance(message,AssistantMessage):
                            ctx.stats['llm_turns']+=1
                            if getattr(message,'error',None):ctx.stats['sdk_error']=message.error
                        if isinstance(message,ResultMessage):
                            ctx.stats['sdk_result']=message.subtype
                            ctx.stats['sdk_cost_estimate_usd']=message.total_cost_usd
                            ctx.stats['llm_turns']=message.num_turns
                            if message.usage:ctx.stats['usage']=message.usage
                            if message.is_error and not ctx.accepted and message.subtype not in {'error_max_turns','error_max_budget_usd'}:
                                raise RuntimeError('模型网关或 SDK 返回错误')

                finally:
                    monitor.cancel()
                    with contextlib.suppress(asyncio.CancelledError):await monitor
            # TemporaryDirectory 同时清理 transcript/config，任何退出路径都适用。

    async def watch(self,client,ctx):
        while True:
            try:await asyncio.wait_for(ctx.submitted.wait(),.1)
            except TimeoutError:pass
            reason=None
            if ctx.submitted.is_set():reason='submitted'
            elif ctx.cancelled():reason='cancelled'
            elif time.monotonic()-ctx.started>float(os.getenv('TAG_AGENT_HARD_TIMEOUT','90')):reason='timeout'
            try:
                # SDK 0.1.50 锁定版本的唯一内部适配点；仅统计该运行的 CLI 子树。
                process=getattr(getattr(client,'_transport',None),'_process',None)
                if process:
                    parent=psutil.Process(process.pid)
                    rss=sum(p.memory_info().rss for p in [parent,*parent.children(recursive=True)] if p.is_running())/1024**2
                    ctx.stats['cli_peak_rss_mb']=round(max(rss,ctx.stats.get('cli_peak_rss_mb',0)),2)
                    if rss>float(os.getenv('TAG_AGENT_MAX_RSS_MB','600')):reason='memory_limit'
            except (psutil.Error,ProcessLookupError):pass
            if reason:
                ctx.stats['stop_reason']=reason
                if reason=='submitted':await asyncio.sleep(.05)
                with contextlib.suppress(Exception):await asyncio.wait_for(client.interrupt(),5)
                return
