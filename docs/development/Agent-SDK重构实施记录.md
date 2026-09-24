# Agent SDK 重构实施记录

实施日期：2026-09-24。对应方案：`.cursor/plans/tagpilot_agent_sdk_重构_f2f40d36.plan.md`。按用户要求完成本地实现，测试与评测只做金标流程冒烟，完整评测由后续独立对话执行。未部署、未提交 Git、未执行客户统计或建群。

## 已落地范围

| 方案项 | 本次实现 | 验证 / 保留事项 |
|---|---|---|
| Phase 0 收敛与 Spike | SDK 0.1.50 + MCP 1.x 锁定；DeepSeek Anthropic；tools=[]、严格 MCP、临时配置目录、停止钩子与 interrupt；Java 状态校验、time_parse、遥测 | 真 SDK/假网关 A01，真模型 A01/B02；基线、thinking A/B、压力与 P99 未执行 |
| Guards/domain | 严格 Pydantic 输入、原文/数值/单位/时间、需求覆盖、逻辑签名、冻结条件、增删改授权、手工编辑共用 Guard、结构化诊断 | 数值修改不能授权改变逻辑；确认只对相同条件和定义有效 |
| Tools/WorkingSet | find_tags / get_tag_details / find_capabilities / check_plan / submit_result；版本与 eligible_hash 隔离；6KB 输出；需求级检索留痕；拒绝提交三次后强制 PARTIAL | READY 需全部 BOUND；提问先查证；声明缺口须有 deep/能力检索记录 |
| Runtime/API | 单 Agent；默认并发 2、每用户 2、队列 24/20秒、工具/轮次/时间/成本/RSS预算；取消、最佳草案、失败重试、冷 resume、Java repair 至多两次 | SQLite 单进程租约；多实例部署仍需共享领取机制或粘性路由 |
| 检索 | 词法 `/lookup`、`fast/deep`、合批编码与重排的 `/retrieve_batch`、重排候选默认30、eligible LRU、码值查询与同族证据 | Strong 默认保留；Bounded 和置信度跳过重排均有开关，待封存集 A/B 后启用 |
| 性能 | L0 prefetch、进程证据缓存、精简卡片、立即停止、编辑免 SDK | 预取集成在 context_builder；冷启动本次样本 0.167–0.509秒，未触发方案“超过1秒才启用预热池”的条件，因此不实现常驻空闲池 |
| Java/UI | TsPlanValidationException 显式诊断码与 clause_id；TsAgentOutcome；confirmed_clause_ids；需求缺口、移除/近似范围操作、业务工具文案；运行中只展示草案，终态才编译和应用版本 | Java 编译、权限与执行仍是权威；修改已确认定义需再次确认；草案不允许执行 |
| 旧图清理 | 删除 workbench_graph / planner_prompt / catalog 及 LangGraph/LangChain/OpenAI Python依赖；实现迁入新包；RunStore 不再依赖图检查点；新结果使用 diagnostics | 纯函数旧模块是薄导入兼容入口，UI 兼容读取历史 validation_errors；旧磁盘检查点未删除，不再访问 |
| 高级能力评估 | 保持单 Agent、冷恢复与固定工具注册 | 洞察聚合端点需要单独 Java 授权契约；热恢复可能保留过期资格/定义；SDK skills 会扩展当前禁用的文件工具边界。均不在本次启用 |

API、环境变量和启动方式见 [Agent README](../../tagpilot-agent/README.md)。语义服务默认仍是 8091，Agent 是 8092。网关设置必须使用 Anthropic 协议；旧 OpenAI URL 仅在启动脚本确认是官方 DeepSeek 时转换。

## 本次证据

汇总留档：[gold-smoke-summary.json](../design/agent-sdk/gold-smoke-summary.json)。所用本地发布工件为 `bge-m3-l107-20260919-002-r3`，快照 `L107-20260919-002`。资格来自固定快照，不冒充某个当前登录用户的 Java 实时授权。

| 验证 | 结果 |
|---|---|
| 真实 SDK/CLI + 本地假 Messages 网关，A01 | READY；只暴露5个领域工具；接受 submit 后网关请求总计1次，无额外收尾调用 |
| 真实 DeepSeek + 真实语义服务，A01 全部客户 | READY，4.76秒 |
| 真实 DeepSeek + 真实语义服务，B02 转入金额/非销户/风评码 | READY，9.31秒；深度检索0次，命中词法预取与详情 |
| 两个金标方案的独立合成输入验证 | A01 1组、B02 54组，共55组边界，差异0；覆盖NULL、阈值、布尔码、C3/C4/C5与未知码 |
| Java TsAgentSdkGoldenSmokeTest | 1例通过；读真实 B02 方案和发布快照，以受控 catalog/tag mock 编译 RulePayload v4，核对1291≥500000、601=0、1466∈C3/C4/C5；不连接业务数据库 |
| Agent 定向冒烟 | 9例通过：金标/API/编辑、缺口查证、字面量、业务码、修改授权、冷恢复/repair、逻辑冻结、确认绑定与已发布定义手工确认 |
| Semantic 定向冒烟 | 1例通过：词法 lookup、fast batch、资格隔离、详情 |
| React 构建与定向浏览器案例 | TypeScript/Vite 构建通过；缺口展示且禁止执行案例通过，1440/390宽度各一次截图复核 |

原始本地报告：`tagpilot-agent/out/sdk-gold-smoke.json` 中保留 A01 成功和早期 B02 失败；B02 最终证据为 `tagpilot-agent/out/sdk-gold-b02-final.json`。不要把包含开发失败的初始报告当作全绿结果。早期迭代发现并修复了 MCP 2.x 不兼容、网关 AUTH_TOKEN 配置、数字码值统一为字符串，以及业务码 C3 被误识别为数值阈值的问题。真实模型调用已经用户明确授权，发送内容限于两个需求和已发布标签定义/码值，没有客户明细。

`llm_turns` 是 SDK 报告的轮次，未当作精确网关请求计数；只有假网关的 `requests` 是实数。`sdk_cost_estimate_usd` 是 SDK 估值，不是 DeepSeek 账单。两次成功耗时不是 p50/p95。上述金标未走 deep 重排，不证明其实际召回质量或性能。截图为本地 UI mock，不代表真实线上全链路验收。

前端构建存在原有大于500KB包体提示；Playwright 初次调用因未安装默认 Chromium 未启动，改用本机 Google Chrome 后通过。未为此安装浏览器。设计工具检测未发现本次代码阻断；仓库 PRODUCT.md/design.json 的旧结构与侧车状态需后续使用 impeccable init/document 单独同步，本次未修改产品设计上下文。

## 后续完整评测入口

以下命令是复现入口，除上文记录的指定案例外本次没有执行全量测试：

```bash
# SDK/Guard 定向冒烟
PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python -m pytest tagpilot-agent/tests/test_sdk_smoke.py -q
# 本地假网关；在 tagpilot-agent/ 下运行
PYTHONPATH=. .venv/bin/python scripts/sdk_gateway_smoke.py
# 真实模型只读金标；先设置 Anthropic / semantic 端点与服务令牌
PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python tagpilot-agent/scripts/evaluate_workbench.py \
  --runtime claude_sdk --index <发布索引目录> --snapshot <snapshot.jsonl> \
  --cases A01,B02 --repeat 1 --output tagpilot-agent/out/sdk-gold.json
PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python tagpilot-agent/scripts/verify_smoke_plans.py tagpilot-agent/out/sdk-gold.json
# Java 单金标编译，参数必须指向含 B02 的报告与对应快照
mvn -pl ruoyi-taglibrary -am test -Dtest=TsAgentSdkGoldenSmokeTest \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtagpilot.sdk.smoke=<报告绝对路径> \
  -Dtagpilot.sdk.snapshot=<快照绝对路径>
```

后续需要执行：完整 Guard/工具/SDK异常/取消/并发/Java/UI契约测试；61案例×3对照；600条封存集 A/B；真实 COUNT/ID 对齐；12并发和RSS P99；生产观察及上线门禁。新 runner 只支持 `--runtime claude_sdk`；历史 LangGraph 基线应在迁移前独立 checkout 使用原脚本，不能在已删除图实现的工作树中假装双运行时对照。

语义侧可配置 `TAG_RERANK_K`（默认30）、`TAG_RERANK_SKIP_CONFIDENT=true`（默认false）、`TAG_RERANK_MARGIN`（默认0.03）、`TAG_MILVUS_READ_CONSISTENCY=Bounded`（默认Strong）。封存集质量门禁未执行前保持当前默认。

## 发布与回滚边界

本次按“全量实施”在本地完成旧图删除；方案中“生产稳定两周且评测达标”尚未满足，所以这不是已批准的上线切换。未创建 `pre-langgraph-removal` tag，迁移前可核对的 HEAD 是 `6a7571977d0f97868a2bf6fb23077e43f920fa74`。发布前应先提交、保留正式回滚标记、备份加密运行库及密钥，并演练旧记录读取和冷恢复。

当前代码的 `TAG_AGENT_RUNTIME=langgraph` 会明确拒绝启动运行，回滚需恢复旧版本代码和锁文件，不能只改环境变量。旧 `.checkpoints` 文件不会自动清理；确认旧版回滚窗口结束后再由运维清理。本次没有执行数据库迁移、Docker 生命周期命令或生产发布，已有 Redis/Milvus 保持不变。

SDK 参考：[Claude Agent SDK Python](https://code.claude.com/docs/en/agent-sdk/python)、[DeepSeek Anthropic API](https://api-docs.deepseek.com/guides/anthropic_api/)。版本与实际配置以本次锁文件及代码为准。
