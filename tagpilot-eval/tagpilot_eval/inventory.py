"""P0：来源、发布快照、实时状态三方审计，发现问题但不修正业务数据。"""
import gzip
import json
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from .io import digest, file_hash, fresh_directory, read_jsonl, write_json, write_jsonl
from .sources import load_ddl, load_code_maps, load_fixture, source_names, normalize_name

SOURCE_DIR = 'sql/indiv_cust'
ARTIFACT_ROOT = 'tagpilot-semantic/out/full-20260919'


def inventory(root, output, observation):
    root, output = Path(root).resolve(), Path(output)
    if output.exists():
        raise ValueError('输出目录已存在，请使用新的版本目录')
    live = json.loads(Path(observation).read_text())
    database = live['database']
    active_snapshots = [s for s in database['snapshots'] if s['status'] == 'ACTIVE']
    active_builds = [b for b in database['builds'] if b['status'] == 'ACTIVE']
    if len(active_snapshots) != 1 or len(active_builds) != 1:
        raise ValueError('ACTIVE 快照/索引不是唯一，停止冻结')
    active, build = active_snapshots[0], active_builds[0]
    if build['snapshot_id'] != active['snapshot_id']:
        raise ValueError('ACTIVE 组合不一致')
    snapshot_path = root / ARTIFACT_ROOT / 'snapshots' / (active['snapshot_id']+'.jsonl')
    manifest_path = root / ARTIFACT_ROOT / 'indexes' / build['build_id'] / 'manifest.json'
    if file_hash(snapshot_path) != active['file_sha256'] or file_hash(manifest_path) != build['artifact_hash']:
        raise ValueError('数据库登记 hash 与本地快照/manifest 不一致')
    snapshot = read_jsonl(snapshot_path)
    manifest = json.loads(manifest_path.read_text())
    if manifest['snapshot_id'] != active['snapshot_id'] or manifest['content_hash'] != active['content_hash']:
        raise ValueError('发布内容 hash 不一致')
    source_paths = {
        'ddl': root / SOURCE_DIR / '01_create_L_INDVCST_LABEL.sql',
        'code_bool': root / SOURCE_DIR / '03_insert_L_INDVCST_LABEL_CODE_MAP_BOOL.sql',
        'code_option': root / SOURCE_DIR / '04_insert_L_INDVCST_LABEL_CODE_MAP_OPTION.sql',
        'code_branch': root / SOURCE_DIR / '05_insert_L_INDVCST_LABEL_CODE_MAP_BRANCH.sql',
        'fixture': root / SOURCE_DIR / '2000_cust_generate/06_insert_L_INDVCST_LABEL_2000.sql',
        'dictionary': root / SOURCE_DIR / '2000_cust_generate/970字段字典.md',
        'scenario': root / SOURCE_DIR / '2000_cust_generate/业务分析场景完整清单.md',
        'fixture_design': root / SOURCE_DIR / '2000_cust_generate/模拟数据设计方案.md',
        'original_labels': root / 'docs/项目参考文档/个人客户经营标签库结构_脱敏版.md',
        'freeze': root / ARTIFACT_ROOT / 'freeze.jsonl',
        'snapshot': snapshot_path, 'index_manifest': manifest_path,
    }
    sources = {name: {'path': str(path.relative_to(root)), 'sha256': file_hash(path)}
               for name, path in source_paths.items()}
    fields = load_ddl(source_paths['ddl'])
    code_maps = load_code_maps([source_paths[k] for k in ('code_bool','code_option','code_branch')])
    fixture = load_fixture(source_paths['fixture'], fields)
    original = source_names(source_paths['original_labels'])
    declared_null_rates = {}
    for line in source_paths['dictionary'].read_text().splitlines():
        cells = [c.strip() for c in line.split('|')]
        if len(cells)>10 and cells[1].isdigit():
            declared_null_rates[cells[2]]=float(cells[9].rstrip('%'))
    frozen = {r['tag_id']: r for r in read_jsonl(source_paths['freeze']) if r['kind'] == 'tag'}
    live_tags = {t['tag_id']: t for t in database['tags']}
    sem = {t['tag_id']: t for t in snapshot if t['kind'] == 'tag'}
    live_sem = {t['tag_id']: t for t in database['semantics']}
    concepts = {r['concept_id']: r for r in snapshot if r['kind']=='concept'}
    code_rows = [r for r in snapshot if r['kind']=='code_value']
    published_codes = {(r['tag_id'],r['code']): r for r in code_rows}
    current_codes = {(r['field_name'],r['code']):r for r in database['codes']}
    issues, facts = [], []

    def issue(tag_id, code, severity, evidence):
        item = {'issue_id': f'P0-{len(issues)+1:04d}', 'tag_id': tag_id,
                'code': code, 'severity': severity, 'evidence': evidence,
                'status': 'OPEN', 'action': '核实来源并通过复核变更包处理；本次不写业务库'}
        issues.append(item)
        return item['issue_id']

    if set(t['field_name'] for t in live_tags.values()) != set(fields):
        raise ValueError('当前标签字段集合与 DDL 不一致，不能静默继续')
    for tag_id, current in sorted(live_tags.items()):
        if str(current['is_object_key']) == '1':
            continue
        field = current['field_name']
        ddl, old, tag = fields[field], frozen.get(tag_id, {}), sem.get(tag_id, {})
        start = len(issues)
        if not tag:
            issue(tag_id, 'NOT_IN_ACTIVE_SNAPSHOT', 'ERROR', {'field': field})
        if current['status'] != '2' or current['source_status'] != 'AVAILABLE':
            issue(tag_id, 'CURRENT_INELIGIBLE', 'ERROR', {'status':current['status'],'source_status':current['source_status']})
        for attr in ('name','data_type','tag_type','business_caliber','source_fingerprint','confirmed_fingerprint'):
            if str(current.get(attr) or '').lower() != str(old.get(attr) or '').lower():
                issue(tag_id, 'LIVE_FREEZE_DRIFT', 'WARNING', {'field':attr,'freeze':old.get(attr),'live':current.get(attr)})
        if current['data_type'].upper() != ddl['data_type']:
            issue(tag_id, 'DDL_TYPE_MISMATCH', 'ERROR', {'ddl':ddl['data_type'],'current':current['data_type']})
        matches = original.get(normalize_name(ddl['name']), [])
        if not matches:
            issue(tag_id, 'ORIGINAL_NAME_NOT_LOCATED', 'WARNING', {'ddl_name':ddl['name']})
        elif current['tag_type'] not in {m['tag_type'] for m in matches}:
            issue(tag_id, 'BUSINESS_TYPE_MISMATCH', 'ERROR', {'source_types':sorted({m['tag_type'] for m in matches}),'current_type':current['tag_type']})
        caliber = tag.get('caliber_struct') or {}
        stype = tag.get('semantic_type')
        if stype == 'NUM_RATIO' and caliber.get('statistic') == 'COUNT':
            issue(tag_id, 'RATIO_COUNT_CONFLICT', 'ERROR', {'semantic_type':stype,'unit':tag.get('unit'),'caliber':caliber})
        if '最高' in str(tag.get('concept_name')) and '最高' not in current['name']:
            issue(tag_id, 'CONCEPT_MAXIMUM_CONFLICT', 'ERROR', {'name':current['name'],'concept_name':tag.get('concept_name')})
        if stype == 'BOOL' and current['tag_type'] != '布尔型':
            issue(tag_id, 'BUSINESS_SEMANTIC_TYPE_CONFLICT', 'ERROR', {'tag_type':current['tag_type'],'semantic_type':stype})
        unit_expected = {'NUM_AMOUNT':{'CNY'},'NUM_RATIO':{'RATIO'},
                         'NUM_COUNT':{'COUNT','PERSON','DAY','MONTH','SHARE','POINT'},
                         'NUM_SCORE':{'POINT'}}.get(stype)
        if unit_expected and tag.get('unit') not in unit_expected:
            issue(tag_id,'UNIT_TYPE_CONFLICT','ERROR',{'accepted_dimensions':sorted(unit_expected),'actual':tag.get('unit')})
        if caliber.get('unit') != tag.get('unit') or float(caliber.get('unit_scale',1)) != float(tag.get('unit_scale',1)):
            issue(tag_id,'CALIBER_UNIT_CONFLICT','ERROR',{'caliber':caliber,'unit':tag.get('unit')})
        if match:=re.search(r'近(\d+)天',current['name']):
            if caliber.get('time_anchor_type')!='WINDOW' or caliber.get('time_window_unit')!='DAY' or caliber.get('time_window_value')!=int(match[1]):
                issue(tag_id,'TIME_WINDOW_CONFLICT','ERROR',{'name':current['name'],'caliber':caliber})
        if caliber.get('time_anchor_type') in {'WINDOW','MONTH_OFFSET'} and '金额' in current['name'] and caliber.get('statistic')=='EOP':
            issue(tag_id,'PERIOD_AMOUNT_STATISTIC_REVIEW','WARNING',{'name':current['name'],'statistic':'EOP','note':'需要区分期间流量与期末存量，不自动改为SUM'})
        if str(tag.get('unit_scale')) not in {'1','1.0','1.0000'}:
            issue(tag_id,'NONTRIVIAL_UNIT_SCALE','WARNING',{'unit_scale':tag.get('unit_scale')})
        ops = tag.get('allowed_operators')
        if not isinstance(ops,list) or not ops:
            issue(tag_id,'OPERATORS_INVALID','ERROR',{'operators':ops})
        if tag.get('concept_id') not in concepts:
            issue(tag_id,'CONCEPT_REFERENCE_INVALID','ERROR',{'concept_id':tag.get('concept_id')})
        if not current.get('business_caliber'):
            issue(tag_id,'DEFINITION_MISSING','ERROR',{})
        if not current['source_fingerprint'] or current['source_fingerprint'] != current['confirmed_fingerprint']:
            issue(tag_id,'CURRENT_FINGERPRINT_UNCONFIRMED','ERROR',{})
        ls = live_sem.get(tag_id,{})
        for attr in ('semantic_type','unit','caliber_struct','concept_id','review_status','basis_hash'):
            if ls.get(attr) != tag.get(attr):
                issue(tag_id,'LIVE_SEMANTIC_DRIFT','WARNING',{'field':attr,'live':ls.get(attr),'active':tag.get(attr)})
        codes = code_maps.get(field,[])
        for code in codes:
            key = (tag_id,code['code'])
            if key not in published_codes:
                issue(tag_id,'PUBLISHED_CODE_MISSING','ERROR',{'code':code['code']})
            elif published_codes[key].get('definition') != code['definition']:
                issue(tag_id,'PUBLISHED_CODE_MEANING_CONFLICT','ERROR',{'code':code['code'],'source':code['definition'],'published':published_codes[key].get('definition')})
            live_code = current_codes.get((field,code['code']))
            if not live_code or live_code['definition'] != code['definition']:
                issue(tag_id,'LIVE_CODE_SOURCE_CONFLICT','ERROR',{'code':code['code'],'source':code['definition'],'live':live_code})
        if {c['code'] for c in codes} != {r['code'] for r in code_rows if r['tag_id']==tag_id}:
            issue(tag_id,'CODE_SET_MISMATCH','ERROR',{})
        values = [r[field] for r in fixture if r[field] is not None]
        null_rate=100*(len(fixture)-len(values))/len(fixture)
        if field in declared_null_rates and abs(declared_null_rates[field]-null_rate)>0.011:
            issue(tag_id,'FIXTURE_DICTIONARY_DRIFT','WARNING',{'dictionary_null_percent':declared_null_rates[field],'sql_null_percent':round(null_rate,4)})
        evidence_status = 'UNRESOLVED' if any(i['severity']=='ERROR' for i in issues[start:]) else 'VERIFIED_SOURCE'
        facts.append({'fact_id':f'TAG:{tag_id}','tag_id':tag_id,'field_name':field,
                      'name':current['name'],'domain':(tag.get('dir_path') or ['UNKNOWN'])[0],
                      'tag_type':current['tag_type'],'physical_type':ddl['data_type'],'nullable':ddl['nullable'],
                      'source_definition':current['business_caliber'], 'ddl_definition':ddl['name'],
                      'source_evidence':{'ddl_line':ddl['line'],'original_matches':matches,
                                         'ddl_sha256':sources['ddl']['sha256'],
                                         'live_observation_sha256':file_hash(observation)},
                      'source_field_status':{'name':'VERIFIED_SOURCE' if matches else 'UNRESOLVED',
                                             'physical_type':'VERIFIED_SOURCE','code_meanings':'DEMO_CONVENTION' if any(c['status']=='DEMO_CONVENTION' for c in codes) else 'VERIFIED_SOURCE' if codes else 'NOT_APPLICABLE',
                                             'caliber':'UNRESOLVED' if evidence_status=='UNRESOLVED' else 'SOURCE_DESCRIPTION_ONLY'},
                      'fact_status':evidence_status,'official_bank_verified':False,
                      'published_semantics':{k:tag.get(k) for k in ['semantic_type','unit','unit_scale','allowed_operators','caliber_struct','concept_id','concept_name','family_key','definition_long','review_status']},
                      'codes':codes,'issue_ids':[i['issue_id'] for i in issues[start:]],
                      'fixture_coverage':{'rows':len(fixture),'nonnull':len(values),'nulls':len(fixture)-len(values),
                                          'distinct_nonnull':len(set(values)),
                                          'status':'ALL_NULL' if not values else 'CONSTANT' if len(set(values))==1 else 'DISCRIMINATING',
                                          'live_values_verified':False,'java_execution_verified':False}})
    summary = {'library_id':107,'business_tags':len(facts),'object_keys':len(live_tags)-len(facts),
               'source_fields':len(fields),'tag_types':dict(Counter(f['tag_type'] for f in facts)),
               'domains':dict(Counter(f['domain'] for f in facts)),
               'fact_status':dict(Counter(f['fact_status'] for f in facts)),
               'fixture_coverage':dict(Counter(f['fixture_coverage']['status'] for f in facts)),
               'issue_codes':dict(Counter(i['code'] for i in issues)),
               'issue_severity':dict(Counter(i['severity'] for i in issues)),
               'code_fields':len(code_maps),'code_values':sum(map(len,code_maps.values())),
               'snapshot_counts':dict(Counter(r['kind'] for r in snapshot)),
               'aliases':sum(len(r.get('aliases') or []) for r in snapshot),
               'examples':sum(len(r.get('examples') or []) for r in snapshot),
               'confusable_pairs':sum(len(r.get('confusable') or []) for r in snapshot)//2,
               'fixture_rows_parsed':len(fixture),'live_customer_counts':database['customer_counts'],
               'human_bank_signoff':False, 'live_customer_content_verified':False,
               'scope':'P0 inventory complete; unresolved facts remain unresolved'}
    if len(facts)!=969 or len(fields)!=970 or len(fixture)!=2000:
        raise ValueError('当前 P0 契约的分母变化，需要重新制定覆盖计划')
    fresh_directory(output)
    write_jsonl(output/'facts.jsonl',facts)
    write_jsonl(output/'issues.jsonl',issues)
    write_json(output/'summary.json',summary)
    shutil.copyfile(observation,output/'live-observation.json')
    source_dir=output/'sources';source_dir.mkdir()
    # 大型本地工件压缩保存；mtime=0 保证重放确定性，内部不含客户明细。
    for key in ('freeze','snapshot','index_manifest','original_labels'):
        payload=source_paths[key].read_bytes()
        name=key+'.gz'
        (source_dir/name).write_bytes(gzip.compress(payload,mtime=0))
        sources[key]['frozen_copy']='sources/'+name
    repo_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    package={'schema_version':'p0.v1','source_revision':repo_revision,'sources':sources,
             'audit_code_sha256':{name:file_hash(Path(__file__).parent/name) for name in ('inventory.py','sources.py','live.py')},
             'observation_sha256':file_hash(output/'live-observation.json'),
             'active_snapshot':active,'active_build':build,
             'index_verified':live.get('active_index_stats',{}).get('id_reconciled') is True,
             'baseline_manifest':manifest,'reference_date':'2026-09-18','timezone':'Asia/Shanghai',
             'files':{p.name:file_hash(p) for p in output.iterdir() if p.is_file()}}
    write_json(output/'manifest.json',package)
    return summary
