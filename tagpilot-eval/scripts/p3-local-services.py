"""授权的本机 P3 服务重载；凭据只存在进程环境中，不写产物。"""
import os,signal,subprocess,time,shutil
from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()/'tagpilot-eval'))
from tagpilot_eval.llm import load_config
root=Path.cwd();config=load_config(root)
selected=set(sys.argv[1:] or ['java','semantic','agent'])
env={**os.environ,'TAG_RUNTIME_TOKEN':(root/'.tag-runtime-token').read_text().strip(),
 'TAG_INDEX_DIR':str(root/'tagpilot-semantic/out/full-20260919/indexes'),
 'TAG_SNAPSHOT_DIR':str(root/'tagpilot-semantic/out/full-20260919/snapshots'),
 'TAG_EMBEDDING_PATH':str(root/'tagpilot-semantic/out/models/bge-m3'),
 'TAG_RERANKER_PATH':str(root/'tagpilot-semantic/out/models/bge-reranker-v2-m3'),
 'TAG_RUNTIME_PYTHON':str(root/'tagpilot-semantic/.venv-models/bin/python'),
 'TAG_AGENT_PYTHON':str(root/'tagpilot-agent/.venv/bin/python'),
 'ANTHROPIC_BASE_URL':'https://api.deepseek.com/anthropic',
 'ANTHROPIC_MODEL':config['TAG_LLM_MODEL'],'ANTHROPIC_API_KEY':config['TAG_LLM_API_KEY'],
 'DATABROKER_CRYPTO_SECRET':(root/'.databroker-crypto-secret').read_text().strip(),
 'TAG_LOCAL_DEMO_CURRENT_FREEZE':str(root/'tagpilot-semantic/out/full-20260919/freeze.jsonl'),
 'TAG_LOCAL_DEMO_CURRENT_FREEZE_SHA256':'b9288b16b73182d30f9ec7b16fb05d5cfef8cebfef1804229d1f7eef45e53781'}
for port in [port for name,port in [('java',8080),('semantic',8091),('agent',8092)] if name in selected]:
 r=subprocess.run(['lsof','-tiTCP:'+str(port),'-sTCP:LISTEN'],text=True,capture_output=True)
 for pid in set(r.stdout.split()):os.kill(int(pid),signal.SIGTERM)
time.sleep(3)
if 'java' in selected:shutil.copy2(root/'ruoyi-admin/target/ruoyi-admin.jar',root/'logs/runtime/ruoyi-admin.jar')
java_home=subprocess.check_output(['/usr/libexec/java_home','-v','1.8'],text=True).strip()
for name,cmd in [('java',[java_home+'/bin/java','-jar','logs/runtime/ruoyi-admin.jar']),
 ('semantic',['bash','bin/tag-semantic-runtime.sh']),('agent',['bash','bin/tagpilot-agent.sh'])]:
 if name not in selected:continue
 with (root/'logs'/('p3-'+name+'.log')).open('a') as log:
  p=subprocess.Popen(cmd,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 print(name,p.pid)
