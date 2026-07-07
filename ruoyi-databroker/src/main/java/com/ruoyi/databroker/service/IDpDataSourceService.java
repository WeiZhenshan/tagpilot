package com.ruoyi.databroker.service;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDataSourceLog;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.domain.dto.TreeNode;
import com.ruoyi.databroker.domain.vo.SyncResultVO;
import com.ruoyi.databroker.domain.vo.TestResultVO;

public interface IDpDataSourceService {
    // Tree
    List<TreeNode> buildTree();

    // CRUD
    DpDataSource selectDataSourceById(Long id);
    int insertDataSource(DpDataSource dataSource);
    int updateDataSource(DpDataSource dataSource);
    int deleteDataSourceByIds(Long[] ids);

    // Test connection
    TestResultVO testConnection(DpDataSource dataSource);

    // Sync metadata
    SyncResultVO syncMetadata(Long id);

    // Tables & Columns
    List<DpMetaTable> listTables(Long datasourceId, DpMetaTable query);
    List<DpMetaColumn> listColumns(Long tableId);

    // CN Name
    int updateTableCnName(Long tableId, String cnName);

    // Logs
    List<DpDataSourceLog> listLogs(Long datasourceId, DpDataSourceLog query);

    /** 更新数据源排序/所属目录（拖拽排序用） */
    int updateDataSourceOrder(DpDataSource dataSource);
}
