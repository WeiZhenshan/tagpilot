package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpMetaTable;

public interface DpMetaTableMapper {
    List<DpMetaTable> selectTableList(DpMetaTable table);
    DpMetaTable selectTableById(Long tableId);
    DpMetaTable selectTableByDsAndName(Long datasourceId, String objectName);
    int insertTable(DpMetaTable table);
    int updateTable(DpMetaTable table);
    int updateTableCnName(Long tableId, String cnName);
    int markTableInvalid(Long datasourceId, String syncBatchNo);
}
