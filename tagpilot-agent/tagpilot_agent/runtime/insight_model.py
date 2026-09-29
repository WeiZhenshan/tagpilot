"""独立洞察画像，一次JSON输出，无工具循环；默认关闭，失败返回模板。"""
import json
import os
import httpx

PROMPTS={
 'narrate':'你是客群洞察文案助手。只能调整cards中的可读文案，输出按skill_id索引的cards数组JSON对象。全部数字必须保留{fact:id}引用；不得改诊断basis、事实引用、行动人数、优先级、基准、适用边界、日期或版本，不得作因果推断。',
 'route':'输出JSON对象skills和parameters。skills只能为asset_structure_profile、product_holding_gap、opportunity_priority；不改变客群条件。歧义输出needs_confirmation=true。',
 'chart_edit':'输出JSON对象classification(view/data/definition)、operation(sort/replace_kind/rerun)、chart_id、parameters。仅视图变化可以直接应用，数据和口径必须确认；不得产生SQL、HTML或ECharts函数，不改Fact数值。'
}
async def structured_once(kind,payload):
    if os.getenv('TAG_INSIGHT_LLM_ENABLED','false').lower()!='true':return None
    base=os.getenv('ANTHROPIC_BASE_URL','');key=os.getenv('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_AUTH_TOKEN') or os.getenv('TAG_LLM_API_KEY','')
    if not base or not key:return None
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r=await client.post(base.rstrip('/')+'/v1/messages',headers={'x-api-key':key,'anthropic-version':'2023-06-01'},json={'model':os.getenv('ANTHROPIC_MODEL') or os.getenv('TAG_LLM_MODEL','deepseek-chat'),'max_tokens':4000,'system':PROMPTS[kind],'messages':[{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]})
            r.raise_for_status();data=r.json();text=''.join(b.get('text','') for b in data.get('content',[]) if b.get('type')=='text')
            value=json.loads(text)
            return value if isinstance(value,dict) else None
    except (httpx.HTTPError,ValueError,KeyError):return None
