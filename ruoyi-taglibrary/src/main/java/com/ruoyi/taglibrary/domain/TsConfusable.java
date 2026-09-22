package com.ruoyi.taglibrary.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 易混淆对 ts_confusable
 */
public class TsConfusable extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long pairId;
    private Long tagIdA;
    private Long tagIdB;
    private String confusionType;
    private String differenceNote;
    private String disambiguationHint;
    private String source;
    private String reviewStatus;
    private String reviewBy;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date reviewTime;
    private String sourceRef;

    public Long getPairId() { return pairId; }
    public void setPairId(Long pairId) { this.pairId = pairId; }
    public Long getTagIdA() { return tagIdA; }
    public void setTagIdA(Long tagIdA) { this.tagIdA = tagIdA; }
    public Long getTagIdB() { return tagIdB; }
    public void setTagIdB(Long tagIdB) { this.tagIdB = tagIdB; }
    public String getConfusionType() { return confusionType; }
    public void setConfusionType(String confusionType) { this.confusionType = confusionType; }
    public String getDifferenceNote() { return differenceNote; }
    public void setDifferenceNote(String differenceNote) { this.differenceNote = differenceNote; }
    public String getDisambiguationHint() { return disambiguationHint; }
    public void setDisambiguationHint(String disambiguationHint) { this.disambiguationHint = disambiguationHint; }
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
