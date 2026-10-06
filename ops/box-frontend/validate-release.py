from pathlib import Path
import re,sys
r=Path(sys.argv[1])
for base,html,prefix in [(r/'dist',r/'dist/index.html','/'),(r/'assistant-www',r/'assistant-www/agent-ui/index.html','/')]:
    for uri in re.findall(r'(?:src|href)=[\"\']([^\"\']+)',html.read_text()):
        if uri.startswith(('http:','https:','data:','//')): continue
        path=base/uri.split('?')[0].lstrip('/')
        if path.suffix and not path.is_file(): raise SystemExit('missing referenced asset: '+str(path))
print('release assets validated')
