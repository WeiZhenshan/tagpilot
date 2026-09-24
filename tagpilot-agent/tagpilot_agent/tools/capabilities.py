import asyncio
from tagpilot_agent.retrieval.working_set import merge
from .cards import card

async def capabilities(ctx,args):
    data=await asyncio.to_thread(ctx.retriever.capabilities,args['query'],ctx.eligible,args['capability_ids'])
    merge(ctx,data)
    for rid in args['requirement_ids']:ctx.searches.setdefault(rid,set()).add('capabilities')
    return {'capabilities':data.get('capabilities',[]),'cards':[card(t) for t in data.get('selection_context',data).get('tags',[])], 'operators':'TAG CONST ADD SUB MUL DIV COUNT_POSITIVE CAPABILITY；禁止 SQL 和自定义函数'}

