import asyncio
import pytest
from claude_agent_sdk import TextBlock, ToolUseBlock, AssistantMessage, UserMessage
from tagpilot_agent.runtime.narration import clean_narration, NarrationEmitter
from tagpilot_agent.tools.summaries import started_fields, completed_fields
from tagpilot_agent.tools.registry import dispatch
from tests.test_tools import ctx_for

@pytest.mark.parametrize('text', ['先调用 find_tags', '标签 tag_id 123', '核对 R1', '参数 {"x":1}', '执行 SELECT 客户 FROM 表', '核对 clause_id', 'Checking customer metadata now', '标签编号 1073'])
def test_reject_technical_narration(text):
    assert clean_narration(text) is None

def test_business_narration_is_clean_bounded_and_only_before_tools():
    assert clean_narration('**先核对**\n转入统计口径') == '先核对 转入统计口径'
    assert len(clean_narration('核对口径' * 30)) == 60
    ctx = ctx_for(); events = []; ctx.emit = events.append
    text = TextBlock(text='先确认近30天的统计口径')
    tool = ToolUseBlock(id='tool-1', name='mcp__tagpilot__find_tags', input={})
    emitter = NarrationEmitter()
    emitter.consume(ctx, AssistantMessage(content=[text], model="fake"))
    assert events == []
    emitter.consume(ctx, AssistantMessage(content=[tool], model="fake"))
    assert events == [{'type': 'narration', 'text': text.text}]
    ctx.accepted = {'outcome': 'READY'}
    emitter.consume(ctx, AssistantMessage(content=[tool], model="fake"))
    assert len(events) == 1

@pytest.mark.parametrize('name', ['find_tags', 'get_tag_details', 'find_capabilities', 'check_plan', 'submit_result'])
def test_summary_errors_are_business_only(name):
    ctx = ctx_for()
    assert completed_fields(ctx, name, {'ok': False, 'code': 'SCHEMA_INVALID', 'message': 'tag_id R1 SQL'})['summary'] == '本次处理暂未完成，已保留当前进度'
    assert completed_fields(ctx, name, {'ok': False, 'code': 'TOOL_BUDGET'})['summary'] == '正在整理已确认的条件'

def test_normal_and_empty_summaries_and_scope():
    ctx = ctx_for(); ctx.tags = {i: {'name': '标签' + str(i)} for i in range(1, 9)}; ctx.request['eligible_tag_ids'] = list(range(1, 8))
    data = completed_fields(ctx, 'find_tags', {'results': [{'cards': [{'tag_id': i} for i in range(1, 9)]}]})
    assert data['counts']['found'] == 7 and len(data['items']) == 5
    assert all(item['name'] != '标签8' for item in data['items'])
    assert completed_fields(ctx, 'find_tags', {'results': []})['summary'] == '暂未命中，换个说法再试'
    assert completed_fields(ctx, 'get_tag_details', {'tags': [{'tag_id': 1, 'unit': 'CNY', 'code_count': 12, 'caliber_struct': {'time_window_value': 30, 'time_window_unit': 'DAY'}}]})['summary'] == '口径：近30天 · 单位：元 · 12 个取值'
    assert completed_fields(ctx, 'get_tag_details', {'tags': []})['summary'] == '暂未取得可核验的口径'
    assert completed_fields(ctx, 'find_capabilities', {'capabilities': [{}, {}]})['summary'] == '找到 2 项已发布业务定义'
    assert completed_fields(ctx, 'find_capabilities', {'capabilities': []})['summary'] == '暂无相关已发布业务定义'
    assert completed_fields(ctx, 'check_plan', {'ok': False, 'clauses': [{'status_hint': 'BOUND'}], 'diagnostics': [{}]})['summary'] == '1 项条件已核验；还有 1 项待处理'
    assert completed_fields(ctx, 'check_plan', {'ok': True, 'clauses': [], 'diagnostics': []})['summary'] == '0 项条件已核验'
    assert completed_fields(ctx, 'submit_result', {'ok': True})['summary'] == '方案已整理'

def test_parallel_calls_have_distinct_ids_and_matching_completion():
    ctx = ctx_for(); events = []; ctx.emit = events.append
    async def run():
        await asyncio.gather(dispatch(ctx, 'find_tags', {'queries': [{'text': '转入', 'requirement_id': 'R1'}]}), dispatch(ctx, 'find_tags', {'queries': [{'text': '金额', 'requirement_id': 'R2'}]}))
    asyncio.run(run())
    starts = [e for e in events if e['type'] == 'tool.started']; ends = [e for e in events if e['type'] == 'tool.completed']
    assert len({e['call_id'] for e in starts}) == 2
    assert {e['call_id'] for e in starts} == {e['call_id'] for e in ends}
    assert starts[0]['targets'] == ['转入'] and starts[0]['queries'][0]['requirement_id'] == 'R1'
    assert all(e['ok'] and e['duration_ms'] >= 0 and e['summary'] for e in ends)

def test_detail_targets_never_expose_out_of_scope_names():
    ctx = ctx_for(); ctx.tags = {1: {'name': '转入金额'}, 2: {'name': '越权标签'}}
    assert started_fields(ctx, 'get_tag_details', {'tag_ids': [1, 2]})['targets'] == ['转入金额']


def test_final_text_is_discarded_at_turn_boundary():
    ctx = ctx_for(); events = []; ctx.emit = events.append; emitter = NarrationEmitter()
    emitter.consume(ctx, AssistantMessage(content=[TextBlock(text='这是收尾总结')], model='fake'))
    emitter.consume(ctx, UserMessage(content=[]))
    emitter.consume(ctx, AssistantMessage(content=[ToolUseBlock(id='tool-1', name='mcp__tagpilot__check_plan', input={})], model='fake'))
    assert events == []

def test_display_queries_are_business_only_and_detail_references_follow_search():
    from tagpilot_agent.tools.summaries import display_target
    assert display_target('近30天转入累计 SUM') == '近30天转入累计'
    assert display_target('R1 tag_id=123') == '圈选条件'
    ctx = ctx_for()
    asyncio.run(dispatch(ctx, 'find_tags', {'queries': [{'text': '转入', 'requirement_id': 'R1'}]}))
    assert started_fields(ctx, 'get_tag_details', {'tag_ids': [1]})['requirement_ids'] == ['R1']
