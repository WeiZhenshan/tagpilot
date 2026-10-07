"""每轮独立的回环转发：仅记录请求时序，不保存消息、响应正文或凭据。"""
import asyncio
from contextlib import asynccontextmanager, nullcontext, suppress
import os
import socket
import time

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

HOP_HEADERS={'host','connection','transfer-encoding','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','upgrade'}


def parse_custom_headers(raw):
    """解析 ANTHROPIC_CUSTOM_HEADERS（每行 Name: Value），返回待补齐的请求头字典。"""
    parsed={}
    for line in (raw or '').splitlines():
        name,sep,value=line.partition(':')
        if sep and name.strip():parsed[name.strip()]=value.strip()
    return parsed


@asynccontextmanager
async def model_transport(ctx,base,key,custom_headers=''):
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    idle=max(.1,float(os.getenv('TAG_AGENT_MODEL_IDLE_TIMEOUT','25')))
    client=httpx.AsyncClient(timeout=httpx.Timeout(idle,connect=min(10.,idle)))
    pending=set()
    injected=parse_custom_headers(custom_headers)

    @app.post('/v1/{path:path}')
    async def forward(path:str,request:Request):
        if path not in {'messages','messages/count_tokens'}:return JSONResponse({},404)
        if request.headers.get('x-api-key')!=key and request.headers.get('authorization')!='Bearer '+key:
            return JSONResponse({},401)
        observed=path=='messages'
        start=time.monotonic();done=False;upstream=None
        metric={'request_id':len(ctx.stats.setdefault('model_requests',[]))+1,
                'started_at_s':round(ctx.budget.elapsed(ctx),3),'phase':ctx.stats.get('model_phase','explore')}
        if observed:
            ctx.stats['model_requests'].append(metric)
            ctx.emit({'type':'model.request.started',**metric})

        def finish(outcome):
            nonlocal done
            if done:return
            done=True
            if observed:
                metric.update(outcome=outcome,duration_ms=round((time.monotonic()-start)*1000))
                ctx.emit({'type':'model.request.completed',**metric})

        headers={k:v for k,v in request.headers.items() if k.lower() not in HOP_HEADERS}
        # 显式补齐 ANTHROPIC_CUSTOM_HEADERS（如 OpenCode 会话头），不依赖 CLI 是否已携带。
        present={k.lower() for k in headers}
        for name,value in injected.items():
            if name.lower() not in present:headers[name]=value
        url=base.rstrip('/')+'/v1/'+path
        if request.url.query:url+='?'+request.url.query
        task=asyncio.create_task(client.send(client.build_request('POST',url,content=await request.body(),headers=headers),stream=True))
        pending.add(task)
        try:
            while not task.done():
                await asyncio.wait({task},timeout=.05)
                if await request.is_disconnected():
                    task.cancel();finish('interrupted')
                    return JSONResponse({},499)
            upstream=await task
            metric.update(http_status=upstream.status_code,headers_ms=round((time.monotonic()-start)*1000))
        except httpx.TimeoutException:
            finish('idle_timeout')
            return JSONResponse({'type':'error','error':{'type':'api_error','message':'model request idle timeout'}},504)
        except httpx.HTTPError:
            finish('transport_error')
            return JSONResponse({'type':'error','error':{'type':'api_error','message':'model transport unavailable'}},502)
        except asyncio.CancelledError:
            finish('interrupted');raise
        finally:
            pending.discard(task)
            if not task.done():task.cancel()
            with suppress(asyncio.CancelledError,httpx.HTTPError):
                response=await task
                if upstream is None:await response.aclose()

        async def stream():
            try:
                async for chunk in upstream.aiter_raw():
                    metric.setdefault('first_byte_ms',round((time.monotonic()-start)*1000))
                    yield chunk
                finish('ok' if upstream.status_code<400 else 'http_error')
            except httpx.TimeoutException:
                finish('idle_timeout')
            except httpx.HTTPError:
                finish('transport_error')
            except asyncio.CancelledError:
                finish('interrupted');raise
            finally:
                await upstream.aclose()
        response_headers={k:v for k,v in upstream.headers.items() if k.lower() not in HOP_HEADERS}
        return StreamingResponse(stream(),status_code=upstream.status_code,headers=response_headers)

    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False,lifespan='off',timeout_graceful_shutdown=0))
    server.capture_signals=lambda:nullcontext()
    serving=asyncio.create_task(server.serve(sockets=[sock]))
    try:
        while not server.started:
            if serving.done():await serving;raise RuntimeError('模型观测转发未启动')
            await asyncio.sleep(.01)
        ctx.stats['model_idle_timeout_s']=idle
        yield f'http://127.0.0.1:{port}'
    finally:
        for task in pending:task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)
        server.should_exit=True
        with suppress(asyncio.CancelledError):await serving
        await client.aclose();sock.close()
