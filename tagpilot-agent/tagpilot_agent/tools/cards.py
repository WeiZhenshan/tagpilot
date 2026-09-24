"""工具观察限制为 UTF-8 6 KiB；完整证据只存 WorkingSet。"""
import json
from copy import deepcopy

def card(t):
    return {'tag_id':t['tag_id'],'name':t.get('name'),'def_short':(t.get('definition_long') or '')[:60],
            **{k:t.get(k) for k in ('semantic_type','unit','family_key','matched_by','code_count')},
            'caliber_short':json.dumps(t.get('caliber_struct') or {},ensure_ascii=False,separators=(',',':'))[:250]}


def observation(data,is_error=False,limit=6144):
    data=deepcopy(data)
    def encode():return json.dumps(data,ensure_ascii=False,separators=(',',':'))
    def lists(obj):
        out=[]
        if isinstance(obj,dict):
            for v in obj.values():out+=lists(v)
        elif isinstance(obj,list):
            if obj:out.append(obj)
            for v in obj:out+=lists(v)
        return out
    if len(encode().encode())>limit:
        data['truncated']=True;data['hint']='结果已截断，请缩小查询或使用 value_query'
        while len(encode().encode())>limit:
            choices=lists(data)
            if not choices:
                data={'truncated':True,'hint':'结果过大，请缩小查询范围','ok':False};break
            max(choices,key=lambda v:len(json.dumps(v,ensure_ascii=False))).pop()
    return {'content':[{'type':'text','text':encode()}],'is_error':is_error}
