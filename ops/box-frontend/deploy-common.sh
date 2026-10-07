#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/workspace/tagpilot-data/frontend-prod
AUDIT=/workspace/tagpilot-data/codex-fix-20261006/fix3
CONF="$ROOT/conf/nginx.conf"
PIDFILE="$ROOT/run/nginx.pid"
mkdir -p "$ROOT/run" "$AUDIT"
atomic_link() {
  local next="$2.next.$$.$RANDOM"
  ln -s "$1" "$next" || return 1
  mv -Tf "$next" "$2" || { rm -f "$next"; return 1; }
}
replace_conf() {
  cp "$1" "$CONF.next.$$" || return 1
  mv -f "$CONF.next.$$" "$CONF" || return 1
}
nginx_apply() {
  sudo -n /usr/sbin/nginx -c "$CONF" 9>&- -t || return 1
  if [[ -f "$PIDFILE" ]] && sudo -n kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    sudo -n /usr/sbin/nginx -c "$CONF" 9>&- -s reload || return 1
  else
    sudo -n /usr/sbin/nginx -c "$CONF" 9>&- || return 1
  fi
}
probe() {
  local path code
  for path in / /agent-ui/ /dev-api/captchaImage; do
    code=$(curl --max-time 15 -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:8081$path") || return 1
    [[ "$code" == 200 ]] || { echo "health failure $path HTTP=$code"; return 1; }
  done
  code=$(curl --max-time 15 -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8081/dev-api/v3/api-docs) || return 1
  [[ "$code" == 404 ]] || return 1
}
# EXIT 覆盖函数、子 shell、构建失败；不依赖 ERR 的继承/条件调用语义。
deployment_begin() {
  original_current=$(readlink "$ROOT/current") || return 1
  original_previous=$(readlink "$ROOT/previous" || true)
  backup="$AUDIT/nginx-before-$1-$(date +%s)-$$.conf"
  cp "$CONF" "$backup" || return 1
  deployment_changed=0
  deployment_verified=0
  trap 'deployment_exit $?' EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  trap 'exit 129' HUP
}
deployment_exit() {
  local status=$1 recovery_failed=0
  trap - EXIT INT TERM HUP
  if [[ "$deployment_verified" != 1 && "$deployment_changed" == 1 ]]; then
    atomic_link "$original_current" "$ROOT/current" || recovery_failed=1
    if [[ -n "$original_previous" ]]; then
      atomic_link "$original_previous" "$ROOT/previous" || recovery_failed=1
    else
      rm -f "$ROOT/previous" || recovery_failed=1
    fi
    replace_conf "$backup" || recovery_failed=1
    nginx_apply || recovery_failed=1
    if [[ "$recovery_failed" == 0 ]]; then
      echo "rolled back current, previous and configuration"
    else
      echo "ROLLBACK FAILED: inspect current/previous/config and nginx; backup=$backup" >&2
    fi
  fi
  if [[ "$deployment_verified" != 1 ]]; then
    # dev 模式失败仅清理本次新建的进程；旧服务保持存活。
    for pidfile in ${started_pidfiles:-}; do
      if [[ -f "$pidfile" ]]; then kill -- -"$(cat "$pidfile")" 2>/dev/null || true; fi
    done
    [[ "$status" != 0 ]] || status=1
  fi
  [[ "$recovery_failed" == 0 ]] || status=1
  exit "$status"
}
