import asyncio
import json
from tagpilot_agent.domain.normalize import input_plan
from tagpilot_agent.domain.expressions import plan_tag_ids
from tagpilot_agent.guards.plan_validator import leaves
from tagpilot_agent.retrieval.working_set import merge, ensure_details
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveError
from tagpilot_agent.tools.cards import card
from tagpilot_agent.runtime.degrade import progress
from .clarification import clarification_state

async def build_context(ctx):
    req=ctx.request
    context={'requirement':req['requirement'],'current_utterance':req.get('_utterance',req['requirement']),
             'history':req.get('history',[])[-12:],'questions':req.get('_questions',[]),'answer':req.get('_answer'),
             'authority_diagnostics':req.get('_repair',[]),'budget':ctx.budget.snapshot(ctx)}
    context['clarification_state']=clarification_state(req)
    pinned=req.get('pinned_tag_ids',[])
    if pinned:
        await ensure_details(ctx,pinned)
        if not set(pinned)<=ctx.details_loaded:
            raise SemanticRetrieveError(409,'所选标签的发布详情不完整，请重新选择并核验')
        context['pinned_tags']=[{**card(ctx.tags[tid]),
            'allowed_operators':ctx.tags[tid].get('allowed_operators',[]),
            'caliber_struct':ctx.tags[tid].get('caliber_struct',{}),
            'code_values':[c for c in ctx.codes if int(c['tag_id'])==tid][:40],
            'code_values_truncated':sum(int(c['tag_id'])==tid for c in ctx.codes)>40} for tid in pinned]
        context['pinned_only']=req.get('pinned_only',False)
        context['pinned_instruction']='用户主动选择的优先候选；只选标签不代表已指定取值。缺阈值、码值或条件组合关系必须分轮追问，不猜值；保留上一版条件。'
    # 评测/生产注入的固定基准日：相对时间表达只能以它为准，不能用运行当天。
    if req.get('reference_date'):
        context['reference_date']=req['reference_date']
        context['timezone']=req.get('timezone') or 'Asia/Shanghai'
    if req.get('previous_plan',{}).get('tree'):
        context['previous_plan']=input_plan(req['previous_plan'])
        nodes=leaves(req['previous_plan']['tree'])
        if progress(req['previous_plan']):
            unresolved=[n for n in nodes if n.get('gap_reason')=='BUDGET_EXHAUSTED']
            context['resume']={'unresolved_clause_ids':[n['clause_id'] for n in unresolved],
                'kept_clause_ids':[n['clause_id'] for n in nodes if n.get('status')=='BOUND'],
                'instruction':'只处理未解决条件；已保留条件不要重新检索或修改'}
            nodes=unresolved
        ids=plan_tag_ids(nodes) & ctx.eligible
        await ensure_details(ctx,ids)
    try:
        query='；'.join(n.get('source_span','') for n in nodes) if context.get('resume') else req['requirement']
        data=await asyncio.to_thread(ctx.retriever.lookup,query or req['requirement'],ctx.eligible,8)
        merge(ctx,data)
        context['prefetch']={'cards':[card(t) for t in data.get('selection_context',data).get('tags',[])], 'terms':data.get('terms',[])}
    except SemanticRetrieveError as exc:
        if exc.status_code in {401,403,409}:raise
        ctx.stats['retrieval_unavailable']=True
        context['prefetch']={'unavailable':True}
    context['previous_cards']=[card(t) for t in ctx.tags.values()][:30]
    return json.dumps(context,ensure_ascii=False,separators=(',',':'))
