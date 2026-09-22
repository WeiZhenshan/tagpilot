"""用户业务要求与可重组的执行节点分离。原始要求不会随绑定结果丢失。"""
from __future__ import annotations
from copy import deepcopy
from .diagnostics import diagnostic


def capture_intent(plan, requirement):
    from .plan import leaves
    supplied = plan.get('intent_plan') or {}
    if not isinstance(supplied, dict):
        supplied = {}
    if supplied.get('requirements') and supplied.get('logic_tree'):
        return deepcopy(supplied)
    nodes = leaves(plan['tree'])
    requirements = []
    for node in nodes:
        rid = node['clause_id']
        node['requirement_ids'] = [rid]
        requirements.append({'requirement_id': rid, 'source_spans': [node.get('source_span') or requirement],
                             'business_meaning': node.get('source_span') or node.get('query') or requirement,
                             'origin': 'USER', 'resolution_state': 'PENDING'})
    def structure(tree):
        if 'children' in tree:
            return {'logic': tree['logic'], 'children': [structure(c) for c in tree['children']]}
        return {'requirement_id': tree['clause_id']}
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
    from .plan import leaves
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
