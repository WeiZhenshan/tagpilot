import os
from tagpilot_agent.retrieval.working_set import ensure_details

async def tag_details(ctx,args):
    if not set(args['tag_ids'])<=ctx.eligible:raise ValueError('INELIGIBLE_TAG：标签不在当前资格范围')
    ctx.stats['details']+=1
    if ctx.stats['details']>int(os.getenv('TAG_AGENT_MAX_DETAILS','6')):raise ValueError('详情读取预算已用完')
    await ensure_details(ctx,args['tag_ids'])
    result=[]
    for tid in args['tag_ids']:
        t=ctx.tags.get(tid)
        if not t:raise ValueError('UNKNOWN_TAG：未找到已发布标签')
        codes=[c for c in ctx.codes if int(c['tag_id'])==tid]
        if args.get('value_query'):
            q=args['value_query'].lower();codes=[c for c in codes if q in str(c.get('code','')).lower() or q in str(c.get('label','')).lower()]
        result.append({**{k:t.get(k) for k in ('tag_id','name','definition_long','allowed_operators','unit','unit_scale','caliber_struct','unknown_policy','family_members')},'code_values':codes[:args['max_values']],'code_count':len(codes)})
    return {'tags':result}

