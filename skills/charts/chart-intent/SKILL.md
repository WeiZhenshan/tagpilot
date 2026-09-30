---
name: "chart-intent"
display-name: "图表意图层"
category: "chart"
version: "1.0.0"
description: "为分析结果自动配图：读取数据画像，先判断“要表达什么”（意图），再决定画不画、画哪张，并调用 chart-atomic 产出合法图表 spec。分析技能产出事实卡后需要配图时使用；数据不足时应输出空图表列表并说明原因，不要为凑图而画。用户不应直接调用本技能。"
argument-hint: "事实列表与想表达的重点（可留空）"
user-invocable: false
disable-model-invocation: false
allowed-tools: ["Read", "Skill"]
---

# 图表意图层

图表不是"美化"，是表达。"选图"的本质是先定**意图**（想说什么），再交给 chart-atomic 实现。

## 工作步骤

1. **数据画像**：列出可用事实（AVAILABLE，满足样本规则）与缺失事实；数一数类别数、系列数、是否有分母、是否能对账。
2. **定意图**：按 `references/intent-taxonomy.md` 从六种意图中选 1 种（多张图各自定意图）。
3. **可画性判定**：按 `references/fallback-rules.md` 检查——不满足就降级或放弃这张图。宁缺毋滥：**没有可信数据时的正确产出是 `charts: []`**，并在正文说明原因。
4. **产出 spec**：调用 **chart-atomic** 技能（Skill 工具），把数据画像、意图和事实 id 交给它，由它按协议编译 spec。
5. 回到分析技能：把 spec 数组放进最终 `insight-result` 块的 `charts` 字段。

## 配图原则

- 每张图只服务一个意图；同一份数据既有对比又想看结构，就画两张（交给 chart-compose 排序）。
- 图表必须能被事实复算：图上每个数字都能在 `facts` 表里找到同一数值。做不到就不画。
- 抑制与缺失是数据的一部分：样本不足的格子用"已抑制"呈现（`value: null`），不要用 0 或省略来掩盖。
- 是否配图服从表达需要：只有一个人数事实时，KPI 是合适的；把它画成柱状图反而喧宾夺主。

## 与相邻技能的关系

- 分析技能（fact/diagnostic/action）产生事实与叙述 → 本技能决定图表方案 → chart-atomic 编译 spec → chart-compose 组合成仪表板顺序。
