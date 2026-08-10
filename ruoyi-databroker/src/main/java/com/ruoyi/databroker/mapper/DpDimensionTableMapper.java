package com.ruoyi.databroker.mapper;

import java.util.List;
import java.util.Map;
import com.ruoyi.databroker.domain.DpDimensionTable;

/**
 * 维表登记 Mapper
 *
 * @author ruoyi
 */
public interface DpDimensionTableMapper {

    /** 分页查询（过滤已删除，联 dp_datasource 回填数据源名称） */
    List<DpDimensionTable> selectDimensionList(DpDimensionTable query);

    /** 按ID查询（联 dp_datasource 回填数据源名称） */
    DpDimensionTable selectDimensionById(Long dimensionId);

    /** 按维表编码查询（含已删除记录，用于唯一性校验与恢复） */
    DpDimensionTable selectByCode(String dimensionCode);

    /** 按数据源+物理表查询（含已删除记录，用于唯一性校验与恢复） */
    DpDimensionTable selectBySource(Long datasourceId, Long sourceTableId);

    int insertDimension(DpDimensionTable dimension);

    /** 仅允许更新名称/备注/更新人/更新时间 */
    int updateDimension(DpDimensionTable dimension);

    /** 恢复已删除的登记记录（重新登记同数据源同表时复用，避免唯一键冲突） */
    int restoreDimension(DpDimensionTable dimension);

    int updateStatus(Long dimensionId, String status);

    /** 批量逻辑删除 */
    int deleteDimensionByIds(Long[] dimensionIds);

    /** 统计维表在标签库默认码表关系表 tl_tag_library_dimension 中的引用次数 */
    int countLibraryReferences(Long dimensionId);

    /** 可用数据连接下拉（正常且未删除的数据源） */
    List<Map<String, Object>> selectAvailableDatasources();

    /** 指定数据源下可登记的物理表（正常且未被登记的表） */
    List<Map<String, Object>> selectAvailableTables(Long datasourceId);
}
