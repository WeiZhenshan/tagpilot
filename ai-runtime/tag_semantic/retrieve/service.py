"""六通道检索服务。"""

from __future__ import annotations

from typing import Any

from tag_semantic.index.alias_index import AliasIndex
from tag_semantic.index.embedder import HashEmbedder, cosine
from tag_semantic.index.local_store import LocalStore
from tag_semantic.retrieve.facets import parse_facets
from tag_semantic.retrieve.family import resolve_family
from tag_semantic.retrieve.fusion import rrf
from tag_semantic.snapshot.loader import Catalog


class RetrieveService:
    def __init__(self, catalog: Catalog, store: LocalStore, alias_index: AliasIndex) -> None:
        self.catalog = catalog
        self.store = store
        self.alias_index = alias_index
        self.embedder = HashEmbedder()

    def retrieve(self, requirement: str, eligible_tag_ids: set[int] | None, k: int = 20) -> dict[str, Any]:
        facets = parse_facets(requirement, self.catalog.terms)
        filters = {"eligible_tag_ids": eligible_tag_ids}
        if eligible_tag_ids is not None:
            concept_ids = set()
            for tag in self.catalog.tags.values():
                if int(tag["tag_id"]) in eligible_tag_ids:
                    concept_ids.add(tag.get("concept_id") or tag.get("concept_code"))
            filters["eligible_concept_ids"] = concept_ids
            if not eligible_tag_ids:
                return {"candidates": [], "facets": facets, "family": None}
        alias_hits = []
        for alias in self.alias_index.lookup(requirement):
            doc = self._alias_to_doc(alias)
            if doc is None:
                continue
            if not _doc_allowed(doc, filters):
                continue
            alias_hits.append({"doc": doc, "score": 1.0, "rank": 1, "channel": "alias"})
        bm25_name = self.store.search("bm25_name", requirement, filters, 30)
        bm25_body = self.store.search("bm25_body", requirement, filters, 30)
        dense_hits = self._dense(requirement, filters, 30)
        fused = rrf([alias_hits, bm25_name, bm25_body, dense_hits])
        tag_candidates = []
        for item in fused:
            doc = item["doc"]
            if doc.get("doc_type") == "concept":
                tag_candidates.extend(self._expand_concept(doc, eligible_tag_ids))
            elif doc.get("doc_type") == "code_value":
                tag_candidates.append(doc)
            else:
                tag_candidates.append(doc)
        family_result = None
        if tag_candidates:
            top = tag_candidates[0]
            family_key = top.get("family_key")
            members = []
            if family_key:
                members = list(self.catalog.family_members.get(family_key) or [])
                if eligible_tag_ids is not None:
                    members = [m for m in members if int(m["tag_id"]) in eligible_tag_ids]
            family_result = resolve_family(members or [self.catalog.tags.get(int(top.get("tag_id") or 0), top)], facets["time"])
        return {
            "candidates": fused[:k],
            "facets": facets,
            "family": family_result,
        }

    def _dense(self, query: str, filters: dict[str, Any], k: int) -> list[dict[str, Any]]:
        qv = self.embedder.encode([query])[0]
        scored = []
        for doc in self.store.docs:
            if not _doc_allowed(doc, filters):
                continue
            vec = doc.get("dense")
            if not vec:
                continue
            scored.append((cosine(qv, vec), doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for rank, (score, doc) in enumerate(scored[:k], 1):
            hits.append({"doc": doc, "score": score, "rank": rank, "channel": "dense"})
        return hits

    def _alias_to_doc(self, alias: dict[str, Any]) -> dict[str, Any] | None:
        target_type = alias.get("target_type")
        target_id = alias.get("target_id")
        if target_type == "TAG":
            tag = self.catalog.tags.get(int(target_id))
            if not tag:
                return None
            return {"doc_id": f"tag:{tag['tag_id']}", "doc_type": "tag", "tag_id": int(tag["tag_id"]), "family_key": tag.get("family_key"), "name_text": tag.get("name")}
        if target_type == "CODE_VALUE":
            return {"doc_id": f"code:{target_id}", "doc_type": "code_value", "tag_id": int(str(target_id).split("#")[0]), "code": str(target_id).split("#")[-1], "family_key": None, "name_text": alias.get("alias_text")}
        if target_type == "CONCEPT":
            return {"doc_id": f"concept:{target_id}", "doc_type": "concept", "tag_id": -1, "concept_id": target_id, "family_key": None, "name_text": alias.get("alias_text")}
        return None

    def _expand_concept(self, doc: dict[str, Any], eligible: set[int] | None) -> list[dict[str, Any]]:
        cid = doc.get("concept_id")
        rows = []
        for tag in self.catalog.tags.values():
            if (tag.get("concept_id") or tag.get("concept_code")) != cid:
                continue
            if eligible is not None and int(tag["tag_id"]) not in eligible:
                continue
            rows.append({"doc_id": f"tag:{tag['tag_id']}", "doc_type": "tag", "tag_id": int(tag["tag_id"]), "family_key": tag.get("family_key"), "name_text": tag.get("name")})
        return rows


def _doc_allowed(doc: dict[str, Any], filters: dict[str, Any]) -> bool:
    eligible = filters.get("eligible_tag_ids")
    if doc.get("doc_type") == "concept":
        concepts = filters.get("eligible_concept_ids")
        if concepts is not None and doc.get("concept_id") not in concepts:
            return False
        return True
    if eligible is not None and int(doc.get("tag_id") or -1) not in eligible:
        return False
    return True
