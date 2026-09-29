"""Skill 数据源：客群成员标签明细与基准客群聚合。

数据来自标签宽表 `ry.ind_tag_data`（67 个字段，全部是标签与统计口径字段，不含姓名等直接标识）。
只读取聚合所需列，输出到洞察与图表的永远是聚合值；明细仅在进程内用于确定性计算。

治理说明：
  * 本类实现 `AudienceDataSource` 协议，默认实现为本地开发直连（mock 宽表）；
  * 生产环境可替换为聚合服务实现（只接收聚合结果），Skill 计算代码无需改动。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Protocol

# Skill 计算所需列（显式声明，避免 SELECT * 越权取数）
AUDIENCE_COLUMNS: tuple[str, ...] = (
    "cust_id",
    "aum_balance",
    "aum_level",
    "avg_daily_deposit",
    "contribution_score",
    "clv_score",
    "cross_sell_index",
    "has_deposit",
    "has_wealth",
    "has_fund",
    "has_insurance",
    "has_credit_card",
    "has_loan",
    "has_forex",
    "has_precious_metal",
    "has_trust",
    "total_products_count",
    "risk_rating",
    "risk_tolerance",
    "channel_preference",
    "is_mobile_banking_user",
    "is_online_banking_user",
    "is_wechat_banking_user",
    "transaction_frequency_monthly",
    "transaction_amt_monthly",
    "online_login_freq_monthly",
    "counter_visit_freq_quarterly",
    "is_active_cust",
    "is_salary_cust",
    "cust_segment",
    "branch_code",
    "region",
    "age",
    "age_group",
    "occupation_type",
    "city_tier",
    "annual_income_k",
    "loyalty_years",
    "loyalty_level",
    "contribution_level",
    "blacklist_flag",
    "fraud_alert_flag",
    "kyc_status",
    "last_transaction_date",
)

MAX_SCOPE_ROWS = 200000

# 标签宽表相对客群源的客户号前缀（ind_tag_data.C010001 ↔ cust_wide.10001）
ID_PREFIX = os.getenv("TAG_SKILL_ID_PREFIX", "C0")


class SkillDataNotReady(Exception):
    """数据不就绪：缺表、缺列、数据陈旧或客群为空。"""


class AudienceDataSource(Protocol):
    def fetch_audience(self, member_ids: Iterable[str]) -> list[dict]:
        """按成员 ID 取标签明细。"""

    def fetch_scope(self, benchmark_type: str, audience_rows: list[dict]) -> list[dict]:
        """取基准客群明细。"""

    def count_audience(self, member_ids: Iterable[str]) -> int:
        """独立计数（用于数值对账）。"""

    def data_as_of(self) -> str:
        """数据日期（用于边界与新鲜度校验）。"""


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(float(str(value).strip() or 0))
    except ValueError:
        return 0


def _expand_ids(member_ids: Iterable[str]) -> list[str]:
    """客群成员编号兼容：客群源与标签宽表可能存在两套编号体系。

    当前环境的映射为 `10001`(客群源 cust_wide) ↔ `C010001`(标签宽表 ind_tag_data)，
    即标签库编号比客群源多一个 ID_PREFIX 前缀。这里做双向展开，避免上层强绑定具体编号规则。
    """
    expanded: set[str] = set()
    for item in member_ids:
        raw = str(item or "").strip()
        if not raw:
            continue
        expanded.add(raw)
        if raw.isdigit():
            expanded.add(ID_PREFIX + raw)
        elif raw.startswith(ID_PREFIX) and raw[len(ID_PREFIX) :].isdigit():
            expanded.add(raw[len(ID_PREFIX) :])
    return sorted(expanded)


def _dedupe_by_cust_id(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        key = str(row.get("cust_id") or "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


@dataclass
class MySqlAudienceSource:
    """本地开发实现：直连 MySQL 标签宽表，取数后交给确定性代码聚合。"""

    host: str = os.getenv("TAG_SKILL_DB_HOST", "127.0.0.1")
    port: int = int(os.getenv("TAG_SKILL_DB_PORT", "3306") or 3306)
    user: str = os.getenv("TAG_SKILL_DB_USER", "root")
    password: str = os.getenv("TAG_SKILL_DB_PASSWORD", "")
    database: str = os.getenv("TAG_SKILL_DB_NAME", "ry")
    table: str = os.getenv("TAG_SKILL_DB_TABLE", "ind_tag_data")
    as_of: str | None = None

    def _connect(self):
        try:
            import pymysql
        except ImportError as exc:  # pragma: no cover - 依赖缺失时给出可操作提示
            raise SkillDataNotReady("缺少 MySQL 驱动 pymysql，请执行 uv sync --project tagpilot-agent") from exc
        try:
            return pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5,
                read_timeout=30,
            )
        except Exception as exc:  # pragma: no cover
            raise SkillDataNotReady(f"指标数据库不可用：{exc}") from exc

    def _columns(self) -> list[str]:
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT column_name AS column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s",
                (self.database, self.table),
            )
            columns: list[str] = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    # DictCursor 的键名大小写取决于驱动与元数据查询（information_schema 常返回大写）
                    name = next(
                        (value for key, value in row.items() if str(key).lower() == "column_name"), None
                    )
                    if name is None:
                        continue
                else:
                    name = row[0]
                columns.append(str(name).lower())
            return columns

    def _ensure_columns(self) -> list[str]:
        available = self._columns()
        if not available:
            raise SkillDataNotReady(f"标签宽表不存在：{self.database}.{self.table}")
        missing = [column for column in AUDIENCE_COLUMNS if column not in available]
        if missing:
            raise SkillDataNotReady("标签宽表缺少 Skill 所需字段：" + "、".join(missing))
        return available

    def _select(self, where_sql: str, params: list) -> list[dict]:
        columns = ", ".join(f"`{column}`" for column in AUDIENCE_COLUMNS)
        sql = f"SELECT {columns} FROM `{self.table}` {where_sql} LIMIT %s"
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute(sql, [*params, MAX_SCOPE_ROWS])
            rows = cursor.fetchall()
        return [self._normalize(row) for row in rows]

    @staticmethod
    def _normalize(row: dict) -> dict:
        row = dict(row)
        row["cust_id"] = str(row.get("cust_id") or "")
        for key in ("aum_balance", "avg_daily_deposit", "annual_income_k", "transaction_amt_monthly", "loyalty_years"):
            row[key] = _to_float(row.get(key))
        for key in (
            "has_deposit", "has_wealth", "has_fund", "has_insurance", "has_credit_card", "has_loan",
            "has_forex", "has_precious_metal", "has_trust", "is_mobile_banking_user",
            "is_online_banking_user", "is_wechat_banking_user", "is_active_cust", "is_salary_cust",
            "blacklist_flag", "fraud_alert_flag",
        ):
            row[key] = _to_int(row.get(key))
        for key in (
            "contribution_score", "clv_score", "cross_sell_index", "total_products_count", "age",
            "city_tier", "transaction_frequency_monthly", "online_login_freq_monthly",
            "counter_visit_freq_quarterly",
        ):
            row[key] = _to_int(row.get(key))
        return row

    def fetch_audience(self, member_ids: Iterable[str]) -> list[dict]:
        ids = _expand_ids(member_ids)
        if not ids:
            return []
        self._ensure_columns()
        rows: list[dict] = []
        batch = 2000
        for start in range(0, len(ids), batch):
            chunk = ids[start : start + batch]
            placeholders = ", ".join(["%s"] * len(chunk))
            rows.extend(self._select(f"WHERE cust_id IN ({placeholders})", list(chunk)))
        # 同一客户可能被多种编号写法命中，按 cust_id 去重后返回
        return _dedupe_by_cust_id(rows)

    def count_audience(self, member_ids: Iterable[str]) -> int:
        ids = _expand_ids(member_ids)
        if not ids:
            return 0
        total = 0
        batch = 2000
        with self._connect() as conn, conn.cursor() as cursor:
            for start in range(0, len(ids), batch):
                chunk = ids[start : start + batch]
                placeholders = ", ".join(["%s"] * len(chunk))
                cursor.execute(
                    f"SELECT COUNT(*) AS c FROM `{self.table}` WHERE cust_id IN ({placeholders})", list(chunk)
                )
                row = cursor.fetchone()
                total += int(row["c"] if isinstance(row, dict) else row[0])
        return total

    def fetch_scope(self, benchmark_type: str, audience_rows: list[dict]) -> list[dict]:
        self._ensure_columns()
        if benchmark_type == "SAME_AUM_BAND":
            levels = sorted({str(row.get("aum_level") or "") for row in audience_rows if row.get("aum_level")})
            if not levels:
                return self._select("WHERE 1 = 1", [])
            placeholders = ", ".join(["%s"] * len(levels))
            return self._select(f"WHERE aum_level IN ({placeholders})", list(levels))
        if benchmark_type == "SAME_RISK_LEVEL":
            levels = sorted({str(row.get("risk_tolerance") or "") for row in audience_rows if row.get("risk_tolerance")})
            if not levels:
                return self._select("WHERE 1 = 1", [])
            placeholders = ", ".join(["%s"] * len(levels))
            return self._select(f"WHERE risk_tolerance IN ({placeholders})", list(levels))
        return self._select("WHERE 1 = 1", [])

    def data_as_of(self) -> str:
        if self.as_of:
            return self.as_of
        env = os.getenv("TAG_SKILL_DATA_AS_OF")
        if env:
            return env
        today = date.today()
        try:
            with self._connect() as conn, conn.cursor() as cursor:
                cursor.execute(f"SELECT MAX(last_transaction_date) AS d FROM `{self.table}`")
                row = cursor.fetchone()
                value = row["d"] if isinstance(row, dict) else row[0]
                if isinstance(value, datetime):
                    return value.date().isoformat()
                if isinstance(value, date):
                    return value.isoformat()
                if value:
                    return str(value)[:10]
        except Exception:
            pass
        return today.isoformat()


BENCHMARK_LABELS = {
    "ALL_BRANCH": "全行客户",
    "SAME_AUM_BAND": "同AUM层级客户",
    "SAME_RISK_LEVEL": "同风险等级客户",
}
