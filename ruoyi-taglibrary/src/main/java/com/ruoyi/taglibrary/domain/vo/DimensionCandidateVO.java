package com.ruoyi.taglibrary.domain.vo;

import java.io.Serializable;
import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;

/**
 * 默认码表候选维表（dp_dimension_table 联查结果，含已选/可选标记）
 *
 * @author ruoyi
 */
public class DimensionCandidateVO implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 维表ID */
    private Long dimensionId;

    /** 维表名称（中文业务名） */
    private String dimensionName;

    /** 维表名（平台唯一英文编码） */
    private String dimensionCode;

    /** 数据连接ID */
    private Long datasourceId;

    /** 数据源名称 */
    private String datasourceName;

    /** 原始物理表名 */
    private String sourceTableName;

    /** 状态（0启用 1停用） */
    private String status;

    /** 创建者 */
    private String createBy;

    /** 创建时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date createTime;

    /** 是否已在该标签库的默认码表集合中 */
    private Boolean selected;

    /** 是否与标签库数据源同源 */
    private Boolean sameSource;

    /** 是否可选（同源且启用） */
    private Boolean selectable;

    /** 不可选原因（可选时为 null） */
    private String disabledReason;

    public Long getDimensionId() { return dimensionId; }
    public void setDimensionId(Long dimensionId) { this.dimensionId = dimensionId; }
    public String getDimensionName() { return dimensionName; }
    public void setDimensionName(String dimensionName) { this.dimensionName = dimensionName; }
    public String getDimensionCode() { return dimensionCode; }
    public void setDimensionCode(String dimensionCode) { this.dimensionCode = dimensionCode; }
    public Long getDatasourceId() { return datasourceId; }
    public void setDatasourceId(Long datasourceId) { this.datasourceId = datasourceId; }
    public String getDatasourceName() { return datasourceName; }
    public void setDatasourceName(String datasourceName) { this.datasourceName = datasourceName; }
    public String getSourceTableName() { return sourceTableName; }
    public void setSourceTableName(String sourceTableName) { this.sourceTableName = sourceTableName; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getCreateBy() { return createBy; }
    public void setCreateBy(String createBy) { this.createBy = createBy; }
    public Date getCreateTime() { return createTime; }
    public void setCreateTime(Date createTime) { this.createTime = createTime; }
    public Boolean getSelected() { return selected; }
    public void setSelected(Boolean selected) { this.selected = selected; }
    public Boolean getSameSource() { return sameSource; }
    public void setSameSource(Boolean sameSource) { this.sameSource = sameSource; }
    public Boolean getSelectable() { return selectable; }
    public void setSelectable(Boolean selectable) { this.selectable = selectable; }
    public String getDisabledReason() { return disabledReason; }
    public void setDisabledReason(String disabledReason) { this.disabledReason = disabledReason; }
}
