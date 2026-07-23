package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDatasetVersion;

public interface DpDatasetVersionMapper {
    /** 版本列表（不含 definition_json） */
    List<DpDatasetVersion> selectVersionListByDatasetId(Long datasetId);
    DpDatasetVersion selectVersionById(Long versionId);

    /** 查询数据集的草稿版本（至多一个） */
    DpDatasetVersion selectDraftByDatasetId(Long datasetId);

    /** 统计数据集的草稿版本数量（复制版本前置校验） */
    int countDraftByDatasetId(Long datasetId);

    int insertVersion(DpDatasetVersion version);
    int updateVersion(DpDatasetVersion version);
}
