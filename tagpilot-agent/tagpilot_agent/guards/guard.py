"""SDK 无关的统一校验入口；工具、提交和手工编辑共用。"""
from copy import deepcopy
import hashlib
import json
from pydantic import ValidationError
from tagpilot_agent.domain.plan_model import AudiencePlan
from tagpilot_agent.domain.normalize import normalize_plan, input_plan
from tagpilot_agent.domain.expressions import plan_tag_ids
from tagpilot_agent.retrieval.working_set import ensure_details
from .plan_validator import validate_plan, leaves
from .ledger import capture_intent, frozen_errors
from .diagnostics import diagnostic
from .literals import check_literals, literal_warnings
from tagpilot_agent.telemetry import span

async def check(plan,ctx,strict=False,trusted=False):
    try:
        if trusted:plan=input_plan(plan)
        plan=normalize_plan(plan)
        # 先检查深度/总节点，随后才进入递归 Pydantic。
        leaves(plan['tree'])
        plan=AudiencePlan.model_validate(plan).model_dump(exclude_none=True)
        if ctx.request.get('_manual_edit'):
            assumptions=(plan.get('intent_plan') or {}).get('assumptions',[])
            plan['intent_plan']=capture_intent(plan,ctx.request['requirement'],rebuild=True)
            refs={r['requirement_id'] for r in plan['intent_plan']['requirements']}
            plan['intent_plan']['assumptions']=[a for a in assumptions if a.get('requirement_id') in refs]
        else:plan['intent_plan']=capture_intent(plan,ctx.request['requirement'])
        for key in ('unresolved_slots','hypotheses_to_check'):plan['intent_plan'].pop(key,None)
        for r in plan['intent_plan']['requirements']:r.pop('resolution_state',None)
        nodes=leaves(plan['tree']);ids=plan_tag_ids(nodes)
        if not ids<=ctx.eligible:
            errors=[diagnostic('INELIGIBLE_TAG','方案引用了资格外标签')]
        else:
            with span(ctx.emit,'guard.evidence',count=len(ids)):
                await ensure_details(ctx,ids)
            confirmed=unchanged_confirmations(plan,ctx.request)
            declared_gaps={n['clause_id']:n.get('gap_reason') for n in nodes if n.get('gap_reason')}
            plan=validate_plan(plan,ctx.tags,ctx.codes,ctx.eligible,ctx.capabilities)
            errors=plan['diagnostics']
            for n in nodes:
                n['status']='BOUND' if n.get('status')=='BOUND' else 'GAP'
                if n['clause_id'] in declared_gaps:
                    n.update(status='GAP',gap_reason=declared_gaps[n['clause_id']])
                    errors.append(diagnostic('REQUIREMENT_MISSING',n['gap_reason'],n['clause_id']))
                if n.get('tag_id') in ctx.tags:
                    n['caliber_struct']=ctx.tags[n['tag_id']].get('caliber_struct',{})
                for a in plan['intent_plan'].get('assumptions',[]):
                    if a.get('requirement_id') not in n.get('requirement_ids',[]):continue
                    if a['status']=='PUBLISHED':
                        ref=a.get('definition_ref') or {};cap=ctx.capabilities.get(ref.get('capability_id'))
                        if not ((ref.get('tag_id') in ctx.tags) or (cap and str(cap.get('version'))==str(ref.get('version')))):
                            errors.append(diagnostic('UNSUPPORTED_CAPABILITY','业务解释缺少已发布证据',n['clause_id']))
                        n.update(status='BOUND' if n['clause_id'] in confirmed else 'ASSUMED',assumption=a,assumption_confirmed=n['clause_id'] in confirmed)
                        if n['clause_id'] not in confirmed:
                            errors.append(diagnostic('BUSINESS_AMBIGUITY','请确认采用的已发布业务定义',n['clause_id'],decision=True))
                    elif a['status']=='CONFIRMED' and n['clause_id'] not in confirmed:
                        errors.append(diagnostic('BUSINESS_AMBIGUITY','业务解释尚未由用户确认',n['clause_id'],decision=True))
            if not ctx.request.get('_manual_edit'):
                errors.extend(check_literals(plan,ctx.request,ctx.tags))
                warnings=literal_warnings(plan,ctx.request)
                if warnings:
                    plan['warnings']=warnings
                    ctx.emit({'type':'guard.warning','message':'请核对否定与条件连接关系','warnings':warnings})
            if not ctx.request.get('_manual_edit'):
                errors.extend(frozen_errors(ctx.request.get('previous_plan') or {},plan,ctx.request.get('_utterance',ctx.request['requirement']),
                    ([q.get('requirement_id') or q.get('clause_id') for q in ctx.request.get('_questions',[])] if ctx.request.get('_answer') else []) +
                    [rid for n in nodes if any(d.get('clause_id')==n['clause_id'] for d in ctx.request.get('_repair',[])) for rid in n.get('requirement_ids',[n['clause_id']])]))
    except (ValidationError,ValueError,TypeError,KeyError,RecursionError) as exc:
        errors=[diagnostic('SCHEMA_INVALID','方案结构不符合契约，请检查字段、类型、深度及数量')]
        if isinstance(exc,ValidationError):errors[0]['hint']=[{'path':list(e['loc']),'type':e['type']} for e in exc.errors()[:8]]
        plan=deepcopy(ctx.best_plan or ctx.request.get('previous_plan') or {})
    plan.update(schema_version=3,valid=not errors,diagnostics=errors,
                plan_status='READY' if not errors else 'DRAFT',**{k:ctx.request[k] for k in ('build_id','snapshot_id','artifact_hash')})
    if plan.get('tree'):
        if not ctx.intent_emitted:
            ctx.intent_emitted=True;ctx.emit({'type':'intent.ready','message':'已整理圈选条件','plan':plan})
        if len(errors)<=ctx.best_errors:
            ctx.best_plan=deepcopy(plan);ctx.best_errors=len(errors)
        ctx.emit({'type':'plan.observed','message':'条件核验通过' if not errors else '正在核验待处理条件','plan':plan})
    return plan


def plan_hash(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def unchanged_confirmations(plan,request):
    """确认只对上一版相同条件与定义生效；沿用 clause_id 不得继承修改前的确认。"""
    previous=request.get('previous_plan') or {}
    if not previous.get('tree'):return set()
    prior=AudiencePlan.model_validate(normalize_plan(input_plan(previous))).model_dump(exclude_none=True)
    old={n['clause_id']:n for n in leaves(prior['tree'])}
    assumptions=lambda p,rid:[a for a in (p.get('intent_plan') or {}).get('assumptions',[]) if a['requirement_id']==rid]
    return {n['clause_id'] for n in leaves(plan['tree'])
            if n['clause_id'] in request.get('confirmed_clause_ids',[]) and old.get(n['clause_id'])==n
            and all(assumptions(prior,rid)==assumptions(plan,rid) for rid in n.get('requirement_ids',[]))}
