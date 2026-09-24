import asyncio
import os
from tagpilot_agent.retrieval.working_set import merge
from tagpilot_agent.retrieval.cache import cards_cache
from .cards import card

async def find_tags(ctx,args):
    depth=args['depth'];results=[];queries=args['queries']
    pending=[]
    for q in queries:
        key=(*ctx.cache_scope,' '.join(q['text'].lower().split()),depth,args['top_k'])
        cached=cards_cache.get(key)
        if cached:results.append((q,cached,True))
        else:pending.append((q,key))
    if pending:
        if depth=='deep':
            ctx.stats['deep']+=1
            if ctx.stats['deep']>int(os.getenv('TAG_AGENT_MAX_DEEP','4')):raise ValueError('深度检索预算已用完，请提交当前草案')
            data=await asyncio.to_thread(ctx.retriever.retrieve_batch,[q['text'] for q,k in pending],ctx.eligible,args['top_k'],'deep')
        else:
            data=await asyncio.gather(*(asyncio.to_thread(ctx.retriever.lookup,q['text'],ctx.eligible,args['top_k']) for q,k in pending))
        for (q,key),response in zip(pending,data):
            merge(ctx,response);cards_cache.put(key,response);results.append((q,response,False))
    output=[]
    for q,data,cached in results:
        merge(ctx,data)
        rid=q.get('requirement_id')
        if rid:ctx.searches.setdefault(rid,set()).add(depth)
        context=data.get('selection_context',data)
        candidates={int(c['tag_id']):c for c in data.get('candidates',[])}
        output.append({'requirement_id':rid,'cards':[card({**t,**{'matched_by':candidates.get(int(t['tag_id']),{}).get('matched_by','SEMANTIC' if depth=='deep' else 'LEXICAL')}}) for t in context.get('tags',[])],
                       'terms':data.get('terms',[]),'decision':data.get('decision'),'cached':cached})
    return {'results':output}

