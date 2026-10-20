---
name: "data-quality-review"
display-name: "分析数据质量核对"
category: "general"
version: "1.0.0"
description: "读取聚合工具提供的质量证据，判断重复键、缺失、单位、数据日期和样本抑制对当前分析的影响。不声称执行未运行的检查。"
argument-hint: "本轮证据批次与相关风险"
user-invocable: false
disable-model-invocation: false
allowed-tools: ["Read", "Skill"]
---

# 分析数据质量核对

仅核对会影响当前问题的风险，复用 query_aggregates 返回的 quality、status、reason、missing 和数据批次。
分清零、空、未接入、取数失败和已抑制。单项缺口不否定其他已核验事实。
查询时间不是业务数据日期；日期未知时在相关结论旁说明。
后续下钻返回新快照时，旧派生值不能继续引用。
人数、分类与互补格的隐私规则由服务端执行；不能据被抑制的总计或差值推算小格。
把风险、受影响指标和可继续分析的范围返回给所属分析技能，不另起质量报告或递归验证。

参考方法来源：Data 的 analyze-data-quality，执行检查以 Java 工具实际返回为准。
