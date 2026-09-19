"""从 JSONL 构建内存对象与结构图，不回查业务库。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tag_semantic.snapshot.canonicalize import content_hash
from tag_semantic.snapshot.schema import validate_catalog
from copy import deepcopy


@dataclass
class Catalog:
    meta: dict[str, Any]
    domains: list[dict[str, Any]] = field(default_factory=list)
    concepts: dict[Any, dict[str, Any]] = field(default_factory=dict)
    tags: dict[int, dict[str, Any]] = field(default_factory=dict)
    code_values: list[dict[str, Any]] = field(default_factory=list)
    terms: list[dict[str, Any]] = field(default_factory=list)
    aliases: list[dict[str, Any]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def family_members(self) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for tag in self.tags.values():
            key = tag.get("family_key")
            if not key:
                continue
            groups.setdefault(key, []).append(tag)
        return groups


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_catalog(path: Path, expected_hash: str | None = None) -> Catalog:
    rows = load_jsonl(path)
    declared = next((r.get("content_hash") for r in rows if r.get("kind") == "meta"), None)
    expected_hash = expected_hash or declared
    if expected_hash:
        actual = content_hash(rows)
        if actual != expected_hash:
            raise ValueError(f"快照内容哈希不一致: expected={expected_hash} actual={actual}")
    original_rows = deepcopy(rows)
    validate_catalog(rows)
    catalog = Catalog(meta={})
    catalog.rows = original_rows
    for row in rows:
        kind = row.get("kind")
        if kind == "meta":
            catalog.meta = row
        elif kind == "domain":
            catalog.domains.append(row)
        elif kind == "concept":
            catalog.concepts[row.get("concept_id") or row.get("code") or row.get("concept_code")] = row
        elif kind == "tag":
            catalog.tags[int(row["tag_id"])] = row
            catalog.aliases.extend(row.get("aliases") or [])
        elif kind == "code_value":
            catalog.code_values.append(row)
            catalog.aliases.extend(row.get("aliases") or [])
        elif kind == "term":
            catalog.terms.append(row)
        if kind == "concept":
            catalog.aliases.extend(row.get("aliases") or [])
    return catalog


def write_graph_sqlite(catalog: Catalog, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("create table if not exists nodes(id text primary key, kind text, payload text)")
        conn.execute("create table if not exists edges(src text, dst text, rel text)")
        conn.execute("delete from nodes")
        conn.execute("delete from edges")
        for tag in catalog.tags.values():
            node_id = f"tag:{tag['tag_id']}"
            conn.execute(
                "insert into nodes(id, kind, payload) values (?,?,?)",
                (node_id, "tag", json.dumps(tag, ensure_ascii=False)),
            )
            if tag.get("concept_id") or tag.get("concept_code"):
                concept_id = f"concept:{tag.get('concept_id') or tag.get('concept_code')}"
                conn.execute("insert into edges(src, dst, rel) values (?,?,?)", (concept_id, node_id, "has_tag"))
                if tag.get("family_key"):
                    fam = f"family:{tag['family_key']}"
                    conn.execute(
                        "insert or ignore into nodes(id, kind, payload) values (?,?,?)",
                        (fam, "family", tag["family_key"]),
                    )
                    conn.execute("insert into edges(src, dst, rel) values (?,?,?)", (fam, node_id, "member"))
        for concept in catalog.concepts.values():
            node_id = f"concept:{concept.get('concept_id') or concept.get('concept_code')}"
            conn.execute(
                "insert or ignore into nodes(id, kind, payload) values (?,?,?)",
                (node_id, "concept", json.dumps(concept, ensure_ascii=False)),
            )
        conn.commit()
    finally:
        conn.close()
