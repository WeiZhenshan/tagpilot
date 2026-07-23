package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDatasetField;

public interface DpDatasetFieldMapper {
    List<DpDatasetField> selectFieldsByVersionId(Long versionId);

    /** 按 version_id 全量重写（先删后插） */
    int insertFields(List<DpDatasetField> fields);
    int deleteFieldsByVersionId(Long versionId);
}
