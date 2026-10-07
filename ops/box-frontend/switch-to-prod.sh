#!/usr/bin/env bash
set -Eeuo pipefail
source /workspace/tagpilot-data/frontend-prod/deploy-common.sh
exec 9>"$ROOT/run/deploy.lock"; flock -n 9
release="$ROOT/releases/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$release/dist" "$release/assistant-www/agent-ui"
deployment_begin prod
previous=$(readlink -f "$ROOT/current")
(cd /workspace/tagpilot/ruoyi-ui; NODE_OPTIONS=--openssl-legacy-provider VUE_APP_BASE_API=/dev-api npm run build:prod 9>&- -- --dest "$release/dist") >"$AUDIT/build-ui.log" 2>&1
(cd /workspace/tagpilot/tagpilot-assistant; npm run build 9>&- -- --outDir "$release/assistant-www/agent-ui") >"$AUDIT/build-assistant.log" 2>&1
[[ -s "$release/dist/index.html" && -s "$release/assistant-www/agent-ui/index.html" ]]
! rg -q '@vite/client' "$release/assistant-www/agent-ui/index.html"
# 校验所有本版本 HTML 引用的本地构建资源，防止空目录或缺 chunk。
python3 "$ROOT/validate-release.py" "$release"
# 保留旧页面懒加载的资源；新版本同名文件优先。index 不复制。
for dir in static js css img fonts; do
  if [[ -d "$previous/dist/$dir" ]]; then mkdir -p "$release/dist/$dir"; cp -an "$previous/dist/$dir/." "$release/dist/$dir/"; fi
done
if [[ -d "$previous/assistant-www/agent-ui/assets" ]]; then
  mkdir -p "$release/assistant-www/agent-ui/assets"; cp -an "$previous/assistant-www/agent-ui/assets/." "$release/assistant-www/agent-ui/assets/"
fi
chmod -R a+rX "$release"
sudo -n /usr/sbin/nginx -c "$ROOT/conf/nginx-prod.conf" -t
deployment_changed=1
atomic_link "$release" "$ROOT/current"
cp "$ROOT/conf/nginx-prod.conf" "$CONF.next"; mv -f "$CONF.next" "$CONF"
nginx_apply
sleep 1
probe
# 验证成功后才更新 previous，更新自身失败仍由 EXIT 恢复。
atomic_link "$previous" "$ROOT/previous"
deployment_verified=1
echo "production release verified: $release; rollback: $previous"
