# P3 语义改进与 100 个客户经理 Demo 案例

Status: Draft — 用户已授权端到端实施；本文为 Agent 复核，未经本人/银行签署。

目的：只做 P3，不扩充 P2 至 P4。修复有来源的语义数据和必要关联/受控变更工程，保留原配置做 A/B；再以 100 个自然语言案例检测终态、条件与实际客群。

来源：方案第四章、P2 REPORT.md 与 p2-diagnosis-v3；案例先按独立来源和固定 fixture 构造标准树，不采用被测 Agent 输出作为真值。

环境：本机 Java 8080、语义 8091、正式 Claude SDK Agent 8092；2000 名 SIM20260918 模拟客户；固定 reference_date=2026-09-18 / Asia/Shanghai。P0、P2 和旧索引保留。先用少量失败题验证，再以并发 2 回放固定 100 题；失败题另目录复跑，不覆盖首轮。

输入：data/p3-demo-100-v3/cases.jsonl，7 场景分别 15/15/14/14/14/14/14；标准、口语、省略、模糊澄清、指代追加。40 个案例包含预设后续用户消息，共 140 条用户消息。全部属于 DEV，迭代后成绩是 Demo 开发集成绩。v3 仅纠正“账上还有”的首轮范围澄清，100 条初始原话及全部最终条件树、ID oracle 均与 v2 相同；记录见 authoring-correction.json。

边界：营销复盘限已发布载体活动参与字段；渠道迁移限已开通手机银行及 APP 低活跃；沉睡激活明确为 APP 低活跃；基金配置限当前持有、基金风评和资产条件。不把未发布明细能力、严格 90 天无活动或活动因果冒充已支持。累计入金仅为有来源支持的 Demo 约定。

通过条件：全部终态与预设期望相符，完整条件树、阈值、码值、时间和逻辑正确；多轮首轮确实询问必要槽位，补充后保留要求；Java 权威编译、COUNT 和完整模拟客户 ID 集与独立 oracle 一致。0 人是有效结果，禁止放宽条件。

裁判：tagpilot_eval.judge/oracle 独立比较；真实 Java /taglibrary/agent/plan/compile 与 /objectgroup/group/run；完整 ID 集只由 Java 生成的固定形状 SELECT COUNT SQL 换投影后在本机只读事务执行，不使用模型 SQL。

无效运行：本地服务、认证、裁判或外部模型认证故障单列 RUN_INVALID；模型在有效环境耗尽时间/预算计失败。不得将 READY、valid 或预览前 100 人当成完整成功。

外部模型：当前 DeepSeek api.deepseek.com / deepseek-flash；用户已明确“授权外部模型”。仅发送合成原话与可见候选语义证据。客户记录、完整 ID 集、凭据留在本机。

执行路径：tagpilot_eval.p3_run（实跑及事件）→ run_java（Java 执行对齐）。所有轮次保留版本、耗时、tokens、成本估计、原始事件和失败；无本轮稳定性、并发容量或生产接受结论。
