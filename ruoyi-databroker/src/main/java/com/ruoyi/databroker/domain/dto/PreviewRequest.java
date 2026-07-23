package com.ruoyi.databroker.domain.dto;

/**
 * 数据预览请求体：{versionId}
 */
public class PreviewRequest {
    private Long versionId;

    public Long getVersionId() { return versionId; }
    public void setVersionId(Long versionId) { this.versionId = versionId; }
}
