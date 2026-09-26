"""代码质量检查；不冒充独立模型的中文语义复核或人的业务复核。"""
import json
import gzip
import hashlib
from collections import Counter
from decimal import Decimal
from pathlib import Path

from .contracts import EvalCase
from .io import file_hash, digest, read_jsonl
from .oracle import references
from .seeds import QUOTAS


def verify_package(path):
    path=Path(path)
    manifest=json.loads((path/'manifest.json').read_text())
    for name,expected in manifest['files'].items():
        if Path(name).name!=name or file_hash(path/name)!=expected:
            raise ValueError('工件 hash 不匹配: '+name)
    for source in manifest.get('sources',{}).values():
        frozen=source.get('frozen_copy')
        if frozen:
            if Path(frozen).parts != ('sources',Path(frozen).name):
                raise ValueError('冻结来源路径非法')
            payload=gzip.decompress((path/frozen).read_bytes())
            if hashlib.sha256(payload).hexdigest()!=source['sha256']:
                raise ValueError('冻结来源 hash 不匹配: '+frozen)
    return manifest


def validate_cases(cases,facts,p0_hash):
    cases=[EvalCase.model_validate(case).model_dump(exclude_none=True) for case in cases]
    errors=[]
    def error(case,code,detail):errors.append({'case_id':case['case_id'],'code':code,'detail':detail})
    ids=[c['case_id'] for c in cases];mothers=[c['mother_id'] for c in cases]
    if len(cases)!=200 or len(set(ids))!=200 or len(set(mothers))!=200:
        raise ValueError('必须恰好200个不同母案例')
    if dict(Counter(c['category'] for c in cases))!=QUOTAS:raise ValueError('配额错误')
    trajectories={digest([c['requirement'],*[t['user_message'] for t in c['turns']]]) for c in cases}
    if len(trajectories)!=200:raise ValueError('完整输入轨迹重复')
    for case in cases:
        if case['source_manifest_sha256']!=p0_hash:error(case,'SOURCE_HASH','P0版本不匹配')
        tids=set(case['target_tag_ids'])
        eligible=set(case['eligible_tag_ids'])
        if len(eligible)!=len(case['eligible_tag_ids']) or not eligible<=facts.keys():error(case,'ELIGIBILITY','资格重复或不存在')
        if not tids<=facts.keys():error(case,'UNKNOWN_TAG','目标标签不存在');continue
        if set(case['fact_ids'])!={f'TAG:{t}' for t in tids}:error(case,'FACT_REFS','事实引用未覆盖目标')
        unresolved={f'TAG:{t}' for t in tids if facts[t]['fact_status']=='UNRESOLVED'}
        if set(case['unresolved_fact_ids'])!=unresolved:error(case,'UNRESOLVED','隐藏未解决事实')
        stages=[case['expected']]+[t['expected'] for t in case['turns']]
        for expected in stages:
            tree=expected.get('tree')
            if not tree:continue
            refs=references(tree)
            if not refs<=tids:error(case,'TARGET_COVERAGE','标准树引用不在案例目标中')
            ready='READY' in expected['outcomes']
            if ready and (unresolved or not refs<=eligible):error(case,'FALSE_READY','未解决事实或资格不能READY')
            if ready and refs&set(case['forbidden_tag_ids']):error(case,'FORBIDDEN_TAG','标准树使用禁止标签')
            def visit_expr(expr):
                if expr['kind']=='TAG':
                    f=facts.get(expr['tag_id'])
                    if not f or expr['field_name']!=f['field_name']:error(case,'FIELD_BINDING','字段与标签不一致')
                    elif expr['unit']!=f['published_semantics']['unit']:error(case,'UNIT_BINDING','单位不一致')
                for child in expr.get('args',[]):visit_expr(child)
            def visit(node):
                if node['kind']=='GROUP':
                    for child in node['children']:visit(child)
                elif node['kind']=='PREDICATE':
                    visit_expr(node['expression'])
                    if node['expression']['kind']=='TAG':
                        f=facts[node['expression']['tag_id']]
                        if ready and node['operator'] not in f['published_semantics']['allowed_operators']:
                            error(case,'UNSUPPORTED_OPERATOR',{'tag_id':f['tag_id'],'operator':node['operator']})
                        if f['codes'] and node['operator'] not in {'is_null','is_not_null'}:
                            if not set(node['values'])<={c['code'] for c in f['codes']}:
                                error(case,'CODE_VALUE','码值非法或丢失前导零')
                        expected_kind='STRING' if f['codes'] or f['tag_type']=='文本型' else 'DATE' if f['tag_type']=='日期型' else 'NUMBER'
                        if node['data_kind']!=expected_kind:error(case,'DATA_KIND','字面量类型不匹配')
                        if ready and node['caliber']!={k:v for k,v in f['published_semantics']['caliber_struct'].items() if v is not None}:
                            error(case,'CALIBER','时间/统计/范围不匹配')
            visit(tree)
    return {'schema_version':'calibration-validation.v1','case_count':len(cases),'mother_count':len(set(mothers)),
            'lineage_groups':len({c['lineage_group'] for c in cases}),'categories':dict(Counter(c['category'] for c in cases)),
            'target_tags':len({t for c in cases for t in c['target_tag_ids']}),
            'domain_coverage':dict(Counter(d for c in cases for d in c['domains'])),
            'outcomes':dict(Counter(c['expected']['outcomes'][0] for c in cases)),
            'errors':errors,'passed':not errors,
            'independent_language_review':'NOT_RUN','human_review':'PENDING','formal_cases':0}


def validate_package(p0,calibration):
    verify_package(p0);manifest=verify_package(calibration)
    if manifest['p0_manifest_sha256']!=file_hash(Path(p0)/'manifest.json'):
        raise ValueError('P1绑定的P0版本不一致')
    facts={r['tag_id']:r for r in read_jsonl(Path(p0)/'facts.jsonl')}
    return validate_cases(read_jsonl(Path(calibration)/'cases.jsonl'),facts,file_hash(Path(p0)/'manifest.json'))
