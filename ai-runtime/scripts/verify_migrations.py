"""从本机配置连接 MySQL，仅在随机隔离库验证新增迁移；不更改业务库。"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlparse
import uuid

root = Path(__file__).resolve().parents[2]
config = (root / 'ruoyi-admin/src/main/resources/application-druid.yml').read_text()
master = config.split('master:', 1)[1].split('slave:', 1)[0]

def value(key):
    found = re.search(r'^\s*' + key + r':\s*(.*?)\s*$', master, re.M)
    if not found:
        raise ValueError('配置缺少连接项')
    result = found.group(1).strip('"\'')
    match = re.fullmatch(r'\$\{([^:}]+)(?::([^}]*))?\}', result)
    if match:
        result = os.getenv(match[1], match[2] or '')
    if '\n' in result:
        raise ValueError('配置格式不支持')
    return result

parsed = urlparse(value('url').removeprefix('jdbc:'))
source_database = parsed.path.lstrip('/')
if not re.fullmatch(r'[A-Za-z0-9_]+', source_database):
    raise ValueError('数据库名不合法')
isolated = 'semantic_verify_' + uuid.uuid4().hex[:12]
with tempfile.TemporaryDirectory(prefix='semantic-db-', dir='/private/tmp') as temp:
    defaults = Path(temp) / 'client.cnf'
    def escaped(v):
        return v.replace('\\', '\\\\').replace('"', '\\"')
    defaults.write_text('[client]\nhost="' + escaped(parsed.hostname) + '"\nport=' + str(parsed.port or 3306) + '\nuser="' + escaped(value('username')) + '"\npassword="' + escaped(value('password')) + '"\n')
    defaults.chmod(0o600)
    def sql(statement, database=None):
        args = ['mysql', '--defaults-extra-file=' + str(defaults), '--batch', '--raw', '--skip-column-names']
        if database:
            args.append('--database=' + database)
        result = subprocess.run(args, input=statement, text=True, capture_output=True, check=True)
        return result.stdout
    created = False
    try:
        definitions = [sql('SHOW CREATE TABLE ' + table, source_database).split('\t', 1)[1] for table in ('ts_catalog_snapshot', 'ts_retrieval_feedback', 'sys_menu', 'sys_role_menu')]
        sql('CREATE DATABASE `' + isolated + '` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'); created = True
        for definition in definitions:
            sql(definition, isolated)
        sql('INSERT INTO sys_role_menu(role_id,menu_id) VALUES (999999,2140)', isolated)
        migrations = sorted((root / 'sql/migration').glob('V20260919_*__tag_*.sql'))
        for _ in range(2):
            for migration in migrations:
                sql(migration.read_text(), isolated)
        assert sql("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='ts_catalog_snapshot' AND column_name='file_sha256'", isolated).strip() == '1'
        assert sql('SELECT COUNT(*) FROM sys_menu WHERE menu_id IN (2145,2146)', isolated).strip() == '2'
        assert sql('SELECT COUNT(*) FROM sys_role_menu WHERE role_id=999999 AND menu_id IN (2145,2146)', isolated).strip() == '2'
        sql("INSERT INTO ts_retrieval_feedback(trace_id,user_id,action,decision_key) VALUES ('test',1,'TRACE','test:1:TRACE'),('test',1,'ACCEPT','test:1:DECISION')", isolated)
        duplicate_rejected = False
        try:
            sql("INSERT INTO ts_retrieval_feedback(trace_id,user_id,action,decision_key) VALUES ('test',1,'REPLACE','test:1:DECISION')", isolated)
        except subprocess.CalledProcessError:
            duplicate_rejected = True
        assert duplicate_rejected
        report = {'scope': 'ISOLATED_MYSQL_SCHEMA', 'business_database_modified': False, 'mysql_version': sql('SELECT VERSION()', isolated).strip(),
                  'migrations': [p.name for p in migrations], 'applied_twice': True, 'menu_and_role_idempotence': True, 'duplicate_feedback_rejected': True}
        path = root / 'docs/validation/semantic-migration-report.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        if created:
            sql('DROP DATABASE `' + isolated + '`')
