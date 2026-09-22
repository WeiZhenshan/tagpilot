"""只读真实模型冒烟评测：固定发布工件，使用现有检索服务，不统计/建群。
能力检索在本进程执行当前代码，便于服务升级前验证；不代表 Java 端到端验收。
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from types import SimpleNamespace
from langgraph.checkpoint.sqlite import SqliteSaver
from tagpilot_agent.retrieve_client import SemanticRetrieveClient
from tagpilot_agent.workbench_graph import build_workbench, Planner

parser=argparse.ArgumentParser()
parser.add_argument('--index',required=True)
parser.add_argument('--snapshot',required=True)
parser.add_argument('--cases',default='A01,A04,B02,D02')
parser.add_argument('--output',required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'tagpilot-semantic'))
import importlib.util
spec=importlib.util.spec_from_file_location('evaluated_capabilities',root/'tagpilot-semantic/tag_semantic/retrieve/capabilities.py')
cap_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap_module)
search_capabilities=cap_module.search_capabilities
manifest_path=Path(args.index)/'manifest.json'
manifest=json.loads(manifest_path.read_text())
rows=[json.loads(line) for line in Path(args.snapshot).read_text().splitlines() if line.strip()]
tags={r['tag_id']:r for r in rows if r['kind']=='tag'}
catalog=SimpleNamespace(capabilities={r['capability_id']:r for r in rows if r['kind']=='capability'})
base={'build_id':manifest['build_id'],'snapshot_id':manifest['snapshot_id'],'artifact_hash':hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
class EvaluatedRetriever(SemanticRetrieveClient):
    def capabilities(self, requirement, eligible, capability_ids=None):
        caps=search_capabilities(catalog,requirement,eligible,capability_ids or [])
        deps={i for c in caps for i in c.get('input_tag_ids',[])}
        return {**base,'capabilities':caps,'selection_context':{'tags':[tags[i] for i in deps],'code_values':[]}}
source=(root/'sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md').read_text()
inputs={}
for line in source.splitlines():
    if re.match(r'^\| [A-K]\d\d \|',line):
        cells=[v.strip() for v in line.split('|')];inputs[cells[1]]=cells[5]

def run(case):
    started=time.monotonic();events=[];actions=[]
    class RecordingPlanner(Planner):
        def decide(self,context):
            action=super().decide(context);actions.append(__import__('copy').deepcopy(action));return action
    request={**base,'run_id':'eval-'+case,'thread_id':'eval-'+case,'owner_id':'offline-evaluation','library_id':manifest['library_id'],'eligible_tag_ids':list(tags),'requirement':inputs[case],'history':[]}
    try:
        retriever=EvaluatedRetriever(os.getenv('TAG_SEMANTIC_URL','http://127.0.0.1:8091'),os.environ['TAG_RUNTIME_TOKEN'],manifest['library_id'],manifest['build_id'])
        with sqlite3.connect(':memory:',check_same_thread=False) as conn:
            result=build_workbench(retriever,SqliteSaver(conn),events.append,lambda:False,RecordingPlanner()).invoke({'request':request},{'configurable':{'thread_id':case},'recursion_limit':240})
        return {'case':case,'seconds':round(time.monotonic()-started,2),'interrupted':bool(result.get('__interrupt__')),'plan':result.get('plan'),'tool_calls':result.get('calls'),'repairs':result.get('repairs'),'actions':actions}
    except Exception as exc:
        # 不记录 HTTP 请求头、环境变量或原始端点凭据。
        import traceback
        return {'case':case,'seconds':round(time.monotonic()-started,2),'error_type':type(exc).__name__,'error_detail':str(exc) if isinstance(exc,(ValueError,AttributeError,TypeError)) else None,'error_location':[f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in traceback.extract_tb(exc.__traceback__)][-6:],'actions':actions,'last_plan':next((e['plan'] for e in reversed(events) if e.get('plan')),None)}

out={'mode':'real_llm_readonly_fixed_artifact','model':os.getenv('TAG_LLM_MODEL'),'build':base,'eligible_source':'snapshot tags; not current Java user eligibility','capability_count':len(catalog.capabilities),'results':[]}
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    for result in pool.map(run,args.cases.split(',')):
        out['results'].append(result)
        print(json.dumps({'case':result['case'],'valid':result.get('plan',{}).get('valid'),'status':result.get('plan',{}).get('plan_status'),'error':result.get('error_type'),'seconds':result['seconds']},ensure_ascii=False),flush=True)
        path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
