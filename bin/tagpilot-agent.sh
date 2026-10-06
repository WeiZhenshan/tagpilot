#!/usr/bin/env bash
# Agent 编排层以前台方式托管；检索走 tagpilot-semantic，不加载索引或向量模型。
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT_DIR=$(pwd)

: "${TAG_RUNTIME_TOKEN:?请通过环境变量提供服务间认证令牌，Java 与 Python 必须一致}"

# 模型配置：本机 .tag-llm-config（不入 Git）始终参与，ANTHROPIC_BASE_URL / ANTHROPIC_CUSTOM_HEADERS 由它导出；
# 外部显式提供的 TAG_LLM_* 仍是权威配置，只覆盖配置文件中的同名值。
llm_config="$ROOT_DIR/.tag-llm-config"
if [[ -f "$llm_config" ]]; then
  env_llm_base="${TAG_LLM_BASE_URL:-}"
  env_llm_model="${TAG_LLM_MODEL:-}"
  env_llm_key="${TAG_LLM_API_KEY:-}"
  env_anthropic_base="${ANTHROPIC_BASE_URL:-}"
  env_custom_headers="${ANTHROPIC_CUSTOM_HEADERS:-}"
  # shellcheck disable=SC1090
  source "$llm_config"
  if [[ -n "$env_llm_base" ]]; then
    if [[ "$env_llm_base" != "${TAG_LLM_BASE_URL:-}" ]]; then
      # 外部端点与配置文件不一致：配置文件里的 Anthropic 协议映射只适用于它自己的端点，保持宿主显式提供的值。
      ANTHROPIC_BASE_URL="$env_anthropic_base"
      ANTHROPIC_CUSTOM_HEADERS="$env_custom_headers"
    fi
    TAG_LLM_BASE_URL="$env_llm_base"
  fi
  if [[ -n "$env_llm_model" ]]; then TAG_LLM_MODEL="$env_llm_model"; fi
  if [[ -n "$env_llm_key" ]]; then TAG_LLM_API_KEY="$env_llm_key"; fi
  unset env_llm_base env_llm_model env_llm_key env_anthropic_base env_custom_headers
fi
export TAG_LLM_BASE_URL TAG_LLM_MODEL TAG_LLM_API_KEY

# 模型配置：TAG_LLM_* 是权威配置，DeepSeek 官方地址必须覆盖宿主环境可能残留的 ANTHROPIC_*（如桌面会话的中转地址），
# 否则模型请求会带着错误的端点返回 401。第三方网关不走映射，仍须显式提供 Anthropic 协议地址（ANTHROPIC_BASE_URL）。
if [[ -n "${TAG_LLM_BASE_URL:-}" && "${TAG_LLM_BASE_URL}" == "https://api.deepseek.com" ]]; then
  export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
fi

# OpenCode Anthropic 网关要求 x-opencode-session，缺失即 400 MissingSessionID；配置文件缺失时也强制注入。
# 会话标识可用 TAG_OPENCODE_SESSION 覆盖，非密钥。
if [[ "${ANTHROPIC_BASE_URL:-}" == *opencode.ai* && "${ANTHROPIC_CUSTOM_HEADERS:-}" != *x-opencode-session* ]]; then
  opencode_session="${TAG_OPENCODE_SESSION:-tagpilot-insight}"
  if [[ -n "${ANTHROPIC_CUSTOM_HEADERS:-}" ]]; then
    ANTHROPIC_CUSTOM_HEADERS="${ANTHROPIC_CUSTOM_HEADERS}"$'\n'"x-opencode-session: ${opencode_session}"
  else
    ANTHROPIC_CUSTOM_HEADERS="x-opencode-session: ${opencode_session}"
  fi
  unset opencode_session
fi
if [[ -n "${ANTHROPIC_BASE_URL:-}" ]]; then export ANTHROPIC_BASE_URL; fi
if [[ -n "${ANTHROPIC_CUSTOM_HEADERS:-}" ]]; then export ANTHROPIC_CUSTOM_HEADERS; fi
export ANTHROPIC_MODEL="${TAG_LLM_MODEL:-${ANTHROPIC_MODEL:-deepseek-flash}}"
export ANTHROPIC_API_KEY="${TAG_LLM_API_KEY:-${ANTHROPIC_API_KEY:-}}"
export TAG_AGENT_RUNTIME="${TAG_AGENT_RUNTIME:-claude_sdk}"
export TAG_AGENT_MAX_CONCURRENCY="${TAG_AGENT_MAX_CONCURRENCY:-2}"

agent_python="${TAG_AGENT_PYTHON:-tagpilot-agent/.venv/bin/python}"
if [[ ! -x "$agent_python" ]]; then
  echo '请先执行 uv sync --project tagpilot-agent --extra dev' >&2
  exit 1
fi
export TAG_SEMANTIC_URL="${TAG_SEMANTIC_URL:-http://127.0.0.1:${TAG_RUNTIME_PORT:-8091}}"
export TAG_AGENT_DB="${TAG_AGENT_DB:-${ROOT_DIR}/tagpilot-agent/out/workbench.sqlite}"
export PYTHONPATH="${ROOT_DIR}/tagpilot-agent${PYTHONPATH:+:$PYTHONPATH}"
exec "$agent_python" -m uvicorn tagpilot_agent.server:app --host "${TAG_AGENT_HOST:-127.0.0.1}" --port "${TAG_AGENT_PORT:-8092}"
