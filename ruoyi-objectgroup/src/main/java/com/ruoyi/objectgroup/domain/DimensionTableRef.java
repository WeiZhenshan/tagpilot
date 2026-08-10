package com.ruoyi.objectgroup.domain;

/**
 * 维表登记引用（跨表查询 dp_dimension_table 的轻量结果，用于码值选项查询）
 */
public class DimensionTableRef {

    /** 维表ID */
    private Long dimensionId;

    /** 维表名称 */
    private String dimensionName;

    /** 物理表名（外部数据源中的维表） */
    private String sourceTableName;

    /** 所属数据源ID */
    private Long datasourceId;

    public Long getDimensionId() { return dimensionId; }
    public void setDimensionId(Long dimensionId) { this.dimensionId = dimensionId; }
    public String getDimensionName() { return dimensionName; }
    public void setDimensionName(String dimensionName) { this.dimensionName = dimensionName; }
    public String getSourceTableName() { return sourceTableName; }
    public void setSourceTableName(String sourceTableName) { this.sourceTableName = sourceTableName; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
}
