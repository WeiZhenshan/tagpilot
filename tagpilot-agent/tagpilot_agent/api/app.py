"""受控 Agent 编排入口。检索与索引由 tagpilot-semantic 提供，本服务承载圈选工作台编排。"""

from __future__ import annotations

import hmac
import os
from typing import Callable

from fastapi import FastAPI, Header, HTTPException

from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveClient


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

    from tagpilot_agent.api.runs import register_workbench
    register_workbench(app, authenticate, retriever_for, secret)
    return app


app = create_app()
