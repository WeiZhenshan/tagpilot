#!/usr/bin/env bash
# 元 Skill 真实模型验证入口：同题跑「带技能」与「无技能」两组，输出到 tagpilot-agent/out/skill-evals/。
# 需要仓库根目录 .tag-llm-config（TAG_LLM_BASE_URL/TAG_LLM_MODEL/TAG_LLM_API_KEY），不读取宿主 ANTHROPIC_* 变量。
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

python_bin="$ROOT_DIR/tagpilot-agent/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  echo '请先执行 uv sync --project tagpilot-agent --extra dev' >&2
  exit 1
fi

exec "$python_bin" tagpilot-agent/scripts/skill_evals.py "$@"
