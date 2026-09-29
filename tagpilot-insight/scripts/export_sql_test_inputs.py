"""输出跨语言合成 SQL 测试计划；仅供单元测试，从不访问真实数据。"""
import json,sys
from pathlib import Path
from tagpilot_insight.registry import SkillRegistry
from tagpilot_insight.contracts import CohortSnapshot
from tagpilot_insight.planning import MetricPlan
reg=SkillRegistry()
cohort=CohortSnapshot(audience_id='sql-reference',audience_name='合成SQL参考客群',library_id=107,revision=1,plan_hash='a'*64,snapshot_id='sql-snapshot',count=240,data_as_of='2026-09-28',reference_date='2026-09-29',binding_version='0.1.0',synthetic=True)
plans=[MetricPlan(skill_id=id,skill_version=m.version,pack_hash=reg.hash(id),snapshot_id=cohort.snapshot_id,binding_version=cohort.binding_version,cohort=cohort,parameters=reg.parameters(id),status='READY',reasons=[],queries=m.queries).model_dump(mode='json') for id,m in reg.manifests.items()]
Path(sys.argv[1]).write_text(json.dumps(plans,ensure_ascii=False,indent=2)+'\n')
