#!/bin/sh
# 一键启停开发环境 (参照 ry.sh 风格，管理 后端jar + 前端dev server + 语义引擎 + Agent 编排层 + 智能体工作台)
# 用法:
#   ./dev.sh start      启动前后端、语义引擎、编排层与智能体工作台 (令牌默认读取/生成本机 .tag-runtime-token)
#   ./dev.sh stop       停止全部 (后端/前端/语义引擎/编排层/智能体工作台)
#   ./dev.sh restart    重启全部
#   ./dev.sh status     查看全部状态
#   ./dev.sh build      强制重新编译后端 (mvn clean package -DskipTests)
#   ./dev.sh runtime {start|stop|restart|status}   单独管理 Python 语义引擎 (端口 8091)
#   ./dev.sh agent {start|stop|restart|status}     单独管理 Agent 编排层 (端口 8092)
#   ./dev.sh assistant {start|stop|restart|status} 单独管理智能体工作台 (端口 5174)
#   PORT=8081 ./dev.sh start   指定前端端口 (默认 80)
#   DATABROKER_CRYPTO_SECRET=xxx ./dev.sh start   指定数据代理加密密钥 (默认读取/生成本机 .databroker-crypto-secret)
#   TAG_RUNTIME_TOKEN=xxx ./dev.sh start          指定服务间令牌 (默认读取/生成本机 .tag-runtime-token)
#   TAG_SNAPSHOT_DIR=xxx TAG_INDEX_DIR=yyy ./dev.sh start   指定快照/索引目录 (默认自动选用 tagpilot-semantic/out 下的完整数据集)
#   LLM 选择器默认读取本机 .tag-llm-config（DeepSeek 等 OpenAI-compatible 端点）；也可用环境变量 TAG_LLM_* 覆盖
AppName=ruoyi-admin.jar

# JVM参数
JVM_OPTS="-Dname=$AppName -Duser.timezone=Asia/Shanghai -Xms512m -Xmx1024m -XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=512m -XX:+HeapDumpOnOutOfMemoryError -XX:+UseParallelGC"

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
JAR_PATH="$ROOT_DIR/ruoyi-admin/target/$AppName"
BACKEND_LOG="$ROOT_DIR/logs/$AppName-dev.log"
RUNTIME_JAR="$ROOT_DIR/logs/runtime/$AppName"
FRONTEND_LOG="$ROOT_DIR/logs/ruoyi-ui-dev.log"
UI_DIR="$ROOT_DIR/ruoyi-ui"
BACKEND_PORT=8080
FRONTEND_PORT="${PORT:-80}"

# 数据代理加密密钥文件（本机持久化，不入库不入 git；外部环境变量优先）
SECRET_FILE="$ROOT_DIR/.databroker-crypto-secret"

# 语义运行时服务间令牌文件（Java 与 Python 必须一致，同样本机持久化、不入 git）
TOKEN_FILE="$ROOT_DIR/.tag-runtime-token"

# LLM 选择器配置（OpenAI-compatible；本机持久化、不入 git）
LLM_CONFIG_FILE="$ROOT_DIR/.tag-llm-config"

# Python 语义引擎（tag_semantic / uvicorn，令牌经环境变量注入两侧进程）
RT_SCRIPT="$ROOT_DIR/bin/tag-semantic-runtime.sh"
RT_LOG="$ROOT_DIR/logs/tag-semantic-runtime.log"
RT_PORT="${TAG_RUNTIME_PORT:-8091}"

# Agent 编排层（tagpilot_agent / uvicorn）
AGENT_SCRIPT="$ROOT_DIR/bin/tagpilot-agent.sh"
AGENT_LOG="$ROOT_DIR/logs/tagpilot-agent.log"
AGENT_PORT="${TAG_AGENT_PORT:-8092}"

ASSISTANT_SCRIPT="$ROOT_DIR/bin/tagpilot-assistant.sh"
ASSISTANT_LOG="$ROOT_DIR/logs/tagpilot-assistant.log"
ASSISTANT_PORT="${TAG_ASSISTANT_PORT:-5174}"
ASSISTANT_DIR="$ROOT_DIR/tagpilot-assistant"

# 后端/前端/运行时进程识别模式
BACKEND_PAT="ruoyi-admin.jar"
FRONTEND_PAT="vue-cli-service"
RT_PAT="tag_semantic.server:app"
AGENT_PAT="tagpilot_agent.server:app"
ASSISTANT_PAT="vite --port ${ASSISTANT_PORT}"

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
blue()   { printf '\033[0;34m%s\033[0m\n' "$*"; }

if [ "$1" = "" ]; then
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi

get_backend_pid()  { pgrep -f "$BACKEND_PAT" 2>/dev/null; }
get_frontend_pid() { pgrep -f "$FRONTEND_PAT" 2>/dev/null; }
get_runtime_pid()  { pgrep -f "$RT_PAT" 2>/dev/null; }
get_agent_pid()    { pgrep -f "$AGENT_PAT" 2>/dev/null; }
get_assistant_pid() { pgrep -f "$ASSISTANT_PAT" 2>/dev/null; }

port_up() { nc -z 127.0.0.1 "$1" >/dev/null 2>&1; }

# 本机默认 JDK 是 17，项目要求 Java 8，自动切换到已安装的 JDK 1.8
select_java() {
    JAVA8_HOME=$(/usr/libexec/java_home -v 1.8 2>/dev/null)
    if [ -n "$JAVA8_HOME" ]; then
        export JAVA_HOME="$JAVA8_HOME"
        export PATH="$JAVA_HOME/bin:$PATH"
    fi
}

# 数据代理模块要求自定义加密密钥（P2-16：拒绝默认占位值）。
# 外部未设置时读取本机密钥文件，缺失则随机生成一次并持久化，避免每次重启都换钥导致存量密文不可解
ensure_crypto_secret() {
    [ -n "$DATABROKER_CRYPTO_SECRET" ] && return 0
    if [ -f "$SECRET_FILE" ]; then
        DATABROKER_CRYPTO_SECRET=$(cat "$SECRET_FILE")
    else
        DATABROKER_CRYPTO_SECRET=$(openssl rand -hex 32) || { red "生成加密密钥失败（缺少 openssl）"; exit 1; }
        printf '%s' "$DATABROKER_CRYPTO_SECRET" > "$SECRET_FILE"
        chmod 600 "$SECRET_FILE"
        blue "已生成本机数据代理加密密钥文件: $SECRET_FILE"
    fi
    export DATABROKER_CRYPTO_SECRET
}

# 语义运行时令牌：Java tag.runtime-token 与 Python TAG_RUNTIME_TOKEN 必须同值。
# 外部未设置时读取本机令牌文件，缺失则随机生成一次并持久化，避免每次重启换令牌导致两侧不一致
ensure_runtime_token() {
    [ -n "$TAG_RUNTIME_TOKEN" ] && return 0
    if [ -f "$TOKEN_FILE" ]; then
        TAG_RUNTIME_TOKEN=$(cat "$TOKEN_FILE")
    else
        TAG_RUNTIME_TOKEN=$(openssl rand -hex 32) || { red "生成语义运行时令牌失败（缺少 openssl）"; exit 1; }
        printf '%s' "$TAG_RUNTIME_TOKEN" > "$TOKEN_FILE"
        chmod 600 "$TOKEN_FILE"
        blue "已生成本机语义运行时令牌文件: $TOKEN_FILE"
    fi
    export TAG_RUNTIME_TOKEN
}

# LLM 选择器：外部 TAG_LLM_* 优先；否则读取本机 .tag-llm-config（供 LangGraph Agent 调用生成式模型）
ensure_llm_config() {
    if [ -n "${TAG_LLM_BASE_URL:-}" ] && [ -n "${TAG_LLM_MODEL:-}" ]; then
        export TAG_LLM_BASE_URL TAG_LLM_MODEL TAG_LLM_API_KEY
        return 0
    fi
    if [ -f "$LLM_CONFIG_FILE" ]; then
        # shellcheck disable=SC1090
        . "$LLM_CONFIG_FILE"
        export TAG_LLM_BASE_URL TAG_LLM_MODEL TAG_LLM_API_KEY
        blue "已加载本机 LLM 配置 (model=${TAG_LLM_MODEL:-?})"
    fi
}

# 语义层快照/索引目录：Java 写快照、Python 读快照并写索引，两侧必须指向同一数据集。
# 外部未配置时自动选用本机 tagpilot-semantic/out 下的完整数据集（同时含 snapshots/ 与 indexes/，按日期命名取最后一个）
ensure_tag_data_dirs() {
    SET=""
    for candidate in "$ROOT_DIR"/tagpilot-semantic/out/*/; do
        [ -d "$candidate/snapshots" ] && [ -d "$candidate/indexes" ] && SET="$candidate"
    done
    [ -n "$SET" ] || return 0
    SET="${SET%/}"
    if [ -z "${TAG_SNAPSHOT_DIR:-}" ]; then
        TAG_SNAPSHOT_DIR="$SET/snapshots"
        export TAG_SNAPSHOT_DIR
    fi
    if [ -z "${TAG_INDEX_DIR:-}" ]; then
        TAG_INDEX_DIR="$SET/indexes"
        export TAG_INDEX_DIR
    fi
    blue "使用本机语义数据集: $SET (快照 $TAG_SNAPSHOT_DIR, 索引 $TAG_INDEX_DIR)"
}

# 真实 BGE 依赖 FlagEmbedding，该包在 Python 3.14+ 不可用；优先使用 .venv-models (Python 3.12)
ensure_runtime_python() {
    [ -n "${TAG_RUNTIME_PYTHON:-}" ] && return 0
    if [ -x "$ROOT_DIR/tagpilot-semantic/.venv-models/bin/python" ]; then
        TAG_RUNTIME_PYTHON="$ROOT_DIR/tagpilot-semantic/.venv-models/bin/python"
    else
        TAG_RUNTIME_PYTHON="$ROOT_DIR/tagpilot-semantic/.venv/bin/python"
    fi
    export TAG_RUNTIME_PYTHON
}

ensure_agent_python() {
    [ -n "${TAG_AGENT_PYTHON:-}" ] && return 0
    TAG_AGENT_PYTHON="$ROOT_DIR/tagpilot-agent/.venv/bin/python"
    export TAG_AGENT_PYTHON
}

# 未显式配置向量模型时使用本机已下载的 bge-m3（真实模式必需，基线实验除外）
ensure_embedding_path() {
    [ -n "${TAG_EMBEDDING_PATH:-}" ] && return 0
    [ "${TAG_ALLOW_HASH_BASELINE:-false}" = true ] && return 0
    if [ -d "$ROOT_DIR/tagpilot-semantic/out/models/bge-m3" ]; then
        TAG_EMBEDDING_PATH="$ROOT_DIR/tagpilot-semantic/out/models/bge-m3"
        export TAG_EMBEDDING_PATH
        blue "使用本机默认向量模型: $TAG_EMBEDDING_PATH"
    fi
}

check_env() {
    port_up 6379 || { red "Redis 未启动 (端口 6379)，请先启动"; exit 1; }
    port_up 3306 || { red "MySQL 未启动 (端口 3306)，请先启动"; exit 1; }
    if [ "${TAG_CHECK_MILVUS:-false}" = true ]; then
        nc -z "${TAG_MILVUS_HOST:-127.0.0.1}" "${TAG_MILVUS_PORT:-19530}" >/dev/null 2>&1 || { red "外部 Milvus 未就绪"; exit 1; }
    fi
    blue "Redis / MySQL 运行中"
}

# jar 缺失或源码比 jar 新时需要重新编译 (排除 ruoyi-ui 及其 node_modules)
backend_stale() {
    [ -f "$JAR_PATH" ] || return 0
    MODULES=""
    for m in "$ROOT_DIR"/ruoyi-*; do
        case "$m" in
            *ruoyi-ui) continue ;;
        esac
        [ -d "$m" ] && MODULES="$MODULES $m"
    done
    find $MODULES "$ROOT_DIR/pom.xml" \( -name "*.java" -o -name "pom.xml" \) -newer "$JAR_PATH" -print -quit 2>/dev/null | grep -q .
}

build_backend() {
    blue "编译后端 (mvn clean package -DskipTests)..."
    (cd "$ROOT_DIR" && mvn clean package -DskipTests) || { red "后端编译失败"; exit 1; }
    green "后端编译完成"
}

compile_backend_if_stale() {
    if backend_stale; then
        build_backend
    else
        blue "后端 jar 已是最新，跳过编译"
    fi
}

# 语义运行时前置校验：令牌由 ensure_runtime_token 注入，模型路径外部优先、本机默认 bge-m3
runtime_check_env() {
    [ -n "${TAG_RUNTIME_TOKEN:-}" ] || {
        red "未配置 TAG_RUNTIME_TOKEN（Java 与 Python 必须使用同一令牌，只经环境变量注入）"
        return 1
    }
    ensure_runtime_python
    RT_PY="$TAG_RUNTIME_PYTHON"
    (cd "$ROOT_DIR" && [ -x "$RT_PY" ]) || {
        red "解释器不可执行: $RT_PY (请先 uv sync --project tagpilot-semantic --extra dev，真实模型还需 --extra models)"
        return 1
    }
    if [ -z "${TAG_EMBEDDING_PATH:-}" ] && [ "${TAG_ALLOW_HASH_BASELINE:-false}" != "true" ]; then
        red "未配置 TAG_EMBEDDING_PATH (隔离基线实验可设 TAG_ALLOW_HASH_BASELINE=true)"
        return 1
    fi
    if [ -n "${TAG_EMBEDDING_PATH:-}" ] && ! (cd "$ROOT_DIR" && [ -d "$TAG_EMBEDDING_PATH" ]); then
        red "TAG_EMBEDDING_PATH 目录不存在: $TAG_EMBEDDING_PATH"
        return 1
    fi
    # 缺 FlagEmbedding 时运行时能起来，但加载索引会失败成一个看不出原因的 503
    if [ -n "${TAG_EMBEDDING_PATH:-}" ] && ! (cd "$ROOT_DIR" && "$RT_PY" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('FlagEmbedding') else 1)" >/dev/null 2>&1); then
        PY_VER=$(cd "$ROOT_DIR" && "$RT_PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
        red "解释器缺少 FlagEmbedding（真实模型依赖，当前 Python ${PY_VER:-?}）"
        red "请执行: UV_PROJECT_ENVIRONMENT=.venv-models uv sync --project tagpilot-semantic --python 3.12 --extra dev --extra models"
        red "或设置: export TAG_RUNTIME_PYTHON='tagpilot-semantic/.venv-models/bin/python'"
        return 1
    fi
    port_up 6379 || yellow "Redis 未运行 (6379)，运行时可能不可用"
    if ! port_up "${TAG_MILVUS_PORT:-19530}"; then
        yellow "Milvus 未运行 (${TAG_MILVUS_PORT:-19530})，MILVUS 存储的索引不可用（LOCAL 存储不受影响）"
    fi
    return 0
}

runtime_start() {
    if [ -n "$(get_runtime_pid)" ]; then
        echo "tagpilot-semantic is running... (pid: $(get_runtime_pid | head -1))"
        return 0
    fi
    if port_up "$RT_PORT"; then
        red "端口 $RT_PORT 已被其他进程占用，无法启动语义引擎"
        return 1
    fi
    ensure_runtime_token
    ensure_runtime_python
    ensure_embedding_path
    ensure_tag_data_dirs
    runtime_check_env || return 1

    mkdir -p "$ROOT_DIR/logs"
    blue "启动语义引擎 (端口 $RT_PORT，日志: $RT_LOG)..."
    (cd "$ROOT_DIR" && nohup "$RT_SCRIPT" > "$RT_LOG" 2>&1 < /dev/null &)

    WAITED=0
    READY=0
    while [ "$WAITED" -lt 120 ]; do
        RT_CODE=$(curl -s -o /dev/null -m 2 -w '%{http_code}' "http://127.0.0.1:$RT_PORT/" 2>/dev/null)
        if [ -n "$RT_CODE" ] && [ "$RT_CODE" != "000" ]; then
            READY=1
            break
        fi
        WAITED=$((WAITED + 1))
        sleep 1
        # 启动几秒后进程消失视为启动失败
        if [ "$WAITED" -ge 3 ] && [ -z "$(get_runtime_pid)" ]; then
            break
        fi
    done

    if [ "$READY" = "1" ]; then
        green "语义引擎已就绪: http://127.0.0.1:$RT_PORT (pid: $(get_runtime_pid | head -1))"
    else
        red "语义引擎启动失败，日志末尾:"
        tail -30 "$RT_LOG"
        return 1
    fi
}

runtime_status() {
    if [ -n "$(get_runtime_pid)" ]; then
        green "tagpilot-semantic is running... (pid: $(get_runtime_pid | head -1))"
    else
        red "tagpilot-semantic is not running..."
    fi
}

agent_check_env() {
    [ -n "${TAG_RUNTIME_TOKEN:-}" ] || {
        red "未配置 TAG_RUNTIME_TOKEN（Java / 语义引擎 / 编排层必须使用同一令牌）"
        return 1
    }
    ensure_agent_python
    [ -x "$TAG_AGENT_PYTHON" ] || {
        red "编排层解释器不可执行: $TAG_AGENT_PYTHON (请先 uv sync --project tagpilot-agent --extra dev)"
        return 1
    }
    return 0
}

agent_start() {
    if [ -n "$(get_agent_pid)" ]; then
        echo "tagpilot-agent is running... (pid: $(get_agent_pid | head -1))"
        return 0
    fi
    if port_up "$AGENT_PORT"; then
        red "端口 $AGENT_PORT 已被其他进程占用，无法启动编排层"
        return 1
    fi
    ensure_runtime_token
    ensure_llm_config
    ensure_agent_python
    export TAG_SEMANTIC_URL="${TAG_SEMANTIC_URL:-http://127.0.0.1:$RT_PORT}"
    export TAG_AGENT_URL="${TAG_AGENT_URL:-http://127.0.0.1:$AGENT_PORT}"
    agent_check_env || return 1

    mkdir -p "$ROOT_DIR/logs"
    blue "启动 Agent 编排层 (端口 $AGENT_PORT，日志: $AGENT_LOG)..."
    (cd "$ROOT_DIR" && nohup "$AGENT_SCRIPT" > "$AGENT_LOG" 2>&1 < /dev/null &)

    WAITED=0
    READY=0
    while [ "$WAITED" -lt 30 ]; do
        AGENT_CODE=$(curl -s -o /dev/null -m 2 -w '%{http_code}' "http://127.0.0.1:$AGENT_PORT/" 2>/dev/null)
        if [ -n "$AGENT_CODE" ] && [ "$AGENT_CODE" != "000" ]; then
            READY=1
            break
        fi
        WAITED=$((WAITED + 1))
        sleep 1
        if [ "$WAITED" -ge 3 ] && [ -z "$(get_agent_pid)" ]; then
            break
        fi
    done

    if [ "$READY" = "1" ]; then
        green "编排层已就绪: http://127.0.0.1:$AGENT_PORT (pid: $(get_agent_pid | head -1))"
    else
        red "编排层启动失败，日志末尾:"
        tail -30 "$AGENT_LOG"
        return 1
    fi
}

agent_status() {
    if [ -n "$(get_agent_pid)" ]; then
        green "tagpilot-agent is running... (pid: $(get_agent_pid | head -1))"
    else
        red "tagpilot-agent is not running..."
    fi
}

assistant_start() {
    if [ -n "$(get_assistant_pid)" ]; then
        echo "tagpilot-assistant is running... (pid: $(get_assistant_pid | head -1))"
        return 0
    fi
    if port_up "$ASSISTANT_PORT"; then
        red "端口 $ASSISTANT_PORT 已被其他进程占用，无法启动智能体工作台"
        return 1
    fi
    if [ ! -d "$ASSISTANT_DIR/node_modules" ]; then
        blue "智能体工作台依赖缺失，执行 npm install..."
        (cd "$ASSISTANT_DIR" && npm install --no-audit --no-fund) || { red "tagpilot-assistant npm install 失败"; return 1; }
    fi
    mkdir -p "$ROOT_DIR/logs"
    blue "启动智能体工作台 (端口 $ASSISTANT_PORT，日志: $ASSISTANT_LOG)..."
    (cd "$ROOT_DIR" && nohup "$ASSISTANT_SCRIPT" > "$ASSISTANT_LOG" 2>&1 < /dev/null &)

    WAITED=0
    READY=0
    while [ "$WAITED" -lt 30 ]; do
        if port_up "$ASSISTANT_PORT"; then
            READY=1
            break
        fi
        WAITED=$((WAITED + 1))
        sleep 1
        if [ "$WAITED" -ge 3 ] && [ -z "$(get_assistant_pid)" ]; then
            break
        fi
    done

    if [ "$READY" = "1" ]; then
        green "智能体工作台已就绪: http://127.0.0.1:$ASSISTANT_PORT/agent-ui/ (pid: $(get_assistant_pid | head -1))"
    else
        red "智能体工作台启动失败，日志末尾:"
        tail -30 "$ASSISTANT_LOG"
        return 1
    fi
}

assistant_status() {
    if [ -n "$(get_assistant_pid)" ]; then
        green "tagpilot-assistant is running... (pid: $(get_assistant_pid | head -1))"
    else
        red "tagpilot-assistant is not running..."
    fi
}

start()
{
    if [ -n "$(get_backend_pid)" ] || [ -n "$(get_frontend_pid)" ]; then
        echo "前后端已有进程在运行，如需重启请先 ./dev.sh stop"
        status
        exit 1
    fi

    check_env
    select_java

    # 1. 编译后端
    compile_backend_if_stale

    # 2. 启动后端（令牌须在 JVM 启动前注入，否则 /taglibrary/semantic 相关接口会因未配置认证而失败）
    ensure_crypto_secret
    ensure_runtime_token
    ensure_tag_data_dirs
    export TAG_AGENT_URL="${TAG_AGENT_URL:-http://127.0.0.1:$AGENT_PORT}"
    mkdir -p "$ROOT_DIR/logs"
    blue "启动后端 (端口 $BACKEND_PORT，日志: $BACKEND_LOG)..."
    # 运行不可变副本，避免开发期间 mvn package 覆盖正在被 JVM 延迟读取的嵌套 JAR。
    mkdir -p "$(dirname "$RUNTIME_JAR")"
    cp "$JAR_PATH" "$RUNTIME_JAR.tmp" && mv "$RUNTIME_JAR.tmp" "$RUNTIME_JAR"
    nohup java $JVM_OPTS -jar "$RUNTIME_JAR" > "$BACKEND_LOG" 2>&1 &
    green "Start $AppName success... (pid: $!)"

    WAITED=0
    while [ "$WAITED" -lt 120 ]; do
        if port_up "$BACKEND_PORT"; then
            green "后端已就绪: http://localhost:$BACKEND_PORT"
            break
        fi
        WAITED=$((WAITED + 1))
        sleep 1
    done
    if ! port_up "$BACKEND_PORT"; then
        red "后端启动失败，日志末尾:"
        tail -30 "$BACKEND_LOG"
        exit 1
    fi

    # 3. 启动前端
    if [ ! -d "$UI_DIR/node_modules" ]; then
        blue "前端依赖缺失，执行 npm install (可能需要几分钟)..."
        (cd "$UI_DIR" && npm install) || { red "npm install 失败"; exit 1; }
    fi
    # Vue CLI 4 (webpack 4) 在 Node 17+ 上需要兼容 OpenSSL 3
    NODE_MAJOR=$(node -v 2>/dev/null | sed 's/^v//; s/\..*//')
    [ -n "$NODE_MAJOR" ] && [ "$NODE_MAJOR" -ge 17 ] 2>/dev/null && export NODE_OPTIONS="--openssl-legacy-provider"

    : > "$FRONTEND_LOG"
    blue "启动前端 (端口 $FRONTEND_PORT，日志: $FRONTEND_LOG)..."
    (cd "$UI_DIR" && nohup env port="$FRONTEND_PORT" npm run dev > "$FRONTEND_LOG" 2>&1 < /dev/null &)
    sleep 2
    FPID=$(pgrep -f "$FRONTEND_PAT" 2>/dev/null | head -1)
    echo "Start ruoyi-ui dev server success... (pid: ${FPID:-?})"

    WAITED=0
    while [ "$WAITED" -lt 180 ]; do
        if grep -q "App running at" "$FRONTEND_LOG" 2>/dev/null; then
            break
        fi
        WAITED=$((WAITED + 1))
        sleep 1
    done
    if grep -q "App running at" "$FRONTEND_LOG" 2>/dev/null; then
        APP_URL=$(sed -n 's/.*Local:[[:space:]]*http:\/\/localhost:\([0-9]*\)\/.*/http:\/\/localhost:\1\//p' "$FRONTEND_LOG" | tail -1)
        [ -n "$APP_URL" ] || APP_URL="http://localhost:$FRONTEND_PORT"
        green "前端已就绪: $APP_URL (默认账号 admin/admin123)"
    else
        red "前端启动可能失败，日志末尾:"
        tail -30 "$FRONTEND_LOG"
        exit 1
    fi

    # 4. 语义引擎与编排层（令牌已由 ensure_runtime_token 注入，启动失败不影响 Java/Vue）
    runtime_start || red "语义引擎启动失败；Java/Vue 不受影响，修复后可执行 ./dev.sh runtime restart"
    agent_start || red "编排层启动失败；Java/Vue 不受影响，修复后可执行 ./dev.sh agent restart"
    assistant_start || red "智能体工作台启动失败；Java/Vue 不受影响，修复后可执行 ./dev.sh assistant restart"
}

stop_one() {  # $1=进程匹配模式 $2=显示名
    pids=$(pgrep -f "$1" 2>/dev/null)
    if [ -z "$pids" ]; then
        echo "$2 already stopped."
        return 0
    fi
    kill -TERM $pids 2>/dev/null
    WAITED=0
    while pgrep -f "$1" >/dev/null 2>&1 && [ "$WAITED" -lt 20 ]; do
        sleep 1
        WAITED=$((WAITED + 1))
    done
    pids=$(pgrep -f "$1" 2>/dev/null)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null
    green "$2 stopped."
}

stop()
{
    echo "Stop $AppName"
    stop_one "$BACKEND_PAT" "$AppName"
    stop_one "$FRONTEND_PAT" "ruoyi-ui dev server"
    stop_one "$ASSISTANT_PAT" "tagpilot-assistant"
    stop_one "$RT_PAT" "tagpilot-semantic"
    stop_one "$AGENT_PAT" "tagpilot-agent"
}

restart()
{
    stop
    sleep 2
    start
}

status()
{
    if [ -n "$(get_backend_pid)" ]; then
        green "$AppName is running... (pid: $(get_backend_pid))"
    else
        red "$AppName is not running..."
    fi
    if [ -n "$(get_frontend_pid)" ]; then
        green "ruoyi-ui dev server is running... (pid: $(get_frontend_pid))"
    else
        red "ruoyi-ui dev server is not running..."
    fi
    runtime_status
    agent_status
    assistant_status
}

case "$1" in
    start)   start;;
    stop)    stop;;
    restart) restart;;
    status)  status;;
    build)   select_java; build_backend;;
    runtime)
        case "${2:-}" in
            start)   runtime_start;;
            stop)    stop_one "$RT_PAT" "tagpilot-semantic";;
            restart) stop_one "$RT_PAT" "tagpilot-semantic"; sleep 2; runtime_start;;
            status)  runtime_status;;
            *)       echo "Usage: $0 runtime {start|stop|restart|status}"; exit 1;;
        esac;;
    agent)
        case "${2:-}" in
            start)   agent_start;;
            stop)    stop_one "$AGENT_PAT" "tagpilot-agent";;
            restart) stop_one "$AGENT_PAT" "tagpilot-agent"; sleep 2; agent_start;;
            status)  agent_status;;
            *)       echo "Usage: $0 agent {start|stop|restart|status}"; exit 1;;
        esac;;
    assistant)
        case "${2:-}" in
            start)   assistant_start;;
            stop)    stop_one "$ASSISTANT_PAT" "tagpilot-assistant";;
            restart) stop_one "$ASSISTANT_PAT" "tagpilot-assistant"; sleep 2; assistant_start;;
            status)  assistant_status;;
            *)       echo "Usage: $0 assistant {start|stop|restart|status}"; exit 1;;
        esac;;
    *)
        echo "Usage: $0 {start|stop|restart|status|build|runtime|agent|assistant}"
        exit 1;;
esac
