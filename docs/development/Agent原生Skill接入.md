# Agent 原生 Skill 登记与调用

2026-09-30。本轮完成技能管理页面、持久化与现有 Agent 原生 Skill 调度接入，不预置基础事实、诊断分析、行动决策或图表技能。

> 2026-09-30 后续：元 Skill 底座（分析三件套 + 图表三件套、insight-result 结果契约与工作台渲染）已在该接入层上落地，见 [元Skill底座实施记录](元Skill底座实施记录.md)。

## 登记协议

技能不再绑定标签库。全局表 `ts_agent_skill` 保存可编辑草稿与独立的已发布快照，`row_version` 防止并发编辑覆盖。修改草稿不影响发布内容；发布修改须更换版本号。沿用 `taglibrary:insight:list/edit/publish/run` 权限。

技能文件采用 Claude `SKILL.md`：`name`、`description`、`argument-hint`、`user-invocable`、`disable-model-invocation`、`allowed-tools` frontmatter 与 Markdown 正文。展示名称、登记分类、发布版本属于平台元数据。支持登记 `references/`、`scripts/`、`assets/` 下的文本文件。

本轮仅开放 `Read` 与 `Skill`。脚本可保存作参考资料，但不能执行；不支持二进制上传、Shell、动态命令预处理、任意 MCP 配置、独立子 Agent 或其他 frontmatter 选项。登记内容不扩大宿主权限。

## 页面与接口

若依洞察技能页面支持列表、搜索/分类/状态筛选、创建、编辑、草稿/发布版本查看、资源编辑、标准文件预览/下载、发布检查与下线。

- `GET /taglibrary/agent/skills`：管理列表与草稿/已发布内容。
- `POST /taglibrary/agent/skills`：保存草稿，携带 `row_version`。
- `POST /taglibrary/agent/skills/{name}/publish`：核验已保存草稿并发布。
- `POST /taglibrary/agent/skills/{name}/retire`：下线。
- `GET /taglibrary/agent/skills/available`：发布技能元信息，不向运行菜单发送正文与资源。

工作台左侧保留会话和标签两个页签。输入 `/` 时在输入框上方搜索已发布、允许手动调用的技能；支持方向键、Enter、Esc 和鼠标选择。添加技能后可补充分析目标或直接发送，也可输入完整的 `/技能名称 分析目标`。技能管理入口返回若依原页面。

## 运行边界

前端提交 `skill_name`、`base_revision`、`plan_hash`，不提交可信人数或技能指令。Java 核验会话归属、技能运行权限、当前方案、发布快照、条件确认状态，再注入当前条件、方案版本、客群名称、已有客群ID与仍有效的人数。未统计或过期人数不作为事实传入。无需创建实体客群，但必须先核验圈选条件。

现有 `/agent/v2/runs` 和 `RunManager` 承载 `profile=skill`，共享准入、用户并发限制、队列、取消、超时、内存预算和加密运行库。ClaudeRunner 在每轮临时目录物化 `.claude/skills/<name>/SKILL.md`，开启 `setting_sources=['project']`，以 `/<name>` 调用原生 Skill。模型可按用途继续调用允许自动调用的已发布技能，包括将来登记的图表技能。每轮结束清理临时文件；不加载用户全局技能。

PreToolUse 和权限回调共同核验资源读取范围与发布技能名单，即使 frontmatter 预授权也不能绕过宿主范围。不存在外部数据库/客户明细访问工具。当前事实证据限于服务端客群上下文；没有指标数据时必须说明缺失。图表技能本身与真实指标取数/图表渲染扩展不属于本轮预置内容。

技能输出追加到原会话，不改变圈选条件、人数、方案版本、实体客群或创建确认。失败/中断须重新发送，重新核验上下文与技能版本，不使用旧版本盲目续跑。

## 原独立工程迁移

不再安装或维护 `tagpilot-insight` 工程及其 pyproject/lock。原计算库移到 `tagpilot-agent/tagpilot_insight/`，仅为旧报告接口保留兼容；原测试移到 `tagpilot-agent/tests/legacy_insight/`，原配置/schema/验证资料移到 `tagpilot-agent/legacy-insight/`。新技能登记/发布/原生运行不读取旧 YAML 目录，不将旧三技能自动登记到新表。`bin/verify-insight.sh` 改用 Agent 环境。

## 启用与验证

现有数据库先执行 `sql/migration/V20260930_01__agent_skill_registry.sql`（通过正常迁移入口），再部署/重启 Java 和 Agent，更新两套前端。本轮不修改真实技能数据，不自动部署服务或执行业务数据库迁移。

本地验证使用 mocked Java 单元测试、真实 Claude SDK/CLI + 本地假 Messages 网关，以及浏览器合成接口夹具，覆盖 Skill 加载、关联 Skill 调用、资源越界、未发布名单、上下文防伪、有效/过期人数、草稿发布隔离及桌面/窄屏操作。不构成真实模型效果、真实客群取数或生产验收。

官方结构参考：[Claude Code Skills](https://code.claude.com/docs/en/skills)、[Agent SDK Skills](https://platform.claude.com/docs/en/agent-sdk/skills)。本地 SDK 保持锁定 0.1.50，以现有 SDK/CLI 的集成测试为准，不依赖新版文档中新增的 SDK 参数。
