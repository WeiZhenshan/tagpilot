package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDimensionTable;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.TlTagLibraryDimension;
import com.ruoyi.taglibrary.mapper.TlTagLibraryDimensionMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;

/**
 * 标签库默认码表保存 Service 单元测试（纯 Mockito，不起 Spring 上下文）
 *
 * @author ruoyi
 */
@ExtendWith(MockitoExtension.class)
class TlTagLibraryDimensionServiceImplTest extends BaseServiceTest {

    private static final Long LIBRARY_ID = 1L;
    private static final Long DATASOURCE_ID = 100L;

    @Mock
    private TlTagLibraryMapper libraryMapper;
    @Mock
    private TlTagLibraryDimensionMapper dimensionMapper;
    @Mock
    private DpDataSourceMapper dataSourceMapper;
    @Mock
    private JdbcConnectionFactory connectionFactory;
    @Mock
    private DataBrokerCryptoService cryptoService;
    @Mock
    private DataBrokerProperties properties;

    @InjectMocks
    private TlTagLibraryDimensionServiceImpl dimensionService;

    /** 保存成功：同源+启用+两表码值定义一致 → deleteByLibraryId + batchInsert，order_num 按入参顺序 */
    @Test
    void saveDimensionsSuccess() throws Exception {
        stubLibrary();
        DpDimensionTable dimA = buildDim(11L, "性别码表A", DATASOURCE_ID, "0", "dim_gender_a");
        DpDimensionTable dimB = buildDim(12L, "性别码表B", DATASOURCE_ID, "0", "dim_gender_b");
        when(dimensionMapper.selectDimensionsForConflictCheck(Arrays.asList(11L, 12L)))
                .thenReturn(Arrays.asList(dimA, dimB));
        Map<String, List<String[]>> tableRows = new LinkedHashMap<>();
        tableRows.put("dim_gender_a", Collections.singletonList(new String[]{"gender", "1", "男", "男性"}));
        tableRows.put("dim_gender_b", Collections.singletonList(new String[]{"gender", "1", "男", "男性"}));
        stubConflictCheck(tableRows);

        int saved = dimensionService.saveDimensions(LIBRARY_ID, Arrays.asList(11L, 12L));

        assertEquals(2, saved);
        verify(dimensionMapper).deleteByLibraryId(LIBRARY_ID);
        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<TlTagLibraryDimension>> captor = ArgumentCaptor.forClass(List.class);
        verify(dimensionMapper).batchInsert(captor.capture());
        List<TlTagLibraryDimension> relations = captor.getValue();
        assertEquals(2, relations.size());
        assertEquals(Long.valueOf(11L), relations.get(0).getDimensionId());
        assertEquals(Integer.valueOf(1), relations.get(0).getOrderNum());
        assertEquals(Long.valueOf(12L), relations.get(1).getDimensionId());
        assertEquals(Integer.valueOf(2), relations.get(1).getOrderNum());
        assertEquals(LIBRARY_ID, relations.get(0).getLibraryId());
        assertEquals(USERNAME, relations.get(0).getCreateBy());
    }

    /** 跨源关联失败：维表 datasource_id ≠ 标签库数据集 datasource_id → ServiceException */
    @Test
    void saveDimensionsCrossSourceRejected() {
        stubLibrary();
        DpDimensionTable dimA = buildDim(11L, "外部码表", 200L, "0", "dim_other");
        when(dimensionMapper.selectDimensionsForConflictCheck(Collections.singletonList(11L)))
                .thenReturn(Collections.singletonList(dimA));

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.saveDimensions(LIBRARY_ID, Collections.singletonList(11L)));
        assertTrue(e.getMessage().contains("不同源"));
        verify(dimensionMapper, never()).deleteByLibraryId(anyLong());
        verify(dimensionMapper, never()).batchInsert(anyList());
    }

    /** 停用维表失败：status='1' → ServiceException */
    @Test
    void saveDimensionsDisabledRejected() {
        stubLibrary();
        DpDimensionTable dimA = buildDim(11L, "停用码表", DATASOURCE_ID, "1", "dim_disabled");
        when(dimensionMapper.selectDimensionsForConflictCheck(Collections.singletonList(11L)))
                .thenReturn(Collections.singletonList(dimA));

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.saveDimensions(LIBRARY_ID, Collections.singletonList(11L)));
        assertTrue(e.getMessage().contains("已停用"));
        verify(dimensionMapper, never()).deleteByLibraryId(anyLong());
        verify(dimensionMapper, never()).batchInsert(anyList());
    }

    /** 定义冲突拒绝：两表同 (tag_name_en, tag_code) 但 code_definition 不同 → ServiceException，不落库 */
    @Test
    void saveDimensionsCodeConflictRejected() throws Exception {
        stubLibrary();
        DpDimensionTable dimA = buildDim(11L, "性别码表A", DATASOURCE_ID, "0", "dim_gender_a");
        DpDimensionTable dimB = buildDim(12L, "性别码表B", DATASOURCE_ID, "0", "dim_gender_b");
        when(dimensionMapper.selectDimensionsForConflictCheck(Arrays.asList(11L, 12L)))
                .thenReturn(Arrays.asList(dimA, dimB));
        Map<String, List<String[]>> tableRows = new LinkedHashMap<>();
        tableRows.put("dim_gender_a", Collections.singletonList(new String[]{"gender", "1", "男", "男性"}));
        tableRows.put("dim_gender_b", Collections.singletonList(new String[]{"gender", "1", "男", "生理男性"}));
        stubConflictCheck(tableRows);

        ServiceException e = assertThrows(ServiceException.class,
                () -> dimensionService.saveDimensions(LIBRARY_ID, Arrays.asList(11L, 12L)));
        assertTrue(e.getMessage().contains("码值冲突"));
        verify(dimensionMapper, never()).deleteByLibraryId(anyLong());
        verify(dimensionMapper, never()).batchInsert(anyList());
    }

    /** 空数组清空：dimensionIds=[] → 只 deleteByLibraryId，不 batchInsert，不做冲突校验 */
    @Test
    void saveDimensionsEmptyClearsOnly() {
        stubLibrary();

        int saved = dimensionService.saveDimensions(LIBRARY_ID, new ArrayList<Long>());

        assertEquals(0, saved);
        verify(dimensionMapper).deleteByLibraryId(LIBRARY_ID);
        verify(dimensionMapper, never()).batchInsert(anyList());
        verify(dimensionMapper, never()).selectDimensionsForConflictCheck(anyList());
        verifyNoInteractions(dataSourceMapper, connectionFactory);
    }

    // ---- 测试辅助 ----

    /** 打桩标签库与其数据源ID */
    private void stubLibrary() {
        when(libraryMapper.selectLibraryById(LIBRARY_ID)).thenReturn(new TlTagLibrary());
        when(dimensionMapper.selectLibraryDatasourceId(LIBRARY_ID)).thenReturn(DATASOURCE_ID);
    }

    private DpDimensionTable buildDim(Long id, String name, Long datasourceId, String status, String tableName) {
        DpDimensionTable dim = new DpDimensionTable();
        dim.setDimensionId(id);
        dim.setDimensionName(name);
        dim.setDatasourceId(datasourceId);
        dim.setStatus(status);
        dim.setDelFlag("0");
        dim.setSourceTableName(tableName);
        return dim;
    }

    /**
     * 打桩码值冲突校验链路：DpDataSourceMapper + JdbcConnectionFactory + Connection/Statement/ResultSet，
     * tableRows 按物理表名给出每张维表的码值行（tag_name_en/tag_code/tag_name_cn/code_definition）
     */
    private void stubConflictCheck(Map<String, List<String[]>> tableRows) throws Exception {
        DpDataSource ds = new DpDataSource();
        ds.setDatasourceId(DATASOURCE_ID);
        ds.setHost("127.0.0.1");
        ds.setPort(3306);
        ds.setDatabaseName("biz_db");
        ds.setUsername("root");
        when(dataSourceMapper.selectDataSourceById(DATASOURCE_ID)).thenReturn(ds);

        DataBrokerProperties.Jdbc jdbc = mock(DataBrokerProperties.Jdbc.class);
        when(jdbc.getSocketTimeout()).thenReturn(5000);
        when(properties.getJdbc()).thenReturn(jdbc);

        Connection conn = mock(Connection.class);
        Statement stmt = mock(Statement.class);
        when(connectionFactory.createConnection(any(DpDataSource.class), anyString()))
                .thenReturn(conn);
        when(conn.createStatement()).thenReturn(stmt);
        for (Map.Entry<String, List<String[]>> entry : tableRows.entrySet()) {
            ResultSet rs = mockResultSet(entry.getValue());
            when(stmt.executeQuery(contains("`" + entry.getKey() + "`"))).thenReturn(rs);
        }
    }

    /** 按行数据构造 mock ResultSet，列序固定为 tag_name_en/tag_code/tag_name_cn/code_definition */
    private ResultSet mockResultSet(List<String[]> rows) throws Exception {
        ResultSet rs = mock(ResultSet.class);
        Boolean[] nextSeq = new Boolean[rows.size() + 1];
        Arrays.fill(nextSeq, Boolean.TRUE);
        nextSeq[rows.size()] = Boolean.FALSE;
        when(rs.next()).thenReturn(nextSeq[0], Arrays.copyOfRange(nextSeq, 1, nextSeq.length));
        for (int col = 1; col <= 4; col++) {
            String[] values = new String[rows.size()];
            for (int i = 0; i < rows.size(); i++) {
                values[i] = rows.get(i)[col - 1];
            }
            when(rs.getString(col)).thenReturn(values[0], Arrays.copyOfRange(values, 1, values.length));
        }
        return rs;
    }
}
