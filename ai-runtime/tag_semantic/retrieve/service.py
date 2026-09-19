"""六通道检索服务。"""

from __future__ import annotations

from typing import Any

from tag_semantic.index.alias_index import AliasIndex
from tag_semantic.index.embedder import HashEmbedder, cosine
from tag_semantic.index.local_store import LocalStore
from tag_semantic.retrieve.facets import parse_facets
from tag_semantic.retrieve.family import resolve_family, interval_covers
from tag_semantic.retrieve.fusion import rrf
from tag_semantic.snapshot.loader import Catalog


class RetrieveService:
    def __init__(self, catalog: Catalog, store, alias_index: AliasIndex, embedder=None, reranker=None, config=None) -> None:
        self.catalog = catalog
        self.store = store
        self.alias_index = alias_index
        self.embedder = embedder or HashEmbedder()
        self.reranker = reranker
        self.config = config or {}

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
                return {"candidates": [], "recall_candidates": [], "facets": facets, "family": None,
                        "decision": "CANDIDATES_ONLY", "code_selection": None, "auto_execute": False}
        alias_hits = []
        for alias in self.alias_index.lookup(requirement):
            doc = self._alias_to_doc(alias)
            if doc is None:
                continue
            if not _doc_allowed(doc, filters):
                continue
            alias_hits.append({"doc": doc, "score": 1.0, "rank": 1, "channel": "alias",
                               "alias_norm": (alias.get("alias_norm") or "").lower().replace(" ", "")})
        budget = int(self.config.get("channel_k", 30))
        import re
        multi_condition = re.search(r"(?:同时|并且|以及|而且|；|;|、)", requirement) is not None
        exact_hits = self._unique_longest_alias_hits(alias_hits) if self.config.get("exact_alias_fast_path") is True and not multi_condition else []
        if exact_hits:
            # 最长已复核别名只指向一个标签时，身份已确定；不再浪费模型重排，也避免短别名稀释证据。
            fused = rrf([exact_hits], k=int(self.config.get("rrf_k", 60)))
        else:
            bm25_name = self.store.search("bm25_name", requirement, filters, budget)
            bm25_body = self.store.search("bm25_body", requirement, filters, budget)
            dense_hits = self._dense(requirement, filters, budget)
            fused = rrf([alias_hits, bm25_name, bm25_body, dense_hits], k=int(self.config.get("rrf_k", 60)))
        # 域只作软先验，不能剪掉其它业务域；权重固化在 build manifest。
        for item in fused:
            doc = item['doc']
            tag = self.catalog.tags.get(doc.get('tag_id'), {})
            domain = (tag.get('dir_path') or [None])[0]
            prior = float(self.config.get('domain_prior_weight', 0.002)) if domain and domain in requirement else 0.0
            item['domain_prior'] = prior
            item['rrf_score'] += prior
        fused.sort(key=lambda c: (-c['rrf_score'], c['doc']['doc_id']))
        recall_candidates = fused[:20]
        if self.reranker and not exact_hits:
            budget = min(50, max(1, int(self.config.get('rerank_k', 50))))
            fused = self.reranker.rerank(requirement, fused[:budget], k=max(k, 10))
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
        decision = "CANDIDATES_ONLY"
        code_selection = None
        if facets["unresolved_fuzzy_terms"] or str((family_result or {}).get("status", "")).startswith("clarify"):
            decision = "CLARIFY"
        selected = (family_result or {}).get("selected") or {}
        if selected.get('semantic_type') in {'ENUM_NOMINAL', 'BOOL'} and decision == 'CANDIDATES_ONLY':
            # 码值必须来自已复核的精确别名证据，不能把向量相似码直接当成条件。
            matched_codes = {hit['doc']['code'] for hit in alias_hits
                             if hit['doc'].get('doc_type') == 'code_value'
                             and hit['doc'].get('tag_id') == selected.get('tag_id')}
            if matched_codes:
                if facets['negated'] or len(matched_codes) != 1:
                    decision = 'CLARIFY'
                else:
                    code_selection = {'expressible': True, 'codes': sorted(matched_codes)}
        if selected.get("semantic_type") == "ENUM_ORDINAL" and facets.get("boundary"):
            import re
            from decimal import Decimal
            match = re.search(r"(?:超过|高于|以上|至少|以下|不到|不足|及以上|及以下)?\s*(\d+(?:\.\d+)?)\s*(亿|万)?", requirement)
            if match:
                amount = Decimal(match.group(1)) * {None: 1, "万": 10000, "亿": 100000000}[match.group(2)]
                op = facets["boundary"]["operator"]
                codes = [c for c in self.catalog.code_values if c['tag_id'] == selected['tag_id']]
                code_selection = interval_covers(codes, amount if op in {">", ">="} else None, amount if op in {"<", "<="} else None, op)
                if not code_selection['expressible']:
                    decision = "INEXPRESSIBLE"
            else:
                decision = "CLARIFY"
        return {
            "decision": decision, "code_selection": code_selection, "auto_execute": False,
            "candidates": fused[:k],
            "recall_candidates": recall_candidates,
            "facets": facets,
            "family": family_result,
        }

    @staticmethod
    def _unique_longest_alias_hits(alias_hits):
        tag_hits = [hit for hit in alias_hits if int(hit["doc"].get("tag_id") or -1) > 0 and hit.get("alias_norm")]
        if not tag_hits:
            return []
        longest = max(len(hit["alias_norm"]) for hit in tag_hits)
        strongest = [hit for hit in tag_hits if len(hit["alias_norm"]) == longest]
        if len({int(hit["doc"]["tag_id"]) for hit in strongest}) != 1:
            return []
        return strongest

    def _dense(self, query: str, filters: dict[str, Any], k: int) -> list[dict[str, Any]]:
        if getattr(self.store, "store_type", "LOCAL") == "MILVUS":
            return self.store.search("dense", query, filters, k)
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
        prefix = {"TAG": "tag:", "CONCEPT": "concept:", "CODE_VALUE": "code:"}.get(alias.get("target_type"))
        if not prefix:
            return None
        doc_id = prefix + str(alias.get("target_id"))
        return next((doc for doc in self.store.docs if doc["doc_id"] == doc_id), None)

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


def visible_candidates(candidates, catalog, eligible, k):
    """HTTP 与评测共用展开/去重/截断，防止离线指标计算未返回给用户的标签。"""
    unique = {}
    for item in candidates:
        doc = item['doc']
        if doc.get('doc_type') == 'concept':
            members = [t for tid, t in catalog.tags.items() if tid in eligible and
                       str(t.get('concept_id') or t.get('concept_code')) == str(doc.get('concept_id'))]
        else:
            members = [catalog.tags[doc['tag_id']]] if doc.get('tag_id') in eligible else []
        for tag in members:
            key = (tag['tag_id'], doc.get('code'))
            unique.setdefault(key, {'tag_id': tag['tag_id'], 'name': tag.get('name'),
                                   'family_key': tag.get('family_key'), 'code': doc.get('code'),
                                   'rank_features': {key: value for key, value in item.items() if key != 'doc'}})
    return list(unique.values())[:k]
