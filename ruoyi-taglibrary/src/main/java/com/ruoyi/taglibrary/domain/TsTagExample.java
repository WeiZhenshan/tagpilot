package com.ruoyi.taglibrary.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 正反例 ts_tag_example
 */
public class TsTagExample extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long exampleId;
    private Long tagId;
    private String exampleType;
    private String utterance;
    private String expectedCondition;
    private String source;
    private String reviewStatus;
    private String reviewBy;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date reviewTime;
    private String sourceRef;

    public Long getExampleId() { return exampleId; }
    public void setExampleId(Long exampleId) { this.exampleId = exampleId; }
    public Long getTagId() { return tagId; }
    public void setTagId(Long tagId) { this.tagId = tagId; }
    public String getExampleType() { return exampleType; }
    public void setExampleType(String exampleType) { this.exampleType = exampleType; }
    public String getUtterance() { return utterance; }
    public void setUtterance(String utterance) { this.utterance = utterance; }
    public String getExpectedCondition() { return expectedCondition; }
    public void setExpectedCondition(String expectedCondition) { this.expectedCondition = expectedCondition; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
    public String getReviewStatus() { return reviewStatus; }
    public void setReviewStatus(String reviewStatus) { this.reviewStatus = reviewStatus; }
    public String getReviewBy() { return reviewBy; }
    public void setReviewBy(String reviewBy) { this.reviewBy = reviewBy; }
    public Date getReviewTime() { return reviewTime; }
    public void setReviewTime(Date reviewTime) { this.reviewTime = reviewTime; }
    public String getSourceRef() { return sourceRef; }
    public void setSourceRef(String sourceRef) { this.sourceRef = sourceRef; }
}
