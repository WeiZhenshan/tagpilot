package com.ruoyi.taglibrary.service;

import java.util.List;
import com.ruoyi.taglibrary.domain.vo.DimensionCandidateVO;
import com.ruoyi.taglibrary.domain.vo.DimensionLibraryVO;

/**
 * 标签库默认码表（维表关联）Service接口
 *
 * @author ruoyi
 */
public interface ITlTagLibraryDimensionService {

    /** 候选维表分页（补充 selectable/disabledReason） */
    List<DimensionCandidateVO> selectCandidates(Long libraryId, String dimensionName);

    /** 该库全部已关联维表ID（跨分页回显用） */
    List<Long> selectSelectedDimensionIds(Long libraryId);

    /**
     * 多选覆盖保存默认码表（空数组=清空）
     * 校验：维表存在/未删除/启用/与标签库同源，多张维表时做码值冲突校验
     *
     * @return 保存的关系条数
     */
    int saveDimensions(Long libraryId, List<Long> dimensionIds);

    /** 引用了某维表的标签库列表（维表详情抽屉用） */
    List<DimensionLibraryVO> selectLibrariesByDimensionId(Long dimensionId);
}
