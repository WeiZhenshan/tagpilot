package com.ruoyi.objectgroup.mapper;

import org.apache.ibatis.annotations.Param;

/**
 * 对象群扩展查询：宽表定位与字段映射（跨库查询数据代理元数据表）
 */
public interface TlObjectGroupExtMapper {

    /** 版本定义 JSON（含 tableId） */
    String selectVersionDefinitionJson(@Param("versionId") Long versionId);

    /** 宽表物理表名 */
    String selectTableObjectName(@Param("tableId") Long tableId);

    /** 字段别名 → 物理列名（无则 null） */
    String selectColumnNameByAlias(@Param("versionId") Long versionId, @Param("fieldAlias") String fieldAlias);

    /** 客户号物理列名（is_object_key 回退查询） */
    String selectObjectKeyColumn(@Param("versionId") Long versionId);

    /** 标签库关联的数据集ID */
    Long selectDatasetIdByLibrary(@Param("libraryId") Long libraryId);

    /** 数据集所属数据源（含连接信息） */
    com.ruoyi.databroker.domain.DpDataSource selectDataSourceByDataset(@Param("datasetId") Long datasetId);

    /** 标签中文名 */
    String selectTagNameByField(@Param("libraryId") Long libraryId, @Param("fieldName") String fieldName);

    /** 单个标签的状态快照（发布状态 + 来源状态 + 类型，无则 null） */
    com.ruoyi.objectgroup.domain.TagStatusRef selectTagRefByField(@Param("libraryId") Long libraryId, @Param("fieldName") String fieldName);

    /** 标签库全部未删除标签的状态快照（对象群规则统一校验用） */
    java.util.List<com.ruoyi.objectgroup.domain.TagStatusRef> selectTagRefsByLibrary(@Param("libraryId") Long libraryId);

    /** 标签库已关联、启用、未删除且与标签库数据集同源的维表列表 */
    java.util.List<com.ruoyi.objectgroup.domain.DimensionTableRef> selectEnabledDimensionsByLibrary(@Param("libraryId") Long libraryId);
}
