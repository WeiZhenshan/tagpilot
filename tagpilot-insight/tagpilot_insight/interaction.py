"""一次结构化路由/改图输出的纯Guard；视图不改Fact，数据和口径不自动生效。"""
from typing import Literal
from pydantic import Field
from .contracts import Contract,Identifier,InsightReport
from .registry import SkillRegistry
from .guards import validate_report

class Route(Contract):
    skills:list[Identifier] = Field(min_length=1,max_length=3)
    parameters:dict = Field(default_factory=dict)
    needs_confirmation:Literal[True] = True

def route(utterance:str,candidate=None):
    reg=SkillRegistry()
    if candidate:
        try:
            out=Route.model_validate(candidate)
            if len(set(out.skills))!=len(out.skills) or not set(out.parameters)<=set(out.skills):raise ValueError('路由重复或参数越界')
            for skill in out.skills:reg.parameters(skill,out.parameters.get(skill,{}))
            return out
        except ValueError:pass
    ids=[]
    if any(x in utterance for x in ('资产','AUM','规模')):ids.append('asset_structure_profile')
    if any(x in utterance for x in ('产品','持仓','缺口')):ids.append('product_holding_gap')
    if any(x in utterance for x in ('机会','优先','渠道')):ids.append('opportunity_priority')
    return Route(skills=ids or list(reg.manifests))

class ChartEdit(Contract):
    classification:Literal['view','data','definition']
    operation:Literal['sort','orientation','table','rerun']
    chart_id:Identifier
    parameters:dict = Field(default_factory=dict)

def propose_edit(report:InsightReport,skill_id:str,chart_id:str,utterance:str,candidate=None,*,published_hashes=None):
    validate_report(report,published_hashes=published_hashes)
    skill=next(r for r in report.results if r.skill_id==skill_id)
    original=next(c for c in skill.charts if c.id==chart_id)
    if candidate:
        try:patch=ChartEdit.model_validate(candidate)
        except ValueError:patch=None
    else:patch=None
    if patch is None:
        classification='definition' if any(x in utterance for x in ('基准','分母','口径')) else 'data' if any(x in utterance for x in ('筛选','只看','分组','维度','粒度')) else 'view'
        op='rerun' if classification!='view' else 'sort' if any(x in utterance for x in ('排序','降序','升序')) else 'orientation' if any(x in utterance for x in ('横向','纵向','竖向')) else 'table' if '表' in utterance else 'rerun'
        parameters={'descending':'升序' not in utterance} if op=='sort' else {'orientation':'horizontal' if '横向' in utterance else 'vertical'} if op=='orientation' else {}
        patch=ChartEdit(classification=classification,operation=op,chart_id=chart_id,parameters=parameters)
    if patch.chart_id!=chart_id:raise ValueError('不能修改未选择图表')
    # 自然语言具有更高优先级，模型不能把数据或口径请求谎称为视图。
    if any(x in utterance for x in ('基准','分母','口径')):patch.classification='definition';patch.operation='rerun';patch.parameters={}
    elif any(x in utterance for x in ('筛选','只看','分组','维度','粒度')):patch.classification='data';patch.operation='rerun';patch.parameters={}
    if patch.classification!='view' or patch.operation=='rerun':
        if skill_id=='asset_structure_profile' and '基准' in utterance:
            for word,value in [('同机构','same_org'),('全部客户','all_customers'),('全体客户','all_customers'),('同层级','same_aum')]:
                if word in utterance:patch.parameters={'benchmark_type':value};break
        if patch.parameters:SkillRegistry().parameters(skill_id,patch.parameters)
        return {'change':patch.model_dump(),'requires_confirmation':True,'report':None,'message':'本次涉及数据或口径，须确认新参数或客群版本后重新运行；当前报告保留。'}
    changed=report.model_copy(deep=True);chart=next(c for r in changed.results if r.skill_id==skill_id for c in r.charts if c.id==chart_id)
    if patch.operation=='sort':
        if set(patch.parameters)!={'descending'} or type(patch.parameters['descending']) is not bool or chart.kind in {'funnel','heatmap','kpi'}:raise ValueError('该图型不可排序，不能破坏漏斗或矩阵语义')
        order=[p.category for p in sorted(chart.series[0].points,key=lambda p:p.value if p.value is not None else float('-inf'),reverse=patch.parameters['descending'])]
        for series in chart.series:series.points.sort(key=lambda p:order.index(p.category))
    elif patch.operation=='orientation':
        if set(patch.parameters)!={'orientation'} or patch.parameters['orientation'] not in {'horizontal','vertical'} or chart.kind not in {'bar','stacked_bar'}:raise ValueError('图表方向或类型非法')
        chart.orientation=patch.parameters['orientation']
    elif patch.operation=='table':
        if patch.parameters:raise ValueError('表格变更不能携带数据参数')
        if chart.kind in {'heatmap','funnel','kpi'}:raise ValueError('此图型需保留矩阵、漏斗或单值编码，请使用现有图表数据表')
        chart.kind='table'
    validate_report(changed,published_hashes=published_hashes)
    if [r.facts for r in changed.results]!=[r.facts for r in report.results]:raise ValueError('视图变更不能修改事实')
    return {'change':patch.model_dump(),'requires_confirmation':False,'report':changed.model_dump(mode='json'),'message':'已应用视图变化，事实、基准与口径保持同一快照。'}
