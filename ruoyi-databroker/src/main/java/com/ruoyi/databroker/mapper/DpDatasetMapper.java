package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataset;

public interface DpDatasetMapper {
    List<DpDataset> selectDatasetList(DpDataset dataset);
    DpDataset selectDatasetById(Long datasetId);
    DpDataset selectDatasetByCode(String datasetCode);
    int insertDataset(DpDataset dataset);
    int updateDataset(DpDataset dataset);
    int deleteDatasetById(Long datasetId);

    /** 统计某目录下的数据集数量（用于删除目录校验） */
    int countByCatalogId(Long catalogId);

    /** 统计关联该数据集且未删除的标签库数量（删除数据集前校验） */
    int countLibrariesByDatasetId(Long datasetId);

    /** 更新最新版本号（复制版本时递增） */
    int updateLatestVersionNo(DpDataset dataset);

    /** 更新默认在线版本ID（发布设默认/下线清默认，允许置 null） */
    int updateDefaultVersionId(Long datasetId, Long defaultVersionId);

    /** 移动数据集到其他目录（跨目录拖拽） */
    int moveDataset(DpDataset dataset);
}
