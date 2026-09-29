"""Skill 管理接口（内部服务间调用，Bearer 服务令牌认证）。

契约见 docs/development/Skill引擎接口契约.md；只有 Java 业务层可访问，浏览器不直连。
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from tagpilot_agent.skills.builtins import register_builtin_skills
from tagpilot_agent.skills.contract import SkillBlocked
from tagpilot_agent.skills.datasource import MySqlAudienceSource
from tagpilot_agent.skills.manifest import SkillManifest, validate_manifest
from tagpilot_agent.skills.registry import SkillRegistry, SkillRegistryError
from tagpilot_agent.skills.runtime import SkillRuntime

_runtime_holder: dict[str, Any] = {}


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^(publish|offline|deprecate|draft)$")
    version: str | None = None
    operator_id: str = ""
    operator_name: str = ""
    reason: str = ""
    permissions: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience_id: str = Field(min_length=1, max_length=64)
    audience_name: str = Field(default="", max_length=120)
    member_ids: list[str] = Field(max_length=100000)
    as_of_date: str | None = None
    benchmark_type: str | None = None
    params: dict = Field(default_factory=dict)
    operator_id: str = ""
    operator_name: str = ""
    permissions: list[str] = Field(default_factory=list)
    trace_id: str | None = None


class ValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: SkillManifest


def build_runtime(source=None) -> SkillRuntime:
    """构建注册表与运行时；内置三个核心 Skill。"""
    if "runtime" not in _runtime_holder:
        registry = SkillRegistry()
        register_builtin_skills(registry)
        _runtime_holder["registry"] = registry
        _runtime_holder["runtime"] = SkillRuntime(registry, source or MySqlAudienceSource())
    elif source is not None:
        _runtime_holder["runtime"] = SkillRuntime(_runtime_holder["registry"], source)
    return _runtime_holder["runtime"]


def _split_permissions(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def register_skills(app, authenticate) -> None:
    """把 Skill 管理接口挂到既有 FastAPI 应用上。"""
    runtime = build_runtime()
    registry = runtime.registry

    @app.get("/skills", dependencies=[Depends(authenticate)])
    def list_skills(
        status: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        permissions: str | None = None,
    ):
        items = registry.list_skills(
            status=status,
            category=category,
            keyword=keyword,
            permissions=_split_permissions(permissions) if permissions is not None else None,
        )
        return {"total": len(items), "items": items}

    @app.get("/skills/recommend", dependencies=[Depends(authenticate)])
    def recommend(intent: str | None = None, permissions: str | None = None):
        return registry.recommend(intent=intent, permissions=_split_permissions(permissions))

    @app.get("/skills/runs", dependencies=[Depends(authenticate)])
    def list_runs(skill_id: str | None = None, audience_id: str | None = None, limit: int = 20):
        items = registry.list_runs(skill_id=skill_id, audience_id=audience_id, limit=limit)
        return {"total": len(items), "items": items}

    @app.get("/skills/{skill_id}", dependencies=[Depends(authenticate)])
    def skill_detail(skill_id: str, version: str | None = None):
        try:
            manifest = registry.effective_manifest(skill_id, version)
        except SkillRegistryError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        payload = manifest.model_dump()
        payload["versions"] = registry.versions(skill_id)
        payload["lifecycle"] = registry.lifecycle(skill_id)
        errors, warnings = validate_manifest(manifest)
        payload["self_check"] = {"valid": not errors, "errors": errors, "warnings": warnings}
        return payload

    @app.get("/skills/{skill_id}/versions", dependencies=[Depends(authenticate)])
    def skill_versions(skill_id: str):
        try:
            return {"skill_id": skill_id, "versions": registry.versions(skill_id)}
        except SkillRegistryError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc

    @app.post("/skills/{skill_id}/validate", dependencies=[Depends(authenticate)])
    def validate(skill_id: str, request: ValidateRequest):
        errors, warnings = validate_manifest(request.manifest)
        if request.manifest.skill_id != skill_id:
            errors.append(f"路径 skill_id({skill_id}) 与 Manifest({request.manifest.skill_id}) 不一致")
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    @app.post("/skills/{skill_id}/status", dependencies=[Depends(authenticate)])
    def change_status(skill_id: str, request: StatusRequest):
        try:
            return registry.transition(
                skill_id,
                request.version,
                request.action,
                operator_id=request.operator_id,
                operator_name=request.operator_name,
                reason=request.reason,
                permissions=request.permissions,
            )
        except SkillRegistryError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc

    @app.post("/skills/{skill_id}/run", dependencies=[Depends(authenticate)])
    def run_skill(skill_id: str, request: RunRequest):
        try:
            return runtime.run(skill_id, request.model_dump())
        except SkillBlocked as exc:
            raise HTTPException(exc.status_code, exc.reason) from exc
        except SkillRegistryError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
