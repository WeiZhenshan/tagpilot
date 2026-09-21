#!/usr/bin/env bash
# Agent 编排层以前台方式托管；检索走 tagpilot-semantic，不加载索引或向量模型。
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT_DIR=$(pwd)

: "${TAG_RUNTIME_TOKEN:?请通过环境变量提供服务间认证令牌，Java 与 Python 必须一致}"

# LLM 选择器：外部 TAG_LLM_* 优先；否则读取本机 .tag-llm-config（不入 Git）
if [[ -z "${TAG_LLM_BASE_URL:-}" || -z "${TAG_LLM_MODEL:-}" ]]; then
  llm_config="$ROOT_DIR/.tag-llm-config"
  if [[ -f "$llm_config" ]]; then
    # shellcheck disable=SC1090
    source "$llm_config"
    export TAG_LLM_BASE_URL TAG_LLM_MODEL TAG_LLM_API_KEY
  fi
fi

agent_python="${TAG_AGENT_PYTHON:-tagpilot-agent/.venv/bin/python}"
if [[ ! -x "$agent_python" ]]; then
  echo '请先执行 uv sync --project tagpilot-agent --extra dev' >&2
  exit 1
fi
export TAG_SEMANTIC_URL="${TAG_SEMANTIC_URL:-http://127.0.0.1:${TAG_RUNTIME_PORT:-8091}}"
export TAG_AGENT_DB="${TAG_AGENT_DB:-${ROOT_DIR}/tagpilot-agent/out/workbench.sqlite}"
export PYTHONPATH="${ROOT_DIR}/tagpilot-agent${PYTHONPATH:+:$PYTHONPATH}"
exec "$agent_python" -m uvicorn tagpilot_agent.server:app --host "${TAG_AGENT_HOST:-127.0.0.1}" --port "${TAG_AGENT_PORT:-8092}"
