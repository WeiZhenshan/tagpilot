# Skill 引擎接口契约（v1）

> 配套文档：[标签智能体两大核心亮点实现计划与整体架构方案] 第 4 章（洞察 Skill 体系）
> 生效日期：2026-09-24　适用范围：tagpilot-agent（执行权威）、ruoyi-taglibrary（治理与 UI）

本文件是**并行开发的接口基线**：Python 侧按此实现，Java/Vue 侧按此对接，任何一方改契约需先改本文件。

## 0. 职责边界

| 层 | 组件 | 职责 |
|---|---|---|
| 执行权威 | `tagpilot-agent/tagpilot_agent/skills/` | Skill 定义（Manifest）、生命周期状态、版本、执行、校验、洞察卡与图表规范 |
| 治理与 UI | `ruoyi-taglibrary` + `ruoyi-ui` | 权限、审计、菜单、客群成员解析、页面展示 |
| 数据 | `ry.ind_tag_data` | 客户标签宽表（67 字段），Skill 聚合的唯一数据来源 |

原则（对齐方案 0.3）：**模型做语义判断，代码做业务约束和数字计算**；Skill 的第一版全部为确定性计算，不依赖 LLM 即可运行。

## 1. HTTP 契约（Python 服务，默认 127.0.0.1:8092）

认证：`Authorization: Bearer $TAG_RUNTIME_TOKEN`（与 Java、tagpilot-semantic 相同）。

### 1.1 列表与详情

```
GET /skills?status=&category=&keyword=&permissions=taglibrary:skill:run,insight:read&limit=&offset=
→ 200 {
    "total": 3,
    "items": [{
      "skill_id": "product_holding_gap",
      "name": "产品持仓缺口诊断",
      "category": "diagnostic",          // fact | diagnostic | action
      "layer": "L2",                      // L1 | L2 | L3
      "version": "1.0.0",
      "status": "published",              // draft | published | deprecated | offline
      "owner": "零售金融部",
      "description": "...",
      "applicable_objects": ["personal_customer_audience"],
      "default_benchmark": "SAME_AUM_BAND",
      "required_permissions": ["audience:read", "insight:product_gap"],
      "updated_at": "2026-09-24T10:00:00+08:00"
    }]
  }

GET /skills/{skill_id}?version=1.0.0
→ 200 完整 Manifest（见第 2 节）+ "versions":["1.0.0"], "lifecycle":[{"version","status","operator_id","changed_at","reason"}]

GET /skills/{skill_id}/versions
→ 200 {"skill_id":"...","versions":[{"version":"1.0.0","status":"published","changed_at":"...","reason":"首次发布"}]}

POST /skills/{skill_id}/validate      body = 完整 Manifest 或 {"manifest": {...}}
→ 200 {"valid": true, "errors": [], "warnings": ["..."]}

POST /skills/{skill_id}/status
  body = {"action":"publish"|"offline"|"deprecate"|"draft","version":"1.0.0",
          "operator_id":"1","operator_name":"admin","reason":"业务验收通过"}
→ 200 {"skill_id":"...","version":"1.0.0","status":"published","changed_at":"..."}
→ 409 非法状态流转（detail 说明当前状态与允许动作）

GET /skills/recommend?intent=&audience_id=
→ 200 {"scenario_pack":{"id":"large_inflow_conversion","name":"大额入金转化场景包",
        "skill_ids":["audience_asset_structure","product_holding_gap","marketing_opportunity_priority"]},
        "skills":[{同 1.1 列表项}], "reason":"按客群圈选目的推荐 L1→L2→L3 组合"}
```

### 1.2 执行

```
POST /skills/{skill_id}/run
  body = {
    "audience_id": "12",                 // 客群ID（字符串，兼容 bigint）
    "audience_name": "大额入金未持有理财",
    "member_ids": ["10001","10002"],     // Java 解析的客群成员（必需；上限 100000）
    "as_of_date": "2026-09-24",          // 可选，默认今天
    "benchmark_type": "SAME_AUM_BAND",   // 可选，缺省用 Manifest default_benchmark
    "params": {},                        // 可选，Skill 自定义参数（白名单校验）
    "operator_id": "1",
    "operator_name": "admin",
    "permissions": ["audience:read","insight:product_gap"],
    "trace_id": "可选"
  }
→ 200 {
    "run_id": "run_xxx",
    "skill_id": "product_holding_gap",
    "skill_version": "1.0.0",
    "status": "succeeded",               // succeeded | blocked
    "blocked_reason": null,              // blocked 时给出中文原因
    "started_at": "...","finished_at":"...","duration_ms": 123,
    "audience": {"audience_id":"12","name":"...","customer_count":64,"as_of_date":"2026-09-24"},
    "benchmark": {"type":"SAME_AUM_BAND","name":"同AUM层级客户","customer_count":3120},
    "metrics": { 指标ID: {"value":..,"unit":"..","metric_id":"..","definition":".."} },
    "insight_cards": [ InsightCard ... ],      // 见第 3 节
    "charts": [ InsightChartSpec ... ],        // 见第 4 节
    "evidence": [ Evidence ... ],
    "diagnostics": [{"level":"info|warn","code":"...","message":"..."}],
    "validations": [{"name":"metric_reconciliation","passed":true,"detail":"..."}],
    "chart_validations": [{"name":"chart_spec_validation","passed":true,"detail":"..."}],
    "data_as_of": "2026-09-24"
  }
→ 403 权限不足（detail：缺少 insight:product_gap）
→ 404 Skill 不存在
→ 409 Skill 未发布（detail：当前状态 draft）
→ 422 数据不就绪 / 样本过小 / 参数非法（detail 为中文原因）

GET /skills/runs?skill_id=&audience_id=&limit=20
→ 200 {"total":N,"items":[{run_id,skill_id,skill_version,audience_id,audience_name,customer_count,status,operator_id,operator_name,duration_ms,created_at}]}
```

## 2. SkillManifest（Python 权威，Java 只透传展示）

```json
{
  "skill_id": "product_holding_gap",
  "version": "1.0.0",
  "name": "产品持仓缺口诊断",
  "category": "diagnostic",
  "layer": "L2",
  "owner": "零售金融部",
  "status": "published",
  "description": "识别客群在九类产品上的持有缺口，并与同价值、同风险层级客户基准比较。",
  "applicable_objects": ["personal_customer_audience"],
  "scenario_packs": ["large_inflow_conversion"],
  "required_inputs": ["audience_id", "as_of_date", "benchmark_type"],
  "required_metrics": ["customer_count", "aum_band", "risk_level", "product_holding_matrix"],
  "preconditions": {
    "min_customer_count": 20,
    "max_data_age_days": 2,
    "required_permissions": ["audience:read", "insight:product_gap"]
  },
  "executor": {"type": "builtin", "operation": "product_holding_gap", "timeout_seconds": 30},
  "output_schema": "ProductHoldingGapResultV1",
  "default_benchmark": "SAME_AUM_BAND",
  "allowed_benchmarks": ["ALL_BRANCH", "SAME_AUM_BAND", "SAME_RISK_LEVEL"],
  "visualizations": [
    {"chart_skill": "chart.intent.compare_categories", "preferred_mark": "bar"},
    {"chart_skill": "chart.intent.show_composition", "preferred_mark": "heatmap"}
  ],
  "validators": ["metric_reconciliation", "small_sample_suppression", "risk_suitability_check",
                 "evidence_completeness", "chart_spec_validation", "accessibility_validation"],
  "evaluation_suite": "product_holding_gap_eval_v1",
  "human_review_required": false
}
```

## 3. InsightCard（对齐方案 4.11）

```json
{
  "card_id": "IC_...",
  "title": "稳健型理财配置缺口明显",
  "fact": {"text": "64位客户中46位活期及短期存款占比超过70%", "metric_ids": ["customer_count","liquid_asset_ratio"], "evidence_ids": ["EV_001"]},
  "benchmark": {"text": "较同AUM层级客户高21个百分点", "benchmark_id": "SAME_AUM_BAND", "benchmark_name": "同AUM层级客户", "evidence_ids": ["EV_002"]},
  "diagnosis": {"text": "资金已入账但配置深度不足", "type": "rule_based_inference", "confidence": 0.91},
  "action": {"eligible_customer_count": 28, "priority": "high", "recommendation": "入金后3个工作日内优先触达", "rule_ids": ["OPP_RULE_V1"]},
  "boundary": {"text": "仅用于营销机会识别，产品推荐仍执行适当性规则", "data_as_of": "2026-09-24", "sample_size": 64},
  "provenance": {"skill_id": "product_holding_gap", "skill_version": "1.0.0", "data_as_of": "2026-09-24", "trace_id": "..."}
}
```

## 4. InsightChartSpec（对齐方案 4.8.5）

```json
{
  "schema_version": "1.0",
  "chart_id": "CHART_...",
  "intent": "category_comparison",
  "chart_skill": "chart.intent.compare_categories",
  "title": "目标客群与同AUM层级客户的产品持有率对比",
  "subtitle": "数据截至2026-09-24",
  "dataset_ref": "DATASET_...",
  "fields": [
    {"field": "product_category", "semantic_type": "category", "role": "dimension"},
    {"field": "holding_rate", "metric_id": "wealth_product_holding_rate", "semantic_type": "percentage", "role": "measure", "unit": "percent"},
    {"field": "audience_type", "semantic_type": "series", "role": "group"}
  ],
  "rows": [{"product_category": "理财", "holding_rate": 12.5, "audience_type": "target"}],
  "transforms": [{"type": "sort", "by": "holding_rate", "order": "desc"}],
  "view": {"mark": "bar", "orientation": "horizontal", "encoding": {"x": "holding_rate", "y": "product_category", "color": "audience_type"}},
  "annotations": [{"type": "highlight", "category": "理财", "text": "较基准低21个百分点", "evidence_id": "EV_002"}],
  "interaction": {"tooltip": true, "legend_filter": true, "drill_down": []},
  "accessibility": {"summary": "目标客群理财持有率显著低于同AUM层级客户", "data_table": true, "do_not_use_color_only": true},
  "export": ["svg", "png"],
  "provenance": {"skill_id": "product_holding_gap", "skill_version": "1.0.0", "metric_versions": ["wealth_product_holding_rate@1.0"], "data_as_of": "2026-09-24", "transform_hash": "sha256:..."}
}
```

`view.mark` 白名单：`kpi | table | bar | line | area | stacked_bar | pie | histogram | scatter | heatmap | funnel | waterfall | treemap`。
`rows` 为**已聚合、已校验**的数据（图表渲染器不得再计算），前端负责按 `view` 渲染。

## 5. 三个核心 Skill

| skill_id | 名称 | 层 | 分类 | 默认基准 |
|---|---|---|---|---|
| `audience_asset_structure` | 客群资产结构透视 | L1 | fact | ALL_BRANCH |
| `product_holding_gap` | 产品持仓缺口诊断 | L2 | diagnostic | SAME_AUM_BAND |
| `marketing_opportunity_priority` | 营销机会优先级排序 | L3 | action | ALL_BRANCH |

场景包 `large_inflow_conversion`（大额入金转化）= 三个 Skill 顺序组合。

## 6. Java 侧表与路由

表（迁移脚本 `sql/migration/V20260924_01__skill_management.sql`）：

| 表 | 用途 | 关键列 |
|---|---|---|
| `tl_skill_run` | 运行记录（Java 侧留存，用于权限化查询） | run_id(PK), skill_id, skill_version, audience_id, audience_name, customer_count, status, blocked_reason, duration_ms, operator_id, operator_name, trace_id, create_time |
| `tl_skill_audit` | 管理动作审计 | audit_id(PK,AUTO), skill_id, version, action, operator_id, operator_name, reason, result, create_time |

菜单（同一迁移脚本，保持幂等 `NOT EXISTS` 写法）：

| menu_id | 名称 | 父 | path | component | perms |
|---|---|---|---|---|---|
| 2147 | 洞察技能 | 2100 | skill | taglibrary/skill/index | `taglibrary:skill:list` |
| 2148 | 技能查询 | 2147 | # | # | `taglibrary:skill:query` |
| 2149 | 技能发布下线 | 2147 | # | # | `taglibrary:skill:publish` |
| 2150 | 技能试运行 | 2147 | # | # | `taglibrary:skill:run` |

Controller：`/taglibrary/skill`
- `GET /list`（`taglibrary:skill:list`）→ 代理 `GET /skills`
- `GET /{skillId}`（`taglibrary:skill:query`）→ 代理 `GET /skills/{id}`
- `GET /{skillId}/versions`（`taglibrary:skill:query`）
- `POST /{skillId}/status`（`taglibrary:skill:publish`）→ 代理 + 写 `tl_skill_audit`
- `POST /{skillId}/run`（`taglibrary:skill:run`）→ 解析客群成员 → 代理 `POST /skills/{id}/run` → 写 `tl_skill_run`
- `GET /runs`（`taglibrary:skill:list`）→ 查 `tl_skill_run`

客群成员解析：复用 `ruoyi-objectgroup` 的规则引擎（`ITlObjectGroupService` + `IRuleSqlBuilder`），按 groupId 取 `rule_json` → 生成 `MODE_SELECT` SQL → 取 cust_id 列表（上限 100000）。成员为空视为 422。

### 6.1 智能工作台入口（tagpilot-assistant）

圈选会话页在输入框下方提供 `SkillDock`（`src/SkillDock.tsx`），把"选客群 → 选技能 → 出洞察"串成一条线：

1. **添加 Skill**：点击"＋ 添加 Skill"懒加载 `GET /taglibrary/skill/list?status=published`，多选后以 chip 形式挂在输入框下方；可移除，可切换对比基准（默认按各 Skill 的 `default_benchmark`）。
2. **对客群运行**：仅当本会话已按当前方案版本创建客群（`thread.execution.revision === thread.revision`）时可用，串行调用 `POST /taglibrary/skill/{skillId}/run`，请求体 `{groupId, benchmarkType?}`；成员名单由后端解析，前端不传客户号。
3. **结果呈现**：`src/SkillChart.tsx` 直接消费引擎下发的 `InsightChartSpec` 渲染（KPI / 表 / 条形 / 堆叠 / 饼 / 折线 / 漏斗 / 散点 / 热力，未知 mark 降级为数据表），洞察卡按事实—对比—诊断—行动—边界五段展示，并折叠运行校验与证据清单。运行失败只展示后端中文原因（如样本不足、数据未就绪）。
4. 切换圈选会话即切换目标客群，已添加的 Skill 与运行结果不跨会话沿用。

## 7. 数据与治理约定

- Skill 只读 `ry.ind_tag_data`（标签宽表，无姓名等直接标识字段），只输出聚合值与客户数。
- 小样本抑制：`min_customer_count` 默认 20，低于阈值时 Skill 返回 `blocked`，不输出任何分组明细。
- 风险适配：`risk_rating` R1/R2（保守/稳健）不得产出基金、信托类机会。
- 排除规则：`blacklist_flag` / `fraud_alert_flag` 客户不进入机会名单。
- 图表数据只含聚合结果，`rows` 中不含客户标识。
