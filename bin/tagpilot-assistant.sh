#!/bin/sh
# TagPilot 智能体工作台（Assistant UI / Vite）
# 用法: ./bin/tagpilot-assistant.sh
# 端口: TAG_ASSISTANT_PORT（默认 5174）

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
APP_DIR="$ROOT_DIR/tagpilot-assistant"
PORT="${TAG_ASSISTANT_PORT:-5174}"

cd "$APP_DIR" || exit 1
if [ ! -d node_modules ]; then
    echo "tagpilot-assistant 依赖缺失，请先: cd tagpilot-assistant && npm install"
    exit 1
fi
exec npx vite --port "$PORT" --host 127.0.0.1
