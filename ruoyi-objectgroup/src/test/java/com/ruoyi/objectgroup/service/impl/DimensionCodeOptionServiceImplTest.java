package com.ruoyi.objectgroup.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.objectgroup.domain.DimensionTableRef;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;

/**
 * DimensionCodeOptionServiceImpl 纯 Mockito 单元测试：
 * 不启动 Spring 容器，Connection/PreparedStatement/ResultSet 全部 mock。
 * 新服务仅依赖 TlObjectGroupExtMapper，与旧链路（TlTagCodeValueMapper / 宽表 DISTINCT）完全隔离。
 */
@ExtendWith(MockitoExtension.class)
class DimensionCodeOptionServiceImplTest {

    private static final Long LIBRARY_ID = 100L;
    private static final String FIELD_NAME = "sex";

    @Mock
    private TlObjectGroupExtMapper extMapper;
    @Mock
    private JdbcConnectionFactory connectionFactory;
    @Mock
    private DataBrokerCryptoService cryptoService;
    @Mock
    private DataBrokerProperties properties;
    @Mock
    private DataBrokerProperties.Jdbc jdbc;

    @InjectMocks
    private DimensionCodeOptionServiceImpl service;

    private Connection conn;

    @BeforeEach
    void setUp() {
        conn = mock(Connection.class);
    }

    /** 构造维表引用 */
    private DimensionTableRef dim(Long id, String name, String table) {
        DimensionTableRef ref = new DimensionTableRef();
        ref.setDimensionId(id);
        ref.setDimensionName(name);
        ref.setSourceTableName(table);
        return ref;
    }

    /** mock 打开外部数据源连接的完整链路（数据集 -> 数据源 -> 解密 -> 建连） */
    private void mockOpenConnection() throws Exception {
        when(extMapper.selectDatasetIdByLibrary(LIBRARY_ID)).thenReturn(10L);
        DpDataSource ds = new DpDataSource();
        ds.setHost("127.0.0.1");
        ds.setPort(3306);
        ds.setDatabaseName("dim_db");
        ds.setUsername("root");
        ds.setPasswordCipher("cipher");
        when(extMapper.selectDataSourceByDataset(10L)).thenReturn(ds);
        when(cryptoService.decrypt("cipher")).thenReturn("pwd");
        when(connectionFactory.createConnection("127.0.0.1", 3306, "dim_db", "root", "pwd")).thenReturn(conn);
    }

    /** mock 某张维表的参数化查询，返回给定的码值行（每行：tag_code, code_definition, tag_name_cn, code_sort, last_update_time） */
    private PreparedStatement mockTableQuery(String table, Object[][] rows) throws Exception {
        PreparedStatement ps = mock(PreparedStatement.class);
        when(properties.getJdbc()).thenReturn(jdbc);
        when(jdbc.getSocketTimeout()).thenReturn(30000);
        when(conn.prepareStatement(startsWith(
                "select tag_code, code_definition, tag_name_cn, code_sort, last_update_time from `" + table + "`")))
                .thenReturn(ps);
        ResultSet rs = mock(ResultSet.class);
        when(ps.executeQuery()).thenReturn(rs);
        Boolean[] nexts = new Boolean[rows.length + 1];
        for (int i = 0; i < rows.length; i++) {
            nexts[i] = true;
        }
        nexts[rows.length] = false;
        when(rs.next()).thenReturn(true, Arrays.copyOfRange(nexts, 1, nexts.length));
        String[] codes = new String[rows.length];
        String[] defs = new String[rows.length];
        String[] names = new String[rows.length];
        Object[] sorts = new Object[rows.length];
        String[] times = new String[rows.length];
        for (int i = 0; i < rows.length; i++) {
            codes[i] = (String) rows[i][0];
            defs[i] = (String) rows[i][1];
            names[i] = (String) rows[i][2];
            sorts[i] = rows[i][3];
            times[i] = (String) rows[i][4];
        }
        // lenient：冲突等场景下异常抛出后，后续列/行的桩可能未被使用
        lenient().when(rs.getString("tag_code")).thenReturn(codes[0], Arrays.copyOfRange(codes, 1, codes.length));
        lenient().when(rs.getString("code_definition")).thenReturn(defs[0], Arrays.copyOfRange(defs, 1, defs.length));
        lenient().when(rs.getString("tag_name_cn")).thenReturn(names[0], Arrays.copyOfRange(names, 1, names.length));
        lenient().when(rs.getObject("code_sort")).thenReturn(sorts[0], Arrays.copyOfRange(sorts, 1, sorts.length));
        lenient().when(rs.getString("last_update_time")).thenReturn(times[0], Arrays.copyOfRange(times, 1, times.length));
        return ps;
    }

    /** 标签存在且为选项型 + 返回给定的关联维表 */
    private void mockTagAndDimensions(List<DimensionTableRef> dims) {
        when(extMapper.selectTagTypeByField(LIBRARY_ID, FIELD_NAME)).thenReturn("选项型");
        when(extMapper.selectEnabledDimensionsByLibrary(LIBRARY_ID)).thenReturn(dims);
    }

    @Test
    void 两张维表同码值定义一致时合并并按排序号与码值排序() throws Exception {
        mockTagAndDimensions(Arrays.asList(dim(1L, "性别维表", "dim_sex"), dim(2L, "性别维表扩展", "dim_sex_ext")));
        mockOpenConnection();
        // 维表1：乱序返回，验证排序逻辑
        PreparedStatement ps1 = mockTableQuery("dim_sex", new Object[][] {
                { "2", "女", "女性", 2, "2026-01-02" },
                { "1", "男", "男性", 1, "2026-01-01" }
        });
        // 维表2：码值 1 与维表1 定义一致（合并去重），另有无排序号的码值 10
        PreparedStatement ps2 = mockTableQuery("dim_sex_ext", new Object[][] {
                { "10", "未知", "未知性别", null, "2026-01-10" },
                { "1", "男", "男性", 1, "2026-01-01" }
        });

        List<Map<String, Object>> options = service.listCodeOptions(LIBRARY_ID, FIELD_NAME);

        // 合并去重：码值 1 只出现一次；排序：orderNum 升序（1, 2），无排序号的 10 排最后
        assertEquals(3, options.size());
        assertEquals("1", options.get(0).get("code"));
        assertEquals("2", options.get(1).get("code"));
        assertEquals("10", options.get(2).get("code"));
        // 行字段完整
        Map<String, Object> first = options.get(0);
        assertEquals("男", first.get("codeDefinition"));
        assertEquals("男性", first.get("tagName"));
        assertEquals(1, first.get("orderNum"));
        assertEquals("2026-01-01", first.get("lastUpdateTime"));
        assertEquals(1L, first.get("dimensionId"));
        // 参数化查询：fieldName 通过 setString 绑定，未拼接进 SQL
        verify(ps1).setString(1, FIELD_NAME);
        verify(ps2).setString(1, FIELD_NAME);
    }

    @Test
    void 同码值跨维表定义不一致时抛冲突异常() throws Exception {
        mockTagAndDimensions(Arrays.asList(dim(1L, "性别维表", "dim_sex"), dim(2L, "性别维表扩展", "dim_sex_ext")));
        mockOpenConnection();
        mockTableQuery("dim_sex", new Object[][] { { "1", "男", "男性", 1, "2026-01-01" } });
        mockTableQuery("dim_sex_ext", new Object[][] { { "1", "男性", "男性", 1, "2026-01-01" } });

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.listCodeOptions(LIBRARY_ID, FIELD_NAME));
        assertTrue(e.getMessage().contains("冲突"), "异常信息应包含“冲突”，实际：" + e.getMessage());
    }

    @Test
    void 无关联维表时返回空列表且不连接外部库() {
        mockTagAndDimensions(Collections.emptyList());

        List<Map<String, Object>> options = service.listCodeOptions(LIBRARY_ID, FIELD_NAME);

        assertTrue(options.isEmpty());
        verifyNoInteractions(connectionFactory);
    }

    @Test
    void 数值型标签不支持码值选项() {
        when(extMapper.selectTagTypeByField(LIBRARY_ID, FIELD_NAME)).thenReturn("数值型");

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.listCodeOptions(LIBRARY_ID, FIELD_NAME));
        assertTrue(e.getMessage().contains("不支持"));
        verifyNoInteractions(connectionFactory);
    }

    @Test
    void 标签不存在时抛异常() {
        when(extMapper.selectTagTypeByField(LIBRARY_ID, FIELD_NAME)).thenReturn(null);

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.listCodeOptions(LIBRARY_ID, FIELD_NAME));
        assertTrue(e.getMessage().contains("不存在"));
        verifyNoInteractions(connectionFactory);
    }

    @Test
    void 特殊字符码值按字符串原样返回() throws Exception {
        mockTagAndDimensions(Collections.singletonList(dim(1L, "性别维表", "dim_sex")));
        mockOpenConnection();
        PreparedStatement ps = mockTableQuery("dim_sex", new Object[][] {
                { "007", "特工", "特工", 1, "2026-01-01" },
                { "a'b", "引号", "引号", 2, "2026-01-02" },
                { "男", "男", "男性", 3, "2026-01-03" }
        });

        List<Map<String, Object>> options = service.listCodeOptions(LIBRARY_ID, FIELD_NAME);

        // 前导零、单引号、中文均原样保留，证明按字符串处理而非转义/转换
        assertEquals(Arrays.asList("007", "a'b", "男"),
                Arrays.asList(options.get(0).get("code"), options.get(1).get("code"), options.get(2).get("code")));
        verify(ps).setString(1, FIELD_NAME);
    }

    @Test
    void 维表物理表名含非法字符时拒绝查询() throws Exception {
        mockTagAndDimensions(Collections.singletonList(dim(1L, "恶意维表", "dim_sex;drop table x")));
        mockOpenConnection();

        ServiceException e = assertThrows(ServiceException.class,
                () -> service.listCodeOptions(LIBRARY_ID, FIELD_NAME));
        assertTrue(e.getMessage().contains("不合法"));
        // 白名单校验失败时不应发起任何 SQL
        verify(conn, org.mockito.Mockito.never()).prepareStatement(anyString());
    }
}
