package com.ruoyi.databroker.service.impl;

import java.sql.Connection;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import com.alibaba.fastjson2.JSON;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;
import com.ruoyi.databroker.domain.DpDataSourceLog;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.domain.dto.TreeNode;
import com.ruoyi.databroker.domain.vo.SyncResultVO;
import com.ruoyi.databroker.domain.vo.TestResultVO;
import com.ruoyi.databroker.mapper.DpDataSourceCatalogMapper;
import com.ruoyi.databroker.mapper.DpDataSourceLogMapper;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.mapper.DpMetaColumnMapper;
import com.ruoyi.databroker.mapper.DpMetaTableMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.metadata.MetadataColumn;
import com.ruoyi.databroker.metadata.MetadataSyncResult;
import com.ruoyi.databroker.metadata.MetadataTable;
import com.ruoyi.databroker.metadata.MySqlMetadataCollector;
import com.ruoyi.databroker.service.IDpDataSourceService;

@Service
public class DpDataSourceServiceImpl implements IDpDataSourceService {

    @Autowired
    private DpDataSourceMapper dataSourceMapper;
    @Autowired
    private DpDataSourceCatalogMapper catalogMapper;
    @Autowired
    private DpMetaTableMapper tableMapper;
    @Autowired
    private DpMetaColumnMapper columnMapper;
    @Autowired
    private DpDataSourceLogMapper logMapper;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private DpDataSourceServiceImpl self;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private MySqlMetadataCollector metadataCollector;

    @Override
    public List<TreeNode> buildTree() {
        // Load catalogs and build a map keyed by "cat_<id>" for O(1) lookup
        List<DpDataSourceCatalog> catalogs = catalogMapper.selectCatalogList(new DpDataSourceCatalog());
        // 保留 SQL 的 order_num 顺序，避免 HashMap 遍历导致目录刷新后随机跳位
        Map<String, TreeNode> catalogNodeMap = new LinkedHashMap<>();
        for (DpDataSourceCatalog cat : catalogs) {
            TreeNode node = new TreeNode();
            node.setId("cat_" + cat.getCatalogId());
            node.setParentId(cat.getParentId() != null && cat.getParentId() != 0L
                ? "cat_" + cat.getParentId() : "0");
            node.setLabel(cat.getCatalogName());
            node.setNodeType("catalog");
            node.setCatalogId(cat.getCatalogId());
            node.setOrderNum(cat.getOrderNum());
            node.setStatus(cat.getStatus());
            node.setChildren(new ArrayList<>());
            catalogNodeMap.put(node.getId(), node);
        }

        // Build nested catalog tree: attach each catalog to its parent (if any)
        List<TreeNode> tree = new ArrayList<>();
        for (TreeNode catNode : catalogNodeMap.values()) {
            TreeNode parent = catalogNodeMap.get(catNode.getParentId());
            if (parent != null) {
                parent.getChildren().add(catNode);
            } else {
                tree.add(catNode); // root catalog (parentId = 0)
            }
        }

        // Load datasources and attach to their catalog leaf
        List<DpDataSource> sources = dataSourceMapper.selectDataSourceList(new DpDataSource());
        for (DpDataSource ds : sources) {
            TreeNode node = new TreeNode();
            node.setId("ds_" + ds.getDatasourceId());
            node.setParentId("cat_" + ds.getCatalogId());
            node.setLabel(ds.getSourceName());
            node.setNodeType("datasource");
            node.setDatasourceId(ds.getDatasourceId());
            node.setCatalogId(ds.getCatalogId());
            node.setOrderNum(ds.getOrderNum());
            node.setSourceType(ds.getSourceType());
            node.setStatus(ds.getStatus());
            node.setChildren(new ArrayList<>());

            TreeNode parent = catalogNodeMap.get(node.getParentId());
            if (parent != null) {
                parent.getChildren().add(node);
            }
        }

        return tree;
    }

    @Override
    public DpDataSource selectDataSourceById(Long id) {
        DpDataSource ds = dataSourceMapper.selectDataSourceById(id);
        if (ds != null) {
            ds.setPassword("******");
            ds.setPasswordCipher(null);
        }
        return ds;
    }

    @Override
    @Transactional
    public int insertDataSource(DpDataSource dataSource) {
        // Encrypt password
        if (dataSource.getPassword() != null && !dataSource.getPassword().isEmpty()
                && !"******".equals(dataSource.getPassword())) {
            dataSource.setPasswordCipher(cryptoService.encrypt(dataSource.getPassword()));
        }
        dataSource.setCreateBy(SecurityUtils.getUsername());
        int rows = dataSourceMapper.insertDataSource(dataSource);

        // Write log
        writeLog(dataSource.getDatasourceId(), "INSERT", "1",
                "新增数据源：" + dataSource.getSourceName(),
                maskDetail(dataSource));
        return rows;
    }

    @Override
    @Transactional
    public int updateDataSource(DpDataSource dataSource) {
        DpDataSource old = dataSourceMapper.selectDataSourceById(dataSource.getDatasourceId());

        // Handle password: empty or ****** means keep old
        if (dataSource.getPassword() != null && !dataSource.getPassword().isEmpty()
                && !"******".equals(dataSource.getPassword())) {
            dataSource.setPasswordCipher(cryptoService.encrypt(dataSource.getPassword()));
        } else {
            dataSource.setPasswordCipher(null); // don't update
        }

        dataSource.setUpdateBy(SecurityUtils.getUsername());
        int rows = dataSourceMapper.updateDataSource(dataSource);

        writeLog(dataSource.getDatasourceId(), "UPDATE", "1",
                "修改数据源：" + dataSource.getSourceName(),
                maskDetail(dataSource));
        return rows;
    }

    @Override
    @Transactional
    public int deleteDataSourceByIds(Long[] ids) {
        if (ids == null || ids.length == 0) {
            return 0;
        }
        int rows = 0;
        for (Long id : ids) {
            DpDataSource ds = dataSourceMapper.selectDataSourceById(id);
            if (ds != null) {
                rows += dataSourceMapper.deleteDataSourceById(id);
                writeLog(id, "DELETE", "1", "删除数据源：" + ds.getSourceName(), null);
            }
        }
        return rows;
    }

    @Override
    public TestResultVO testConnection(DpDataSource dataSource) {
        TestResultVO result = new TestResultVO();
        String password = resolvePassword(dataSource);

        try (Connection conn = connectionFactory.createConnection(
                dataSource.getHost(), dataSource.getPort(),
                dataSource.getDatabaseName(), dataSource.getUsername(), password)) {

            String version = metadataCollector.fetchVersion(conn);
            result.setDbVersion(version);
            result.setDatabaseName(dataSource.getDatabaseName());

        } catch (Exception e) {
            throw new RuntimeException("连接失败：" + e.getMessage(), e);
        }
        return result;
    }

    @Override
    @Transactional
    public SyncResultVO syncMetadata(Long id) {
        DpDataSource ds = dataSourceMapper.selectDataSourceById(id);
        if (ds == null) {
            throw new RuntimeException("数据源不存在");
        }

        String password = "";
        if (ds.getPasswordCipher() != null && !ds.getPasswordCipher().isEmpty()) {
            password = cryptoService.decrypt(ds.getPasswordCipher());
        }
        String batchNo = "SYNC" + new SimpleDateFormat("yyyyMMddHHmmssSSS").format(new Date());

        SyncResultVO result = new SyncResultVO();
        result.setSyncBatchNo(batchNo);

        try (Connection conn = connectionFactory.createConnection(
                ds.getHost(), ds.getPort(), ds.getDatabaseName(), ds.getUsername(), password)) {

            // Fetch version
            String version = metadataCollector.fetchVersion(conn);
            ds.setDbVersion(version);
            ds.setLastSyncTime(new Date());
            ds.setLastSyncStatus("1");

            // Collect metadata
            MetadataSyncResult meta = metadataCollector.collect(conn, ds.getDatabaseName());
            result.setTableCount(meta.getTableCount());
            result.setViewCount(meta.getViewCount());
            result.setColumnCount(meta.getColumnCount());

            String username = SecurityUtils.getUsername();

            // Sync tables
            for (MetadataTable mt : meta.getTables()) {
                DpMetaTable existing = tableMapper.selectTableByDsAndName(id, mt.getTableName());
                String objectType = "BASE TABLE".equals(mt.getTableType()) ? "TABLE" : "VIEW";

                if (existing != null) {
                    existing.setObjectType(objectType);
                    existing.setTableComment(mt.getTableComment());
                    existing.setRowCount(mt.getTableRows());
                    existing.setSyncBatchNo(batchNo);
                    existing.setStatus("0");
                    tableMapper.updateTable(existing);
                } else {
                    DpMetaTable newTable = new DpMetaTable();
                    newTable.setDatasourceId(id);
                    newTable.setObjectName(mt.getTableName());
                    newTable.setObjectType(objectType);
                    newTable.setTableComment(mt.getTableComment());
                    newTable.setCnName(mt.getTableComment()); // init cn_name from comment
                    newTable.setRowCount(mt.getTableRows());
                    newTable.setSyncBatchNo(batchNo);
                    newTable.setStatus("0");
                    newTable.setCreateBy(username);
                    tableMapper.insertTable(newTable);
                }
            }

            // Mark tables not in this batch as invalid
            tableMapper.markTableInvalid(id, batchNo);

            // Sync columns — delete orphan columns first (doc §12.3 rule)
            columnMapper.deleteOrphanColumns(id, batchNo);

            for (MetadataColumn mc : meta.getColumns()) {
                DpMetaTable tbl = tableMapper.selectTableByDsAndName(id, mc.getTableName());
                if (tbl == null) continue;

                DpMetaColumn existing = columnMapper.selectColumnByTableAndName(tbl.getTableId(), mc.getColumnName());

                String isNullable = "NO".equals(mc.getIsNullable()) ? "0" : "1";
                String isPk = "PRI".equals(mc.getColumnKey()) ? "1" : "0";
                String isFk = "FK".equals(mc.getColumnKey()) ? "1" : "0";

                if (existing != null) {
                    existing.setOrdinalPosition(mc.getOrdinalPosition());
                    existing.setColumnType(mc.getColumnType());
                    existing.setDataType(mc.getDataType());
                    existing.setIsNullable(isNullable);
                    existing.setColumnDefault(mc.getColumnDefault());
                    existing.setColumnComment(mc.getColumnComment());
                    existing.setIsPk(isPk);
                    existing.setIsFk(isFk);
                    existing.setSyncBatchNo(batchNo);
                    columnMapper.updateColumn(existing);
                } else {
                    DpMetaColumn newCol = new DpMetaColumn();
                    newCol.setTableId(tbl.getTableId());
                    newCol.setDatasourceId(id);
                    newCol.setObjectName(mc.getTableName());
                    newCol.setColumnName(mc.getColumnName());
                    newCol.setOrdinalPosition(mc.getOrdinalPosition());
                    newCol.setColumnType(mc.getColumnType());
                    newCol.setDataType(mc.getDataType());
                    newCol.setIsNullable(isNullable);
                    newCol.setColumnDefault(mc.getColumnDefault());
                    newCol.setColumnComment(mc.getColumnComment());
                    newCol.setIsPk(isPk);
                    newCol.setIsFk(isFk);
                    newCol.setSyncBatchNo(batchNo);
                    newCol.setCreateBy(username);
                    columnMapper.insertColumn(newCol);
                }
            }

            // Update datasource sync status
            ds.setLastSyncTime(new Date());
            ds.setLastSyncStatus("1");
            ds.setLastErrorMsg("");
            dataSourceMapper.updateDataSource(ds);

            writeLog(id, "SYNC", "1",
                    "同步成功：表" + meta.getTableCount() + "个，视图" + meta.getViewCount() + "个，字段" + meta.getColumnCount() + "个",
                    "{\"batchNo\":\"" + batchNo + "\"}");

        } catch (Exception e) {
            self.recordSyncError(id, e.getMessage());
            throw new RuntimeException("同步失败：" + e.getMessage(), e);
        }

        return result;
    }

    @Override
    public List<DpMetaTable> listTables(Long datasourceId, DpMetaTable query) {
        query.setDatasourceId(datasourceId);
        return tableMapper.selectTableList(query);
    }

    @Override
    public List<DpMetaColumn> listColumns(Long tableId) {
        return columnMapper.selectColumnsByTableId(tableId);
    }

    @Override
    @Transactional
    public int updateTableCnName(Long tableId, String cnName) {
        DpMetaTable table = tableMapper.selectTableById(tableId);
        if (table == null) {
            throw new RuntimeException("表信息不存在");
        }
        int rows = tableMapper.updateTableCnName(tableId, cnName);
        writeLog(table.getDatasourceId(), "CN_NAME", "1",
                "修改中文名：" + table.getObjectName() + " -> " + cnName, null);
        return rows;
    }

    @Override
    public List<DpDataSourceLog> listLogs(Long datasourceId, DpDataSourceLog query) {
        query.setDatasourceId(datasourceId);
        List<DpDataSourceLog> logs = logMapper.selectLogList(query);
        // Mask sensitive data in detail_json
        for (DpDataSourceLog log : logs) {
            if (log.getDetailJson() != null) {
                log.setDetailJson(cryptoService.maskSensitive(log.getDetailJson()));
            }
        }
        return logs;
    }

    // ---- private helpers ----

    private String resolvePassword(DpDataSource ds) {
        // If no ID, it's a test from form (password in plain text)
        if (ds.getDatasourceId() == null) {
            return ds.getPassword();
        }
        // If saved, decrypt from DB
        DpDataSource existing = dataSourceMapper.selectDataSourceById(ds.getDatasourceId());
        if (existing != null && existing.getPasswordCipher() != null
                && !existing.getPasswordCipher().isEmpty()) {
            return cryptoService.decrypt(existing.getPasswordCipher());
        }
        return ds.getPassword();
    }

    private void writeLog(Long datasourceId, String logType, String result,
                          String message, String detailJson) {
        DpDataSourceLog log = new DpDataSourceLog();
        log.setDatasourceId(datasourceId);
        log.setLogType(logType);
        log.setOperatorName(SecurityUtils.getUsername());
        log.setResult(result);
        log.setMessage(message);
        log.setDetailJson(detailJson);
        logMapper.insertLog(log);
    }

    private String maskDetail(DpDataSource ds) {
        if (ds == null) return null;
        DpDataSource copy = new DpDataSource();
        copy.setSourceName(ds.getSourceName());
        copy.setSourceType(ds.getSourceType());
        copy.setHost(ds.getHost());
        copy.setPort(ds.getPort());
        copy.setDatabaseName(ds.getDatabaseName());
        copy.setPassword("******");
        copy.setPasswordCipher("******");
        return JSON.toJSONString(copy);
    }

    @Override
    @Transactional
    public int updateDataSourceOrder(DpDataSource dataSource) {
        DpDataSource old = dataSourceMapper.selectDataSourceById(dataSource.getDatasourceId());
        if (old == null) {
            throw new RuntimeException("数据源不存在");
        }

        // If catalog changed, move to new catalog; otherwise just reorder
        if (dataSource.getCatalogId() != null && !dataSource.getCatalogId().equals(old.getCatalogId())) {
            int rows = dataSourceMapper.moveDataSource(dataSource);
            writeLog(dataSource.getDatasourceId(), "UPDATE", "1",
                    "移动数据源：" + old.getSourceName() + " 至目录 " + dataSource.getCatalogId(), null);
            return rows;
        }

        int rows = dataSourceMapper.updateDataSourceOrder(dataSource);
        writeLog(dataSource.getDatasourceId(), "UPDATE", "1",
                "重排数据源：" + old.getSourceName(), null);
        return rows;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordSyncError(Long datasourceId, String errorMsg) {
        DpDataSource ds = dataSourceMapper.selectDataSourceById(datasourceId);
        if (ds != null) {
            ds.setLastSyncStatus("2");
            ds.setLastErrorMsg(errorMsg != null && errorMsg.length() > 1000 ? errorMsg.substring(0, 1000) : errorMsg);
            dataSourceMapper.updateDataSource(ds);
        }
        DpDataSourceLog log = new DpDataSourceLog();
        log.setDatasourceId(datasourceId);
        log.setLogType("SYNC");
        log.setOperatorName(SecurityUtils.getUsername());
        log.setResult("0");
        log.setMessage("同步失败：" + errorMsg);
        logMapper.insertLog(log);
    }
}
