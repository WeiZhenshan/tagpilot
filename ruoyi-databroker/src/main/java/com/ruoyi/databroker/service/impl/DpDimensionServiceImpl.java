package com.ruoyi.databroker.service.impl;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.common.constant.HttpStatus;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDimensionTable;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.mapper.DpDimensionTableMapper;
import com.ruoyi.databroker.mapper.DpMetaTableMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.IDpDimensionService;

/**
 * 维表管理 Service 实现
 * 只登记和读取外部物理维表，不建表/改表/写数据
 *
 * @author ruoyi
 */
@Service
public class DpDimensionServiceImpl implements IDpDimensionService {

    /** 物理维表必须具备的六个标准列 */
    private static final String[] STANDARD_COLUMNS = {
        "tag_name_en", "tag_code", "tag_name_cn", "code_definition", "code_sort", "last_update_time"
    };

    /** 维表编码格式（字母数字下划线，1-64位） */
    private static final String CODE_PATTERN = "^[A-Za-z0-9_]{1,64}$";

    @Autowired
    private DpDimensionTableMapper dimensionMapper;
    @Autowired
    private DpDataSourceMapper dataSourceMapper;
    @Autowired
    private DpMetaTableMapper tableMapper;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private DataBrokerProperties properties;

    @Override
    public List<DpDimensionTable> selectDimensionList(DpDimensionTable query) {
        return dimensionMapper.selectDimensionList(query);
    }

    @Override
    public Map<String, Object> getDimensionDetail(Long dimensionId) {
        DpDimensionTable dimension = dimensionMapper.selectDimensionById(dimensionId);
        if (dimension == null) {
            throw new ServiceException("维表不存在");
        }
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("dimension", dimension);
        // 标准字段校验失败不拖累详情整体返回，仅附带错误信息
        try {
            DpDataSource ds = dataSourceMapper.selectDataSourceById(dimension.getDatasourceId());
            if (ds == null || "2".equals(ds.getDelFlag())) {
                throw new ServiceException("数据连接不存在或已删除");
            }
            data.put("fieldChecks", checkStandardFields(ds, dimension.getSourceTableName()));
            data.put("checkError", null);
        } catch (Exception e) {
            data.put("fieldChecks", null);
            data.put("checkError", e.getMessage());
        }
        return data;
    }

    @Override
    @Transactional
    public int insertDimension(DpDimensionTable dimension) {
        // 1. 必填校验
        if (StringUtils.isEmpty(dimension.getDimensionName())) {
            throw new ServiceException("维表名称不能为空");
        }
        if (StringUtils.isEmpty(dimension.getDimensionCode())) {
            throw new ServiceException("维表编码不能为空");
        }
        if (dimension.getDatasourceId() == null) {
            throw new ServiceException("数据连接不能为空");
        }
        if (dimension.getSourceTableId() == null) {
            throw new ServiceException("物理表不能为空");
        }
        // 2. 编码格式校验（字母数字下划线，1-64位）
        if (!dimension.getDimensionCode().matches(CODE_PATTERN)) {
            throw new ServiceException("维表编码仅支持字母、数字、下划线，长度1-64位");
        }
        // 3. 编码全局唯一（含已删除记录，避免唯一键冲突）
        DpDimensionTable codeDup = dimensionMapper.selectByCode(dimension.getDimensionCode());
        if (codeDup != null && "0".equals(codeDup.getDelFlag())) {
            throw new ServiceException("维表编码已存在");
        }
        // 4. 反查物理表元数据（不信任前端传表名）
        DpMetaTable metaTable = tableMapper.selectTableById(dimension.getSourceTableId());
        if (metaTable == null) {
            throw new ServiceException("物理表不存在，请重新同步元数据");
        }
        if (!dimension.getDatasourceId().equals(metaTable.getDatasourceId())) {
            throw new ServiceException("物理表与所选数据连接不匹配");
        }
        if (!"0".equals(metaTable.getStatus())) {
            throw new ServiceException("物理表已失效，请重新同步元数据");
        }
        // 5. 数据连接校验
        DpDataSource ds = dataSourceMapper.selectDataSourceById(dimension.getDatasourceId());
        if (ds == null || "2".equals(ds.getDelFlag())) {
            throw new ServiceException("数据连接不存在或已删除");
        }
        if (!"0".equals(ds.getStatus())) {
            throw new ServiceException("数据连接已停用");
        }
        // 6. 同一数据源+物理表唯一：未删除则报错，已删除则恢复原记录
        DpDimensionTable sourceDup = dimensionMapper.selectBySource(
                dimension.getDatasourceId(), dimension.getSourceTableId());
        if (sourceDup != null && "0".equals(sourceDup.getDelFlag())) {
            throw new ServiceException("该物理表已登记维表");
        }
        if (codeDup != null && (sourceDup == null
                || !codeDup.getDimensionId().equals(sourceDup.getDimensionId()))) {
            throw new ServiceException("维表编码已被历史删除记录占用，请更换编码");
        }
        // 7. 连接外部库校验六个标准字段，缺列则报错
        String tableName = metaTable.getObjectName();
        List<Map<String, Object>> checks = checkStandardFields(ds, tableName);
        List<String> missing = missingColumns(checks);
        if (!missing.isEmpty()) {
            throw new ServiceException("物理表缺少标准字段：" + String.join("、", missing));
        }
        // 8. 只保存登记信息，不复制物理数据；source_table_name 存当前表名快照
        if (sourceDup != null) {
            // 恢复已删除的登记记录，避免唯一键阻塞
            sourceDup.setDimensionName(dimension.getDimensionName());
            sourceDup.setDimensionCode(dimension.getDimensionCode());
            sourceDup.setSourceTableName(tableName);
            sourceDup.setRemark(dimension.getRemark());
            sourceDup.setUpdateBy(SecurityUtils.getUsername());
            return dimensionMapper.restoreDimension(sourceDup);
        }
        dimension.setSourceTableName(tableName);
        dimension.setStatus("0");
        dimension.setCreateBy(SecurityUtils.getUsername());
        return dimensionMapper.insertDimension(dimension);
    }

    @Override
    @Transactional
    public int updateDimension(DpDimensionTable dimension) {
        if (dimension.getDimensionId() == null) {
            throw new ServiceException("维表ID不能为空");
        }
        DpDimensionTable old = dimensionMapper.selectDimensionById(dimension.getDimensionId());
        if (old == null) {
            throw new ServiceException("维表不存在");
        }
        // 仅允许修改维表名称和备注，编码/数据源/物理表等变更由 update SQL 天然忽略
        DpDimensionTable update = new DpDimensionTable();
        update.setDimensionId(dimension.getDimensionId());
        update.setDimensionName(dimension.getDimensionName());
        update.setRemark(dimension.getRemark());
        update.setUpdateBy(SecurityUtils.getUsername());
        return dimensionMapper.updateDimension(update);
    }

    @Override
    @Transactional
    public int deleteDimensionByIds(Long[] dimensionIds) {
        if (dimensionIds == null || dimensionIds.length == 0) {
            return 0;
        }
        // 全有或全无：任意一个被标签库关联则整个请求失败
        for (Long id : dimensionIds) {
            DpDimensionTable dimension = dimensionMapper.selectDimensionById(id);
            if (dimension == null) {
                continue;
            }
            if (dimensionMapper.countLibraryReferences(id) > 0) {
                throw new ServiceException("维表 " + dimension.getDimensionName() + " 仍被标签库关联");
            }
        }
        // 只删登记记录，不动外部物理表
        return dimensionMapper.deleteDimensionByIds(dimensionIds);
    }

    @Override
    @Transactional
    public int updateStatus(Long dimensionId, String status) {
        DpDimensionTable dimension = dimensionMapper.selectDimensionById(dimensionId);
        if (dimension == null) {
            throw new ServiceException("维表不存在");
        }
        if (!"0".equals(status) && !"1".equals(status)) {
            throw new ServiceException("非法的状态值");
        }
        if ("1".equals(status)) {
            // 停用：被标签库关联则拒绝
            if (dimensionMapper.countLibraryReferences(dimensionId) > 0) {
                throw new ServiceException("维表 " + dimension.getDimensionName() + " 仍被标签库关联，不能停用");
            }
        } else {
            // 启用：重新校验物理表存在且六列齐全
            DpDataSource ds = dataSourceMapper.selectDataSourceById(dimension.getDatasourceId());
            if (ds == null || "2".equals(ds.getDelFlag())) {
                throw new ServiceException("数据连接不存在或已删除");
            }
            if (!"0".equals(ds.getStatus())) {
                throw new ServiceException("数据连接已停用，不能启用维表");
            }
            List<Map<String, Object>> checks = checkStandardFields(ds, dimension.getSourceTableName());
            List<String> missing = missingColumns(checks);
            if (!missing.isEmpty()) {
                throw new ServiceException("物理表缺少标准字段：" + String.join("、", missing));
            }
        }
        return dimensionMapper.updateStatus(dimensionId, status);
    }

    @Override
    public List<Map<String, Object>> listDatasourceOptions() {
        return dimensionMapper.selectAvailableDatasources();
    }

    @Override
    public List<Map<String, Object>> listTableOptions(Long datasourceId) {
        if (datasourceId == null) {
            throw new ServiceException("数据连接ID不能为空");
        }
        return dimensionMapper.selectAvailableTables(datasourceId);
    }

    @Override
    public TableDataInfo previewValues(Long dimensionId, Integer pageNum, Integer pageSize) {
        DpDimensionTable dimension = dimensionMapper.selectDimensionById(dimensionId);
        if (dimension == null) {
            throw new ServiceException("维表不存在");
        }
        // 表名只允许来自 dp_meta_table.object_name，绝不拼接前端输入
        DpMetaTable metaTable = tableMapper.selectTableById(dimension.getSourceTableId());
        if (metaTable == null) {
            throw new ServiceException("物理表元数据不存在，请重新同步元数据");
        }
        DpDataSource ds = dataSourceMapper.selectDataSourceById(dimension.getDatasourceId());
        if (ds == null || "2".equals(ds.getDelFlag())) {
            throw new ServiceException("数据连接不存在或已删除");
        }

        int page = (pageNum == null || pageNum < 1) ? 1 : pageNum;
        int size = (pageSize == null || pageSize < 1) ? 10 : Math.min(pageSize, 100);
        String tableName = "`" + metaTable.getObjectName().replace("`", "``") + "`";
        String password = StringUtils.isNotEmpty(ds.getPasswordCipher())
                ? cryptoService.decrypt(ds.getPasswordCipher()) : "";

        long total = 0;
        List<Map<String, Object>> rows = new ArrayList<>();
        try (Connection conn = connectionFactory.createConnection(ds, password)) {
            int timeout = Math.max(1, properties.getJdbc().getSocketTimeout() / 1000);
            // 总数
            try (PreparedStatement countStmt = conn.prepareStatement("SELECT COUNT(*) FROM " + tableName)) {
                countStmt.setQueryTimeout(timeout);
                try (ResultSet rs = countStmt.executeQuery()) {
                    if (rs.next()) {
                        total = rs.getLong(1);
                    }
                }
            }
            // 手工分页（外部 JDBC，PageHelper 管不到）
            String sql = "SELECT tag_name_en, tag_code, tag_name_cn, code_definition, code_sort, last_update_time"
                    + " FROM " + tableName
                    + " ORDER BY tag_name_en, code_sort, tag_code LIMIT ? OFFSET ?";
            try (PreparedStatement stmt = conn.prepareStatement(sql)) {
                stmt.setQueryTimeout(timeout);
                stmt.setInt(1, size);
                stmt.setInt(2, (page - 1) * size);
                try (ResultSet rs = stmt.executeQuery()) {
                    while (rs.next()) {
                        Map<String, Object> row = new LinkedHashMap<>();
                        row.put("tagNameEn", rs.getObject("tag_name_en"));
                        row.put("tagCode", rs.getObject("tag_code"));
                        row.put("tagNameCn", rs.getObject("tag_name_cn"));
                        row.put("codeDefinition", rs.getObject("code_definition"));
                        row.put("codeSort", rs.getObject("code_sort"));
                        row.put("lastUpdateTime", rs.getObject("last_update_time"));
                        rows.add(row);
                    }
                }
            }
        } catch (Exception e) {
            throw new ServiceException("码值预览失败：" + e.getMessage());
        }

        TableDataInfo dataInfo = new TableDataInfo();
        dataInfo.setRows(rows);
        dataInfo.setTotal(total);
        dataInfo.setCode(HttpStatus.SUCCESS);
        dataInfo.setMsg("查询成功");
        return dataInfo;
    }

    @Override
    public List<Map<String, Object>> checkTableFields(Long sourceTableId) {
        if (sourceTableId == null) {
            throw new ServiceException("物理表ID不能为空");
        }
        DpMetaTable metaTable = tableMapper.selectTableById(sourceTableId);
        if (metaTable == null) {
            throw new ServiceException("物理表不存在，请重新同步元数据");
        }
        DpDataSource ds = dataSourceMapper.selectDataSourceById(metaTable.getDatasourceId());
        if (ds == null || "2".equals(ds.getDelFlag())) {
            throw new ServiceException("数据连接不存在或已删除");
        }
        return checkStandardFields(ds, metaTable.getObjectName());
    }

    // ---- private helpers ----

    /**
     * 连接外部库校验六个标准列是否存在（register/enable/detail 共用）
     * 返回 [{columnName, exists}]，连接失败抛 ServiceException
     */
    private List<Map<String, Object>> checkStandardFields(DpDataSource ds, String tableName) {
        String password = StringUtils.isNotEmpty(ds.getPasswordCipher())
                ? cryptoService.decrypt(ds.getPasswordCipher()) : "";
        Set<String> columns = new HashSet<>();
        try (Connection conn = connectionFactory.createConnection(ds, password);
             PreparedStatement stmt = conn.prepareStatement(
                     "SELECT column_name FROM information_schema.COLUMNS WHERE table_schema = ? AND table_name = ?")) {
            stmt.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
            stmt.setString(1, ds.getDatabaseName());
            stmt.setString(2, tableName);
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    String col = rs.getString(1);
                    if (col != null) {
                        columns.add(col.toLowerCase());
                    }
                }
            }
        } catch (Exception e) {
            throw new ServiceException("连接数据源失败：" + e.getMessage());
        }
        List<Map<String, Object>> checks = new ArrayList<>();
        for (String col : STANDARD_COLUMNS) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("columnName", col);
            item.put("exists", columns.contains(col));
            checks.add(item);
        }
        return checks;
    }

    /** 从校验结果中提取缺失的列名 */
    private List<String> missingColumns(List<Map<String, Object>> checks) {
        List<String> missing = new ArrayList<>();
        for (Map<String, Object> item : checks) {
            if (!Boolean.TRUE.equals(item.get("exists"))) {
                missing.add((String) item.get("columnName"));
            }
        }
        return missing;
    }
}
