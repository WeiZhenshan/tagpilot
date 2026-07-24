package com.ruoyi.taglibrary.domain.vo;

import java.io.Serializable;

/**
 * 已上线数据集（dp_dataset 联查结果，新建弹窗选用）
 *
 * @author ruoyi
 */
public class DatasetVO implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 数据集ID */
    private Long datasetId;

    /** 数据集编码 */
    private String datasetCode;

    /** 数据集名称 */
    private String datasetName;

    public Long getDatasetId() { return datasetId; }
    public void setDatasetId(Long datasetId) { this.datasetId = datasetId; }
    public String getDatasetCode() { return datasetCode; }
    public void setDatasetCode(String datasetCode) { this.datasetCode = datasetCode; }
    public String getDatasetName() { return datasetName; }
    public void setDatasetName(String datasetName) { this.datasetName = datasetName; }
}
