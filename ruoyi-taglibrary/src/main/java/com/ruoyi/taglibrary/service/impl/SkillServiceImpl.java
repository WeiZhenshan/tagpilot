package com.ruoyi.taglibrary.service.impl;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.domain.TlObjectGroup;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.mapper.TlObjectGroupImportMapper;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;
import com.ruoyi.objectgroup.service.ITlObjectGroupService;
import com.ruoyi.objectgroup.service.impl.RuleSqlBuilder;
import com.ruoyi.taglibrary.domain.TlSkillAudit;
import com.ruoyi.taglibrary.domain.TlSkillRun;
import com.ruoyi.taglibrary.domain.dto.SkillRunRequest;
import com.ruoyi.taglibrary.domain.dto.SkillStatusRequest;
import com.ruoyi.taglibrary.mapper.TlSkillAuditMapper;
import com.ruoyi.taglibrary.mapper.TlSkillRunMapper;
import com.ruoyi.taglibrary.service.ISkillService;
import com.ruoyi.taglibrary.service.SkillClient;

/**
 * 洞察Skill治理服务实现。
 *
 * <p>列表/详情/版本/状态流转代理 Python 技能引擎；试运行额外复用对象群规则引擎解析客群成员，
 * 全部写操作留存审计或运行记录。</p>
 */
@Service
public class SkillServiceImpl implements ISkillService {

    private static final Logger log = LoggerFactory.getLogger(SkillServiceImpl.class);

    /** 客群成员上限（与契约一致） */
    private static final int MAX_MEMBERS = 100000;

    /** 导入批次值装载分片行数（与对象群一致） */
    private static final int TEMP_LOAD_CHUNK = 1000;

    /** 允许的状态流转动作 */
    private static final List<String> ACTIONS = java.util.Arrays.asList("publish", "offline", "deprecate", "draft");

    /** 技能ID白名单：进入 URL 路径前先校验，避免路径注入 */
    private static final Pattern SKILL_ID_PATTERN = Pattern.compile("[A-Za-z0-9_-]{1,64}");

    @Autowired private SkillClient skillClient;
    @Autowired private TlSkillRunMapper runMapper;
    @Autowired private TlSkillAuditMapper auditMapper;
    @Autowired private ITlObjectGroupService objectGroups;
    @Autowired private IRuleSqlBuilder ruleSqlBuilder;
    @Autowired private TlObjectGroupExtMapper objectGroupExtMapper;
    @Autowired private TlObjectGroupImportMapper objectGroupImportMapper;
    @Autowired private DpOnlineVersionResolver versionResolver;
    @Autowired private JdbcConnectionFactory connectionFactory;
    @Autowired private DataBrokerCryptoService cryptoService;
    @Autowired private DataBrokerProperties dataBrokerProperties;
    @Autowired private ObjectMapper objectMapper;

    // ---- 列表与详情 ----

    @Override
    public Map<String, Object> listSkills(String status, String category, String keyword, Integer limit, Integer offset) {
        Map<String, String> query = new LinkedHashMap<String, String>();
        query.put("status", status);
        query.put("category", category);
        query.put("keyword", keyword);
        // 管理员不做权限收敛；其他用户把权限集透传给引擎并按需在本地二次过滤
        if (!hasAllPermission()) {
            query.put("permissions", String.join(",", currentPermissions()));
        }
        query.put("limit", limit == null ? null : String.valueOf(limit));
        query.put("offset", offset == null ? null : String.valueOf(offset));
        Map<String, Object> result = skillClient.get("/skills", query);
        filterByPermission(result);
        return result;
    }

    @Override
    public Map<String, Object> getSkill(String skillId, String version) {
        validateSkillId(skillId);
        Map<String, String> query = new LinkedHashMap<String, String>();
        query.put("version", version);
        return skillClient.get("/skills/" + skillId, query);
    }

    @Override
    public Map<String, Object> listVersions(String skillId) {
        validateSkillId(skillId);
        return skillClient.get("/skills/" + skillId + "/versions");
    }

    // ---- 状态流转 ----

    @Override
    public Map<String, Object> changeStatus(String skillId, SkillStatusRequest request) {
        validateSkillId(skillId);
        if (request == null || request.getAction() == null || !ACTIONS.contains(request.getAction())) {
            throw new ServiceException("不支持的技能状态动作");
        }
        String reason = request.getReason() == null ? "" : request.getReason().trim();
        if (reason.isEmpty()) {
            throw new ServiceException("请填写操作原因");
        }
        String operatorId = String.valueOf(SecurityUtils.getUserId());
        String operatorName = operatorName();

        Map<String, Object> body = new LinkedHashMap<String, Object>();
        body.put("action", request.getAction());
        body.put("version", request.getVersion());
        body.put("operator_id", operatorId);
        body.put("operator_name", operatorName);
        body.put("reason", reason);
        try {
            Map<String, Object> result = skillClient.post("/skills/" + skillId + "/status", body);
            writeAudit(skillId, request.getVersion(), request.getAction(), operatorId, operatorName, reason, text(result.get("status")));
            return result;
        } catch (ServiceException e) {
            // 失败同样留痕，但审计写入异常不得掩盖原始错误
            writeAudit(skillId, request.getVersion(), request.getAction(), operatorId, operatorName, reason, "失败：" + e.getMessage());
            throw e;
        }
    }

    // ---- 试运行 ----

    @Override
    public Map<String, Object> runSkill(String skillId, SkillRunRequest request) {
        validateSkillId(skillId);
        if (request == null || request.getGroupId() == null) {
            throw new ServiceException("请选择要试运行的客群");
        }
        TlObjectGroup group = objectGroups.selectObjectGroupById(request.getGroupId());
        if (group == null) {
            throw new ServiceException("客群不存在或已删除");
        }
        List<String> members = resolveMembers(group);
        if (members.isEmpty()) {
            throw new ServiceException("客群成员为空，请先完善客群规则并统计人数", 422);
        }

        String operatorId = String.valueOf(SecurityUtils.getUserId());
        String operatorName = operatorName();
        Map<String, Object> body = new LinkedHashMap<String, Object>();
        body.put("audience_id", String.valueOf(group.getGroupId()));
        body.put("audience_name", group.getGroupName());
        body.put("member_ids", members);
        if (notBlank(request.getAsOfDate())) {
            body.put("as_of_date", request.getAsOfDate().trim());
        }
        if (notBlank(request.getBenchmarkType())) {
            body.put("benchmark_type", request.getBenchmarkType().trim());
        }
        if (request.getParams() != null && !request.getParams().isEmpty()) {
            body.put("params", request.getParams());
        }
        body.put("operator_id", operatorId);
        body.put("operator_name", operatorName);
        body.put("permissions", new ArrayList<String>(currentPermissions()));

        Map<String, Object> result = skillClient.post("/skills/" + skillId + "/run", body);
        saveRun(skillId, group, members.size(), operatorId, operatorName, result);
        return result;
    }

    @Override
    public List<TlSkillRun> listRuns(TlSkillRun query) {
        return runMapper.selectRunList(query);
    }

    // ---- 客群成员解析 ----

    /**
     * 解析客群成员：按 groupId 取 rule_json → 复用对象群规则引擎生成 MODE_SELECT SQL → 取客户号列表。
     * 客群不存在或成员为空由调用方按业务口径处理（空即 422）。
     */
    private List<String> resolveMembers(TlObjectGroup group) {
        String ruleJson = group.getRuleJson();
        if (ruleJson == null || ruleJson.trim().isEmpty()) {
            throw new ServiceException("客群规则为空，无法解析成员");
        }
        Long libraryId = group.getLibraryId();
        if (libraryId == null) {
            throw new ServiceException("客群未关联标签库，无法解析成员");
        }
        RulePayload rule;
        try {
            rule = objectMapper.readValue(ruleJson, RulePayload.class);
        } catch (Exception e) {
            throw new ServiceException("客群规则解析失败，请联系客群维护人");
        }
        if (rule == null) {
            throw new ServiceException("客群规则为空，无法解析成员");
        }
        // 复用对象群规则引擎做权威校验（含 V4 发布方案核验），校验通过后 rule.authorityValidated=true
        objectGroups.buildRuleSql(libraryId, rule);

        Long datasetId = objectGroupExtMapper.selectDatasetIdByLibrary(libraryId);
        if (datasetId == null) {
            throw new ServiceException("客群关联的标签库未关联数据集");
        }
        DpResolvedVersion version = versionResolver.resolve(datasetId);
        if (version == null) {
            throw new ServiceException("客群关联的数据集不存在或未上线");
        }
        // 只取客户号列：清空预览列，避免取回冗余字段
        rule.setPreviewColumns(null);
        String sql = ruleSqlBuilder.buildSql(version.getVersionId(), rule, IRuleSqlBuilder.MODE_SELECT);
        sql = applyMemberLimit(sql, MAX_MEMBERS + 1);
        return executeMemberQuery(sql, datasetId, rule);
    }

    /**
     * 对象群预览 SQL 固定 LIMIT 100，这里改写为成员上限（多取 1 条用于判断是否超限）。
     * 若上游 SQL 形态变化导致尾部没有 limit，则直接追加，仍受同一上限约束。
     */
    private String applyMemberLimit(String sql, int limit) {
        String stripped = sql.trim().replaceAll("(?is)\\s+limit\\s+\\d+\\s*$", "");
        return stripped + " limit " + limit;
    }

    /** 在客群数据源上执行成员查询，返回客户号字符串列表（上限 10 万） */
    private List<String> executeMemberQuery(String sql, Long datasetId, RulePayload rule) {
        try {
            DpDataSource dataSource = objectGroupExtMapper.selectDataSourceByDataset(datasetId);
            if (dataSource == null) {
                throw new ServiceException("客群数据集的数据源不存在");
            }
            // 数据源口令解密失败属配置问题，必须转成中文提示而非裸异常
            String password = dataSource.getPasswordCipher() == null || dataSource.getPasswordCipher().isEmpty()
                    ? "" : cryptoService.decrypt(dataSource.getPasswordCipher());
            try (Connection conn = connectionFactory.createConnection(dataSource, password)) {
                try {
                    hydrateImportTempTables(conn, rule);
                    try (Statement stmt = conn.createStatement()) {
                        stmt.setQueryTimeout(Math.max(1, dataBrokerProperties.getJdbc().getSocketTimeout() / 1000));
                        try (ResultSet rs = stmt.executeQuery(sql)) {
                            List<String> ids = new ArrayList<String>();
                            while (rs.next()) {
                                Object value = rs.getObject(1);
                                if (value == null) {
                                    continue;
                                }
                                String id = String.valueOf(value).trim();
                                if (id.isEmpty()) {
                                    continue;
                                }
                                ids.add(id);
                                if (ids.size() > MAX_MEMBERS) {
                                    throw new ServiceException("客群成员超过上限 10 万，请缩小客群范围后再试");
                                }
                            }
                            return ids;
                        }
                    }
                } finally {
                    dropImportTempTables(conn, rule);
                }
            }
        } catch (ServiceException e) {
            throw e;
        } catch (Exception e) {
            // 外部库异常原文含库表列名，只进服务端日志
            log.error("解析客群成员失败, datasetId={}", datasetId, e);
            throw new ServiceException("解析客群成员失败，请检查客群数据源连通性与加密密钥配置");
        }
    }

    /** 把客户号导入批次装载进客群数据源的 session 临时表（须与主查询同一连接） */
    private void hydrateImportTempTables(Connection conn, RulePayload rule) throws Exception {
        if (rule == null || rule.getConditions() == null) {
            return;
        }
        for (RulePayload.Condition condition : rule.getConditions()) {
            if (!"import".equals(condition.getMatchType())) {
                continue;
            }
            String batchNo = condition.getImportBatchNo();
            if (batchNo == null || batchNo.isEmpty()) {
                throw new ServiceException("客群客户号导入批次缺失");
            }
            String tableRef = RuleSqlBuilder.importTempTableRef(batchNo);
            List<String> values = objectGroupImportMapper.selectValuesByBatch(batchNo);
            if (values == null || values.isEmpty()) {
                throw new ServiceException("客群导入批次无数据，请重新导入");
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

    /** 释放本连接上装载的导入临时表（连接可能被池化复用） */
    private void dropImportTempTables(Connection conn, RulePayload rule) {
        if (conn == null || rule == null || rule.getConditions() == null) {
            return;
        }
        for (RulePayload.Condition condition : rule.getConditions()) {
            if (!"import".equals(condition.getMatchType())) {
                continue;
            }
            String batchNo = condition.getImportBatchNo();
            if (batchNo == null || batchNo.isEmpty()) {
                continue;
            }
            try (Statement stmt = conn.createStatement()) {
                stmt.execute("drop temporary table if exists " + RuleSqlBuilder.importTempTableRef(batchNo));
            } catch (Exception e) {
                log.warn("清理客群导入临时表失败: batch={}, {}", batchNo, e.getMessage());
            }
        }
    }

    // ---- 落库与审计 ----

    /** 把引擎返回的关键字段落到 tl_skill_run，供权限化的运行历史查询 */
    @SuppressWarnings("unchecked")
    private void saveRun(String skillId, TlObjectGroup group, int memberCount,
                         String operatorId, String operatorName, Map<String, Object> result) {
        TlSkillRun row = new TlSkillRun();
        String runId = text(result.get("run_id"));
        row.setRunId(runId == null || runId.isEmpty()
                ? UUID.randomUUID().toString().replace("-", "") : runId);
        row.setSkillId(skillId);
        row.setSkillVersion(text(result.get("skill_version")));
        row.setAudienceId(String.valueOf(group.getGroupId()));
        row.setAudienceName(group.getGroupName());
        Object audienceObj = result.get("audience");
        int customerCount = memberCount;
        if (audienceObj instanceof Map) {
            Object count = ((Map<String, Object>) audienceObj).get("customer_count");
            if (count != null) {
                customerCount = asInt(count, memberCount);
            }
        }
        row.setCustomerCount(customerCount);
        row.setStatus(text(result.get("status")));
        row.setBlockedReason(text(result.get("blocked_reason")));
        Object duration = result.get("duration_ms");
        row.setDurationMs(duration == null ? null : asLong(duration));
        row.setOperatorId(operatorId);
        row.setOperatorName(operatorName);
        row.setTraceId(text(result.get("trace_id")));
        try {
            runMapper.insertRun(row);
        } catch (Exception e) {
            log.error("Skill 运行记录落库失败: skill={}", skillId, e);
            throw new ServiceException("运行结果已生成，但运行记录保存失败，请联系管理员");
        }
    }

    /** 写管理动作审计；审计失败只记录日志，绝不掩盖业务结果 */
    private void writeAudit(String skillId, String version, String action, String operatorId,
                            String operatorName, String reason, String result) {
        TlSkillAudit audit = new TlSkillAudit();
        audit.setSkillId(skillId);
        audit.setVersion(version);
        audit.setAction(action);
        audit.setOperatorId(operatorId);
        audit.setOperatorName(operatorName);
        audit.setReason(reason);
        audit.setResult(result);
        try {
            auditMapper.insertAudit(audit);
        } catch (Exception e) {
            log.warn("Skill 审计写入失败: skill={}, action={}, {}", skillId, action, e.getMessage());
        }
    }

    // ---- 权限 ----

    /** 管理员（拥有全部权限）不做技能可见性收敛 */
    private boolean hasAllPermission() {
        return currentPermissions().contains(Constants.ALL_PERMISSION);
    }

    private Set<String> currentPermissions() {
        return SecurityUtils.getLoginUser().getPermissions();
    }

    /**
     * 本地权限过滤：非管理员仅保留"至少持有一项 required_permissions"的技能，
     * 与引擎侧过滤形成双重收敛，避免越权可见。
     */
    @SuppressWarnings("unchecked")
    private void filterByPermission(Map<String, Object> result) {
        if (hasAllPermission()) {
            return;
        }
        Object itemsObj = result.get("items");
        if (!(itemsObj instanceof List)) {
            return;
        }
        Set<String> granted = currentPermissions();
        List<Object> kept = new ArrayList<Object>();
        for (Object item : (List<Object>) itemsObj) {
            if (item instanceof Map) {
                Object required = ((Map<String, Object>) item).get("required_permissions");
                if (required instanceof List && !((List<Object>) required).isEmpty()) {
                    boolean hit = false;
                    for (Object permission : (List<Object>) required) {
                        if (granted.contains(String.valueOf(permission))) {
                            hit = true;
                            break;
                        }
                    }
                    if (!hit) {
                        continue;
                    }
                }
            }
            kept.add(item);
        }
        result.put("items", kept);
        result.put("total", kept.size());
    }

    // ---- 小工具 ----

    private void validateSkillId(String skillId) {
        if (skillId == null || !SKILL_ID_PATTERN.matcher(skillId).matches()) {
            throw new ServiceException("技能ID不合法");
        }
    }

    private String operatorName() {
        String nickName = SecurityUtils.getLoginUser().getUser().getNickName();
        return nickName == null || nickName.isEmpty() ? SecurityUtils.getUsername() : nickName;
    }

    private boolean notBlank(String value) {
        return value != null && !value.trim().isEmpty();
    }

    private String text(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private int asInt(Object value, int fallback) {
        try {
            return Integer.parseInt(String.valueOf(value).trim());
        } catch (Exception e) {
            return fallback;
        }
    }

    private long asLong(Object value) {
        try {
            return Long.parseLong(String.valueOf(value).trim());
        } catch (Exception e) {
            return 0L;
        }
    }
}
