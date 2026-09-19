#!/bin/sh
# 一键启动/停止前后端工程 (参照 ry.sh 风格，管理 后端jar + 前端dev server)
# 用法:
#   ./dev.sh start      启动前后端 (jar 缺失或源码有更新时自动增量编译)
#   ./dev.sh stop       停止前后端
#   ./dev.sh restart    重启
#   ./dev.sh status     查看状态
#   ./dev.sh build      强制重新编译后端 (mvn clean package -DskipTests)
#   PORT=8081 ./dev.sh start   指定前端端口 (默认 80)
#   DATABROKER_CRYPTO_SECRET=xxx ./dev.sh start   指定数据代理加密密钥 (默认读取/生成本机 .databroker-crypto-secret)
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

# 后端/前端进程识别模式
BACKEND_PAT="ruoyi-admin.jar"
FRONTEND_PAT="vue-cli-service"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*"; }

if [ "$1" = "" ]; then
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi

get_backend_pid()  { pgrep -f "$BACKEND_PAT" 2>/dev/null; }
get_frontend_pid() { pgrep -f "$FRONTEND_PAT" 2>/dev/null; }

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

    # 2. 启动后端
    ensure_crypto_secret
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
}

stop()
{
    echo "Stop $AppName"
    for name in "$BACKEND_PAT" "$FRONTEND_PAT"; do
        pids=$(pgrep -f "$name" 2>/dev/null)
        if [ -n "$pids" ]; then
            kill -TERM $pids 2>/dev/null
            WAITED=0
            while pgrep -f "$name" >/dev/null 2>&1 && [ "$WAITED" -lt 20 ]; do
                sleep 1
                WAITED=$((WAITED + 1))
            done
            pids=$(pgrep -f "$name" 2>/dev/null)
            [ -n "$pids" ] && kill -9 $pids 2>/dev/null
            green "$name stopped."
        else
            echo "$name already stopped."
        fi
    done
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
}

case "$1" in
    start)   start;;
    stop)    stop;;
    restart) restart;;
    status)  status;;
    build)   select_java; build_backend;;
    *)
        echo "Usage: $0 {start|stop|restart|status|build}"
        exit 1;;
esac
