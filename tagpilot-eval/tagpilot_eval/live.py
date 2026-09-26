"""P0 本机只读观测。固定 SQL、只读事务；不导出客户或连接凭据。"""
import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .io import write_json


def collect(root):
    # 凭据只在进程内交给 mysql，禁止记录配置内容或进程环境。
    import yaml
    config = yaml.safe_load((root / 'ruoyi-admin/src/main/resources/application-druid.yml').read_text())
    master = config['spring']['datasource']['druid']['master']
    address = urlparse(master['url'].removeprefix('jdbc:'))
    if address.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('P0 自动观测仅允许本机数据库')
    db = address.path.strip('/')
    if not re.fullmatch(r'[a-zA-Z0-9_]+', db):
        raise ValueError('数据库标识非法')
    selects = {
        'snapshots': "SELECT JSON_OBJECT('snapshot_id',snapshot_id,'status',status,'tag_count',tag_count,'content_hash',content_hash,'file_sha256',file_sha256,'storage_uri',storage_uri,'schema_version',schema_version) FROM ts_catalog_snapshot WHERE library_id=107 ORDER BY snapshot_no",
        'builds': "SELECT JSON_OBJECT('build_id',b.build_id,'snapshot_id',b.snapshot_id,'status',b.status,'artifact_hash',b.artifact_hash,'artifact_uri',b.artifact_uri,'embedding_model',b.embedding_model,'reranker_model',b.reranker_model,'doc_count',b.doc_count,'eval_summary',b.eval_summary) FROM ts_index_build b JOIN ts_catalog_snapshot s ON s.snapshot_id=b.snapshot_id WHERE s.library_id=107 ORDER BY b.build_id",
        'tags': "SELECT JSON_OBJECT('tag_id',tag_id,'field_name',field_name,'name',tag_name,'data_type',data_type,'tag_type',tag_type,'is_object_key',is_object_key,'business_caliber',business_caliber,'status',status,'source_status',source_status,'source_fingerprint',source_fingerprint,'confirmed_fingerprint',confirmed_fingerprint,'version',version) FROM tl_tag WHERE library_id=107 AND del_flag='0' ORDER BY tag_id",
        'semantics': "SELECT JSON_OBJECT('tag_id',s.tag_id,'semantic_type',s.semantic_type,'unit',s.unit,'unit_scale',s.unit_scale,'allowed_operators',s.allowed_operators,'caliber_struct',s.caliber_struct,'concept_id',s.concept_id,'review_status',s.review_status,'semantic_version',s.semantic_version,'basis_hash',s.basis_hash) FROM ts_tag_semantic s JOIN tl_tag t ON t.tag_id=s.tag_id WHERE t.library_id=107 AND t.del_flag='0' ORDER BY s.tag_id",
        'codes': "SELECT JSON_OBJECT('field_name',tag_name_en,'code',tag_code,'definition',code_definition) FROM indiv_cust.L_INDVCST_LABEL_CODE_MAP ORDER BY tag_name_en,tag_code",
        'capabilities': "SELECT JSON_OBJECT('capability_id',capability_id,'version',version,'review_status',review_status) FROM ts_agent_capability WHERE library_id=107 ORDER BY capability_id,version",
        'customer_counts': "SELECT JSON_OBJECT('all_rows',COUNT(*),'fixture_rows',SUM(CUST_ID LIKE 'SIM20260918%')) FROM indiv_cust.L_INDVCST_LABEL",
    }
    statements = ['SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ',
                  'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY']
    for key, query in selects.items():
        statements.extend(["SELECT 'SECTION:" + key + "'", query])
    statements.append('COMMIT')
    env = dict(os.environ, MYSQL_PWD=str(master['password']))
    result = subprocess.run(['mysql', '--protocol=TCP', '-h', address.hostname,
                             '-P', str(address.port or 3306), '-u', master['username'],
                             '--connect-timeout=5', '--batch', '--raw', '--skip-column-names',
                             '--default-character-set=utf8mb4', db],
                            input=';\n'.join(statements)+';', text=True, capture_output=True,
                            env=env, timeout=45)
    if result.returncode:
        # 不输出配置、SQL 原始响应或未审查的服务器错误。
        raise RuntimeError('只读数据库观测失败；检查本机连接与 SELECT 权限')
    report = {'observed_at': datetime.now(timezone.utc).isoformat(),
              'status': 'OBSERVED_READ_ONLY', 'library_id': 107,
              'consistency': 'repeatable_read_consistent_snapshot_read_only', 'database': {}}
    section = None
    for line in result.stdout.splitlines():
        if line.startswith('SECTION:'):
            section = line[8:]
            report['database'][section] = []
        elif line.strip():
            report['database'][section].append(json.loads(line))
    report['services'] = {}
    for name, port in [('semantic', 8091), ('agent', 8092)]:
        try:
            with urlopen(f'http://127.0.0.1:{port}/health', timeout=5) as response:
                report['services'][name] = json.load(response)
        except Exception:
            report['services'][name] = {'status': 'UNAVAILABLE'}
    active = [b for b in report['database']['builds'] if b['status'] == 'ACTIVE']
    if len(active) == 1:
        secret_file = root / '.tag-runtime-token'
        if secret_file.exists():
            request = Request('http://127.0.0.1:8091/stats?build_id=' + active[0]['build_id'],
                              headers={'Authorization': 'Bearer ' + secret_file.read_text().strip()})
            try:
                with urlopen(request, timeout=30) as response:
                    report['active_index_stats'] = json.load(response)
            except Exception:
                report['active_index_stats'] = {'status': 'UNVERIFIED'}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('禁止覆盖历史观测')
    result = collect(args.root.resolve())
    write_json(args.output, result)
    print(json.dumps({'status': result['status'],
                      'tags': len(result['database']['tags']),
                      'active_builds': [b['build_id'] for b in result['database']['builds'] if b['status']=='ACTIVE']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
