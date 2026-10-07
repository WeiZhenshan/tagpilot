# Box 项目防火墙（FIX3）

本目录保存运行副本，权威入口 `/workspace/tagpilot-data/codex-fix-20261006/apply-firewall.sh`；安装时逐文件复制三个脚本到该目录。应用：`sudo -n bash /workspace/tagpilot-data/codex-fix-20261006/apply-firewall.sh`。

Docker 建链后执行，IPv4/IPv6 按表原子 COMMIT 更新项目链，没有独立 flush 空窗；不改 daemon 配置或重启 dockerd。2375 仅放行 loopback；FIX3 调查没有发现桥来源依赖。原有 Docker 互访例外保留，不等于授予 2375 访问。所有测试数据、备份、调查和验收在 fix3 输出目录，不在仓库。

`restore-firewall.sh` 用 FIX3 前完整规则备份撤销本轮变更，只适用于 Docker 拓扑不变的紧急回滚；日常启动恢复必须运行 apply（含2375）。实际启动注册与整机重启验收仍未完成。调查中的2375监听 socket 所有者在当前PID命名空间不可见，不能认定它属于项目dockerd。
