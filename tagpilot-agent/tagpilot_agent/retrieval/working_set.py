"""一次运行共享的证据；版本与资格永远由可信请求决定。"""
import asyncio
import os
from copy import deepcopy
from .cache import details_cache, eligible_hash
from .semantic_client import SemanticRetrieveError


def merge(ctx,data,details=False):
    for key in ('build_id','snapshot_id','artifact_hash'):
        if data.get(key)!=ctx.request[key]:raise SemanticRetrieveError(409,'发布证据版本不一致')
    if data.get('eligible_hash') and data['eligible_hash']!=eligible_hash(ctx.eligible):
        raise SemanticRetrieveError(409,'标签资格摘要不一致')
    context=data.get('selection_context',data)
    tags=context.get('tags',[])
    if any(int(t['tag_id']) not in ctx.eligible for t in tags):raise SemanticRetrieveError(403,'返回了资格外标签')
    codes=context.get('code_values',[])
    if any(int(c['tag_id']) not in ctx.eligible for c in codes):raise SemanticRetrieveError(403,'返回了资格外码值')
    ctx.tags.update({int(t['tag_id']):deepcopy(t) for t in tags})
    index={(int(c['tag_id']),str(c['code'])):c for c in ctx.codes}
    index.update({(int(c['tag_id']),str(c['code'])):deepcopy(c) for c in codes})
    ctx.codes=list(index.values())
    for cap in data.get('capabilities',[]):
        if not set(cap.get('input_tag_ids',[]))<=ctx.eligible:raise SemanticRetrieveError(403,'能力包含资格外指标')
        ctx.capabilities[str(cap['capability_id'])]=deepcopy(cap)
    if details:ctx.details_loaded.update(int(t['tag_id']) for t in tags)


async def ensure_details(ctx,ids):
    ids=set(ids)
    if not ids<=ctx.eligible:raise ValueError('INELIGIBLE_TAG')
    missing=[]
    for tid in ids-ctx.details_loaded:
        cached=details_cache.get((*ctx.cache_scope,tid))
        if cached:merge(ctx,cached,True)
        else:missing.append(tid)
    for offset in range(0,len(missing),10):
        batch=missing[offset:offset+10]
        ctx.stats['evidence_requests']=ctx.stats.get('evidence_requests',0)+1
        if ctx.stats['evidence_requests']>int(os.getenv('TAG_AGENT_MAX_DETAILS','6')):raise ValueError('详情读取预算已用完')
        data=await asyncio.to_thread(ctx.retriever.evidence,batch,ctx.request['requirement'],ctx.eligible)
        merge(ctx,data,True)
        # 完整校验用码值留在进程内，向模型呈现时才过滤截断。
        for tid in batch:
            context=data.get('selection_context',data)
            if tid not in ctx.tags:continue
            details_cache.put((*ctx.cache_scope,tid),{**{k:data[k] for k in ('build_id','snapshot_id','artifact_hash')},
                'tags':[ctx.tags[tid]],'code_values':[c for c in context.get('code_values',[]) if int(c['tag_id'])==tid]})
