package com.ruoyi.taglibrary.domain;

import java.math.BigDecimal;
import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 码值语义 ts_code_value_semantic
 */
public class TsCodeValueSemantic extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long tagId;
    private String code;
    private Integer rankNo;
    private BigDecimal lowerBound;
    private BigDecimal upperBound;
    private Integer lowerInclusive;
    private Integer upperInclusive;
    private String boundUnit;
    private Long parentTagId;
    private String parentCode;
    private Integer levelNo;
    private Integer isUnknownBucket;
    private String basisHash;
    private String source;
    private String reviewStatus;
    private String reviewBy;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date reviewTime;
    private String sourceRef;

    public Long getTagId() { return tagId; }
    public void setTagId(Long tagId) { this.tagId = tagId; }
    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }
    public Integer getRankNo() { return rankNo; }
    public void setRankNo(Integer rankNo) { this.rankNo = rankNo; }
    public BigDecimal getLowerBound() { return lowerBound; }
    public void setLowerBound(BigDecimal lowerBound) { this.lowerBound = lowerBound; }
    public BigDecimal getUpperBound() { return upperBound; }
    public void setUpperBound(BigDecimal upperBound) { this.upperBound = upperBound; }
    public Integer getLowerInclusive() { return lowerInclusive; }
    public void setLowerInclusive(Integer lowerInclusive) { this.lowerInclusive = lowerInclusive; }
    public Integer getUpperInclusive() { return upperInclusive; }
    public void setUpperInclusive(Integer upperInclusive) { this.upperInclusive = upperInclusive; }
    public String getBoundUnit() { return boundUnit; }
    public void setBoundUnit(String boundUnit) { this.boundUnit = boundUnit; }
    public Long getParentTagId() { return parentTagId; }
    public void setParentTagId(Long parentTagId) { this.parentTagId = parentTagId; }
    public String getParentCode() { return parentCode; }
    public void setParentCode(String parentCode) { this.parentCode = parentCode; }
    public Integer getLevelNo() { return levelNo; }
    public void setLevelNo(Integer levelNo) { this.levelNo = levelNo; }
    public Integer getIsUnknownBucket() { return isUnknownBucket; }
    public void setIsUnknownBucket(Integer isUnknownBucket) { this.isUnknownBucket = isUnknownBucket; }
    public String getBasisHash() { return basisHash; }
    public void setBasisHash(String basisHash) { this.basisHash = basisHash; }
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
