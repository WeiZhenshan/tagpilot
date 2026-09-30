---
name: "diagnostic-analysis"
display-name: "客群诊断分析"
category: "diagnosis"
version: "1.0.0"
description: "回答“哪里值得关注、为什么值得关注”：在事实基础上寻找对比对象、量化差异、下钻定位集中方向，并严格区分规则、统计与假设三种依据。用户提到异常、差异、缺口、为什么、是否偏低/偏高时使用；没有基准数据时必须如实说明无法诊断，绝不把差异说成原因；简单描述现状请用 fact-analysis。"
argument-hint: "要诊断的方向（如：产品配置、资产结构）"
user-invocable: true
disable-model-invocation: false
allowed-tools: ["Read", "Skill"]
---

# 诊断分析

你要回答：「哪里值得关注」「为什么值得关注」。诊断的前提是**有可比较的对象**——基准、规则或统计检验；没有对比就没有诊断。

## 前置事实

先检查当前上下文里是否已经有本轮事实（同一次会话中先跑过 fact-analysis 时，提示词里会带有其输出）。没有就先调用 **fact-analysis** 技能补齐事实链，再做诊断——诊断必须建立在同一份事实表上，不能另起一套口径。

## 诊断循环

1. **读事实**：列出 AS-IS 事实（客群实际值）与已声明的缺口。
2. **找可比对象**（见 `references/benchmark-selection.md`）：同类客群、全量客群、同机构、标准化基准。本轮没有基准取数通道时，明确记录"无基准"，进入第 5 步。
3. **量化差异**：差异 = 客群值 − 基准值，注明单位与方向（pp / % / 元）。差异只在两侧口径一致时才成立（同期、同口径、同分母）。
4. **下钻定位**（见 `references/drilldown-strategy.md`）：差异集中在哪些子群？按资产层、风险层、机构、产品线逐层看；下钻每一层都需要对应维度数据，数据没有就停下并声明。
5. **形成诊断**（见 `references/diagnosis-boundaries.md`）：每条结论标明依据类型——`RULE`（明确业务规则推导）、`STAT`（统计检验，需附检验方法与区间）、`HYPOTHESIS`（未验证的假设）。**差异 ≠ 原因**：可以说"差异主要集中在高 AUM 且中高风险承受能力客户"，不能说"因为客户不喜欢理财"。

## 阈值与显著性

- 规则型判断（如"低于同类客群 X pp 以上算缺口"）要把规则原文写进 `boundary.metric_definitions`。
- 统计型判断必须给检验方法与双侧区间（如 Wilson + 多重比较校正），样本不足时降级为 HYPOTHESIS 或不下结论。
- 没有依据时宁可输出「未形成诊断」，也不要输出一个看起来像结论的猜测。

## 输出

正文之后以 ```insight-result 块收尾，字段与示例见 `references/result-contract.md`（与基础事实技能同一契约；块内是严格 JSON，字符串里不要用英文双引号）。诊断结论写进卡片的 `diagnosis` 段，`basis` 如实填写；`comparison` 段写清比较对象、差异值与区间；行动建议只写"值得考虑的检验方向"，不要产出行动对象（那是 action-decision 的职责）。

配图：差异对比适合 `compare_categories` 柱状图、结构占比适合 `stacked_bar`、下钻矩阵适合 `heatmap`；调用 chart-intent 判定，不要直接画。没有可展示数值时 `charts` 为 `[]`。
