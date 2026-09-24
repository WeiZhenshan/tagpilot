"""业务选择、能力缺口和内部修复分流；诊断可直接作为模型修复输入。"""
from __future__ import annotations


CATEGORY = {'INVALID_OPERATOR': 'FORMAT_ERROR', 'INVALID_VALUE': 'FORMAT_ERROR', 'SCHEMA_INVALID': 'FORMAT_ERROR', 'UNKNOWN_CODE': 'BINDING_MISMATCH', 'INELIGIBLE_TAG': 'PERMISSION_DENIED', 'UNKNOWN_TAG': 'BINDING_MISMATCH', 'UNIT_MISMATCH': 'CALIBER_CONFLICT', 'REQUIREMENT_MISSING': 'INTENT_COVERAGE', 'LOGIC_CHANGED': 'INTENT_LOGIC_CHANGED'}

def diagnostic(code, message, clause_id=None, *, expected=None, actual=None,
               actions=None, decision=False, retryable=False):
    return {'code': code, 'category': CATEGORY.get(code, code), 'resolution': 'USER_DECISION' if decision else 'CAPABILITY_GAP' if code in {'CAPABILITY_UNAVAILABLE', 'UNSUPPORTED_CAPABILITY', 'METADATA_INCOMPLETE'} else 'AGENT_FIXABLE', 'clause_id': clause_id,
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
    return diagnostic('SCHEMA_INVALID', '条件格式或数值非法', clause_id, actions=['check_plan'], retryable=True)


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
