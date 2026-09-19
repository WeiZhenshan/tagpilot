# Docker 运行时

本目录按服务拆分，拷到另一台电脑后在对应子目录执行 `docker compose up -d` 即可。不依赖本机绝对路径。

| 目录 | 是否应用必需 | 说明 |
|---|---|---|
| [redis/](redis/README.md) | **是** | 登录 Token / 缓存 / 限流。`localhost:6379`，无密码 |
| [milvus/](milvus/docker-compose.yml) | 否（语义检索索引） | 对齐本机 OrbStack 的 Milvus 3.0.1 栈 |

应用启动前 Redis 必须在 6379 监听（`dev.sh` 会检查该端口）。
