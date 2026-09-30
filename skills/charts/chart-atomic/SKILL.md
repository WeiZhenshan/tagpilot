---
name: "chart-atomic"
display-name: "图表原子层"
category: "chart"
version: "1.0.0"
description: "把一组已核验事实编译为一张符合平台图表协议的 InsightChartSpec（kpi/table/bar/stacked_bar/heatmap/funnel）。当图表意图已明确、需要产出或修订具体图表 spec 时使用；字段规则与对账要求见技能内参考资料，任何字段都不能自行发明。用户不应直接调用本技能。"
argument-hint: "数据画像、图表意图与事实 id 列表"
user-invocable: false
disable-model-invocation: false
allowed-tools: ["Read", "Skill"]
---

# 图表原子层

输入：一组已核验事实、一个图表意图（`intent`）、以及要表达的取数结构；输出：**一张** `InsightChartSpec`。spec 是声明式协议（不是 ECharts option），由平台前端渲染、校验并导出。

## 产出步骤

1. 读 `references/marks.md`：确认所选图形（kind）的表达语义与数据形态匹配。
2. 读 `references/encoding-rules.md`：按单位、方向、系列与格子的规则组装 `series` / `points`。
3. 读 `references/spec-guard.md`：这是平台的渲染守卫（chartGuard），**逐条自查**——不满足的 spec 会被前端拒绝渲染，显示为错误。
4. 输出：一张图一个 ```json 围栏块，块内只有 spec 对象；随后用一句话说明该图表达什么、以及任何未展示的类别。

## 硬性判断

- **数值只来自事实**：`points[].value` 必须与事实表里对应 `fact_id` 的 `value` 完全相等；不一致的图会被守卫拒绝。没有事实就没有图。
- **缺失即抑制**：MISSING/SUPPRESSED 事实对应的格子 `value` 写 `null`（`sample_size` 也是 null）——渲染为"已抑制"占位，不得补零或省略该格子。
- **不发明字段**：spec 顶层、series、point、annotation、reconcile 都只允许协议列出的字段；多余字段同样会被拒绝。
- **一张图一个意图**：多意图拆成多张图，交给 chart-compose 组合；不要在一张图里塞多种表达。

## 与其他技能的关系

- 图表 **选择**（画什么、要不要画）属于 chart-intent；本技能只负责"怎么把已定意图画成合法 spec"。
- 多图组合（顺序、仪表板）属于 chart-compose。
- 修订 spec（用户改图需求）同样走本技能：改字段后重新自查。

## 常见失败与修正

| 失败 | 修正 |
| --- | --- |
| 类别超过 12 | 选择业务关键 ≤12 个类别并说明截断；不能造"其他"桶 |
| 百分比堆叠没有分组对账 | 每个类别补一条 `percentage` 对账（引用该类别全部格子） |
| KPI 放多个事实 | KPI 只允许一格；多指标拆多张 KPI 或用 table |
| 漏斗未单调 | 检查逐层人数是否单调不增；数据不满足就不要画漏斗 |
| 注解里有阿拉伯数字 | 数字改成 `{fact:id}` 占位；注解只允许占位形式的数字 |
