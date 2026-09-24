"""固定发布工件的只读冒烟；默认四个金标，不执行客户查询或建群。"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from tagpilot_agent.runtime.run_store import RunStore
from tagpilot_agent.runtime.run_manager import RunManager
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveClient

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--index',required=True)
    parser.add_argument('--snapshot',required=True)
    parser.add_argument('--cases',default='A01,A04,B02,D02')
    parser.add_argument('--output',required=True)
    parser.add_argument('--runtime',choices=['claude_sdk'],default='claude_sdk')
    parser.add_argument('--repeat',type=int,default=1)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    manifest_path=Path(args.index)/'manifest.json';manifest=json.loads(manifest_path.read_text())
    rows=[json.loads(line) for line in Path(args.snapshot).read_text().splitlines() if line.strip()]
    tags=[r['tag_id'] for r in rows if r['kind']=='tag']
    base={'build_id':manifest['build_id'],'snapshot_id':manifest['snapshot_id'],'artifact_hash':hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    source=(root/'sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md').read_text()
    inputs={}
    for line in source.splitlines():
        if re.match(r'^\| [A-K]\d\d \|',line):
            cells=[v.strip() for v in line.split('|')];inputs[cells[1]]=cells[5]
    report={'mode':'real_sdk_real_model_real_semantic_readonly','runtime':args.runtime,'model':os.getenv('ANTHROPIC_MODEL') or os.getenv('TAG_LLM_MODEL'),
            'build':base,'eligible_source':'fixed snapshot; not current Java user authorization','java_execution':False,'results':[]}
    with tempfile.TemporaryDirectory(prefix='tagpilot-gold-') as tmp:
        store=RunStore(str(Path(tmp)/'runs.sqlite'),'local-gold-smoke')
        manager=RunManager(store,lambda lib,build:SemanticRetrieveClient(os.getenv('TAG_SEMANTIC_URL','http://127.0.0.1:8091'),os.environ['TAG_RUNTIME_TOKEN'],lib,build))
        try:
            for repeat in range(args.repeat):
                for case in args.cases.split(','):
                    rid=f'eval-{case}-{repeat}';started=time.monotonic()
                    req={**base,'run_id':rid,'thread_id':rid,'owner_id':'offline-gold','library_id':manifest['library_id'],
                         'eligible_tag_ids':tags,'requirement':inputs[case],'previous_plan':{},'history':[]}
                    store.create(rid,req);await manager.execute(rid,req)
                    row=store.get(rid,'offline-gold');result=row['result'] or {}
                    item={'case':case,'repeat':repeat,'seconds':round(time.monotonic()-started,2),'status':row['status'],
                          'plan':result.get('plan',{}),'outcome':result.get('outcome'), 'events':store.events(rid), 'error':row['error']}
                    report['results'].append(item)
                    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                    print(json.dumps({'case':case,'status':row['status'],'valid':item['plan'].get('valid'),'seconds':item['seconds'],'stats':(item['outcome'] or {}).get('stats')},ensure_ascii=False),flush=True)
        finally:await manager.close();store.db.close()
    if any(not r['plan'].get('valid') for r in report['results']):raise SystemExit(1)

if __name__=='__main__':asyncio.run(main())
