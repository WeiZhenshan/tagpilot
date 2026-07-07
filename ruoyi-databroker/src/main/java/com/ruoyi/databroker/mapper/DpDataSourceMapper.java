package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSource;

public interface DpDataSourceMapper {
    List<DpDataSource> selectDataSourceList(DpDataSource dataSource);
    DpDataSource selectDataSourceById(Long datasourceId);
    DpDataSource selectDataSourceByName(String sourceName);
    int insertDataSource(DpDataSource dataSource);
    int updateDataSource(DpDataSource dataSource);
    int deleteDataSourceById(Long datasourceId);
    int deleteDataSourceByIds(Long[] datasourceIds);
    int incrementUsageCount(Long datasourceId);

    /** 统计某目录下的数据源数量（用于删除目录校验） */
    int countByCatalogId(Long catalogId);

    /** 更新数据源排序（同目录内拖拽排序） */
    int updateDataSourceOrder(DpDataSource dataSource);

    /** 移动数据源到其他目录（跨目录拖拽 + 排序） */
    int moveDataSource(DpDataSource dataSource);
}
