# 日期校验修复验证记录

日期：2026-09-28。范围：修复省略年份的日期校验、补充工作台日期上下文；不扩量，不调整运行预算。

## 原因与修复

原案例运行 `13bd6240-f116-45e6-b800-09b6e9b16519` 在 90.075 秒超时。工作台缺少 reference_date，校验器无法补全“9月19号”，继而把 9 和 19 当作普通数字并错误报告 LITERAL_DRIFT。模型最初已经生成正确的三项条件，后续反复修复该误诊断。

日期校验现在优先沿用区间另一端明确写出的年份，并按区间顺序处理跨年。日期即使校验失败也不会回落为金额等普通数字；错误或遗漏端点仍会被拒绝。完全省略年份时使用请求基准日；没有基准日则返回明确诊断，不采用模型答案的年份。

Java 为新运行注入上海时区的服务端日期，并随请求持久化，恢复沿用原上下文。未改变模型提示、标签快照或预算；README 轮数修正为代码已有的 16。

## 验证

- Python 针对性检查：50 PASS（日期、Guard、SDK 冒烟）；覆盖省略年份、空基准日、显式年份优先、跨年、非法日期、错误或遗漏端点、金额不被日期吞掉。
- Java 工作台单元测试：18 PASS；包含服务端日期传递及不接受浏览器伪造基准日。
- 构建：mvn clean package -DskipTests 成功；重载本机 Java 与 Agent，核对打包类与编译类一致。
- 第一轮实际工作台验证：仅 Python 修复、reference_date 仍为空，11.690 秒 READY，COUNT=22。记录见 workbench-python-only.json。
- 第二轮实际工作台验证：完整修复，14.968 秒 READY，6 模型轮、5 次工具调用、0 次提交拒绝，COUNT=22。记录见 workbench.json。
- 第二轮请求上下文：reference_date=2026-09-28，timezone=Asia/Shanghai。
- Java 编译 SQL 与 CAL-8017 原独立验证 SQL 完全一致，实际 COUNT 与原 Oracle 的 22 人一致；样例预览成功。未创建客群。

实际输入：

> 盯一下下一笔定期，9月19号到2026-09-30到期的，两头都含，金额不低于20万，而且现在没有理财。

编译 SQL：

```sql
select count(*) from `L_INDVCST_LABEL` where ((`NEXT_TIME_DEPOSIT_LATEST_MAT_DATE` >= '2026-09-19' and `NEXT_TIME_DEPOSIT_LATEST_MAT_DATE` <= '2026-09-30') and (`NEXT_TIME_DEPOSIT_LATEST_MATURITY_AMT` >= 200000) and (`CUR_HOLDING_WMP_FLAG` = '0'))
```

最终验证会话：`ea308344-442c-4199-afca-a95f13a0309e`；运行：`82780d98-c876-48b5-8a4f-1d76f496f861`。

本轮未重跑全部 100 个案例，结论范围为针对性检查和该原案例的真实工作台验证。原有失败记录保留。本机服务已加载修复；未提交或推送 Git。
