"""用户业务要求与可重组的执行节点分离。原始要求不会随绑定结果丢失。"""
from __future__ import annotations
from copy import deepcopy
from tagpilot_agent.guards.diagnostics import diagnostic


def capture_intent(plan, requirement, rebuild=False):
    from tagpilot_agent.guards.plan_validator import leaves
    supplied = plan.get('intent_plan') or {}
    if not isinstance(supplied, dict):
        supplied = {}
    if not rebuild and supplied.get('requirements') and supplied.get('logic_tree'):
        return deepcopy(supplied)
    nodes = leaves(plan['tree'])
    requirements = []
    for node in nodes:
        refs=node.get('requirement_ids') or [node['clause_id']]
        rid = refs[0] if rebuild and len(refs)==1 else node['clause_id']
        node['requirement_ids'] = [rid]
        requirements.append({'requirement_id': rid, 'source_spans': [node.get('source_span') or requirement],
                             'business_meaning': node.get('source_span') or node.get('query') or requirement,
                             'origin': 'USER', 'resolution_state': 'PENDING'})
    def structure(tree):
        if 'children' in tree:
            return {'logic': tree['logic'], 'children': [structure(c) for c in tree['children']]}
        return {'requirement_id': tree['requirement_ids'][0]}
    return {'original_request': requirement, 'requirements': requirements,
            'logic_tree': structure(plan['tree']), 'assumptions': [], 'unresolved_slots': [],
            'hypotheses_to_check': deepcopy(supplied.get('assumptions') or [])}


def logic_signature(tree, execution=False, depth=0):
    if depth > 8 or not isinstance(tree, dict):
        raise ValueError('业务逻辑树格式非法')
    if 'children' not in tree:
        refs = (tree.get('requirement_ids') or [tree.get('clause_id')]) if execution else [tree.get('requirement_id')]
        if len(refs) != 1 or not refs[0]:
            raise ValueError('每项执行条件必须对应一项原始业务要求；组合计算放在该要求的表达式内')
        return ('REQ', str(refs[0]))
    logic = tree.get('logic')
    if logic not in {'AND', 'OR'} or not tree['children']:
        raise ValueError('业务逻辑树格式非法')
    children = set()
    for child in tree['children']:
        signature = logic_signature(child, execution, depth+1)
        children.update(signature[1:] if signature[0] == logic else [signature])
    if len(children) == 1:
        return next(iter(children))
    return (logic, *sorted(children))


def check_coverage(intent, nodes, tree=None):
    required = {r['requirement_id'] for r in intent.get('requirements', [])}
    covered, errors = set(), []
    for node in nodes:
        refs = node.get('requirement_ids') or [node['clause_id']]
        node['requirement_ids'] = refs
        if not set(refs) <= required:
            errors.append(diagnostic('INTENT_COVERAGE', '新增执行条件缺少业务要求来源', node['clause_id'], actions=['repair_plan']))
        covered.update(refs)
    for rid in required - covered:
        errors.append(diagnostic('INTENT_COVERAGE', '方案遗漏了一项原始业务要求，正在恢复', rid, actions=['repair_plan']))
    for assumption in intent.get('assumptions', []):
        if assumption.get('status') not in {'CONFIRMED', 'PUBLISHED'}:
            errors.append(diagnostic('BUSINESS_AMBIGUITY', assumption.get('question') or '需要确认一项业务解释',
                                     assumption.get('requirement_id'), decision=True))
    if tree is not None:
        try:
            if logic_signature(intent.get('logic_tree')) != logic_signature(tree, execution=True):
                raise ValueError('重组方案改变了原始条件的 AND/OR 关系')
        except ValueError as exc:
            errors.append(diagnostic('INTENT_LOGIC_CHANGED', str(exc), actions=['repair_plan']))
    return errors


def transition_errors(previous, proposed, utterance):
    """自动重写不得静默删掉旧条件；显式删除须附本轮用户原话。"""
    from tagpilot_agent.guards.plan_validator import leaves
    if not previous.get('tree'):
        return []
    old={n['clause_id'] for n in leaves(previous['tree'])}
    new={n['clause_id'] for n in leaves(proposed['tree'])}
    removed=set()
    for change in proposed.get('intent_changes') or []:
        span=change.get('source_span') if isinstance(change,dict) else None
        if not isinstance(span,str) or not span.strip() or span not in utterance:
            continue
        if change.get('operation')=='REMOVE':
            removed.update(change.get('clause_ids') or [])
        elif change.get('operation')=='REPLACE_ALL':
            removed.update(old)
    return [diagnostic('INTENT_COVERAGE','本轮改写遗漏旧条件，须保留未修改条件或引用用户明确删除的原话',cid,actions=['repair_plan']) for cid in sorted(old-new-removed)]


def frozen_errors(previous, proposed, utterance, authorized_requirements=None):
    from tagpilot_agent.guards.plan_validator import leaves
    from tagpilot_agent.domain.normalize import input_plan
    import json
    import re
    if not previous.get('tree'):return []
    old={n['clause_id']:n for n in leaves(input_plan(previous)['tree'])}
    new={n['clause_id']:n for n in leaves(input_plan(proposed)['tree'])}
    allowed={cid for cid,n in old.items() if set(n.get('requirement_ids') or [cid]) & set(authorized_requirements or [])}
    removed=set(); errors=[]; replace=False
    old_requirements={r['requirement_id']:r for r in previous.get('intent_plan',{}).get('requirements',[])}
    for change in proposed.get('intent_changes',[]):
        span=change.get('source_span','')
        operation=change.get('operation')
        # 授权既要求逐字来源，又要求实际修改/删除意图；仅引用一个数字不算授权。
        verbs = {'REMOVE':r'去掉|取消|删除|不再|不要',
                 'REPLACE_ALL':r'重新.*(圈选|筛选|开始)|全部.*(替换|重来)|改为只|只要',
                 'ADD':r'增加|加上|还要|也要'}.get(operation,r'改|调整|换|设为|变为|重新')
        if not span.strip() or span not in utterance or (operation!='ADD' and not re.search(verbs,span)):
            errors.append(diagnostic('FROZEN_CLAUSE_CHANGED','变更须引用本轮明确修改或删除的原话'));continue
        ids=set(change.get('clause_ids',[]))
        refs=set(change.get('requirement_ids',[]))
        ids.update(cid for cid,n in old.items() if refs & set(n.get('requirement_ids') or [cid]))
        if operation=='REPLACE_ALL':replace=True;ids=set(old)
        if operation in {'MODIFY','REMOVE','REPLACE_ALL'}:allowed.update(ids)
        if operation in {'REMOVE','REPLACE_ALL'}:removed.update(ids)
    # 对比业务语义字段；显示字段与默认空值不参与指纹。
    def fp(n):
        n={k:v for k,v in n.items() if v is not None and v not in ([],{},'') and k not in {'gap_reason'}}
        n.setdefault('unknown_policy','EXCLUDE')
        for k in ('values',):
            if k in n:n[k]=[str(v) for v in n[k]]
        if 'value_scale' in n:n['value_scale']=str(n['value_scale'])
        return json.dumps(n,sort_keys=True,ensure_ascii=False)
    for cid,node in old.items():
        if cid not in new and cid not in removed:
            errors.append(diagnostic('REQUIREMENT_MISSING','未授权删除上一版条件',cid))
        elif cid in new and cid not in allowed and fp(node)!=fp(new[cid]):
            errors.append(diagnostic('FROZEN_CLAUSE_CHANGED','本轮未授权修改该条件，请恢复原值',cid))
    new_requirements={r['requirement_id']:r for r in proposed.get('intent_plan',{}).get('requirements',[])}
    authorized_refs={rid for cid in allowed for rid in old[cid].get('requirement_ids',[cid])}
    for rid,r in old_requirements.items():
        if not replace and rid not in authorized_refs and new_requirements.get(rid)!=r:
            errors.append(diagnostic('REQUIREMENT_MISSING','需求台账中的旧要求须保留',rid))
    def retained(tree):
        if 'children' not in tree:return tree if tree['clause_id'] in old.keys() & new.keys() else None
        children=[node for c in tree['children'] if (node:=retained(c)) is not None]
        return {'logic':tree['logic'],'children':children} if children else None
    old_logic,new_logic=retained(previous['tree']),retained(proposed['tree'])
    if not replace and old_logic and new_logic:
        if logic_signature(old_logic,True)!=logic_signature(new_logic,True):
            logic_authorized=any(c.get('operation')=='MODIFY' and c.get('source_span','') in utterance
                and re.search(r'(改|调整|换).*(且|或|任一|全部|同时|AND|OR)',c.get('source_span',''),re.I)
                for c in proposed.get('intent_changes',[]))
            if not logic_authorized:
                errors.append(diagnostic('LOGIC_CHANGED','修改 AND/OR 关系须有明确授权'))
    return errors
