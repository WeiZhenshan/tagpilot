"""兼容 V2/V3 的圈选契约；发布证据限定标签、表达式、口径与值。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from tagpilot_agent.guards.diagnostics import PlanError, from_error, plan_status
from tagpilot_agent.domain.expressions import check_caliber, inspect_expression, finite
from tagpilot_agent.guards.ledger import check_coverage

OPS = {"=", "!=", "in", "not_in", ">", ">=", "<", "<=", "between", "contains", "like", "is_null", "is_not_null"}


def leaves(tree: dict, depth: int = 0) -> list[dict]:
    if depth > 8 or not isinstance(tree, dict):
        raise PlanError('SCHEMA_INVALID', '条件树过深或格式非法')
    if "children" in tree:
        if tree.get("logic") not in {"AND", "OR"} or not 1 <= len(tree["children"]) <= 30:
            raise PlanError('SCHEMA_INVALID', '条件组须为 AND/OR，且包含 1–30 项')
        return [leaf for child in tree["children"] for leaf in leaves(child, depth + 1)]
    if not tree.get("clause_id"):
        raise PlanError('SCHEMA_INVALID', '条件缺少 clause_id')
    return [tree]


def validate_plan(plan: dict, tags: dict[int, dict], codes: list[dict], eligible: set[int], capabilities=None) -> dict:
    nodes = leaves(plan.get("tree", {}))
    if not 1 <= len(nodes) <= 30 or len({n["clause_id"] for n in nodes}) != len(nodes):
        raise PlanError('SCHEMA_INVALID', '条件数量非法或 ID 重复')
    errors = []
    for node in nodes:
        cid = node["clause_id"]
        try:
            kind = node.get('kind', 'TAG_PREDICATE')
            if kind == 'SCOPE_ALL':
                if len(nodes) != 1 or node.get('unresolved'):
                    raise PlanError('FORMAT_ERROR', '全量范围不能与其他筛选条件混合')
                node.update(name='当前授权范围内的全部客户', status='BOUND')
                continue
            if kind == 'DERIVED_PREDICATE':
                info = inspect_expression(node.get('expression'), tags, eligible, capabilities)
                if node.get('operator') not in {'=', '!=', '>', '>=', '<', '<=', 'between', 'is_null', 'is_not_null'}:
                    raise PlanError('FORMAT_ERROR', '计算指标不支持此比较方式')
                if node.get('compare_expression'):
                    if node['operator'] not in {'=', '!=', '>', '>=', '<', '<='}:
                        raise PlanError('FORMAT_ERROR', '两个指标之间只能使用大小或等值比较')
                    right = inspect_expression(node['compare_expression'], tags, eligible, capabilities)
                    if info['unit'] != right['unit']:
                        raise PlanError('CALIBER_CONFLICT', '两个比较指标的单位不同')
                    if info['grain'] != right['grain'] and info['grain'] and right['grain']:
                        raise PlanError('CALIBER_CONFLICT', '两个比较指标的粒度不同')
                    if info['time'] != right['time'] and node.get('time_alignment') != 'EXPLICIT_PERIODS':
                        raise PlanError('CALIBER_CONFLICT', '跨期比较需要明确两侧口径')
                elif node['operator'] not in {'is_null', 'is_not_null'}:
                    vals = node.get('values') or []
                    if len(vals) != (2 if node['operator'] == 'between' else 1):
                        raise PlanError('FORMAT_ERROR', '请修正计算条件的比较值', actions=['repair_plan'])
                    if node.get('value_unit', info['unit']) != info['unit']:
                        raise PlanError('CALIBER_CONFLICT', '比较值与计算指标单位不同')
                    scale = finite(node.get('value_scale', 1))
                    if scale <= 0:
                        raise PlanError('FORMAT_ERROR', '数值倍率必须大于零')
                    nums = [finite(v) * scale for v in vals]
                    if len(nums) == 2 and nums[0] > nums[1]:
                        raise PlanError('FORMAT_ERROR', '区间下限不能大于上限')
                    node.update(values=[format(v, 'f') for v in nums], value_scale='1')
                if node.get('unresolved'):
                    raise PlanError('CAPABILITY_UNAVAILABLE', str(node['unresolved']))
                node.update(unit=info['unit'], value_unit=info['unit'], status='BOUND', null_policy='PROPAGATE',
                            name=node.get('name') or node.get('source_span') or '计算条件')
                continue
            if kind != 'TAG_PREDICATE':
                raise PlanError('FORMAT_ERROR', '未知执行条件类型')
            tid = int(node.get("tag_id") or 0)
            if tid not in eligible and tid:
                raise PlanError('INELIGIBLE_TAG', '标签不在当前资格范围')
            if tid not in tags:
                raise PlanError('UNKNOWN_TAG', '请选择可用的已发布标签')
            tag = tags[tid]
            node.update(name=tag.get("name"), semantic_type=tag.get("semantic_type"), unit=tag.get("unit"),
                        definition=tag.get("definition_long"), allowed_operators=tag.get("allowed_operators", []),
                        code_options=[c for c in codes if int(c["tag_id"]) == tid])
            op = node.get("operator")
            if op not in OPS or op not in tag.get("allowed_operators", []):
                raise PlanError('INVALID_OPERATOR', '标签不支持该比较方式')
            values = node.get("values", [])
            if op not in {"is_null", "is_not_null"}:
                if not isinstance(values, list) or not values or any(v is None or str(v) == "" for v in values):
                    raise PlanError('INVALID_VALUE', '请补充条件值')
                if op == "between" and len(values) != 2:
                    raise PlanError('INVALID_VALUE', '区间必须包含两个端点')
                if op not in {"between", "in", "not_in"} and len(values) != 1:
                    raise PlanError('INVALID_VALUE', '该比较方式只允许一个值')
            typ = str(tag.get("semantic_type", ""))
            check_caliber(node, tag)
            if typ.startswith("NUM_"):
                nums = [Decimal(str(v)) for v in values]
                if any(not v.is_finite() for v in nums):
                    raise PlanError('INVALID_VALUE', '数值必须有限')
                target_unit = tag.get("unit") or "NONE"
                if node.get("value_unit", target_unit) != target_unit:
                    raise PlanError('UNIT_MISMATCH', '数值单位与标签单位不一致')
                target_scale = Decimal(str(tag.get("unit_scale") or 1))
                input_scale = Decimal(str(node.get("value_scale", target_scale)))
                if not target_scale.is_finite() or not input_scale.is_finite() or target_scale <= 0 or input_scale <= 0:
                    raise PlanError('UNIT_MISMATCH', '数值单位倍率非法')
                nums = [v * input_scale / target_scale for v in nums]
                node.update(values=[format(v, 'f') for v in nums], value_unit=target_unit, value_scale=str(target_scale))
                if op == "between" and nums[0] > nums[1]:
                    raise PlanError('INVALID_VALUE', '区间下限不能大于上限')
            if typ == "BOOL" or typ.startswith("ENUM_"):
                node["values"] = values = [str(v) for v in values]
                allowed = {str(c["code"]) for c in codes if int(c["tag_id"]) == tid}
                if any(str(v) not in allowed for v in values):
                    raise PlanError('UNKNOWN_CODE', '存在未发布码值')
                if op in {"not_in", "!="}:
                    unknown = {str(c['code']) for c in codes if int(c['tag_id']) == tid and c.get('is_unknown_bucket') in {1, True, '1'}}
                    policy = node.get('unknown_policy') or 'EXCLUDE'
                    if policy not in {'EXCLUDE', 'INCLUDE'}:
                        raise PlanError('INVALID_VALUE', '请明确未知码值是否参与圈选')
                    if unknown and policy == 'EXCLUDE':
                        if op == '!=' and unknown - set(map(str, values)):
                            raise PlanError('UNKNOWN_CODE', '该否定条件含未知码值，请改为支持的“不属于”集合条件')
                        node['values'] = sorted(set(map(str, values)) | unknown)
                    node.update(null_policy='EXCLUDE', unknown_policy=policy)
            if node.get("unresolved"):
                raise PlanError('REQUIREMENT_MISSING', str(node['unresolved']))
            node.update(name=tag.get("name"), semantic_type=typ, unit=tag.get("unit"),
                        definition=tag.get("definition_long"), allowed_operators=tag.get("allowed_operators", []),
                        code_options=[c for c in codes if int(c["tag_id"]) == tid], status="BOUND")
        except (ValueError, TypeError, InvalidOperation, ArithmeticError) as exc:
            node["status"] = "UNRESOLVED"
            errors.append(from_error(exc, cid))
    if plan.get('intent_plan'):
        errors.extend(check_coverage(plan['intent_plan'], nodes, plan['tree']))
    modern = bool(plan.get('intent_plan')) or any(n.get('kind') in {'SCOPE_ALL', 'DERIVED_PREDICATE'} for n in nodes)
    plan.update(schema_version=3 if modern else 2, diagnostics=errors,
                plan_status=plan_status(errors), valid=not errors)
    return plan
