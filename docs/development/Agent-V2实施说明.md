# Agent V2 与圈选工作台实施说明

2026-09-21。依据用户提供的 `Agent V2.md`、工作台评审与当前代码实现。范围覆盖 `tagpilot-agent`、`tagpilot-assistant`、Java 圈选桥接、发布证据读取以及若依嵌入/规则编辑衔接。

## 1. 完成的业务流程

1. 用户选择标签库、新建或打开自己的圈选会话。
2. Agent 将需求拆为有稳定 `clause_id` 和原文 `source_span` 的 AND/OR 条件树，每个条件先取得真实候选，再按需调用发布态详情、术语和码值证据工具。
3. 程序验证资格、发布版本、操作符、真实码值、单位倍率、结构化时间口径及完整性。缺失项集中形成 Ask；用户可以回答，也可以直接编辑条件后继续。
4. 方案保存为新 revision，支持只读查看历史、比较条件变化，以及从旧版生成新版本。修改后旧统计/创建确认失效。
5. 人数统计经 Java 编译和原对象群服务执行，`groupId=null`，不写回已有客群。样例只进入本次弹窗，不进入 Agent 或持久会话。
6. 用户明确确认名称和当前方案后创建客群；同一会话/版本只创建一次，网络结果不确定时查询执行记录。已创建客群可以跳转原编辑器。

白灰工作台继承若依主题；桌面三栏、窄屏历史/对话/方案三页；呈现真实任务计划、检索行动与口径证据，不生成伪造的模型思考轨迹。

## 2. 状态与持久化归属

| 数据 | 权威位置 | 说明 |
|---|---|---|
| 用户身份与操作权限 | Java / 若依 JWT | 浏览器不传 owner；每次读取/执行校验登录用户和接口权限 |
| 会话消息、方案历史、已同步事件、运行引用、统计 | MySQL `ts_agent_thread.payload` | 复用 DataBroker AES-GCM 加密；title/归属/更新时间为检索用明文字段 |
| 建群幂等记录 | MySQL `ts_agent_execution` | `(thread_id, revision)` 唯一；业务写入与执行记录同一事务 |
| 运行状态、事件、请求及结果 | Python SQLite `TAG_AGENT_DB` | 内容 Fernet 加密，事件有递增游标，运行 ID 幂等 |
| LangGraph 状态及 interrupt | 同路径 `.checkpoints` | 加密序列化；检查点不保存客户端或模型凭据 |
| 证据与资格 | 固定发布快照 + Java 当前资格 | 绑定 `library_id/build_id/snapshot_id/artifact_hash` |

运行状态：IDLE → RUNNING → WAITING/COMPLETED/FAILED；WAITING/FAILED/INTERRUPTED 可以恢复，活动运行可以取消。进程启动将遗留 RUNNING 标记 INTERRUPTED；取消不能被迟到的成功结果覆盖。部分方案可保留，但没有通过校验不得执行。

Java 到 Python 按事件游标同步；浏览器使用带 JWT 的有界 SSE 状态帧，约一秒重连，失败退避。当前实现是运行事件/状态更新，不是模型 token 逐字流式输出；重连和刷新不重发用户命令。

当前持久化实现面向单个 Agent 服务进程，通过文件锁拒绝多进程共用 SQLite；进程内有4个执行工作线程。多实例共享队列/分布式领取不在当前单机实现中。

## 3. 接口契约

Java 前缀 `/taglibrary/agent`，返回若依 `AjaxResult`，错误使用现有全局异常格式。共同要求 `taglibrary:semantic:list` 和会话归属；库访问沿用现有标签库权限与对象群库可见性规则，不把 `eligible_tag_ids` 当作用户身份。

| 方法与路径 | 请求/结果 |
|---|---|
| GET `/threads?archived=false&page=1` | 只列当前用户，每页30条 |
| POST `/threads` | `library_id`；一个会话固定一个标签库 |
| GET `/threads/{id}` | 消息、版本、当前方案、Ask、过程、能力与状态 |
| PATCH `/threads/{id}` | `title` 或 `archived` |
| POST `/threads/{id}/runs` | `client_request_id`、`base_revision`、`message`、可选编辑后 `plan` |
| POST `/threads/{id}/resume` | `base_revision`、`interrupt_id`、`answer`（文字或 `{plan}`） |
| POST `/threads/{id}/cancel` | 停止；已有局部方案保留为不可执行新版本 |
| GET `/threads/{id}/events` | `text/event-stream` 的持久状态帧 |
| POST `/threads/{id}/count` | `base_revision`、`plan_hash`；额外检查 `objectgroup:group:run` |
| POST `/threads/{id}/preview` | 同上；额外检查 `objectgroup:group:preview` |
| POST `/threads/{id}/create-group` | 同上加 `name`；额外检查 `objectgroup:group:add` |
| GET `/threads/{id}/execution` | 查询当前版本是否已创建及 group_id |

Python 内部 `/agent/v2/runs` 的创建、读取、恢复、取消仅接受服务令牌。Java 注入 owner 与资格。语义服务新增 `/evidence`，只读固定构建内、资格集合内的标签/码值/术语，读取期间持有构建 lease。

## 4. 表达与执行边界

- 外部圈选树 `schema_version=2`；编译成 Java `RulePayload.schemaVersion=3`。旧 V2 规则仍走原解释路径，避免历史客群比较含义变化。
- 最多30个叶子、8层嵌套；AND/OR 编译成连接符和成对括号。绑定阶段禁止丢掉未解决条件。
- 支持发布标签允许的精确比较、集合、闭区间、文本包含/匹配、空值操作；类型与操作符不兼容时拒绝执行。任意范围的开区间可以用严格比较与 AND 表达。
- 金额使用 Decimal/BigDecimal，输入 `value_unit/value_scale` 与标签目录单位核对和换算。重复校验不能再次放大数值。
- 时间条件用 `expected_caliber` 与发布口径逐字段比较，上月不能静默改成近30天。
- 否定默认排除 SQL NULL；选项的发布未知桶默认也排除，用户明确要求时可选择包含未知码值。前端显示该语义。
- 等级、分档、层级只能使用发布的码值与证据；没有完整可验证映射时应澄清或检索连续数值标签，不能根据名称自行猜出分档阈值。当前未提供任意层级/范围表达的通用自动展开器。
- 每轮最多12次模型工具选择，每条件最多3次不同表述检索，最多2次校验/修复；重复工具结果复用，连续无新证据停止并澄清。校验阶段会独立重新读取绑定标签证据。
- COUNT 为0不自动放宽条件。数据源没有提供业务数据时点时显示“数据源未提供”，执行时间与数据时点分开。
- 用户级客户行范围继续由现有对象群与数据集执行边界承接；没有新增银行机构/客户经理级行权限政策，不能据此宣称新增了该类权限能力。

## 5. 安装、迁移与运行

新增迁移：`sql/migration/V20260921_03__agent_workbench_v2.sql`。只创建两张新表，不修改已发布迁移，不执行全量初始化。现有环境按 `bin/db-migrate.sh` 正常升级；首次部署也需应用新迁移。

Python：`uv sync --project tagpilot-agent --extra dev --frozen`。保留 `TAG_AGENT_DB` 及 `.checkpoints`，保留 `TAG_AGENT_STORAGE_KEY`（缺省沿用服务令牌）和 Java DataBroker 密钥。密钥变化不是数据迁移，直接更换会导致已有加密历史不可读。运行状态目录已加入 `.gitignore`。

前端：`npm --prefix tagpilot-assistant ci`，构建后使用项目已有 `/agent-ui/` 同域发布路径；无需新建 Cloud 服务。继续复用已启动的 Redis、Milvus。

启动脚本默认将运行与检查点保存到 `<项目根>/tagpilot-agent/out/workbench.sqlite` 及 `.checkpoints`，与本次验证路径一致。

本次本地联调已经执行该新迁移。未改生产数据、未执行发布、未创建真实业务客群、未提交或推送 Git。

## 6. 验证记录

### 真实本地联调

- 通过验证码和若依演示账号登录，创建本地测试会话并读回，验证真实 MySQL 存储。
- 真实模型 + 现有发布索引：`近30天有异名跨行转入的客户` → 标签709（近30天异名跨行转入标志），值 `1`，方案通过 Java 校验；只读 COUNT 得到1422人。
- 继续要求保留原条件并新增“近30天异名跨行转入金额大于50万元”：新方案保留原条件，新增标签1291，使用严格 `>` 和500000元，生成独立版本。
- 实际浏览器用登录 cookie 打开上述持久会话，无前端运行时异常；最终重启 Java/语义/Agent 后再次读回 COMPLETED、revision 3、3个版本和6条消息，两个 Python 健康检查均200。客户人数仅是本地当前数据结果，不能视为业务验收。

### 自动验证

最终数量与结果见开发计划末尾的验收记录。测试分层：Java 校验/授权/幂等，Python 图恢复/加密/工具契约，React 条件差异，Playwright 合成状态交互；合成测试不证明真实模型准确率。

真实建群写入没有在业务库中试做；确认流程、执行记录和重复请求有单元/浏览器测试。没有执行 Agent V2 文档建议的独立 A/B/C 大样本对比评测，因此不报告整体准确率提升，也不替代银行业务审核。

## 7. 参考与入口

- [开发计划](Agent-V2开发计划.md)
- [界面方向](Agent-V2界面方向.md)与[实现视觉规则](../../tagpilot-assistant/DESIGN.md)
- [assistant-ui ExternalStoreRuntime](https://www.assistant-ui.com/docs/runtimes/custom/external-store)：自有消息状态、持久化和回调适配。
- [assistant-ui Reasoning](https://www.assistant-ui.com/elements/reasoning)：仅在有真实 reasoning 内容时展示；本实现使用业务证据事件与可恢复状态。
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 与 [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。
