"""数字与来源逐字检查；连接词/否定词先做可观测警告。"""
import json
import re
from decimal import Decimal, InvalidOperation
from datetime import date
from .diagnostics import diagnostic
from .plan_validator import leaves

# C3、A01 等完整业务代码不是数值阈值；只提取独立数字。
NUMBER=re.compile(r'(?<![0-9A-Za-z_.])([0-9]+(?:\.[0-9]+)?)\s*(亿|万|%|％)?')
DATE=re.compile(r'(?:(\d{4})[-年])?(\d{1,2})[-月](\d{1,2})(?:日|号)?')
DATE_RANGE=re.compile(r'\s*(?:到|至|~|～|—|–|-)\s*')


def date_year(matches,index,span,reference_date):
    """省略年份先沿用区间另一端；跨年按端点顺序推导，不从模型答案取年份。"""
    match=matches[index]
    if match[1]:return int(match[1])
    month_day=(int(match[2]),int(match[3]))
    years=set()
    if index and matches[index-1][1]:
        previous=matches[index-1]
        if DATE_RANGE.fullmatch(span[previous.end():match.start()]):
            years.add(int(previous[1])+(month_day<(int(previous[2]),int(previous[3]))))
    if index+1<len(matches) and matches[index+1][1]:
        following=matches[index+1]
        if DATE_RANGE.fullmatch(span[match.end():following.start()]):
            years.add(int(following[1])-(month_day>(int(following[2]),int(following[3]))))
    if len(years)==1:return years.pop()
    if years:raise ValueError('日期区间的省略年份存在冲突，请明确年份')
    if not reference_date:raise ValueError('日期缺少年份且未提供基准日期，请明确年份')
    return date.fromisoformat(reference_date).year


def check_literals(plan,request,tags):
    errors=[];nodes=leaves(plan['tree'])
    current=request.get('_utterance',request['requirement'])
    sources=[request['requirement'],current]+[str(m.get('text') or m.get('content') or '') for m in request.get('history',[])]
    sources += [str(r.get('answer') or '') for r in (request.get('clarification_state') or {}).get('records',[])]
    previous=request.get('previous_plan',{})
    if previous.get('intent_plan'):sources.append(previous['intent_plan'].get('original_request',''))
    old_nodes={n['clause_id']:n for n in leaves(previous['tree'])} if previous.get('tree') else {}
    # 来源既包括用户原话，也包括服务端保存的已核验条件和本轮主动勾选的标签。
    # 只承认语义未改变的保存条件，不能用旧来源替新增值或模型改写背书。
    anchors=[p for p in (previous,request.get('source_plan') or {}) if p.get('valid') and p.get('tree')]
    semantic_keys=('kind','tag_id','operator','values','value_scale','value_unit','expected_caliber',
                   'expression','compare_expression','source_span','time_constraint','unknown_policy','requirement_ids')
    def fingerprint(node):
        result={k:node[k] for k in semantic_keys if node.get(k) not in (None,[],{},'')}
        result.setdefault('kind','TAG_PREDICATE');result.setdefault('unknown_policy','EXCLUDE')
        if 'value_scale' in result:result['value_scale']=str(result['value_scale'])
        return result
    trusted_nodes={}
    trusted_requirements={}
    for anchor in anchors:
        old={n['clause_id']:n for n in leaves(anchor['tree'])}
        for node in nodes:
            prior=old.get(node['clause_id'])
            if prior and fingerprint(prior)==fingerprint(node):
                trusted_nodes[node['clause_id']]=node
                for rid in node.get('requirement_ids',[node['clause_id']]):
                    for r in (anchor.get('intent_plan') or {}).get('requirements',[]):
                        if r['requirement_id']==rid:trusted_requirements.setdefault(rid,set()).update(r.get('source_spans',[]))
    def selected_source(node,span):
        if node.get('tag_id') not in request.get('pinned_tag_ids',[]):return False
        name=tags.get(node['tag_id'],{}).get('name')
        if not name or name not in span:return False
        remainder=span.replace(name,'',1).strip(' ，,：:；;、')
        return not remainder or any(remainder in s for s in sources)
    for n in nodes:
        span=n.get('source_span','')
        if not span or (n['clause_id'] not in trusted_nodes and not any(span in s for s in sources) and not selected_source(n,span)):
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
            c=e.get('expected_caliber') or e.get('caliber_struct') or {}
            for key in ('time_window_value','time_offset_months','time_offset_years','month_of_year'):
                if c.get(key) is not None:
                    try:time_values.add(abs(Decimal(str(c[key]))))
                    except InvalidOperation:pass
            for a in e.get('args',[]):times(a)
        times(n);times(n.get('expression'));times(n.get('compare_expression'))
        date_spans=[]
        if tags.get(n.get('tag_id'),{}).get('semantic_type')=='DATE':
            matches=list(DATE.finditer(span))
            for index,match in enumerate(matches):
                # 日期无论是否通过校验，都不能再被当成金额等普通数值。
                date_spans.append((match.start(),match.end()))
                try:
                    year=date_year(matches,index,span,request.get('reference_date'))
                    value=date(year,int(match[2]),int(match[3])).isoformat()
                except (ValueError,TypeError) as exc:
                    errors.append(diagnostic('LITERAL_DRIFT','无法核验原话中的日期：'+str(exc),n['clause_id'],expected=match[0]))
                    continue
                if value not in n.get('values',[]):
                    errors.append(diagnostic('LITERAL_DRIFT','原话中的日期端点未被条件保留',n['clause_id'],expected=value))
        for m in NUMBER.finditer(span):
            if any(a<=m.start() and m.end()<=b for a,b in date_spans):continue
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
        selected_spans={n.get('source_span') for n in nodes if r['requirement_id'] in n.get('requirement_ids',[n['clause_id']]) and selected_source(n,n.get('source_span',''))}
        if any(span not in trusted_requirements.get(r['requirement_id'],set()) and span not in selected_spans
               and not any(span in s for s in sources) for span in r.get('source_spans',[])):
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
