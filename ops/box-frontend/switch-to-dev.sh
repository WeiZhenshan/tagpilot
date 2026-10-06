#!/usr/bin/env bash
set -Eeuo pipefail
source /workspace/tagpilot-data/frontend-prod/deploy-common.sh
exec 9>"$ROOT/run/deploy.lock"; flock -n 9
deployment_begin dev
started_pidfiles=""
if ! curl --max-time 3 -fsS http://127.0.0.1:5174/agent-ui/ -o /dev/null; then
  (cd /workspace/tagpilot/tagpilot-assistant; nohup setsid npm run dev -- --host 127.0.0.1 >"$AUDIT/assistant-dev.log" 2>&1 </dev/null & echo $! >"$ROOT/run/assistant-dev.pid")
  started_pidfiles="$ROOT/run/assistant-dev.pid"
fi
if ! curl --max-time 3 -fsS http://127.0.0.1:18081/ -o /dev/null; then
  (cd /workspace/tagpilot/ruoyi-ui; nohup setsid env PORT=18081 NODE_OPTIONS=--openssl-legacy-provider npm run dev -- --host 127.0.0.1 --port 18081 >"$AUDIT/ui-dev.log" 2>&1 </dev/null & echo $! >"$ROOT/run/vue-cli.pid")
  started_pidfiles="$started_pidfiles $ROOT/run/vue-cli.pid"
fi
ready=0
for ((i=0;i<90;i++)); do
  code=$(curl --max-time 2 -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18081/ || true)
  assistant_code=$(curl --max-time 2 -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5174/agent-ui/ || true)
  if [[ "$code" == 200 && "$assistant_code" == 200 ]]; then ready=1; break; fi
  sleep 1
done
[[ "$ready" == 1 ]]
sudo -n /usr/sbin/nginx -c "$ROOT/conf/nginx-dev.conf" -t
deployment_changed=1
replace_conf "$ROOT/conf/nginx-dev.conf"
nginx_apply
sleep 1
probe
deployment_verified=1
echo 'development frontend ready; nginx remains the only public entry on 8081'
