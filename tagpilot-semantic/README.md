# tagpilot-semantic

标签语义检索服务（FastAPI，默认 `:8091`）。Java 负责快照与资格；本服务加载 **LOCAL** 或 Milvus 索引并执行多通道检索。

**竞赛交付**：环境与启动步骤见仓库根目录 [README.md](../README.md)。BGE 权重使用 [bin/download-bge-models.sh](../bin/download-bge-models.sh) 下载；索引产物在 `out/full-20260919/`（`snapshots/` + `indexes/`，激活 build：`bge-m3-l107-20260919-002-r3`）。

## 开发速查

```bash
uv sync --project tagpilot-semantic --extra dev --extra models
export TAG_RUNTIME_TOKEN='与 Java 一致'
export TAG_EMBEDDING_PATH="$PWD/out/models/bge-m3"
export TAG_RERANKER_PATH="$PWD/out/models/bge-reranker-v2-m3"
export TAG_SNAPSHOT_DIR="$PWD/out/full-20260919/snapshots"
export TAG_INDEX_DIR="$PWD/out/full-20260919/indexes"
../bin/tag-semantic-runtime.sh
```

或使用仓库根目录 `./dev.sh runtime start`。

模型清单模板：[models-sources.json.example](models-sources.json.example)。
