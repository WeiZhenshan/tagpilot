"""独立洞察库：只接受聚合事实，无数据库、HTTP 或 Agent SDK 依赖。"""

from .contracts import InsightReport, Manifest, MetricQuery
from .guards import GuardError, validate_report

__all__ = ["InsightReport", "Manifest", "MetricQuery", "GuardError", "validate_report"]
