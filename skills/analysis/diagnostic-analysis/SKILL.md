---
name: "diagnostic-analysis"
display-name: "客群诊断分析"
category: "diagnosis"
version: "1.2.0"
description: "回答“哪里值得关注、为什么值得关注”：在事实基础上寻找对比对象、量化差异、下钻定位集中方向，并严格区分规则、统计与假设三种依据。运行前若选择了对照客群，用两套服务端统计做差并说明方向；没有基准数据时如实说明无法诊断，绝不把差异说成原因；简单描述现状请用 fact-analysis。"
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

1. **读事实**：列出 AS-IS 事实（客群实际值，优先使用 `tag_stats` 里服务端注入的统计）与已声明的缺口。
2. **找可比对象**：上下文里有 `baseline`（对照客群）时，它就是本轮基准——对照客群由服务端重新编译并统计，与客群使用同一批标签列，可直接做差；在报告里写清对照客群的名称与人数。没有 `baseline` 时，按 `references/benchmark-selection.md` 逐项检查同类客群、全量客群、同机构、标准化基准，都不具备就明确记录「无基准」，进入第 5 步。`tag_stats`/`baseline.tag_stats` 只覆盖各自客群自身，不能跨客群拼接成本轮之外的基准。
3. **量化差异**：差异 = 客群值 − 对照值，登记为 `diff.*` 派生事实（比率类差值单位 `pp`），注明方向（高于/低于）。差异只在两侧口径一致时才成立（同期、同口径、同分母、同单位）；只有一侧可用时不得做差。被条件截断的列（`plan_tag`）要在结论里声明截断影响。
4. **下钻定位**（见 `references/drilldown-strategy.md`）：差异集中在哪些子群？按资产层、风险层、机构、产品线逐层看；下钻每一层都需要对应维度数据，数据没有就停下并声明。本轮可选标签有限，无法下钻时如实记录，不得用明细臆测子群差异。
5. **形成诊断**（见 `references/diagnosis-boundaries.md`）：每条结论标明依据类型——`RULE`（明确业务规则推导）、`STAT`（统计检验，需附检验方法与区间）、`HYPOTHESIS`（未验证的假设）。**差异 ≠ 原因**：可以说"权益类占比均值低于对照客群 X pp"，不能说"因为客户不喜欢理财"。对照客群的位置只是可比对象，不是目标值。

## 阈值与显著性

- 规则型判断（如"低于同类客群 X pp 以上算缺口"）要把规则原文写进 `boundary.metric_definitions`。
- 统计型判断必须给检验方法与双侧区间（如 Wilson + 多重比较校正），样本不足时降级为 HYPOTHESIS 或不下结论。没有做检验时，只能把差异陈述为观察（事实/派生事实），诊断句用 `HYPOTHESIS` 或规则口径，不得声称"显著"。
- 没有依据时宁可输出「未形成诊断」，也不要输出一个看起来像结论的猜测。

## 输出

正文之后以 ```insight-result 块收尾，字段与示例见 `references/result-contract.md`（与基础事实技能同一契约；块内是严格 JSON，字符串里不要用英文双引号）。诊断结论写进卡片的 `diagnosis` 段，`basis` 如实填写；`comparison` 段写清比较对象、差异值与方向，`benchmark_fact_ids` 引用 `benchmark.*` 事实、`difference_fact_ids` 引用 `diff.*` 事实；没有基准时才写「本轮未接入基准数据，无法对比」。行动建议只写"值得考虑的检验方向"，不要产出行动对象（那是 action-decision 的职责）。

输出前逐段自查：`text` 里出现的每一个 `{fact:id}` 都必须同时出现在该段的 `fact_ids` 数组里（`comparison` 段的引用也计入 `fact_ids`）；`{fact:}` 只能引用本块 `facts` 中 `status` 为 `AVAILABLE` 的事实。漏登记或引用了不可用事实，该卡片会被服务端整卡丢弃。

配图：差异对比适合 `compare_categories` 柱状图（客群与对照两组系列）、结构占比适合 `stacked_bar`、下钻矩阵适合 `heatmap`；调用 chart-intent 判定，不要直接画。没有可展示数值时 `charts` 为 `[]`。
