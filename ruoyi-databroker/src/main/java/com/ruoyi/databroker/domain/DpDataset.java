package com.ruoyi.databroker.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

public class DpDataset extends BaseEntity {
    private static final long serialVersionUID = 1L;

    private Long datasetId;
    private Long catalogId;
    private String datasetCode;
    private String datasetName;
    private Long datasourceId;
    private Long defaultVersionId;
    private Integer latestVersionNo;
    private String ownerName;
    private String status;
    private String delFlag;
    private String datasourceName;  // transient，详情展示用

    // getters and setters
    public Long getDatasetId() { return datasetId; }
    public void setDatasetId(Long datasetId) { this.datasetId = datasetId; }
    public Long getCatalogId() { return catalogId; }
    public void setCatalogId(Long catalogId) { this.catalogId = catalogId; }
    public String getDatasetCode() { return datasetCode; }
    public void setDatasetCode(String datasetCode) { this.datasetCode = datasetCode; }
    public String getDatasetName() { return datasetName; }
    public void setDatasetName(String datasetName) { this.datasetName = datasetName; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
    public Long getDefaultVersionId() { return defaultVersionId; }
    public void setDefaultVersionId(Long defaultVersionId) { this.defaultVersionId = defaultVersionId; }
    public Integer getLatestVersionNo() { return latestVersionNo; }
    public void setLatestVersionNo(Integer latestVersionNo) { this.latestVersionNo = latestVersionNo; }
    public String getOwnerName() { return ownerName; }
    public void setOwnerName(String ownerName) { this.ownerName = ownerName; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getDelFlag() { return delFlag; }
    public void setDelFlag(String delFlag) { this.delFlag = delFlag; }
    public String getDatasourceName() { return datasourceName; }
    public void setDatasourceName(String datasourceName) { this.datasourceName = datasourceName; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("datasetId", getDatasetId())
            .append("datasetCode", getDatasetCode())
            .append("datasetName", getDatasetName())
            .append("datasourceId", getDatasourceId())
            .toString();
    }
}
