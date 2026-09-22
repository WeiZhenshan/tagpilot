package com.ruoyi.taglibrary.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 业务模糊词典 ts_business_term
 */
public class TsBusinessTerm extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long termId;
    private String term;
    private String termNorm;
    private String termType;
    private String options;
    private String defaultPolicy;
    private String applicableSemanticTypes;
    private String tagObject;
    private String reviewStatus;
    private String reviewBy;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date reviewTime;
    private String sourceRef;

    public Long getTermId() { return termId; }
    public void setTermId(Long termId) { this.termId = termId; }
    public String getTerm() { return term; }
    public void setTerm(String term) { this.term = term; }
    public String getTermNorm() { return termNorm; }
    public void setTermNorm(String termNorm) { this.termNorm = termNorm; }
    public String getTermType() { return termType; }
    public void setTermType(String termType) { this.termType = termType; }
    public String getOptions() { return options; }
    public void setOptions(String options) { this.options = options; }
    public String getDefaultPolicy() { return defaultPolicy; }
    public void setDefaultPolicy(String defaultPolicy) { this.defaultPolicy = defaultPolicy; }
    public String getApplicableSemanticTypes() { return applicableSemanticTypes; }
    public void setApplicableSemanticTypes(String applicableSemanticTypes) { this.applicableSemanticTypes = applicableSemanticTypes; }
    public String getTagObject() { return tagObject; }
    public void setTagObject(String tagObject) { this.tagObject = tagObject; }
    public String getReviewStatus() { return reviewStatus; }
    public void setReviewStatus(String reviewStatus) { this.reviewStatus = reviewStatus; }
    public String getReviewBy() { return reviewBy; }
    public void setReviewBy(String reviewBy) { this.reviewBy = reviewBy; }
    public Date getReviewTime() { return reviewTime; }
    public void setReviewTime(Date reviewTime) { this.reviewTime = reviewTime; }
    public String getSourceRef() { return sourceRef; }
    public void setSourceRef(String sourceRef) { this.sourceRef = sourceRef; }
}
