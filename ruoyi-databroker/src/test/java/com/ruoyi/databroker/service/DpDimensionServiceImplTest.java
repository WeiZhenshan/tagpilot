package com.ruoyi.databroker.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.Arrays;
import java.util.Collections;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import com.ruoyi.common.core.domain.entity.SysUser;
import com.ruoyi.common.core.domain.model.LoginUser;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDimensionTable;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.mapper.DpDimensionTableMapper;
import com.ruoyi.databroker.mapper.DpMetaTableMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.impl.DpDimensionServiceImpl;

/**
 * 维表管理 Service 单元测试（纯Mockito，不起Spring上下文、不连数据库）
 *
 * @author ruoyi
 */
@ExtendWith(MockitoExtension.class)
public class DpDimensionServiceImplTest {

    private static final String[] ALL_STANDARD_COLUMNS = {
        "tag_name_en", "tag_code", "tag_name_cn", "code_definition", "code_sort", "last_update_time"
    };

    @Mock
    private DpDimensionTableMapper dimensionMapper;
    @Mock
    private DpDataSourceMapper dataSourceMapper;
    @Mock
    private DpMetaTableMapper tableMapper;
    @Mock
    private DataBrokerCryptoService cryptoService;
    @Mock
    private JdbcConnectionFactory connectionFactory;
    @Mock
    private DataBrokerProperties properties;

    @InjectMocks
    private DpDimensionServiceImpl dimensionService;

    /** SecurityUtils.getUsername() 走静态 SecurityContextHolder，这里预置一个 admin 登录用户 */
    @BeforeEach
    public void setUpSecurityContext() {
        SysUser sysUser = new SysUser();
        sysUser.setUserId(1L);
        sysUser.setUserName("admin");
        LoginUser loginUser = new LoginUser(sysUser, Collections.emptySet());
        UsernamePasswordAuthenticationToken authentication =
                new UsernamePasswordAuthenticationToken(loginUser, null, Collections.emptyList());
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    @AfterEach
    public void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    // ---- 登记 ----

    @Test
    public void 登记成功_标准字段齐全_插入登记记录() throws Exception {
        DpDimensionTable dimension = newDimension();
        when(dimensionMapper.selectByCode("dim_gender")).thenReturn(null);
        when(tableMapper.selectTableById(10L)).thenReturn(newMetaTable());
        when(dataSourceMapper.selectDataSourceById(1L)).thenReturn(newDataSource());
        when(dimensionMapper.selectBySource(1L, 10L)).thenReturn(null);
        stubJdbcColumns(ALL_STANDARD_COLUMNS);
        when(dimensionMapper.insertDimension(any(DpDimensionTable.class))).thenReturn(1);

        int rows = dimensionService.insertDimension(dimension);

        assertEquals(1, rows);
        ArgumentCaptor<DpDimensionTable> captor = ArgumentCaptor.forClass(DpDimensionTable.class);
        verify(dimensionMapper).insertDimension(captor.capture());
        DpDimensionTable saved = captor.getValue();
        // sourceTableName 必须取 dp_meta_table.objectName 快照
        assertEquals("dim_gender_tab", saved.getSourceTableName());
        assertEquals("0", saved.getStatus());
        assertEquals("admin", saved.getCreateBy());
    }

    @Test
    public void 登记失败_物理表缺少标准列() throws Exception {
        DpDimensionTable dimension = newDimension();
        when(dimensionMapper.selectByCode("dim_gender")).thenReturn(null);
        when(tableMapper.selectTableById(10L)).thenReturn(newMetaTable());
        when(dataSourceMapper.selectDataSourceById(1L)).thenReturn(newDataSource());
        when(dimensionMapper.selectBySource(1L, 10L)).thenReturn(null);
        // 结果集缺 code_sort
        stubJdbcColumns("tag_name_en", "tag_code", "tag_name_cn", "code_definition", "last_update_time");

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.insertDimension(dimension));
        assertTrue(e.getMessage().contains("code_sort"), "异常消息应包含缺失列名：" + e.getMessage());
        verify(dimensionMapper, never()).insertDimension(any(DpDimensionTable.class));
    }

    @Test
    public void 登记失败_维表编码已存在() {
        DpDimensionTable dimension = newDimension();
        DpDimensionTable dup = new DpDimensionTable();
        dup.setDimensionId(99L);
        dup.setDelFlag("0");
        when(dimensionMapper.selectByCode("dim_gender")).thenReturn(dup);

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.insertDimension(dimension));
        assertTrue(e.getMessage().contains("维表编码已存在"));
        verify(dimensionMapper, never()).insertDimension(any(DpDimensionTable.class));
    }

    @Test
    public void 登记失败_同一物理表已登记() {
        DpDimensionTable dimension = newDimension();
        when(dimensionMapper.selectByCode("dim_gender")).thenReturn(null);
        when(tableMapper.selectTableById(10L)).thenReturn(newMetaTable());
        when(dataSourceMapper.selectDataSourceById(1L)).thenReturn(newDataSource());
        DpDimensionTable sourceDup = new DpDimensionTable();
        sourceDup.setDimensionId(88L);
        sourceDup.setDelFlag("0");
        when(dimensionMapper.selectBySource(1L, 10L)).thenReturn(sourceDup);

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.insertDimension(dimension));
        assertTrue(e.getMessage().contains("该物理表已登记维表"));
        verify(dimensionMapper, never()).insertDimension(any(DpDimensionTable.class));
    }

    @Test
    public void 登记_同表历史记录已删除_恢复原记录() throws Exception {
        DpDimensionTable dimension = newDimension();
        when(dimensionMapper.selectByCode("dim_gender")).thenReturn(null);
        when(tableMapper.selectTableById(10L)).thenReturn(newMetaTable());
        when(dataSourceMapper.selectDataSourceById(1L)).thenReturn(newDataSource());
        DpDimensionTable deleted = new DpDimensionTable();
        deleted.setDimensionId(88L);
        deleted.setDelFlag("2");
        when(dimensionMapper.selectBySource(1L, 10L)).thenReturn(deleted);
        stubJdbcColumns(ALL_STANDARD_COLUMNS);
        when(dimensionMapper.restoreDimension(any(DpDimensionTable.class))).thenReturn(1);

        int rows = dimensionService.insertDimension(dimension);

        assertEquals(1, rows);
        ArgumentCaptor<DpDimensionTable> captor = ArgumentCaptor.forClass(DpDimensionTable.class);
        verify(dimensionMapper).restoreDimension(captor.capture());
        assertEquals(88L, captor.getValue().getDimensionId());
        assertEquals("dim_gender_tab", captor.getValue().getSourceTableName());
        verify(dimensionMapper, never()).insertDimension(any(DpDimensionTable.class));
    }

    @Test
    public void 登记失败_维表编码格式非法() {
        DpDimensionTable dimension = newDimension();
        dimension.setDimensionCode("dim-gender");

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.insertDimension(dimension));
        assertTrue(e.getMessage().contains("维表编码仅支持"));
        verify(dimensionMapper, never()).insertDimension(any(DpDimensionTable.class));
    }

    // ---- 删除 ----

    @Test
    public void 删除失败_维表被标签库关联() {
        DpDimensionTable dimension = new DpDimensionTable();
        dimension.setDimensionId(5L);
        dimension.setDimensionName("性别维表");
        when(dimensionMapper.selectDimensionById(5L)).thenReturn(dimension);
        when(dimensionMapper.countLibraryReferences(5L)).thenReturn(2);

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.deleteDimensionByIds(new Long[]{5L}));
        assertTrue(e.getMessage().contains("仍被标签库关联"));
        verify(dimensionMapper, never()).deleteDimensionByIds(any(Long[].class));
    }

    // ---- 状态 ----

    @Test
    public void 停用失败_维表被标签库关联() {
        DpDimensionTable dimension = new DpDimensionTable();
        dimension.setDimensionId(5L);
        dimension.setDimensionName("性别维表");
        when(dimensionMapper.selectDimensionById(5L)).thenReturn(dimension);
        when(dimensionMapper.countLibraryReferences(5L)).thenReturn(1);

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.updateStatus(5L, "1"));
        assertTrue(e.getMessage().contains("不能停用"));
        verify(dimensionMapper, never()).updateStatus(any(), anyString());
    }

    @Test
    public void 启用失败_物理表缺少标准列() throws Exception {
        DpDimensionTable dimension = new DpDimensionTable();
        dimension.setDimensionId(5L);
        dimension.setDatasourceId(1L);
        dimension.setSourceTableName("dim_gender_tab");
        when(dimensionMapper.selectDimensionById(5L)).thenReturn(dimension);
        when(dataSourceMapper.selectDataSourceById(1L)).thenReturn(newDataSource());
        // 结果集缺 last_update_time
        stubJdbcColumns("tag_name_en", "tag_code", "tag_name_cn", "code_definition", "code_sort");

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.updateStatus(5L, "0"));
        assertTrue(e.getMessage().contains("last_update_time"), "异常消息应包含缺失列名：" + e.getMessage());
        verify(dimensionMapper, never()).updateStatus(any(), anyString());
    }

    // ---- 编辑 ----

    @Test
    public void 编辑_仅更新名称和备注() {
        DpDimensionTable old = new DpDimensionTable();
        old.setDimensionId(5L);
        when(dimensionMapper.selectDimensionById(5L)).thenReturn(old);
        when(dimensionMapper.updateDimension(any(DpDimensionTable.class))).thenReturn(1);

        DpDimensionTable input = new DpDimensionTable();
        input.setDimensionId(5L);
        input.setDimensionName("性别维表V2");
        input.setRemark("新备注");
        // 即使前端传了编码/数据源，也不应被更新
        input.setDimensionCode("dim_gender");
        input.setDatasourceId(1L);

        int rows = dimensionService.updateDimension(input);

        assertEquals(1, rows);
        ArgumentCaptor<DpDimensionTable> captor = ArgumentCaptor.forClass(DpDimensionTable.class);
        verify(dimensionMapper).updateDimension(captor.capture());
        DpDimensionTable update = captor.getValue();
        assertEquals(5L, update.getDimensionId());
        assertEquals("性别维表V2", update.getDimensionName());
        assertEquals("新备注", update.getRemark());
        assertEquals("admin", update.getUpdateBy());
        assertNull(update.getDimensionCode());
        assertNull(update.getDatasourceId());
        assertNull(update.getSourceTableId());
    }

    // ---- 测试数据与JDBC模拟 ----

    private DpDimensionTable newDimension() {
        DpDimensionTable dimension = new DpDimensionTable();
        dimension.setDimensionName("性别维表");
        dimension.setDimensionCode("dim_gender");
        dimension.setDatasourceId(1L);
        dimension.setSourceTableId(10L);
        return dimension;
    }

    private DpMetaTable newMetaTable() {
        DpMetaTable metaTable = new DpMetaTable();
        metaTable.setTableId(10L);
        metaTable.setDatasourceId(1L);
        metaTable.setObjectName("dim_gender_tab");
        metaTable.setStatus("0");
        return metaTable;
    }

    private DpDataSource newDataSource() {
        DpDataSource ds = new DpDataSource();
        ds.setDatasourceId(1L);
        ds.setHost("127.0.0.1");
        ds.setPort(3306);
        ds.setDatabaseName("ext_db");
        ds.setUsername("root");
        ds.setStatus("0");
        ds.setDelFlag("0");
        return ds;
    }

    /**
     * 模拟 information_schema.COLUMNS 查询：连接/语句/结果集全部mock，
     * 按传入列名逐个返回，socketTimeout 用真实的 DataBrokerProperties.Jdbc 默认值
     */
    private void stubJdbcColumns(String... columnNames) throws Exception {
        Connection conn = mock(Connection.class);
        PreparedStatement stmt = mock(PreparedStatement.class);
        ResultSet rs = mock(ResultSet.class);
        when(connectionFactory.createConnection(any(DpDataSource.class), anyString()))
                .thenReturn(conn);
        when(conn.prepareStatement(contains("information_schema"))).thenReturn(stmt);
        when(stmt.executeQuery()).thenReturn(rs);
        Boolean[] moreNexts = new Boolean[columnNames.length];
        Arrays.fill(moreNexts, Boolean.TRUE);
        moreNexts[columnNames.length - 1] = Boolean.FALSE;
        when(rs.next()).thenReturn(Boolean.TRUE, moreNexts);
        String[] restColumns = Arrays.copyOfRange(columnNames, 1, columnNames.length);
        when(rs.getString(1)).thenReturn(columnNames[0], restColumns);
        when(properties.getJdbc()).thenReturn(new DataBrokerProperties.Jdbc());
    }
}
