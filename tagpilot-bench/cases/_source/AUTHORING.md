# 61 案例条件树编写指南（供作者/代理）

目标：把 `sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md` 的 61 个场景，
逐条写成评测侧**条件树**（JSON），使「实算人数 = 文档人数」。人数是自动硬校核，不匹配即错。

## 你需要读的输入

| 文件 | 内容 |
|---|---|
| `cases/_source/scenario_61_parsed.json` | 每条：`main_input` / `caliber`（口径对齐）/ `contrast`（对照）/ `expect`（期望+人数）/ `eval`（**口径陷阱，必须遵守**） |
| `cases/_source/tag_map.tsv` | `field_name<TAB>中文名<TAB>tag_id`（970 行，物理列名与标签 id） |
| 本指南 + `docs/legacy/reference/contracts.py`（Tree/Expression 定义，只读参照） |

> 原文档路径若需重读：`../sql/indiv_cust/2000_cust_generate/客群圈选Agent自然语言测试案例.md`

## 输出

写 `cases/_source/trees/<你的组>.json`，结构：

```json
{
  "A03": {"target": { ...Tree... }, "contrast": { ...Tree... }},
  "A04": {"target": { ...Tree... }, "contrast": null}
}
```
- `target`：命中目标客群的条件树（必填）。
- `contrast`：对照客群（`eval`/`contrast` 提到就写；没有就 `null`）。
- 只写你负责的 case_id；**不要**动别人的文件。

## 条件树 schema

节点三选一：

```jsonc
// 全集
{"kind": "SCOPE_ALL"}

// 逻辑分组（AND/OR），children ≥ 1
{"kind": "GROUP", "logic": "AND", "children": [ ... ]}

// 单条件
{"kind": "PREDICATE",
 "expression": {"kind": "TAG", "tag_id": 721, "field_name": "CUR_POINT_AUM", "unit": "CNY"},
 "operator": ">=",                 // = != > >= < <= in not_in between contains is_null is_not_null
 "values": ["1000000"],            // 一律字符串；in/between 多值；is_null/is_not_null 空数组
 "data_kind": "NUMBER",            // NUMBER | STRING | DATE
 "caliber": {}}
```

表达式 `expression` 还可写派生：`{"kind":"CONST","value":"10000"}`、
`{"kind":"DIV","args":[...]}`、`{"kind":"ADD|SUB|MUL","args":[a,b]}`、
`{"kind":"COUNT_POSITIVE","args":[...]}`（对 args 求「>0 的个数」——用于「产品大类数」）。

### 硬规则（schema 会校验）
- `values` 全是字符串。数值不加千分位、不写单位（`"1000000"`）。
- `in`/`not_in` 的 values 去重；`between` 恰好 2 个端点且升序；比较运算符恰好 1 个值；`is_null`/`is_not_null` 不带值。
- `data_kind`：数值/金额/天数/次数 → `NUMBER`；码值（C1..C5）、机构名、文本 → `STRING`；日期 → `DATE`（ISO `YYYY-MM-DD`）。
- 码值保留字符串（`"03"` ≠ `"3"`）；NULL≠0≠空串。
- 布尔/标志字段：`data_kind:"NUMBER"`，值 `"0"`/`"1"`。

## 编写方法

1. 读该 case 的 `caliber`（这是权威口径）→ 逐条拆成 PREDICATE，按 `logic` 组装。
2. 用 `tag_map.tsv` 找每个概念的 `field_name` 与 `tag_id`。
   - 相近字段很多（如 `CUR_MONTH_APP_LOGIN_DAYS` vs `LAST_30_DAYS_APP_LOGIN_DAYS` vs `CUR_YEAR_APP_LOGIN_DAYS`）——**按 `eval` 里的口径陷阱选**，不要想当然。
3. 派生/占比/类数：用表达式（`DIV`/`COUNT_POSITIVE`）。
4. 对照树照 `contrast` 描述写（通常把 > 变 ≤ 之类，或换成「已持有」）。
5. 写完后跑自检：

```bash
cd tagpilot-bench
../tagpilot-agent/.venv/bin/python tools/build_cases_61.py --check --only A03,A04,B03
```
实算人数 ≠ 文档人数就会 `MISMATCH`，据此修正字段/阈值/口径，直到全 `ok`。
**如果反复对不上**：先怀疑字段选错（换近义字段）、口径错（时间窗口/范围）、或运算符/端点错；
仍对不上就在返回报告里列明该 case 的 want/got 与你的怀疑，不要硬凑。

## 常见概念 → 字段（摘，务必自行确认）

| 概念 | 字段 |
|---|---|
| 当前时点 AUM | `CUR_POINT_AUM`（≠ 本行 AUM `CUR_POINT_AUM_OUR_BANK`） |
| 当前存款余额 | `CUR_DEPOSIT_BALANCE` |
| 当前持有理财标志 | `CUR_HOLDING_WMP_FLAG`（1/0）；历史 `HIST_HOLDING_WMP_FLAG` |
| 当前理财风评等级 | `CUR_WMP_RISK_ASSESSMENT_LEVEL`（C1..C5） |
| 当前基金风评等级 | `CUR_FUND_RISK_ASSESSMENT_LEVEL` |
| 近30天异名跨行转入金额 | `LAST_30_DAYS_DIFF_NAME_INTERBANK_TRANSFER_IN_AMT` |
| 近30天 APP 登录天数 | `LAST_30_DAYS_APP_LOGIN_DAYS` |
| 当前手机银行开通标志 | `CUR_MOBILE_BANKING_OPENED_FLAG` |
| 本月信用卡消费金额 | `CUR_MONTH_CC_CONSUMPTION_AMT` |
| 本月代发金额 | `CUR_MONTH_PAYROLL_AMT`；上月 `LAST_MONTH_PAYROLL_AMT` |

（完整列表用 `grep -i '<关键词>' cases/_source/tag_map.tsv` 查。）
