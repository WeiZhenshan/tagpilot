package com.ruoyi.databroker.domain.vo;

import java.io.Serializable;

/**
 * 在线版本解析结果（默认在线版本优先，否则回退版本号最大的 ONLINE 版本）
 *
 * @author ruoyi
 */
public class DpResolvedVersion implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 数据集ID */
    private Long datasetId;

    /** 解析出的版本ID */
    private Long versionId;

    /** 版本号 */
    private Integer versionNo;

    /** 版本名称 */
    private String versionName;

    /** 是否数据集默认版本 */
    private Boolean isDefault;

    /** 选择原因文案（默认在线版本 / 默认版本不可用，回退至最大版本号在线版本） */
    private String reason;

    public Long getDatasetId() { return datasetId; }
    public void setDatasetId(Long datasetId) { this.datasetId = datasetId; }
    public Long getVersionId() { return versionId; }
    public void setVersionId(Long versionId) { this.versionId = versionId; }
    public Integer getVersionNo() { return versionNo; }
    public void setVersionNo(Integer versionNo) { this.versionNo = versionNo; }
    public String getVersionName() { return versionName; }
    public void setVersionName(String versionName) { this.versionName = versionName; }
    public Boolean getIsDefault() { return isDefault; }
    public void setIsDefault(Boolean isDefault) { this.isDefault = isDefault; }
    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }
}
