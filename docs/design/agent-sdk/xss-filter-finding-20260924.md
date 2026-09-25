# XSS 过滤器改写工作台方案请求体（2026-09-24 验证发现）

## 现象

把评测产出的方案（含 `>=`、`>`、`<`、`<=` 算子）通过 `POST /taglibrary/agent/threads/{id}/runs` 提交时：

- 15/19 例被 Java 判为 `INVALID_OPERATOR`（`标签不支持所选比较方式`）；
- 4/19 例直接 HTTP 500：`JsonParseException: Unexpected character (',' 或 ':')`，即请求体被截断成非法 JSON。

## 根因

`ruoyi-admin/src/main/resources/application.yml`：

```yaml
xss:
  enabled: true
  excludes: /system/notice,/taglibrary/semantic/**
  urlPatterns: /system/*,/monitor/*,/tool/*,/databroker/*,/taglibrary/*
```

`/taglibrary/agent/**` 未被排除，进入 `XssHttpServletRequestWrapper` 的 `EscapeUtil.clean`：

- `>` / `<` 被转义为 `&gt;` / `&lt;`（`XssOperatorCleanTest.htmlFilterTruncatesOperatorsWhenGreaterThanFollows` 已记录该行为）；
- 含 `<` 的内容会被“从 `<` 截断到下一个 `>`”，导致 JSON 结构被破坏 → 500。

语义草稿接口当年遇到同一问题，靠 `excludes` 里的 `/taglibrary/semantic/**` 规避；Agent 工作台接口漏掉。

## 影响

- **手工编辑条件**：UI `App.tsx savePlan` → `api.startRun(t, "按编辑后的条件核验圈选方案", plan)`（`agentApi.ts` 原样 JSON fetch），方案里必然带比较算子 → 必现失败（INVALID_OPERATOR 或 500）。
- 任何把方案放进请求体的调用（例如 `/resume` 的 `answer.plan`）同样受影响。
- 只读路径（start 无 plan、count/preview/create-group 只传 plan_hash、GET）不受影响，因此金标 smoke 与 09-23 的 Java 全链路（方案由 Python 返回、不经请求体）都没暴露该问题。

## 证据

- `tagpilot-agent/out/sdk-count-alignment-preworkaround.json`：未规避时 19 例中 15 例 INVALID_OPERATOR、4 例 500。
- 规避验证：同一 A02 方案把 `<`/`>` 写成 JSON 转义（`\u003e`）后重发 → `plan_valid=true`，`count=203`（=金标准）。
- 规避脚本：`tagpilot-agent/scripts/java_count_alignment.py` 的 `request()`。

## 建议修复（未实施，需产品确认）

在 `xss.excludes` 增加 `/taglibrary/agent/**`（与 `/taglibrary/semantic/**` 同理），并补一条端到端回归（真实 HTTP 提交含算子的方案）。
