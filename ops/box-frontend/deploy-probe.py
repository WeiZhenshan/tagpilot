from pathlib import Path
import subprocess,os,json,shutil,re
base=Path(__file__).parent/'deploy-probe';base.mkdir(exist_ok=True)
source=Path('/workspace/tagpilot-data/frontend-prod');results=[]
stubs={
'npm':'''#!/usr/bin/env python3
import pathlib,sys,os
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
path=sys.argv[-1];case=os.environ['PROBE_CASE']
if '8081' not in path:sys.exit(0)
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
  mapping={str(source):str(root),'/workspace/tagpilot-data/codex-fix-20261006/fix2':str(root/'audit'),'/workspace/tagpilot/ruoyi-ui':str(root/'code/ruoyi-ui'),'/workspace/tagpilot/tagpilot-assistant':str(root/'code/tagpilot-assistant')}
  text=re.sub('|'.join(re.escape(x) for x in mapping),lambda m:mapping[m.group()],(source/name).read_text());(root/name).write_text(text)
 (root/'validate-release.py').write_text((source/'validate-release.py').read_text())
 for n,t in stubs.items():p=root/'mockbin'/n;p.write_text(t);p.chmod(0o700)
 return root

def state(root):return {k:os.readlink(root/k) if (root/k).is_symlink() else None for k in ['current','previous']}|{'config':(root/'conf/nginx.conf').read_text()}
def run(root,script,case):
 env=dict(os.environ,PATH=str(root/'mockbin')+':'+os.environ['PATH'],PROBE_CASE=case,PROBE_ROOT=str(root),TMPDIR=str(base))
 proc=subprocess.run(['bash',str(root/script)],env=env,text=True,capture_output=True,timeout=30)
 (root/(script+'-'+case+'.log')).write_text(proc.stdout+proc.stderr)
 return proc
for script in ['switch-to-prod.sh','switch-to-dev.sh','start-prod-frontend.sh']:
 cases=['config_failure','reload_failure','connection_failure','health_500','signal_term']
 if script=='switch-to-prod.sh':cases+=['build_failure','link_failure','previous_failure']
 for case in cases:
  root=fixture(script+'-'+case);before=state(root);proc=run(root,script,case);after=state(root)
  assert proc.returncode!=0 and before==after,(script,case,proc.returncode,before,after)
  results.append({'script':script,'case':case,'exit':proc.returncode,'current_restored':before['current']==after['current'],'previous_restored':before['previous']==after['previous'],'config_restored':before['config']==after['config']})
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
