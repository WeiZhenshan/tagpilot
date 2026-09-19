package com.ruoyi.taglibrary.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;

public class TsIndexBuild extends BaseEntity {
    private static final long serialVersionUID = 1L;
    private String embeddingModelHash;
    public String getEmbeddingModelHash() { return embeddingModelHash; }
    public void setEmbeddingModelHash(String value) { embeddingModelHash = value; }
    private String rerankerModel;
    public String getRerankerModel() { return rerankerModel; }
    public void setRerankerModel(String value) { rerankerModel = value; }
    private String rerankerModelHash;
    public String getRerankerModelHash() { return rerankerModelHash; }
    public void setRerankerModelHash(String value) { rerankerModelHash = value; }
    private String retrievalConfigHash;
    public String getRetrievalConfigHash() { return retrievalConfigHash; }
    public void setRetrievalConfigHash(String value) { retrievalConfigHash = value; }
    private String buildId;
    private String snapshotId;
    private String docTemplateVersion;
    private String analyzerVersion;
    private String embeddingModel;
    private Integer embeddingDim;
    private String storeType;
    private String milvusCollection;
    private String milvusAlias;
    private String artifactUri;
    private String artifactHash;
    private Integer docCount;
    private String docIdHash;
    private String status;
    private String evalSummary;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date buildTime;
    private Long buildDurationMs;

    public String getBuildId() { return buildId; }
    public void setBuildId(String buildId) { this.buildId = buildId; }
    public String getSnapshotId() { return snapshotId; }
    public void setSnapshotId(String snapshotId) { this.snapshotId = snapshotId; }
    public String getDocTemplateVersion() { return docTemplateVersion; }
    public void setDocTemplateVersion(String docTemplateVersion) { this.docTemplateVersion = docTemplateVersion; }
    public String getAnalyzerVersion() { return analyzerVersion; }
    public void setAnalyzerVersion(String analyzerVersion) { this.analyzerVersion = analyzerVersion; }
    public String getEmbeddingModel() { return embeddingModel; }
    public void setEmbeddingModel(String embeddingModel) { this.embeddingModel = embeddingModel; }
    public Integer getEmbeddingDim() { return embeddingDim; }
    public void setEmbeddingDim(Integer embeddingDim) { this.embeddingDim = embeddingDim; }
    public String getStoreType() { return storeType; }
    public void setStoreType(String storeType) { this.storeType = storeType; }
    public String getMilvusCollection() { return milvusCollection; }
    public void setMilvusCollection(String milvusCollection) { this.milvusCollection = milvusCollection; }
    public String getMilvusAlias() { return milvusAlias; }
    public void setMilvusAlias(String milvusAlias) { this.milvusAlias = milvusAlias; }
    public String getArtifactUri() { return artifactUri; }
    public void setArtifactUri(String artifactUri) { this.artifactUri = artifactUri; }
    public String getArtifactHash() { return artifactHash; }
    public void setArtifactHash(String artifactHash) { this.artifactHash = artifactHash; }
    public Integer getDocCount() { return docCount; }
    public void setDocCount(Integer docCount) { this.docCount = docCount; }
    public String getDocIdHash() { return docIdHash; }
    public void setDocIdHash(String docIdHash) { this.docIdHash = docIdHash; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getEvalSummary() { return evalSummary; }
    public void setEvalSummary(String evalSummary) { this.evalSummary = evalSummary; }
    public Date getBuildTime() { return buildTime; }
    public void setBuildTime(Date buildTime) { this.buildTime = buildTime; }
    public Long getBuildDurationMs() { return buildDurationMs; }
    public void setBuildDurationMs(Long buildDurationMs) { this.buildDurationMs = buildDurationMs; }
}
