from fastapi.testclient import TestClient
from tagpilot_agent.server import create_app
from tests.test_agent_graph import FakeRetrieve


def test_agent_http_auth_identity_and_no_auto_execute():
    app = create_app(token="test-service-token", retriever_factory=lambda library_id, build_id: FakeRetrieve())
    client = TestClient(app)
    request = {"requirement": "近30天转入至少50万", "library_id": 107, "build_id": "b1", "eligible_tag_ids": [1]}
    assert client.post("/agent/query", json=request).status_code == 401
    headers = {"Authorization": "Bearer test-service-token"}
    result = client.post("/agent/query", json=request, headers=headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["auto_execute"] is False
    assert body["requires_confirmation"] is True
    assert body["snapshot_id"] == "s1"
    assert body["build_id"] == "b1"
    assert body["store_type"] == "LOCAL"
    assert {c["tag_id"] for c in body["candidates"]} <= {1}


def test_agent_rejects_out_of_eligibility_recommendation():
    class BadRetrieve(FakeRetrieve):
        def retrieve(self, requirement, eligible, k=20):
            payload = super().retrieve(requirement, eligible, k)
            payload["candidates"] = [{"tag_id": 2, "name": "越权"}]
            payload["catalog"].tags[2] = {"tag_id": 2, "name": "越权", "semantic_type": "BOOL", "allowed_operators": ["="], "aliases": []}
            return payload
    app = create_app(token="test", retriever_factory=lambda library_id, build_id: BadRetrieve())
    client = TestClient(app)
    request = {"requirement": "越权", "library_id": 107, "build_id": "b1", "eligible_tag_ids": [1]}
    result = client.post("/agent/query", json=request, headers={"Authorization": "Bearer test"})
    assert result.status_code == 409
