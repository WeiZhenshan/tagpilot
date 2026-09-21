"""调用 tagpilot-semantic /retrieve；失败不降级、不本地检索。"""

from __future__ import annotations

from typing import Any

import httpx

from tagpilot_agent.catalog import SliceCatalog


class SemanticRetrieveError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class SemanticRetrieveClient:
    def __init__(self, base_url: str, token: str, library_id: int, build_id: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.library_id = library_id
        self.build_id = build_id
        self.timeout = timeout

    def retrieve(self, requirement: str, eligible_tag_ids: set[int], k: int = 20) -> dict[str, Any]:
        response = httpx.post(
            self.base_url + "/retrieve",
            headers={"authorization": "Bearer " + self.token, "content-type": "application/json"},
            timeout=self.timeout,
            json={"requirement": requirement, "library_id": self.library_id, "build_id": self.build_id,
                  "eligible_tag_ids": [int(tag_id) for tag_id in eligible_tag_ids], "k": k},
        )
        if response.status_code >= 400:
            detail = response.text
            try:
                payload = response.json()
                detail = str(payload.get("detail") or detail)
            except Exception:
                pass
            raise SemanticRetrieveError(response.status_code, detail)
        data = response.json()
        data["catalog"] = SliceCatalog(data.get("selection_context") or {})
        return data

    def evidence(self, tag_ids: list[int], requirement: str, eligible: set[int]) -> dict:
        response = httpx.post(self.base_url + "/evidence", timeout=self.timeout,
            headers={"authorization": "Bearer " + self.token},
            json={"requirement": requirement[:500] or "标签详情", "library_id": self.library_id,
                  "build_id": self.build_id, "eligible_tag_ids": sorted(eligible), "tag_ids": tag_ids})
        if response.status_code >= 400:
            raise SemanticRetrieveError(response.status_code, "发布证据读取失败")
        return response.json()
