import asyncio
import httpx
from fastapi.testclient import TestClient
from tagpilot_agent.api.app import create_app
from tagpilot_agent.runtime.title_model import fallback_title, sanitize_title, summarize_title


def test_fallback_and_sanitize():
    assert fallback_title("") == "新对话"
    assert fallback_title("  跨行资金转入客户  ") == "跨行资金转入客户"
    assert fallback_title("a" * 50) == "a" * 40
    assert sanitize_title('"跨行资金转入"', "原文") == "跨行资金转入"
    assert sanitize_title("标题：高净值客户", "原文") == "高净值客户"
    assert sanitize_title("太长" * 30, "截断原文消息内容") == "截断原文消息内容"[:40]
    assert sanitize_title("", "首条消息") == "首条消息"


def test_summarize_title_uses_model_text(monkeypatch):
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"content": [{"type": "text", "text": "跨行资金转入客户"}]}

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def post(self, *args, **kwargs): return FakeResponse()

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://fake.invalid")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("ANTHROPIC_MODEL", "fake-model")
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    assert asyncio.run(summarize_title("帮我圈选近30天有跨行资金转入的客户")) == "跨行资金转入客户"


def test_summarize_title_falls_back_on_http_error(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def post(self, *args, **kwargs): raise httpx.ConnectError("down")

    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://fake.invalid")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    assert asyncio.run(summarize_title("帮我圈选高净值客户")) == "帮我圈选高净值客户"


def test_title_endpoint_returns_summarized_title(tmp_path, monkeypatch):
    monkeypatch.setenv("TAG_AGENT_DB", str(tmp_path / "runs.sqlite"))

    async def fake_summarize(message):
        assert "跨行" in message
        return "跨行资金转入"

    monkeypatch.setattr("tagpilot_agent.runtime.title_model.summarize_title", fake_summarize)
    app = create_app(token="controlled-test-secret", retriever_factory=lambda *_: None)
    headers = {"Authorization": "Bearer controlled-test-secret"}
    with TestClient(app) as client:
        assert client.post("/agent/v2/title", json={"message": "跨行资金转入客户"}).status_code == 401
        body = client.post("/agent/v2/title", headers=headers, json={"message": "跨行资金转入客户"}).json()
        assert body == {"title": "跨行资金转入"}
        assert client.post("/agent/v2/title", headers=headers, json={"message": ""}).status_code == 422
