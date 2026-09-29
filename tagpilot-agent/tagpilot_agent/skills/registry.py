"""Skill Registry：注册、版本、生命周期状态机、权限过滤、场景包推荐与运行留痕。

状态机（对齐方案 4.13 生命周期治理）：
    draft ──publish──▶ published ──offline──▶ offline
      ▲                   │  │                  │
      │                   │  └─deprecate─▶ deprecated ──publish──▶ published
      └───────────────────┘                              └─offline──▶ offline

注册表只接受通过 Manifest 深度校验的 Skill；发布动作会执行质量门禁并记录到生命周期事件。
"""

from __future__ import annotations

import copy
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from tagpilot_agent.skills.manifest import SkillManifest, validate_manifest


class SkillRegistryError(Exception):
    """注册表错误：校验失败、找不到 Skill、非法状态流转。"""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


TRANSITIONS: dict[str, dict[str, str]] = {
    "publish": {"draft": "published", "deprecated": "published", "offline": "published"},
    "offline": {"published": "offline", "deprecated": "offline"},
    "deprecate": {"published": "deprecated"},
    "draft": {"offline": "draft"},
}

SCENARIO_PACKS: dict[str, dict] = {
    "large_inflow_conversion": {
        "id": "large_inflow_conversion",
        "name": "大额入金转化场景包",
        "skill_ids": [
            "audience_asset_structure",
            "product_holding_gap",
            "marketing_opportunity_priority",
        ],
        "intent": "AUDIENCE_SELECTION_AND_ANALYSIS",
        "description": "先看结构、再看缺口、最后排优先级，形成可执行的营销机会清单。",
    },
    "dormant_reactivation": {
        "id": "dormant_reactivation",
        "name": "沉睡客户激活场景包",
        "skill_ids": ["audience_asset_structure", "marketing_opportunity_priority"],
        "intent": "AUDIENCE_SELECTION_AND_ANALYSIS",
        "description": "先看资产与活跃结构，再按可解释规则排优先级。",
    },
}


@dataclass
class RegisteredSkill:
    manifest: SkillManifest
    executor: Callable


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class SkillRegistry:
    def __init__(self, storage_path: str | None = None, db_path: str | None = None):
        self._skills: dict[str, dict[str, RegisteredSkill]] = {}
        self._lock = threading.RLock()
        self._path = self._resolve_path(storage_path or db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_store()

    # ---------- 存储 ----------

    @staticmethod
    def _resolve_path(explicit: str | None) -> Path:
        if explicit:
            return Path(explicit).resolve()
        env = os.getenv("TAG_SKILL_DB")
        if env:
            return Path(env).resolve()
        agent_db = os.getenv("TAG_AGENT_DB")
        if agent_db:
            return Path(agent_db).resolve().parent / "skill-registry.sqlite"
        return Path("./data/agent/skill-registry.sqlite").resolve()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_store(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS skill_lifecycle (
                    event_id      TEXT PRIMARY KEY,
                    skill_id      TEXT NOT NULL,
                    version       TEXT NOT NULL,
                    action        TEXT NOT NULL,
                    from_status   TEXT NOT NULL,
                    to_status     TEXT NOT NULL,
                    operator_id   TEXT NOT NULL DEFAULT '',
                    operator_name TEXT NOT NULL DEFAULT '',
                    reason        TEXT NOT NULL DEFAULT '',
                    gate          TEXT NOT NULL DEFAULT '',
                    changed_at    TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_skill_lifecycle ON skill_lifecycle (skill_id, version, changed_at);
                CREATE TABLE IF NOT EXISTS skill_run (
                    run_id          TEXT PRIMARY KEY,
                    skill_id        TEXT NOT NULL,
                    skill_version   TEXT NOT NULL,
                    audience_id     TEXT NOT NULL DEFAULT '',
                    audience_name   TEXT NOT NULL DEFAULT '',
                    customer_count  INTEGER NOT NULL DEFAULT 0,
                    status          TEXT NOT NULL,
                    blocked_reason  TEXT NOT NULL DEFAULT '',
                    duration_ms     INTEGER NOT NULL DEFAULT 0,
                    operator_id     TEXT NOT NULL DEFAULT '',
                    operator_name   TEXT NOT NULL DEFAULT '',
                    trace_id        TEXT NOT NULL DEFAULT '',
                    created_at      TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_skill_run ON skill_run (skill_id, audience_id, created_at);
                """
            )

    # ---------- 注册 ----------

    def register(self, manifest: SkillManifest, executor: Callable) -> SkillManifest:
        errors, _warnings = validate_manifest(manifest)
        if errors:
            raise SkillRegistryError("Skill Manifest 校验失败：" + "；".join(errors), status_code=422)
        if not callable(executor):
            raise SkillRegistryError("executor 必须可调用", status_code=422)
        with self._lock:
            versions = self._skills.setdefault(manifest.skill_id, {})
            if manifest.version in versions:
                raise SkillRegistryError(f"版本已注册：{manifest.skill_id}@{manifest.version}", status_code=409)
            versions[manifest.version] = RegisteredSkill(manifest=manifest, executor=executor)
        return manifest

    # ---------- 查询 ----------

    def get(self, skill_id: str, version: str | None = None) -> RegisteredSkill:
        with self._lock:
            versions = self._skills.get(skill_id)
            if not versions:
                raise SkillRegistryError(f"技能不存在：{skill_id}", status_code=404)
            if version:
                skill = versions.get(version)
                if skill is None:
                    raise SkillRegistryError(f"技能版本不存在：{skill_id}@{version}", status_code=404)
                return skill
            published = [v for v in versions.values() if self._status_of(v.manifest) == "published"]
            pool = published or list(versions.values())
            return max(pool, key=lambda item: _semver_key(item.manifest.version))

    def _status_of(self, manifest: SkillManifest) -> str:
        events = self._lifecycle(manifest.skill_id, manifest.version)
        return events[-1]["to_status"] if events else manifest.status

    def effective_manifest(self, skill_id: str, version: str | None = None) -> SkillManifest:
        skill = self.get(skill_id, version)
        manifest = skill.manifest.model_copy(deep=True)
        manifest.status = self._status_of(skill.manifest)
        return manifest

    def list_skills(
        self,
        status: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        permissions: Iterable[str] | None = None,
    ) -> list[dict]:
        caller = set(permissions or [])
        wildcard = bool(caller & {"*", "*:*:*"})
        items: list[dict] = []
        with self._lock:
            for skill_id in self._skills:
                manifest = self.effective_manifest(skill_id)
                if status and manifest.status != status:
                    continue
                if category and manifest.category != category:
                    continue
                if keyword:
                    needle = keyword.strip().lower()
                    haystack = f"{manifest.skill_id} {manifest.name} {manifest.description} {manifest.owner}".lower()
                    if needle not in haystack:
                        continue
                # permissions=None 表示管理视角（不过滤）；显式传入空集则严格过滤
                if (
                    permissions is not None
                    and not wildcard
                    and not set(manifest.preconditions.required_permissions) <= caller
                ):
                    continue
                summary = manifest.summary()
                summary["updated_at"] = self._last_changed_at(skill_id, manifest.version) or manifest.version
                items.append(summary)
        items.sort(key=lambda row: (row["layer"], row["skill_id"]))
        return items

    def versions(self, skill_id: str) -> list[dict]:
        with self._lock:
            versions = self._skills.get(skill_id)
            if not versions:
                raise SkillRegistryError(f"技能不存在：{skill_id}", status_code=404)
            rows = []
            for version in sorted(versions, key=_semver_key, reverse=True):
                events = self._lifecycle(skill_id, version)
                rows.append(
                    {
                        "version": version,
                        "status": events[-1]["to_status"] if events else versions[version].manifest.status,
                        "changed_at": events[-1]["changed_at"] if events else None,
                        "reason": events[-1]["reason"] if events else "内置注册",
                    }
                )
            return rows

    # ---------- 生命周期 ----------

    def transition(
        self,
        skill_id: str,
        version: str | None,
        action: str,
        operator_id: str = "",
        operator_name: str = "",
        reason: str = "",
        permissions: Iterable[str] | None = None,
    ) -> dict:
        if action not in TRANSITIONS:
            raise SkillRegistryError(f"不支持的生命周期动作：{action}", status_code=422)
        skill = self.get(skill_id, version)
        manifest = skill.manifest
        current = self._status_of(manifest)
        target = TRANSITIONS[action].get(current)
        if target is None:
            allowed = "、".join(sorted(TRANSITIONS[a].get(current, "") for a in TRANSITIONS if current in TRANSITIONS[a]))
            raise SkillRegistryError(
                f"非法状态流转：{current} 不能执行 {action}（当前状态允许：{allowed or '无'}）", status_code=409
            )

        caller = set(permissions or [])
        if caller and "*" not in caller and not set(manifest.preconditions.required_permissions) <= caller:
            raise SkillRegistryError("当前用户对该技能没有管理权限", status_code=403)

        gate = ""
        if action == "publish":
            errors, warnings = validate_manifest(manifest)
            if errors:
                raise SkillRegistryError("质量门禁未通过：" + "；".join(errors), status_code=409)
            gate = "manifest_valid;validators=" + ",".join(manifest.validators)
            if warnings:
                gate += ";warnings=" + ",".join(warnings)

        event = {
            "event_id": uuid.uuid4().hex,
            "skill_id": skill_id,
            "version": manifest.version,
            "action": action,
            "from_status": current,
            "to_status": target,
            "operator_id": str(operator_id or ""),
            "operator_name": str(operator_name or ""),
            "reason": (reason or "")[:200],
            "gate": gate,
            "changed_at": _now(),
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO skill_lifecycle (event_id, skill_id, version, action, from_status, to_status,"
                " operator_id, operator_name, reason, gate, changed_at)"
                " VALUES (:event_id, :skill_id, :version, :action, :from_status, :to_status,"
                " :operator_id, :operator_name, :reason, :gate, :changed_at)",
                event,
            )
        return {
            "skill_id": skill_id,
            "version": manifest.version,
            "status": target,
            "from_status": current,
            "action": action,
            "changed_at": event["changed_at"],
            "gate": gate,
        }

    def _lifecycle(self, skill_id: str, version: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skill_lifecycle WHERE skill_id = ? AND version = ? ORDER BY changed_at, rowid",
                (skill_id, version),
            ).fetchall()
        return [dict(row) for row in rows]

    def lifecycle(self, skill_id: str, version: str | None = None) -> list[dict]:
        skill = self.get(skill_id, version)
        return self._lifecycle(skill_id, skill.manifest.version)

    def _last_changed_at(self, skill_id: str, version: str) -> str | None:
        events = self._lifecycle(skill_id, version)
        return events[-1]["changed_at"] if events else None

    # ---------- 场景包推荐 ----------

    def recommend(self, intent: str | None = None, permissions: Iterable[str] | None = None) -> dict:
        pack_id = "large_inflow_conversion"
        for candidate in SCENARIO_PACKS.values():
            if intent and candidate["intent"] == intent:
                pack_id = candidate["id"]
                break
        pack = copy.deepcopy(SCENARIO_PACKS[pack_id])
        caller = set(permissions or [])
        visible: list[dict] = []
        for skill_id in pack["skill_ids"]:
            try:
                manifest = self.effective_manifest(skill_id)
            except SkillRegistryError:
                continue
            if caller and "*" not in caller and not set(manifest.preconditions.required_permissions) <= caller:
                continue
            visible.append(manifest.summary())
        return {
            "scenario_pack": pack,
            "skills": visible,
            "reason": "按客群圈选目的推荐 L1 事实 → L2 诊断 → L3 行动的组合，全部为已发布且当前用户可见的技能",
        }

    # ---------- 运行留痕 ----------

    def record_run(self, row: dict) -> None:
        payload = {
            "run_id": row["run_id"],
            "skill_id": row["skill_id"],
            "skill_version": row.get("skill_version", ""),
            "audience_id": str(row.get("audience_id", "")),
            "audience_name": row.get("audience_name", "") or "",
            "customer_count": int(row.get("customer_count") or 0),
            "status": row.get("status", "succeeded"),
            "blocked_reason": (row.get("blocked_reason") or "")[:500],
            "duration_ms": int(row.get("duration_ms") or 0),
            "operator_id": str(row.get("operator_id", "")),
            "operator_name": row.get("operator_name", "") or "",
            "trace_id": row.get("trace_id", "") or "",
            "created_at": row.get("created_at") or _now(),
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO skill_run (run_id, skill_id, skill_version, audience_id, audience_name,"
                " customer_count, status, blocked_reason, duration_ms, operator_id, operator_name, trace_id, created_at)"
                " VALUES (:run_id, :skill_id, :skill_version, :audience_id, :audience_name, :customer_count,"
                " :status, :blocked_reason, :duration_ms, :operator_id, :operator_name, :trace_id, :created_at)",
                payload,
            )

    def list_runs(
        self, skill_id: str | None = None, audience_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        sql = "SELECT * FROM skill_run WHERE 1 = 1"
        params: list = []
        if skill_id:
            sql += " AND skill_id = ?"
            params.append(skill_id)
        if audience_id:
            sql += " AND audience_id = ?"
            params.append(str(audience_id))
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        params.append(max(1, min(int(limit or 20), 200)))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def run_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM skill_run").fetchone()[0])


def _semver_key(version: str) -> tuple[int, int, int]:
    try:
        major, minor, patch = (int(part) for part in version.split("."))
        return major, minor, patch
    except (ValueError, AttributeError):
        return 0, 0, 0
