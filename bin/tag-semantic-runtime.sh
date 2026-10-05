#!/usr/bin/env bash
# 标签语义引擎 + 向量检索索引层以前台方式托管；依赖外部 Redis/Milvus，不管理基础服务。
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT_DIR=$(pwd)

: "${TAG_RUNTIME_TOKEN:?请通过环境变量提供服务间认证令牌，Java 与 Python 必须一致}"

# 外部 TAG_EMBEDDING_* 优先；否则读取本机 .tag-embedding-config（不入 Git，不回显密钥）
if [[ "${TAG_EMBEDDING_BACKEND:-}" == "remote" && -n "${TAG_EMBEDDING_API_KEY:-}${SILICONFLOW_API_KEY:-}" ]]; then
  :
elif [[ -n "${TAG_EMBEDDING_PATH:-}" || "${TAG_ALLOW_HASH_BASELINE:-false}" == true || "${TAG_EMBEDDING_BACKEND:-}" == "hash" ]]; then
  :
elif [[ -f "$ROOT_DIR/.tag-embedding-config" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.tag-embedding-config"
  export TAG_EMBEDDING_BACKEND TAG_RERANK_BACKEND \
    TAG_EMBEDDING_BASE_URL TAG_EMBEDDING_MODEL TAG_EMBEDDING_DIM TAG_EMBEDDING_PATH \
    TAG_EMBEDDING_API_KEY TAG_RERANK_API_KEY SILICONFLOW_API_KEY \
    TAG_RERANK_BASE_URL TAG_RERANK_MODEL TAG_RERANKER_PATH \
    TAG_EMBEDDING_TIMEOUT_S TAG_EMBEDDING_BATCH_SIZE TAG_EMBEDDING_MAX_RETRIES
fi

backend="${TAG_EMBEDDING_BACKEND:-local}"
if [[ "$backend" == "remote" ]]; then
  : "${TAG_EMBEDDING_BASE_URL:=https://api.siliconflow.cn/v1}"
  : "${TAG_EMBEDDING_MODEL:=BAAI/bge-m3}"
  : "${TAG_EMBEDDING_DIM:=1024}"
  export TAG_EMBEDDING_BACKEND TAG_EMBEDDING_BASE_URL TAG_EMBEDDING_MODEL TAG_EMBEDDING_DIM
  key="${TAG_EMBEDDING_API_KEY:-${SILICONFLOW_API_KEY:-}}"
  if [[ -z "$key" ]]; then
    echo '远程 Embedding 需要 TAG_EMBEDDING_API_KEY 或 SILICONFLOW_API_KEY（或仓库根 .tag-embedding-config）' >&2
    exit 1
  fi
  if [[ -z "${TAG_RERANK_BACKEND:-}" || "${TAG_RERANK_BACKEND}" == "remote" ]]; then
    TAG_RERANK_BACKEND=remote
    : "${TAG_RERANK_BASE_URL:=https://api.siliconflow.cn/v1}"
    : "${TAG_RERANK_MODEL:=BAAI/bge-reranker-v2-m3}"
    export TAG_RERANK_BACKEND TAG_RERANK_BASE_URL TAG_RERANK_MODEL
  fi
elif [[ "$backend" != "hash" && -z "${TAG_EMBEDDING_PATH:-}" && "${TAG_ALLOW_HASH_BASELINE:-false}" != true ]]; then
  echo '请提供 TAG_EMBEDDING_PATH；远程模式设 TAG_EMBEDDING_BACKEND=remote；只有隔离基线实验才设置 TAG_ALLOW_HASH_BASELINE=true' >&2
  exit 1
fi
runtime_python="${TAG_RUNTIME_PYTHON:-tagpilot-semantic/.venv/bin/python}"
if [[ ! -x "$runtime_python" ]]; then
  echo '请先执行 uv sync --project tagpilot-semantic --extra dev（本地模型还需 --extra models）' >&2
  exit 1
fi
export PYTHONPATH="${ROOT_DIR}/tagpilot-semantic${PYTHONPATH:+:$PYTHONPATH}"
exec "$runtime_python" -m uvicorn tag_semantic.server:app --host "${TAG_RUNTIME_HOST:-127.0.0.1}" --port "${TAG_RUNTIME_PORT:-8091}"
