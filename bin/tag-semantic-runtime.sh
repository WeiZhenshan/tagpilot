#!/usr/bin/env bash
# 运行时以前台方式托管；依赖外部 Redis/Milvus，不管理基础服务。
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TAG_RUNTIME_TOKEN:?请通过环境变量提供服务间认证令牌，Java 与 Python 必须一致}"
if [[ -z "${TAG_EMBEDDING_PATH:-}" && "${TAG_ALLOW_HASH_BASELINE:-false}" != true ]]; then
  echo '请提供 TAG_EMBEDDING_PATH；只有隔离基线实验才设置 TAG_ALLOW_HASH_BASELINE=true' >&2
  exit 1
fi
runtime_python="${TAG_RUNTIME_PYTHON:-ai-runtime/.venv/bin/python}"
if [[ ! -x "$runtime_python" ]]; then
  echo '请先执行 uv sync --project ai-runtime --extra dev（真实模型还需 --extra models）' >&2
  exit 1
fi
exec "$runtime_python" -m uvicorn tag_semantic.server:app --host "${TAG_RUNTIME_HOST:-127.0.0.1}" --port "${TAG_RUNTIME_PORT:-8091}"
