package com.ruoyi.databroker.domain.vo;

import java.io.Serializable;

/**
 * 数据集版本启用字段解析结果（含来源物理表/列快照信息，供来源指纹与快照使用）
 *
 * @author ruoyi
 */
public class DpResolvedField implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 字段ID（dp_dataset_field.field_id） */
    private Long fieldId;

    /** 输出字段别名 */
    private String fieldAlias;

    /** 来源物理字段名（建版时快照） */
    private String fieldName;

    /** 数据类型 */
    private String dataType;

    /** 是否对象键（dp_dataset_field.is_object_key：0否 1是） */
    private String isObjectKey;

    /** 来源列是否主键（dp_meta_column.is_pk：0否 1是） */
    private String isPk;

    /** 来源列中文注释 */
    private String columnComment;

    /** 来源表元数据ID */
    private Long sourceTableId;

    /** 来源字段元数据ID */
    private Long sourceColumnId;

    /** 来源物理表名（dp_meta_table.object_name） */
    private String tableName;

    /** 数据集所属数据源ID */
    private Long datasourceId;

    public Long getFieldId() { return fieldId; }
    public void setFieldId(Long fieldId) { this.fieldId = fieldId; }
    public String getFieldAlias() { return fieldAlias; }
    public void setFieldAlias(String fieldAlias) { this.fieldAlias = fieldAlias; }
    public String getFieldName() { return fieldName; }
    public void setFieldName(String fieldName) { this.fieldName = fieldName; }
    public String getDataType() { return dataType; }
    public void setDataType(String dataType) { this.dataType = dataType; }
    public String getIsObjectKey() { return isObjectKey; }
    public void setIsObjectKey(String isObjectKey) { this.isObjectKey = isObjectKey; }
    public String getIsPk() { return isPk; }
    public void setIsPk(String isPk) { this.isPk = isPk; }
    public String getColumnComment() { return columnComment; }
    public void setColumnComment(String columnComment) { this.columnComment = columnComment; }
    public Long getSourceTableId() { return sourceTableId; }
    public void setSourceTableId(Long sourceTableId) { this.sourceTableId = sourceTableId; }
    public Long getSourceColumnId() { return sourceColumnId; }
    public void setSourceColumnId(Long sourceColumnId) { this.sourceColumnId = sourceColumnId; }
    public String getTableName() { return tableName; }
    public void setTableName(String tableName) { this.tableName = tableName; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
}
