"""洞察元 Skill：源码包校验、种子 SQL 往返、结果块抽取与端到端运行。"""
import asyncio
import importlib.util
import json
import re
from pathlib import Path

import pytest

from tagpilot_agent.skills.packages import extract_result, materialize
from tests.test_sdk_integration import gateway, manager_for, request_for

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('build_agent_skill_seed', ROOT / 'bin' / 'build-agent-skill-seed.py')
seed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seed)

EXPECTED = {
    'fact-analysis': ('fact', True),
    'diagnostic-analysis': ('diagnosis', True),
    'action-decision': ('decision', True),
    'chart-atomic': ('chart', False),
    'chart-intent': ('chart', False),
    'chart-compose': ('chart', False),
}


@pytest.fixture(scope='module')
def packs():
    return {pack['name']: pack for pack in seed.collect()}


def test_six_meta_skills_are_valid(packs):
    assert set(packs) == set(EXPECTED)
    for name, (category, invocable) in EXPECTED.items():
        pack = packs[name]
        assert pack['category'] == category
        assert pack['user_invocable'] is invocable
        assert pack['disable_model_invocation'] is False
        assert pack['allowed_tools'] == ['Read', 'Skill']
        assert re.fullmatch(r'\d+\.\d+\.\d+', pack['version']), f'{name} 版本号须为三段数字'
        assert pack['resources'], f'{name} 缺少参考资料'
        for resource in pack['resources']:
            assert resource['path'].startswith('references/')
            assert resource['content'].strip()


def test_analysis_skills_share_result_contract(packs):
    for name in ('fact-analysis', 'diagnostic-analysis', 'action-decision'):
        assert 'insight-result' in packs[name]['instructions'], f'{name} 未声明结果块'
    assert 'result-contract' in packs['fact-analysis']['instructions']


def test_chart_skills_teach_guard_rules(packs):
    guard = next(r['content'] for r in packs['chart-atomic']['resources'] if r['path'].endswith('spec-guard.md'))
    for fragment in ('zero_baseline', 'reconcile', 'column', 'sample_size'):
        assert fragment in guard


def test_materialize_real_packs(tmp_path, packs):
    root = materialize(tmp_path, list(packs.values()), 'fact-analysis')
    skill_md = (root / 'fact-analysis' / 'SKILL.md').read_text(encoding='utf-8')
    assert 'name: "fact-analysis"' in skill_md
    assert 'allowed-tools: ["Read", "Skill"]' in skill_md
    assert (root / 'fact-analysis' / 'references' / 'result-contract.md').is_file()
    assert (root / 'chart-atomic' / 'references' / 'spec-guard.md').is_file()
    frontmatter = (root / 'chart-atomic' / 'SKILL.md').read_text(encoding='utf-8').split('---')[1]
    assert 'display-name' not in frontmatter and 'category' not in frontmatter


def test_seed_sql_round_trip(packs):
    sql = seed.build_sql(list(packs.values()))
    literals = re.findall(r"VALUES \('([^']+)', '((?:[^']|'')*)', '((?:[^']|'')*)'", sql)
    assert len(literals) == len(packs)

    def unescape(literal):
        return literal.replace("''", "'").replace('\\\\', '\\')

    seen = set()
    for name, draft, published in literals:
        row = json.loads(unescape(draft))
        assert json.loads(unescape(published)) == row
        assert row['name'] == name and name not in seen
        seen.add(name)
        assert row['instructions'] == packs[name]['instructions']
        assert row['skill_md'].startswith('---\nname: ')
        assert row['skill_md'].endswith('\n')
        assert [r['path'] for r in row['resources']] == [r['path'] for r in packs[name]['resources']]
    assert seen == set(EXPECTED)


def test_extract_result_forms():
    payload = {'status': 'PARTIAL', 'reasons': ['缺少指标'], 'facts': [], 'cards': [], 'charts': [], 'followups': []}
    block = '```insight-result\n' + json.dumps(payload) + '\n```'
    assert extract_result(None) == (None, None)
    assert extract_result('没有结果块') == (None, '没有结果块')
    assert extract_result('```insight-result\n{不是JSON}\n```') == (None, '```insight-result\n{不是JSON}\n```')
    assert extract_result('```insight-result\n[1,2]\n```')[0] is None
    result, text = extract_result('正文一。\n\n' + block)
    assert result == payload and text == '正文一。'
    result, text = extract_result(block + '\n\n结尾说明。')
    assert result == payload and text == '结尾说明。'
    first = '```insight-result\n{"status": "BLOCKED"}\n```'
    result, text = extract_result(first + '\n中间。\n' + block)
    assert result == payload and '中间。' in text and first in text
    huge = '```insight-result\n' + json.dumps({'status': 'PARTIAL', 'reasons': ['x' * 300000]}) + '\n```'
    assert extract_result(huge)[0] is None


def test_skill_run_stores_structured_result(tmp_path, gateway, packs):
    payload = {'status': 'PARTIAL', 'reasons': ['本轮未接入指标数据'], 'facts': [], 'cards': [], 'charts': [], 'followups': ['接入指标后重跑']}
    app = gateway([{'text': '分析正文。\n\n```insight-result\n' + json.dumps(payload, ensure_ascii=False) + '\n```'}])
    store, manager = manager_for(tmp_path)
    request = request_for('meta-skill', profile='skill', skill_name='fact-analysis', skill_packages=list(packs.values()),
                          cohort_context={'name': '合成测试客群', 'revision': 2, 'plan': {'valid': True, 'tree': {'kind': 'SCOPE_ALL'}},
                                          'count': {'value': 240}})
    store.create(request['run_id'], request)
    asyncio.run(manager.execute(request['run_id'], request))
    row = store.get(request['run_id'], '7')
    assert row['status'] == 'COMPLETED', row
    assert row['result']['skill_result'] == payload
    assert row['result']['skill_output'] == '分析正文。'
    assert 'fact-analysis' in json.dumps(app.state.requests, ensure_ascii=False)
    store.db.close()


def test_skill_run_without_block_keeps_text(tmp_path, gateway, packs):
    app = gateway([{'text': '纯文本回答，没有结果块。'}])
    store, manager = manager_for(tmp_path)
    request = request_for('meta-skill-plain', profile='skill', skill_name='fact-analysis', skill_packages=list(packs.values()),
                          cohort_context={'name': '合成测试客群', 'revision': 2, 'plan': {'valid': True, 'tree': {'kind': 'SCOPE_ALL'}},
                                          'count': {'value': 240}})
    store.create(request['run_id'], request)
    asyncio.run(manager.execute(request['run_id'], request))
    row = store.get(request['run_id'], '7')
    assert row['status'] == 'COMPLETED', row
    assert row['result']['skill_output'] == '纯文本回答，没有结果块。'
    assert 'skill_result' not in row['result']
    store.db.close()
