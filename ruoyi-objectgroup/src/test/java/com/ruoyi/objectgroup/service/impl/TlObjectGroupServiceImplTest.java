package com.ruoyi.objectgroup.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.core.domain.entity.SysUser;
import com.ruoyi.common.core.domain.model.LoginUser;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.framework.web.service.PermissionService;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.domain.TlObjectGroup;
import com.ruoyi.objectgroup.domain.TlObjectGroupImport;
import com.ruoyi.objectgroup.domain.vo.RuleRunResultVO;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.mapper.TlObjectGroupImportMapper;
import com.ruoyi.objectgroup.mapper.TlObjectGroupMapper;
import com.ruoyi.objectgroup.service.IDimensionCodeOptionService;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;

/**
 * 对象群 Service 单元测试：客户号导入链路（BOM/分片落库、临时表装载 + join 执行）、
 * 在线版本单次解析、统一标签校验接入、样例预览中文副本
 */
@ExtendWith(MockitoExtension.class)
class TlObjectGroupServiceImplTest {

    private static final Long LIBRARY_ID = 7L;
    private static final Long DATASET_ID = 100L;
    private static final Long VERSION_ID = 11L;
    /** parseImportFile 生成的 32 位十六进制批次号 */
    private static final String BATCH = "0123456789abcdef0123456789abcdef";

    @Mock
    private TlObjectGroupMapper groupMapper;
    @Mock
    private TlObjectGroupImportMapper importMapper;
    @Mock
    private TlObjectGroupExtMapper extMapper;
    @Mock
    private IRuleSqlBuilder ruleSqlBuilder;
    @Mock
    private JdbcConnectionFactory connectionFactory;
    @Mock
    private DataBrokerCryptoService cryptoService;
    @Mock
    private DpDataSourceMapper dataSourceMapper;
    @Mock
    private DataBrokerProperties properties;
    @Mock
    private DataBrokerProperties.Jdbc jdbc;
    @Mock
    private PermissionService permissionService;
    @Mock
    private DpOnlineVersionResolver onlineVersionResolver;
    @Mock
    private RuleTagValidator ruleTagValidator;
    @Mock
    private IDimensionCodeOptionService dimensionCodeOptionService;

    @Spy
    private ObjectMapper objectMapper = new ObjectMapper();

    @InjectMocks
    private TlObjectGroupServiceImpl service;

    @BeforeEach
    void setUpSecurityContext() {
        SysUser sysUser = new SysUser();
        sysUser.setUserId(1L);
        sysUser.setUserName("admin");
        LoginUser loginUser = new LoginUser(sysUser, Collections.emptySet());
        UsernamePasswordAuthenticationToken authentication =
                new UsernamePasswordAuthenticationToken(loginUser, null, Collections.emptyList());
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    private RulePayload importRule(String batchNo) {
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        RulePayload.Condition c = new RulePayload.Condition();
        c.setFieldName("cust");
        c.setTagType("客户号");
        c.setMatchType("import");
        c.setImportBatchNo(batchNo);
        rule.setConditions(Collections.singletonList(c));
        return rule;
    }

    /** mock 在线版本解析：libraryId → datasetId → 指定版本 */
    private void mockOnlineVersion(long versionId) {
        when(extMapper.selectDatasetIdByLibrary(LIBRARY_ID)).thenReturn(DATASET_ID);
        DpResolvedVersion version = new DpResolvedVersion();
        version.setDatasetId(DATASET_ID);
        version.setVersionId(versionId);
        when(onlineVersionResolver.resolve(DATASET_ID)).thenReturn(version);
    }

    /** mock 打开目标库连接的完整链路，返回 mock 连接 */
    private Connection mockOpenConnection() throws Exception {
        Connection conn = mock(Connection.class);
        DpDataSource ds = new DpDataSource();
        ds.setDatasourceId(1L);
        ds.setHost("127.0.0.1");
        ds.setPort(3306);
        ds.setDatabaseName("dw");
        ds.setUsername("root");
        ds.setPasswordCipher("cipher");
        when(extMapper.selectDataSourceByDataset(DATASET_ID)).thenReturn(ds);
        when(cryptoService.decrypt("cipher")).thenReturn("pwd");
        when(connectionFactory.createConnection(any(DpDataSource.class), anyString())).thenReturn(conn);
        // 直接携带 libraryId+规则 的运行/预览默认放行；组内规则刷新路径不触发该权限点
        lenient().when(permissionService.hasAnyPermi(anyString())).thenReturn(true);
        return conn;
    }

    // ==================== 导入文件解析 ====================

    @Test
    void txt导入剥离首行BOM并去重() throws Exception {
        byte[] bytes = ("﻿C001\nC002\nC002\nC003\n").getBytes(StandardCharsets.UTF_8);
        MockMultipartFile file = new MockMultipartFile("file", "c.txt", "text/plain", bytes);

        Map<String, Object> result = service.parseImportFile(file, "cust");

        String batchNo = (String) result.get("batchNo");
        assertTrue(batchNo.matches("^[0-9a-f]{32}$"), "批次号应为32位十六进制，实际：" + batchNo);
        assertEquals(3L, result.get("total"));
        ArgumentCaptor<List<TlObjectGroupImport>> captor = ArgumentCaptor.forClass(List.class);
        verify(importMapper).insertBatch(captor.capture());
        List<TlObjectGroupImport> rows = captor.getValue();
        assertEquals(3, rows.size());
        assertEquals("C001", rows.get(0).getValue());
        assertFalse(rows.get(0).getValue().contains("﻿"), "BOM 应被剥离");
    }

    @Test
    void csv导入取首列且超1000条按分片写入() throws Exception {
        StringBuilder sb = new StringBuilder("﻿");
        for (int i = 1; i <= 1001; i++) {
            sb.append("V").append(String.format("%04d", i)).append(",备注列\n");
        }
        sb.append("V0002,重复行\n"); // 重复值去重，不计入条数
        MockMultipartFile file = new MockMultipartFile("file", "c.csv", "text/csv",
                sb.toString().getBytes(StandardCharsets.UTF_8));

        Map<String, Object> result = service.parseImportFile(file, "cust");

        assertEquals(1001L, result.get("total"));
        ArgumentCaptor<List<TlObjectGroupImport>> captor = ArgumentCaptor.forClass(List.class);
        verify(importMapper, times(2)).insertBatch(captor.capture());
        List<List<TlObjectGroupImport>> calls = captor.getAllValues();
        assertEquals(1000, calls.get(0).size());
        assertEquals(1, calls.get(1).size());
        // 第一列截断 + BOM 剥离
        assertEquals("V0001", calls.get(0).get(0).getValue());
        assertEquals("V1001", calls.get(1).get(0).getValue());
        for (TlObjectGroupImport row : calls.get(0)) {
            assertFalse(row.getValue().contains("﻿"));
            assertFalse(row.getValue().contains(","));
        }
    }

    @Test
    void 超过64字符的客户号被拒绝() throws Exception {
        String longValue = new String(new char[65]).replace('\0', 'X');
        MockMultipartFile file = new MockMultipartFile("file", "c.txt", "text/plain",
                (longValue + "\n").getBytes(StandardCharsets.UTF_8));

        ServiceException e = assertThrows(ServiceException.class, () -> service.parseImportFile(file, "cust"));
        assertTrue(e.getMessage().contains("长度超过"), e.getMessage());
        verify(importMapper, never()).insertBatch(anyList());
    }

    // ==================== 规则运行（临时表 join） ====================

    @Test
    void 导入条件先装载临时表再执行join且查询SQL不内联值() throws Exception {
        mockOnlineVersion(VERSION_ID);
        Connection conn = mockOpenConnection();
        Statement stmt = mock(Statement.class);
        PreparedStatement ps = mock(PreparedStatement.class);
        ResultSet rs = mock(ResultSet.class);
        when(conn.createStatement()).thenReturn(stmt);
        when(conn.prepareStatement(anyString())).thenReturn(ps);
        when(stmt.executeQuery(anyString())).thenReturn(rs);
        when(rs.next()).thenReturn(true);
        when(rs.getLong(1)).thenReturn(42L);
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(properties.getJdbc()).thenReturn(jdbc);
        when(importMapper.selectValuesByBatch(BATCH)).thenReturn(Arrays.asList("C001", "C002"));
        RulePayload rule = importRule(BATCH);
        when(ruleSqlBuilder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_COUNT))
                .thenReturn("select count(*) from `wide` where `cust_no` in (select `v` from `tmp_og_imp_" + BATCH + "`)");

        RuleRunResultVO result = service.runRule(null, LIBRARY_ID, rule);

        assertEquals(42L, result.getCount());
        assertNull(result.getWarning());
        // 统一校验先于 SQL 生成与外部连接
        verify(ruleTagValidator).validateRule(LIBRARY_ID, VERSION_ID, rule);
        verify(ruleTagValidator).validateCodeValues(LIBRARY_ID, rule);
        // 主查询引用临时表，而非内联导入值
        ArgumentCaptor<String> queryCaptor = ArgumentCaptor.forClass(String.class);
        verify(stmt).executeQuery(queryCaptor.capture());
        assertTrue(queryCaptor.getValue().contains("in (select `v` from `tmp_og_imp_" + BATCH + "`)"),
                "主查询应 join 临时表，实际：" + queryCaptor.getValue());
        assertFalse(queryCaptor.getValue().contains("C001"), "导入值不应内联进 SQL");
        // drop(装载前) + create + drop(清理) 共 3 次 DDL
        ArgumentCaptor<String> ddlCaptor = ArgumentCaptor.forClass(String.class);
        verify(stmt, times(3)).execute(ddlCaptor.capture());
        assertEquals(2, ddlCaptor.getAllValues().stream().filter(s -> s.contains("drop temporary table")).count());
        assertTrue(ddlCaptor.getAllValues().stream().anyMatch(s -> s.contains("create temporary table") && s.contains("idx_v")));
        // 装载使用参数化批量插入
        verify(ps).setString(1, "C001");
        verify(ps).setString(2, "C002");
        verify(ps).executeUpdate();
    }

    @Test
    void 导入批次无数据时运行报错且不执行查询() throws Exception {
        mockOnlineVersion(VERSION_ID);
        mockOpenConnection();
        when(importMapper.selectValuesByBatch(BATCH)).thenReturn(Collections.emptyList());

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.runRule(null, LIBRARY_ID, importRule(BATCH)));
        assertTrue(e.getMessage().contains("批次无数据"), e.getMessage());
        verify(connectionFactory, times(1)).createConnection(any(DpDataSource.class), anyString());
    }

    @Test
    void 非法批次号拒绝运行() throws Exception {
        mockOnlineVersion(VERSION_ID);
        mockOpenConnection();

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.runRule(null, LIBRARY_ID, importRule("bad'batch")));
        assertTrue(e.getMessage().contains("不合法"), e.getMessage());
        // 批次号未通过校验时不得查询本地导入表，更不建临时表
        verify(importMapper, never()).selectValuesByBatch(anyString());
        verify(connectionFactory, times(1)).createConnection(any(DpDataSource.class), anyString());
    }

    @Test
    void 预览导入条件结果集按元数据组装且生成显示副本() throws Exception {
        mockOnlineVersion(VERSION_ID);
        Connection conn = mockOpenConnection();
        Statement stmt = mock(Statement.class);
        PreparedStatement ps = mock(PreparedStatement.class);
        when(conn.createStatement()).thenReturn(stmt);
        when(conn.prepareStatement(anyString())).thenReturn(ps);
        when(importMapper.selectValuesByBatch(BATCH)).thenReturn(Collections.singletonList("C001"));
        RulePayload rule = importRule(BATCH);
        when(ruleSqlBuilder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_SELECT))
                .thenReturn("select `cust_no` from `wide` where `cust_no` in (select `v` from `tmp_og_imp_" + BATCH + ")");

        // executeQuery 需要返回带元数据的 ResultSet：列标签 cust_no + 一行 C001
        java.sql.ResultSetMetaData meta = mock(java.sql.ResultSetMetaData.class);
        ResultSet rs = mock(ResultSet.class);
        when(stmt.executeQuery(anyString())).thenReturn(rs);
        when(rs.getMetaData()).thenReturn(meta);
        when(meta.getColumnCount()).thenReturn(1);
        when(meta.getColumnLabel(1)).thenReturn("cust_no");
        when(rs.next()).thenReturn(true, false);
        when(rs.getObject(1)).thenReturn("C001");
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(properties.getJdbc()).thenReturn(jdbc);

        Map<String, Object> result = service.previewRule(null, LIBRARY_ID, rule);

        assertEquals(Collections.singletonList("cust_no"), result.get("columns"));
        List<Map<String, Object>> rows = (List<Map<String, Object>>) result.get("rows");
        assertEquals(1, rows.size());
        assertEquals("C001", rows.get(0).get("cust_no"));
        // 无选项/布尔预览列时显示副本与原始结果一致
        List<Map<String, Object>> displayRows = (List<Map<String, Object>>) result.get("displayRows");
        assertEquals(1, displayRows.size());
        assertEquals("C001", displayRows.get(0).get("cust_no"));
        assertNull(result.get("mappingNotes"));
    }

    // ==================== 统一标签校验接入 ====================

    @Test
    void 运行规则标签校验失败时不生成SQL也不连外部库() throws Exception {
        mockOnlineVersion(VERSION_ID);
        lenient().when(permissionService.hasAnyPermi(anyString())).thenReturn(true);
        RulePayload rule = importRule(BATCH);
        doThrow(new ServiceException("标签[性别]未上线，不能用于对象群"))
                .when(ruleTagValidator).validateRule(LIBRARY_ID, VERSION_ID, rule);

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.runRule(null, LIBRARY_ID, rule));

        assertTrue(e.getMessage().contains("未上线"), e.getMessage());
        verify(connectionFactory, never()).createConnection(any(DpDataSource.class), anyString());
        verify(importMapper, never()).selectValuesByBatch(anyString());
    }

    @Test
    void 运行规则失效编码校验失败时不执行查询() throws Exception {
        mockOnlineVersion(VERSION_ID);
        lenient().when(permissionService.hasAnyPermi(anyString())).thenReturn(true);
        RulePayload rule = importRule(BATCH);
        doThrow(new ServiceException("标签[性别]的码值[M]已失效，请修正后重新保存"))
                .when(ruleTagValidator).validateCodeValues(LIBRARY_ID, rule);

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.runRule(null, LIBRARY_ID, rule));

        assertTrue(e.getMessage().contains("已失效"), e.getMessage());
        verify(connectionFactory, never()).createConnection(any(DpDataSource.class), anyString());
    }

    @Test
    void 数据集未上线时运行报错且不连外部库() throws Exception {
        when(extMapper.selectDatasetIdByLibrary(LIBRARY_ID)).thenReturn(DATASET_ID);
        when(onlineVersionResolver.resolve(DATASET_ID)).thenReturn(null);
        lenient().when(permissionService.hasAnyPermi(anyString())).thenReturn(true);

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.runRule(null, LIBRARY_ID, importRule(BATCH)));

        assertTrue(e.getMessage().contains("未上线"), e.getMessage());
        verify(connectionFactory, never()).createConnection(any(DpDataSource.class), anyString());
    }

    // ==================== SQL 预览端点（可见性 + 统一校验） ====================

    @Test
    void SQL预览校验标签库可见性并返回生成结果() {
        mockOnlineVersion(VERSION_ID);
        when(permissionService.hasAnyPermi(anyString())).thenReturn(true);
        RulePayload rule = importRule(BATCH);
        when(ruleSqlBuilder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_COUNT))
                .thenReturn("select count(*) from `wide`");

        String sql = service.buildRuleSql(LIBRARY_ID, rule);

        assertEquals("select count(*) from `wide`", sql);
        verify(ruleTagValidator).validateRule(LIBRARY_ID, VERSION_ID, rule);
    }

    @Test
    void SQL预览无标签库查看权限被拒绝() {
        when(permissionService.hasAnyPermi(anyString())).thenReturn(false);

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.buildRuleSql(LIBRARY_ID, importRule(BATCH)));

        assertTrue(e.getMessage().contains("无权"), e.getMessage());
    }

    // ==================== 数据集版本基线（保存盖章 + 运行期漂移告警） ====================

    @Test
    void 保存对象群时把在线数据集版本写入规则基线() throws Exception {
        TlObjectGroup group = new TlObjectGroup();
        group.setGroupName("白金客户");
        group.setLibraryId(LIBRARY_ID);
        group.setRuleJson("{\"objectKeyField\":\"cust\",\"conditions\":[]}");
        mockOnlineVersion(9L);

        service.insertObjectGroup(group);

        verify(groupMapper).insertObjectGroup(group);
        verify(ruleTagValidator).validateRule(eq(LIBRARY_ID), eq(9L), any(RulePayload.class));
        RulePayload saved = objectMapper.readValue(group.getRuleJson(), RulePayload.class);
        assertEquals(9L, saved.getDatasetVersionId().longValue(), "保存时应盖章当前在线版本");
    }

    @Test
    void 保存对象群标签校验失败时不落库() {
        TlObjectGroup group = new TlObjectGroup();
        group.setGroupName("白金客户");
        group.setLibraryId(LIBRARY_ID);
        group.setRuleJson("{\"objectKeyField\":\"cust\",\"conditions\":[]}");
        mockOnlineVersion(9L);
        doThrow(new ServiceException("标签[性别]来源已变更待确认"))
                .when(ruleTagValidator).validateRule(eq(LIBRARY_ID), eq(9L), any(RulePayload.class));

        ServiceException e = assertThrows(ServiceException.class, () -> service.insertObjectGroup(group));

        assertTrue(e.getMessage().contains("待确认"), e.getMessage());
        verify(groupMapper, never()).insertObjectGroup(any(TlObjectGroup.class));
    }

    @Test
    void 数据集未上线但规则未引用字段时允许保存且不盖章() {
        TlObjectGroup group = new TlObjectGroup();
        group.setGroupName("空规则群");
        group.setLibraryId(LIBRARY_ID);
        group.setRuleJson("{\"conditions\":[]}");
        when(extMapper.selectDatasetIdByLibrary(LIBRARY_ID)).thenReturn(DATASET_ID);
        when(onlineVersionResolver.resolve(DATASET_ID)).thenReturn(null);

        service.insertObjectGroup(group);

        verify(groupMapper).insertObjectGroup(group);
        assertFalse(group.getRuleJson().contains("datasetVersionId"), "无在线版本时不应写入基线");
    }

    @Test
    void 刷新计数时在线版本已切换返回告警且不改写规则基线() throws Exception {
        TlObjectGroup saved = new TlObjectGroup();
        saved.setGroupId(1L);
        saved.setGroupName("白金客户");
        saved.setLibraryId(LIBRARY_ID);
        saved.setRuleJson("{\"objectKeyField\":\"cust\",\"datasetVersionId\":11,\"conditions\":[]}");
        when(groupMapper.selectObjectGroupById(1L)).thenReturn(saved);
        mockOnlineVersion(12L);
        Connection conn = mockOpenConnection();
        Statement stmt = mock(Statement.class);
        ResultSet rs = mock(ResultSet.class);
        when(conn.createStatement()).thenReturn(stmt);
        when(stmt.executeQuery(anyString())).thenReturn(rs);
        when(rs.next()).thenReturn(true);
        when(rs.getLong(1)).thenReturn(88L);
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(properties.getJdbc()).thenReturn(jdbc);
        when(ruleSqlBuilder.buildSql(eq(12L), any(RulePayload.class), eq(IRuleSqlBuilder.MODE_COUNT)))
                .thenReturn("select count(*) from `wide`");

        RuleRunResultVO result = service.runRule(1L, null, null);

        assertEquals(88L, result.getCount());
        assertNotNull(result.getWarning(), "版本切换时应返回告警");
        assertTrue(result.getWarning().contains("重发布"), result.getWarning());
        // 仅回传 groupId 的刷新执行群内已保存规则，不做请求级标签库可见性校验
        verify(permissionService, never()).hasAnyPermi(anyString());
        // 告警仅提示，回写 group_sql 时不得把新版本写成规则基线
        ArgumentCaptor<TlObjectGroup> captor = ArgumentCaptor.forClass(TlObjectGroup.class);
        verify(groupMapper).updateObjectGroup(captor.capture());
        assertTrue(captor.getValue().getRuleJson().contains("\"datasetVersionId\":11"));
        assertFalse(captor.getValue().getRuleJson().contains("\"datasetVersionId\":12"));
    }

    @Test
    void 运行规则在线版本未切换不返回告警() throws Exception {
        mockOnlineVersion(VERSION_ID);
        Connection conn = mockOpenConnection();
        Statement stmt = mock(Statement.class);
        ResultSet rs = mock(ResultSet.class);
        when(conn.createStatement()).thenReturn(stmt);
        when(stmt.executeQuery(anyString())).thenReturn(rs);
        when(rs.next()).thenReturn(true);
        when(rs.getLong(1)).thenReturn(5L);
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(properties.getJdbc()).thenReturn(jdbc);
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setDatasetVersionId(VERSION_ID);
        rule.setConditions(Collections.emptyList());
        when(ruleSqlBuilder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_COUNT))
                .thenReturn("select count(*) from `wide`");

        RuleRunResultVO result = service.runRule(null, LIBRARY_ID, rule);

        assertEquals(5L, result.getCount());
        assertNull(result.getWarning());
    }

    // ==================== 样例预览中文副本（displayRows） ====================

    @Test
    void 预览选项型列生成中文显示副本且未映射码值附提示() throws Exception {
        mockOnlineVersion(VERSION_ID);
        Connection conn = mockOpenConnection();
        Statement stmt = mock(Statement.class);
        when(conn.createStatement()).thenReturn(stmt);
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(properties.getJdbc()).thenReturn(jdbc);
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setConditions(Collections.emptyList());
        RulePayload.PreviewColumn pc = new RulePayload.PreviewColumn();
        pc.setFieldName("sex");
        pc.setTagName("性别");
        pc.setTagType("选项型");
        rule.setPreviewColumns(Collections.singletonList(pc));
        when(ruleSqlBuilder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_SELECT))
                .thenReturn("select `cust_no`, `sex_code` as `性别` from `wide`");

        java.sql.ResultSetMetaData meta = mock(java.sql.ResultSetMetaData.class);
        ResultSet rs = mock(ResultSet.class);
        when(stmt.executeQuery(anyString())).thenReturn(rs);
        when(rs.getMetaData()).thenReturn(meta);
        when(meta.getColumnCount()).thenReturn(2);
        when(meta.getColumnLabel(1)).thenReturn("cust_no");
        when(meta.getColumnLabel(2)).thenReturn("性别");
        when(rs.next()).thenReturn(true, true, false);
        when(rs.getObject(1)).thenReturn("C001", "C002");
        when(rs.getObject(2)).thenReturn("1", "9");
        // 码表只有 1→男；9 无映射
        when(dimensionCodeOptionService.listCodeOptions(LIBRARY_ID, "sex")).thenReturn(
                Collections.singletonList(new java.util.LinkedHashMap<String, Object>() {{
                    put("code", "1");
                    put("codeDefinition", "男");
                }}));

        Map<String, Object> result = service.previewRule(null, LIBRARY_ID, rule);

        // 原始 rows 保留编码
        List<Map<String, Object>> rows = (List<Map<String, Object>>) result.get("rows");
        assertEquals("1", rows.get(0).get("性别"));
        assertEquals("9", rows.get(1).get("性别"));
        // 显示副本翻译中文，未映射显示原码并附提示
        List<Map<String, Object>> displayRows = (List<Map<String, Object>>) result.get("displayRows");
        assertEquals("男", displayRows.get(0).get("性别"));
        assertEquals("9（未映射）", displayRows.get(1).get("性别"));
        List<Map<String, String>> notes = (List<Map<String, String>>) result.get("mappingNotes");
        assertNotNull(notes);
        assertTrue(notes.stream().anyMatch(n -> "性别".equals(n.get("column")) && n.get("message").contains("9")),
                "应提示未映射码值，实际：" + notes);
    }

    @Test
    void 预览码表查询失败时显示副本保留原码且不影响原始结果() throws Exception {
        mockOnlineVersion(VERSION_ID);
        Connection conn = mockOpenConnection();
        Statement stmt = mock(Statement.class);
        when(conn.createStatement()).thenReturn(stmt);
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(properties.getJdbc()).thenReturn(jdbc);
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setConditions(Collections.emptyList());
        RulePayload.PreviewColumn pc = new RulePayload.PreviewColumn();
        pc.setFieldName("sex");
        pc.setTagName("性别");
        pc.setTagType("选项型");
        rule.setPreviewColumns(Collections.singletonList(pc));
        when(ruleSqlBuilder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_SELECT))
                .thenReturn("select `cust_no`, `sex_code` as `性别` from `wide`");

        java.sql.ResultSetMetaData meta = mock(java.sql.ResultSetMetaData.class);
        ResultSet rs = mock(ResultSet.class);
        when(stmt.executeQuery(anyString())).thenReturn(rs);
        when(rs.getMetaData()).thenReturn(meta);
        when(meta.getColumnCount()).thenReturn(2);
        when(meta.getColumnLabel(1)).thenReturn("cust_no");
        when(meta.getColumnLabel(2)).thenReturn("性别");
        when(rs.next()).thenReturn(true, false);
        when(rs.getObject(1)).thenReturn("C001");
        when(rs.getObject(2)).thenReturn("1");
        when(dimensionCodeOptionService.listCodeOptions(LIBRARY_ID, "sex"))
                .thenThrow(new ServiceException("码值选项查询失败：连接超时"));

        Map<String, Object> result = service.previewRule(null, LIBRARY_ID, rule);

        List<Map<String, Object>> rows = (List<Map<String, Object>>) result.get("rows");
        assertEquals("1", rows.get(0).get("性别"));
        List<Map<String, Object>> displayRows = (List<Map<String, Object>>) result.get("displayRows");
        assertEquals("1", displayRows.get(0).get("性别"), "翻译失败时显示副本保留原码");
        List<Map<String, String>> notes = (List<Map<String, String>>) result.get("mappingNotes");
        assertNotNull(notes);
        assertTrue(notes.stream().anyMatch(n -> n.get("message").contains("码表查询失败")), "实际：" + notes);
    }

    // ==================== 外部 SQL 异常脱敏 ====================

    @Test
    void 运行规则外部SQL异常脱敏为通用提示() throws Exception {
        mockOnlineVersion(VERSION_ID);
        Connection conn = mockOpenConnection();
        Statement stmt = mock(Statement.class);
        when(conn.createStatement()).thenReturn(stmt);
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(properties.getJdbc()).thenReturn(jdbc);
        when(stmt.executeQuery(anyString()))
                .thenThrow(new java.sql.SQLException("Table 'dw.wide' doesn't exist"));
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setConditions(Collections.emptyList());
        when(ruleSqlBuilder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_COUNT))
                .thenReturn("select count(*) from `wide`");

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.runRule(null, LIBRARY_ID, rule));

        assertTrue(e.getMessage().contains("查询数据源失败"), e.getMessage());
        assertFalse(e.getMessage().contains("wide"), "外部库表名不得泄露给前端");
    }

    @Test
    void 样例预览外部SQL异常脱敏为通用提示() throws Exception {
        mockOnlineVersion(VERSION_ID);
        Connection conn = mockOpenConnection();
        Statement stmt = mock(Statement.class);
        when(conn.createStatement()).thenReturn(stmt);
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(properties.getJdbc()).thenReturn(jdbc);
        when(stmt.executeQuery(anyString()))
                .thenThrow(new java.sql.SQLException("Unknown column 'cust_no' in 'field list'"));
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setConditions(Collections.emptyList());
        when(ruleSqlBuilder.buildSql(VERSION_ID, rule, IRuleSqlBuilder.MODE_SELECT))
                .thenReturn("select `cust_no` from `wide`");

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.previewRule(null, LIBRARY_ID, rule));

        assertTrue(e.getMessage().contains("查询数据源失败"), e.getMessage());
        assertFalse(e.getMessage().contains("cust_no"), "外部库列名不得泄露给前端");
    }

    // ==================== 请求携带规则的标签库可见性校验（越权收敛） ====================

    @Test
    void 无标签库查看权限时请求携带规则的运行被拒绝且不连外部库() throws Exception {
        when(permissionService.hasAnyPermi(anyString())).thenReturn(false);
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setConditions(Collections.emptyList());

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.runRule(null, LIBRARY_ID, rule));

        assertTrue(e.getMessage().contains("无权"), e.getMessage());
        verify(connectionFactory, never()).createConnection(any(DpDataSource.class), anyString());
        verify(importMapper, never()).selectValuesByBatch(anyString());
    }

    @Test
    void 无标签库查看权限时请求携带规则的预览被拒绝() throws Exception {
        when(permissionService.hasAnyPermi(anyString())).thenReturn(false);
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setConditions(Collections.emptyList());

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.previewRule(null, LIBRARY_ID, rule));

        assertTrue(e.getMessage().contains("无权"), e.getMessage());
        verify(connectionFactory, never()).createConnection(any(DpDataSource.class), anyString());
    }

    @Test
    void 缺libraryId时请求携带规则的运行给出明确提示() throws Exception {
        RulePayload rule = new RulePayload();
        rule.setObjectKeyField("cust");
        rule.setConditions(Collections.emptyList());

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.runRule(null, null, rule));

        assertTrue(e.getMessage().contains("缺少关联标签库"), e.getMessage());
        verify(connectionFactory, never()).createConnection(any(DpDataSource.class), anyString());
    }
}
