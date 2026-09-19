package com.ruoyi.taglibrary.domain;
import java.util.Date;
import com.ruoyi.common.core.domain.BaseEntity;
/** 聚合画像，不存客户原值。 */
public class TsTagProfile extends BaseEntity {
    private Long tagId;
    private Date profileDate;
    private Long rowCount;
    private java.math.BigDecimal nullRate;
    private Integer distinctCount;
    private java.math.BigDecimal minVal, maxVal, p50, p90, p99;
    private String topValues;
    private Long sampleSize, sourceVersionId;
    private Integer sampled;
    private String sourceFingerprint;
    public Long getTagId() { return tagId; } public void setTagId(Long v) { tagId=v; }
    public Date getProfileDate() { return profileDate; } public void setProfileDate(Date v) { profileDate=v; }
    public Long getRowCount() { return rowCount; } public void setRowCount(Long v) { rowCount=v; }
    public java.math.BigDecimal getNullRate() { return nullRate; } public void setNullRate(java.math.BigDecimal v) { nullRate=v; }
    public Integer getDistinctCount() { return distinctCount; } public void setDistinctCount(Integer v) { distinctCount=v; }
    public java.math.BigDecimal getMinVal() { return minVal; } public void setMinVal(java.math.BigDecimal v) { minVal=v; }
    public java.math.BigDecimal getMaxVal() { return maxVal; } public void setMaxVal(java.math.BigDecimal v) { maxVal=v; }
    public java.math.BigDecimal getP50() { return p50; } public void setP50(java.math.BigDecimal v) { p50=v; }
    public java.math.BigDecimal getP90() { return p90; } public void setP90(java.math.BigDecimal v) { p90=v; }
    public java.math.BigDecimal getP99() { return p99; } public void setP99(java.math.BigDecimal v) { p99=v; }
    public String getTopValues() { return topValues; } public void setTopValues(String v) { topValues=v; }
    public Long getSampleSize() { return sampleSize; } public void setSampleSize(Long v) { sampleSize=v; }
    public Long getSourceVersionId() { return sourceVersionId; } public void setSourceVersionId(Long v) { sourceVersionId=v; }
    public Integer getSampled() { return sampled; } public void setSampled(Integer v) { sampled=v; }
    public String getSourceFingerprint() { return sourceFingerprint; } public void setSourceFingerprint(String v) { sourceFingerprint=v; }
}
