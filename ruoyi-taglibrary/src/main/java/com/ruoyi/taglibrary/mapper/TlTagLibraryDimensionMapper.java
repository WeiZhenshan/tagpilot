package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.databroker.domain.DpDimensionTable;
import com.ruoyi.taglibrary.domain.TlTagLibraryDimension;
import com.ruoyi.taglibrary.domain.vo.DimensionCandidateVO;
import com.ruoyi.taglibrary.domain.vo.DimensionLibraryVO;

/**
 * 标签库默认码表关系 Mapper
 *
 * @author ruoyi
 */
public interface TlTagLibraryDimensionMapper {

    /** 该库全部默认码表关系（按 order_num/relation_id 排序） */
    List<TlTagLibraryDimension> selectByLibraryId(Long libraryId);

    /** 该库全部已关联维表ID（跨分页回显用） */
    List<Long> selectDimensionIdsByLibraryId(Long libraryId);

    /** 清空该库全部默认码表关系 */
    int deleteByLibraryId(Long libraryId);

    /** 批量插入关系记录 */
    int batchInsert(@Param("list") List<TlTagLibraryDimension> list);

    /** 该库默认码表关系数量 */
    int countByLibraryId(Long libraryId);

    /** 解析标签库的数据源ID：libraryId → tl_tag_library.dataset_id → dp_dataset.datasource_id */
    Long selectLibraryDatasourceId(Long libraryId);

    /**
     * 候选维表分页（全部已登记维表，含非同源/停用，由前端禁用复选框）
     * selected=是否已关联，sameSource=是否与标签库数据源同源
     */
    List<DimensionCandidateVO> selectCandidates(@Param("libraryId") Long libraryId,
                                                @Param("libraryDatasourceId") Long libraryDatasourceId,
                                                @Param("dimensionName") String dimensionName);

    /** 引用了某维表的标签库列表（维表详情抽屉用） */
    List<DimensionLibraryVO> selectLibrariesByDimensionId(Long dimensionId);

    /** 按ID批量查维表登记记录（保存前校验与码值冲突检查用） */
    List<DpDimensionTable> selectDimensionsForConflictCheck(@Param("dimensionIds") List<Long> dimensionIds);
}
