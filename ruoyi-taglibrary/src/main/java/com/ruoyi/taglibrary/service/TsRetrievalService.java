package com.ruoyi.taglibrary.service;

import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.*;

@Service
public class TsRetrievalService {
    @Autowired private ITsCatalogRuntimeService catalog;
    @Autowired private TsRuntimeClient runtime;
    @Autowired private TsRetrievalFeedbackMapper feedback;
    @Autowired private TsCatalogSnapshotMapper snapshots;
    @Autowired private TsIndexBuildMapper builds;

    @SuppressWarnings("unchecked")
    public Map<String, Object> retrieve(Long libraryId, String requirement) {
        if (requirement == null || requirement.trim().isEmpty() || requirement.length() > 500) throw new ServiceException("检索条件须为 1–500 字符");
        Map<String, Object> bundle = catalog.activeBundle(libraryId);
        String snapshotId = String.valueOf(bundle.get("snapshot_id")), buildId = String.valueOf(bundle.get("build_id"));
        List<Long> eligible = catalog.eligibleTagIds(libraryId, snapshotId);
        // Python 端 LangGraph 只在 Java 已计算的资格集合内选择；仍由本服务校验响应并持久化 Trace。
        Map<String, Object> result = runtime.post("/agent/query", map("requirement", requirement, "library_id", libraryId, "build_id", buildId, "eligible_tag_ids", eligible));
        if (!snapshotId.equals(result.get("snapshot_id")) || !buildId.equals(result.get("build_id")) || !bundle.get("store_type").equals(result.get("store_type")) || !java.util.Objects.equals(bundle.get("artifact_hash"), result.get("artifact_hash"))) throw new ServiceException("检索构建身份不一致");
        List<Map<String, Object>> candidates = (List<Map<String, Object>>) result.get("candidates");
        if (candidates == null) throw new ServiceException("检索响应缺少候选列表");
        for (Map<String, Object> c : candidates) if (!eligible.contains(Long.valueOf(String.valueOf(c.get("tag_id"))))) throw new ServiceException("检索响应包含资格外标签");
        String traceId = UUID.randomUUID().toString(); result.put("trace_id", traceId);
        TsRetrievalFeedback trace = new TsRetrievalFeedback();
        trace.setTraceId(traceId); trace.setSnapshotId(snapshotId); trace.setBuildId(buildId); trace.setUserId(SecurityUtils.getUserId());
        // 查询可能包含姓名/账号等原值，默认只留不可逆摘要，绝不将原文用于别名学习。
        trace.setQueryText("sha256:" + TsSnapshotCanonicalizer.sha256(requirement)); trace.setAction("TRACE");
        trace.setRankFeatures(json(result)); feedback.insert(trace);
        return result;
    }

    @SuppressWarnings("unchecked")
    public int feedback(TsRetrievalFeedback request) {
        if (request == null || !Arrays.asList("ACCEPT", "REPLACE", "REMOVE", "CLARIFY_PICKED", "REJECT_ALL").contains(request.getAction())) throw new ServiceException("反馈动作非法");
        TsRetrievalFeedback trace = feedback.selectTrace(request.getTraceId(), SecurityUtils.getUserId());
        if (trace == null) throw new ServiceException("追踪记录不存在或不属于当前用户");
        if ((request.getBuildId() != null && !request.getBuildId().equals(trace.getBuildId())) || (request.getSnapshotId() != null && !request.getSnapshotId().equals(trace.getSnapshotId()))) throw new ServiceException("反馈构建身份不一致");
        TsCatalogSnapshot snapshot = snapshots.selectById(trace.getSnapshotId());
        if (snapshot == null) throw new ServiceException("快照不存在");
        List<Long> eligible = catalog.eligibleTagIds(snapshot.getLibraryId(), trace.getSnapshotId());
        Set<Long> recommended = new HashSet<>();
        Map<String, Object> result = (Map<String, Object>) parse(trace.getRankFeatures(), Collections.emptyMap());
        for (Map<String, Object> c : (List<Map<String, Object>>) result.get("candidates")) recommended.add(Long.valueOf(String.valueOf(c.get("tag_id"))));
        if (request.getRecommendedTagId() != null && !recommended.contains(request.getRecommendedTagId())) throw new ServiceException("推荐标签不在原始 Trace 中");
        if (request.getFinalTagId() != null && !eligible.contains(request.getFinalTagId())) throw new ServiceException("最终标签不在当前资格集合");
        if (Arrays.asList("ACCEPT", "REPLACE", "CLARIFY_PICKED").contains(request.getAction()) && request.getFinalTagId() == null) throw new ServiceException("该反馈必须包含最终标签");
        TsRetrievalFeedback row = new TsRetrievalFeedback();
        row.setTraceId(trace.getTraceId()); row.setSnapshotId(trace.getSnapshotId()); row.setBuildId(trace.getBuildId()); row.setUserId(SecurityUtils.getUserId());
        row.setQueryText(trace.getQueryText()); row.setRecommendedTagId(request.getRecommendedTagId()); row.setFinalTagId(request.getFinalTagId()); row.setAction(request.getAction());
        return feedback.insert(row);
    }

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
