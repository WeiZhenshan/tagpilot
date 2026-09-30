# 洞察元 Skill 源码目录

本目录是 TagPilot「分析元 Skill + 图表元 Skill」的**内容源码**。技能内容通过登记台（`/taglibrary/insight-skill`）保存草稿、发布后由工作台原生加载运行；本目录不直接参与运行，只作为版本管理与再制种的来源。

## 目录结构

```
skills/
├── analysis/
│   ├── fact-analysis/          基础事实    （category=fact）
│   ├── diagnostic-analysis/    诊断分析    （category=diagnosis）
│   └── action-decision/        行动决策    （category=decision）
├── charts/
│   ├── chart-atomic/           图表原子层  （category=chart，仅模型可调用）
│   ├── chart-intent/           图表意图层  （category=chart，仅模型可调用）
│   └── chart-compose/          图表组合层  （category=chart，仅模型可调用）
├── shared/                     公共协议（生成种子时按文件名分发进分析技能的 references/）
│   └── result-contract.md      结果块契约：字段、示例与 JSON 纪律
└── README.md
```

每个技能目录含一个 `SKILL.md`（frontmatter + 指令正文）与 `references/` 下的参考资料。运行时会把这些文件物化到 Claude 会话的 `.claude/skills/<name>/` 下；模型按需 Read 参考资料。技能包在运行时彼此独立，不能跨包读文件，因此 `shared/` 下的文件由生成器复制进每个**分析技能**包的 `references/`（图表技能不产出结果块，不分发）。

## SKILL.md frontmatter

平台元数据（不入运行时 frontmatter，仅登记用）：

| 字段 | 说明 |
| --- | --- |
| `display-name` | 登记台展示名 |
| `category` | `fact` / `diagnosis` / `decision` / `chart` / `general` |
| `version` | 三段数字，发布内容变化必须升版本 |

运行时字段（发布后原样写入运行态 SKILL.md）：

| 字段 | 说明 |
| --- | --- |
| `name` | 与目录名一致，小写连字符 |
| `description` | 触发与用途说明（≤1024，不含 XML 标签） |
| `argument-hint` | 工作台输入提示 |
| `user-invocable` | 是否出现在工作台 `/` 列表 |
| `disable-model-invocation` | 是否禁止模型链式调用 |
| `allowed-tools` | 仅允许 `Read` 和 `Skill` |

约束（由 `TsAgentSkillService.validate` 与 `skills/packages.py` 双重校验）：指令 ≤60000 字；资源仅 `references/`、`scripts/`、`assets/` 下的文本文件，单文件 ≤60000 字、总计 ≤200000 字、≤30 项；不支持命令预处理（`` !`cmd` ``）与脚本执行。

## 输出契约

三个分析技能以一条约定收尾：正文之后以 ```insight-result 围栏块输出一个 JSON 对象（status / reasons / facts / cards / charts / followups）。Python 侧抽取该块，Java 侧校验并组装成工作台「洞察」面板可渲染的报告；块缺失或校验失败时降级为纯文本消息。图表 spec 的字段约束见 `charts/chart-atomic/references/spec-guard.md`。

## 修改与再制种

1. 直接编辑本目录下的 SKILL.md 与 references（保持 frontmatter 值使用 JSON 字符串写法，便于脚本解析）。
2. 生成种子 SQL：

```bash
python3 bin/build-agent-skill-seed.py
```

3. 输出写入 `sql/seed/agent-meta-skills.sql`，按需手工执行（幂等，重复执行会把技能刷新为文件当前内容）。导入必须带 utf8mb4，否则中文会被双重编码：

```bash
mysql --default-character-set=utf8mb4 -u<user> -p <库名> < sql/seed/agent-meta-skills.sql
```

4. 或者把改动粘贴进登记台保存草稿、发布新版本（生产环境推荐走登记台治理流程）。

本地模型效果验证见 `bin/verify-insight-skills.sh`（可选，需要本机模型配置）。
