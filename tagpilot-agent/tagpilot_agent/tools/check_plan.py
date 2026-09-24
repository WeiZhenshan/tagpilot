import json
from tagpilot_agent.guards.guard import check, plan_hash
from tagpilot_agent.guards.plan_validator import leaves

async def check_plan(ctx,args):
    plan=await check(args['plan'],ctx)
    fingerprint=json.dumps(plan['diagnostics'],sort_keys=True,ensure_ascii=False)
    ctx.diagnostic_repeats=ctx.diagnostic_repeats+1 if fingerprint==ctx.last_diagnostic else 0
    ctx.last_diagnostic=fingerprint
    return {'ok':plan['valid'],'plan_hash':plan_hash(plan),'clauses':[{'clause_id':n['clause_id'],'status_hint':n.get('status'),'name':n.get('name')} for n in leaves(plan['tree'])] if plan.get('tree') else [],
            'diagnostics':plan['diagnostics'],'hint':'无新进展，请换思路或提交 PARTIAL' if ctx.diagnostic_repeats>=1 else None}

