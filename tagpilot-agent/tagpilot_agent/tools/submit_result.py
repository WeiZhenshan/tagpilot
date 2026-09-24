from tagpilot_agent.guards.guard import check
from tagpilot_agent.guards.plan_validator import leaves

async def submit_result(ctx,args):
    plan=await check(args['plan'],ctx,strict=True)
    errors=[];outcome=args['outcome'];nodes=leaves(plan['tree']) if plan.get('tree') else []
    requirements={r['requirement_id'] for r in plan.get('intent_plan',{}).get('requirements',[])}
    if not nodes:errors.append('必须保留需求条件树')
    if outcome=='READY':
        if not plan['valid'] or any(n.get('status')!='BOUND' for n in nodes):errors.append('READY 须零阻断且所有条件 BOUND')
        if args['questions'] or args['gaps']:errors.append('READY 不能包含问题或缺口')
    if outcome=='NEEDS_USER_INPUT':
        if not args['questions']:errors.append('需要提供具体业务问题')
        for q in args['questions']:
            if q['requirement_id'] not in requirements:errors.append('问题必须对应需求')
            if q['reason']!='GOAL_UNCLEAR' and not ctx.searches.get(q['requirement_id']):errors.append('请先查证该需求，再提出业务问题')
            if any(x in q['prompt'] for x in ('tag_id','SQL','caliber','eligible','build_id')):errors.append('问题中不能包含技术字段')
    declared_refs={rid for n in nodes if n.get('gap_reason') for rid in n.get('requirement_ids',[])}
    if outcome=='CAPABILITY_GAP':
        declared_refs.update(rid for n in nodes if n.get('status')=='GAP' for rid in n.get('requirement_ids',[]))
    if not declared_refs <= {g['requirement_id'] for g in args['gaps']}:
        errors.append('已声明的业务缺口必须逐项列明 gaps 并提供检索留痕')
    for gap in args['gaps']:
        if gap['requirement_id'] not in requirements:errors.append('缺口必须对应需求')
        if not ctx.searches.get(gap['requirement_id'],set()) & {'deep','capabilities'}:errors.append('缺口须先做 deep 或能力检索')
        if not set(gap['nearest_tag_ids'])<=set(ctx.tags):errors.append('最近候选必须来自已检索证据')
    if outcome=='CAPABILITY_GAP' and not args['gaps']:errors.append('能力缺口必须列明 gaps')
    if errors:
        ctx.stats['submit_rejections']+=1
        if ctx.stats['submit_rejections']<=3:
            return {'ok':False,'errors':errors,'diagnostics':plan.get('diagnostics',[])}
        outcome='PARTIAL';ctx.stats['forced_partial']=True
    plan.update(valid=outcome=='READY' and plan['valid'],plan_status={'READY':'READY','NEEDS_USER_INPUT':'NEEDS_DECISION','CAPABILITY_GAP':'CAPABILITY_GAP','PARTIAL':'DRAFT'}[outcome])
    for n in nodes:
        if any(q['requirement_id'] in n.get('requirement_ids',[]) for q in args['questions']):n['status']='NEEDS_DECISION'
        for gap in args['gaps']:
            if gap['requirement_id'] in n.get('requirement_ids',[]):n.update(status='GAP',gap_reason=gap['reason'])
    ctx.accepted={**args,'outcome':outcome,'plan':plan,'questions':args['questions'] if outcome=='NEEDS_USER_INPUT' else []}
    ctx.best_plan=plan
    ctx.emit({'type':'plan.validated','message':'条件已核验' if plan['valid'] else '已保留待处理事项','plan':plan})
    for n in nodes:ctx.emit({'type':'clause.updated','clause_id':n['clause_id'],'message':n.get('name') or n.get('source_span')})
    ctx.emit({'type':'draft.ready','message':args['summary'] or '圈选方案已保存','plan':plan})
    ctx.submitted.set()
    return {'ok':True,'accepted':True,'outcome':outcome,'message':'已提交，请结束'}

