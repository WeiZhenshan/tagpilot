package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDatasetField;
import com.ruoyi.databroker.domain.vo.DpResolvedField;

public interface DpDatasetFieldMapper {
    List<DpDatasetField> selectFieldsByVersionId(Long versionId);

    /** 指定版本启用字段（联查来源表/列快照与数据集数据源，按 order_num 排序） */
    List<DpResolvedField> selectEnabledResolvedFields(Long versionId);

    /** 按 version_id 全量重写（先删后插） */
    int insertFields(List<DpDatasetField> fields);
    int deleteFieldsByVersionId(Long versionId);
}
