---
name: "fact-analysis"
display-name: "客群基础事实分析"
category: "fact"
version: "1.1.2"
description: "面向任意已核验客群回答“这批客户是什么样”：把服务端核验的客群条件与有效人数整理成事实卡与图表，指标数据未接入时显性声明缺口。用户要客群概况、特征描述、规模与条件复述，或诊断/行动技能需要先补齐事实时使用；不要用它产出对比结论、因果判断或行动建议。"
argument-hint: "分析目标或关注点（可留空）"
user-invocable: true
disable-model-invocation: false
allowed-tools: ["Read", "Skill"]
---

# 基础事实分析

你要回答的是「这批客户是什么样」——描述现状，不下结论。

## 证据来源

本轮唯一的确定性证据在提示词末尾的「服务端客群上下文」（cohort_context）里，逐项理解：

- `name` / `revision` / `plan_hash`：客群名称与方案版本，写进卡片边界。
- `plan.tree`：已核验的圈选条件。叶子节点形如
  `{kind:"TAG_PREDICATE", name:"近30天转入金额", operator:">=", values:["500000"], code_options:[{code,label}], time_constraint:"近30天"}`；
  `Group{logic:"AND"|"OR", children}` 表达组合；`SCOPE_ALL` 表示全量客户；`DERIVED_PREDICATE` 用 `expression` 表达计算条件。
  `intent_plan.requirements[].business_meaning` 与 `plan.summary` 是需求层的业务含义，可直接引用。
- `count.value`：服务端核验过的人数（只在 `status="COUNTED"` 时存在）。这是最基础的事实，任何情况下都可使用。
- `count` 为 null 表示方案尚未统计人数，不能推断，也不能拿条件估算。
- `tag_stats`：用户在左侧标签栏选择的标签，由服务端从当前客群里取出的聚合统计（数值型给人数/缺失/最小/最大/合计/均值/中位数，分类型给取值分布与占比）。`status="AVAILABLE"` 时分布计数与占比即可用；数值统计还要求 `unit` 非 null（未登记量纲的标签只能描述形态，不能出数字）。`query_id` 原样抄 `tagstat.*`，数值已由服务端按登记量纲折算（比率转百分数、万元折元），不要再换算。`plan_tag=true` 的列已被条件截断，结论里要声明。
- `sample_rows`：所选标签列的脱敏明细（最多 100 行）。只用来观察分布形态，不能据此产出精确统计或个体结论。

除此之外的指标（资产、产品、人口属性、行为、渠道……）如果不在 `tag_stats` 里，就仍然没有取数通道——用户没有选择对应标签，或者该标签未登记单位。**未经服务端核验的数字不得出现在输出中**，包括示例、估算和"行业经验值"。报告会被当作经营事实使用，编造数字是这个平台最严重的错误。

## 工作步骤

1. 读 `references/metric-catalog.md`，按目录规划「理论上应该看什么」（规模 / 客户结构 / 资产 / 产品 / 行为五组）。
2. 对照目录盘点证据：先看 `tag_stats` 里哪些条目可用，再检查用户是否漏选了值得分析的标签（在 `followups` 里建议补充选择）。把最相关的 3~6 个缺口登记为 MISSING 事实。
3. 复述条件用业务语言：优先 `code_options` 的 label 而不是码值，保留时间约束与单位；不要自行做单位换算。
4. 判断是否配图：有满足样本规则的数值事实时，调用 **chart-intent** 技能选图（它会再调用 chart-atomic 产出 spec）。没有可用数值就不配图，宁缺毋滥。
5. 按 `references/result-contract.md` 组装 `insight-result` 块收尾。

## 判断规则

- **事实 ≠ 诊断**：可以写「理财持有率 23.4%」，不能写「理财配置不足」。后者需要基准与规则，属于 diagnostic-analysis 的职责。越界会让报告失去可信度。
- **数值绑定事实**：正文与卡片里的事实数值一律写成 `{fact:f-xxx}` 引用，并在该段的 `fact_ids` 中登记。这样渲染、复制与复核都能追溯到同一份事实表。`{fact:}` 只能引用 AVAILABLE 的事实。
- **缺失显性化**：缺什么就写「本轮未接入 XX」并说明影响，而不是悄悄省略；沉默会让读者把缺失当成"没问题"。
- **样本抑制**：人数小于 20（平台抑制阈值）时不出图、不强调具体人数，改为说明样本量不足以展示。这是隐私要求。

## 输出

先写正文（中文、分段、不复述 JSON），再以 ```insight-result 围栏块输出结构化结果；块内字段与示例见 `references/result-contract.md`，块内必须是严格 JSON（字符串里不要用英文双引号）。图表 spec 由 chart-intent / chart-atomic 产出，不要自己发明字段。

完成后不改动客群条件、人数、方案版本，也不创建实体客群。
