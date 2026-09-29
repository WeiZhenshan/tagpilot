"""InsightChartSpec：与渲染器解耦的声明式图表规范（对齐方案 4.8.5）。

约定：
  * `rows` 必须是**已经聚合、已经校验**的数据；渲染器不得再做计算；
  * `rows` 不得出现客户标识字段；分组样本量低于安全阈值时由调用方先行合并或抑制；
  * 业务 Skill 只负责产出 Spec，前端 ECharts / 服务端 SVG 共用同一份 Spec。
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from tagpilot_agent.skills.manifest import ALLOWED_MARKS

ALLOWED_TRANSFORMS = {"sort", "top_n", "filter", "bin", "fold"}
ALLOWED_ENCODINGS = {"x", "y", "color", "size", "row", "column", "series", "value", "category"}
FORBIDDEN_ROW_KEYS = {"cust_id", "customer_id", "cust_name", "name", "id_card", "mobile", "phone"}
PERCENTAGE_MARKS = {"pie", "stacked_bar"}


class ChartField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=64)
    semantic_type: Literal["category", "measure", "series", "percentage", "time", "count"] = "measure"
    role: Literal["dimension", "measure", "group"] = "measure"
    metric_id: str = ""
    unit: str = ""


class ChartTransform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    by: str = ""
    order: str = ""
    field: str = ""
    n: int = 0
    remainder: str = ""


class ChartView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mark: str
    orientation: str = "vertical"
    encoding: dict[str, str] = Field(default_factory=dict)


class ChartAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["highlight", "reference_line", "target", "note"] = "note"
    category: str = ""
    text: str = ""
    evidence_id: str = ""


class ChartInteraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tooltip: bool = True
    legend_filter: bool = False
    drill_down: list[str] = Field(default_factory=list)


class ChartAccessibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    data_table: bool = True
    do_not_use_color_only: bool = True


class ChartProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str
    skill_version: str
    metric_versions: list[str] = Field(default_factory=list)
    data_as_of: str = ""
    transform_hash: str = ""


class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    chart_id: str
    intent: str
    chart_skill: str
    title: str = Field(min_length=2, max_length=120)
    subtitle: str = ""
    dataset_ref: str = ""
    fields: list[ChartField] = Field(min_length=1)
    rows: list[dict] = Field(default_factory=list, max_length=2000)
    transforms: list[ChartTransform] = Field(default_factory=list)
    view: ChartView
    annotations: list[ChartAnnotation] = Field(default_factory=list)
    interaction: ChartInteraction = Field(default_factory=ChartInteraction)
    accessibility: ChartAccessibility = Field(default_factory=ChartAccessibility)
    export: list[str] = Field(default_factory=lambda: ["svg", "png"])
    provenance: ChartProvenance


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    detail: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _chart_id() -> str:
    return "CHART_" + uuid.uuid4().hex[:12]


def _transform_hash(spec_fields: list[ChartField], transforms: list[ChartTransform], rows: list[dict]) -> str:
    payload = json.dumps(
        {
            "fields": [item.model_dump() for item in spec_fields],
            "transforms": [item.model_dump() for item in transforms],
            "row_count": len(rows),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _provenance(skill_id: str, skill_version: str, metrics: list[str], data_as_of: str) -> ChartProvenance:
    return ChartProvenance(
        skill_id=skill_id,
        skill_version=skill_version,
        metric_versions=[f"{metric}@1.0" for metric in metrics],
        data_as_of=data_as_of,
        transform_hash="",
    )


def _finalize(spec: ChartSpec) -> ChartSpec:
    spec.provenance.transform_hash = _transform_hash(spec.fields, spec.transforms, spec.rows)
    return spec


def build_kpi_spec(
    skill_id: str,
    skill_version: str,
    data_as_of: str,
    title: str,
    items: list[dict],
    summary: str = "",
    annotations: list[ChartAnnotation] | None = None,
) -> ChartSpec:
    """KPI 卡：items = [{label, value, unit, metric_id, delta_text?}]"""
    rows = [
        {
            "label": item["label"],
            "value": item["value"],
            "unit": item.get("unit", ""),
            "metric_id": item.get("metric_id", ""),
            "delta_text": item.get("delta_text", ""),
        }
        for item in items
    ]
    spec = ChartSpec(
        chart_id=_chart_id(),
        intent="single_value",
        chart_skill="chart.compose.audience_overview",
        title=title,
        subtitle=f"数据截至{data_as_of}",
        dataset_ref="DATASET_KPI",
        fields=[
            ChartField(field="label", semantic_type="category", role="dimension"),
            ChartField(field="value", semantic_type="measure", role="measure"),
        ],
        rows=rows,
        view=ChartView(mark="kpi", encoding={"value": "value", "category": "label"}),
        annotations=annotations or [],
        accessibility=ChartAccessibility(summary=summary or title, data_table=True),
        provenance=_provenance(skill_id, skill_version, [row["metric_id"] for row in rows if row["metric_id"]], data_as_of),
    )
    return _finalize(spec)


def build_table_spec(
    skill_id: str,
    skill_version: str,
    data_as_of: str,
    title: str,
    columns: list[dict],
    rows: list[dict],
    summary: str = "",
    intent: str = "ranking",
    chart_skill: str = "chart.intent.show_ranking",
    annotations: list[ChartAnnotation] | None = None,
) -> ChartSpec:
    fields = [
        ChartField(
            field=column["field"],
            semantic_type=column.get("semantic_type", "measure"),
            role=column.get("role", "measure"),
            metric_id=column.get("metric_id", ""),
            unit=column.get("unit", ""),
        )
        for column in columns
    ]
    spec = ChartSpec(
        chart_id=_chart_id(),
        intent=intent,
        chart_skill=chart_skill,
        title=title,
        subtitle=f"数据截至{data_as_of}",
        dataset_ref="DATASET_TABLE",
        fields=fields,
        rows=rows,
        view=ChartView(mark="table", encoding={field.field: field.field for field in fields}),
        annotations=annotations or [],
        accessibility=ChartAccessibility(summary=summary or title, data_table=True),
        provenance=_provenance(skill_id, skill_version, [f.metric_id for f in fields if f.metric_id], data_as_of),
    )
    return _finalize(spec)


def build_category_spec(
    skill_id: str,
    skill_version: str,
    data_as_of: str,
    title: str,
    category_field: str,
    measure_field: str,
    rows: list[dict],
    mark: str = "bar",
    orientation: str = "horizontal",
    series_field: str = "",
    unit: str = "",
    intent: str = "category_comparison",
    chart_skill: str = "chart.intent.compare_categories",
    summary: str = "",
    annotations: list[ChartAnnotation] | None = None,
    legend_filter: bool = False,
    transforms: list[ChartTransform] | None = None,
    semantic_type: str = "measure",
    metric_id: str = "",
) -> ChartSpec:
    fields = [ChartField(field=category_field, semantic_type="category", role="dimension")]
    fields.append(
        ChartField(
            field=measure_field,
            semantic_type=semantic_type,
            role="measure",
            unit=unit,
            metric_id=metric_id,
        )
    )
    if series_field:
        fields.append(ChartField(field=series_field, semantic_type="series", role="group"))
    encoding = {"x": measure_field if orientation == "horizontal" else category_field,
                "y": category_field if orientation == "horizontal" else measure_field}
    if series_field:
        encoding["color"] = series_field
    spec = ChartSpec(
        chart_id=_chart_id(),
        intent=intent,
        chart_skill=chart_skill,
        title=title,
        subtitle=f"数据截至{data_as_of}",
        dataset_ref="DATASET_CATEGORY",
        fields=fields,
        rows=rows,
        transforms=transforms or [],
        view=ChartView(mark=mark, orientation=orientation, encoding=encoding),
        annotations=annotations or [],
        interaction=ChartInteraction(tooltip=True, legend_filter=legend_filter or bool(series_field)),
        accessibility=ChartAccessibility(summary=summary or title, data_table=True),
        provenance=_provenance(skill_id, skill_version, [measure_field], data_as_of),
    )
    return _finalize(spec)


def build_correlation_spec(
    skill_id: str,
    skill_version: str,
    data_as_of: str,
    title: str,
    x_field: str,
    y_field: str,
    size_field: str,
    rows: list[dict],
    *,
    category_field: str = "",
    summary: str = "",
) -> ChartSpec:
    """散点/气泡：相关关系不得写成因果结论。"""
    fields = [
        ChartField(field=x_field, semantic_type="measure", role="measure"),
        ChartField(field=y_field, semantic_type="measure", role="measure"),
    ]
    if size_field:
        fields.append(ChartField(field=size_field, semantic_type="measure", role="measure"))
    if category_field:
        fields.append(ChartField(field=category_field, semantic_type="series", role="group"))
    spec = ChartSpec(
        chart_id=_chart_id(),
        intent="correlation",
        chart_skill="chart.intent.show_correlation",
        title=title,
        subtitle=f"数据截至{data_as_of}",
        dataset_ref="DATASET_CORRELATION",
        fields=fields,
        rows=rows,
        view=ChartView(mark="scatter", encoding={"x": x_field, "y": y_field, "size": size_field} if size_field
                       else {"x": x_field, "y": y_field}),
        accessibility=ChartAccessibility(summary=summary or title, data_table=True),
        provenance=_provenance(skill_id, skill_version, [x_field, y_field], data_as_of),
    )
    return _finalize(spec)


def build_funnel_spec(
    skill_id: str,
    skill_version: str,
    data_as_of: str,
    title: str,
    rows: list[dict],
    category_field: str = "stage",
    measure_field: str = "customer_count",
    summary: str = "",
    annotations: list[ChartAnnotation] | None = None,
    metric_id: str = "customer_count",
) -> ChartSpec:
    fields = [
        ChartField(field=category_field, semantic_type="category", role="dimension"),
        ChartField(field=measure_field, semantic_type="count", role="measure", unit="人", metric_id=metric_id),
    ]
    spec = ChartSpec(
        chart_id=_chart_id(),
        intent="conversion",
        chart_skill="chart.intent.show_conversion",
        title=title,
        subtitle=f"数据截至{data_as_of}",
        dataset_ref="DATASET_FUNNEL",
        fields=fields,
        rows=rows,
        view=ChartView(mark="funnel", encoding={"category": category_field, "value": measure_field}),
        annotations=annotations or [],
        accessibility=ChartAccessibility(summary=summary or title, data_table=True),
        provenance=_provenance(skill_id, skill_version, [measure_field], data_as_of),
    )
    return _finalize(spec)


def build_stacked_spec(
    skill_id: str,
    skill_version: str,
    data_as_of: str,
    title: str,
    rows: list[dict],
    category_field: str = "aum_level",
    measure_field: str = "share",
    series_field: str = "audience_type",
    summary: str = "",
    mark: str = "stacked_bar",
    intent: str = "composition",
    metric_id: str = "aum_band_share",
) -> ChartSpec:
    """百分比堆叠：分母必须明确（这里是各组内占比，按目标客群与基准分别归一）。"""
    fields = [
        ChartField(field=category_field, semantic_type="category", role="dimension"),
        ChartField(field=measure_field, semantic_type="percentage", role="measure", unit="percent", metric_id=metric_id),
        ChartField(field=series_field, semantic_type="series", role="group"),
    ]
    spec = ChartSpec(
        chart_id=_chart_id(),
        intent=intent,
        chart_skill="chart.intent.show_composition",
        title=title,
        subtitle=f"数据截至{data_as_of}（分母=各分组内客户数）",
        dataset_ref="DATASET_COMPOSITION",
        fields=fields,
        rows=rows,
        view=ChartView(
            mark=mark,
            orientation="vertical",
            encoding={"x": category_field, "y": measure_field, "color": series_field},
        ),
        interaction=ChartInteraction(tooltip=True, legend_filter=True),
        accessibility=ChartAccessibility(summary=summary or title, data_table=True),
        provenance=_provenance(skill_id, skill_version, [measure_field], data_as_of),
    )
    return _finalize(spec)


def build_heatmap_spec(
    skill_id: str,
    skill_version: str,
    data_as_of: str,
    title: str,
    rows: list[dict],
    x_field: str,
    y_field: str,
    value_field: str,
    summary: str = "",
    annotations: list[ChartAnnotation] | None = None,
) -> ChartSpec:
    fields = [
        ChartField(field=x_field, semantic_type="category", role="dimension"),
        ChartField(field=y_field, semantic_type="category", role="dimension"),
        ChartField(field=value_field, semantic_type="percentage", role="measure", unit="percent"),
    ]
    spec = ChartSpec(
        chart_id=_chart_id(),
        intent="matrix",
        chart_skill="chart.intent.show_composition",
        title=title,
        subtitle=f"数据截至{data_as_of}",
        dataset_ref="DATASET_HEATMAP",
        fields=fields,
        rows=rows,
        view=ChartView(mark="heatmap", encoding={"x": x_field, "y": y_field, "color": value_field}),
        annotations=annotations or [],
        accessibility=ChartAccessibility(summary=summary or title, data_table=True),
        provenance=_provenance(skill_id, skill_version, [value_field], data_as_of),
    )
    return _finalize(spec)


def validate_chart_spec(
    spec: ChartSpec,
    expected_totals: dict[str, float] | None = None,
    min_group_size: int = 20,
    tolerance: float = 0.01,
) -> list[ValidationResult]:
    """六类校验的精简实现：Schema、数据一致、语义、可读性、安全与可访问性、可渲染。"""
    results: list[ValidationResult] = []
    expected_totals = expected_totals or {}

    schema_problems: list[str] = []
    if spec.view.mark not in ALLOWED_MARKS:
        schema_problems.append(f"mark 不在白名单：{spec.view.mark}")
    for transform in spec.transforms:
        if transform.type not in ALLOWED_TRANSFORMS:
            schema_problems.append(f"transform 不在白名单：{transform.type}")
    for key in spec.view.encoding:
        if key not in ALLOWED_ENCODINGS and spec.view.mark != "table":
            schema_problems.append(f"encoding 通道不合法：{key}")
    field_names = {item.field for item in spec.fields}
    for channel, field in spec.view.encoding.items():
        if field and field not in field_names and spec.view.mark != "table":
            schema_problems.append(f"encoding.{channel} 引用了未声明字段：{field}")
    if spec.view.mark != "kpi" and not spec.rows:
        schema_problems.append("非 KPI 图表必须包含 rows")
    results.append(
        ValidationResult(
            name="chart_spec_schema",
            passed=not schema_problems,
            detail="；".join(schema_problems) or "ChartSpec 字段、mark、transform 与编码均在白名单内",
        )
    )

    data_problems: list[str] = []
    for metric_id, expected in expected_totals.items():
        if not any(field.metric_id == metric_id for field in spec.fields):
            continue
        if not any(field.metric_id == metric_id and field.role == "measure" for field in spec.fields):
            continue
        value_field = next(field.field for field in spec.fields if field.metric_id == metric_id and field.role == "measure")
        actual = 0.0
        counted = 0
        for row in spec.rows:
            raw = row.get(value_field)
            if isinstance(raw, (int, float)):
                actual += float(raw)
                counted += 1
        if counted == 0:
            continue
        if abs(actual - float(expected)) > max(abs(float(expected)) * tolerance, 0.5):
            data_problems.append(f"字段 {value_field} 合计 {round(actual, 2)} 与指标 {metric_id} 期望 {expected} 不一致")
    results.append(
        ValidationResult(
            name="chart_data_reconciliation",
            passed=not data_problems,
            detail="；".join(data_problems) or "图表数据与指标口径一致（合计对账通过）",
        )
    )

    semantic_problems: list[str] = []
    for row in spec.rows[:200]:
        for key in row:
            if key.lower() in FORBIDDEN_ROW_KEYS:
                semantic_problems.append(f"rows 含客户标识字段：{key}")
    descriptive = " ".join([spec.title, spec.subtitle, spec.accessibility.summary])
    if re.search(r"导致|因此必然|证明", descriptive):
        semantic_problems.append("图表标题或摘要出现因果性表述")
    if spec.view.mark in PERCENTAGE_MARKS and "分母" not in spec.subtitle:
        semantic_problems.append("占比类图表必须在副标题中说明分母")
    if spec.view.mark in {"line", "area"}:
        time_fields = [field.field for field in spec.fields if field.semantic_type == "time"]
        if not time_fields:
            semantic_problems.append("折线或面积图缺少时间语义字段")
    results.append(
        ValidationResult(
            name="chart_semantic_validation",
            passed=not semantic_problems,
            detail="；".join(semantic_problems) or "时间轴、分母与表述语义校验通过",
        )
    )

    readability_problems: list[str] = []
    dimension_field = next((f.field for f in spec.fields if f.role == "dimension"), None)
    if dimension_field and spec.view.mark != "kpi":
        categories = {str(row.get(dimension_field)) for row in spec.rows}
        if len(categories) > 30:
            readability_problems.append(f"维度 {dimension_field} 类别数 {len(categories)} 超过 30，需要 Top-N 或分面")
    for row in spec.rows:
        for key, value in row.items():
            if isinstance(value, str) and len(value) > 40:
                readability_problems.append(f"字段 {key} 的标签长度超过 40 字符")
                break
    results.append(
        ValidationResult(
            name="chart_readability_validation",
            passed=not readability_problems,
            detail="；".join(sorted(set(readability_problems))) or "类别数量与标签长度在可读范围内",
        )
    )

    safety_problems: list[str] = []
    for field in spec.fields:
        if field.semantic_type == "count":
            for row in spec.rows:
                value = row.get(field.field)
                if isinstance(value, (int, float)) and 0 < value < min_group_size:
                    safety_problems.append(f"{field.field}={value} 低于最小样本阈值 {min_group_size}")
                    break
    results.append(
        ValidationResult(
            name="chart_safety_accessibility",
            passed=not safety_problems,
            detail="；".join(sorted(set(safety_problems))) or f"无低于 {min_group_size} 的裸露分组；已提供文字摘要与数据表",
        )
    )

    render_problems: list[str] = []
    encoding_fields = {field for field in spec.view.encoding.values() if field}
    for field in encoding_fields:
        if spec.view.mark == "kpi":
            continue
        if not any(field in row for row in spec.rows[:1]):
            render_problems.append(f"rows 缺少编码字段：{field}")
    if spec.view.mark == "funnel":
        values = [row.get(spec.view.encoding.get("value", "customer_count")) for row in spec.rows]
        numeric = [float(v) for v in values if isinstance(v, (int, float))]
        if numeric != sorted(numeric, reverse=True):
            render_problems.append("漏斗阶段数值必须单调不增")
    results.append(
        ValidationResult(
            name="chart_render_validation",
            passed=not render_problems,
            detail="；".join(render_problems) or "编码字段齐备、图形语义可渲染",
        )
    )
    return results
