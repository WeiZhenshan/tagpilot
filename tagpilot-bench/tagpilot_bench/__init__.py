"""TagPilot 评测体系（重建）。

分层测量 + 差分决策，取代一次性的 tagpilot-eval。
- L1 语义层：原子条件检索（确定性、免费）
- L2 Agent 层：条件计划 / 澄清 / 缺口（付费、重跑方差大）
- L3 执行层：Java 权威编译 + COUNT + 完整 ID 集（确定性、权威）

与被测 Agent 的耦合被限制在 `adapter` 一个模块内（Agent 协议 → 评测侧标准树），
其余（schema / oracle / grade / report）不引用 Agent 任何词表。
"""

__version__ = '0.1.0'
