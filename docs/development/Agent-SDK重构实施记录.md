# Agent SDK 重构实施记录

实施日期：2026-09-24。对应方案：`.cursor/plans/tagpilot_agent_sdk_重构_f2f40d36.plan.md`。按用户要求完成本地实现，测试与评测只做金标流程冒烟，完整评测由后续独立对话执行。未部署、未提交 Git、未执行客户统计或建群。

> **2026-09-24 补记**：上句描述的是当天早些时候的实施状态。同日后续对话已执行完整验证（测试、600 封存 A/B、61×3 真模型评测、容量压测、Java 权威编译与模拟库人数对齐），结果与证据见下文“2026-09-24 后续完整验证”；代码已由用户提交；本轮执行了模拟库人数统计（未建群）。生产观察仍未执行。

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

## 2026-09-24 后续完整验证（本次对话执行）

依据实施记录“后续需要执行”清单逐项执行。除生产观察外均为本地实测；命令与原始证据见文末。

### 1. 测试（全部本地执行）

| 范围 | 结果 |
|---|---|
| Agent 契约/集成（tests/，含真 SDK/CLI + 假网关） | 78 例通过；新增 guards 18、tools 12、SDK 集成 12（多轮工具循环、一轮并行工具、Ask/WAITING、拒绝后修复、取消保留草案、硬超时取最佳草案、持续 5xx 降级、RSS 熔断、排队/每用户上限/队列超时、崩溃重试一次）；补 langgraph 明确拒绝、单进程文件租约、缓存跨用例隔离 |
| Java（ruoyi-taglibrary 全量） | 131 例通过（含结构化诊断 code/clause_id、repair 回灌、outcome/gaps 展示、执行门禁、XSS 排除断言）；B02 金标编译用例带参数通过 |
| 语义（lookup/retrieval/runtime/acceptance gates） | 33 例通过（1 例按条件跳过） |
| 前端（vitest + Playwright e2e） | 8 + 9 例通过（含 gap 卡片禁止执行）；修复 return-to-latest 用例 0.2s 过渡动画导致的 ±2px 抖动 |
| 旧运行库读兼容 | 开发运行库 51 条历史记录（最早 2026-09-21 旧版写入）经新代码与 API 正常解密读取；`workbench.sqlite.checkpoints`（100MB 遗留文件）仍在，按记录约定等回滚窗口结束后由运维清理 |

### 2. 600 条封存集 A/B（同一 build r3）

四组配置（Strong/Bounded × 置信度跳过重排开/关）全部通过全部门禁：失败项均为 2，hit@20 / final_hit@10 / query_exact_match 均为 1.0。插桩显示 600 题仅 3 次真正触发重排（绝大多数走精确别名快路径），纯检索 20.7–21.7 秒/600 题（≈35ms/题）。结论：**Bounded 一致性质量中性，可启用**；跳过重排开关在该集无法度量影响面（触发太少），建议在 deep 真实 query 集上补验。

### 3. 容量与资源分配（真 CLI + 假网关，scripts/capacity_probe.py）

| 剖面 | n | 峰值 RSS p50 | p99/max | 冷启动 p50 |
|---|---|---|---|---|
| 简单 | 10 | 253.31MB | 254.17MB | 255ms |
| 中等 | 10 | 259.05MB | 260.27MB | 258ms |
| 复杂 | 10 | 259.39MB | 260.48MB | 248ms |
| 满 10 轮会话 | 13 | 210.27MB | 268.23MB | 232ms |

- 12 并发（MAX_CONCURRENCY=12）：总 RSS 峰值 2477.7MB、均值 1931.2MB，9.0 秒完成 12×11 轮；每进程峰值 198–214MB，首波冷启动 1.2–1.6 秒。
- 183 次真实模型运行的 CLI 峰值 RSS：p50 323.25MB / p95 350.97MB / max 369.89MB（样本最大）——全部低于 400MB 规划值与 600MB 熔断线；冷启动 p50 183ms / p95 1419ms。
- 真实模型校准轮实测峰值 288–333MB；按 0.33GB 保守规划：dev 2GB → floor((2−0.3−1)/0.33)=2（与现配置一致，**资源分配不缺**）；8GB → 20（现取 12，约 1.6 倍余量）。600MB 熔断线远未触及。
- `NODE_OPTIONS=--max-old-space-size=64` 实测无变化：内置 CLI 为原生 arm64 可执行文件，堆上限参数不生效。
- 结论：内存/并发不是瓶颈；**瓶颈是语义服务 CPU 的 deep 检索延迟**（全量 969 标签下 30–90 秒/批），这也是评测超时的根因。

### 4. 61 案例 ×3 真模型评测（DeepSeek + 真实语义服务，readonly）

- 总体：183 次运行（61 例 ×3），READY 且方案有效 40.4%；outcome 分布 {"READY": 74, "PARTIAL": 50, "NEEDS_USER_INPUT": 18, "CAPABILITY_GAP": 41}；耗时 p50 36.73s / p95 90.22s / max 91.15s；首份草案 p50 15396ms；硬超时 37 次；强制接受 0 次；重复间 outcome 一致率 52.5%。
- 按金标类型分组的 READY 率与耗时：

| 金标类型 | 运行数 | READY+valid | p50 | p95 | max |
|---|---|---|---|---|---|
| 明细 | 30 | 0.0% | 75.5s | 90.16s | 90.35s |
| 明细·需澄清 | 15 | 0.0% | 29.5s | 59.76s | 82.7s |
| 明细·需组合 | 6 | 0.0% | 90.09s | 90.22s | 90.22s |
| 直达 | 69 | 78.3% | 13.64s | 74.66s | 91.15s |
| 直达·空集 | 3 | 0.0% | 66.23s | 90.85s | 90.85s |
| 需澄清 | 33 | 30.3% | 47.86s | 90.27s | 90.57s |
| 需澄清·空集 | 12 | 58.3% | 45.4s | 90.3s | 90.45s |
| 需组合 | 15 | 20.0% | 78.18s | 90.2s | 90.25s |

- 诊断分布（Top）：{"REQUIREMENT_MISSING": 87, "UNKNOWN_TAG": 64, "TRANSIENT_FAILURE": 43, "BUSINESS_AMBIGUITY": 21, "FORMAT_ERROR": 16, "METADATA_INCOMPLETE": 4, "INVALID_OPERATOR": 3, "LITERAL_DRIFT": 3}
- 不必要提问（金标“直达”却要求澄清）：6 个案例 ['A02', 'B01', 'C02', 'D05', 'G05', 'K07']；deep 检索批次数 237、工具调用 1409、LLM 轮次 p50 8 / p95 16
- 与 LangGraph 基线（11 个典型案例 23/30=76.7%、p50 63.5s、p95 180s，迁移前留档）对比：案例集不同，仅作参考——本套件的 p50 明显更低，READY 率受 deep 检索超时拖累。
- SDK 成本估值合计 26.2977 USD（SDK 估算，非账单）。

### 5. 真实 COUNT/ID 对齐（运行中的 Java + 模拟库 indiv_cust）

- 对评测中 READY 的案例，把方案回放给 Java 权威编译并执行 count/preview（脚本 scripts/java_count_alignment.py）：已处理 29 例，成功计数 28 例，**与金标准人数一致 27 例**（含空集 0 的 B04/G04）。
- 差异/异常：
  - J06：count 0 vs 金标准 65 —— 见缺陷 3（否定条件静默空集）。
  - C01：Java 权威拒绝“日期型标签的日期格式”，触发 2 次 repair 后 FAILED —— 见缺陷 4（Python 未校验 DATE 值形态）。
  - A03/C01 在本轮修复前还叠加了缺陷 1/2 的影响。
- ID 侧：金标准客户 ID 集（`12_主表_命中客户.sql`）不在仓库内，本轮以 count 对齐为主，预览抽样记录 ID 哈希作为运行证据。

### 6. 缺陷发现与处理

1. **XSS 过滤器改写工作台方案请求体**（已修复）：`/taglibrary/agent/**` 未排除 XSS 过滤，方案里的 `>=`/`<` 被转义或截断（`INVALID_OPERATOR`、HTTP 500）。修复：`xss.excludes` 增加 `/taglibrary/agent/**`，补 Java 断言；重建并重启后原始请求直接通过。详见 `docs/design/agent-sdk/xss-filter-finding-20260924.md`。
2. **手工编辑重建台账产生重复 requirement_id**（已修复）：`capture_intent(rebuild=True)` 每个子句生成一条需求，同一需求多子句时产生 `['R1','R1','R2']`，Java 判 `业务要求标识非法` 并触发多余 repair。修复：按 requirement_id 合并 source_spans；新增单测；重启 Agent 后验证通过。
3. **否定条件静默空集**（未修，建议后续）：J06“为空”被表达为 `not_in(C1..C5)` + 固定 `null_policy=EXCLUDE`，SQL 三值逻辑排除 NULL → 0；Guard/Java 均无诊断。详见 `docs/design/agent-sdk/silent-empty-negative-condition-20260924.md`。
4. **Python 未校验 DATE 型值形态**（未修，建议后续）：C01 的 `between 0–30 天` 被 Python 放行，Java 权威拒绝后 repair；端到端最终给出 CAPABILITY_GAP（行为正确，但多一轮往返）。

### 7. 生产观察与上线门禁

本地无法执行生产观察，予以显式标注并给出清单：

- 已达标（本地证据）：封存集质量门禁全绿；Java 131 / Agent 78 / 语义 33 / UI 8+9 全绿；P99 RSS 远低于 600MB；12 并发内存有余量；冷启动 <1s；旧运行库读兼容验证（09-21 旧版写入的行可被新代码与 API 正常解密读取）。
- 待生产执行：连续 2 周观察（READY 率、误 READY、超时率、成本、RSS）；旧数据升级演练（备份加密运行库与密钥、恢复演练）；回滚演练（旧版本代码 + 锁文件）；`sqlite.checkpoints`（现存 100MB 遗留文件）在回滚窗口结束后的清理；水平扩展前解决 SQLite 单进程约束。
- 未达标项（需决策）：deep 检索在 969 标签全量资格下的 30–90 秒延迟使组合/明细类案例大量超时（37 次硬超时），若要在生产达到“中等 p50 ≤ 20s”，需要语义侧容量（GPU 或分片）或降低 deep 预算。

**证据索引**：汇总 `docs/design/agent-sdk/full-verification-summary-20260924.json`；评测报告/指标 `tagpilot-agent/out/sdk-eval-61x3-20260924{,-metrics}.json`；人数对齐 `tagpilot-agent/out/sdk-count-alignment-20260924.json`（修复前对照 `…-preworkaround.json`）；容量 `tagpilot-agent/out/capacity-20260924.json`；封存 A/B `tagpilot-semantic/out/full-20260919/eval/ab-20260924/`；校准 `tagpilot-agent/out/sdk-calibration-20260924.json`；缺陷 `docs/design/agent-sdk/xss-filter-finding-20260924.md`、`…/silent-empty-negative-condition-20260924.md`。

## 后续完整评测入口

以下命令是复现入口，除上文记录的指定案例外本次没有执行全量测试：

```bash
# SDK/Guard 定向冒烟
PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python -m pytest tagpilot-agent/tests/test_sdk_smoke.py -q
# 本地假网关；在 tagpilot-agent/ 下运行
PYTHONPATH=. .venv/bin/python scripts/sdk_gateway_smoke.py
# 真实模型只读评测；先设置 Anthropic / semantic 端点与服务令牌（本轮用 /tmp/run_eval.sh 封装了同样的命令）
PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python tagpilot-agent/scripts/evaluate_workbench.py \
  --runtime claude_sdk --index <发布索引目录> --snapshot <snapshot.jsonl> \
  --cases A01,B02 --repeat 1 --output tagpilot-agent/out/sdk-gold.json
# 报告指标与门禁对照（本轮的 61×3 报告：out/sdk-eval-61x3-20260924.json）
PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python tagpilot-agent/scripts/eval_metrics.py <报告>.json <指标>.json
# Java 权威编译 + 模拟库人数对齐（走运行中的 Java；金标人数来自案例文档）
PYTHONPATH=tagpilot-agent tagpilot-agent/.venv/bin/python tagpilot-agent/scripts/java_count_alignment.py \
  --report tagpilot-agent/out/sdk-eval-61x3-20260924.json --output tagpilot-agent/out/sdk-count-alignment-20260924.json
# 容量探针（真 CLI + 假网关：冷启动、RSS P50/P99、12 并发；在 tagpilot-agent/ 下运行）
PYTHONPATH=. .venv/bin/python scripts/capacity_probe.py
# Java 单金标编译，参数必须指向含 B02 的报告与对应快照
mvn -pl ruoyi-taglibrary -am test -Dtest=TsAgentSdkGoldenSmokeTest \
  -Dsurefire.failIfNoSpecifiedTests=false -Dtagpilot.sdk.smoke=<报告绝对路径> \
  -Dtagpilot.sdk.snapshot=<快照绝对路径>
```

后续需要执行：生产观察与上线门禁（部署后连续两周）；deep 检索延迟治理（决定中等请求 p50 能否达标）；缺陷 3/4 的修复决策；可选：在 deep 真实 query 集上补验 `TAG_RERANK_SKIP_CONFIDENT` 的影响面。新 runner 只支持 `--runtime claude_sdk`；历史 LangGraph 基线应在迁移前独立 checkout 使用原脚本，不能在已删除图实现的工作树中假装双运行时对照。

语义侧可配置 `TAG_RERANK_K`（默认30）、`TAG_RERANK_SKIP_CONFIDENT=true`（默认false）、`TAG_RERANK_MARGIN`（默认0.03）、`TAG_MILVUS_READ_CONSISTENCY=Bounded`（默认Strong）。600 条封存集 A/B 已完成且四组配置质量一致，Bounded 可按需启用；跳过重排开关保留默认关闭。

## 发布与回滚边界

本次按“全量实施”在本地完成旧图删除；方案中“生产稳定两周且评测达标”尚未满足，所以这不是已批准的上线切换。重构代码已在本地提交（`1b3bcc6f` 及后续测试提交），但仍未创建 `pre-langgraph-removal` tag，迁移前可核对的 HEAD 是 `6a7571977d0f97868a2bf6fb23077e43f920fa74`。发布前应保留正式回滚标记、备份加密运行库及密钥，并演练旧记录读取和冷恢复。后续完整验证在本机进行时又产生了三处未提交改动：`application.yml`（XSS 排除 `/taglibrary/agent/**`）、`guards/ledger.py`（台账去重）与相应回归测试——发布时必须一并纳入。本地已按此重启 Java（重建 jar）与 Agent 服务并复验通过。

当前代码的 `TAG_AGENT_RUNTIME=langgraph` 会明确拒绝启动运行，回滚需恢复旧版本代码和锁文件，不能只改环境变量。旧 `.checkpoints` 文件不会自动清理；确认旧版回滚窗口结束后再由运维清理。本次没有执行数据库迁移、Docker 生命周期命令或生产发布，已有 Redis/Milvus 保持不变。

SDK 参考：[Claude Agent SDK Python](https://code.claude.com/docs/en/agent-sdk/python)、[DeepSeek Anthropic API](https://api-docs.deepseek.com/guides/anthropic_api/)。版本与实际配置以本次锁文件及代码为准。
