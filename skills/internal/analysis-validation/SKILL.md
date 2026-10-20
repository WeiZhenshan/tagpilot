---
name: "analysis-validation"
display-name: "分析结论核验"
category: "general"
version: "1.0.0"
description: "在对话内容提交前核对问题覆盖、事实引用、比较口径、图型与结论边界。返回修订建议，不能代替服务端计算或声称全量审计。"
argument-hint: "问题、最新证据与候选回答"
user-invocable: false
disable-model-invocation: false
allowed-tools: ["Read", "Skill"]
---

# 分析结论核验

核对用户要求的指标、比较和下钻是否已回答，缺失是否解释。
所有业务数值只能引用最新证据；比率引用正确分母，差值单位为 pp 或原指标单位。
差异与算术贡献不是原因。未验证解释标记 HYPOTHESIS；无检验结果不声称显著，无发布规则不声称适当性已通过。
注意圈选条件造成的选择效应，尤其是被“未持有”条件截断的产品持有率。
图表必须支持当前问题，采用一致的单位、范围和比较尺度；不能相加非互斥持有率。
使用 submit_insight_result 发布核验内容；服务端拒绝时修正引用或缩小结论。不要输出另一份未经核验的最终正文。
本技能只返回所属分析的修订意见，不循环调用自身或发起独立报告。

参考方法来源：Data 的 validate-data 与 analysis-quality，按 TagPilot 对话内容协议适配。
