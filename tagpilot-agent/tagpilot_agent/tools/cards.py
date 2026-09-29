"""工具观察限制为 UTF-8 6 KiB；完整证据只存 WorkingSet。"""
import json
from copy import deepcopy

def card(t):
    aliases=[a.get('alias_text') for a in t.get('aliases') or [] if a.get('review_status')=='REVIEWED' and a.get('alias_text')]
    return {'tag_id':t['tag_id'],'name':t.get('name'),'def_short':(t.get('definition_long') or '')[:60],
            'reviewed_aliases':list(dict.fromkeys(aliases[:1]+aliases[-7:])),
            **{k:t.get(k) for k in ('semantic_type','unit','family_key','matched_by','code_count')},
            'dir_path':' > '.join(t.get('dir_path') or []),
            'concept_name':t.get('concept_name'),'update_cycle':t.get('update_cycle'),
            'confusable_notes':'；'.join(t.get('confusable_notes') or [])[:200],
            'caliber_short':json.dumps(t.get('caliber_struct') or {},ensure_ascii=False,separators=(',',':'))[:250]}


def observation(data,is_error=False,limit=6144):
    def compact(value,depth=0):
        if isinstance(value,dict):return {k:compact(v,depth+1) for k,v in value.items() if v is not None or depth==0}
        if isinstance(value,list):return [compact(v,depth+1) for v in value]
        return value
    data=compact(deepcopy(data))
    def encode():return json.dumps(data,ensure_ascii=False,separators=(',',':'))
    def lists(obj):
        out=[]
        if isinstance(obj,dict):
            for v in obj.values():out+=lists(v)
        elif isinstance(obj,list):
            if obj:out.append(obj)
            for v in obj:out+=lists(v)
        return out
    def named_lists(obj,names,minimum=0):
        out=[]
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key in names and isinstance(value,list) and len(value)>minimum:out.append(value)
                out+=named_lists(value,names,minimum)
        elif isinstance(obj,list):
            for value in obj:out+=named_lists(value,names,minimum)
        return out
    if len(encode().encode())>limit:
        data['truncated']=True;data['hint']='结果已截断，请缩小查询或使用 value_query'
        while len(encode().encode())>limit:
            # 先裁剪旁证与低排名候选，保留每个请求标签的单位、口径、码值。
            # 不能因为一个标签的族成员很长而直接弹掉整个 tags/results。
            choices=(named_lists(data,{'family_members','examples','concept_candidate_relations','confusable_notes'})
                     or named_lists(data,{'cards'},1)
                     or named_lists(data,{'reviewed_aliases'},1)
                     or named_lists(data,{'code_values'},1)
                     or lists(data))
            if not choices:
                data={'truncated':True,'hint':'结果过大，请缩小查询范围','ok':False};break
            max(choices,key=lambda v:len(json.dumps(v,ensure_ascii=False))).pop()
    return {'content':[{'type':'text','text':encode()}],'is_error':is_error}
