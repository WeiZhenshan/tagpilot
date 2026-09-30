# 结果契约（insight-result 块）

正文之后必须追加一个 ```insight-result 围栏块，内含一个 JSON 对象。平台会在服务端校验并组装为洞察报告；块缺失或校验失败时只保留正文，图表与卡片不会展示。

## JSON 纪律（先看这一节）

块内必须是**严格 JSON**，平台直接解析，不接受任何近似写法：

- 字符串内部不要出现英文双引号；需要引用词句时用中文引号 `「」` 或 `“”`。未转义的英文双引号是最常见的解析失败原因。
- 不要写注释、尾逗号、单引号；换行、反斜杠按 JSON 规则转义（正文段落已写在 JSON 外面，字符串内如需换行用 `\n`）。
- 输出块之前自查一遍括号配对与逗号，宁可少写一段文字，也不要产出不合法 JSON。
- 块只写一次，放在正文最后；界面会把它从正文中移除，不要把同一份结果重复输出。

## 顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | `COMPLETE` / `PARTIAL` / `BLOCKED` | 本轮分析完成度。只有人数可用、其余指标缺失时为 `PARTIAL`；连人数都没有或无法归纳任何事实时为 `BLOCKED` |
| `reasons` | string[]（≤6） | 为什么是这个状态：一句话一条，写清缺失了什么 |
| `facts` | Fact[]（≤300） | 事实表，见下 |
| `cards` | InsightCard[]（1~30） | 五段式洞察卡，见下 |
| `charts` | ChartSpec[]（0~30） | 由 chart-intent / chart-atomic 产出的图表 spec；没有可用数据时为 `[]` |
| `followups` | string[]（≤10） | 建议的下一步（可运行的技能、可补充的条件、值得关注的方向） |

## Fact（事实）

| 字段 | 规则 |
| --- | --- |
| `id` | `f-` 开头小写标识（`f-count`、`f-aum-missing`），全表唯一 |
| `metric` | 指标 id（见 metric-catalog），如 `customer_count`、`aum` |
| `label` | 中文短标签，如「客群规模」「总资产」 |
| `value` | 数值；MISSING/SUPPRESSED 时必须为 `null` |
| `unit` | 只能是 `人` `元` `%` `pp` `分` |
| `sample_size` | 计算该事实的样本量（整数）。客群人数事实填人数本身；MISSING 填 `null` |
| `status` | `AVAILABLE`（有数）/ `SUPPRESSED`（样本太小被抑制）/ `MISSING`（数据未接入） |
| `query_id` | 证据来源标记：`cohort.count`（服务端人数）、`catalog.<metric>`（目录中未接入的指标）等 |
| `evidence` | 1~10 条来源说明（中文），写清"来自服务端核验的什么" |
| `role` | `OBSERVED`（直接观测）/ `BENCHMARK` / `POST_EXCLUSION` / `DERIVED` |
| `denominator_id` | 百分比的分子分母引用；非百分比填 `null` |
| `derived_from` | 派生来源事实 id 数组；直接观测填 `[]` |
| `exclusions_applied` | 已应用的排除项；未排除填 `[]` |

允许登记为 AVAILABLE 的数值只有三类：

1. **服务端核验的人数**（`count.value`，`query_id` 用 `cohort.count`）。
2. **条件原文中的阈值**（如「转入金额 ≥ 500000 元」中的 500000）。条件阈值事实用最接近的目录指标 id 作 `metric`、条件原文单位作 `unit`，并在 `evidence` 注明「来自服务端核验的圈选条件」——这样正文才能用 `{fact:id}` 安全引用这些数字。
3. **`tag_stats` 与 `baseline.tag_stats` 中服务端注入的标签统计**（本节下一小节）。服务端会逐条复核：`query_id` 命中 `tagstat.*`、`benchmark.*`、`diff.*` 的事实，取值必须与注入的统计量一致，否则整条被丢弃；数值统计的 `unit` 必须与注入值相同，未登记单位的标签统计不得登记为 AVAILABLE。

除此之外的一切数值都必须来自确定性数据系统，没有就登记 `MISSING`。

## 标签统计（tag_stats）与脱敏明细（sample_rows）

当用户在左侧标签栏选择了标签并运行技能时，`cohort_context` 会多出两个字段：

- `tag_stats`：每个所选标签一条，字段为 `tag_id` / `label` / `tag_type` / `unit` / `unit_source` / `plan_tag` / `status` / `reason` / `sample_size`，以及二选一的 `numeric` 或 `categories`。
  - `status` 为 `AVAILABLE` 时才可作为事实来源；`SUPPRESSED`（存在小于 20 人的分类，整组已抑制）、`MISSING`（取数失败或人数漂移）、`UNSUPPORTED`（该标签类型不支持统计）一律登记为 `MISSING` 事实并复述 `reason`。
  - `numeric`：`{n, missing, min, max, sum, avg, median}`，`query_id` 用 `tagstat.<tag_id>.<统计名>`（如 `tagstat.812.avg`）。数值已按标签登记的量纲折算到 `unit` 上（比率类已转成百分数，万元量纲已折算成元），**不要**再自行换算。
  - `categories`：`[{code, label, count, share}]`，计数用 `tagstat.<tag_id>.cat.<code>`（单位「人」），占比用 `tagstat.<tag_id>.share.<code>`（单位「%」）；占比事实必须带 `denominator_id`（指向人数事实）。分布的单位是固有的，不受该标签是否登记量纲影响。
  - `unit` 为 `null` 表示该标签的数值统计没有登记量纲：它的 `numeric` 数字只能用于定性描述与边界说明，**不得**登记为 AVAILABLE 事实；`categories` 的计数与占比不受此限制。
  - `plan_tag` 为 `true` 表示该列已被圈选条件截断（例如条件是「AUM ≥ 50 万」，那么 AUM 的均值有偏），结论里必须声明这一点。
- `sample_rows`：`{columns, rows, limit, masked, note}`，是所选标签列在客群内的脱敏明细（客户号已打码，最多 100 行）。它只用于观察分布形态与异常值，**不得**据以产出任何个体级结论或精确统计；正式数值一律引用 `tag_stats` 或人数。

`stats_note` 非空时说明本轮取数已降级，要在 `boundary` 里如实转述。

## 对照客群基准（baseline）

当用户在运行技能前选择了「对照客群」时，`cohort_context` 会多出 `baseline`：`{group_id, name, count, tag_stats, stats_note}`。`tag_stats` 的结构与当前客群完全一致，字段含义相同；`plan_tag` 表示该列被对照客群自身的条件截断，做差与结论时要一并声明。`baseline` 是服务端核验的已保存客群，同一批标签列的两套统计可以直接比较。

- 对照统计登记为事实时，`query_id` 用 `benchmark.<tag_id>.<统计名>` / `benchmark.<tag_id>.cat.<code>` / `benchmark.<tag_id>.share.<code>`，`role` 填 `BENCHMARK`；取值必须与注入值一致，服务端同样逐条复核。
- 客群与对照的差值登记为派生事实：`query_id` 用 `diff.<tag_id>.<统计名>`（数值差，单位与量纲同该统计）、`diff.<tag_id>.cat.<code>`（人数差，单位「人」）、`diff.<tag_id>.share.<code>`（占比差，单位 `pp`）；`role` 填 `DERIVED`，`derived_from` 填两侧事实 id。差值只在两侧同口径（均 AVAILABLE 且单位相同）时成立；只有一侧可用时不得登记差值。
- 差异 = 客群值 − 对照值；方向说明（高于/低于）本身不做价值判断，高与低都不等于好与坏。
- `baseline.stats_note` 非空时说明对照取数已降级，`comparison` 段与 `boundary` 要如实转述。
- 没选对照客群时以上都不适用，`comparison` 段按无基准处理。

## Statement（陈述段）

`{ text, fact_ids }`：`text` 是中文陈述，事实数值写成 `{fact:id}` 占位符，`fact_ids` 列出本段引用的全部 id。`{fact:}` 只允许引用 AVAILABLE 事实；缺失数据改用自然语言说明。日期、版本号、阈值这类非事实数字可以直接写。

## InsightCard（五段式卡片）

| 段 | 要求 |
| --- | --- |
| `facts` | 事实陈述 + 条件复述；引用规模事实 |
| `comparison` | `{text, fact_ids, benchmark_fact_ids, difference_fact_ids}`。有对照客群时写清比较对象（名称与人数）与差异事实；没有基准数据时如实写「本轮未接入基准数据，无法对比」并把两个数组填空数组 |
| `diagnosis` | `{text, fact_ids, basis}`，`basis ∈ RULE / STAT / HYPOTHESIS`。事实技能只做方法性说明（如「缺少基准，未形成诊断」），basis 用 `RULE`；`statistical_evidence` 填 `null` |
| `action` | `{text, fact_ids, population_fact_id, priority}`。不产出行动对象时 `population_fact_id: null`、`priority: "NONE"` |
| `boundary` | `{text, data_as_of, skill_version, sample_fact_id, metric_definitions}`。`text` 写适用边界与缺失影响；`data_as_of` 与 `skill_version` 先写空串（服务端回填）；`sample_fact_id` 填规模事实 id，无人数时写 `""`；`metric_definitions` 是本次使用/欠缺的指标口径说明（每条一句话） |

## 完整示例

```insight-result
{
  "status": "PARTIAL",
  "reasons": [
    "仅接入服务端核验的客群条件与有效人数，资产、产品与行为指标未接入",
    "缺少基准数据，不产出对比与诊断结论"
  ],
  "facts": [
    {
      "id": "f-count",
      "metric": "customer_count",
      "label": "客群规模",
      "value": 1268,
      "unit": "人",
      "sample_size": 1268,
      "status": "AVAILABLE",
      "query_id": "cohort.count",
      "evidence": ["服务端按当前已核验方案统计的人数"],
      "role": "OBSERVED",
      "denominator_id": null,
      "derived_from": [],
      "exclusions_applied": []
    },
    {
      "id": "f-aum-missing",
      "metric": "aum",
      "label": "总资产",
      "value": null,
      "unit": "元",
      "sample_size": null,
      "status": "MISSING",
      "query_id": "catalog.aum",
      "evidence": ["本轮未接入指标取数通道，无法计算总资产"],
      "role": "OBSERVED",
      "denominator_id": null,
      "derived_from": [],
      "exclusions_applied": []
    },
    {
      "id": "f-holding-missing",
      "metric": "product_holding_rate",
      "label": "产品持有率",
      "value": null,
      "unit": "%",
      "sample_size": null,
      "status": "MISSING",
      "query_id": "catalog.product_holding_rate",
      "evidence": ["本轮未接入指标取数通道，无法计算产品持有结构"],
      "role": "OBSERVED",
      "denominator_id": null,
      "derived_from": [],
      "exclusions_applied": []
    }
  ],
  "cards": [
    {
      "id": "card-overview",
      "title": "客群概况",
      "facts": {
        "text": "本客群由「近30天转入金额至少500000元」且「未持有理财产品」两个条件圈定，共 {fact:f-count}。",
        "fact_ids": ["f-count"]
      },
      "comparison": {
        "text": "本轮未接入基准数据，无法回答「和同类客户比怎么样」。",
        "fact_ids": [],
        "benchmark_fact_ids": [],
        "difference_fact_ids": []
      },
      "diagnosis": {
        "text": "缺少对比对象与指标数据，本轮未形成诊断；条件的业务含义不等于客户的经营结论。",
        "fact_ids": [],
        "basis": "RULE",
        "statistical_evidence": null
      },
      "action": {
        "text": "本轮不产出行动对象：既没有客户级产品数据，也没有营销与适当性规则。",
        "fact_ids": [],
        "population_fact_id": null,
        "priority": "NONE"
      },
      "boundary": {
        "text": "结论仅覆盖客群条件与规模；资产、产品、人口与行为表现均未接入，不能据此推断客户特征或配置缺口。",
        "data_as_of": "",
        "skill_version": "",
        "sample_fact_id": "f-count",
        "metric_definitions": [
          "customer_count：按当前已核验方案服务端统计的客户数",
          "aum：客户名下资产总额，本轮未接入",
          "product_holding_rate：持有指定产品的客户占比，本轮未接入"
        ]
      }
    }
  ],
  "charts": [
    {
      "schema_version": 1,
      "id": "chart-scale",
      "title": "客群规模",
      "kind": "kpi",
      "intent": "single_value",
      "unit": "人",
      "metric_label": "客户数",
      "series": [
        {
          "name": "客群规模",
          "fact_ids": ["f-count"],
          "points": [{ "category": "客户数", "column": null, "fact_id": "f-count", "value": 1268 }]
        }
      ],
      "annotations": [],
      "reconcile": [],
      "zero_baseline": true,
      "orientation": "vertical"
    }
  ],
  "followups": [
    "运行 diagnostic-analysis：在接入基准数据后对比同类客群的资产与产品结构",
    "补充产品持有相关条件后再圈选，可缩小到更聚焦的客群"
  ]
}
```

## 常见错误

- 写了「约 1200 人」「近七成」这类未绑定事实的数字——必须用 `{fact:f-count}`。
- 把估算或经验值写成事实——宁可 `MISSING`，不可编造。
- 用 `{fact:}` 引用 MISSING 事实——面板会拒绝渲染；缺失只做文字说明。
- 段内 `text` 引用了 `{fact:id}` 却没写进该段的 `fact_ids`——服务端会按引用自动补齐；引用了不存在或不可用事实的，整卡丢弃。
- 图表 spec 引用了 `facts` 中不存在、或数值与事实不一致的 `fact_id`——spec 里的 `value` 必须与事实值完全相等。
- 忘了 `insight-result` 块或 JSON 不合法——结果是降级为纯文本，卡片和图表全部丢失。
- 给标签统计事实写了 `tagstat.*` 的 `query_id` 却改了数值，或引用了未选择标签、已抑制、未登记单位的统计量——服务端会整条丢弃。
- 给对照统计写了 `benchmark.*` / `diff.*` 却自行改数，或对只有一侧可用的统计量造差值——同样整条丢弃。
- 把 `sample_rows` 里的明细当成统计口径，或据它写出个体级结论。
