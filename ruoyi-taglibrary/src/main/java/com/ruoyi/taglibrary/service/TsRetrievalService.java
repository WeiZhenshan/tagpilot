package com.ruoyi.taglibrary.service;

import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.*;

@Service
public class TsRetrievalService {
    @Autowired private ITsCatalogRuntimeService catalog;
    @Autowired private TsRuntimeClient runtime;
    @Autowired private TsCatalogSnapshotMapper snapshots;
    @Autowired private TsIndexBuildMapper builds;

    public TsIndexBuild startBuild(String snapshotId, String storeType) {
        TsCatalogSnapshot snapshot = snapshots.selectById(snapshotId);
        if (snapshot == null) throw new ServiceException("快照不存在");
        TsIndexBuild build = new TsIndexBuild(); build.setBuildId("b-" + UUID.randomUUID()); build.setSnapshotId(snapshotId); build.setStoreType(storeType);
        catalog.registerBuild(build);
        try {
            Map<String, Object> manifest = runtime.post("/build", map("snapshot_id", snapshotId, "build_id", build.getBuildId(), "library_id", snapshot.getLibraryId(), "store_type", storeType));
            if (!snapshotId.equals(manifest.get("snapshot_id")) || !build.getBuildId().equals(manifest.get("build_id")) || !snapshot.getContentHash().equals(manifest.get("content_hash")) || !storeType.equals(manifest.get("store_type"))) throw new ServiceException("构建 manifest 身份校验失败");
            build.setDocCount(Integer.valueOf(String.valueOf(manifest.get("doc_count")))); build.setDocIdHash((String) manifest.get("doc_id_hash"));
            build.setArtifactUri((String) manifest.get("artifact_uri")); build.setArtifactHash((String) manifest.get("artifact_hash")); build.setMilvusCollection((String) manifest.get("milvus_collection"));
            build.setEmbeddingModel((String) manifest.get("embedding_model")); build.setEmbeddingDim(Integer.valueOf(String.valueOf(manifest.get("embedding_dim"))));
            build.setEmbeddingModelHash((String) manifest.get("embedding_model_hash")); build.setRerankerModel((String) manifest.get("reranker_model"));
            build.setRerankerModelHash((String) manifest.get("reranker_model_hash")); build.setRetrievalConfigHash((String) manifest.get("retrieval_config_hash"));
            build.setAnalyzerVersion((String) manifest.get("analyzer_version")); build.setDocTemplateVersion((String) manifest.get("doc_template_version"));
            builds.updateBuild(build);
            return catalog.updateBuildStatus(build.getBuildId(), "READY", json(manifest.get("eval_summary")));
        } catch (Exception e) { catalog.updateBuildStatus(build.getBuildId(), "FAILED", "{\"status\":\"BUILD_FAILED\"}"); throw e; }
    }
}
