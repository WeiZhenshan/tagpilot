"""意图 → 有界证据探索 → 表达式规划 → 修复/业务澄清；执行始终由 Java 掌握。"""
from __future__ import annotations
import copy
import hashlib
import json
import os
import time
from typing import TypedDict
import openai
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from .plan import leaves, validate_plan
from .intent import capture_intent, check_coverage, transition_errors
from .expressions import plan_tag_ids
from .diagnostics import diagnostic, from_error, plan_status
from .planner_prompt import INSTRUCTION


class State(TypedDict, total=False):
    request: dict
    plan: dict
    intent: dict
    tags: dict
    codes: list
    capabilities: dict
    evidence: list
    attempts: dict
    calls: int
    repairs: int
    action: dict
    questions: list
    answer: str
    done: bool
    cache: dict
    manual_edit: bool
    no_progress: int
    budget: int
    started_at: float
    terminal: bool
    repair_history: list
    authority_repairs: int


class Planner:
    def __init__(self):
        self.url = os.getenv('TAG_LLM_BASE_URL', '').rstrip('/')
        self.model = os.getenv('TAG_LLM_MODEL', '')
        # 兼容端点可能免鉴权；openai SDK 拒绝空密钥，占位符不影响此类端点。
        self.client = (ChatOpenAI(model_name=self.model, openai_api_base=self.url + '/v1',
            openai_api_key=os.getenv('TAG_LLM_API_KEY', '') or 'EMPTY',
            temperature=0, request_timeout=60, max_retries=0, use_responses_api=False,
            model_kwargs={'response_format': {'type': 'json_object'}})
            if self.url and self.model else None)

    def decide(self, context):
        if not self.client:
            raise ValueError('尚未配置模型，请配置 TAG_LLM_BASE_URL 和 TAG_LLM_MODEL')
        messages = [SystemMessage(content=INSTRUCTION), HumanMessage(content=json.dumps(context, ensure_ascii=False))]
        for attempt in range(2):
            try:
                content = self.client.invoke(messages).content
            except openai.APIConnectionError:
                if attempt == 0:
                    continue
                raise
            except openai.APIStatusError as exc:
                if attempt == 0 and exc.response.status_code in {429, 502, 503, 504}:
                    time.sleep(.5)
                    continue
                raise
            try:
                result = json.loads(content)
                if isinstance(result, dict):
                    result['action'] = str(result.get('action') or '').lower()
                    if result['action'] in {'plan', 'replan', 'finish'}:
                        candidate = result.get('plan')
                        if not isinstance(candidate, dict):
                            raise ValueError('plan 必须是对象')
                        leaves(candidate.get('tree'))
                    if result.get('action') in {'plan', 'tool', 'replan', 'finish', 'ask'}:
                        return result
            except (ValueError, TypeError, AttributeError) as exc:
                messages.append(AIMessage(content=content[:20000]))
                messages.append(HumanMessage(content='格式错误：'+str(exc)+'。plan.tree 必须是条件树对象，每个叶子都须有 clause_id；组须有 logic 和 children。修正后输出完整 JSON。'))
            messages.append(HumanMessage(content='上次输出不是合法行动 JSON，请仅输出一个 action=plan/tool/replan/finish/ask 的 JSON 对象。'))
        raise ValueError('模型输出格式暂未修复，已保留运行状态')


def normalize_plan(plan):
    if plan.get('tree'):
        for node in leaves(plan['tree']):
            aliases = {'EQ':'=', 'NE':'!=', 'GT':'>', 'GTE':'>=', 'GE':'>=', 'LT':'<', 'LTE':'<=', 'LE':'<=', 'IN':'in', 'NOT_IN':'not_in', 'BETWEEN':'between', 'IS_NULL':'is_null', 'IS_NOT_NULL':'is_not_null'}
            node['operator'] = aliases.get(node.get('operator'), node.get('operator'))
            value = node.get('time_constraint')
            if isinstance(value, dict):
                node['expected_caliber'] = node.get('expected_caliber') or value.get('expected_caliber') or {}
                node['time_constraint'] = str(value.get('raw') or value.get('label') or '')
    return plan


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()



def inherit_evidence(nodes, prior_nodes):
    """新执行树继承旧树的检索候选与证据引用；模型回传的重组/终版树不带这些系统字段。"""
    old = {n['clause_id']: n for n in prior_nodes}
    for node in nodes:
        refs = set(node.get('requirement_ids') or [node['clause_id']])
        related = [n for n in prior_nodes if refs & set(n.get('requirement_ids') or [n['clause_id']])]
        candidates = {int(c['tag_id']): c for n in related for c in n.get('candidates', [])}
        for n in related:
            if n.get('tag_id') and n.get('status') == 'BOUND':
                candidates[int(n['tag_id'])] = {'tag_id': n['tag_id'], 'name': n.get('name')}
        prior = old.get(node['clause_id'], {})
        for key in ('source_span', 'evidence_id'):
            if key in prior:
                node[key] = prior[key]
        node['candidates'] = list(candidates.values())



def compact_evidence(events):
    """保留绑定所需证据；不把向量分数、别名索引和长画像重复发送给模型。"""
    fields = {'tag_id', 'name', 'semantic_type', 'definition_long', 'caliber_struct', 'unit', 'unit_scale',
              'grain', 'allowed_operators', 'semantic_tags', 'value_source_type'}
    result = []
    for event in events:
        data = event['result']; context = data.get('selection_context', data)
        result.append({'tool': event['tool'], 'clause_id': event['clause_id'], 'result': {
            'tags': [{k: v for k, v in tag.items() if k in fields} for tag in context.get('tags', [])],
            'code_values': [{k: v for k, v in code.items() if k in {'tag_id','code','label','definition','is_unknown_bucket'}} for code in context.get('code_values', [])],
            'capabilities': data.get('capabilities', []), 'terms': data.get('terms', []),
            'diagnostic': data.get('diagnostic')}})
    return result

def build_workbench(retriever, saver, emit, cancelled, planner=None):
    planner = planner or Planner()

    def guard():
        if cancelled():
            raise InterruptedError('用户已停止运行')

    def merge_evidence(state, data):
        req = state['request']
        for field in ('build_id', 'snapshot_id', 'artifact_hash'):
            if req.get(field) and data.get(field) != req[field]:
                raise ValueError('发布证据版本不一致')
        tags = dict(state.get('tags', {}))
        context = data.get('selection_context', data)
        for tag in context.get('tags', []):
            if int(tag['tag_id']) not in req['eligible_tag_ids']:
                raise ValueError('证据引用资格外标签')
            tags[str(tag['tag_id'])] = tag
        codes = {(str(c['tag_id']), str(c['code'])): c for c in state.get('codes', [])}
        codes.update({(str(c['tag_id']), str(c['code'])): c for c in context.get('code_values', [])})
        return tags, list(codes.values())

    def stop(state, code, message):
        plan = copy.deepcopy(state.get('plan', {}))
        errors = list(plan.get('diagnostics', [])) + [diagnostic(code, message)]
        plan.update(valid=False, diagnostics=errors, validation_errors=errors, plan_status=plan_status(errors))
        emit({'type': 'plan.validated', 'plan': plan, 'message': message})
        return {'plan': plan, 'terminal': True, 'action': {'action': 'stop'}, 'questions': []}

    def start(state):
        guard()
        req = state['request']
        emit({'type': 'plan.updated', 'steps': [{'id': 'understand', 'label': '理解业务要求', 'status': 'running'},
              {'id': 'bind', 'label': '查找可用指标与计算能力', 'status': 'pending'}, {'id': 'validate', 'label': '核验并修复方案', 'status': 'pending'}]})
        previous = copy.deepcopy(req.get('previous_plan') or {})
        if req.get('edited_plan'):
            plan = copy.deepcopy(req['edited_plan'])
            # 显式编辑形成新的业务版本，不用旧覆盖集合阻止用户删除条件。
            plan.pop('intent_plan', None)
        else:
            action = planner.decide({'phase': 'understand', 'requirement': req['requirement'], 'previous_plan': previous,
                                     'history': req.get('history', [])[-12:]})
            plan = action.get('plan') or {}
            if not plan.get('tree'):
                return {'plan': {}, 'questions': action.get('questions') or [{'prompt': '希望找哪些客户？可以直接描述业务目标。'}],
                        'action': {'action': 'ask'}, 'calls': 0, 'repairs': 0, 'tags': {}, 'codes': [], 'capabilities': {},
                        'evidence': [], 'attempts': {}, 'cache': {}, 'terminal': False, 'no_progress': 0,
                        'budget': 12, 'started_at': time.time(), 'intent': {}, 'repair_history': []}
        if previous.get('tree') and not req.get('edited_plan'):
            errors = transition_errors(previous, plan, req['requirement'])
            if errors:
                action = planner.decide({'phase':'understand', 'requirement':req['requirement'],
                    'previous_plan':previous, 'proposed_plan':plan, 'validation_errors':errors})
                plan = action.get('plan') or previous
                errors = transition_errors(previous, plan, req['requirement'])
                if errors:
                    result = stop({'plan':previous}, 'INTENT_COVERAGE', '已保留原方案，本轮改写遗漏了旧条件，尚未应用')
                    result['plan']['unapplied_request'] = req['requirement']
                    return result
        plan = normalize_plan(plan)
        intent = capture_intent(plan, req['requirement'])
        plan.update(intent_plan=intent, schema_version=3, plan_status='DRAFT', valid=False)
        budget = min(int(os.getenv('TAG_AGENT_MAX_TOOL_CALLS', '36')), max(12, len(leaves(plan['tree'])) * 4 + 4))
        emit({'type': 'intent.ready', 'plan': plan, 'message': '已整理业务要求，将核对指标与计算方式'})
        return {'plan': plan, 'intent': intent, 'calls': 0, 'budget': budget, 'started_at': time.time(),
                'repairs': 0, 'tags': {}, 'codes': [], 'capabilities': {}, 'evidence': [], 'attempts': {},
                'cache': {}, 'no_progress': 0, 'terminal': False, 'repair_history': [],
                'action': {'action': 'finish' if req.get('edited_plan') else 'continue'}}

    def decide(state):
        guard()
        if state['calls'] >= state['budget'] or time.time() - state['started_at'] > int(os.getenv('TAG_AGENT_MAX_SECONDS', '240')):
            return stop(state, 'BUDGET_EXHAUSTED', '本轮处理额度已用完，已保留需求和已找到的证据。可以稍后继续。')
        if state.get('no_progress', 0) >= 3:
            code = 'CAPABILITY_UNAVAILABLE' if not state.get('tags') else 'BINDING_MISMATCH'
            return stop(state, code, '现有证据尚不足以完成全部条件，已保留方案和具体缺口。')
        for node in leaves(state['plan']['tree']) if state['plan'].get('tree') else []:
            if node.get('kind') == 'SCOPE_ALL':
                continue
            if not state.get('attempts', {}).get(node['clause_id']) and not node.get('candidates'):
                return {'action': {'action': 'tool', 'tool': 'search_tags', 'clause_id': node['clause_id'],
                                   'query': node.get('query') or node.get('source_span')}, 'questions': []}
        action = planner.decide({'phase': 'bind', 'requirement': state['request']['requirement'],
            'plan': state['plan'], 'intent_plan': state['intent'], 'answer': state.get('answer'),
            'evidence': compact_evidence(state.get('evidence', [])[-24:]), 'remaining_calls': state['budget']-state['calls'],
            'validation_errors': state['plan'].get('validation_errors', []), 'repair_history': state.get('repair_history', [])})
        if action.get('action') == 'plan':
            action['action'] = 'finish'
        return {'action': action, 'questions': action.get('questions') or []}

    def replan(state):
        guard()
        try:
            plan = normalize_plan(copy.deepcopy(state['action'].get('plan') or state['plan']))
            errors = check_coverage(state['intent'], leaves(plan['tree']), plan['tree'])
        except (ValueError, KeyError, TypeError) as exc:
            plan = copy.deepcopy(state['plan']); errors = [from_error(exc)]
        if errors:
            plan = copy.deepcopy(state['plan'])
            plan.update(diagnostics=errors, validation_errors=errors)
            return {'plan': plan, 'no_progress': state.get('no_progress', 0)+1}
        inherit_evidence(leaves(plan['tree']), leaves(state['plan']['tree']) if state['plan'].get('tree') else [])
        plan.update(intent_plan=state['intent'], valid=False, schema_version=3, plan_status='DRAFT')
        same = fingerprint(plan.get('tree')) == fingerprint(state['plan'].get('tree'))
        emit({'type': 'plan.restructured', 'plan': plan, 'message': '已保留业务要求，调整指标组合与计算路径'})
        return {'plan': plan, 'calls': state['calls']+1, 'no_progress': state.get('no_progress', 0)+1 if same else 0}

    def tool(state):
        guard()
        action = state['action']; name = action.get('tool'); cid = action.get('clause_id')
        plan = copy.deepcopy(state['plan']); nodes = leaves(plan['tree'])
        node = next((n for n in nodes if n['clause_id'] == cid), None)
        if not node:
            matches = [n for n in nodes if cid in n.get('requirement_ids', [])]
            node = matches[0] if len(matches) == 1 else nodes[0] if len(nodes) == 1 else None
            if node:
                cid = node['clause_id']
            else:
                errors = [diagnostic('FORMAT_ERROR', '工具需引用现有 clause_id', actual=[n['clause_id'] for n in nodes], actions=['repair_plan'])]
                plan.update(valid=False, diagnostics=errors, validation_errors=errors, plan_status='DRAFT')
                return {'plan': plan, 'calls': state['calls']+1, 'no_progress': state.get('no_progress', 0)+1}
        query = str(action.get('query') or node.get('query') or node.get('source_span') or '')[:500]
        req = state['request']; eligible = set(req['eligible_tag_ids'])
        attempts = dict(state.get('attempts', {})); cache = dict(state.get('cache', {}))
        key = fingerprint([name, query, sorted(action.get('tag_ids') or []), action.get('capability_ids'), req['build_id'], sorted(eligible)])
        emit({'type': 'tool.started', 'tool': name, 'clause_id': cid, 'message': '正在核对：' + query})
        cached = key in cache
        if cached:
            data = cache[key]
        elif name == 'search_tags':
            if attempts.get(cid, 0) >= int(os.getenv('TAG_AGENT_SEARCHES_PER_CLAUSE', '6')):
                data = {'diagnostic': '该条件的标签检索已无进展，请检查派生或聚合能力'}
            else:
                data = retriever.retrieve(query, eligible, 12)
                data.pop('catalog', None)
                attempts[cid] = attempts.get(cid, 0) + 1
        elif name in {'get_tag_details', 'resolve_tag_values', 'resolve_business_term'}:
            ids = [int(v) for v in action.get('tag_ids', [])]
            if not set(ids) <= eligible:
                raise ValueError('工具请求资格外标签')
            data = retriever.evidence(ids, query, eligible)
        elif name in {'search_capabilities', 'get_capability_details', 'resolve_business_definition'}:
            data = retriever.capabilities(query, eligible, action.get('capability_ids') or [])
        else:
            data = {'diagnostic': '工具不可用，请使用已登记工具'}
        cache[key] = data
        # 每个工具结果都可以向本业务要求贡献可引用输入；资格和快照重新检查。
        tags, codes = merge_evidence(state, data) if 'build_id' in data else (state.get('tags', {}), state.get('codes', []))
        context = data.get('selection_context', data)
        candidates = data.get('candidates', []) or [{'tag_id': t['tag_id'], 'name': t['name']} for t in context.get('tags', [])]
        prior_candidate_ids = {int(c['tag_id']) for c in node.get('candidates', [])}
        new_to_clause = bool({int(c['tag_id']) for c in candidates} - prior_candidate_ids)
        node['candidates'] = list({c['tag_id']: c for c in [*node.get('candidates', []), *candidates]}.values())
        node['evidence_id'] = data.get('trace_id') or fingerprint(data)[:16]
        capabilities = dict(state.get('capabilities', {}))
        for cap in data.get('capabilities') or []:
            if not set(cap.get('input_tag_ids') or []) <= eligible:
                raise ValueError('能力依赖不在当前资格范围')
            capabilities[cap['capability_id']] = cap
        # 证据内容相同即无进展，随机 trace_id 不参与判断。
        progress_value = {k: v for k, v in data.items() if k not in {'trace_id', 'rank_features'}}
        previous_values = [{k: v for k, v in e['result'].items() if k not in {'trace_id', 'rank_features'}} for e in state.get('evidence', [])]
        progress = new_to_clause or (bool(candidates or data.get('capabilities') or data.get('terms')) and fingerprint(progress_value) not in {fingerprint(v) for v in previous_values})
        emit({'type': 'tool.completed', 'tool': name, 'clause_id': cid, 'message': '已取得证据' if progress else '本次没有新增证据',
              'candidates': candidates, 'evidence_id': node['evidence_id']})
        return {'plan': plan, 'calls': state['calls']+(0 if cached else 1), 'tags': tags, 'codes': codes,
                'capabilities': capabilities, 'cache': cache, 'attempts': attempts,
                'no_progress': 0 if progress else state.get('no_progress', 0)+1,
                'evidence': [*state.get('evidence', []), {'tool': name, 'clause_id': cid, 'result': data}]}

    def validate(state):
        guard()
        prior_nodes = leaves(state['plan']['tree']) if state['plan'].get('tree') else []
        try:
            plan = normalize_plan(copy.deepcopy(state['action'].get('plan') or state['plan']))
            nodes = leaves(plan['tree'])
        except (ValueError, KeyError, TypeError) as exc:
            plan = copy.deepcopy(state['plan'])
            err = from_error(exc)
            plan.update(valid=False, diagnostics=[err], validation_errors=[err], plan_status='DRAFT')
            return {'plan': plan, 'done': False, 'repairs': state['repairs']+1}
        intent = copy.deepcopy(state['intent'])
        supplied_intent = plan.get('intent_plan') or {}
        proposed = supplied_intent.get('assumptions') if isinstance(supplied_intent, dict) else None
        assumption_format_error = proposed is not None and not (isinstance(proposed, list) and all(isinstance(a, dict) for a in proposed))
        if proposed is not None and not assumption_format_error:
            intent['assumptions'] = proposed
        plan['intent_plan'] = intent
        inherit_evidence(nodes, prior_nodes)
        for node in nodes:
            # 新条件结构可变，候选资格与来源不可变；手工修改仍由 Java 复核。
            ids = plan_tag_ids([node])
            candidate_ids = {int(c['tag_id']) for c in node.get('candidates') or []}
            if not state['request'].get('edited_plan') and not state.get('manual_edit') and not ids <= candidate_ids:
                node['unresolved'] = '计算或标签条件缺少本项需求的检索证据'
        ids = sorted(plan_tag_ids(nodes) & set(state['request']['eligible_tag_ids']))
        tags, codes = state.get('tags', {}), state.get('codes', [])
        if ids:
            # 详情接口单次最多50；复杂组合按批次读取全部依赖。
            for offset in range(0, len(ids), 50):
                data = retriever.evidence(ids[offset:offset+50], state['request']['requirement'], set(state['request']['eligible_tag_ids']))
                tags, codes = merge_evidence({**state, 'tags': tags, 'codes': codes}, data)
        plan = validate_plan(plan, {int(k): v for k, v in tags.items()}, codes,
                             set(state['request']['eligible_tag_ids']), state.get('capabilities'))
        plan.update(build_id=state['request']['build_id'], snapshot_id=state['request'].get('snapshot_id'),
                    artifact_hash=state['request'].get('artifact_hash'))
        for node in nodes:
            if node.get('tag_id'):
                tag = tags.get(str(node['tag_id']), {})
                node['caliber_struct'] = tag.get('caliber_struct', {})
                node['unit_scale'] = tag.get('unit_scale', 1)
        errors = plan['diagnostics']
        if assumption_format_error:
            errors.append(diagnostic('FORMAT_ERROR', 'assumptions必须为对象数组', actions=['repair_plan']))
        for assumption in intent.get('assumptions', []):
            if assumption.get('status') == 'PUBLISHED':
                ref = assumption.get('definition_ref') or {}
                if not isinstance(ref, dict):
                    errors.append(diagnostic('FORMAT_ERROR', 'definition_ref须为{tag_id}或{capability_id,version}对象', actions=['repair_plan']))
                    continue
                if ref.get('tag_id'):
                    if str(ref['tag_id']) not in tags:
                        errors.append(diagnostic('BINDING_MISMATCH', '业务解释引用未检索的标签', actions=['get_tag_details']))
                else:
                    cap = state.get('capabilities', {}).get(ref.get('capability_id'))
                    if not cap or str(cap.get('version')) != str(ref.get('version')):
                        errors.append(diagnostic('CAPABILITY_UNAVAILABLE', '业务定义缺少本轮发布证据', actions=['resolve_business_definition']))
            elif assumption.get('status') == 'CONFIRMED' and assumption not in state['intent'].get('assumptions', []):
                errors.append(diagnostic('BUSINESS_AMBIGUITY', assumption.get('question') or '请确认这项业务解释', decision=True))
        plan.update(valid=not errors, diagnostics=errors, validation_errors=errors, plan_status=plan_status(errors))
        history = [*state.get('repair_history', []), {'round': state['repairs']+1, 'diagnostics': errors}][-8:]
        plan['repair_history'] = history
        emit({'type': 'plan.validated', 'plan': plan, 'message': '全部条件核验通过' if plan['valid'] else '已定位待处理项，正在检查可修复路径'})
        return {'plan': plan, 'tags': tags, 'codes': codes, 'repairs': state['repairs']+1,
                'repair_history': history, 'done': plan['valid'],
                'questions': [{'clause_id': e['clause_id'], 'prompt': e['message']} for e in errors if e.get('user_decision_required')]}

    def ask(state):
        answer = interrupt({'questions': state.get('questions') or [{'prompt': '请说明需要确认的业务条件。'}], 'plan': state.get('plan', {})})
        guard()
        if isinstance(answer, dict) and answer.get('plan'):
            plan = copy.deepcopy(answer['plan']); plan.pop('intent_plan', None)
            intent = capture_intent(plan, state['request']['requirement'])
            return {'plan': plan, 'intent': intent, 'action': {'action': 'finish'}, 'repairs': 0, 'questions': [], 'manual_edit': True}
        # 业务澄清应重新理解完整需求；旧条件通过 previous_plan 保留。
        action = planner.decide({'phase': 'understand', 'requirement': str(answer),
                                 'previous_plan': state.get('plan', {}), 'history': state['request'].get('history', [])})
        plan = normalize_plan(copy.deepcopy(action.get('plan') or state.get('plan', {})))
        if not plan.get('tree'):
            return {'questions': action.get('questions') or [{'prompt': '请再补充一个具体的客群条件。'}], 'action': {'action': 'ask'}}
        plan.pop('intent_plan', None)
        intent = capture_intent(plan, state['request']['requirement'] + '\n补充：' + str(answer))
        plan.update(intent_plan=intent, valid=False)
        return {'plan': plan, 'intent': intent, 'answer': str(answer), 'questions': [], 'repairs': 0, 'calls': 0,
                'attempts': {}, 'no_progress': 0, 'terminal': False, 'started_at': time.time(), 'action': {'action': 'continue'}}

    def after_validate(state):
        if state['done']:
            return END
        if state.get('questions'):
            return 'ask'
        if state['repairs'] >= int(os.getenv('TAG_AGENT_MAX_REPAIRS', '3')) or state['request'].get('edited_plan'):
            return END
        return 'decide'

    graph = StateGraph(State)
    for name, fn in [('start', start), ('decide', decide), ('tool', tool), ('replan', replan), ('validate', validate), ('ask', ask)]:
        graph.add_node(name, fn)
    graph.add_edge(START, 'start')
    graph.add_conditional_edges('start', lambda s: END if s.get('terminal') else 'ask' if s['action']['action']=='ask' else 'validate' if s['action']['action']=='finish' else 'decide')
    graph.add_conditional_edges('decide', lambda s: END if s.get('terminal') else s['action']['action'] if s['action'].get('action') in {'tool', 'ask', 'replan'} else 'validate')
    graph.add_conditional_edges('tool', lambda s: END if s.get('terminal') else 'decide')
    graph.add_edge('replan', 'decide')
    graph.add_conditional_edges('validate', after_validate)
    graph.add_conditional_edges('ask', lambda s: 'validate' if s['action']['action']=='finish' else 'ask' if s['action']['action']=='ask' else 'decide')
    return graph.compile(checkpointer=saver)
