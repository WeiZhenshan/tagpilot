# 对话内容协议

宿主提供 get_analysis_context、query_aggregates、derive_facts、submit_insight_result 时，使用这些工具完成自然对话分析；它们由宿主授权，不能由 Skill 扩大权限。

- 先读当前分析范围、图表引用、证据快照；必要时调用 analysis-context。
- 通过 find_tags/get_tag_details 匹配真实指标；用户不必先选标签。
- 查询后调用 data-quality-review 检查与问题相关的质量风险；结论提交前调用 analysis-validation。
- 数值来自最新证据批次，派生计算交给 derive_facts。新查询会重算活动查询计划并使旧派生值失效。
- 使用 submit_insight_result 的 text/chart/table/clarification 内容块交付，可分次 complete=false，最后 complete=true。此模式不输出 insight-result 围栏或另一份未经核验的最终正文。
- 短回答只展示必要内容，不强制五段式卡片或固定图表数量。
- 仅改方向、排序或条形图/表格切换时使用 view_only，不调用取数工具。
- 历史数据、营销规则、显著性检验未提供时说明缺口。动作只给建议与执行前提，不生成客户名单。

未提供这些工具的显式原生 Skill 运行继续遵守 result-contract，保持旧入口兼容。
