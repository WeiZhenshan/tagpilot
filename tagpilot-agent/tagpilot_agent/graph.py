"""LangGraph 受控选择图；LLM 不拥有授权、校验、写入或自动执行能力。"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from tagpilot_agent.dsl import validate_dsl


class Retriever(Protocol):
    def retrieve(self, requirement: str, eligible_tag_ids: set[int], k: int = 20) -> dict[str, Any]: ...


class Selector(Protocol):
    name: str

    def select(self, requirement: str, candidates: list[dict[str, Any]], catalog) -> dict[str, Any] | None: ...


class OpenAICompatibleSelector:
    """面向本地或远端 OpenAI-compatible 服务；只发送已过滤候选，不发送全库或客户数据。"""

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.name = f"openai-compatible:{model}"

    def select(self, requirement, candidates, catalog):
        allowed = []
        for candidate in candidates[:20]:
            tag = catalog.tags[int(candidate["tag_id"])]
            allowed.append({
                "tag_id": int(tag["tag_id"]), "name": tag.get("name"), "definition": tag.get("definition_long"),
                "semantic_type": tag.get("semantic_type"), "allowed_operators": tag.get("allowed_operators"),
                "codes": [{"code": str(c["code"]), "label": c.get("label"), "definition": c.get("definition")}
                          for c in catalog.code_values if int(c["tag_id"]) == int(tag["tag_id"])],
            })
        instruction = (
            "你是银行个人客户经营标签选择器。只能使用 candidates 中的 tag_id/code/operator。"
            "输出单个 JSON 对象：{decision, confidence, explanation, dsl}。"
            "不明确则 decision=CLARIFY 且 dsl=null；禁止生成 SQL，禁止补造标签。"
        )
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = "Bearer " + self.api_key
        response = httpx.post(
            self.base_url + "/v1/chat/completions", headers=headers, timeout=self.timeout,
            json={"model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": instruction},
                               {"role": "user", "content": json.dumps({"requirement": requirement, "candidates": allowed}, ensure_ascii=False)}]},
        )
        response.raise_for_status()
        return json.loads(response.json()["choices"][0]["message"]["content"])


class ExactEvidenceSelector:
    """无生成式模型时的显式演示后备：只接受唯一的标签名称/别名证据。"""

    name = "exact-evidence-offline"

    def select(self, requirement, candidates, catalog):
        normalized = "".join(requirement.lower().split())
        exact = []
        candidate_ids = {int(c["tag_id"]) for c in candidates}
        for tag_id in candidate_ids:
            tag = catalog.tags[tag_id]
            names = {str(tag.get("name") or "")}
            names.update(str(a.get("alias_text") or "") for a in tag.get("aliases") or [] if a.get("review_status") == "REVIEWED")
            matched = ["".join(name.lower().split()) for name in names if name and "".join(name.lower().split()) in normalized]
            if matched:
                exact.append((max(map(len, matched)), tag))
        if len(exact) != 1:
            if not exact:
                return None
            longest = max(length for length, _ in exact)
            exact = [item for item in exact if item[0] == longest]
            if len(exact) != 1:
                return None
        tag = exact[0][1]
        semantic_type = tag.get("semantic_type")
        operator = "=" if semantic_type in {"BOOL", "ENUM_NOMINAL", "ENUM_ORDINAL", "ENUM_HIERARCHY"} else None
        dsl = None
        if str(semantic_type).startswith("NUM_"):
            import re
            from decimal import Decimal
            boundary = re.search(r"(至少|不低于|大于等于|超过|高于|大于|不超过|不高于|小于等于|低于|小于)\s*(\d+(?:\.\d+)?)\s*(亿|万)?", normalized)
            if boundary:
                word, number, magnitude = boundary.groups()
                operator = {"至少": ">=", "不低于": ">=", "大于等于": ">=", "超过": ">", "高于": ">", "大于": ">",
                            "不超过": "<=", "不高于": "<=", "小于等于": "<=", "低于": "<", "小于": "<"}[word]
                value = Decimal(number) * {None: 1, "万": 10000, "亿": 100000000}[magnitude]
                dsl = {"logic": "AND", "conditions": [{"tag_id": int(tag["tag_id"]), "operator": operator,
                                                            "value": int(value) if value == value.to_integral() else float(value)}]}
        # 标签名本身不携带安全可执行的值；只给出标签建议，不伪造条件。
        return {"decision": "RECOMMEND" if dsl else "NEEDS_VALUE", "confidence": 1.0, "explanation": "唯一已复核名称或别名精确命中",
                "recommended_tag_ids": [int(tag["tag_id"])], "operator_hint": operator, "dsl": dsl}


class AgentState(TypedDict, total=False):
    requirement: str
    eligible_tag_ids: set[int]
    retrieval: dict[str, Any]
    candidates: list[dict[str, Any]]
    catalog: Any
    proposal: dict[str, Any] | None
    validated_dsl: dict[str, Any] | None
    validation_error: str | None
    result: dict[str, Any]


def selector_from_env() -> Selector:
    base_url = os.getenv("TAG_LLM_BASE_URL", "")
    model = os.getenv("TAG_LLM_MODEL", "")
    if base_url and model:
        return OpenAICompatibleSelector(base_url, model, os.getenv("TAG_LLM_API_KEY", ""))
    return ExactEvidenceSelector()


def build_agent(retriever: Retriever, selector: Selector | None = None):
    selector = selector or selector_from_env()

    def retrieve_node(state: AgentState):
        response = retriever.retrieve(state["requirement"], state["eligible_tag_ids"], 20)
        return {"retrieval": response, "candidates": response.get("candidates") or [], "catalog": response["catalog"]}

    def select_node(state: AgentState):
        if state["retrieval"].get("decision") in {"CLARIFY", "INEXPRESSIBLE"}:
            return {"proposal": None}
        return {"proposal": selector.select(state["requirement"], state["candidates"], state["catalog"])}

    def validate_node(state: AgentState):
        proposal = state.get("proposal") or {}
        if not proposal.get("dsl"):
            return {"validated_dsl": None, "validation_error": None}
        try:
            dsl = validate_dsl(proposal["dsl"], state["catalog"], state["eligible_tag_ids"])
            return {"validated_dsl": dsl.model_dump(mode="json"), "validation_error": None}
        except Exception as exc:
            return {"validated_dsl": None, "validation_error": str(exc)}

    def finalize_node(state: AgentState):
        retrieval_decision = state["retrieval"].get("decision", "CANDIDATES_ONLY")
        proposal = state.get("proposal") or {}
        if retrieval_decision in {"CLARIFY", "INEXPRESSIBLE"}:
            decision = retrieval_decision
        elif state.get("validation_error"):
            decision = "REJECTED_BY_DSL_GATE"
        elif state.get("validated_dsl"):
            decision = "NEEDS_CONFIRMATION"
        elif proposal:
            decision = proposal.get("decision", "CANDIDATES_ONLY")
        else:
            decision = "CANDIDATES_ONLY"
        return {"result": {"decision": decision, "selector": selector.name, "model_connected": not isinstance(selector, ExactEvidenceSelector),
                           "confidence": proposal.get("confidence"), "explanation": proposal.get("explanation"),
                           "recommended_tag_ids": proposal.get("recommended_tag_ids") or [],
                           "dsl": state.get("validated_dsl"), "dsl_valid": state.get("validated_dsl") is not None,
                           "validation_error": state.get("validation_error"), "candidates": state["candidates"],
                           "auto_execute": False, "requires_confirmation": True}}

    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("select", select_node)
    graph.add_node("validate_dsl", validate_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "select")
    graph.add_edge("select", "validate_dsl")
    graph.add_edge("validate_dsl", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
