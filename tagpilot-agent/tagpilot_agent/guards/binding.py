"""明确发布名称/等价别名不能绑定成另一个相似字段。仅使用已检索证据。"""
import unicodedata
import re
from .diagnostics import diagnostic
from .plan_validator import leaves


def remove_explicit_enum_assumptions(plan, tags, codes):
    """首轮明写完整字段名和全部码值时，清除模型误加的默认定义假设。

    只处理已校验 BOUND 的枚举叶子，不处理数值阈值、模糊别名或多字段歧义。
    这是用户显式条件，不写成虚假的 CONFIRMED。
    """
    normalize=lambda text:''.join(unicodedata.normalize('NFKC',str(text or '')).lower().split())
    intent=plan.get('intent_plan') or {}
    if not any(a.get('status')=='PUBLISHED' for a in intent.get('assumptions',[])):
        return
    direct=set()
    for node in leaves(plan['tree']):
        tid=node.get('tag_id');tag=tags.get(tid,{})
        if node.get('status')!='BOUND' or not str(tag.get('semantic_type','')).startswith(('ENUM_','BOOL')):
            continue
        if node.get('operator') not in {'=','in'} or not node.get('values'):
            continue
        text=normalize(node.get('source_span'))
        named={candidate for candidate,t in tags.items() if len(normalize(t.get('name')))>=4
               and normalize(t.get('name')) in text}
        if named!={tid}:
            continue
        if any(word in text for word in ('不是','不为','不属于','排除','非正常')):
            continue
        options={str(c['code']):c for c in codes if int(c['tag_id'])==tid}
        def explicit(token):
            token=normalize(token)
            # 数字码不能从日期、金额或其它数字的子串取值。
            boundary=r'(?![a-z0-9.])' if token.isascii() else ''
            return bool(re.search(r'(?:为|是|属于|=)[“"\'「]?'+re.escape(token)+boundary,text))
        if not all(str(v) in options and any(explicit(token) for token in
                   [str(v), options[str(v)].get('label') or str(v)]) for v in node['values']):
            continue
        direct.update((rid,tid) for rid in node.get('requirement_ids',[]))
    intent['assumptions']=[a for a in intent.get('assumptions',[]) if not
        (a.get('status')=='PUBLISHED' and (a.get('requirement_id'),
         (a.get('definition_ref') or {}).get('tag_id')) in direct)]


def check_named_binding(plan,tags):
    normalize=lambda text:''.join(unicodedata.normalize('NFKC',str(text or '')).lower().split())
    errors=[]
    for node in leaves(plan['tree']):
        if node.get('kind','TAG_PREDICATE')!='TAG_PREDICATE' or not node.get('tag_id'):continue
        text=normalize(node.get('source_span'));matches=[]
        for tid,tag in tags.items():
            names=[tag.get('name')]+[a.get('alias_text') for a in tag.get('aliases',[])
                if a.get('review_status')=='REVIEWED' and a.get('alias_type')!='NEGATIVE']
            for name in names:
                word=normalize(name)
                if len(word)>=4 and word in text:matches.append((len(word),int(tid),name))
        if not matches:continue
        longest=max(m[0] for m in matches);best=[m for m in matches if m[0]==longest]
        ids={m[1] for m in best}
        if len(ids)==1 and int(node['tag_id']) not in ids:
            errors.append(diagnostic('BINDING_MISMATCH','原话明确匹配已发布字段，请核对该字段而非沿用相似候选',
                node['clause_id'],expected={'tag_id':best[0][1],'matched_text':best[0][2]},actual=node['tag_id'],
                actions=['get_tag_details','repair_plan']))
    return errors
