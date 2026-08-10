package com.ruoyi.objectgroup.service;

import java.util.List;
import java.util.Map;

public interface IDimensionCodeOptionService {

    /**
     * 查询标签的码值选项（从标签库默认码表对应的物理维表实时读取）
     *
     * @param libraryId 标签库ID
     * @param fieldName 标签字段名（维表 tag_name_en 列）
     * @return 码值选项列表（code/codeDefinition/tagName/orderNum/lastUpdateTime/dimensionId）
     */
    List<Map<String, Object>> listCodeOptions(Long libraryId, String fieldName);
}
