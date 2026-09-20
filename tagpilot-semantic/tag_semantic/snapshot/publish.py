"""从内存语义对象组装快照行（仅 REVIEWED）。"""

from __future__ import annotations

from typing import Any

from tag_semantic.snapshot.canonicalize import content_hash, dumps_jsonl


def reviewed(row: dict[str, Any]) -> bool:
    return row.get("review_status") == "REVIEWED"


def assemble_snapshot(
    *,
    library_id: int,
    snapshot_id: str,
    tags: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
    codes: list[dict[str, Any]],
    aliases: list[dict[str, Any]],
    confusable: list[dict[str, Any]],
    examples: list[dict[str, Any]],
    terms: list[dict[str, Any]],
    coverage_note: str,
) -> dict[str, Any]:
    tag_aliases = _by_target(aliases, "TAG")
    concept_aliases = _by_target(aliases, "CONCEPT")
    code_aliases = _by_target(aliases, "CODE_VALUE")
    rows: list[dict[str, Any]] = []
    business_tags = [t for t in tags if t.get("semantic_type") != "ID_KEY" and reviewed(t)]
    published_concepts = [c for c in concepts if reviewed(c) and c.get("status", "0") == "0"]
    published_codes = [c for c in codes if reviewed(c)]
    published_terms = [t for t in terms if reviewed(t)]
    meta = {
        "kind": "meta",
        "library_id": library_id,
        "schema_version": "v1",
        "scope": "PILOT",
        "coverage_note": coverage_note,
        "counts": {
            "tag": len(business_tags),
            "concept": len(published_concepts),
            "code_value": len(published_codes),
            "term": len(published_terms),
        },
    }
    rows.append(meta)
    for concept in published_concepts:
        cid = str(concept.get("concept_id") or concept.get("concept_code"))
        row = {
            "kind": "concept",
            "concept_id": concept.get("concept_id"),
            "concept_code": concept.get("concept_code"),
            "library_id": library_id,
            "name": concept.get("concept_name"),
            "definition": concept.get("definition"),
            "status": concept.get("status", "0"),
            "aliases": concept_aliases.get(cid, []) + concept_aliases.get(concept.get("concept_code"), []),
        }
        rows.append(row)
    for tag in business_tags:
        tid = str(tag.get("tag_id"))
        tag_conf = [
            c
            for c in confusable
            if reviewed(c) and tag.get("tag_id") in {c.get("tag_id_a"), c.get("tag_id_b")}
        ]
        tag_ex = [e for e in examples if reviewed(e) and e.get("tag_id") == tag.get("tag_id")]
        rows.append(
            {
                "kind": "tag",
                "tag_id": tag.get("tag_id"),
                "field_name": tag.get("field_name"),
                "name": tag.get("name"),
                "status": "2",
                "source_status": "AVAILABLE",
                "semantic_type": tag.get("semantic_type"),
                "family_key": tag.get("family_key"),
                "concept_code": tag.get("concept_code"),
                "concept_id": tag.get("concept_id"),
                "concept_name": tag.get("concept_name"),
                "unit": tag.get("unit"),
                "caliber_struct": tag.get("caliber_struct"),
                "definition_long": tag.get("definition_long"),
                "dir_path": tag.get("dir_path") or [],
                "aliases": tag_aliases.get(tid, []),
                "confusable": tag_conf,
                "examples": tag_ex,
            }
        )
    for code in published_codes:
        target = f"{code.get('tag_id')}#{code.get('code')}"
        rows.append(
            {
                "kind": "code_value",
                "tag_id": code.get("tag_id"),
                "code": code.get("code"),
                "label": code.get("definition") or code.get("label"),
                "rank_no": code.get("rank_no"),
                "lower_bound": code.get("lower_bound"),
                "upper_bound": code.get("upper_bound"),
                "lower_inclusive": code.get("lower_inclusive"),
                "upper_inclusive": code.get("upper_inclusive"),
                "aliases": code_aliases.get(target, []),
            }
        )
    for term in published_terms:
        rows.append(
            {
                "kind": "term",
                "term": term.get("term"),
                "term_norm": term.get("term_norm"),
                "type": term.get("term_type"),
                "options": term.get("options"),
                "policy": term.get("default_policy"),
            }
        )
    hashed = content_hash(rows)
    meta["content_hash"] = hashed
    meta["snapshot_id"] = snapshot_id
    return {"rows": rows, "jsonl": dumps_jsonl(rows), "content_hash": hashed}


def mark_reviewed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        if item.get("semantic_type") == "ID_KEY":
            out.append(item)
            continue
        item["review_status"] = "REVIEWED"
        item["source_ref"] = item.get("source_ref") or "pilot_review_pack"
        out.append(item)
    return out


def _by_target(aliases: list[dict[str, Any]], target_type: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for alias in aliases:
        if alias.get("target_type") != target_type or not reviewed(alias):
            continue
        grouped.setdefault(str(alias.get("target_id")), []).append(alias)
    return grouped
