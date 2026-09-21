"""受控 Agent 编排入口。检索与索引由 tagpilot-semantic 提供，本服务只做选择与 DSL 门禁。"""

from __future__ import annotations

import hmac
import os
import uuid
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from tagpilot_agent.graph import build_agent
from tagpilot_agent.retrieve_client import SemanticRetrieveClient, SemanticRetrieveError


class AgentRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=500)
    library_id: int = Field(gt=0)
    build_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,48}$")
    eligible_tag_ids: list[int] = Field(max_length=100000)


def create_app(token=None, semantic_url=None, retriever_factory: Callable | None = None):
    secret = token if token is not None else os.getenv("TAG_RUNTIME_TOKEN", "")
    semantic = (semantic_url or os.getenv("TAG_SEMANTIC_URL") or "http://127.0.0.1:8091").rstrip("/")
    app = FastAPI(title="TagPilot agent", docs_url=None, redoc_url=None)

    def authenticate(authorization: str = Header(default="")):
        if not secret:
            raise HTTPException(503, "编排层服务认证未配置")
        if not hmac.compare_digest(authorization, "Bearer " + secret):
            raise HTTPException(401, "服务认证失败")

    def retriever_for(library_id: int, build_id: str):
        if retriever_factory is not None:
            return retriever_factory(library_id, build_id)
        return SemanticRetrieveClient(semantic, secret, library_id, build_id)

    @app.get("/health")
    def health():
        return {"status": "ok", "configured": bool(secret), "semantic_url": semantic}

    @app.post("/agent/query", dependencies=[Depends(authenticate)])
    def agent_query(request: AgentRequest):
        eligible = set(request.eligible_tag_ids)
        retriever = retriever_for(request.library_id, request.build_id)
        try:
            state = build_agent(retriever).invoke({"requirement": request.requirement, "eligible_tag_ids": eligible})
            result = dict(state["result"])
        except SemanticRetrieveError as exc:
            raise HTTPException(exc.status_code if exc.status_code in {401, 409, 422, 503} else 503,
                                exc.detail if exc.status_code != 503 else "智能体选择失败；未自动执行") from exc
        except Exception as exc:
            raise HTTPException(503, "智能体选择失败；未自动执行") from exc
        referenced = {int(item["tag_id"]) for item in result.get("candidates") or []}
        referenced.update(int(tag_id) for tag_id in result.get("recommended_tag_ids") or [])
        if not referenced <= eligible:
            raise HTTPException(409, "智能体响应包含资格外标签")
        retrieval = state.get("retrieval") or {}
        result.update(trace_id=uuid.uuid4().hex, snapshot_id=retrieval.get("snapshot_id"),
                      build_id=request.build_id, artifact_hash=retrieval.get("artifact_hash"),
                      store_type=retrieval.get("store_type"), eligible_hash=retrieval.get("eligible_hash"))
        return result

    from tagpilot_agent.workbench_api import register_workbench
    register_workbench(app, authenticate, retriever_for, secret)
    return app


app = create_app()
