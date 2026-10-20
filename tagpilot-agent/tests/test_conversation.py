import asyncio
import json

import pytest
from pydantic import ValidationError
from tagpilot_agent.api.schemas import RunRequest
from tagpilot_agent.tools.analysis import QueryAggregates, dispatch
from tests.test_sdk_integration import gateway, manager_for, request_for


def test_analysis_query_rejects_sql_and_extra_fields():
    with pytest.raises(ValidationError):
        QueryAggregates.model_validate({'queries': [{'id': 'aum', 'operation': 'sum', 'tag_id': 1, 'sql': 'select *'}]})
    with pytest.raises(ValidationError):
        QueryAggregates.model_validate({'queries': [{'id': 'aum', 'operation': 'sum', 'dimensions': [1, 2, 3]}]})


def test_conversation_rejects_incomplete_chart_reference():
    with pytest.raises(ValidationError):
        RunRequest.model_validate(request_for('invalid', profile='conversation', target_artifact_id='a'))


def test_real_sdk_conversation_uses_relay_and_publishes_incremental_blocks(tmp_path, gateway):
    app = gateway([
        [('mcp__insight__route_request', {'intent':'analysis'})],
        [('mcp__insight__get_analysis_context', {})],
        [('mcp__insight__query_aggregates', {'queries': [{'id': 'aum', 'tag_id': 1, 'operation': 'avg'}]})],
        [('mcp__insight__submit_insight_result', {'blocks': [{'type': 'text', 'text': '均值为{fact:f-aum-0}。'}], 'complete': False})],
        [('mcp__insight__submit_insight_result', {'blocks': [{'type': 'chart', 'title': '资产均值', 'query_ids': ['aum'], 'kind': 'kpi'}]})],
    ])
    store, manager = manager_for(tmp_path)
    observed = []

    async def relay(rid):
        cursor = 0
        while rid in manager.contexts or not manager.contexts:
            for event in store.events(rid, cursor):
                cursor = event['seq']
                if event['type'] != 'analysis.request':
                    continue
                observed.append(event)
                result = {'ok': True}
                if event['tool'] == 'query_aggregates':
                    result['bundle'] = {'snapshot_id': 'synthetic-batch', 'facts': [{'id': 'f-aum-0', 'value': 500000, 'unit': '元'}]}
                if event['tool'] == 'submit_insight_result':
                    result.update(parts=event['args']['blocks'], complete=event['args']['complete'])
                manager.analysis_reply(rid, '7', event['request_id'], result)
            if store.get(rid, '7')['status'] != 'RUNNING':
                break
            await asyncio.sleep(.01)

    async def scenario():
        request = request_for('conversation-sdk', profile='conversation', intent='auto', requirement='分析当前客群资产结构')
        store.create(request['run_id'], request)
        task = asyncio.create_task(manager.execute(request['run_id'], request))
        bridge = asyncio.create_task(relay(request['run_id']))
        await asyncio.wait_for(task, 25)
        await asyncio.wait_for(bridge, 2)
        assert manager.active == 0

    asyncio.run(scenario())
    assert store.get('conversation-sdk', '7')['result'] == {'analysis_complete': True}
    assert [e['tool'] for e in observed] == ['get_analysis_context', 'query_aggregates', 'submit_insight_result', 'submit_insight_result']
    assert len(app.state.requests) == 5
    assert {'Read', 'Skill', 'mcp__insight__query_aggregates'} <= {t['name'] for t in app.state.requests[0]['tools']}
    store.db.close()


def test_cancel_releases_pending_relay_and_rejects_late_reply(tmp_path):
    store, manager = manager_for(tmp_path)
    from tagpilot_agent.runtime.run_context import RunContext

    async def scenario():
        request = request_for('cancel-analysis', profile='conversation')
        store.create(request['run_id'], request)
        ctx = RunContext(request, None, lambda e: store.emit(request['run_id'], e), lambda: store.get(request['run_id'], '7')['status'] == 'CANCELLED')
        manager.contexts[request['run_id']] = ctx
        pending = asyncio.create_task(dispatch(ctx, 'get_analysis_context', {}))
        await asyncio.sleep(.01)
        event = next(e for e in store.events(request['run_id']) if e['type'] == 'analysis.request')
        with pytest.raises(ValueError):
            manager.analysis_reply(request['run_id'], 'other-owner', event['request_id'], {'ok': True})
        store.cancel(request['run_id'], '7')
        await manager.cancel(request['run_id'])
        result = await asyncio.wait_for(pending, .5)
        assert json.loads(result['content'][0]['text'])['ok'] is False
        with pytest.raises(ValueError):
            manager.analysis_reply(request['run_id'], '7', event['request_id'], {'ok': True})
    asyncio.run(scenario())
    store.db.close()


def test_hybrid_ready_selection_continues_into_java_analysis_context():
    from tagpilot_agent.runtime.run_context import RunContext
    from tagpilot_agent.tools.registry import dispatch as domain_dispatch
    from tests.test_sdk_smoke import Evidence
    from tests.test_sdk_integration import PLAN

    async def scenario():
        request=request_for('hybrid-selection',profile='conversation',requirement='转入超过50万，并分析资产')
        ctx=RunContext(request,Evidence());ctx.conversation_intent='audience_then_analysis'
        requests=[]
        def emitted(event):
            if event['type']=='analysis.request':
                requests.append(event)
                asyncio.get_running_loop().call_soon(ctx.analysis_pending[event['request_id']].set_result,{'ok':True,'scope_ready':True})
        ctx.emit=emitted
        await domain_dispatch(ctx,'find_tags',{'queries':[{'text':'转入金额','requirement_id':'a'}],'depth':'deep'})
        await domain_dispatch(ctx,'get_tag_details',{'tag_ids':[1]})
        result=await domain_dispatch(ctx,'submit_result',{'outcome':'READY','plan':PLAN,'summary':'已核验范围'})
        assert json.loads(result['content'][0]['text'])['ok'] is True
        assert ctx.accepted is None and not ctx.submitted.is_set()
        assert requests[0]['tool']=='get_analysis_context' and requests[0]['args']['scope']=='selection'
        assert requests[0]['args']['plan']['valid'] is True
    asyncio.run(scenario())
