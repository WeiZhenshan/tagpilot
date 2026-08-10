package com.ruoyi.objectgroup.service.impl;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.domain.TlObjectGroup;
import com.ruoyi.objectgroup.domain.TlObjectGroupImport;
import com.ruoyi.objectgroup.mapper.TlObjectGroupImportMapper;
import com.ruoyi.objectgroup.mapper.TlObjectGroupMapper;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.ITlObjectGroupService;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;

/**
 * 对象群业务层：CRUD、规则运行、样例预览、导入解析
 */
@Service
public class TlObjectGroupServiceImpl implements ITlObjectGroupService {

    private static final Logger log = LoggerFactory.getLogger(TlObjectGroupServiceImpl.class);

    private static final long MAX_FILE_SIZE = 5L * 1024 * 1024;
    private static final int MAX_IMPORT_COUNT = 50000;

    @Autowired
    private TlObjectGroupMapper groupMapper;
    @Autowired
    private TlObjectGroupImportMapper importMapper;
    @Autowired
    private TlObjectGroupExtMapper extMapper;
    @Autowired
    private IRuleSqlBuilder ruleSqlBuilder;
    @Autowired
    private JdbcConnectionFactory connectionFactory;
    @Autowired
    private DataBrokerCryptoService cryptoService;
    @Autowired
    private DpDataSourceMapper dataSourceMapper;
    @Autowired
    private DataBrokerProperties properties;
    @Autowired
    private ObjectMapper objectMapper;

    @Override
    public List<TlObjectGroup> selectObjectGroupList(TlObjectGroup query) {
        List<TlObjectGroup> list = groupMapper.selectObjectGroupList(query);
        for (TlObjectGroup g : list) {
            g.setTagNames(extractTagNames(g.getRuleJson()));
        }
        return list;
    }

    @Override
    public TlObjectGroup selectObjectGroupById(Long groupId) {
        return groupMapper.selectObjectGroupById(groupId);
    }

    @Override
    @Transactional
    public int insertObjectGroup(TlObjectGroup group) {
        if (group.getGroupName() == null || group.getGroupName().trim().isEmpty()) {
            throw new ServiceException("对象群名称不能为空");
        }
        if (group.getLibraryId() == null) {
            throw new ServiceException("请选择关联标签库");
        }
        group.setCreateBy(SecurityUtils.getUsername());
        int rows = groupMapper.insertObjectGroup(group);
        bindImportBatches(group.getRuleJson(), group.getGroupId());
        return rows;
    }

    @Override
    @Transactional
    public int updateObjectGroup(TlObjectGroup group) {
        group.setUpdateBy(SecurityUtils.getUsername());
        int rows = groupMapper.updateObjectGroup(group);
        bindImportBatches(group.getRuleJson(), group.getGroupId());
        return rows;
    }

    @Override
    @Transactional
    public int deleteObjectGroupByIds(Long[] groupIds) {
        for (Long id : groupIds) {
            importMapper.deleteByGroupId(id);
        }
        return groupMapper.deleteObjectGroupByIds(groupIds);
    }

    @Override
    public String buildRuleSql(Long libraryId, RulePayload rule) {
        return ruleSqlBuilder.buildSql(libraryId, rule, IRuleSqlBuilder.MODE_COUNT);
    }

    @Override
    public long runRule(Long groupId, Long libraryId, RulePayload rule) {
        // 列表页刷新按钮只传 groupId：从库中加载规则
        if (groupId != null && (rule == null || rule.getConditions() == null)) {
            TlObjectGroup group = groupMapper.selectObjectGroupById(groupId);
            if (group == null) {
                throw new ServiceException("对象群不存在");
            }
            libraryId = group.getLibraryId();
            try {
                rule = objectMapper.readValue(group.getRuleJson(), RulePayload.class);
            } catch (Exception e) {
                throw new ServiceException("对象群规则解析失败");
            }
        }
        String sql = ruleSqlBuilder.buildSql(libraryId, rule, IRuleSqlBuilder.MODE_COUNT);
        long count = executeCount(sql, libraryId);
        if (groupId != null) {
            groupMapper.updateUserCount(groupId, count);
            TlObjectGroup group = groupMapper.selectObjectGroupById(groupId);
            if (group != null) {
                group.setGroupSql(sql);
                group.setUpdateBy(SecurityUtils.getUsername());
                groupMapper.updateObjectGroup(group);
            }
        }
        return count;
    }

    @Override
    public Map<String, Object> previewRule(Long groupId, Long libraryId, RulePayload rule) {
        if (groupId != null && (rule == null || rule.getConditions() == null)) {
            TlObjectGroup group = groupMapper.selectObjectGroupById(groupId);
            if (group == null) {
                throw new ServiceException("对象群不存在");
            }
            libraryId = group.getLibraryId();
            try {
                rule = objectMapper.readValue(group.getRuleJson(), RulePayload.class);
            } catch (Exception e) {
                throw new ServiceException("对象群规则解析失败");
            }
        }
        String sql = ruleSqlBuilder.buildSql(libraryId, rule, IRuleSqlBuilder.MODE_SELECT);
        return executeSelect(sql, libraryId);
    }

    @Override
    public Map<String, Object> parseImportFile(MultipartFile file, String fieldName) {
        if (file == null || file.isEmpty()) {
            throw new ServiceException("请选择要上传的文件");
        }
        if (file.getSize() > MAX_FILE_SIZE) {
            throw new ServiceException("文件大小不能超过 5M");
        }
        String filename = file.getOriginalFilename() == null ? "" : file.getOriginalFilename().toLowerCase();
        if (!filename.endsWith(".txt") && !filename.endsWith(".csv")) {
            throw new ServiceException("仅支持 txt/csv 文件");
        }

        Set<String> values = new LinkedHashSet<>();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(file.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String v = line.trim();
                if (v.isEmpty()) {
                    continue;
                }
                // csv 取第一列
                if (filename.endsWith(".csv") && v.contains(",")) {
                    v = v.substring(0, v.indexOf(',')).trim();
                }
                if (!v.isEmpty()) {
                    values.add(v);
                }
                if (values.size() > MAX_IMPORT_COUNT) {
                    throw new ServiceException("导入值超过上限（5万条），请拆分后重新导入");
                }
            }
        } catch (ServiceException e) {
            throw e;
        } catch (Exception e) {
            throw new ServiceException("文件解析失败：" + e.getMessage());
        }
        if (values.isEmpty()) {
            throw new ServiceException("文件中没有有效数据");
        }

        String batchNo = UUID.randomUUID().toString().replace("-", "");
        String username = SecurityUtils.getUsername();
        List<TlObjectGroupImport> imports = new ArrayList<>();
        for (String v : values) {
            TlObjectGroupImport item = new TlObjectGroupImport();
            item.setImportBatch(batchNo);
            item.setFieldName(fieldName);
            item.setValue(v);
            item.setCreateBy(username);
            imports.add(item);
        }
        importMapper.insertBatch(imports);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("batchNo", batchNo);
        result.put("total", (long) imports.size());
        return result;
    }

    // ---- private ----

    /** 保存/更新后按 rule_json 里的批次号回填 group_id */
    private void bindImportBatches(String ruleJson, Long groupId) {
        if (ruleJson == null || ruleJson.isEmpty()) {
            return;
        }
        try {
            RulePayload rule = objectMapper.readValue(ruleJson, RulePayload.class);
            if (rule.getConditions() == null) {
                return;
            }
            Set<String> batches = new LinkedHashSet<>();
            for (RulePayload.Condition c : rule.getConditions()) {
                if (c.getImportBatchNo() != null && !c.getImportBatchNo().isEmpty()) {
                    batches.add(c.getImportBatchNo());
                }
            }
            for (String batch : batches) {
                importMapper.bindGroup(batch, groupId);
            }
        } catch (Exception e) {
            log.warn("绑定导入批次失败: {}", e.getMessage());
        }
    }

    /** 从 rule_json 提取标签中文名（去重顿号串） */
    private String extractTagNames(String ruleJson) {
        if (ruleJson == null || ruleJson.isEmpty()) {
            return "";
        }
        try {
            RulePayload rule = objectMapper.readValue(ruleJson, RulePayload.class);
            if (rule.getConditions() == null) {
                return "";
            }
            Set<String> names = new LinkedHashSet<>();
            for (RulePayload.Condition c : rule.getConditions()) {
                if (c.getTagName() != null && !c.getTagName().isEmpty()) {
                    names.add(c.getTagName());
                }
            }
            return String.join("、", names);
        } catch (Exception e) {
            return "";
        }
    }

    /** 执行 COUNT 查询 */
    private long executeCount(String sql, Long libraryId) {
        try (Connection conn = openConnection(libraryId); Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
            try (ResultSet rs = stmt.executeQuery(sql)) {
                return rs.next() ? rs.getLong(1) : 0L;
            }
        } catch (Exception e) {
            throw new ServiceException("规则运行失败：" + e.getMessage());
        }
    }

    /** 执行 SELECT 预览（客户号 + 预览列） */
    private Map<String, Object> executeSelect(String sql, Long libraryId) {
        List<String> columns = new ArrayList<>();
        List<Map<String, Object>> rows = new ArrayList<>();
        try (Connection conn = openConnection(libraryId); Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
            try (ResultSet rs = stmt.executeQuery(sql)) {
                int colCount = rs.getMetaData().getColumnCount();
                for (int i = 1; i <= colCount; i++) {
                    columns.add(rs.getMetaData().getColumnLabel(i));
                }
                while (rs.next()) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (int i = 1; i <= colCount; i++) {
                        row.put(columns.get(i - 1), rs.getObject(i));
                    }
                    rows.add(row);
                }
            }
        } catch (Exception e) {
            throw new ServiceException("样例预览失败：" + e.getMessage());
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("columns", columns);
        result.put("rows", rows);
        return result;
    }

    /** 打开目标数据源连接（复用数据代理链路） */
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
