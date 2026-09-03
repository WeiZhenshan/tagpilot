package com.ruoyi.objectgroup.service.impl;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.objectgroup.domain.TlTagCodeValue;
import com.ruoyi.objectgroup.domain.vo.CodeValueSyncVO;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.mapper.TlTagCodeValueMapper;
import com.ruoyi.objectgroup.service.ICodeValueService;

/**
 * 码值业务层：宽表 DISTINCT 同步 + 手工维护
 */
@Service
public class CodeValueServiceImpl implements ICodeValueService {

    private static final int MAX_CODE_COUNT = 500;

    @Autowired
    private TlTagCodeValueMapper codeValueMapper;
    @Autowired
    private TlObjectGroupExtMapper extMapper;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private DataBrokerProperties properties;

    @Override
    public List<TlTagCodeValue> selectCodeValueList(TlTagCodeValue query) {
        return codeValueMapper.selectCodeValueList(query);
    }

    @Override
    public int insertCodeValue(TlTagCodeValue codeValue) {
        codeValue.setCreateBy(SecurityUtils.getUsername());
        codeValue.setUpdateBy(SecurityUtils.getUsername());
        return codeValueMapper.insertCodeValue(codeValue);
    }

    @Override
    public int updateCodeValue(TlTagCodeValue codeValue) {
        codeValue.setUpdateBy(SecurityUtils.getUsername());
        return codeValueMapper.updateCodeValue(codeValue);
    }

    @Override
    public int deleteCodeValueByIds(Long[] valueIds) {
        return codeValueMapper.deleteCodeValueByIds(valueIds);
    }

    @Override
    @Transactional
    public CodeValueSyncVO syncCodeValue(Long libraryId, String fieldName) {
        if (fieldName == null || fieldName.trim().isEmpty()) {
            throw new ServiceException("请选择要同步的标签");
        }
        String columnName = resolveColumnName(libraryId, fieldName);
        String tableName = resolveTableName(libraryId);

        // 多读一行用于截断检测；ORDER BY 保证截断窗口稳定
        String sql = "select distinct `" + columnName.replace("`", "``") + "` from `"
                + tableName.replace("`", "``") + "` order by `" + columnName.replace("`", "``")
                + "` limit " + (MAX_CODE_COUNT + 1);

        List<String> codes = new ArrayList<>();
        try (Connection conn = openConnection(libraryId); Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
            try (ResultSet rs = stmt.executeQuery(sql)) {
                while (rs.next()) {
                    Object value = rs.getObject(1);
                    // SQL NULL 跳过，避免落成字符串 "null"
                    if (value == null) {
                        continue;
                    }
                    codes.add(String.valueOf(value));
                }
            }
        } catch (Exception e) {
            throw new ServiceException("码值同步失败：" + e.getMessage());
        }

        if (codes.isEmpty()) {
            throw new ServiceException("宽表该列无数据");
        }

        boolean truncated = codes.size() > MAX_CODE_COUNT;
        if (truncated) {
            codes = new ArrayList<>(codes.subList(0, MAX_CODE_COUNT));
        } else {
            // 全量对齐：宽表中已不存在的码值清理掉；截断时看不到完整码值集，保留其余行
            codeValueMapper.deleteNotInCodes(libraryId, fieldName, codes);
        }

        String username = SecurityUtils.getUsername();
        int count = 0;
        for (String code : codes) {
            TlTagCodeValue cv = new TlTagCodeValue();
            cv.setLibraryId(libraryId);
            cv.setFieldName(fieldName);
            cv.setTagName(resolveTagName(libraryId, fieldName));
            cv.setCode(code);
            cv.setCodeDefinition(code);
            cv.setOrderNum(++count);
            cv.setCreateBy(username);
            cv.setUpdateBy(username);
            codeValueMapper.upsertCodeValue(cv);
        }
        return new CodeValueSyncVO(count, truncated);
    }

    // ---- private ----

    private String resolveColumnName(Long libraryId, String fieldName) {
        Long versionId = extMapper.selectOnlineVersionId(libraryId);
        if (versionId == null) {
            throw new ServiceException("关联标签库的数据集不存在或未上线");
        }
        String column = extMapper.selectColumnNameByAlias(versionId, fieldName);
        if (column == null) {
            throw new ServiceException("字段[" + fieldName + "]未在数据集中启用");
        }
        return column;
    }

    private String resolveTableName(Long libraryId) {
        Long versionId = extMapper.selectOnlineVersionId(libraryId);
        if (versionId == null) {
            throw new ServiceException("关联标签库的数据集不存在或未上线");
        }
        String definitionJson = extMapper.selectVersionDefinitionJson(versionId);
        if (definitionJson == null || definitionJson.isEmpty()) {
            throw new ServiceException("数据集定义为空");
        }
        try {
            com.alibaba.fastjson2.JSONObject def = com.alibaba.fastjson2.JSON.parseObject(definitionJson);
            Long tableId = def.getLong("tableId");
            if (tableId == null) {
                throw new ServiceException("数据集未配置宽表");
            }
            String tableName = extMapper.selectTableObjectName(tableId);
            if (tableName == null) {
                throw new ServiceException("宽表不存在");
            }
            return tableName;
        } catch (ServiceException e) {
            throw e;
        } catch (Exception e) {
            throw new ServiceException("数据集定义解析失败：" + e.getMessage());
        }
    }

    private String resolveTagName(Long libraryId, String fieldName) {
        // tl_tag 表中取中文名，无则用字段名
        String tagName = extMapper.selectTagNameByField(libraryId, fieldName);
        return tagName == null ? fieldName : tagName;
    }

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
