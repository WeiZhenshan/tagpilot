"""将发布快照物化为本轮独立的 Claude project skills。"""
import json
import re
from pathlib import Path


RESERVED = {'synced','clear','compact','init','login','logout','config','settings','help','cost','context','exit','quit','model','permissions','add-dir','resume','rewind','mcp','plugin','plugins','agents','skills','memory','status','theme','doctor','feedback','bug','terminal-setup','hooks','output-style','plan'}


RESULT_BLOCK = re.compile(r'```insight-result[ \t]*\r?\n(.*?)```', re.S)
MAX_RESULT_BYTES = 262144


def extract_result(text):
    """抽取技能约定的 insight-result 结果块；缺失或不可解析时返回 (None, 原文)。"""
    if not isinstance(text, str):
        return None, text
    matches = list(RESULT_BLOCK.finditer(text))
    if not matches:
        return None, text
    match = matches[-1]
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None, text
    if not isinstance(data, dict) or len(json.dumps(data, ensure_ascii=False)) > MAX_RESULT_BYTES:
        return None, text
    return data, (text[:match.start()] + text[match.end():]).strip()


def materialize(directory, packages, selected):
    root = Path(directory).resolve() / '.claude' / 'skills'
    names = set()
    for skill in packages:
        name = skill.get('name', '')
        if not isinstance(name,str) or len(name)>64 or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) or name in names:
            raise ValueError('技能名称非法或重复')
        if name in RESERVED or 'anthropic' in name or 'claude' in name:
            raise ValueError('技能名称与平台保留名称冲突')
        names.add(name)
        if not skill.get('description') or not skill.get('instructions'):
            raise ValueError('发布技能缺少描述或指令')
        if set(skill.get('allowed_tools',[]))-{'Read','Skill'}:
            raise ValueError('技能声明了未开放工具')
        if re.search(r'!`[^`]+`',skill['instructions']):
            raise ValueError('不支持命令预处理')
        folder=root/name
        fields={'name':name,'description':skill['description'],'argument-hint':skill.get('argument_hint',''),
                'user-invocable':skill.get('user_invocable',True),
                'disable-model-invocation':skill.get('disable_model_invocation',False),
                'allowed-tools':skill.get('allowed_tools',[])}
        content='---\n'+'\n'.join(f'{key}: {json.dumps(value,ensure_ascii=False)}' for key,value in fields.items())+'\n---\n\n'+skill['instructions']+'\n'
        if re.search(r'!`[^`]+`',content):
            raise ValueError('不支持命令预处理')
        folder.mkdir(parents=True)
        (folder/'SKILL.md').write_text(content,encoding='utf-8')
        seen=set()
        for resource in skill.get('resources',[]):
            path=resource['path']
            if not re.fullmatch(r'(references|scripts|assets)/[A-Za-z0-9_./-]+',path) or '..' in path or '//' in path or path.endswith('/') or path in seen:
                raise ValueError('资源路径非法')
            seen.add(path)
            target=folder/path
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(resource['content'],encoding='utf-8')
    entry=next((s for s in packages if s['name']==selected),None)
    if not entry or not entry.get('user_invocable',True):
        raise ValueError('技能不可手动调用')
    return root


def permitted(name,args,root,packages,selected):
    if name=='Read':
        path=Path(str(args.get('file_path','')))
        if not path.is_absolute():path=root.parent.parent/path
        resolved=path.resolve()
        return resolved.is_file() and resolved.is_relative_to(root)
    if name=='Skill':
        skill=next((s for s in packages if s['name']==args.get('skill')),None)
        return bool(skill and (skill['name']==selected or not skill.get('disable_model_invocation',False)))
    return False
