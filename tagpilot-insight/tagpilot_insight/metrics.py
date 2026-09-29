"""统一指标语义与基准定义；运行事实引用这些版本，不由模型重定义口径。"""
from typing import Literal
from pydantic import Field
from .contracts import Contract, Identifier, Text, Unit, Version

class MetricDefinition(Contract):
    id: Identifier
    name: Text
    definition: Text
    calculation: Text
    unit: Unit
    numerator: Text | None = None
    denominator: Text | None = None
    dimensions: list[Identifier] = Field(default_factory=list, max_length=2)
    time_grain: Literal["day"] = "day"
    update_frequency: Text = "每日"
    owner: Text = "待业务复核"
    quality_rules: list[Text] = Field(min_length=1)
    permission: Literal["taglibrary:insight:run"] = "taglibrary:insight:run"
    version: Version = "0.1.0"
    sources: list[Identifier] = Field(default_factory=list)

class BenchmarkDefinition(Contract):
    id: Identifier
    type: Literal["same_aum", "all_customers", "same_org", "standardized"]
    definition: Text
    dimensions: list[Identifier] = Field(default_factory=list, max_length=2)
    sparse_fallback: Literal["aum_then_risk_then_suppress"] = "aum_then_risk_then_suppress"
    version: Version = "0.1.0"
    # 缓存还须包含授权范围和绑定版本，避免跨用户/机构复用。
    cache_fields: tuple[str, ...] = ("data_as_of", "definition", "version", "binding_version", "snapshot_id", "scope_hash")

METRICS = {
 "customer_count": MetricDefinition(id="customer_count",name="客户数",definition="数据日有效且在客群规则范围内的唯一客户数",calculation="唯一客户键计数",unit="人",quality_rules=["客户键唯一且非空"]),
 "aum": MetricDefinition(id="aum",name="当前 AUM",definition="当前数据日客户资产总额",calculation="有效值求和、均值及连续分位数；NULL不补零",unit="元",quality_rules=["非负、资产分类合计与AUM对账"]),
 "product_holding": MetricDefinition(id="product_holding",name="产品持有率",definition="统计日持有有效品类产品的客户占比",calculation="有效持有标志计数/有效标志客户数",unit="%",numerator="品类有效持有客户数",denominator="品类持有标志非空客户数",dimensions=["aum_tier","risk_level"],quality_rules=["标志仅为零或一，NULL单独记缺失"]),
 "liquid_share": MetricDefinition(id="liquid_share",name="高流动资产客户",definition="AUM有效且流动资产/AUM超过治理阈值的客户",calculation="在Java内计算比值并计数，分母必须正数",unit="人",sources=["liquid_aum","aum"],quality_rules=["无效AUM硬排除"]),
 "product_gap": MetricDefinition(id="product_gap",name="结构标准化覆盖缺口",definition="按客群AUM×风险结构加权基准与客群覆盖率之差",calculation="Σ客群格权重×基准格持有率−客群持有率；Wilson区间及多格同时区间的加权包络判定",unit="pp",sources=["product_holding","aum_tier","risk_level"],quality_rules=["两侧有效样本充分；稀疏回退须明示；区间不重叠才作STAT诊断"]),
}

# 每个逻辑指标统一登记，品类通过绑定category细分，不重复定义分母。
for metric,name,definition,unit,source in [
 ("aum_tier","AUM层级","业务复核的当前AUM层级码，未知码不参加比较","人",["aum"]),
 ("risk_level","风险等级","经治理映射为有序风险等级，不按字典编码大小猜测等级","分",[]),
 ("liquid_aum","流动资产AUM","当前时点活期及约定流动资产金额","元",["aum"]),
 ("fixed_aum","定期资产AUM","当前时点定期资产金额","元",["aum"]),
 ("investment_aum","投资资产AUM","当前时点理财、基金、保险等经复核的完整投资资产金额","元",["aum"]),
 ("asset_holder","资产持有客户","对应资产类别余额大于零的客户；允许持有多个类别","人",[]),
 ("aum_missing","AUM缺失客户","当前AUM为NULL的客户数；不以零替代NULL","人",["aum"]),
 ("suitability","适当性资格","品类最低风险等级治理映射与客户有效风险等级比较","人",["risk_level"]),
 ("marketing_excluded","营销排除标志","经复核排除规则命中的客户；未知资格不能视作可营销","人",[]),
 ("value_score","价值评分输入","按治理画像读取当前AUM值再作固定分档","元",["aum"]),
 ("demand_event","需求事件标志","经业务复核的近期需求事件，非模型因果判断","分",[]),
 ("historical_response","历史响应标志","数据日期前已确认的响应事件；未知不作正贡献","分",[]),
 ("channel_reach","渠道可达标志","经核验的有效触达渠道资格","分",["channel"]),
 ("disturbance_penalty","打扰惩罚输入","经治理触达历史生成的打扰惩罚标志","分",[]),
 ("channel","主要渠道","经治理选出的单一主要有效渠道，非手机号等客户明细","人",[]),
 ("risk_mismatch","风险不适配","目标品类风险适当性不满足或未知","人",["risk_level"]),
 ("do_not_disturb","勿扰资格","客户勿扰或禁止营销标志","人",[]),
 ("recent_contact","近期触达排除","数据日期前N日已经触达；N由已校验参数传入Java","人",[]),
 ("no_channel","无有效渠道排除","缺少有效主渠道或渠道资格未知","人",["channel"]),
]:
 METRICS[metric]=MetricDefinition(id=metric,name=name,definition=definition,calculation="已发布MetricBinding及固定白名单节点；NULL资格排除",unit=unit,sources=source,quality_rules=["来源与数据集在线版本一致","口径须经业务复核，不自动推断"])

BENCHMARKS = [BenchmarkDefinition(id=kind,type=kind,definition=description,dimensions=dimensions) for kind,description,dimensions in [
 ("same_aum","同数据日、当前授权来源、客群所包含AUM层级的有效客户",["aum_tier"]),
 ("all_customers","同数据日、当前账号获授权来源中的全部有效客户",[]),
 ("same_org","经治理机构绑定、客群唯一机构对应的授权有效客户",[]),
 ("standardized","按客群AUM×风险构成加权同数据日授权基准；稀疏时退回单维",["aum_tier","risk_level"]),
]]
