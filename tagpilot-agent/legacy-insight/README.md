# TagPilot 洞察 Skill 库

独立、只接受聚合数据的 Python 库，实现 G1 客群资产结构透视、G2 产品持仓缺口诊断、G3 营销机会优先级排序。依据《Skill体系.md》，并对齐亮点二的指标语义、五段卡、统计证明与发布治理。P0–P7 已完成本批代码与固定合成验证；真实业务绑定、目标 MySQL 和服务整链验收仍待接入。

库不连接数据库、不接收客户明细、不生成任意 SQL、不依赖 Agent SDK，也不增加服务端口。Java 拥有身份、资格、当前来源 / 方案版本、白名单 SQL、发布治理和保存；现有 `tagpilot-agent` 导入本库完成聚合事实计算和 Guard。真实请求缺绑定时返回 BLOCKED / PARTIAL，不使用 fixtures 回退。

## 验证

```bash
# 仓库根目录：实际 Java H2 SQL → Python → 独立手算，随后运行64项库测试
bin/verify-insight.sh
# 本库测试 / 包内合成门禁
cd tagpilot-insight
uv sync --extra dev
.venv/bin/python -m pytest -q
.venv/bin/python -m tagpilot_insight.cli verify --output reports/p0-p1-verification.json
```

固定 SQL 验证：240 人客群 / 800 人合成来源；G1 总 AUM 1.2 亿元，G2 理财缺口 45pp、机会 120 人，G3 可营销 180 人、高中低 80/60/40。期望常量在 `tagpilot-eval/tagpilot_eval/insight.py` 独立登记。包内 fixtures 是模板与 Guard 材料，不能证明实际绑定 SQL 正确。

## 模块与契约

| 文件 | 用途 |
| --- | --- |
| `contracts.py` / `aggregates.py` | 严格 Manifest、MetricBinding、客群快照、Fact、五段卡、ChartSpec、报告和聚合契约；拒绝客户行与 SQL |
| `metrics.py` | 指标定义 / 单位 / 来源 / 质量 / 版本与四种基准，责任人待业务复核 |
| `planning.py` | 当前发布 hash、快照、绑定、资格、参数、时效、样本校验；只输出四种白名单 MetricQuery |
| `compose.py` / `statistics.py` | G1计算；G2标准化与 Wilson / Bonferroni 证明；G3分档 / 贡献 / 原因组合对账 |
| `guards.py` | 事实算术、权重、引用、统计证明、行动范围、图表对账、版本及因果边界 |
| `charts.py` | DataProfile→六意图→规则选图→六原子→三个默认仪表板 |
| `interaction.py` / `narration.py` | 一次路由 / 改图 / 叙述候选；无效回退；数据或口径须确认，视图不更换事实 |
| `evaluation.py` / `registry.py` | 固定合成包门禁、当前代码 hash；Java 保存真实复核状态 |
| `skills/` / `fixtures/` | 三个 DRAFT / 0.1.0 代码包与明确 synthetic 的固定聚合材料 |
| `schemas/` / `reports/` | 导出协议、包内验证和独立 SQL 验证结果 |

文字数字只能通过 `{fact:xxx}` 展开。STAT 诊断必须附可重算证据并通过阈值与区间不重叠判定；评分为未校准的 HYPOTHESIS。小样本及互补格由 Java 抑制后输出，Python 不反推人数；稀疏 G2 格在 Java 内先合并单维，仍不满足时抑制。缺适当性仅保留覆盖事实并标 L2。

允许的图表是 KPI、table、bar、stacked_bar、heatmap、funnel。不能传入原始 ECharts option、函数或 HTML。结果绑定 revision / plan hash / snapshot / 日期 / binding version / pack hash；Java 补充注册版本与定义 hash。包 hash 包含库代码与 fixtures，代码变化后旧发布门禁失效。

## 生成共享产物

```bash
.venv/bin/python -m tagpilot_insight.cli schema --output schemas
.venv/bin/python -m tagpilot_insight.cli preview --output ../tagpilot-assistant/src/insight/synthetic-preview.json
.venv/bin/python scripts/export_sql_test_inputs.py ../ruoyi-taglibrary/src/test/resources/insight/metric-plans.json
```

fixture 中 hash 是零占位；仅显式 synthetic 加载器换为当前 hash。真实报告必须使用 Java 校验过的 `published_hashes`，不能以文件 DRAFT 状态或 synthetic 标记替代授权。

## 工作台与开发预览

正式工作台先统计当前圈选人数；运行洞察时由 Java 再次实时统计，客户数无需标签绑定或手工配置。添加已发布技能 / 场景包 chip，确认后运行。报告提供独立摘要、右栏 / 宽模式、事实与边界、改图 Ask、反馈与 SVG / PNG；方案失效则禁导出和修改。模型默认关闭，关闭时仍可执行确定性计算。

```bash
cd ../tagpilot-assistant
npm run dev
# 开发专用固定预览：/agent-ui/?insightPreview=1
npm test
npm run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm run test:e2e -- --grep '正式洞察|合成报告|condition edits invalidate count'
```

生产构建不包含开发预览。ECharts 5.4 按需加载，交互 SVG、临时 Canvas PNG；SVG metadata 保存 ChartSpec 和聚合事实。59 项前端单元测试、5 项 mock E2E 与 React / Vue 构建通过；图表 chunk 仍有 >500kB 构建提示。

架构、发布 / 缓存、权限、验证范围与真实接入步骤见 [实施记录](../docs/development/洞察Skill体系实施记录.md)。本批未应用迁移、发布真实绑定、调用模型、部署或提交。
