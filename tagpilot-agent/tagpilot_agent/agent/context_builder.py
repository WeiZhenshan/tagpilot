import asyncio
import json
from tagpilot_agent.domain.normalize import input_plan
from tagpilot_agent.domain.expressions import plan_tag_ids
from tagpilot_agent.guards.plan_validator import leaves
from tagpilot_agent.retrieval.working_set import merge, ensure_details
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveError
from tagpilot_agent.tools.cards import card

async def build_context(ctx):
    req=ctx.request
    context={'requirement':req['requirement'],'current_utterance':req.get('_utterance',req['requirement']),
             'history':req.get('history',[])[-12:],'questions':req.get('_questions',[]),'answer':req.get('_answer'),
             'authority_diagnostics':req.get('_repair',[])}
    if req.get('previous_plan',{}).get('tree'):
        context['previous_plan']=input_plan(req['previous_plan'])
        ids=plan_tag_ids(leaves(req['previous_plan']['tree'])) & ctx.eligible
        await ensure_details(ctx,ids)
    try:
        data=await asyncio.to_thread(ctx.retriever.lookup,req['requirement'],ctx.eligible,8)
        merge(ctx,data)
        context['prefetch']={'cards':[card(t) for t in data.get('selection_context',data).get('tags',[])], 'terms':data.get('terms',[])}
    except SemanticRetrieveError as exc:
        if exc.status_code in {401,403,409}:raise
        context['prefetch']={'unavailable':True}
    context['previous_cards']=[card(t) for t in ctx.tags.values()][:30]
    return json.dumps(context,ensure_ascii=False,separators=(',',':'))
