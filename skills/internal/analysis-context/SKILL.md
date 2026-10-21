---
name: "analysis-context"
display-name: "分析上下文核对"
category: "general"
version: "1.0.0"
description: "在对话分析前核对问题、客群、指标口径、比较对象和当前图表引用。已有完整上下文时直接复用；不负责生成独立报告。"
argument-hint: "分析问题与现有上下文"
user-invocable: false
disable-model-invocation: false
allowed-tools: ["Read", "Skill"]
---

# 分析上下文核对

通过宿主的 get_analysis_context 读取当前范围、图表引用和已发布能力，再决定是否需要检索指标。
自然语言问题通过 find_tags/get_tag_details 匹配已发布指标与维度；不要让用户提供技术编号。
当前客群优先继承，用户明确指定全量才切换全量。比较全量不等于改变目标客群。
区分客户粒度、观察日期、查询时间、指标单位、分母和条件截断；当前时点字段不代表历史数据。
只有会改变分析结论的歧义才向用户提问。多个图表对象不明确时返回候选选择，不猜测。
不自行保存口径、设定高资产阈值或发布规则；把缺口传给所属分析技能。

参考方法来源：Data 的 gather-business-context 与 create-data-context，按 TagPilot 服务端权威定义适配。
