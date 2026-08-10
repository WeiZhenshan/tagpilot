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

    /** 源字段中文注释（标签中文名来源） */
    private String fieldComment;

    /** 源字段是否主键（0否 1是，客户号识别） */
    private String isPk;

    /** 数据类型 */
    private String dataType;

    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getFieldComment() { return fieldComment; }
    public void setFieldComment(String fieldComment) { this.fieldComment = fieldComment; }
    public String getIsPk() { return isPk; }
    public void setIsPk(String isPk) { this.isPk = isPk; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
}
