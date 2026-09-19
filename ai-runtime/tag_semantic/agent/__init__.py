"""受控标签智能体：模型只在资格内候选中建议，确定性代码负责校验与执行边界。"""

from tag_semantic.agent.graph import build_agent

__all__ = ["build_agent"]
