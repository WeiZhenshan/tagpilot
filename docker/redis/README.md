# Redis（与当前运行实例对齐）

本目录可单独拷贝到另一台已安装 Docker / OrbStack 的电脑直接启动。配置来自本机正在运行的容器：

| 项 | 值 |
|---|---|
| 镜像 | `redis:7.4.7`（当前 `redis:7` 解析到的版本） |
| 端口 | `6379` |
| 密码 | 无（与 `ruoyi-admin` 的 `spring.redis.password` 空值一致） |
| 持久化 | AOF（`--appendonly yes`） |
| 数据 | Docker 命名卷 `redis-data`，不依赖 `/mydata/...` 这类本机路径 |

## 另一台电脑

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 或 [OrbStack](https://orbstack.dev/)。
2. 复制整个 `docker/redis/` 目录（或整个仓库）。
3. 在该目录执行：

```bash
docker compose up -d
docker compose ps
docker compose exec redis redis-cli ping
```

成功应返回 `PONG`。应用侧保持：

```yaml
spring.redis.host: localhost
spring.redis.port: 6379
spring.redis.password:   # 空
spring.redis.database: 0
```

停止 / 删除容器（**默认不删数据卷**）：

```bash
docker compose down
```

连数据一起清掉（新环境一般不需要）：

```bash
docker compose down -v
```

## 本机注意

本机 OrbStack 里已有名为 `redis`、占用 `6379` 的实例。不要在本机再 `up` 一份，会端口冲突。这份文件是给新机器或重建环境用的。
