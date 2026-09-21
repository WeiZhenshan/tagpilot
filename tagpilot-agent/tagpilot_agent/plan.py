"""V2 圈选契约。模型给出意图，发布目录限定类型、操作符和值。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

OPS = {"=", "!=", "in", "not_in", ">", ">=", "<", "<=", "between", "contains", "like", "is_null", "is_not_null"}


def leaves(tree: dict, depth: int = 0) -> list[dict]:
    if depth > 8 or not isinstance(tree, dict):
        raise ValueError("条件树过深或格式非法")
    if "children" in tree:
        if tree.get("logic") not in {"AND", "OR"} or not 1 <= len(tree["children"]) <= 30:
            raise ValueError("条件组须为 AND/OR，且包含 1–30 项")
        return [leaf for child in tree["children"] for leaf in leaves(child, depth + 1)]
    if not tree.get("clause_id"):
        raise ValueError("条件缺少 clause_id")
    return [tree]


def validate_plan(plan: dict, tags: dict[int, dict], codes: list[dict], eligible: set[int]) -> dict:
    nodes = leaves(plan.get("tree", {}))
    if not 1 <= len(nodes) <= 30 or len({n["clause_id"] for n in nodes}) != len(nodes):
        raise ValueError("条件数量非法或 ID 重复")
    errors = []
    for node in nodes:
        cid = node["clause_id"]
        try:
            tid = int(node.get("tag_id") or 0)
            if tid not in eligible or tid not in tags:
                raise ValueError("请选择可用的已发布标签")
            tag = tags[tid]
            node.update(name=tag.get("name"), semantic_type=tag.get("semantic_type"), unit=tag.get("unit"),
                        definition=tag.get("definition_long"), allowed_operators=tag.get("allowed_operators", []),
                        code_options=[c for c in codes if int(c["tag_id"]) == tid])
            op = node.get("operator")
            if op not in OPS or op not in tag.get("allowed_operators", []):
                raise ValueError("标签不支持该比较方式")
            values = node.get("values", [])
            if op not in {"is_null", "is_not_null"}:
                if not isinstance(values, list) or not values or any(v is None or str(v) == "" for v in values):
                    raise ValueError("请补充条件值")
                if op == "between" and len(values) != 2:
                    raise ValueError("区间必须包含两个端点")
                if op not in {"between", "in", "not_in"} and len(values) != 1:
                    raise ValueError("该比较方式只允许一个值")
            typ = str(tag.get("semantic_type", ""))
            caliber = tag.get("caliber_struct") or {}
            expected = node.get("expected_caliber") or {}
            if node.get("time_constraint") and not expected:
                raise ValueError("请明确时间窗口对应的发布口径，不能以相近周期替代")
            if not isinstance(expected, dict) or any(str(caliber.get(k)) != str(v) for k, v in expected.items() if v is not None):
                raise ValueError("标签口径与需求不一致，请重新选择标签或明确修改口径")
            if typ.startswith("NUM_"):
                nums = [Decimal(str(v)) for v in values]
                if any(not v.is_finite() for v in nums):
                    raise ValueError("数值必须有限")
                target_unit = tag.get("unit") or "NONE"
                if node.get("value_unit", target_unit) != target_unit:
                    raise ValueError("数值单位与标签单位不一致")
                target_scale = Decimal(str(tag.get("unit_scale") or 1))
                input_scale = Decimal(str(node.get("value_scale", target_scale)))
                if not target_scale.is_finite() or not input_scale.is_finite() or target_scale <= 0 or input_scale <= 0:
                    raise ValueError("数值单位倍率非法")
                nums = [v * input_scale / target_scale for v in nums]
                node.update(values=[format(v, 'f') for v in nums], value_unit=target_unit, value_scale=str(target_scale))
                if op == "between" and nums[0] > nums[1]:
                    raise ValueError("区间下限不能大于上限")
            if typ == "BOOL" or typ.startswith("ENUM_"):
                allowed = {str(c["code"]) for c in codes if int(c["tag_id"]) == tid}
                if any(str(v) not in allowed for v in values):
                    raise ValueError("存在未发布码值")
                if op in {"not_in", "!="}:
                    unknown = {str(c['code']) for c in codes if int(c['tag_id']) == tid and c.get('is_unknown_bucket') in {1, True, '1'}}
                    policy = node.get('unknown_policy') or 'EXCLUDE'
                    if policy not in {'EXCLUDE', 'INCLUDE'}:
                        raise ValueError('请明确未知码值是否参与圈选')
                    if unknown and policy == 'EXCLUDE':
                        if op == '!=' and unknown - set(map(str, values)):
                            raise ValueError('该否定条件含未知码值，请改为支持的“不属于”集合条件')
                        node['values'] = sorted(set(map(str, values)) | unknown)
                    node.update(null_policy='EXCLUDE', unknown_policy=policy)
            if node.get("unresolved"):
                raise ValueError(str(node["unresolved"]))
            node.update(name=tag.get("name"), semantic_type=typ, unit=tag.get("unit"),
                        definition=tag.get("definition_long"), allowed_operators=tag.get("allowed_operators", []),
                        code_options=[c for c in codes if int(c["tag_id"]) == tid], status="BOUND")
        except (ValueError, TypeError, InvalidOperation, ArithmeticError) as exc:
            node["status"] = "UNRESOLVED"
            errors.append({"clause_id": cid, "message": str(exc)})
    plan.update(schema_version=2, validation_errors=errors, valid=not errors)
    return plan
