from pathlib import Path
import subprocess,os,json,shutil,re,argparse,time,signal
parser=argparse.ArgumentParser(description='仅在显式隔离目录测试脚本副本，不操作在线服务')
parser.add_argument('--output-dir', required=True, type=Path)
args=parser.parse_args()
base=args.output_dir.resolve()
repo=Path('/workspace/tagpilot').resolve()
if base==repo or repo in base.parents:
 parser.error('输出目录必须位于仓库之外')
base.mkdir(parents=True,exist_ok=True)
source=Path(__file__).resolve().parent;results=[]
stubs={
'npm':'''#!/usr/bin/env python3
import pathlib,sys,os,time
if 'dev' in sys.argv:
 time.sleep(20);sys.exit(0)
if os.environ['PROBE_CASE']=='build_failure':sys.exit(1)
args=sys.argv[1:];p=pathlib.Path(args[args.index('--dest')+1] if '--dest' in args else args[args.index('--outDir')+1]);p.mkdir(parents=True,exist_ok=True);(p/'index.html').write_text('<html>new</html>')
''',
'sudo':'''#!/usr/bin/env python3
import sys,os,pathlib,signal
args=sys.argv[1:];case=os.environ['PROBE_CASE']
p=pathlib.Path(os.environ['PROBE_ROOT'])/'conf/nginx.conf'
new=p.read_text()=='NEW-CONFIG'
if new and any(a.endswith('/conf/nginx.conf') for a in args):
 if case=='config_failure' and '-t' in args:sys.exit(1)
 if case=='reload_failure' and 'reload' in args:sys.exit(1)
 if case=='signal_term' and 'reload' in args:os.kill(os.getppid(),signal.SIGTERM)
sys.exit(0)
''',
'curl':'''#!/usr/bin/env python3
import sys,os
path=next((a for a in sys.argv if a.startswith('http://')), '');case=os.environ['PROBE_CASE']
from urllib.parse import urlsplit
if urlsplit(path).port != 8081:
 import pathlib
 root=pathlib.Path(os.environ['PROBE_ROOT'])
 pidfile='assistant-dev.pid' if '5174' in path else 'vue-cli.pid'
 # 冷启动必须先失败，再由脚本创建本次 PID 文件；覆盖两侧启动分支。
 if not (root/'run'/pidfile).exists():sys.exit(7)
 print('200',end='');sys.exit(0)
if case=='connection_failure':sys.exit(7)
print('404' if path.endswith('/dev-api/v3/api-docs') else '500' if case=='health_500' else '200',end='')
''',
'sleep':'#!/bin/sh\nexit 0\n',
'mv':'''#!/usr/bin/env python3
import sys,os,pathlib
args=sys.argv[1:];target=args[-1];case=os.environ['PROBE_CASE'];sentinel=pathlib.Path(os.environ['PROBE_ROOT'])/'mv-failed'
if not sentinel.exists() and ((case=='link_failure' and target.endswith('/current')) or (case=='previous_failure' and target.endswith('/previous'))):sentinel.touch();sys.exit(1)
os.execv('/usr/bin/mv',['/usr/bin/mv']+args)
'''}

def fixture(label):
 root=base/label
 if root.exists():shutil.rmtree(root)
 for d in ['conf','run','audit','releases/v1/dist','releases/v1/assistant-www/agent-ui','releases/v0','mockbin','code/ruoyi-ui','code/tagpilot-assistant']:(root/d).mkdir(parents=True,exist_ok=True)
 for d in ['dist','assistant-www/agent-ui']:(root/'releases/v1'/d/'index.html').write_text('<html>old</html>')
 (root/'current').symlink_to(root/'releases/v1');(root/'previous').symlink_to(root/'releases/v0')
 (root/'conf/nginx.conf').write_text('OLD-CONFIG');(root/'conf/nginx-prod.conf').write_text('NEW-CONFIG');(root/'conf/nginx-dev.conf').write_text('NEW-CONFIG');(root/'run/nginx.pid').write_text('12345')
 for name in ['deploy-common.sh','switch-to-prod.sh','switch-to-dev.sh','start-prod-frontend.sh']:
  mapping={str(source):str(root),'/workspace/tagpilot-data/frontend-prod':str(root),'/workspace/tagpilot-data/codex-fix-20261006/fix3':str(root/'audit'),'/workspace/tagpilot/ruoyi-ui':str(root/'code/ruoyi-ui'),'/workspace/tagpilot/tagpilot-assistant':str(root/'code/tagpilot-assistant')}
  text=re.sub('|'.join(re.escape(x) for x in mapping),lambda m:mapping[m.group()],(source/name).read_text());assert '/workspace/tagpilot-data/frontend-prod' not in text; (root/name).write_text(text)
 (root/'validate-release.py').write_text((source/'validate-release.py').read_text())
 for n,t in stubs.items():p=root/'mockbin'/n;p.write_text(t);p.chmod(0o700)
 return root

def state(root):return {k:os.readlink(root/k) if (root/k).is_symlink() else None for k in ['current','previous']}|{'config':(root/'conf/nginx.conf').read_text()}
def run(root,script,case):
 env=dict(os.environ,PATH=str(root/'mockbin')+':'+os.environ['PATH'],PROBE_CASE=case,PROBE_ROOT=str(root),TMPDIR=str(base))
 proc=subprocess.run(['bash',str(root/script)],env=env,text=True,capture_output=True,timeout=30)
 (root/(script+'-'+case+'.log')).write_text(proc.stdout+proc.stderr)
 return proc

def cleanup(root):
 for name in ['assistant-dev.pid','vue-cli.pid']:
  p=root/'run'/name
  if p.exists() and p.read_text()!='999999':
   try:os.killpg(int(p.read_text()),signal.SIGTERM)
   except ProcessLookupError:pass

for script in ['switch-to-prod.sh','switch-to-dev.sh','start-prod-frontend.sh']:
 cases=['config_failure','reload_failure','connection_failure','health_500','signal_term']
 if script=='switch-to-prod.sh':cases+=['build_failure','link_failure','previous_failure']
 for case in cases:
  root=fixture(script+'-'+case);before=state(root);proc=run(root,script,case);after=state(root)
  cleanup(root)
  assert proc.returncode!=0 and before==after,(script,case,proc.returncode,before,after)
  results.append({'script':script,'case':case,'exit':proc.returncode,'current_restored':before['current']==after['current'],'previous_restored':before['previous']==after['previous'],'config_restored':before['config']==after['config']})
# 成功冷启动后锁立刻释放，实际长驻假 npm FD 不含 deploy.lock，随即切 prod。
for label,existing in [('cold_dev_then_prod',None),('only_assistant_cold','vue-cli.pid'),('only_vue_cold','assistant-dev.pid')]:
 root=fixture(label)
 if existing:(root/'run'/existing).write_text('999999')
 try:
  proc=run(root,'switch-to-dev.sh','success');assert proc.returncode==0
  lock=str(root/'run/deploy.lock')
  assert subprocess.run(['flock','-n',lock,'true']).returncode==0
  children=[]
  for name in ['assistant-dev.pid','vue-cli.pid']:
   pid=int((root/'run'/name).read_text())
   if pid==999999:continue
   assert (Path('/proc')/str(pid)).exists()
   targets=[]
   for fd in (Path('/proc')/str(pid)/'fd').glob('*'):
    try:targets.append(os.readlink(fd))
    except OSError:pass
   assert lock not in targets;children.append({'pid':pid,'deploy_lock_present':False})
  assert len(children)==(2 if existing is None else 1)
  assert run(root,'switch-to-prod.sh','success').returncode==0
  results.append({'case':label,'dev_exit':0,'next_flock_exit':0,'prod_exit':0,'children':children,'passed':True})
 finally:cleanup(root)
# 原先没有 previous 时，失败不得凭空建立它。
root=fixture('no-previous');(root/'previous').unlink();before=state(root);proc=run(root,'switch-to-prod.sh','health_500');assert before==state(root)
results.append({'case':'absent_previous','restored_absence':True})
# 成功两次、失败一次、手动回切，证明 previous 始终是上一成功版本。
root=fixture('success-success-failure');first=state(root)['current']
assert run(root,'switch-to-prod.sh','success').returncode==0
second=state(root)['current'];assert state(root)['previous']==first
assert run(root,'switch-to-prod.sh','success').returncode==0
third=state(root)['current'];assert state(root)['previous']==second and third!=second
before=state(root);assert run(root,'switch-to-prod.sh','health_500').returncode!=0;assert before==state(root)
(root/'current.next').symlink_to(second);os.replace(root/'current.next',root/'current');assert state(root)['current']==second
results.append({'case':'success_success_failure_manual_rollback','passed':True})
(base/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('Deployment probes passed: '+str(len(results)))
