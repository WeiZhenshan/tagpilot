package com.ruoyi.databroker.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 维表登记表对象 dp_dimension_table
 * 只登记外部物理维表的元数据，不存储码值
 *
 * @author ruoyi
 */
public class DpDimensionTable extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 维表ID */
    private Long dimensionId;

    /** 维表名称（中文业务名） */
    private String dimensionName;

    /** 维表名（平台唯一英文编码） */
    private String dimensionCode;

    /** 数据连接ID（dp_datasource.datasource_id） */
    private Long datasourceId;

    /** 原始物理表ID（dp_meta_table.table_id） */
    private Long sourceTableId;

    /** 原始表名（登记时物理表名快照） */
    private String sourceTableName;

    /** 状态（0启用 1停用） */
    private String status;

    /** 删除标志（0存在 2删除） */
    private String delFlag;

    /** 数据源名称（联表回填，非表字段） */
    private String datasourceName;

    public Long getDimensionId() { return dimensionId; }
    public void setDimensionId(Long dimensionId) { this.dimensionId = dimensionId; }
    public String getDimensionName() { return dimensionName; }
    public void setDimensionName(String dimensionName) { this.dimensionName = dimensionName; }
    public String getDimensionCode() { return dimensionCode; }
    public void setDimensionCode(String dimensionCode) { this.dimensionCode = dimensionCode; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
    public Long getSourceTableId() { return sourceTableId; }
    public void setSourceTableId(Long sourceTableId) { this.sourceTableId = sourceTableId; }
    public String getSourceTableName() { return sourceTableName; }
    public void setSourceTableName(String sourceTableName) { this.sourceTableName = sourceTableName; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getDelFlag() { return delFlag; }
    public void setDelFlag(String delFlag) { this.delFlag = delFlag; }
    public String getDatasourceName() { return datasourceName; }
    public void setDatasourceName(String datasourceName) { this.datasourceName = datasourceName; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("dimensionId", getDimensionId())
            .append("dimensionName", getDimensionName())
            .append("dimensionCode", getDimensionCode())
            .append("datasourceId", getDatasourceId())
            .append("sourceTableId", getSourceTableId())
            .append("sourceTableName", getSourceTableName())
            .append("status", getStatus())
            .toString();
    }
}
