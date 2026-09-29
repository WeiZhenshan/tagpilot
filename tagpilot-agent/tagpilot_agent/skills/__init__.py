"""洞察 Skill 体系：Manifest 契约、注册表、运行时、内置业务 Skill。

对齐《标签智能体两大核心亮点实现计划与整体架构方案》第 4 章：
模型做语义判断，代码做业务约束和数字计算；Skill 是确定性计算产品，不依赖 LLM 即可运行。
"""

from tagpilot_agent.skills.manifest import SkillManifest, validate_manifest
from tagpilot_agent.skills.registry import SkillRegistry, SkillRegistryError
from tagpilot_agent.skills.runtime import SkillRuntime

__all__ = ["SkillManifest", "validate_manifest", "SkillRegistry", "SkillRegistryError", "SkillRuntime"]
