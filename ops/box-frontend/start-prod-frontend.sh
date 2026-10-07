#!/usr/bin/env bash
set -Eeuo pipefail
source /workspace/tagpilot-data/frontend-prod/deploy-common.sh
exec 9>"$ROOT/run/deploy.lock"; flock -n 9
[[ -s "$ROOT/current/dist/index.html" && -s "$ROOT/current/assistant-www/agent-ui/index.html" ]]
deployment_begin start
deployment_changed=1
replace_conf "$ROOT/conf/nginx-prod.conf"
nginx_apply
sleep 1
probe
deployment_verified=1
echo 'production frontend healthy on 8081'
