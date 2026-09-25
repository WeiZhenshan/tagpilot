"""真实 SDK/CLI 的本地 Messages API：按剧本返回原生 tool_use，不调用外部模型。

剧本条目：call 列表（正常应答）、'error'（5xx）、'stall'（挂起直到客户端中断）。
"""
import asyncio
import json
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse


def create_gateway(script):
    app=FastAPI();app.state.requests=[];app.state.script=list(script)
    @app.post('/v1/messages/count_tokens')
    async def count():return {'input_tokens':100}
    @app.post('/v1/messages')
    async def messages(request:Request):
        body=await request.json();app.state.requests.append(body)
        index=min(len(app.state.requests)-1,len(app.state.script)-1)
        calls=app.state.script[index] if app.state.script else []
        if calls in ('error','stall'):
            if calls=='stall':
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    if await request.is_disconnected():break
                    await asyncio.sleep(.2)
            return JSONResponse(status_code=500,content={'type':'error','error':{'type':'api_error','message':'fake gateway failure'}})
        content=[{'type':'tool_use','id':'toolu_'+uuid.uuid4().hex,'name':name,'input':args} for name,args in calls]
        if not content:content=[{'type':'text','text':'已处理'}]
        response={'id':'msg_'+uuid.uuid4().hex,'type':'message','role':'assistant','model':body.get('model','fake'),
                  'content':content,'stop_reason':'tool_use' if calls else 'end_turn','stop_sequence':None,'usage':{'input_tokens':100,'output_tokens':100}}
        if not body.get('stream'):return response
        async def events():
            def event(kind,data):return 'event: '+kind+'\ndata: '+json.dumps({'type':kind,**data},ensure_ascii=False)+'\n\n'
            yield event('message_start',{'message':{**response,'content':[],'stop_reason':None}})
            for i,block in enumerate(content):
                if block['type']=='tool_use':
                    yield event('content_block_start',{'index':i,'content_block':{**block,'input':{}}})
                    yield event('content_block_delta',{'index':i,'delta':{'type':'input_json_delta','partial_json':json.dumps(block['input'],ensure_ascii=False)}})
                else:
                    yield event('content_block_start',{'index':i,'content_block':{'type':'text','text':''}})
                    yield event('content_block_delta',{'index':i,'delta':{'type':'text_delta','text':block['text']}})
                yield event('content_block_stop',{'index':i})
            yield event('message_delta',{'delta':{'stop_reason':response['stop_reason'],'stop_sequence':None},'usage':{'output_tokens':100}})
            yield event('message_stop',{})
        return StreamingResponse(events(),media_type='text/event-stream')
    return app
