# 洞察元 Skill 底座实施记录

2026-09-30。在「Agent 原生 Skill 登记与调用」（见 [`Agent原生Skill接入.md`](Agent原生Skill接入.md)）之上，落地上传文档《元skill体系》的**分析元 Skill + 图表元 Skill 底座**：六个顶层技能、统一结果契约、种子与登记、工作台结果渲染，并用真实模型做了带/不带技能的对照验证。本轮不接入真实指标取数，技能在缺少指标时按契约显性声明缺口。

## 一、技能体系

顶层只注册 6 个技能（对应上传文档的 `analysis/` 与 `charts/` 两组），具体图表形态放在 `chart-atomic` 的参考资料里，不膨胀顶层技能数量：

| 技能 | 分类 | 调用方式 | 职责 |
| --- | --- | --- | --- |
| `fact-analysis` 客群基础事实分析 | `fact` | 用户 `/` 可选 | 回答"这批客户是什么样"；条件复述、规模事实、缺口声明 |
| `diagnostic-analysis` 客群诊断分析 | `diagnosis` | 用户 `/` 可选 | 回答"哪里值得关注、为什么"；基准对比、下钻、差异≠原因 |
| `action-decision` 客群行动决策 | `decision` | 用户 `/` 可选 | 回答"接下来做什么"；规则漏斗、优先级、合规红线 |
| `chart-atomic` 图表原子层 | `chart` | 仅模型链式调用 | 将事实编译为一张符合平台协议的 `InsightChartSpec` |
| `chart-intent` 图表意图层 | `chart` | 仅模型链式调用 | 先定"表达什么"再选图；数据不足时落空图表清单 |
| `chart-compose` 图表组合层 | `chart` | 仅模型链式调用 | 多图按「KPI→差异→结构→明细」排序与去重 |

技能内容源码在仓库根 `skills/`（`analysis/`、`charts/`、`shared/`），编辑规则见 [`skills/README.md`](../../skills/README.md)。`shared/result-contract.md` 是三个分析技能共用的结果契约，由生成器按文件名分发进每个分析技能包的 `references/`（运行时技能包彼此独立，不能跨包读文件）。

## 二、结果契约与渲染闭环

技能最终答复以 ```insight-result 围栏块输出结构化结果（status/reasons/facts/cards/charts/followups），与工作台既有洞察报告组件同构：

```
技能运行 → 模型按 SKILL.md 产出正文 + insight-result 块
        → Python 抽取校验（skills/packages.py::extract_result），块内 JSON 必须严格合法
        → Java 服务端再校验并组装（TsAgentWorkbenchService::skillReport）：
           注入 skill_id/display_name/version/pack_hash/level、cohort（人数/方案哈希/数据日期）、
           卡片 boundary 的 skill_version/data_as_of；丢弃会破坏渲染的卡片与图表
        → 线程状态 skill_report → 工作台右栏「洞察」面板（复用 InsightReportPanel + ECharts）
```

- 数字纪律：`AVAILABLE` 数值只允许是服务端核验的人数与条件原文阈值；其余指标必须登记 `MISSING`。卡片里的事实引用（`{fact:id}`）在 Java 侧逐个核验，引用不可用事实的卡片整卡丢弃（前端渲染会拒绝）。
- 图表 spec 复用既有 `chartGuard` 约束（kind/intent 映射、对账、抑制格、标注数字必须绑定事实等），由 `chart-atomic` 的参考资料逐条教给模型。
- 缺少基准或规则服务时，诊断/行动技能输出"未形成诊断/不产出行动对象"并说明缺什么，而不是编造结论。

## 三、系统与 Agent 改造点

| 位置 | 改动 |
| --- | --- |
| `tagpilot-agent/skills/packages.py` | 新增 `extract_result()`：抽取最后一个 ```insight-result 块，大小上限 256KB，解析失败降级纯文本 |
| `tagpilot-agent/runtime/run_manager.py` | 技能运行完成后写入 `skill_result`；失败路径补 `logger.exception`（原先只回通用文案，排障靠猜） |
| `tagpilot-agent/runtime/claude_runner.py` | 技能运行的轮次口径改为「观测到的模型请求数」——按 AssistantMessage 逐条计数会被内容块拆分放大（实测 5 次请求记到 16 轮），在链条中途误判 max_turns 中断 |
| `ruoyi-taglibrary/TsAgentWorkbenchService` | `skillReport()`：服务端校验 + 组装 `skill_report`（含 cohort 包装、包元数据注入、非法卡片/图表按条丢弃）；`view()` 原样下发 |
| `tagpilot-assistant` | 右栏洞察面板支持 `skill_report`（不挂旧链路的改图/反馈操作）；`display_name` 显示；技能报告到达后自动切到「洞察」页；渲染「建议下一步」列表；`cohort.count` 允许"人数未统计" |
| `bin/tagpilot-agent.sh` | 模型配置加固：`TAG_LLM_*`（DeepSeek 官方地址映射）强制覆盖宿主环境残留的 `ANTHROPIC_*`。桌面会话启动 agent 会把宿主中转地址带进进程导致模型请求全部 401，本次实测踩中后修复 |
| `bin/build-agent-skill-seed.py` | 新增：从 `skills/` 源码生成 `sql/seed/agent-meta-skills.sql`（幂等，含 `shared/` 分发与全套平台校验） |
| `bin/verify-insight-skills.sh` + `tagpilot-agent/scripts/skill_evals.py` | 新增：真实模型评测工具（带技能 vs 无技能两组，程序化断言 + skill-creator 查看器工作区） |

## 四、登记与种子

- 六个技能以「已发布」状态登记进 `ts_agent_skill`（`sql/seed/agent-meta-skills.sql`，由源码生成，idempotent），洞察技能页面直接可见、可编辑、可下线。
- 导入必须显式 `--default-character-set=utf8mb4`（`bin/db-migrate.sh` 自带；手工导入忘记会双重编码中文）。
- 后续内容修订走登记台草稿→发布流程（发布须升版本号）；种子只用于初始化与本地开发刷新。
- 本地库已执行 `V20260921_04 ~ V20260930_01` 六个待应用迁移与技能种子。

## 五、验证证据（2026-09-30）

| 层 | 结果 |
| --- | --- |
| Python 单测 | 212 passed（含抽取、物化、越界、保留词、种子 SQL 往返、SDK 假网关整链；顺带修复了 `test_p3_pending_questions` 使用真实 RunContext 的既有夹具问题） |
| Java 单测 | 293 passed（taglibrary 193 / objectgroup 70 / databroker 30；新增：报告组装、非法卡片/图表丢弃、纯文本降级） |
| 前端单测 | Vitest 59 passed |
| 浏览器 e2e | Playwright 47 passed（新增 `skill-report.spec.ts`：面板自动切换、卡片、KPI、过期标记、双端宽度；修 4 处上一轮 UI 文案改动留下的过期定位符） |
| 真实模型评测 | `bin/verify-insight-skills.sh`，5 个用例（大额入金客群的事实/诊断/行动、12 人小客群、未统计人数）× 带/不带技能：带技能 **51/51 断言**，无技能 32/40；查看器人工审阅（1 条反馈） |
| 真实端到端 | 本地全栈：圈选线程（1,422 人、方案 v1）→ 工作台技能运行 → 约 25 秒 COMPLETED → 右栏自动展示报告（2 张卡 + 规模 KPI + 导出），登记页与工作台截图留档 |

## 六、已知边界与下一步

1. **指标取数未接入**：技能在事实层只能使用人数与条件阈值，资产/产品/结构指标全部按 `MISSING` 声明。取数通道接入后，技能内容无需修改即可扩充事实与图表（契约已就位）。
2. **图表组合层尚未用武之地**：当前单 KPI 场景下 `chart-compose` 不会被触发；多指标接入后自然生效（评测用虚构数据验证过其规则）。
3. **技能报告的操作能力**：改图/反馈只挂在旧洞察链路上；技能报告暂不支持图表微调与评分反馈，需后续设计对应接口。
4. **本轮不修改生产数据**：真实环境的迁移与技能发布由部署流程执行（`bin/db-migrate.sh` + 种子或登记台）。
5. 模型效果仅在 DeepSeek（本机配置）上验证；更换模型后建议重跑 `bin/verify-insight-skills.sh`。
