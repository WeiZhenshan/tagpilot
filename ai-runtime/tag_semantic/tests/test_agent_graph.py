from tag_semantic.agent.dsl import validate_dsl
from tag_semantic.agent.graph import build_agent


class FakeSelector:
    name = "fake-llm"
    def select(self, requirement, candidates, catalog):
        return {"decision": "RECOMMEND", "confidence": .999,
                "explanation": "仅从候选选择", "recommended_tag_ids": [1],
                "dsl": {"logic": "AND", "conditions": [{"tag_id": 1, "operator": ">=", "value": 500000}]}}


class FakeRetrieve:
    def __init__(self):
        self.catalog = type("Catalog", (), {})()
        self.catalog.tags = {1: {"tag_id": 1, "name": "近30天转入金额", "semantic_type": "NUM_AMOUNT",
                                 "allowed_operators": [">", ">=", "<", "<=", "between"], "family_key": "FLOW"}}
        self.catalog.code_values = []
        self.catalog.terms = []
    def retrieve(self, requirement, eligible, k):
        return {"decision": "CANDIDATES_ONLY", "candidates": [{"doc": {"doc_type": "tag", "tag_id": 1}, "rrf_score": 1}],
                "facets": {}, "family": {}, "auto_execute": False}


def test_agent_keeps_llm_inside_candidate_and_dsl_gates():
    result = build_agent(FakeRetrieve(), FakeSelector()).invoke({"requirement": "近30天转入至少50万", "eligible_tag_ids": {1}})["result"]
    assert result["decision"] == "NEEDS_CONFIRMATION"
    assert result["dsl_valid"] is True
    assert result["auto_execute"] is False
    assert result["requires_confirmation"] is True


def test_dsl_rejects_unauthorized_tag():
    service = FakeRetrieve()
    try:
        validate_dsl({"logic": "AND", "conditions": [{"tag_id": 1, "operator": ">=", "value": 1}]}, service.catalog, set())
    except ValueError as exc:
        assert "资格外" in str(exc)
    else:
        raise AssertionError("资格外标签必须拒绝")
