"""对四条冒烟方案做独立业务边界验证；合成输入，不是客户人数验收。"""
import argparse
from decimal import Decimal
import itertools
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('results',nargs='+');args=p.parse_args()
plans={}
for name in args.results:
    for result in json.loads(Path(name).read_text())['results']:
        if result.get('plan'):plans[result['case']]=result['plan']

def number(v):return Decimal(str(v)) if v is not None else None

def expr(e,row):
    if e['kind']=='TAG':
        value=number(row.get(e['tag_id']));return None if value is None else value*number(e.get('unit_scale',1))
    if e['kind']=='CONST':return number(e['value'])
    a=[expr(v,row) for v in e['args']]
    if None in a:return None
    return {'DIV':lambda:a[0]/a[1] if a[1]>0 else None,'MUL':lambda:a[0]*a[1],'SUB':lambda:a[0]-a[1],'ADD':lambda:a[0]+a[1],'COUNT_POSITIVE':lambda:sum(v>0 for v in a)}[e['kind']]()

def evaluate(t,row):
    if 'children'in t:
        items=[evaluate(c,row) for c in t['children']];return all(items) if t['logic']=='AND' else any(items)
    if t.get('kind')=='SCOPE_ALL':return True
    derived=t.get('kind')=='DERIVED_PREDICATE';v=expr(t['expression'],row) if derived else row.get(t['tag_id'])
    op=t['operator'];values=t.get('values',[])
    if op=='is_null':return v is None
    if op=='is_not_null':return v is not None
    if v is None:return False
    if op in {'in','not_in'}:return (v in values) if op=='in' else (v not in values)
    if not derived and t['tag_id'] in {601,1466}:
        return v==values[0] if op=='=' else v!=values[0]
    v=number(v)
    right=expr(t['compare_expression'],row) if t.get('compare_expression') else number(values[0])
    if right is None:return False
    return {'>':lambda:v>right,'>=':lambda:v>=right,'<':lambda:v<right,'<=':lambda:v<=right,'=':lambda:v==right,'!=':lambda:v!=right,'between':lambda:right<=v<=number(values[1])}[op]()

cases={
 'A01':([{}],lambda r:True),
 'A04':([{721:a,813:b} for a,b in itertools.product([None,0,199999,200000,500000],[None,0,159999,160000,400000])],lambda r:r[721] is not None and r[813] is not None and r[721]>=200000 and Decimal(r[813])/Decimal(r[721])>=Decimal('.8')),
 'B02':([{1291:a,601:b,1466:c} for a,b,c in itertools.product([None,499999,500000], [None,'0','1'],[None,'C2','C3','C4','C5','UNKNOWN'])],lambda r:r[1291] is not None and r[1291]>=500000 and r[601]=='0' and r[1466] in {'C3','C4','C5'}),
 'D02':([{1033:a,1043:b,1036:c} for a,b,c in itertools.product([None,0,100,600,700,850,1000,1200],repeat=3)],lambda r:all(r[i] is not None for i in [1033,1043,1036]) and r[1043]>0 and r[1036]>0 and Decimal(r[1033])/Decimal(r[1043])<Decimal('.7') and Decimal(r[1043])/Decimal(r[1036])<Decimal('.85'))
}
for case,(rows,gold) in cases.items():
    if case not in plans:continue
    plan=plans[case];wrong=sum(evaluate(plan['tree'],row)!=bool(gold(row)) for row in rows)
    print(json.dumps({'case':case,'synthetic_boundaries':len(rows),'mismatches':wrong,'python_gate_valid':plan.get('valid')},ensure_ascii=False))
    if wrong:raise SystemExit(1)
