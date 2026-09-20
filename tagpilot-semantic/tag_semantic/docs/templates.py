"""tpl1 上下文化检索文档。三种视图由同一函数派生。"""

from __future__ import annotations

from typing import Any

TEMPLATE_VERSION = "tpl1"


def _join(items: list[str]) -> str:
    return " | ".join(x for x in items if x)


def tag_views(tag: dict[str, Any]) -> dict[str, str]:
    aliases = [
        a.get("alias_text")
        for a in tag.get("aliases") or []
        if a.get("review_status") == "REVIEWED" and a.get("alias_type") != "NEGATIVE"
    ]
    caliber = tag.get("caliber_struct") or {}
    time_label = caliber.get("time_anchor_label") or "无"
    examples = [
        e.get("utterance")
        for e in tag.get("examples") or []
        if e.get("review_status") == "REVIEWED" and e.get("example_type") == "POS"
    ]
    confusable = [
        c.get("difference_note") or c.get("disambiguation_hint")
        for c in tag.get("confusable") or []
        if c.get("review_status") == "REVIEWED"
    ]
    name_text = _join([tag.get("name") or ""] + aliases)
    body_parts = [
        f"[名称] {tag.get('name') or ''}",
        f"[别名] {_join(aliases)}",
        f"[目录] {' > '.join(tag.get('dir_path') or [])}",
        f"[概念] {tag.get('concept_name') or tag.get('concept_code') or ''}:{tag.get('concept_definition') or ''}",
        f"[口径] 时间：{time_label}；统计：{caliber.get('statistic')}；范围：{caliber.get('scope')}",
        f"[类型] {tag.get('semantic_type')}；单位：{tag.get('unit')}",
        f"[定义] {tag.get('definition_long') or ''}",
        f"[示例] {_join(examples)}",
        f"[区别于] {_join(confusable)}",
    ]
    body_text = "\n".join(body_parts)
    dense_text = "\n".join(
        p for p in body_parts if not p.startswith("[示例]") and not p.startswith("[区别于]")
    )
    return {"name_text": name_text, "body_text": body_text, "dense_text": dense_text}


def concept_views(concept: dict[str, Any]) -> dict[str, str]:
    aliases = [
        a.get("alias_text")
        for a in concept.get("aliases") or []
        if a.get("review_status") == "REVIEWED" and a.get("alias_type") != "NEGATIVE"
    ]
    name = concept.get("name") or concept.get("concept_name") or ""
    definition = concept.get("definition") or ""
    name_text = _join([name] + aliases)
    body = f"[名称] {name}\n[别名] {_join(aliases)}\n[定义] {definition}"
    return {"name_text": name_text, "body_text": body, "dense_text": body}


def code_value_views(row: dict[str, Any]) -> dict[str, str]:
    aliases = [
        a.get("alias_text")
        for a in row.get("aliases") or []
        if a.get("review_status") == "REVIEWED" and a.get("alias_type") != "NEGATIVE"
    ]
    label = row.get("label") or row.get("definition") or row.get("code")
    name_text = _join([str(label)] + aliases)
    body = f"[码值] {row.get('code')} {label}\n[别名] {_join(aliases)}\n[标签] {row.get('tag_id')}"
    return {"name_text": name_text, "body_text": body, "dense_text": body}


def render_documents(catalog_tags: list[dict[str, Any]], concepts: list[dict[str, Any]], codes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    docs = []
    for tag in catalog_tags:
        if tag.get("semantic_type") == "ID_KEY":
            continue
        views = tag_views(tag)
        docs.append({"doc_type": "tag", "doc_id": f"tag:{tag['tag_id']}", "tag_id": int(tag["tag_id"]), "concept_id": tag.get("concept_id") or -1, "family_key": tag.get("family_key"), **views})
    for concept in concepts:
        views = concept_views(concept)
        cid = concept.get("concept_id") or concept.get("concept_code")
        docs.append({"doc_type": "concept", "doc_id": f"concept:{cid}", "tag_id": -1, "concept_id": cid, "family_key": None, **views})
    for row in codes:
        views = code_value_views(row)
        docs.append({"doc_type": "code_value", "doc_id": f"code:{row['tag_id']}#{row['code']}", "tag_id": int(row["tag_id"]), "concept_id": -1, "code": row.get("code"), "family_key": None, **views})
    return docs
