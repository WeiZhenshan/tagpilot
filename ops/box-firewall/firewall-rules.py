from pathlib import Path
import subprocess,json,re
out=Path('/workspace/tagpilot-data/codex-fix-20261006')
ports=[8080,8091,8092,3306,6379,19529,19530,9091,2379,2380,9000,9001,5174,18081,2375]
base=list(ports)
ss=subprocess.check_output(['ss','-H','-lntp'],text=True)
internal=sorted({int(l.split()[3].rsplit(':',1)[1]) for l in ss.splitlines() if 'milvus' in l})
ports=sorted(set(ports+internal))
addresses=[l.split()[3].split('/')[0] for l in subprocess.check_output(['ip','-o','-4','addr','show','scope','global'],text=True).splitlines()]
def reject(port):return f'-p tcp --dport {port} -j REJECT --reject-with tcp-reset'
def commit(binary,chains,jumps):
 rules=['*filter']
 for chain,entries in chains.items():
  if subprocess.run([binary,'-S',chain],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:rules.append('-N '+chain)
  else:rules.append('-F '+chain) # 内核在 COMMIT 才替换整张表，中间状态从不生效。
  rules += ['-A '+chain+' '+r for r in entries]
 for parent,child in jumps:
  if subprocess.run([binary,'-C',parent,'-j',child],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:rules.append(f'-I {parent} 1 -j {child}')
 rules.append('COMMIT');data='\n'.join(rules)+'\n'
 (out/(binary+'-desired-transaction.rules')).write_text(data)
 subprocess.run([binary+'-restore','--wait','5','--noflush'],input=data,text=True,check=True)
# 不含任何桥网段的 2375 例外：调查未发现依赖。主机 127/8 和 ::1 回连正常。
input_rules=['-i lo -d 127.0.0.0/8 -j RETURN']
input_rules += [f'-i lo -p tcp --dport {p} -j RETURN' for p in internal if p not in base or p==19529]
input_rules += [reject(p) for p in ports]+['-j RETURN']
docker_rules=['-i docker+ -j RETURN','-i br-+ -j RETURN']+[reject(p) for p in ports]+['-j RETURN']
output_rules=[f'-p tcp -m conntrack --ctorigdst {a} --ctorigdstport {p} --ctdir ORIGINAL -j REJECT --reject-with tcp-reset' for a in addresses for p in base if p!=19529]+['-j RETURN']
commit('iptables',{'TAGPILOT-INPUT':input_rules,'TAGPILOT-DOCKER':docker_rules,'TAGPILOT-OUTPUT':output_rules},[('INPUT','TAGPILOT-INPUT'),('DOCKER-USER','TAGPILOT-DOCKER'),('OUTPUT','TAGPILOT-OUTPUT')])
commit('ip6tables',{'TAGPILOT-INPUT':['-i lo -d ::1/128 -j RETURN']+[reject(p) for p in ports]+['-j RETURN']},[('INPUT','TAGPILOT-INPUT')])
for b in ['iptables','ip6tables']:(out/(b+'-after.rules')).write_text(subprocess.check_output([b+'-save'],text=True))
print('Project firewall rules applied atomically; 2375 loopback only')
