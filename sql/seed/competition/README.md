# 竞赛彩排数据库快照

面向评委：**用一份 mysqldump 还原与录制演示一致的 `ry` + `indiv_cust` 全库**，替代 `sql/init/ry_init.sql` + `bin/db-migrate.sh` + `agent-meta-skills.sql` 分步初始化。

## 文件

| 文件 | 说明 |
| :--- | :--- |
| `tagpilot-competition-20260930.sql.gz` | 全库导出（约 5MB 压缩），含库 107、已发布元 Skill、语义快照 ACTIVE、对照客群 group 128 等 |
| `tagpilot-competition-20260930.manifest.json` | 导出时间与 git commit |

## 导入

```bash
DB_PASSWORD=你的密码 bash bin/import-competition-db.sh
# 或指定文件：
DB_PASSWORD=xxx bash bin/import-competition-db.sh sql/seed/competition/tagpilot-competition-20260930.sql.gz
```

导入前会 `CREATE DATABASE` 并覆盖两库内对象（dump 内含 `DROP`/`CREATE`）。

## 维护者重新导出

在本机彩排库就绪后：

```bash
DB_PASSWORD=xxx bash bin/export-competition-db.sh 20260930
```

## 仍不在 MySQL 里的复现项

见仓库根 [README.md](../../../README.md)「评委复现清单」与 `docs/交付文档/演示脚本`；主要包括 BGE 权重、语义 LOCAL 索引目录、大模型 API 配置、可选 Agent SQLite 运行库。
