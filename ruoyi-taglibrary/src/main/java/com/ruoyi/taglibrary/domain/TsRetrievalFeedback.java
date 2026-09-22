package com.ruoyi.taglibrary.domain;

import com.ruoyi.common.core.domain.BaseEntity;

public class TsRetrievalFeedback extends BaseEntity {
    private static final long serialVersionUID = 1L;
    private Long feedbackId;
    public Long getFeedbackId() { return feedbackId; }
    public void setFeedbackId(Long value) { feedbackId = value; }
    private String traceId;
    public String getTraceId() { return traceId; }
    public void setTraceId(String value) { traceId = value; }
    private String snapshotId;
    public String getSnapshotId() { return snapshotId; }
    public void setSnapshotId(String value) { snapshotId = value; }
    private String buildId;
    public String getBuildId() { return buildId; }
    public void setBuildId(String value) { buildId = value; }
    private Long userId;
    public Long getUserId() { return userId; }
    public void setUserId(Long value) { userId = value; }
    private String queryText;
    public String getQueryText() { return queryText; }
    public void setQueryText(String value) { queryText = value; }
    private String requirementText;
    public String getRequirementText() { return requirementText; }
    public void setRequirementText(String value) { requirementText = value; }
    private Long recommendedTagId;
    public Long getRecommendedTagId() { return recommendedTagId; }
    public void setRecommendedTagId(Long value) { recommendedTagId = value; }
    private Long finalTagId;
    public Long getFinalTagId() { return finalTagId; }
    public void setFinalTagId(Long value) { finalTagId = value; }
    private String action;
    public String getAction() { return action; }
    public void setAction(String value) { action = value; }
    private String rankFeatures;
    public String getRankFeatures() { return rankFeatures; }
    public void setRankFeatures(String value) { rankFeatures = value; }
}
