# 否定条件静默空集：J06“理财风评待补充”（2026-09-24 验证发现）

## 现象

金标案例 J06（口径对齐：“当前理财风评等级为空”，金标准 65，对照 1935）在 61×3 评测中出现 READY + 可编译的方案，但 Java 实算 `COUNT = 0`，与金标准 65 不符，且全链路无任何诊断。

## 复现

Agent 产出的条件（`tagpilot-agent/out/sdk-eval-61x3-20260924.json`，J06）：

```json
{"clause_id": "c1", "kind": "TAG_PREDICATE", "tag_id": 1466, "name": "当前理财风评等级",
 "semantic_type": "ENUM_ORDINAL", "operator": "not_in",
 "values": ["C1","C2","C3","C4","C5"], "unknown_policy": "INCLUDE", "status": "BOUND"}
```

- 标签 1466 的已发布证据：`allowed_operators = ['=', 'in', 'not_in']`，码值只有 C1–C5，**没有 is_unknown_bucket 码值，也不支持 is_null**（`sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md` J06 期望 IS NULL）。
- Python Guard：`null_policy` 由校验器固定为 `EXCLUDE`（模型无法声明包含空值），未知码值集合为空 → 条件被判定为合法 BOUND。
- Java 编译：`not_in ('C1'..'C5')` → SQL `col NOT IN (...)`；SQL 三值逻辑下 NULL 不满足 NOT IN → 全部“待补充”客户被静默排除 → 0。

## 影响

- 任何“为空 / 待补充 / 未持有”类需求，如果模型用 `not_in`/`!=` 表达、而该标签既无未知码值也不支持 `is_null`，就会得到静默空集或严重偏低的计数，且 UI 显示“零阻断、可执行”。
- 在全量 61×3 评测中扫描到该形态的 READY 子句 1 例（J06，出现在 2 次重复中）。

## 建议（未实施，需产品确认）

1. Guard：对 `not_in`/`!=` 条件，若标签既无未知码值又不支持空值算子，产出 `METADATA_INCOMPLETE`/`CAPABILITY_UNAVAILABLE` 诊断，促使模型提交 CAPABILITY_GAP 或向用户提问，而不是静默通过。
2. 元数据：为存在“空值即业务含义”的标签发布未知码值桶或开放 `is_null`（J06 这类自然语言直指空值的场景应可表达）。
3. 两处任选其一即可消除静默偏答；建议同时做，Guard 兜底、元数据治本。
