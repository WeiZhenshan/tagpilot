package com.ruoyi.objectgroup.service.impl;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
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
import com.ruoyi.objectgroup.domain.vo.RuleRunResultVO;
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
    /** 单批次导入值上限（与 tl_object_group_import.value 列宽 64 配套的语义上限） */
    private static final int MAX_IMPORT_COUNT = 50000;
    /** 值长度上限：tl_object_group_import.value 为 varchar(64) */
    private static final int MAX_VALUE_LENGTH = 64;
    /** 本地导入表分片写入行数（避免单条巨型 insert 超 max_allowed_packet） */
    private static final int IMPORT_INSERT_CHUNK = 1000;
    /** 目标库 session 临时表分片装载行数 */
    private static final int TEMP_LOAD_CHUNK = 1000;

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
        group.setRuleJson(stampDatasetVersion(group.getRuleJson(), group.getLibraryId()));
        int rows = groupMapper.insertObjectGroup(group);
        bindImportBatches(group.getRuleJson(), group.getGroupId());
        return rows;
    }

    @Override
    @Transactional
    public int updateObjectGroup(TlObjectGroup group) {
        group.setUpdateBy(SecurityUtils.getUsername());
        Long libraryId = group.getLibraryId();
        if (libraryId == null) {
            TlObjectGroup saved = groupMapper.selectObjectGroupById(group.getGroupId());
            libraryId = saved == null ? null : saved.getLibraryId();
        }
        group.setRuleJson(stampDatasetVersion(group.getRuleJson(), libraryId));
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
    public RuleRunResultVO runRule(Long groupId, Long libraryId, RulePayload rule) {
        // 列表页刷新按钮只传 groupId：从库中加载规则
        if (groupId != null && (rule == null || rule.getConditions() == null)) {
            TlObjectGroup group = requireGroup(groupId);
            libraryId = group.getLibraryId();
            rule = parseRule(group.getRuleJson());
        }
        String warning = checkVersionDrift(groupId, libraryId, rule);
        String sql = ruleSqlBuilder.buildSql(libraryId, rule, IRuleSqlBuilder.MODE_COUNT);
        long count = executeCount(sql, libraryId, rule);
        if (groupId != null) {
            groupMapper.updateUserCount(groupId, count);
            TlObjectGroup group = groupMapper.selectObjectGroupById(groupId);
            if (group != null) {
                group.setGroupSql(sql);
                group.setUpdateBy(SecurityUtils.getUsername());
                groupMapper.updateObjectGroup(group);
            }
        }
        return new RuleRunResultVO(count, warning);
    }

    @Override
    public Map<String, Object> previewRule(Long groupId, Long libraryId, RulePayload rule) {
        if (groupId != null && (rule == null || rule.getConditions() == null)) {
            TlObjectGroup group = requireGroup(groupId);
            libraryId = group.getLibraryId();
            rule = parseRule(group.getRuleJson());
        }
        String warning = checkVersionDrift(groupId, libraryId, rule);
        Map<String, Object> result = executeSelect(ruleSqlBuilder.buildSql(libraryId, rule, IRuleSqlBuilder.MODE_SELECT),
                libraryId, rule);
        if (warning != null) {
            result.put("warning", warning);
        }
        return result;
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
        boolean firstLine = true;
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(file.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (firstLine) {
                    firstLine = false;
                    // UTF-8 BOM 仅出现在文件首行，不剥离会导致首个客户号匹配不到
                    if (!line.isEmpty() && line.charAt(0) == '\uFEFF') {
                        line = line.substring(1);
                    }
                }
                String v = line.trim();
                if (v.isEmpty()) {
                    continue;
                }
                // csv 取第一列
                if (filename.endsWith(".csv") && v.contains(",")) {
                    v = v.substring(0, v.indexOf(',')).trim();
                }
                if (!v.isEmpty()) {
                    if (v.length() > MAX_VALUE_LENGTH) {
                        throw new ServiceException("客户号[" + v.substring(0, 20) + "...]长度超过 "
                                + MAX_VALUE_LENGTH + " 字符，请检查文件内容");
                    }
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
        for (int i = 0; i < imports.size(); i += IMPORT_INSERT_CHUNK) {
            importMapper.insertBatch(imports.subList(i, Math.min(i + IMPORT_INSERT_CHUNK, imports.size())));
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("batchNo", batchNo);
        result.put("total", (long) imports.size());
        return result;
    }

    // ---- private ----

    /** 按 groupId 加载对象群，不存在时抛业务异常 */
    private TlObjectGroup requireGroup(Long groupId) {
        TlObjectGroup group = groupMapper.selectObjectGroupById(groupId);
        if (group == null) {
            throw new ServiceException("对象群不存在");
        }
        return group;
    }

    /** 解析 rule_json；解析失败视为规则损坏 */
    private RulePayload parseRule(String ruleJson) {
        try {
            return objectMapper.readValue(ruleJson, RulePayload.class);
        } catch (Exception e) {
            throw new ServiceException("对象群规则解析失败");
        }
    }

    /** 保存时把当前在线数据集版本写入 rule_json，作为运行期版本漂移告警的基线 */
    private String stampDatasetVersion(String ruleJson, Long libraryId) {
        if (ruleJson == null || ruleJson.isEmpty() || libraryId == null) {
            return ruleJson;
        }
        try {
            RulePayload rule = objectMapper.readValue(ruleJson, RulePayload.class);
            if (rule == null) {
                return ruleJson;
            }
            Long online = extMapper.selectOnlineVersionId(libraryId);
            if (online == null) {
                return ruleJson; // 数据集未上线，无法确定基线，保持原样
            }
            rule.setDatasetVersionId(online);
            return objectMapper.writeValueAsString(rule);
        } catch (Exception e) {
            log.warn("写入规则版本基线失败: {}", e.getMessage());
            return ruleJson;
        }
    }

    /**
     * 版本漂移检测：规则基于的版本与当前在线版本不一致时返回告警。
     * 前端提交的规则通常不带版本基线，此时回退读取库中已保存规则的基线。
     */
    private String checkVersionDrift(Long groupId, Long libraryId, RulePayload rule) {
        if (rule == null) {
            return null;
        }
        Long baseline = rule.getDatasetVersionId();
        if (baseline == null && groupId != null) {
            TlObjectGroup saved = groupMapper.selectObjectGroupById(groupId);
            if (saved != null && saved.getRuleJson() != null) {
                try {
                    RulePayload savedRule = objectMapper.readValue(saved.getRuleJson(), RulePayload.class);
                    baseline = savedRule == null ? null : savedRule.getDatasetVersionId();
                } catch (Exception e) {
                    log.warn("解析已保存规则失败: {}", e.getMessage());
                }
            }
        }
        if (baseline == null) {
            return null; // 历史规则无基线，不告警
        }
        Long online = extMapper.selectOnlineVersionId(libraryId);
        if (online == null || online.equals(baseline)) {
            return null;
        }
        return "数据集已重发布（规则基于版本 " + baseline + "，当前在线版本 " + online
                + "），运行口径可能已变化，请确认规则字段后重新保存";
    }

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
    private long executeCount(String sql, Long libraryId, RulePayload rule) {
        try (Connection conn = openConnection(libraryId)) {
            try {
                hydrateImportTempTables(conn, rule);
                try (Statement stmt = conn.createStatement()) {
                    stmt.setQueryTimeout(Math.max(1, properties.getJdbc().getSocketTimeout() / 1000));
                    try (ResultSet rs = stmt.executeQuery(sql)) {
                        return rs.next() ? rs.getLong(1) : 0L;
                    }
                }
            } finally {
                dropImportTempTables(conn, rule);
            }
        } catch (ServiceException e) {
            throw e;
        } catch (Exception e) {
            // 外部库 SQL 异常原文含库表/列名等内部细节，只进服务端日志，前端给通用提示
            log.error("对象群规则 COUNT 查询失败, libraryId={}", libraryId, e);
            throw new ServiceException("查询数据源失败，请检查外部数据源后重试");
        }
    }

    /** 执行 SELECT 预览（客户号 + 预览列） */
    private Map<String, Object> executeSelect(String sql, Long libraryId, RulePayload rule) {
        List<String> columns = new ArrayList<>();
        List<Map<String, Object>> rows = new ArrayList<>();
        try (Connection conn = openConnection(libraryId)) {
            try {
                hydrateImportTempTables(conn, rule);
                try (Statement stmt = conn.createStatement()) {
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
                }
            } finally {
                dropImportTempTables(conn, rule);
            }
        } catch (ServiceException e) {
            throw e;
        } catch (Exception e) {
            // 外部库 SQL 异常原文含库表/列名等内部细节，只进服务端日志，前端给通用提示
            log.error("对象群样例预览查询失败, libraryId={}", libraryId, e);
            throw new ServiceException("查询数据源失败，请检查外部数据源后重试");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("columns", columns);
        result.put("rows", rows);
        return result;
    }

    /**
     * 把规则中的导入批次值装载进目标库 session 临时表（须与主查询同一连接），
     * 替代把数万条值内联成巨型 IN 的旧方案
     */
    private void hydrateImportTempTables(Connection conn, RulePayload rule) throws Exception {
        if (rule == null || rule.getConditions() == null) {
            return;
        }
        for (RulePayload.Condition c : rule.getConditions()) {
            if (!"import".equals(c.getMatchType())) {
                continue;
            }
            String batchNo = c.getImportBatchNo();
            if (batchNo == null || batchNo.isEmpty()) {
                throw new ServiceException("客户号导入批次缺失");
            }
            String tableRef = RuleSqlBuilder.importTempTableRef(batchNo);
            List<String> values = importMapper.selectValuesByBatch(batchNo);
            if (values == null || values.isEmpty()) {
                throw new ServiceException("导入批次无数据，请重新导入");
            }
            if (values.size() > MAX_IMPORT_COUNT) {
                throw new ServiceException("导入值超过上限（5万条），请拆分后重新导入");
            }
            try (Statement stmt = conn.createStatement()) {
                stmt.execute("drop temporary table if exists " + tableRef);
                stmt.execute("create temporary table " + tableRef
                        + " (`v` varchar(64) not null, key `idx_v` (`v`))");
            }
            String insertHead = "insert into " + tableRef + " (`v`) values ";
            for (int i = 0; i < values.size(); i += TEMP_LOAD_CHUNK) {
                int end = Math.min(i + TEMP_LOAD_CHUNK, values.size());
                StringBuilder sb = new StringBuilder(insertHead);
                for (int j = i; j < end; j++) {
                    if (j > i) {
                        sb.append(",");
                    }
                    sb.append("(?)");
                }
                try (PreparedStatement ps = conn.prepareStatement(sb.toString())) {
                    for (int j = i; j < end; j++) {
                        ps.setString(j - i + 1, values.get(j));
                    }
                    ps.executeUpdate();
                }
            }
        }
    }

    /** 释放本连接上装载的导入临时表（连接可能被池化复用，session 表需显式清理） */
    private void dropImportTempTables(Connection conn, RulePayload rule) {
        if (conn == null || rule == null || rule.getConditions() == null) {
            return;
        }
        for (RulePayload.Condition c : rule.getConditions()) {
            if (!"import".equals(c.getMatchType())) {
                continue;
            }
            String batchNo = c.getImportBatchNo();
            if (batchNo == null || batchNo.isEmpty()) {
                continue;
            }
            try (Statement stmt = conn.createStatement()) {
                stmt.execute("drop temporary table if exists " + RuleSqlBuilder.importTempTableRef(batchNo));
            } catch (Exception e) {
                log.warn("清理导入临时表失败: batch={}, {}", batchNo, e.getMessage());
            }
        }
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
            return connectionFactory.createConnection(ds, password);
        } catch (Exception e) {
            throw new ServiceException("连接数据源失败：" + e.getMessage());
        }
    }
}
