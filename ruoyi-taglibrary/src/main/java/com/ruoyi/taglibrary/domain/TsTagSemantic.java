package com.ruoyi.taglibrary.domain;

import java.math.BigDecimal;
import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 标签语义 ts_tag_semantic（与 tl_tag 1:1）
 */
public class TsTagSemantic extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long tagId;
    private Long conceptId;
    private String familyKey;
    private String caliberVariant;
    private String semanticType;
    private String allowedOperators;
    private String defaultOperator;
    private String unit;
    private BigDecimal unitScale;
    /** 结构化口径 JSON 字符串 */
    private String caliberStruct;
    private String definitionLong;
    private String sensitivity;
    private Integer completenessScore;
    private String basisHash;
    private String source;
    private String reviewStatus;
    private Integer semanticVersion;
    private String reviewBy;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date reviewTime;
    private String sourceRef;
    /** 列表展示：所属库（联表，非本表列） */
    private Long libraryId;
    /** 列表展示：字段名（联表） */
    private String fieldName;
    /** 列表展示：标签名（联表） */
    private String tagName;

    public Long getTagId() { return tagId; }
    public void setTagId(Long tagId) { this.tagId = tagId; }
    public Long getConceptId() { return conceptId; }
    public void setConceptId(Long conceptId) { this.conceptId = conceptId; }
    public String getFamilyKey() { return familyKey; }
    public void setFamilyKey(String familyKey) { this.familyKey = familyKey; }
    public String getCaliberVariant() { return caliberVariant; }
    public void setCaliberVariant(String caliberVariant) { this.caliberVariant = caliberVariant; }
    public String getSemanticType() { return semanticType; }
    public void setSemanticType(String semanticType) { this.semanticType = semanticType; }
    public String getAllowedOperators() { return allowedOperators; }
    public void setAllowedOperators(String allowedOperators) { this.allowedOperators = allowedOperators; }
    public String getDefaultOperator() { return defaultOperator; }
    public void setDefaultOperator(String defaultOperator) { this.defaultOperator = defaultOperator; }
    public String getUnit() { return unit; }
    public void setUnit(String unit) { this.unit = unit; }
    public BigDecimal getUnitScale() { return unitScale; }
    public void setUnitScale(BigDecimal unitScale) { this.unitScale = unitScale; }
    public String getCaliberStruct() { return caliberStruct; }
    public void setCaliberStruct(String caliberStruct) { this.caliberStruct = caliberStruct; }
    public String getDefinitionLong() { return definitionLong; }
    public void setDefinitionLong(String definitionLong) { this.definitionLong = definitionLong; }
    public String getSensitivity() { return sensitivity; }
    public void setSensitivity(String sensitivity) { this.sensitivity = sensitivity; }
    public Integer getCompletenessScore() { return completenessScore; }
    public void setCompletenessScore(Integer completenessScore) { this.completenessScore = completenessScore; }
    public String getBasisHash() { return basisHash; }
    public void setBasisHash(String basisHash) { this.basisHash = basisHash; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
    public String getReviewStatus() { return reviewStatus; }
    public void setReviewStatus(String reviewStatus) { this.reviewStatus = reviewStatus; }
    public Integer getSemanticVersion() { return semanticVersion; }
    public void setSemanticVersion(Integer semanticVersion) { this.semanticVersion = semanticVersion; }
    public String getReviewBy() { return reviewBy; }
    public void setReviewBy(String reviewBy) { this.reviewBy = reviewBy; }
    public Date getReviewTime() { return reviewTime; }
    public void setReviewTime(Date reviewTime) { this.reviewTime = reviewTime; }
    public String getSourceRef() { return sourceRef; }
    public void setSourceRef(String sourceRef) { this.sourceRef = sourceRef; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getTagName() { return tagName; }
    public void setTagName(String tagName) { this.tagName = tagName; }
}
