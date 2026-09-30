# 竞赛彩排数据库快照

面向评委：**用一份 mysqldump 还原与录制演示一致的 `ry` + `indiv_cust` 全库**，替代 `sql/init/ry_init.sql` + `bin/db-migrate.sh` + `agent-meta-skills.sql` 分步初始化。

## 文件

| 文件 | 说明 |
| :--- | :--- |
| `tagpilot-competition-20260930.sql.gz` | 全库导出（约 6MB 压缩），含库 107、已发布元 Skill、语义快照 ACTIVE、演示对照客群「全量客户（资产结构基准）」等 |
| `tagpilot-competition-20260930.manifest.json` | 导出时间与 git commit |
| `demo-baseline-cohort.sql` | 演示对照客群的**重建脚本**（幂等；方案自动绑定库内 ACTIVE 快照与索引构建）——快照已含该对象群，仅在导入其他/更新后的快照或对象群被删时执行 |

## 导入

```bash
DB_PASSWORD=你的密码 bash bin/import-competition-db.sh
# 或指定文件：
DB_PASSWORD=xxx bash bin/import-competition-db.sh sql/seed/competition/tagpilot-competition-20260930.sql.gz
```

导入前会 `CREATE DATABASE` 并覆盖两库内对象（dump 内含 `DROP`/`CREATE`）。

## 演示对照客群（资产结构透视）

演示「客群资产结构透视」需要两个客群：目标客群现场一句话圈选生成（不预置），**对照客群**为对象群「全量客户（资产结构基准）」（当前授权范围内的全部客户，2,000 人；技能运行时在「对照客群」下拉里选它）。快照已含该对象群，导入后即可用。

需要重建时（换了其他/更新的快照、或对象群被删）：

```bash
mysql --default-character-set=utf8mb4 -h127.0.0.1 -uroot -p ry < sql/seed/competition/demo-baseline-cohort.sql
```

脚本按「库 107 + 名称」判重，可重复执行；对象群的方案 `build_id/snapshot_id/artifact_hash` 在执行时从 **库内 ACTIVE 快照与索引构建**读取，因此换快照后重建不会出现「对照客群与当前发布版本不一致」。执行末尾会打印一行校验结果（snapshot_id / build_id / scope 应为 SCOPE_ALL）。

对照口径与预期数字（287 人 vs 2,000 人的逐项对账）见 [演示脚本附录 A](../../../docs/交付文档/演示脚本（客群资产结构透视）-v1.0.md)。

## 维护者重新导出

在本机彩排库就绪后：

```bash
DB_PASSWORD=xxx bash bin/export-competition-db.sh 20260930
```

## 仍不在 MySQL 里的复现项

见仓库根 [README.md](../../../README.md)「评委复现清单」与 `docs/交付文档/演示脚本`；主要包括 BGE 权重、语义 LOCAL 索引目录、大模型 API 配置、可选 Agent SQLite 运行库。
