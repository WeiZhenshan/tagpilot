"""澄清先确定业务定义，再确定该定义的阈值；旧问题也使用相同顺序。"""
from copy import deepcopy

DEFINITION_REASONS={'MULTIPLE_PUBLISHED_DEFINITIONS','CONFLICTING_INTERPRETATIONS','DEFINITION_MISSING'}


def staged_questions(questions):
    definitions={q.get('requirement_id') or q.get('clause_id') for q in questions
                 if q.get('reason') in DEFINITION_REASONS}
    return [deepcopy(q) for q in questions if not
            (q.get('reason')=='THRESHOLD_MISSING' and (q.get('requirement_id') or q.get('clause_id')) in definitions)]


def validate_staged_answer(questions,answer):
    """兼容旧表单的文本回答；不能提交尚未确定指标对应的第二题。"""
    if not isinstance(answer,str):return
    shown=staged_questions(questions)
    deferred=[q for q in questions if q not in shown]
    if any(q['prompt']+'：' in answer or q['prompt']+':' in answer for q in deferred):
        raise ValueError('请先确认采用哪个业务口径，再选择该口径对应的档位或阈值')


def clarification_state(request):
    state=deepcopy(request.get('clarification_state') or {'records':[],'pending_questions':[]})
    if not state.get('records') and request.get('_questions') and request.get('_answer'):
        state['records']=[{'questions':request['_questions'],'answer':request['_answer']}]
    state.setdefault('pending_questions',[])
    # 旧版并列题的回答须重新确认，不能作为两个指标间可自由组合的授权。
    if state.get('records'):
        last=state['records'][-1]
        try:validate_staged_answer(last['questions'],last['answer'])
        except ValueError:state['pending_questions']=staged_questions(last['questions'])
    return state


def record_answer(request,questions,answer):
    state=clarification_state(request)
    if questions and answer:
        state['records']=[*state.get('records',[]),{'questions':staged_questions(questions),'answer':answer}][-20:]
    state['pending_questions']=[]
    return state
