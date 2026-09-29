"""P3 原始运行证据与独立裁判。每轮独立 ID，失败不覆盖；支持仅重跑失败题。"""
import argparse
import json
import time
import re
import copy
from pathlib import Path
from collections import Counter
from .io import read_jsonl,file_hash,digest,write_json
from .runtime import SemanticClient,AgentClient
from .l2 import _drive_case,_terminal_result,_fixture_rows,_stages,_merge_multiturn,_append,OWNER
from .judge import grade_case
from .local import JavaClient,mysql

def grade_state(case,expected,state,facts,rows):
    result=_terminal_result(state)
    if '权限或发布版本' in str(state.get('error')):
        return {'status':'RUN_INVALID','checks':{},'failures':['AUTHORITY_CONTEXT_MISMATCH'],
                'evidence':{'agent_error':state.get('error')}}
    if state.get('cancelled_by_harness') or state.get('status') in {'FAILED','CANCELLED'}:
        return {'status':'FAIL','checks':{'run_terminal':False},'failures':['AGENT_TIMEOUT_OR_FAILED'],
                'evidence':{'agent_error':state.get('error'),'original_verdict':grade_case(case,expected,result,facts,rows)}}
    return grade_case(case,expected,result,facts,rows)


def run_cases(p0,cases_dir,output,build_id,case_ids=None,limit=None,max_seconds=90):
    p0,cases_dir,output=map(Path,(p0,cases_dir,output));output.mkdir(parents=True,exist_ok=True)
    facts={f['tag_id']:f for f in read_jsonl(p0/'facts.jsonl')}
    rows=_fixture_rows(json.loads((p0/'manifest.json').read_text()))
    cases=read_jsonl(cases_dir/'cases.jsonl')
    # 637 在本轮开始前已经是 DRAFT；A/B 固定同一已发布资格，不能把
    # 已从新快照排除的标签传给 Agent，再将资格摘要拒绝误判为语义失败。
    cases=copy.deepcopy(cases)
    for case in cases:
        case['eligible_tag_ids']=sorted(set(case['eligible_tag_ids'])-{637})
    if case_ids:cases=[c for c in cases if c['case_id'] in set(case_ids)]
    if limit:cases=cases[:limit]
    bundle=SemanticClient().bundle(build_id);agent=AgentClient()
    write_json(output/'qualification.json',{'excluded_tag_ids':[637],
        'basis':'p3-observation-20260928.json: tag 637 pre-existing DRAFT',
        'policy':'same published eligibility in all P3 A/B/C/D runs'})
    if not (output/'bundle.json').exists():write_json(output/'bundle.json',bundle)
    prior=read_jsonl(output/'runs.jsonl') if (output/'runs.jsonl').exists() else []
    done={r['case_id'] for r in prior}
    for case in cases:
        if case['case_id'] in done:continue
        rid='p3-'+digest(str(output)+file_hash(cases_dir/'cases.jsonl'))[:12]+'-'+case['case_id'].lower()
        started=time.monotonic();stats={};states=[];events=[]
        try:
            states,events=_drive_case(agent,case,bundle,rid,max_seconds)
            result=_terminal_result(states[-1]);stats=(result.get('outcome') or {}).get('stats') or {}
            verdict=grade_state(case,_stages(case)[-1],states[-1],facts,rows)
            if len(states)>1:
                first=grade_state(case,case['expected'],states[0],facts,rows)
                verdict=_merge_multiturn(verdict,first,result)
            if states[-1].get('cancelled_by_harness') or not result.get('outcome'):
                verdict={'status':'FAIL','checks':verdict.get('checks',{}),'failures':['AGENT_TIMEOUT_OR_FAILED'],
                         'evidence':{'original_verdict':verdict,'agent_error':states[-1].get('error')}}
                if '权限或发布版本' in str(states[-1].get('error')):
                    verdict['status']='RUN_INVALID';verdict['failures']=['AUTHORITY_CONTEXT_MISMATCH']
        except Exception as e:
            result={};verdict={'status':'RUN_INVALID','checks':{},'failures':['ENVIRONMENT_EXCEPTION'],'evidence':{'error':str(e)[:500]}}
        evidence=output/'evidence';evidence.mkdir(exist_ok=True)
        write_json(evidence/(case['case_id']+'.json'),{'states':states,'events':events})
        turn_stats=[((_terminal_result(s).get('outcome') or {}).get('stats') or {}) for s in states]
        run={'schema_version':'eval-run.v1','run_id':rid,'case_id':case['case_id'],'dataset_sha256':file_hash(cases_dir/'cases.jsonl'),
             'source_revision':build_id,'model':stats.get('model'),
             'prompt_sha256':stats.get('prompt_sha256'),
             **{k:bundle[k] for k in ('snapshot_id','build_id','artifact_hash')},
             'eligible_sha256':digest(case['eligible_tag_ids']),'reference_date':case['reference_date'],
             'status':'COMPLETED' if result.get('outcome') else 'AGENT_FAILED','outcome':(result.get('outcome') or {}).get('outcome'),
             'output':result,'evidence_paths':[str(evidence/(case['case_id']+'.json'))],
             'elapsed_ms':round((time.monotonic()-started)*1000),
             'input_tokens':sum((s.get('usage') or {}).get('input_tokens',0) for s in turn_stats),
             'output_tokens':sum((s.get('usage') or {}).get('output_tokens',0) for s in turn_stats),
             'actual_cost':str(sum(float(s.get('sdk_cost_estimate_usd') or 0) for s in turn_stats)),
             'stats':{**stats,'turns':len(states),'cost_basis':'sum of per-turn SDK estimates, not provider invoice'}}
        _append(output/'runs.jsonl',run);_append(output/'verdicts.jsonl',{'case_id':case['case_id'],**verdict})
        print(case['case_id'],case['scenario'],verdict['status'],run['outcome'],run['elapsed_ms']/1000,verdict.get('failures'),flush=True)
    runs=read_jsonl(output/'runs.jsonl');vs=read_jsonl(output/'verdicts.jsonl')
    elapsed=sorted(r['elapsed_ms'] for r in runs)
    summary={'phase':'P3','runs':len(runs),'verdicts':dict(Counter(v['status'] for v in vs)),
             'failed_case_ids':[v['case_id'] for v in vs if v['status']!='PASS'],
             'p50_ms':elapsed[len(elapsed)//2],'p95_ms':elapsed[min(len(elapsed)-1,int(len(elapsed)*.95))],
             'cost_sdk_estimate_usd':sum(float(r['actual_cost']) for r in runs),'bundle':bundle,
             'dataset_sha256':file_hash(cases_dir/'cases.jsonl')}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary


def run_java(p0,cases_dir,runs_dirs,output,client):
    """真实 Java 编译/COUNT + 同一 Java SQL 的完整模拟 ID 集，与独立 oracle 对齐。"""
    p0,cases_dir,output=map(Path,(p0,cases_dir,output));output.mkdir(parents=True,exist_ok=True)
    rows=_fixture_rows(json.loads((p0/'manifest.json').read_text()))
    from .oracle import fixture_result
    cases={c['case_id']:c for c in read_jsonl(cases_dir/'cases.jsonl')}
    latest={}
    for path in runs_dirs:
        for run in read_jsonl(Path(path)/'runs.jsonl'):latest[run['case_id']]=run
    done={r['case_id'] for r in read_jsonl(output/'results.jsonl')} if (output/'results.jsonl').exists() else set()
    for cid,run in latest.items():
        if cid in done:continue
        try:
            plan=run['output']['plan']
            compiled=client.call('POST','/taglibrary/agent/plan/compile',{'library_id':107,'plan':plan})
            actual=client.call('POST','/objectgroup/group/run',{'libraryId':107,'rule':compiled['rule']})
            sql=compiled['count_sql']
            if not re.match(r'^select count\(\*\)\s+from\s',sql,re.I):raise ValueError('Java COUNT SQL 形状不受支持')
            sql=re.sub(r'^select count\(\*\)', 'select `CUST_ID`',sql,count=1,flags=re.I)
            ids=sorted(mysql('START TRANSACTION READ ONLY; USE indiv_cust; '+sql+' ORDER BY `CUST_ID`; COMMIT;'))
            if any(not i.startswith('SIM20260918') for i in ids):raise ValueError('出现模拟fixture之外客户，停止验证')
            final=(cases[cid]['turns'] or [{'expected':cases[cid]['expected']}])[-1]['expected']
            expected=fixture_result(final['tree'],rows)
            count=actual.get('count')
            result={'case_id':cid,'status':'PASS' if ids==expected['ids'] and count==expected['count'] else 'FAIL',
                'java_count':count,'oracle_count':expected['count'],'java_ids':ids,'java_ids_sha256':digest(ids),
                'oracle_ids_sha256':expected['ids_sha256'],'full_id_set_equal':ids==expected['ids'],'java_sql':compiled['count_sql']}
        except Exception as e:result={'case_id':cid,'status':'RUN_INVALID','error':str(e)[:800]}
        _append(output/'results.jsonl',result)
        print('L3',cid,result['status'],result.get('java_count'),result.get('error',''),flush=True)
    results=read_jsonl(output/'results.jsonl')
    summary={'phase':'P3','layer':'L3','cases':len(results),'statuses':dict(Counter(r['status'] for r in results))}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--p0',type=Path,required=True);p.add_argument('--cases',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--build',required=True);p.add_argument('--limit',type=int)
    p.add_argument('--case-ids',nargs='*');a=p.parse_args()
    print(json.dumps(run_cases(a.p0,a.cases,a.output,a.build,a.case_ids,a.limit),ensure_ascii=False))
if __name__=='__main__':main()
