package com.ruoyi.taglibrary.domain.vo;

import java.io.Serializable;

/**
 * 数据集启用输出字段（dp_dataset_field 查询结果，字段快照来源）
 *
 * @author ruoyi
 */
public class DatasetFieldVO implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 输出字段别名 */
    private String fieldName;

    /** 数据类型 */
    private String dataType;

    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
}
