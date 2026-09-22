package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.config.DataBrokerProperties;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.DpDimensionTable;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportRequest;
import com.ruoyi.taglibrary.domain.dto.BootstrapExportResult;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryDimensionMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;

@ExtendWith(MockitoExtension.class)
class TsBootstrapExportServiceTest {

    private static final Long LIBRARY_ID = 107L;
    private static final Long DATASET_ID = 6L;
    private static final Long VERSION_ID = 12L;
    private static final Long DATASOURCE_ID = 101L;

    @Mock
    private TlTagLibraryMapper libraryMapper;
    @Mock
    private TlTagMapper tagMapper;
    @Mock
    private TlTagDirMapper dirMapper;
    @Mock
    private TlTagLibraryDimensionMapper dimensionMapper;
    @Mock
    private DpDataSourceMapper dataSourceMapper;
    @Mock
    private DpOnlineVersionResolver versionResolver;
    @Mock
    private JdbcConnectionFactory connectionFactory;
    @Mock
    private DataBrokerCryptoService cryptoService;
    @Mock
    private DataBrokerProperties properties;

    @InjectMocks
    private TsBootstrapExportService exportService;

    @Test
    void exportMergesSameCodeDefinition() throws Exception {
        stubLibraryAndVersion();
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Arrays.asList(
                tag(526L, "GENDER", "性别", "text", "选项型", "0"),
                tag(525L, "CUST_ID", "客户号", "varchar(32)", "文本型", "1")));
        when(dirMapper.selectDirList(LIBRARY_ID)).thenReturn(Collections.singletonList(dir(1L, 0L, "客户概况")));
        when(dimensionMapper.selectDimensionIdsByLibraryId(LIBRARY_ID)).thenReturn(Arrays.asList(2L));
        DpDimensionTable dim = dim(2L, "个人客户经营标签码值表", "L_INDVCST_LABEL_CODE_MAP");
        when(dimensionMapper.selectDimensionsForConflictCheck(Arrays.asList(2L)))
                .thenReturn(Collections.singletonList(dim));
        stubCodeTable(Collections.singletonList(
                new String[]{"GENDER", "M", "性别", "男", "1", "2026-01-01"}));

        BootstrapExportRequest req = request("GENDER", "CUST_ID");
        BootstrapExportResult result = exportService.exportFreeze(req);

        assertEquals(2, result.getTagCount());
        assertEquals(1, result.getCodeValueCount());
        assertTrue(result.getJsonl().contains("\"kind\":\"meta\""));
        assertTrue(result.getJsonl().contains("\"kind\":\"tag\""));
        assertTrue(result.getJsonl().contains("\"kind\":\"code_value\""));
        assertTrue(result.getJsonl().contains("\"field_name\":\"CUST_ID\""));
        assertTrue(result.getJsonl().contains("\"is_object_key\":\"1\""));
        assertTrue(result.getJsonl().contains("\"business_candidate\":false"));
        assertFalse(result.getJsonl().contains("tl_tag_code_value"));
        assertTrue(result.getIssues().isEmpty());
    }

    @Test
    void exportRejectsConflictingCodeDefinition() throws Exception {
        stubLibraryAndVersion();
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(
                tag(526L, "GENDER", "性别", "text", "选项型", "0")));
        when(dirMapper.selectDirList(LIBRARY_ID)).thenReturn(Collections.<TlTagDir>emptyList());
        when(dimensionMapper.selectDimensionIdsByLibraryId(LIBRARY_ID)).thenReturn(Arrays.asList(2L, 3L));
        when(dimensionMapper.selectDimensionsForConflictCheck(Arrays.asList(2L, 3L)))
                .thenReturn(Arrays.asList(
                        dim(2L, "码表A", "code_a"),
                        dim(3L, "码表B", "code_b")));
        stubTwoTablesConflict();

        ServiceException ex = assertThrows(ServiceException.class,
                () -> exportService.exportFreeze(request("GENDER")));
        assertTrue(ex.getMessage().contains("码值冲突"));
    }

    @Test
    void exportRecordsIssueWhenEnumHasNoCode() throws Exception {
        stubLibraryAndVersion();
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(
                tag(526L, "GENDER", "性别", "text", "选项型", "0")));
        when(dirMapper.selectDirList(LIBRARY_ID)).thenReturn(Collections.<TlTagDir>emptyList());
        when(dimensionMapper.selectDimensionIdsByLibraryId(LIBRARY_ID)).thenReturn(Collections.<Long>emptyList());

        BootstrapExportResult result = exportService.exportFreeze(request("GENDER"));
        assertEquals(1, result.getTagCount());
        assertEquals(0, result.getCodeValueCount());
        assertEquals(1, result.getIssues().size());
        assertEquals("CODE_UNMAPPED", result.getIssues().get(0).get("code"));
    }

    private void stubLibraryAndVersion() {
        TlTagLibrary library = new TlTagLibrary();
        library.setLibraryId(LIBRARY_ID);
        library.setDatasetId(DATASET_ID);
        library.setLibraryName("个人客户经营标签库");
        library.setTagObject("客户");
        when(libraryMapper.selectLibraryById(LIBRARY_ID)).thenReturn(library);

        DpResolvedVersion version = new DpResolvedVersion();
        version.setDatasetId(DATASET_ID);
        version.setVersionId(VERSION_ID);
        version.setVersionNo(1);
        version.setVersionName("V1");
        version.setIsDefault(Boolean.TRUE);
        version.setReason("默认在线版本");
        when(versionResolver.resolve(DATASET_ID)).thenReturn(version);

        DpResolvedField genderField = field(401L, "GENDER", "GENDER", "text", "0");
        DpResolvedField custField = field(400L, "CUST_ID", "CUST_ID", "varchar(32)", "1");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Arrays.asList(custField, genderField));
        org.mockito.Mockito.lenient().when(dimensionMapper.selectLibraryDatasourceId(LIBRARY_ID)).thenReturn(DATASOURCE_ID);
    }

    private void stubCodeTable(List<String[]> rows) throws Exception {
        DpDataSource ds = new DpDataSource();
        ds.setDatasourceId(DATASOURCE_ID);
        when(dataSourceMapper.selectDataSourceById(DATASOURCE_ID)).thenReturn(ds);
        DataBrokerProperties.Jdbc jdbc = mock(DataBrokerProperties.Jdbc.class);
        when(jdbc.getSocketTimeout()).thenReturn(5000);
        when(properties.getJdbc()).thenReturn(jdbc);
        Connection conn = mock(Connection.class);
        Statement stmt = mock(Statement.class);
        when(connectionFactory.createConnection(any(DpDataSource.class), anyString())).thenReturn(conn);
        when(conn.createStatement()).thenReturn(stmt);
        ResultSet rs = resultSet(rows);
        when(stmt.executeQuery(contains("`L_INDVCST_LABEL_CODE_MAP`"))).thenReturn(rs);
    }

    private void stubTwoTablesConflict() throws Exception {
        DpDataSource ds = new DpDataSource();
        ds.setDatasourceId(DATASOURCE_ID);
        when(dataSourceMapper.selectDataSourceById(DATASOURCE_ID)).thenReturn(ds);
        DataBrokerProperties.Jdbc jdbc = mock(DataBrokerProperties.Jdbc.class);
        when(jdbc.getSocketTimeout()).thenReturn(5000);
        when(properties.getJdbc()).thenReturn(jdbc);
        Connection conn = mock(Connection.class);
        Statement stmt = mock(Statement.class);
        when(connectionFactory.createConnection(any(DpDataSource.class), anyString())).thenReturn(conn);
        when(conn.createStatement()).thenReturn(stmt);
        ResultSet rsA = resultSet(Collections.singletonList(
                new String[]{"GENDER", "M", "性别", "男", "1", null}));
        ResultSet rsB = resultSet(Collections.singletonList(
                new String[]{"GENDER", "M", "性别", "男性", "1", null}));
        when(stmt.executeQuery(contains("`code_a`"))).thenReturn(rsA);
        when(stmt.executeQuery(contains("`code_b`"))).thenReturn(rsB);
    }

    private ResultSet resultSet(List<String[]> rows) throws Exception {
        ResultSet rs = mock(ResultSet.class);
        Boolean[] nextSeq = new Boolean[rows.size() + 1];
        Arrays.fill(nextSeq, Boolean.TRUE);
        nextSeq[rows.size()] = Boolean.FALSE;
        when(rs.next()).thenReturn(nextSeq[0], Arrays.copyOfRange(nextSeq, 1, nextSeq.length));
        String[] names = {"tag_name_en", "tag_code", "tag_name_cn", "code_definition", "code_sort", "last_update_time"};
        for (int col = 0; col < names.length; col++) {
            String[] values = new String[Math.max(rows.size(), 1)];
            for (int i = 0; i < rows.size(); i++) {
                values[i] = rows.get(i)[col];
            }
            if (rows.isEmpty()) {
                continue;
            }
            org.mockito.Mockito.lenient().when(rs.getString(names[col])).thenReturn(values[0], Arrays.copyOfRange(values, 1, values.length));
        }
        return rs;
    }

    private BootstrapExportRequest request(String... fields) {
        BootstrapExportRequest req = new BootstrapExportRequest();
        req.setLibraryId(LIBRARY_ID);
        req.setFieldNames(Arrays.asList(fields));
        return req;
    }

    private TlTag tag(Long id, String field, String name, String dataType, String tagType, String objectKey) {
        TlTag tag = new TlTag();
        tag.setTagId(id);
        tag.setLibraryId(LIBRARY_ID);
        tag.setDirId(1L);
        tag.setFieldName(field);
        tag.setTagName(name);
        tag.setDataType(dataType);
        tag.setTagType(tagType);
        tag.setIsObjectKey(objectKey);
        tag.setStatus("2");
        tag.setSourceStatus("AVAILABLE");
        tag.setVersion(3);
        tag.setBusinessCaliber("口径");
        tag.setTechCaliber("技术口径");
        tag.setSourceFingerprint("abc");
        tag.setConfirmedFingerprint("abc");
        return tag;
    }

    private TlTagDir dir(Long id, Long parentId, String name) {
        TlTagDir dir = new TlTagDir();
        dir.setDirId(id);
        dir.setParentId(parentId);
        dir.setDirName(name);
        dir.setLibraryId(LIBRARY_ID);
        return dir;
    }

    private DpDimensionTable dim(Long id, String name, String table) {
        DpDimensionTable dim = new DpDimensionTable();
        dim.setDimensionId(id);
        dim.setDimensionName(name);
        dim.setDatasourceId(DATASOURCE_ID);
        dim.setSourceTableName(table);
        dim.setStatus("0");
        dim.setDelFlag("0");
        return dim;
    }

    private DpResolvedField field(Long fieldId, String alias, String name, String dataType, String objectKey) {
        DpResolvedField field = new DpResolvedField();
        field.setFieldId(fieldId);
        field.setFieldAlias(alias);
        field.setFieldName(name);
        field.setDataType(dataType);
        field.setIsObjectKey(objectKey);
        field.setDatasourceId(DATASOURCE_ID);
        field.setTableName("L_INDVCST_LABEL");
        field.setSourceTableId(501L);
        field.setSourceColumnId(fieldId);
        return field;
    }
}
