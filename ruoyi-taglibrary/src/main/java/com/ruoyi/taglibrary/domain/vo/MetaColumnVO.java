package com.ruoyi.taglibrary.domain.vo;

import java.io.Serializable;

/**
 * 表字段元数据（information_schema.columns 查询结果）
 *
 * @author ruoyi
 */
public class MetaColumnVO implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 字段名 */
    private String columnName;

    /** 数据类型 */
    private String dataType;

    /** 字段注释 */
    private String columnComment;

    public String getColumnName() { return columnName; }
    public void setColumnName(String columnName) { this.columnName = columnName; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
    public String getColumnComment() { return columnComment; }
    public void setColumnComment(String columnComment) { this.columnComment = columnComment; }
}
