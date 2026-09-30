# 图形（Marks）

平台支持六种图形，各自对应确定的表达语义。图形与意图（intent）必须匹配，否则渲染守卫会拒绝。

| kind | 表达 | 数据形态 | 配套 intent |
| --- | --- | --- | --- |
| `kpi` | 单个关键数值 | 恰好 1 个格子、1 个系列 | `single_value` |
| `table` | 精确读数（守卫通过后以可访问表格渲染） | 类别 × 系列 | 任意 intent |
| `bar` | 类别间比较、分布 | 1~8 个系列，类别 ≤12 | `compare_categories` / `show_distribution` |
| `stacked_bar` | 构成（占比或绝对量堆叠） | 1~8 个系列 | `show_composition` |
| `heatmap` | 二维矩阵（类别 × 列） | 恰好 1 个系列，格子带 `column` | `show_matrix` |
| `funnel` | 逐级收窄的转化 | 恰好 1 个系列、单调递减 | `show_conversion` |

## 选择提示

- 一个数说清的事，用 `kpi`；精确对读，用 `table`。
- 比较/分布：类别少且量纲一致用 `bar`；类别多但需要精确值，`table` 比堆叠条更诚实。
- 构成：占总量且各组可加时用 `stacked_bar`；占比堆叠必须带分组对账。
- 矩阵：两个维度（如 AUM 段 × 风险等级）呈现密度/差异时用 `heatmap`；格子缺失用抑制占位。
- 漏斗：只有在各层人数来自同一口径、且单调递减时才画；任何一层是估算都不画。

## 平台既有词表

守卫中的 `intent → kind` 固定映射（不可更改）：

```
single_value      → kpi
compare_categories→ bar
show_composition  → stacked_bar
show_distribution → bar
show_matrix       → heatmap
show_conversion   → funnel
table             → 任意 intent
```

## 与旧平台词表的对应

内容体系中的「六图表原子」（KPI、表格、柱状、堆叠、热力、漏斗）就是以上六种；不再引入桑基、地图、树图等新 kind——渲染与守卫没有对应的支持，产出即失败。
