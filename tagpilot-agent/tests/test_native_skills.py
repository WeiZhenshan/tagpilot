import asyncio
import json
import pytest
from tagpilot_agent.skills.packages import materialize, permitted
from tests.test_sdk_integration import gateway, manager_for, request_for


def skill(name='test-analysis', **changes):
    return dict(name=name,display_name='测试分析',description='仅供自动化测试的分析技能',instructions='读取参考资料，依据当前客群条件和有效人数作答，数据缺失时明确说明。',
                version='1.0.0',argument_hint='',user_invocable=True,disable_model_invocation=False,allowed_tools=['Read','Skill'],
                resources=[{'path':'references/guide.md','content':'仅使用上下文已有事实。'}],**changes)


def test_materialization_and_permissions(tmp_path):
    packages=[skill(),{**skill('test-chart'),'disable_model_invocation':True}]
    root=materialize(tmp_path,packages,'test-analysis')
    content=(root/'test-analysis/SKILL.md').read_text()
    assert 'name: "test-analysis"' in content and 'user-invocable: true' in content
    assert permitted('Read',{'file_path':str(root/'test-analysis/references/guide.md')},root,packages,'test-analysis')
    assert not permitted('Read',{'file_path':'/etc/passwd'},root,packages,'test-analysis')
    assert not permitted('Skill',{'skill':'test-chart'},root,packages,'test-analysis')
    assert not permitted('Bash',{'command':'pwd'},root,packages,'test-analysis')
    assert not permitted('Skill',{'skill':'unpublished'},root,packages,'test-analysis')
    (root/'test-analysis/references/link').symlink_to('/etc/passwd')
    assert not permitted('Read',{'file_path':str(root/'test-analysis/references/link')},root,packages,'test-analysis')


@pytest.mark.parametrize('resource',['references/../../secret','scripts/a/../secret','assets//a','assets/a/'])
def test_resource_traversal_rejected(tmp_path,resource):
    package=skill();package['resources']=[{'path':resource,'content':'test'}]
    with pytest.raises(ValueError):materialize(tmp_path,[package],'test-analysis')


@pytest.mark.parametrize('name',['clear','init','synced','anthropic-skills','claude-helper'])
def test_reserved_commands_cannot_be_registered(tmp_path,name):
    with pytest.raises(ValueError):materialize(tmp_path,[skill(name)],name)


def test_preprocessing_and_unpublished_rejected(tmp_path):
    for field in ['instructions','description','argument_hint']:
        package=skill();package[field]='!`cat /etc/passwd`'
        with pytest.raises(ValueError):materialize(tmp_path,[package],'test-analysis')
    with pytest.raises(ValueError):materialize(tmp_path,[skill()],'missing')


def test_native_sdk_loads_skills_and_composes_chart_without_model_or_business_calls(tmp_path,gateway):
    app=gateway([[('Skill',{'skill':'test-chart'})],{'text':'测试分析完成：当前客群240人，无指标数据，不能生成事实图表。'}])
    store,manager=manager_for(tmp_path)
    request=request_for('native-skills',profile='skill',skill_name='test-analysis',skill_packages=[skill(),skill('test-chart')],
                        cohort_context={'name':'合成测试客群','revision':2,'plan':{'valid':True,'tree':{'kind':'SCOPE_ALL'}},'count':{'value':240}})
    store.create(request['run_id'],request)
    asyncio.run(manager.execute(request['run_id'],request))
    row=store.get(request['run_id'],'7')
    assert row['status']=='COMPLETED',row
    assert '240人' in row['result']['skill_output']
    assert 'plan' not in row['result']
    calls=json.dumps(app.state.requests,ensure_ascii=False)
    assert 'test-analysis' in calls and 'test-chart' in calls and '合成测试客群' in calls
    assert {t['name'] for t in app.state.requests[0]['tools']}=={'Read','Skill'}
    assert any(e['type']=='skill.invoked' for e in store.events(request['run_id']))
    store.db.close()
