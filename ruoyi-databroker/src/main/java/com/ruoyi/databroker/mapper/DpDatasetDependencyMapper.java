package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDatasetDependency;

public interface DpDatasetDependencyMapper {
    List<DpDatasetDependency> selectDependenciesByVersionId(Long versionId);

    /** 按 version_id 全量重写（先删后插） */
    int insertDependencies(List<DpDatasetDependency> dependencies);
    int deleteDependenciesByVersionId(Long versionId);
}
