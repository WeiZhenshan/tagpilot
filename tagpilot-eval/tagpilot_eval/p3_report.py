"""P3 报告汇总：按明确列出的迭代顺序取最后一次判定，不挑选最好的一次。"""
import json
from collections import Counter
from pathlib import Path
from .io import read_jsonl,write_json,write_jsonl,file_hash


def summarize(cases_dir,runs_dirs,java_dir,output):
    cases_dir,java_dir,output=map(Path,(cases_dir,java_dir,output))
    output.mkdir(exist_ok=True,parents=True)
    cases=read_jsonl(cases_dir/'cases.jsonl');ids={c['case_id'] for c in cases}
    dataset=file_hash(cases_dir/'cases.jsonl');latest={};history=[]
    for path in map(Path,runs_dirs):
        runs={r['case_id']:r for r in read_jsonl(path/'runs.jsonl')}
        verdicts={v['case_id']:v for v in read_jsonl(path/'verdicts.jsonl')}
        if runs.keys()!=verdicts.keys():raise ValueError('运行与判定行集不同')
        run_hash=file_hash(path/'runs.jsonl');verdict_hash=file_hash(path/'verdicts.jsonl')
        for cid,run in runs.items():
            if cid not in ids or run['dataset_sha256']!=dataset:raise ValueError('Demo 输入版本或案例越界')
            record={'case_id':cid,'run_directory':str(path),'run_id':run['run_id'],
                'status':verdicts[cid]['status'],'failures':verdicts[cid].get('failures',[]),
                'elapsed_ms':run['elapsed_ms'],'prompt_sha256':run.get('prompt_sha256'),
                'build_id':run['build_id'],'artifact_hash':run['artifact_hash'],
                'model':run.get('model'),'turns':run['stats'].get('turns'),
                'sdk_estimate_usd':float(run['actual_cost']),
                'raw_run_sha256':run_hash,'raw_verdict_sha256':verdict_hash}
            history.append(record);latest[cid]=record
    if set(latest)!=ids:raise ValueError('未完整实际运行全部100案例')
    ordered=[latest[c['case_id']] for c in cases]
    java=read_jsonl(java_dir/'results.jsonl') if (java_dir/'results.jsonl').exists() else []
    jmap={r['case_id']:r for r in java}
    if len(jmap)!=len(java) or set(jmap)-ids:raise ValueError('Java 行集重复或越界')
    elapsed=sorted(r['elapsed_ms'] for r in ordered)
    turn_elapsed=[]
    for r in ordered:
        import json
        evidence=json.loads((Path(r['run_directory'])/'evidence'/f"{r['case_id']}.json").read_text())
        # resume 从 seq=0 再读事件，保存文件含重复前缀；按事件身份去重。
        events={(e.get('seq'),e.get('type'),e.get('occurred_at')):e for e in evidence['events']}
        started=None
        for e in sorted(events.values(),key=lambda e:e.get('occurred_at',0)):
            if e.get('type')=='run.started':started=e['occurred_at']
            elif started is not None and e.get('type') in {'run.waiting','run.completed','run.failed'}:
                turn_elapsed.append(round((e['occurred_at']-started)*1000));started=None
    turn_elapsed.sort()
    scenarios={name:{'cases':sum(c['scenario']==name for c in cases),
        'l2_pass':sum(latest[c['case_id']]['status']=='PASS' for c in cases if c['scenario']==name),
        'l3_pass':sum(jmap.get(c['case_id'],{}).get('status')=='PASS' for c in cases if c['scenario']==name)}
        for name in dict.fromkeys(c['scenario'] for c in cases)}
    summary={'phase':'P3','scope':'固定100个Demo开发案例；不扩量到P4','cases':len(cases),
        'user_messages':sum(1+len(c['turns']) for c in cases),'multiturn_cases':sum(bool(c['turns']) for c in cases),
        'dataset_sha256':dataset,'run_directories_in_iteration_order':list(map(str,runs_dirs)),
        'latest_l2_statuses':dict(Counter(r['status'] for r in ordered)),
        'l3_statuses':dict(Counter(r['status'] for r in java)),
        'latest_builds':dict(Counter(r['build_id'] for r in ordered)),
        'latest_prompts':dict(Counter(r['prompt_sha256'] for r in ordered)),
        'first_full_round_statuses':dict(Counter(r['status'] for r in history[:100])),
        'iterations_recorded':len(history),'latest_case_latency':{
            'p50_ms':elapsed[len(elapsed)//2],'p95_ms':elapsed[int(len(elapsed)*.95)],'max_ms':max(elapsed),
            'includes_multiturn':True,'concurrency':2},
        'latest_user_turn_latency':{'turns':len(turn_elapsed),'p50_ms':turn_elapsed[len(turn_elapsed)//2],
            'p95_ms':turn_elapsed[int(len(turn_elapsed)*.95)],'max_ms':max(turn_elapsed)},
        'sdk_cost_estimate_usd':sum(r['sdk_estimate_usd'] for r in history),
        'cost_basis':'所有指定轮次逐轮SDK估算总和；不是DeepSeek账单；既有其它开发回放另列。',
        'scenarios':scenarios,'successful':all(r['status']=='PASS' for r in ordered)
            and set(jmap)==ids and all(r['status']=='PASS' for r in java)}
    write_jsonl(output/'latest-case-evidence.jsonl',ordered)
    write_json(output/'summary.json',summary)
    return summary
