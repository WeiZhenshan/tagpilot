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
