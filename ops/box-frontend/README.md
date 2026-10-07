# Box 前端部署交付（2026-10-06 FIX3）

本目录版本化保存当前 box 的 nginx 配置、三个部署入口、公共回滚函数、资源验证和隔离故障探针。运行位置：`/workspace/tagpilot-data/frontend-prod/`，源码位置：`/workspace/tagpilot/`。路径不同的主机须先调整路径，不能直接运行。

安装时逐文件复制到运行目录，保留现有 `current`、`previous`、releases、PID、日志和秘密文件；不要覆盖在线 nginx.conf。运行 `switch-to-prod.sh` 会将新配置和两前端构建一起切换，经 nginx -t/reload/HTTP 验证后才更新 previous；任何失败恢复原 current/previous/config。脚本共用 flock，EXIT 捕获函数与子 shell 失败，回滚失败明确报警。start/dev 同样保存和恢复三个状态。

安全演练：`python3 /workspace/tagpilot/ops/box-frontend/deploy-probe.py --output-dir /workspace/tagpilot-data/codex-fix-20261006/fix3/deploy-probe-suite`。输出目录必须显式传入且位于仓库之外；探针复制本目录版本化脚本并在指定目录运行假 npm/sudo/curl/mv，涵盖构建、配置检查、reload、连接失败、HTTP 500、TERM、链接更新、previous 缺失、连续成功再失败与手动回切。不会调用真实 nginx/服务。dev 探针先模拟端口未就绪，实际覆盖冷启动、仅单侧启动及冷启动成功后立即切 prod；断言长驻子进程无 deploy.lock FD。部署子进程启动前关闭 FD 9，锁只由发布控制进程持有。

源站固定名资源 no-cache，Cloudflare 仍可能覆写浏览器 TTL（观察值四小时）；控制面需配置 `/styles/*` 遵守源站、API/profile bypass cache，并验证最终 HTTPS 响应。未获得该控制面入口，本交付不声称端到端缓存已完成。

M5 真实启动监督尚未注册；本机 PID 1 为 tini，按 `/workspace/tagpilot-data/INFRA_STATUS.md` 在真实平台启动器注册 Docker→防火墙→Java/Python→nginx→项目 tunnel，之后另行演练重启。本轮不动系统 cloudflared；2375 防火墙调查及规则见 FIX3 报告和 INFRA_STATUS；Docker 桥来源仍视为可信并保留容器互访。ACTIVE 工件小备份不能代替历史工件或完整索引灾备。部署副本不包含密钥、token、账户或数据库凭据。
