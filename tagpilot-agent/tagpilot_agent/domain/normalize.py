"""仅作等价规范化；不猜测业务值，不放宽条件。"""
from copy import deepcopy
from .time_parse import parse_time
from tagpilot_agent.guards.plan_validator import leaves
from .plan_model import AudiencePlan, TagPredicate, DerivedPredicate, ScopeAll, TagRef, Const, CapabilityRef, BinaryOp, CountPositive

ALIASES = {'EQ':'=', 'NE':'!=', 'GT':'>', 'GTE':'>=', 'GE':'>=', 'LT':'<', 'LTE':'<=', 'LE':'<=', 'IN':'in', 'NOT_IN':'not_in', 'BETWEEN':'between', 'IS_NULL':'is_null', 'IS_NOT_NULL':'is_not_null'}


def input_plan(plan):
    """从服务端方案提取模型输入字段；只用于可信的 previous/edited plan。"""
    models = {'TAG_PREDICATE': TagPredicate, 'DERIVED_PREDICATE': DerivedPredicate, 'SCOPE_ALL': ScopeAll,
              'TAG': TagRef, 'CONST': Const, 'CAPABILITY': CapabilityRef, 'COUNT_POSITIVE': CountPositive,
              **{k: BinaryOp for k in ('ADD','SUB','MUL','DIV')}}
    def clean(node):
        if 'children' in node:
            return {k: ([clean(c) for c in v] if k == 'children' else v) for k,v in node.items() if k in {'children','logic'}}
        kind = node.get('kind', 'TAG_PREDICATE')
        result = {k:deepcopy(v) for k,v in node.items() if k in models.get(kind, TagPredicate).model_fields}
        result['kind'] = kind
        for k in ('expression','compare_expression'):
            if result.get(k):result[k]=clean(result[k])
        if 'args' in result:result['args']=[clean(c) for c in result['args']]
        return result
    result={k:deepcopy(v) for k,v in plan.items() if k in AudiencePlan.model_fields}
    result['schema_version']=3
    result['tree']=clean(plan['tree'])
    intent=result.get('intent_plan')
    if intent:
        for k in ('unresolved_slots','hypotheses_to_check'):intent.pop(k,None)
        for r in intent.get('requirements',[]):r.pop('resolution_state',None)
    return result


def normalize_plan(plan):
    plan=deepcopy(plan)
    for node in leaves(plan['tree']):
        node.setdefault('kind','TAG_PREDICATE')
        if node.get('kind') != 'SCOPE_ALL':
            node['operator']=ALIASES.get(node.get('operator'),node.get('operator'))
            node.setdefault('unknown_policy','EXCLUDE')
        if node.get('time_constraint') and not node.get('expected_caliber'):
            expected=parse_time(node.get('source_span',''))
            if not expected and '当前' in node.get('source_span',''):expected={'time_anchor_label':'当前'}
            if expected:node['expected_caliber']=expected
        if not node.get('requirement_ids'):node['requirement_ids']=[node['clause_id']]
    return plan
