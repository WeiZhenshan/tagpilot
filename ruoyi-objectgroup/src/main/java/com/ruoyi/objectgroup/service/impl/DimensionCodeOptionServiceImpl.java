package com.ruoyi.objectgroup.service.impl;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.objectgroup.domain.DimensionTableRef;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.IDimensionCodeOptionService;

/**
 * 维表码值选项业务层：从标签库默认码表对应的物理维表实时读取码值
 */
@Service
public class DimensionCodeOptionServiceImpl implements IDimensionCodeOptionService {

    /** 物理表名白名单（字母/数字/下划线），防注入 */
    private static final Pattern TABLE_NAME_PATTERN = Pattern.compile("^[A-Za-z0-9_]+$");

    /** 支持码值选项的标签类型 */
    private static final String TAG_TYPE_OPTION = "选项型";
    private static final String TAG_TYPE_BOOL = "布尔型";

    @Autowired
    private TlObjectGroupExtMapper extMapper;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private DataBrokerProperties properties;

    @Override
    public List<Map<String, Object>> listCodeOptions(Long libraryId, String fieldName) {
        if (libraryId == null || fieldName == null || fieldName.trim().isEmpty()) {
            throw new ServiceException("标签库与标签字段不能为空");
        }
        // 1. 校验标签存在且类型支持码值选项
        String tagType = extMapper.selectTagTypeByField(libraryId, fieldName);
        if (tagType == null) {
            throw new ServiceException("标签不存在或已删除");
        }
        if (!TAG_TYPE_OPTION.equals(tagType) && !TAG_TYPE_BOOL.equals(tagType)) {
            throw new ServiceException("该标签类型不支持码值选项");
        }

        // 2. 查标签库全部已关联、启用、未删除且同源的维表；无关联维表返回空列表
        List<DimensionTableRef> dimensions = extMapper.selectEnabledDimensionsByLibrary(libraryId);
        if (dimensions == null || dimensions.isEmpty()) {
            return new ArrayList<>();
        }

        // 3. 连接外部数据源，逐张维表参数化查询并按 tag_code 合并
        Map<String, Map<String, Object>> merged = new LinkedHashMap<>();
        try (Connection conn = openConnection(libraryId)) {
            for (DimensionTableRef dim : dimensions) {
                queryDimensionTable(conn, dim, fieldName, merged);
            }
        } catch (ServiceException e) {
            throw e;
        } catch (Exception e) {
            throw new ServiceException("码值选项查询失败：" + e.getMessage());
        }

        // 4. 排序：code_sort 升序，再 tag_code 字符串升序
        List<Map<String, Object>> options = new ArrayList<>(merged.values());
        options.forEach(row -> row.remove("dimensionName"));
        options.sort((a, b) -> {
            Integer sa = (Integer) a.get("orderNum");
            Integer sb = (Integer) b.get("orderNum");
            if (sa == null && sb == null) {
                // 均无排序号时按码值排序
            } else if (sa == null) {
                return 1;
            } else if (sb == null) {
                return -1;
            } else {
                int cmp = sa.compareTo(sb);
                if (cmp != 0) {
                    return cmp;
                }
            }
            String ca = (String) a.get("code");
            String cb = (String) b.get("code");
            if (ca == null) {
                return cb == null ? 0 : 1;
            }
            return cb == null ? -1 : ca.compareTo(cb);
        });
        return options;
    }

    /** 查询单张维表并合并到结果集；同码值定义不一致时抛冲突异常 */
    private void queryDimensionTable(Connection conn, DimensionTableRef dim, String fieldName,
                                     Map<String, Map<String, Object>> merged) throws Exception {
        String tableName = dim.getSourceTableName();
        if (tableName == null || !TABLE_NAME_PATTERN.matcher(tableName).matches()) {
            throw new ServiceException("维表[" + dim.getDimensionName() + "]的物理表名不合法");
        }
        String sql = "select tag_code, code_definition, tag_name_cn, code_sort, last_update_time from `"
                + tableName + "` where tag_name_en = ?";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
            ps.setString(1, fieldName);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    String code = rs.getString("tag_code");
                    if (code == null) {
                        continue;
                    }
                    String codeDefinition = rs.getString("code_definition");
                    Map<String, Object> exist = merged.get(code);
                    if (exist != null) {
                        // 同码值跨维表出现：定义一致则保留首个，不一致则报冲突
                        String existDef = (String) exist.get("codeDefinition");
                        boolean same = existDef == null ? codeDefinition == null : existDef.equals(codeDefinition);
                        if (!same) {
                            throw new ServiceException("维表码值冲突：码值 " + code + " 在维表 "
                                    + exist.get("dimensionName") + " 与维表 " + dim.getDimensionName() + " 中定义不一致");
                        }
                        continue;
                    }
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("code", code);
                    row.put("codeDefinition", codeDefinition);
                    row.put("tagName", rs.getString("tag_name_cn"));
                    Object sort = rs.getObject("code_sort");
                    row.put("orderNum", sort == null ? null : ((Number) sort).intValue());
                    row.put("lastUpdateTime", rs.getString("last_update_time"));
                    row.put("dimensionId", dim.getDimensionId());
                    // dimensionName 仅用于冲突提示，不返回给前端
                    row.put("dimensionName", dim.getDimensionName());
                    merged.put(code, row);
                }
            }
        }
    }

    /** 打开标签库数据集对应的外部数据源连接（与码值同步同一链路） */
    private Connection openConnection(Long libraryId) {
        Long datasetId = extMapper.selectDatasetIdByLibrary(libraryId);
        if (datasetId == null) {
            throw new ServiceException("标签库未关联数据集");
        }
        DpDataSource ds = extMapper.selectDataSourceByDataset(datasetId);
        if (ds == null) {
            throw new ServiceException("数据集的数据源不存在");
        }
        String password = "";
        if (ds.getPasswordCipher() != null && !ds.getPasswordCipher().isEmpty()) {
            password = cryptoService.decrypt(ds.getPasswordCipher());
        }
        try {
            return connectionFactory.createConnection(
                    ds.getHost(), ds.getPort(), ds.getDatabaseName(), ds.getUsername(), password);
        } catch (Exception e) {
            throw new ServiceException("连接数据源失败：" + e.getMessage());
        }
    }
}
