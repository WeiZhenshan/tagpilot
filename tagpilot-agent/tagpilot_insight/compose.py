"""确定性G1/G2/G3执行器：只消费带版本证据的聚合，不读取fixtures或客户数据。"""
from __future__ import annotations
from math import fsum
from .aggregates import AggregateBatch
from .contracts import Fact, InsightCard, InsightReport, SkillResult, ChartSeries, ChartPoint, Reconcile
from .planning import MetricPlan
from .registry import SkillRegistry
from .charts import compose_chart
from .guards import validate_report, GuardError
from .statistics import standardize

LABELS={"wealth":"理财","fund":"基金","insurance":"保险","liquid":"流动资产","fixed":"定期","investment":"投资资产"}
TIERS={"low":"低","medium":"中","high":"高"}

class Builder:
    def __init__(self,plan,batch):
        self.plan=plan;self.batch=batch;self.facts={};self.charts=[];self.cards=[];self.reasons=list(plan.partial_reasons)
        self.queries={(q.query_id,q.category):q for q in batch.queries}
    def rows(self,qid,category=None):
        q=self.queries.get((qid,category))
        if q is None or q.status != "AVAILABLE" or not q.rows:
            raise ValueError(q.reason if q else "缺少聚合："+qid)
        return q.rows
    def one(self,qid,category=None):
        rows=self.rows(qid,category)
        if len(rows)!=1:raise ValueError("总体指标不能包含多个聚合格")
        return rows[0]
    def add(self,fid,metric,label,value,unit="人",query="customers",n=None,**kwargs):
        n=self.plan.cohort.count if n is None else n
        status="AVAILABLE"
        if value is None or n<20 or (unit=="人" and 0<float(value)<20):status="SUPPRESSED";value=None;n=None
        category=kwargs.pop("category",None)
        self.facts[fid]=Fact(id=fid,metric=metric,label=label,value=float(value) if value is not None else None,unit=unit,
            sample_size=n,status=status,query_id=query,evidence=[self.queries[(query,category)].evidence_id if (query,category) in self.queries else "确定性派生："+query,
                self.batch.benchmark_definition+" / "+self.batch.benchmark_version],**kwargs)
        return fid
    def rate(self,fid,metric,label,num,den,query,role="DERIVED",n=None):
        a,b=self.facts[num],self.facts[den]
        if a.value is None or b.value is None or b.value<=0:raise ValueError("覆盖率源已抑制或分母无效")
        return self.add(fid,metric,label,a.value/b.value*100,"%",query,n,denominator_id=den,derived_from=[num],role=role,calculation="RATIO")
    def chart(self,cid,title,intent,rows,metric_label,reconcile=None,table=False):
        series=[ChartSeries(name=name,fact_ids=[r[1] for r in points],points=[ChartPoint(category=r[0],fact_id=r[1],value=self.facts[r[1]].value,column=r[2] if len(r)>2 else None) for r in points]) for name,points in rows]
        self.charts.append(compose_chart(chart_id=cid,title=title,intent=intent,metric_label=metric_label,series=series,facts=self.facts,reconcile=reconcile,as_table=table))
    def card(self,cid,title,text,comparison,diagnosis,action,boundary,definitions,basis="RULE",benchmark=(),difference=(),population=None,statistical_evidence=None):
        import re
        def statement(t):return {"text":t,"fact_ids":re.findall(r"\{fact:([^}]+)\}",t)}
        self.cards.append(InsightCard.model_validate(dict(id=cid,title=title,facts=statement(text),comparison={**statement(comparison),"benchmark_fact_ids":list(benchmark),"difference_fact_ids":list(difference)},diagnosis={**statement(diagnosis),"basis":basis,"statistical_evidence":statistical_evidence},action={**statement(action),"population_fact_id":population,"priority":"MEDIUM" if population else "NONE"},boundary=dict(text=boundary,data_as_of=self.plan.cohort.data_as_of,skill_version=self.plan.skill_version,sample_fact_id="customers",metric_definitions=definitions))))
    def finish(self):
        return SkillResult(skill_id=self.plan.skill_id,skill_version=self.plan.skill_version,pack_hash=self.plan.pack_hash,
            status="PARTIAL" if self.reasons else "COMPLETE",level="L2" if self.reasons else None,reasons=list(dict.fromkeys(self.reasons))[:10],facts=list(self.facts.values()),cards=self.cards,charts=self.charts)


def g1(b):
    for fid,label in [("total_aum","总AUM"),("average_aum","人均AUM"),("median_aum","中位AUM")]:
        r=b.one(fid);b.add(fid,"aum",label,r.value,"元",fid,r.n)
    for fid,label in [("customers","客户数"),("total_aum","总AUM"),("average_aum","人均AUM"),("median_aum","中位AUM")]:
        b.chart("kpi_"+fid,label,"single_value",[(label,[(label,fid)])],label)
    bands=b.rows("aum_bands");keys=[]
    cuts=next(q.cuts for q in b.plan.queries if q.id=="aum_bands")
    def band_label(code):
        i=int(code);value=lambda v:format(v/10000,"g")+"万元"
        return "低于"+value(cuts[0]) if i==0 else "不低于"+value(cuts[-1]) if i==len(cuts) else value(cuts[i-1])+"至"+value(cuts[i])
    for r in bands:
        fid="band_"+r.dimensions[0];keys.append(fid);b.add(fid,"aum_tier","AUM层级"+r.dimensions[0],r.value,query="aum_bands",n=r.n)
    b.chart("aum_bands","AUM分层有效客户数","show_distribution",[("客群",[(band_label(r.dimensions[0]),fid) for r,fid in zip(bands,keys)])],"客户数")
    bm=b.one("benchmark_count");b.add("benchmark_customers","customer_count","基准客户数",bm.value,query="benchmark_count",n=bm.n,role="BENCHMARK")
    total=b.rows("benchmark_assets");b.add("benchmark_total","aum","基准总AUM",fsum(r.value for r in total),"元","benchmark_assets",sum(r.n for r in total),role="BENCHMARK")
    mix=[];holders=[];parts=[];bm_parts=[]
    for category in ("liquid","fixed","investment"):
        label=LABELS[category];r=b.one(category);base=b.one("benchmark_"+category)
        b.add(category+"_amount",category+"_aum",label+"金额",r.value,"元",category,r.n)
        b.add("benchmark_"+category+"_amount",category+"_aum",label+"基准金额",base.value,"元","benchmark_"+category,base.n,role="BENCHMARK")
        part=b.rate(category+"_share",category+"_aum",label+"金额加权占比",category+"_amount","total_aum",category)
        bp=b.rate("benchmark_"+category+"_share",category+"_aum",label+"基准金额占比","benchmark_"+category+"_amount","benchmark_total","benchmark_"+category,role="BENCHMARK",n=bm.n)
        parts.append(part);bm_parts.append(bp);mix.append((label,[("客群",part),("基准",bp)]))
        try:
            h=b.one("holders",category);num=b.add(category+"_holders","asset_holder",label+"持有客户",h.holders,query="holders",n=h.n,category=category)
            holders.append((label,b.rate(category+"_holder_share","asset_holder",label+"持有客户占比",num,"customers","holders")))
        except ValueError as e:b.reasons.append(str(e))
    if abs(fsum(b.facts[f].value for f in parts)-100)>.05 or abs(fsum(b.facts[f].value for f in bm_parts)-100)>.05:
        raise ValueError("资产分类不能与AUM对账，请核验完整口径")
    b.chart("asset_mix","资产结构·金额加权占比","show_composition",mix,"资产金额占比",[Reconcile(kind="percentage",fact_ids=parts),Reconcile(kind="percentage",fact_ids=bm_parts)])
    if holders:b.chart("holder_mix","持有客户占比·客户可持有多个品类","compare_categories",[("客群",holders)],"持有客户占比")
    gap=b.facts["liquid_share"].value-b.facts["benchmark_liquid_share"].value
    b.add("liquid_gap","liquid_aum","流动资产占比偏离",gap,"pp","liquid",derived_from=["liquid_share","benchmark_liquid_share"],role="DERIVED")
    liquid=b.one("high_liquid");b.add("high_liquid","liquid_share","高流动资产有效客户",liquid.holders,query="high_liquid",n=liquid.n,role="POST_EXCLUSION",exclusions_applied=["missing_aum"])
    meaningful=abs(gap)>=b.plan.parameters["min_deviation_pp"] and min(b.plan.cohort.count,bm.n)>=30
    comp="流动资产占比"+("高于" if gap>=0 else "低于")+"基准，差值 {fact:liquid_gap}。" if min(b.plan.cohort.count,bm.n)>=30 else "比较样本不足，暂不解释结构差异。"
    b.card("asset_findings","资产结构核对","客群 {fact:customers}，总AUM {fact:total_aum}。",comp,
           "规则提示资产结构偏离，需继续核验持仓深度。" if meaningful else "本次未达到结构偏离规则，不扩大解读。",
           "对AUM有效且流动占比较高的 {fact:high_liquid} 继续核验产品持仓。" if b.facts["high_liquid"].value is not None else "行动范围已抑制，暂不提供人数或触达建议。",
           "金额加权占比与持有客户占比不同；基准定义由治理版本钉住；不构成产品推荐。",["NULL不补零；AUM分箱只统计有效AUM。","当前时点资产分类须与总AUM对账。"],benchmark=["benchmark_liquid_share"] if min(b.plan.cohort.count,bm.n)>=30 else [],difference=["liquid_gap"] if min(b.plan.cohort.count,bm.n)>=30 else [],population="high_liquid" if b.facts["high_liquid"].value is not None else None)
    try:
        quality=b.one("missing");b.add("aum_missing_count","aum_missing","AUM缺失客户",quality.holders,query="missing",n=quality.n)
        if quality.holders/quality.n>.05:b.reasons.append("AUM缺失率超过治理阈值，核验数据质量后使用")
    except ValueError as e:b.reasons.append("AUM缺失统计不可用："+str(e))


def g2(b):
    gap_rows=[];cohort_rows=[];baseline_rows=[];matrix=[]
    for category in b.plan.parameters["categories"]:
        label=LABELS.get(category,category)
        before=set(b.facts);charts_before=len(b.charts);cards_before=len(b.cards); entries_before=len(gap_rows)
        try:
            c=b.rows("coverage",category);baseline=b.rows("benchmark_coverage",category);mode=b.queries[("coverage",category)].standardization_mode
            if mode!=b.queries[("benchmark_coverage",category)].standardization_mode:raise ValueError("比较两侧标准化维度不一致")
            stats=standardize(c,baseline,mode=mode)
            if any(r.missing for r in [*c,*baseline]):b.reasons.append(label+"持有标志存在缺失；仅对有效标志样本比较")
            n=stats["sample"];bn=stats["baseline_sample"]
            num=b.add(category+"_holders","product_holding",label+"有效持有客户",sum(s for _,s in stats["cohort"].values()),query="coverage",n=n,category=category)
            den=b.add(category+"_valid","product_holding",label+"有效样本",n,query="coverage",n=n,category=category)
            rate=b.rate(category+"_rate","product_holding",label+"覆盖率",num,den,"coverage",n=n)
            bmden=b.add(category+"_benchmark_n","product_holding",label+"比较基准样本",bn,query="benchmark_coverage",n=bn,role="BENCHMARK",category=category)
            weights={}
            for i,(key,(celln,success)) in enumerate(stats["benchmark"].items()):
                d=b.add(f"{category}_bn_{i}","product_holding","基准格样本",celln,query="benchmark_coverage",n=celln,role="BENCHMARK",category=category)
                a=b.add(f"{category}_bh_{i}","product_holding","基准格持有客户",success,query="benchmark_coverage",n=celln,role="BENCHMARK",category=category)
                r=b.rate(f"{category}_br_{i}","product_holding","基准格持有率",a,d,"benchmark_coverage",role="BENCHMARK",n=celln)
                weights[r]=stats["weights"][key]
            br=b.add(category+"_benchmark_rate","product_holding",label+"结构标准化基准",stats["rate"],"%","benchmark_coverage",bn,role="BENCHMARK",denominator_id=bmden,derived_from=list(weights),calculation="WEIGHTED",weights=weights)
            gap=b.add(category+"_gap","product_holding",label+"覆盖缺口",stats["gap"],"pp","coverage",n,derived_from=[br,rate],role="DERIVED")
            cohort_rows.append((label,rate));baseline_rows.append((label,br));gap_rows.append((label,gap));matrix.append((label,gap,stats["mode"]))
            significant=stats["gap"]>=b.plan.parameters["min_gap_pp"] and stats["nonoverlapping"]
            if stats["fallback"]:b.reasons.append(label+"稀疏格退回"+stats["mode"]+"结构标准化")
            # 置信区间值也进入事实登记，叙述不得另写数字。
            for prefix,ci,denom,sz in [("cohort",stats["cohort_ci"],den,n),("baseline",stats["benchmark_ci"],bmden,bn)]:
                for end,value in zip(("lower","upper"),ci):b.add(category+"_"+prefix+"_"+end,"product_holding","置信区间"+end,value,"%","coverage" if prefix=="cohort" else "benchmark_coverage",sz,denominator_id=denom,role="DERIVED" if prefix=="cohort" else "BENCHMARK")
            population=None;action="本次不提供营销机会人数，先核验适当性或统计证据。"
            if significant:
                try:
                    stage=b.one("opportunity",category)
                    for fid,title,value in [("unheld","未持有",stage.unheld),("suitable","风险适配",stage.suitable),("opportunity","扣除营销排除后机会",stage.opportunity)]:
                        b.add(category+"_"+fid,"product_holding",label+title,value,query="opportunity",n=stage.n,category=category,role="POST_EXCLUSION" if fid=="opportunity" else "OBSERVED",exclusions_applied=["risk_mismatch","marketing_excluded"] if fid=="opportunity" else [])
                    population=category+"_opportunity"
                    stages=["customers",category+"_unheld",category+"_suitable",population]
                    if all(b.facts[f].value is not None for f in stages):
                        b.chart(category+"_funnel",label+"机会漏斗","show_conversion",[("客户",[(t,f) for t,f in zip(["客群","未持有","风险适配","可营销"],stages)])],"客户数",[Reconcile(kind="funnel",fact_ids=stages)])
                        action="对扣除风险不适配及营销排除后的 {fact:"+population+"} 核验触达意愿。"
                    else:population=None;raise ValueError("机会范围已抑制")
                except ValueError as e:b.reasons.append(label+str(e))
            diagnosis="统计比较满足阈值且置信区间不重叠，持有覆盖存在差异。" if significant else "本次统计证据未同时满足阈值和区间规则，不认定低配。"
            b.card(category+"_findings",label+"持仓核验","有效持有 {fact:"+num+"}，覆盖率 {fact:"+rate+"}。",
                "与结构标准化基准 {fact:"+br+"} 相比，覆盖缺口 {fact:"+gap+"}。",diagnosis,action,
                "圈选条件仅为已声明背景；Wilson区间及基准多格同时区间加权包络，非因果解释；缺适当性时只展示覆盖。",
                ["本次标准化维度："+stats["mode"],"权重来自当前客群构成，基准按同数据日有效持有标志计算。"],basis="STAT" if significant else "RULE",benchmark=[br],difference=[gap],population=population,statistical_evidence=dict(cohort_rate_id=rate,benchmark_rate_id=br,cohort_interval=stats["cohort_ci"],benchmark_interval=stats["benchmark_ci"],threshold_pp=b.plan.parameters["min_gap_pp"]) if significant else None)
        except (ValueError,GuardError) as e:
            b.facts={fid:f for fid,f in b.facts.items() if fid in before};del b.charts[charts_before:];del b.cards[cards_before:]
            del gap_rows[entries_before:];del cohort_rows[entries_before:];del baseline_rows[entries_before:];del matrix[entries_before:]
            b.reasons.append(label+"："+str(e))
    if gap_rows:
        order=sorted(range(len(gap_rows)),key=lambda i:b.facts[gap_rows[i][1]].value,reverse=True)
        b.chart("coverage","覆盖率与结构标准化基准","compare_categories",[("客群",[cohort_rows[i] for i in order]),("基准",[baseline_rows[i] for i in order])],"持有覆盖率")
        b.chart("gap_heatmap","品类标准化缺口","show_matrix",[("缺口",matrix)],"覆盖缺口")
        b.chart("gap_table","品类缺口汇总","compare_categories",[("缺口",[gap_rows[i] for i in order])],"覆盖缺口",table=True)
    else:raise ValueError("所有品类比较均不可用")
    if not any(c.intent=="show_conversion" for c in b.charts):b.reasons.append("没有通过统计与适当性门禁的机会漏斗")


def g3(b):
    rows=b.rows("priority");marketable=[r for r in rows if r.dimensions[0] in TIERS]
    count=sum(r.n for r in marketable)
    b.add("marketable","customer_count","可营销客户",count,query="priority",role="POST_EXCLUSION",exclusions_applied=["risk_mismatch","do_not_disturb","recent_contact","no_channel"])
    if count<20:raise ValueError("可营销样本不足")
    tiers=[];components={};channels={};reason_rows=[];reason_counts={};excluded=[]
    for tier in ("high","medium","low"):
        subset=[r for r in marketable if r.dimensions[0]==tier];n=sum(r.n for r in subset)
        b.add(tier,"customer_count",TIERS[tier]+"优先级",n,query="priority",n=count,role="POST_EXCLUSION",exclusions_applied=["risk_mismatch","do_not_disturb","recent_contact","no_channel"])
        tiers.append((TIERS[tier],tier))
        if n<20 and n!=0:raise ValueError("优先级小档已抑制")
        if not n:continue
        for metric in b.plan.queries[-1].components:
            value=fsum(r.contributions[metric.metric]*r.n for r in subset)/n
            fid=b.add(tier+"_"+metric.metric,metric.metric,"平均分项贡献",value,"分","priority",n)
            components.setdefault({"value_score":"价值","demand_event":"需求事件","product_gap":"产品缺口","historical_response":"历史响应","channel_reach":"渠道可达","disturbance_penalty":"打扰惩罚"}[metric.metric],[]).append((TIERS[tier],fid))
        for channel in sorted({r.dimensions[1] for r in subset}):
            channeln=sum(r.n for r in subset if r.dimensions[1]==channel)
            fid=b.add(tier+"_channel_"+str(sorted({r.dimensions[1] for r in subset}).index(channel)),"channel","主要有效渠道",channeln,query="priority",n=n)
            channels.setdefault({"app":"手机银行","phone":"电话","branch":"网点","manager":"客户经理"}.get(channel,channel),[]).append((TIERS[tier],fid))
    for i,r in enumerate(rows):
        if r.dimensions[0].startswith("excluded:"):
            fid=b.add("excluded_"+str(i),"customer_count","互斥排除原因",r.n,query="priority")
            excluded.append(({"risk_mismatch":"风险不适配","do_not_disturb":"勿扰","recent_contact":"近期已触达","no_channel":"无有效渠道","missing_score":"评分输入缺失"}.get(r.dimensions[0].split(":")[1],"资格未知"),fid))
        else:
            key="/".join({"value_score":"价值","demand_event":"需求","product_gap":"缺口","historical_response":"响应","channel_reach":"渠道","disturbance_penalty":"打扰","unknown":"未确定"}.get(x,x) for x in r.reasons)
            reason_counts[key]=reason_counts.get(key,0)+r.n
    ordered=sorted(reason_counts.items(),key=lambda x:(-x[1],x[0]))
    if len(ordered)>12:ordered=ordered[:11]+[("其他组合",sum(n for _,n in ordered[11:]))]
    for i,(label,n) in enumerate(ordered):
        fid=b.add("reason_"+str(i),"customer_count","主因组合人数",n,query="priority",n=count);reason_rows.append((label,fid))
    if sum(r.n for r in rows)!=b.plan.cohort.count:raise ValueError("评分排除与分档未覆盖客群")
    b.chart("priority_funnel","可营销机会漏斗","show_conversion",[("客户",[("客群","customers"),("可营销","marketable")])],"客户数",[Reconcile(kind="funnel",fact_ids=["customers","marketable"])])
    b.chart("tier_counts","并列优先级分档","show_distribution",[("客户",tiers)],"客户数",[Reconcile(kind="sum",fact_ids=[r[1] for r in tiers],total_fact_id="marketable")])
    b.chart("contributions","规则假设分项平均贡献","show_composition",list(components.items()),"平均贡献")
    b.chart("channels","各档主要有效渠道","compare_categories",list(channels.items()),"客户数")
    if reason_rows:b.chart("reason_table","贡献前两项原因组合","compare_categories",[("人数",reason_rows)],"客户数",table=True)
    if excluded:b.chart("exclusions","硬排除原因·顺序互斥归因","compare_categories",[("客户",excluded)],"客户数")
    b.card("priority_findings","营销机会规则排序","可营销客户 {fact:marketable}，高优先级 {fact:high}。","各档使用同一规则画像，本次不比较响应效果。",
           "假设：按已复核分档映射计算规则优先级，需用后续响应回测。","优先对 {fact:high} 按主要有效渠道人工核验。",
           "权重是规则假设，未经响应数据校准；先硬排除后打分；高、中、低是并列分组。范围按整体营销资格计算，产品缺口分仅赋给目标品类未持有客户；不下发名单或任务。",["排除原因采用顺序互斥归因；NULL资格与分项均排除。","主因仅取正贡献最大的前两项，相等按声明顺序；每人只计主渠道。"],basis="HYPOTHESIS",population="high")


def compose(plan: MetricPlan,batch: AggregateBatch,registry=None) -> SkillResult:
    registry=registry or SkillRegistry()
    if plan.status!="READY":return SkillResult(skill_id=plan.skill_id,skill_version=plan.skill_version,pack_hash=plan.pack_hash,status="BLOCKED",level="L4",reasons=plan.reasons)
    pins={"skill_id":plan.skill_id,"pack_hash":plan.pack_hash,"snapshot_id":plan.snapshot_id,"binding_version":plan.binding_version,"plan_hash":plan.cohort.plan_hash,"data_as_of":plan.cohort.data_as_of}
    if any(getattr(batch,k)!=v for k,v in pins.items()) or registry.hash(plan.skill_id)!=plan.pack_hash:
        raise ValueError("聚合结果或执行包版本与取数计划不一致")
    b=Builder(plan,batch)
    try:
        r=b.one("customers");
        if r.value!=plan.cohort.count:raise ValueError("客群人数与快照不一致，需要重新统计")
        b.add("customers","customer_count","客群客户数",r.value,n=r.n)
        {"asset_structure_profile":g1,"product_holding_gap":g2,"opportunity_priority":g3}[plan.skill_id](b)
        result=b.finish();validate_report(InsightReport(run_id="guard-compose",cohort=plan.cohort,results=[result]),registry,published_hashes={plan.skill_id:plan.pack_hash})
        return result
    except (ValueError,GuardError,TypeError,KeyError) as exc:
        return SkillResult(skill_id=plan.skill_id,skill_version=plan.skill_version,pack_hash=plan.pack_hash,status="BLOCKED",level="L4",reasons=[str(exc)[:500]])
