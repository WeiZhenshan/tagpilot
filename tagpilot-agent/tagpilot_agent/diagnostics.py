"""业务选择、能力缺口和内部修复分流；诊断可直接作为模型修复输入。"""
from __future__ import annotations


def diagnostic(code, message, clause_id=None, *, expected=None, actual=None,
               actions=None, decision=False, retryable=False):
    return {'code': code, 'category': code, 'clause_id': clause_id,
            'requirement_id': clause_id, 'message': message, 'user_message': message,
            'expected': expected, 'actual': actual, 'repair_actions': actions or [],
            'user_decision_required': decision, 'retryable': retryable}


class PlanError(ValueError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def from_error(exc, clause_id=None):
    if isinstance(exc, PlanError):
        return diagnostic(exc.code, str(exc), clause_id, **exc.details)
    message = str(exc)
    if '码值' in message:
        code, actions = 'BINDING_MISMATCH', ['resolve_tag_values']
    elif '标签' in message and ('可用' in message or '请选择' in message):
        code, actions = 'BINDING_MISMATCH', ['search_tags', 'search_capabilities']
    else:
        code, actions = 'FORMAT_ERROR', ['repair_plan']
    return diagnostic(code, message, clause_id, actions=actions, retryable=True)


def plan_status(errors):
    if not errors:
        return 'READY'
    if any(e.get('user_decision_required') for e in errors):
        return 'NEEDS_DECISION'
    if any(e['code'] in {'CAPABILITY_UNAVAILABLE', 'METADATA_INCOMPLETE'} for e in errors):
        return 'CAPABILITY_GAP'
    if any(e['code'] in {'TRANSIENT_FAILURE', 'BUDGET_EXHAUSTED'} for e in errors):
        return 'RETRYABLE_FAILURE'
    return 'DRAFT'
