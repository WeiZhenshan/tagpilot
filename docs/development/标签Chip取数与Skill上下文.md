# 标签 Chip 取数与 Skill 分析上下文接入

2026-09-30。在 [元Skill底座实施记录](元Skill底座实施记录.md) 之上补齐它列出的已知边界第 1 条（指标取数未接入）：圈选并核验（暂存）方案后，用户选中 Skill、补充分析目标时，可把左侧标签栏的标签作为 chip 选入，服务端按这些标签从**当前已核验客群**取出列级统计与脱敏明细，注入 `cohort_context`，技能据此产出有真实数据支撑的事实与图表。

## 一、交互

- 技能运行不再禁止携带标签：删除前端「技能使用右侧已核验的客群条件，请先移除输入框中尚未处理的标签」拦截、Java 的 `!pinned.isEmpty()` 闸门、Python 的 `profile=='skill'` 必须 `pinned_tag_ids` 为空。
- **方案内标签在技能模式下可再选**：条件是阈值（如 AUM ≥ 50 万），该列在客群内仍有分布，仍有分析价值。左栏提示改为「所选标签将作为「XX」的分析列，从当前客群取数」；取消技能后恢复原有限制，与方案冲突的 chip 自动清理。
- 标签可选但非必需：不选标签时技能行为与之前完全一致（人数 + 条件阈值事实）。
- 仍被拒绝的组合：技能运行携带 `edited_plan`、`context_only=true`（仅选标签无分析目标）、`plan.valid=false`、越权或跨库标签。

## 二、取数契约

`TsAgentWorkbenchService.start()` 在技能分支组装 `cohort` 时新增三个字段。

`tag_stats`（每个 chip 一项，≤5）：`tag_id` / `label` / `tag_type` / `unit` / `unit_source` / `plan_tag` / `status` / `reason` / `sample_size`，以及二选一的 `numeric` 或 `categories`。

- 数值型：`{n, missing, min, max, sum, avg, median}`，`query_id` 形如 `tagstat.<tag_id>.avg`。数值按标签语义层登记的换算系数折算到 `unit` 上（`unit_scale`，如万元口径 ×10000 得元）；`RATIO`/`SHARE` 的物理值是 0~1 的小数，按 `%` 输出时再乘 100。`n`/`missing` 是人数，不折算。
- 分类型（选项型/布尔型）：`[{code, label, count, share}]`，`query_id` 形如 `tagstat.<tag_id>.cat.<code>` / `tagstat.<tag_id>.share.<code>`；码值中文名来自既有维表码值服务，缺失时回落原始编码。分布计数与占比的单位是天然的「人」「%」，与标签自身是否登记量纲无关。
- 文本型/日期型/客户号：`UNSUPPORTED`，不产出数值。
- **单位**取自既有标签语义层 `ts_tag_semantic.unit` / `unit_scale`：`CNY→元`、`COUNT`/`PERSON→人`、`POINT→分`、`RATIO`/`SHARE→%`；`DAY`/`MONTH`/`NONE`/未登记一律 `null`，对应的**数值统计**不得登记为 AVAILABLE 事实（分布计数不受此限）。本轮不需要任何数据库迁移。
- 抑制：客群人数 < 20 时不下发；分类取值 `0<n<20` 或互补格 `0<总数-n<20` 时整组 `SUPPRESSED`；分类超过 24 类要求治理合并，不造「其他」桶。
- `plan_tag=true` 标记该列已被圈选条件截断，技能须在卡片边界里声明。

`sample_rows`：所选标签列 + 客户号（首字符 + `*` + 末 4 位脱敏）的明细，`LIMIT 100`，客群 < 20 人时不下发。用户明确接受客户级明细进入模型提示词；提示词与技能契约要求它只用于观察分布，不得产出个体结论。

`stats_note`：降级说明（人数漂移、数据集无在线版本、取数失败等），正常为空串。

## 三、服务端复核

`TsAgentWorkbenchService.skillReport()` 增加窄口径数值复核：从 `cohort_context.tag_stats` 建 `query_id → 值` 白名单（只收 `AVAILABLE` 且 `unit` 非 null 的条目），fact 的 `query_id` 命中 `tagstat.*` 时取值必须一致（`%` 容差 0.05pp），挂名引用却改数或引用未注入统计量的整条丢弃。未声明 `tagstat.*` 的事实维持原有结构校验，不误杀模型自算的派生百分比。

Python 侧 `RunRequest` 仍只做结构校验；提示词 `system` 改为「事实证据只有条件、有效人数与 `tag_stats` 中的服务端统计；`sample_rows` 是脱敏明细，只用于观察分布」。

## 四、改动点

| 位置 | 改动 |
| --- | --- |
| `ruoyi-taglibrary/TsTagStatsService`（新增） | chip 取数：复用 `RuleSqlBuilder.MODE_IDS` 作 `key in (...)` 子查询、`TlObjectGroupExtMapper` 定位宽表与列、`DpOnlineVersionResolver` + `JdbcConnectionFactory` 建只读连接、`TsTagSemanticMapper` 取单位；列名过 `[A-Za-z_][A-Za-z0-9_]{0,127}` 白名单。20 秒总预算、单语句 15 秒、`maxRows 25`；单标签失败只降级该条 |
| `TsAgentWorkbenchService` | 技能分支放开 pinned、拒绝 `context_only`、注入 `tag_stats`/`sample_rows`/`stats_note`、`planTagIds` 遍历方案树、`skillReport` 数值复核 |
| `tagpilot-agent/api/schemas.py` | skill 分支改为拒绝 `pinned_only`，允许 `pinned_tag_ids` |
| `tagpilot-agent/runtime/claude_runner.py` | system 提示词补充证据边界 |
| `tagpilot-assistant/src/App.tsx`、`TagTree.tsx` | 解锁技能 + 标签、chip 随技能运行发出并在成功后清空、`usedTags` 在技能模式下为空、左栏提示文案 |
| `skills/shared/result-contract.md`、三个分析技能与 `metric-catalog.md` | AVAILABLE 数值来源由两类扩为三类；新增 `tag_stats` / `sample_rows` 使用规则；分析技能版本升到 1.1.0 |
| `sql/seed/agent-meta-skills.sql` | 由 `bin/build-agent-skill-seed.py` 重新生成 |

未改动 `TsInsightQueryService`（旧洞察链路，仅作范式参照）。本轮不接基准通道：`diagnostic-analysis` 仍按「无基准」出 RULE 依据结论，`tag_stats` 只覆盖当前客群自身。

## 五、验证证据（2026-09-30）

| 层 | 结果 |
| --- | --- |
| Java 单测 | `ruoyi-taglibrary` 211 passed（含新增），`ruoyi-objectgroup` 70、`ruoyi-databroker` 30 全绿；新增 `TsTagStatsServiceTest` 14 例（合计/均值/中位数、量纲映射与折算、比率 ×100、万元 ×10000、无单位不产事实、分类分布与 share、小格整组抑制、跨库标签只降级自身、人数漂移全弃、未统计人数只说明原因、明细脱敏与列裁剪、低于抑制阈值不取数、空选择不连库、列名注入被拒）与 `TsAgentWorkbenchServiceTest` 4 例（技能携带标签并注入统计、仅选标签 / 编辑方案被拒、伪造 `tagstat.*` 数值被丢弃、分布事实不因标签无量纲被误杀） |
| Python 单测 | 284 passed（新增技能携带 pinned 合法、`edited_plan` / `pinned_only` / 未核验方案 / 越权标签各自拒绝、技能提示词含 `tag_stats`） |
| 前端单测 | Vitest 59 passed；TypeScript 编译通过 |
| 浏览器 e2e | Playwright 48 个用例，新增「选中技能后左栏标签作为分析列随技能运行发出」：选技能 → 方案内标签可再选 → chip 入输入框 → 断言 `/runs` 请求体同时带 `skill_name` 与 `context_tag_ids`。既有 `workbench.spec.ts` 的「回到最新消息」滚动断言在本机为偶发失败（单文件/单用例重跑稳定通过），与本次改动无关 |
| 固定合成对账 | H2 建 800 人合成来源、客群 240 人，逐项核对合计 120,000,000 元、均值/中位数 500,000 元、分类 200/40 与占比 83.3%/16.7%、比率量纲 ×100 折算、万元量纲 ×10000 折算 |
| **真实全栈**（2026-09-30 16:00，重启后端与 Agent 后） | 会话「近30天有异名跨行转入的客户」（方案 v1、1,422 人）选 `fact-analysis` + 标签 721 当前时点AUM（CNY）、719 固收类AUM占比（RATIO）、673 潜力资产等级（选项型，未登记量纲），约 60 秒 COMPLETED，产出 3 张卡片、4 张图表、25 条事实 |
| 独立 SQL 对账 | 直接查 `indiv_cust.L_INDVCST_LABEL`（条件 `LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_FLAG=1`）逐项核对：人数 1422、AUM 合计 905,721,239.60、均值 636,934.77、中位数 38,614.37、固收占比均值 40.29% / 最小 0% / 最大 80.64%、等级六档 1137/121/82/32/24/26 与占比 80.0/8.5/5.8/2.3/1.7/1.8 —— 与报告完全一致 |

### 本轮真实运行暴露并修复的两个问题

1. **比率量纲少乘 100**：`RATIO`/`SHARE` 的物理值是 0~1 的小数（该列实测 0~0.806），直接按 `%` 输出会把 40.29% 写成 0.4%。已改为按 `unit_scale × 100` 折算。
2. **分布事实被单位门槛误杀**：分类计数的单位天然是「人」、占比是「%」，与标签自身量纲无关；原先 `unit` 为 null 时整条条目被排除在数值复核白名单之外，选项型标签的分布一条也出不来。已把数值统计与分布拆开判断。

同时补齐了 `PERSON→人`、`SHARE→%`、`POINT→分` 三个语料里实际存在的量纲。

## 六、已知边界

1. **未压测**：大客群下 `key in (MODE_IDS)` 的聚合性能（1 万 / 10 万 / 100 万级）未在目标库实测，超时走降级路径。本轮实测 1,422 人客群带 3 个标签的整轮约 60 秒（含模型），未见取数超时。
2. **客户级明细入提示词**是用户确认后的边界放宽，实际投放前建议按机构合规口径复核。
3. **单位覆盖依赖治理**：未在 `ts_tag_semantic` 登记可映射量纲的标签（`DAY`/`MONTH`/`NONE`）只能出分布事实，金额与数量类数值统计会退化为不可用事实；当前库内 `NONE` 多为布尔/文本/日期/选项列，影响面有限。
4. 基准通道、`median` 之外的统计量、按客户计数类指标（如人均产品数）仍属未接入。
5. 技能效果本轮只验证了 `fact-analysis` 一条真实链路；`diagnostic-analysis` / `action-decision` 未跑真实模型，但基准缺失时的降级路径由技能内容与既有评测覆盖。
