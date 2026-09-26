"""独立解释器：不导入 Agent、Guard、Java 编译器，也不执行模型生成 SQL。"""
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import product

from .contracts import Tree
from .io import digest


class EvidenceError(ValueError):
    pass


def number(value):
    if value is None: return None
    try:
        result=Decimal(str(value))
        if not result.is_finite(): raise EvidenceError('非有限数据')
        return result
    except InvalidOperation as exc:
        raise EvidenceError('数值数据非法') from exc


def expression(expr, row):
    kind=expr['kind']
    if kind=='TAG':
        if expr['field_name'] not in row:
            raise EvidenceError('证据字段缺失，不等于 NULL')
        return row[expr['field_name']]
    if kind=='CONST': return number(expr['value'])
    args=[number(expression(a,row)) for a in expr['args']]
    if any(a is None for a in args): return None
    if kind=='COUNT_POSITIVE': return Decimal(sum(a>0 for a in args))
    a,b=args
    if kind=='DIV': return None if b==0 else a/b
    if kind=='ADD': return a+b
    if kind=='SUB': return a-b
    if kind=='MUL': return a*b
    raise EvidenceError('表达式不支持')


def evaluate(tree,row):
    kind=tree['kind']
    if kind=='SCOPE_ALL': return True
    if kind=='GROUP':
        # 先求全部条件，不能用短路隐藏缺失/损坏证据。
        values=[evaluate(child,row) for child in tree['children']]
        return all(values) if tree['logic']=='AND' else any(values)
    value=expression(tree['expression'],row)
    op=tree['operator']
    if op=='is_null': return value is None
    if op=='is_not_null': return value is not None
    if value is None: return False
    kind=tree['data_kind']
    convert=number if kind=='NUMBER' else date.fromisoformat if kind=='DATE' else str
    try:
        value=convert(value); values=[convert(v) for v in tree['values']]
    except (TypeError,ValueError) as exc:
        raise EvidenceError('日期或字面量证据非法') from exc
    if op=='in': return value in values
    if op=='not_in': return value not in values
    if op=='contains': return values[0] in value
    if op=='between': return values[0]<=value<=values[1]
    right=values[0]
    return {'=':lambda:value==right,'!=':lambda:value!=right,
            '>':lambda:value>right,'>=':lambda:value>=right,
            '<':lambda:value<right,'<=':lambda:value<=right}[op]()


def normalized(tree):
    result=Tree.model_validate(tree).model_dump(exclude_none=True)
    def visit(node):
        if node['kind']=='GROUP':
            children=[]
            for child in node['children']:
                child=visit(child)
                if child['kind']=='GROUP' and child['logic']==node['logic']:
                    children.extend(child['children'])
                else: children.append(child)
            node['children']=sorted(children,key=digest)
        elif node['kind']=='PREDICATE':
            if node['data_kind']=='NUMBER':
                node['values']=[format(number(v).normalize(),'f') for v in node['values']]
            if node['operator'] in {'in','not_in'}:
                node['values']=sorted(node['values'])
        return node
    return visit(result)


def references(tree):
    if tree is None: return set()
    found=set()
    def scan(value):
        if isinstance(value,dict):
            if value.get('kind')=='TAG': found.add(value['tag_id'])
            for item in value.values(): scan(item)
        elif isinstance(value,list):
            for item in value: scan(item)
    scan(tree)
    return found


def fixture_result(tree,rows):
    ids=sorted(r['CUST_ID'] for r in rows if evaluate(tree,r))
    return {'count':len(ids),'ids_sha256':digest(ids),'ids':ids}


def boundary_rows(tree):
    """一元扰动 + 有限全组合；只构造校验探针，不把探针当新的客户或案例。"""
    pools={}
    def expr_fields(expr):
        if expr['kind']=='TAG':
            pools.setdefault(expr['field_name'],[None,'0','1','-1','100'])
        for child in expr.get('args',[]): expr_fields(child)
    def scan(node):
        if node['kind']=='GROUP':
            for child in node['children']: scan(child)
        elif node['kind']=='PREDICATE':
            expr=node['expression']
            expr_fields(expr)
            if expr['kind']!='TAG': return
            field=expr['field_name']
            values=node['values']
            if node['data_kind']=='NUMBER':
                pool=[None,'0','-1']
                for value in values:
                    n=number(value)
                    pool.extend(format(n+d,'f') for d in [Decimal('-.01'),Decimal('0'),Decimal('.01')])
            elif node['data_kind']=='DATE':
                from datetime import timedelta
                pool=[None]
                for value in values:
                    d=date.fromisoformat(value)
                    pool.extend((d+timedelta(days=delta)).isoformat() for delta in [-1,0,1])
            else:
                pool=[None,'__UNKNOWN__',*values]
            # 同一字段可能同时有上下界；保留两侧探针。
            previous=pools[field] if field in direct_fields else []
            pools[field]=list(dict.fromkeys(previous+pool))
            direct_fields.add(field)
    direct_fields=set()
    scan(tree)
    if not pools: return [{}]
    size=1
    for values in pools.values(): size*=len(values)
    if size<=4096:
        return [dict(zip(pools,vals)) for vals in product(*pools.values())]
    baseline={field:next((v for v in values if v is not None),'0') for field,values in pools.items()}
    return [{**baseline,field:v} for field,values in pools.items() for v in values]


def grade_tree(expected,actual,rows=None):
    """P1 只实现严格语义标准化和执行证据；无法证明的变换不猜测等价。"""
    try:
        a,b=normalized(expected),normalized(actual)
        checks={'normalized_tree_equal':a==b}
        def bindings(value):
            if isinstance(value,dict):
                found={(value['tag_id'],value['field_name'])} if value.get('kind')=='TAG' else set()
                return found.union(*(bindings(v) for v in value.values()))
            if isinstance(value,list):return set().union(*(bindings(v) for v in value))
            return set()
        if bindings(a)!=bindings(b):
            return {'status':'FAIL','checks':{**checks,'field_bindings_equal':False},
                    'failures':['FIELD_BINDING_MISMATCH'],'evidence':{}}
        probes=boundary_rows(a)
        checks['boundary_equal']=references(a)==references(b) and all(evaluate(a,r)==evaluate(b,r) for r in probes)
        evidence={'boundary_rows':len(probes)}
        if rows is not None:
            er,ar=fixture_result(a,rows),fixture_result(b,rows)
            checks['full_id_set_equal']=er['ids']==ar['ids']
            evidence.update(expected_count=er['count'],actual_count=ar['count'],expected_ids_sha256=er['ids_sha256'],actual_ids_sha256=ar['ids_sha256'])
        return {'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,
                'failures':[k for k,v in checks.items() if not v],'evidence':evidence}
    except EvidenceError as exc:
        return {'status':'RUN_INVALID','checks':{},'failures':['EVIDENCE_INVALID'],'evidence':{'reason':str(exc)}}
    except (ValueError,KeyError,TypeError,InvalidOperation) as exc:
        return {'status':'FAIL','checks':{},'failures':['INVALID_PLAN'],'evidence':{'reason':type(exc).__name__}}
