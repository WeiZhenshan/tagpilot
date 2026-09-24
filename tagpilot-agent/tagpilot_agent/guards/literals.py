"""数字与来源逐字检查；连接词/否定词先做可观测警告。"""
import json
import re
from decimal import Decimal, InvalidOperation
from .diagnostics import diagnostic
from .plan_validator import leaves

# C3、A01 等完整业务代码不是数值阈值；只提取独立数字。
NUMBER=re.compile(r'(?<![0-9A-Za-z_.])([0-9]+(?:\.[0-9]+)?)\s*(亿|万|%|％)?')


def check_literals(plan,request,tags):
    errors=[];nodes=leaves(plan['tree'])
    current=request.get('_utterance',request['requirement'])
    sources=[request['requirement'],current]+[str(m.get('text') or m.get('content') or '') for m in request.get('history',[])]
    previous=request.get('previous_plan',{})
    if previous.get('intent_plan'):sources.append(previous['intent_plan'].get('original_request',''))
    old_nodes={n['clause_id']:n for n in leaves(previous['tree'])} if previous.get('tree') else {}
    for n in nodes:
        span=n.get('source_span','')
        if not span or not any(span in s for s in sources):
            errors.append(diagnostic('LITERAL_DRIFT','条件来源必须逐字引用用户原话',n['clause_id']))
        if n.get('status') in {'GAP','NEEDS_DECISION'}:continue
        prior=old_nodes.get(n['clause_id'])
        semantic_keys=('kind','tag_id','operator','values','value_scale','value_unit','expected_caliber','expression','compare_expression','source_span')
        if prior and all(prior.get(k)==n.get(k) for k in semantic_keys):continue
        nums=set()
        for v in n.get('values',[]):
            try:nums.add(Decimal(str(v))*Decimal(str(n.get('value_scale') or 1)))
            except InvalidOperation:pass
        def collect(e):
            if not isinstance(e,dict):return
            if e.get('kind')=='CONST':
                try:nums.add(Decimal(str(e.get('value'))))
                except InvalidOperation:pass
            for a in e.get('args',[]):collect(a)
        collect(n.get('expression'));collect(n.get('compare_expression'))
        time_values=set()
        def times(e):
            if not isinstance(e,dict):return
            c=e.get('expected_caliber') or {}
            for key in ('time_window_value','time_offset_months','time_offset_years'):
                if c.get(key) is not None:
                    try:time_values.add(abs(Decimal(str(c[key]))))
                    except InvalidOperation:pass
            for a in e.get('args',[]):times(a)
        times(n);times(n.get('expression'));times(n.get('compare_expression'))
        for m in NUMBER.finditer(span):
            value=Decimal(m[1])*{'万':Decimal(10000),'亿':Decimal(100000000),'%':Decimal('.01'),'％':Decimal('.01')}.get(m[2],1)
            suffix=span[m.end():m.end()+2]
            if suffix.startswith(('天','个月','月','年')) and value in time_values:continue
            # 已发布分档用其边界作为数值证据；不把码值编号当数值阈值。
            bounds=set()
            for c in n.get('code_options',[]):
                if str(c.get('code')) not in set(map(str,n.get('values',[]))):continue
                for key in ('lower_bound','upper_bound'):
                    try:bounds.add(Decimal(str(c.get(key))))
                    except InvalidOperation:pass
            if value not in nums|bounds:
                errors.append(diagnostic('LITERAL_DRIFT','原话中的数值未被条件或时间口径保留',n['clause_id'],expected=str(value)))
    # 不能通过只引用原话的一小段而丢弃另一个明确数字。
    if not request.get('previous_plan'):
        spans=' '.join(n.get('source_span','') for n in nodes)
        for match in NUMBER.finditer(current):
            if match.group(0).strip() not in spans:
                errors.append(diagnostic('LITERAL_DRIFT','方案遗漏原始需求中的数值',expected=match.group(0).strip()))
    for r in plan.get('intent_plan',{}).get('requirements',[]):
        if any(not any(span in s for s in sources) for span in r.get('source_spans',[])):
            errors.append(diagnostic('LITERAL_DRIFT','需求台账来源必须逐字引用用户原话',r['requirement_id']))
    return errors


def literal_warnings(plan,request):
    """否定/连接词缺失只提示人工核对，避免把词法启发式当作语义裁决。"""
    source=request.get('_utterance',request['requirement'])
    spans=' '.join(n.get('source_span','') for n in leaves(plan['tree']))
    warnings=[]
    for kind,words in [('NEGATION_COVERAGE',('排除','不包含','非','不是','不要')),('CONNECTOR_COVERAGE',('并且','同时','或者','任一'))]:
        missing=[word for word in words if word in source and word not in spans]
        if missing:warnings.append({'code':kind,'message':'请核对原话中的否定或条件连接关系','markers':missing})
    return warnings
