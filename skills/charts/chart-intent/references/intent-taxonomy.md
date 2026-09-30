# 意图分类

六种图表意图，与图形（kind）一一对应（table 例外，可承载任意意图）：

| intent | 想表达 | kind | 典型数据 |
| --- | --- | --- | --- |
| `single_value` | 一个关键数字 | kpi | 客群规模、可执行对象数 |
| `compare_categories` | 类别之间的高低 | bar | 各产品持有率、各机构客户数 |
| `show_composition` | 整体由什么构成 | stacked_bar | 资产构成（活期/定期/投资） |
| `show_distribution` | 数值在区间上的分布 | bar | AUM 分层人数 |
| `show_matrix` | 两个维度的交叉格局 | heatmap | AUM 段 × 风险等级 |
| `show_conversion` | 逐层收窄的转化 | funnel | 行动漏斗（候选→适当性→排除→可执行） |

## 意图判断问句

按顺序自问，命中即停：

1. 「我要强调的是一件事的**一个数**吗？」→ `single_value`
2. 「我在**比大小**吗？」（谁高谁低、排名）→ `compare_categories`
3. 「我在说**一部分占整体**吗？」（占比、构成）→ `show_composition`
4. 「我在看**分布形态**吗？」（集中在哪段、长尾）→ `show_distribution`
5. 「我要同时看**两个维度**吗？」（谁和谁交叉最突出）→ `show_matrix`
6. 「我在讲**一条链路**吗？」（每一层剩下多少人）→ `show_conversion`

## 意图纪律

- 意图是"表达什么"，不是"数据长什么样"：同一份分层数据，强调分布用 `show_distribution`，强调占比构成用 `show_composition`——先想清楚要传达的信息。
- 一张图只选一个意图；表达不清就不要配图。
- 分布 vs 构成的自查：各格相加等于整体 → 构成；各格是互斥分箱的绝对量 → 分布。
