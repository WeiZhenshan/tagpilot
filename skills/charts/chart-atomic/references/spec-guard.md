# 渲染守卫清单（spec-guard）

平台前端在渲染与导出前会执行完整的 spec 校验（chartGuard）。**任何一条不满足，该图整体不渲染**。产出 spec 后逐条自查。

## 1. 字段与形状

- [ ] spec 顶层只允许这些键：`schema_version, id, title, kind, intent, unit, metric_label, series, annotations, reconcile, zero_baseline, orientation`。
- [ ] `series[]` 只允许：`name, fact_ids, points`；`points[]` 只允许：`category, column, fact_id, value`。
- [ ] `reconcile[]` 只允许：`kind, fact_ids, total_fact_id, tolerance`；`annotations[]` 只允许：`text, fact_ids`。
- [ ] `schema_version` = `1`；`zero_baseline` = `true`（布尔）。

## 2. 类型与意图

- [ ] `kind ∈ {kpi, table, bar, stacked_bar, heatmap, funnel}`。
- [ ] `intent` 与 `kind` 匹配：`single_value→kpi`、`compare_categories→bar`、`show_composition→stacked_bar`、`show_distribution→bar`、`show_matrix→heatmap`、`show_conversion→funnel`；`table` 允许任意 intent。
- [ ] `orientation ∈ {horizontal, vertical}`；`unit ∈ {人, 元, %, pp, 分}`。
- [ ] 文字长度：`id`≤80、`title`≤80、`metric_label`≤40、系列名≤24、`category`≤24、`column`≤24。
- [ ] 所有文字不含 `<`（防注入）。

## 3. 事实绑定

- [ ] 每个 `point.fact_id` 都能在事实表中找到；`fact.unit === spec.unit`；**`fact.value === point.value`（严格相等）**。
- [ ] AVAILABLE 事实才可出现在图里：`sample_size` 为整数且 ≥20（平台抑制阈值）。
- [ ] `unit="人"` 的事实值：整数，且为 0 或 ≥20。
- [ ] `unit="%"` 的事实：`denominator_id` 必须指向可用的分母事实（值>0），值域 0~100；若 `calculation="WEIGHTED"`，`weights` 的键必须与 `derived_from` 完全一致、非负且合计为 1，加权结果与事实值一致（±0.01）；若 `derived_from` 非空，`sum(derived_from 事实值) / denominator × 100` 与事实值一致（±0.01）。
- [ ] MISSING / SUPPRESSED 事实的格子：`point.value` 必须为 `null` 且事实 `sample_size` 为 `null`——这是"已抑制"的合法形态，渲染为占位而非数值。

## 4. 系列与格子

- [ ] `series` 数量 1~8；`kpi` / `heatmap` / `funnel` 恰好 1 个系列。
- [ ] 每个系列 `points` 数量 1~100；`fact_ids` 集合与格子引用集合**完全相等**。
- [ ] 同一系列内 `(category, column)` 组合不重复。
- [ ] 全部类别去重 ≤12；全部列去重 ≤12。
- [ ] `heatmap` 的格子必须带 `column`；**其他所有 kind 的 `column` 必须为 `null`**（包括 table）。
- [ ] `kpi` 的全部格子数必须为 1。

## 5. 对账

- [ ] `reconcile` ≤12 条；每条 `fact_ids` 非空、不重复、且都是图上已展示的格子。
- [ ] `tolerance ∈ [0, 0.05]`。
- [ ] `kind="sum"`：必须给 `total_fact_id`（可用事实、单位与图一致），且格子之和 = 总值（±tolerance）。
- [ ] `kind="percentage"`：`unit` 必须为 `%`，格子之和 = 100（±tolerance）。
- [ ] `kind="funnel"`：各格值单调不增（`v[i] ≤ v[i-1]`）。
- [ ] `kind="funnel"` 的图：`unit="人"`，且必须有一条 `funnel` 对账，其 `fact_ids` 与展示顺序（逐个格子）**完全一致**。
- [ ] `unit="%"` 的 `stacked_bar`：每个类别都要有一条 `percentage` 对账，覆盖该类别全部格子。

## 6. 标注

- [ ] ≤8 条；`text` ≤500 字；`fact_ids` 1~10 个且都是 AVAILABLE 事实。
- [ ] `text` 中出现的每个 `{fact:id}` 都必须在该条 `fact_ids` 中。
- [ ] `text` 去掉 `{fact:...}` 占位后**不得含任何数字字符**（含全角０-９）——"近30天"要改写为"近一月"，或把数字做成事实占位。

## 自查方法

产出后给自己过一遍这张清单，特别是：字段拼写、`column` 空值规则、`value` 与事实严格相等、对账完整性、标注数字。任何一条拿不准，就换成更保守的 kind（table）或删除该图。
