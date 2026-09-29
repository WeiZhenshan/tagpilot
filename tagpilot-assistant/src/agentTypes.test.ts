import {describe,it,expect} from 'vitest';
import {clauses,planDiff,expressionText,planStateText,toolText,gapText,type Plan} from './agentTypes';
const plan:Plan={tree:{logic:'AND',children:[{clause_id:'a',tag_id:1,name:'消费',operator:'>',values:['5000']},{logic:'OR',children:[{clause_id:'b',tag_id:2,name:'转入',operator:'>=',values:['500000']},{clause_id:'c',tag_id:3,name:'等级',operator:'in',values:['GOLD']}]}]}};
describe('版本化圈选条件',()=>{it('保留嵌套逻辑的全部条件',()=>expect(clauses(plan.tree).map(c=>c.clause_id)).toEqual(['a','b','c']));it('只报告发生变化的目标条件',()=>{const next=structuredClone(plan);clauses(next.tree)[1].values=['300000'];expect(planDiff(plan,next)).toEqual(['修改：转入 >= 500000 → >= 300000']);expect(clauses(plan.tree)[1].values).toEqual(['500000']);});it('逻辑变化单独可见',()=>{const next=structuredClone(plan);if('children'in next.tree)next.tree.logic='OR';expect(planDiff(plan,next)).toContain('条件组合结构已变化');});});

it('计算差异可见且不暴露物理实现',()=>{
  const a:Plan={tree:{kind:'DERIVED_PREDICATE',clause_id:'r',name:'存款占比',operator:'>=',values:['0.8'],expression:{kind:'DIV',args:[{kind:'TAG',tag_id:1,name:'存款'},{kind:'TAG',tag_id:2,name:'AUM'}]}}};
  const b=structuredClone(a);if(!('children' in b.tree))b.tree.values=['0.9'];
  expect(planDiff(a,b).length).toBeGreaterThan(0);
  expect(expressionText({kind:'TAG',tag_id:99})).not.toContain('99');
  expect(planStateText.CAPABILITY_GAP).toBeTruthy();
});

it('五个领域工具与缺口原因都有业务化文案',()=>{
  for(const name of ['find_tags','get_tag_details','find_capabilities','check_plan','submit_result'])
    expect(toolText[name],name).toBeTruthy();
  expect(toolText.find_tags).not.toContain('find_tags');
  for(const reason of ['NO_PUBLISHED_TAG','NO_CAPABILITY','CALIBER_UNAVAILABLE','METADATA_INCOMPLETE'])
    expect(gapText[reason],reason).toBeTruthy();
});

import {degradedOf,degradedText,runNotice,type Thread} from './agentTypes';
const partialThread = () => ({status:'COMPLETED',outcome:{outcome:'PARTIAL',gaps:[],stats:{degraded:{
  level:'L2',reason:'timeout',kept_clauses:['a'],unresolved_clause_ids:['b'],resumable:true,
  resume_mode:'lean',attempt:1,ops_alert:false,
}}}} as unknown as Thread);
it('降级结果可区分，旧结果和不合契约的数据安全兜底',()=>{
  expect(degradedOf(partialThread())?.kept_clauses).toEqual(['a']);
  expect(degradedOf({status:'COMPLETED'} as Thread)).toBeUndefined();
  const malformed=partialThread();malformed.outcome!.stats!.degraded={level:'L2',reason:'timeout'};
  expect(degradedOf(malformed)).toBeUndefined();
  for(const reason of ['timeout','memory_limit','max_turns','max_budget','tool_budget','queue_timeout','gateway','retrieval'])
    expect(degradedText[reason as keyof typeof degradedText]).toBeTruthy();
});
it('部分完成进入提示分支，真故障进入错误分支',()=>{
  const t=partialThread();expect(runNotice(t)).toBe('partial');
  t.status='FAILED';expect(runNotice(t)).toBe('failure');
  t.status='RUNNING';expect(runNotice(t)).toBeUndefined();
  expect(runNotice({status:'COMPLETED'} as Thread)).toBeUndefined();
});

import {clauseSentence,clauseUnit,pendingItems,treeSentence,type Clause} from './agentTypes';
describe('圈选方案业务摘要',()=>{
  it('保留单位倍率、否定、时间及区间，不把业务码值暴露为原始编码',()=>{
    const c:Clause={clause_id:'a',name:'消费金额',operator:'between',values:['1','5'],value_unit:'CNY',value_scale:'10000',time_constraint:'近3个月'};
    expect(clauseSentence(c)).toBe('近3个月 消费金额 介于 1 至 5万元');
    expect(clauseUnit(c)).toBe('万元');
    expect(clauseSentence({...c,name:'近3个月消费金额'})).toBe('近3个月消费金额 介于 1 至 5万元');
    expect(clauseSentence({clause_id:'b',name:'等级',operator:'not_in',values:['GOLD','NEW'],code_options:[{code:'GOLD',label:'金卡'}]})).toBe('等级 不属于 金卡、NEW');
    expect(clauseSentence({...c,operator:'is_not_null',values:[]})).toBe('近3个月 消费金额 不为空');
  });
  it('复制方案保留嵌套 AND/OR 和计算条件',()=>{
    const text=treeSentence(plan.tree);
    expect(text).toContain('满足以下全部条件');expect(text).toContain('满足以下任一条件');
    expect(clauseSentence({clause_id:'c',kind:'DERIVED_PREDICATE',operator:'>=',values:['0.8'],expression:{kind:'DIV',args:[{kind:'TAG',name:'存款'},{kind:'TAG',name:'AUM'}]}})).toBe('(存款 ÷ AUM) 至少 0.8');
  });
  it('合并相同条件的缺口与诊断，保留独立待处理事项',()=>{
    const p:Plan={valid:false,tree:{logic:'AND',children:[{clause_id:'a',requirement_ids:['r'],name:'消费',status:'GAP',gap_reason:'NO_PUBLISHED_TAG'}, {clause_id:'b',name:'高净值',status:'ASSUMED',assumption:{status:'PENDING',question:'确认口径'}}]},diagnostics:[{clause_id:'a',message:'缺少标签'},{message:'独立计算能力缺口'}]};
    const t={status:'COMPLETED',outcome:{gaps:[{requirement_id:'r',reason:'NO_PUBLISHED_TAG',nearest_tag_ids:[]}]}} as unknown as Thread;
    const q=pendingItems(t,p);expect(q.map(i=>i.kind)).toEqual(['gap','assumption','diagnostic']);expect(q[0].clause_id).toBe('a');
    expect(pendingItems(null,{...p,valid:true,tree:{clause_id:'a',status:'BOUND'},diagnostics:[]})).toEqual([]);
  });
});
