"""指标语义层与业务口径（对齐方案 4.9）：集中定义指标、分子分母、单位、维度与负责人。

Skill 不得各自重复定义口径；所有数值都通过本模块的确定性函数计算。
"""

from __future__ import annotations

from statistics import median as _median

# ---------- 风险等级与产品适配 ----------

RISK_ORDER: dict[str, int] = {"R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}

RISK_TOLERANCE_TO_RATING: dict[str, str] = {
    "保守型": "R1",
    "稳健型": "R2",
    "平衡型": "R3",
    "成长型": "R4",
    "进取型": "R5",
    "低": "R1",
    "中低": "R2",
    "中等": "R3",
    "中高": "R4",
    "高": "R5",
}

PRODUCT_DEFINITIONS: tuple[dict, ...] = (
    {"key": "deposit", "label": "存款", "flag": "has_deposit", "min_rating": "R1", "category": "基础"},
    {"key": "wealth", "label": "理财", "flag": "has_wealth", "min_rating": "R1", "category": "稳健"},
    {"key": "fund", "label": "基金", "flag": "has_fund", "min_rating": "R3", "category": "权益"},
    {"key": "insurance", "label": "保险", "flag": "has_insurance", "min_rating": "R1", "category": "保障"},
    {"key": "credit_card", "label": "信用卡", "flag": "has_credit_card", "min_rating": "R1", "category": "基础"},
    {"key": "loan", "label": "贷款", "flag": "has_loan", "min_rating": "R1", "category": "基础"},
    {"key": "forex", "label": "外汇", "flag": "has_forex", "min_rating": "R4", "category": "进阶"},
    {"key": "precious_metal", "label": "贵金属", "flag": "has_precious_metal", "min_rating": "R4", "category": "进阶"},
    {"key": "trust", "label": "信托", "flag": "has_trust", "min_rating": "R5", "category": "私行"},
)

# 机会优先级权重（可解释规则，第一版不使用机器学习模型）
OPPORTUNITY_WEIGHTS: dict[str, float] = {
    "value": 0.30,
    "event": 0.25,
    "gap": 0.20,
    "response": 0.15,
    "channel": 0.10,
}
OPPORTUNITY_PENALTY: dict[str, float] = {"risk_mismatch": 40.0, "disturbance": 15.0}
OPPORTUNITY_BANDS: tuple[tuple[str, float], ...] = (("high", 70.0), ("medium", 45.0), ("low", 0.0))

# ---------- 指标定义（指标语义层） ----------

METRIC_DEFINITIONS: dict[str, dict] = {
    "customer_count": {"name": "客户数", "definition": "客群内有效客户数量", "numerator": "客群客户数", "denominator": "—", "unit": "人", "owner": "零售金融部"},
    "total_aum": {"name": "总AUM", "definition": "客群内客户 AUM 余额合计", "numerator": "Σ aum_balance", "denominator": "—", "unit": "元", "owner": "零售金融部"},
    "avg_aum": {"name": "人均AUM", "definition": "客群总 AUM / 客群客户数", "numerator": "总AUM", "denominator": "客户数", "unit": "元", "owner": "零售金融部"},
    "median_aum": {"name": "AUM中位数", "definition": "客群客户 AUM 余额中位数", "numerator": "—", "denominator": "—", "unit": "元", "owner": "零售金融部"},
    "aum_band_share": {"name": "AUM分层占比", "definition": "各 AUM 层级客户数占客群客户数比例", "numerator": "该层级客户数", "denominator": "客群客户数", "unit": "percent", "owner": "零售金融部"},
    "liquid_asset_ratio": {"name": "活期及短期存款占比", "definition": "日均存款 / AUM 余额，超过 70% 视为资金沉淀于活期", "numerator": "avg_daily_deposit", "denominator": "aum_balance", "unit": "percent", "owner": "零售金融部"},
    "liquid_heavy_share": {"name": "活期沉淀客群占比", "definition": "活期及短期存款占比超过 70% 的客户占客群比例", "numerator": "活期占比>70% 客户数", "denominator": "客群客户数", "unit": "percent", "owner": "零售金融部"},
    "product_holding_rate": {"name": "产品持有率", "definition": "持有该类产品的客户占客群比例", "numerator": "持有该类产品客户数", "denominator": "客群客户数", "unit": "percent", "owner": "零售金融部"},
    "wealth_product_holding_rate": {"name": "理财产品持有率", "definition": "统计日持有至少一款有效理财产品的客户占比", "numerator": "持有理财产品客户数", "denominator": "客群客户数", "unit": "percent", "owner": "零售金融部"},
    "product_coverage_avg": {"name": "平均持有产品数", "definition": "客群人均持有产品数量", "numerator": "Σ total_products_count", "denominator": "客群客户数", "unit": "个", "owner": "零售金融部"},
    "product_gap_rate": {"name": "产品覆盖缺口", "definition": "基准客群持有率 − 目标客群持有率，正值表示低配", "numerator": "基准持有率−目标持有率", "denominator": "—", "unit": "percent", "owner": "零售金融部"},
    "opportunity_customer_count": {"name": "机会客户数", "definition": "通过风险适配与排除规则校验后进入机会名单的客户数", "numerator": "机会名单客户数", "denominator": "—", "unit": "人", "owner": "零售金融部"},
    "high_priority_opportunity_count": {"name": "高优先级机会客户数", "definition": "机会分 ≥ 70 的客户数", "numerator": "机会分≥70客户数", "denominator": "—", "unit": "人", "owner": "零售金融部"},
    "channel_reachable_rate": {"name": "线上渠道可达率", "definition": "手机银行/网银/微信银行任一开通的客户占比", "numerator": "线上渠道客户数", "denominator": "客群客户数", "unit": "percent", "owner": "零售金融部"},
    "risk_unsuitable_share": {"name": "风险不适配占比", "definition": "风险等级低于目标产品最低适配等级的客户占比", "numerator": "不适配客户数", "denominator": "客群客户数", "unit": "percent", "owner": "风险管理部"},
    "excluded_customer_share": {"name": "营销排除客户占比", "definition": "命中黑名单或欺诈预警的客户占比", "numerator": "排除客户数", "denominator": "客群客户数", "unit": "percent", "owner": "风险管理部"},
}


# ---------- 数值工具 ----------

def share(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count * 100.0 / total, 2)


def ratio_delta(left: float, right: float) -> float:
    return round(float(left) - float(right), 2)


def median_of(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(float(_median(values)), 2)


def avg_of(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def rating_of(row: dict) -> str:
    raw = str(row.get("risk_rating") or "").strip().upper()
    if raw in RISK_ORDER:
        return raw
    return RISK_TOLERANCE_TO_RATING.get(str(row.get("risk_tolerance") or "").strip(), "R3")


def rating_value(row: dict) -> int:
    return RISK_ORDER.get(rating_of(row), 3)


def is_excluded(row: dict) -> bool:
    return bool(row.get("blacklist_flag")) or bool(row.get("fraud_alert_flag"))


def is_online_reachable(row: dict) -> bool:
    return any(
        row.get(flag) for flag in ("is_mobile_banking_user", "is_online_banking_user", "is_wechat_banking_user")
    )


def product_available(product: dict, row: dict) -> bool:
    """风险适配：客户风险等级必须 ≥ 产品最低适配等级。"""
    return rating_value(row) >= RISK_ORDER.get(product["min_rating"], 1)


def metric(payload: dict) -> dict:
    """包装指标值，附带口径定义，便于证据与前端展示。"""
    metric_id = payload.get("metric_id", "")
    definition = METRIC_DEFINITIONS.get(metric_id, {})
    return {
        "value": payload.get("value"),
        "unit": payload.get("unit") or definition.get("unit", ""),
        "metric_id": metric_id,
        "name": definition.get("name", metric_id),
        "definition": definition.get("definition", ""),
        "numerator": payload.get("numerator", definition.get("numerator", "")),
        "denominator": payload.get("denominator", definition.get("denominator", "")),
        "owner": definition.get("owner", ""),
        "dimensions": payload.get("dimensions", []),
        "version": payload.get("version", "1.0"),
    }


def band_order(label: str) -> int:
    """AUM 层级排序键：支持如 '1万以下'/'100万以上' 这类中文层级名称。"""
    digits = "".join(ch for ch in str(label) if ch.isdigit() or ch == ".")
    try:
        return int(float(digits or 0))
    except ValueError:
        return 0


def merge_small_counts(
    rows: list[dict],
    label_field: str,
    count_field: str,
    min_count: int,
    remainder_label: str = "其他（小样本合并）",
) -> tuple[list[dict], int]:
    """把低于最小样本阈值的分组合并为“其他”，保证合计可对账且不泄露小样本。

    返回 (合并后的行, 被合并的分组数)。
    """
    big: list[dict] = [dict(row) for row in rows if float(row.get(count_field) or 0) >= min_count]
    small = [row for row in rows if float(row.get(count_field) or 0) < min_count]
    if small:
        merged: dict = {label_field: remainder_label, count_field: sum(float(row.get(count_field) or 0) for row in small)}
        for key in rows[0] if rows else []:
            if key not in merged:
                merged[key] = ""
        big.append(merged)
    return big, len(small)
