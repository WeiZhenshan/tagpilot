"""对照只读取版本证据，不调用模型、不修改历史产物。"""
import json
from pathlib import Path
from .io import read_jsonl,write_json,fresh_directory,file_hash

def compare(baseline,candidate,output):
    a,b=Path(baseline),Path(candidate)
    sa=json.loads((a/'l1-summary.json').read_text());sb=json.loads((b/'l1-summary.json').read_text())
    ar=read_jsonl(a/'l1-results.jsonl');br=read_jsonl(b/'l1-results.jsonl')
    if [r['case_id'] for r in ar]!=[r['case_id'] for r in br]:raise ValueError('A/B案例行集不一致')
    for key in ('retrieval_config_hash','embedding_model','reranker_model','doc_template_version','store_type'):
        if sa['bundle'][key]!=sb['bundle'][key]:raise ValueError('A/B控制项不一致：'+key)
    gains=sorted(set(sa['failures'])-set(sb['failures']));losses=sorted(set(sb['failures'])-set(sa['failures']))
    micro=lambda rows:round(sum(sum(r['recalled']) for r in rows)/sum(r['conditions'] for r in rows),6)
    report={'phase':'P3','comparison':'A原语义/B新语义，固定原索引配置','cases':sa['cases'],'conditions':sa['conditions'],
        'a_recall':micro(ar),'b_recall':micro(br),'metric':'atomic_micro_recall',
        'a_all_covered':sa['all_conditions_covered_at_k'],'b_all_covered':sb['all_conditions_covered_at_k'],
        'gains':gains,'regressions':losses,'a_bundle':sa['bundle'],'b_bundle':sb['bundle'],
        'evidence_sha256':{'a':file_hash(a/'l1-results.jsonl'),'b':file_hash(b/'l1-results.jsonl')},
        'scope':'本地开发质量；不替代L2终态/L3完整ID集，不表示银行业务验收'}
    write_json(fresh_directory(output)/'comparison.json',report)
    return report
