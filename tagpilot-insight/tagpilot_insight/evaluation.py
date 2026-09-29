"""部署包内的小范围确定性门禁，不接受客户端上传PASS。生产数据/业务验收仍由复核人负责。"""
from .registry import SkillRegistry
from .fixtures import synthetic_golden_report
from .guards import validate_report
from .statistics import wilson,standardize
from .aggregates import AggregateRow

def evaluate_pack(skill_id):
    registry=SkillRegistry();registry.get(skill_id);checks=[]
    validate_report(synthetic_golden_report());checks.append('fixture_guard_and_charts')
    lo,hi=wilson(60,240)
    if not(abs(lo-19.947)<.01 and abs(hi-30.835)<.01):raise ValueError('Wilson独立参考未通过')
    checks.append('wilson_independent_reference')
    c=[AggregateRow(dimensions=['0','2'],n=120,holders=30,missing=0),AggregateRow(dimensions=['1','2'],n=120,holders=30,missing=0)]
    b=[AggregateRow(dimensions=['0','2'],n=400,holders=300,missing=0),AggregateRow(dimensions=['1','2'],n=400,holders=200,missing=0)]
    s=standardize(c,b)
    if not(s['rate']==62.5 and s['gap']==37.5 and s['nonoverlapping']):raise ValueError('结构标准化独立参考未通过')
    checks.append('standardization_independent_reference')
    return {'skill_id':skill_id,'pack_hash':registry.hash(skill_id),'passed':True,'checks':checks,'scope':'固定合成聚合契约与统计规则，非生产SQL或业务验收'}
