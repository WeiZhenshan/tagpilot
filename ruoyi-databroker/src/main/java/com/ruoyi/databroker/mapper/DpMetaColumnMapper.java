package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpMetaColumn;

public interface DpMetaColumnMapper {
    List<DpMetaColumn> selectColumnList(DpMetaColumn column);
    List<DpMetaColumn> selectColumnsByTableId(Long tableId);
    DpMetaColumn selectColumnById(Long columnId);
    DpMetaColumn selectColumnByTableAndName(Long tableId, String columnName);
    int insertColumn(DpMetaColumn column);
    int updateColumn(DpMetaColumn column);
    int deleteColumnsByTableId(Long tableId);
    int deleteOrphanColumns(Long datasourceId, String syncBatchNo);
}
