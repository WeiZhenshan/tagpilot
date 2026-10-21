package com.ruoyi.taglibrary.service;

import java.math.BigDecimal;
import java.sql.*;
import java.util.*;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.IDimensionCodeOptionService;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;
import com.ruoyi.objectgroup.service.impl.RuleTagValidator;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;
import org.junit.jupiter.api.*;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** 合成 H2 提供客户行，元数据与语义层由 mock 提供；执行真实取数与 SQL。 */
class TsTagStatsServiceTest {
    private TsTagStatsService service;
    private TlObjectGroupExtMapper ext;
    private TlTagMapper tags;
    private TsTagSemanticMapper semantics;
    private IDimensionCodeOptionService codeOptions;
    private String url;
    private Connection keeper;

    private static final Long LIBRARY = 107L;
    private static final Long VERSION = 7L;
    private static final Long COHORT = 240L;

    @SuppressWarnings("unchecked")
    @Test void conversationBatchRunsRealAggregatesAndTwoDimensionsInOneSnapshot() throws Exception {
        tag(812L,"总资产","数值型","aum");unit(812L,"CNY");
        tag(813L,"风险等级","选项型","risk_level");tag(814L,"渠道","选项型","channel");
        try(Statement st=keeper.createStatement()){st.executeUpdate("update customer set channel='branch' where customer_count<=120");}
        Map<String,RulePayload> populations=new LinkedHashMap<>();populations.put("target",new RulePayload());
        Map<String,Object> result=service.analysisBatch(LIBRARY,populations,Arrays.asList(
            com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("id","aum","tag_id",812L,"operation","avg","dimensions",Arrays.asList(813L,814L))),new HashSet<>(Arrays.asList(812L,813L,814L)));
        List<Map<String,Object>> qs=(List<Map<String,Object>>)result.get("queries");
        List<Map<String,Object>> rows=(List<Map<String,Object>>)qs.get(0).get("rows");
        assertEquals(2,rows.size());
        Set<Double> values=new HashSet<>();for(Map<String,Object> row:rows)values.add(((Number)row.get("value")).doubleValue());
        assertEquals(new HashSet<>(Arrays.asList(200000d,800000d)),values);
        assertNotNull(result.get("snapshot_id"));assertNull(result.get("data_as_of"));
        assertEquals(true,((Map)result.get("quality")).get("consistent_batch"));
    }

    @SuppressWarnings("unchecked")
    @Test void conversationDistributionUsesRealDenominatorAndSuppressesComplement() throws Exception {
        tag(814L,"渠道","选项型","channel");
        try(Statement st=keeper.createStatement()){st.executeUpdate("update customer set channel='branch' where customer_count<=40");}
        Map<String,RulePayload> populations=new LinkedHashMap<>();populations.put("target",new RulePayload());
        List<Map<String,Object>> queries=Arrays.asList(com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("id","channel","tag_id",814L,"operation","distribution"));
        Map<String,Object> bundle=service.analysisBatch(LIBRARY,populations,queries,new HashSet<>(Arrays.asList(814L)));
        List<Map<String,Object>> facts=(List<Map<String,Object>>)bundle.get("facts");
        assertTrue(facts.stream().anyMatch(f->"%".equals(f.get("unit"))&&Math.abs(((Number)f.get("value")).doubleValue()-16.67)<.001));
        assertTrue(facts.stream().filter(f->"%".equals(f.get("unit"))).allMatch(f->"f-channel-total".equals(f.get("denominator_id"))));
        try(Statement st=keeper.createStatement()){st.executeUpdate("update customer set channel='app' where customer_count>10");}
        bundle=service.analysisBatch(LIBRARY,populations,queries,new HashSet<>(Arrays.asList(814L)));
        Map<String,Object> query=((List<Map<String,Object>>)bundle.get("queries")).get(0);
        assertEquals("SUPPRESSED",query.get("status"));assertTrue(((List)bundle.get("facts")).isEmpty());assertTrue(((List)query.get("rows")).isEmpty());
    }

    @Test void conversationRejectsDuplicateCustomerKeysAndRawSql() throws Exception {
        Map<String,RulePayload> populations=new LinkedHashMap<>();populations.put("target",new RulePayload());
        List<Map<String,Object>> queries=Arrays.asList(com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("id","count","operation","count"));
        try(Statement st=keeper.createStatement()){st.executeUpdate("update customer set customer_key='duplicate' where customer_count<=2");}
        assertThrows(IllegalArgumentException.class,()->service.analysisBatch(LIBRARY,populations,queries,Collections.emptySet()));
        queries.get(0).put("sql","select * from customer");
        assertThrows(IllegalArgumentException.class,()->service.analysisBatch(LIBRARY,populations,queries,Collections.emptySet()));
    }
    @SuppressWarnings("unchecked")
    @Test void conversationDistinguishesEmptyPopulationFromSuppressedOrMissing() throws Exception {
        try(Statement st=keeper.createStatement()){st.executeUpdate("delete from customer");}
        Map<String,RulePayload> populations=new LinkedHashMap<>();populations.put("target",new RulePayload());
        Map<String,Object> result=service.analysisBatch(LIBRARY,populations,Arrays.asList(com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("id","empty","operation","count")),Collections.emptySet());
        assertEquals("EMPTY",((List<Map<String,Object>>)result.get("queries")).get(0).get("status"));
        assertEquals(0,((Number)((List<Map<String,Object>>)result.get("facts")).get(0).get("value")).intValue());
    }
    @SuppressWarnings("unchecked")
    @Test void absentPublishedCategoryIsStructuralZeroWithPopulationSample() {
        tag(814L,"渠道","选项型","channel");
        TsPublishedAnalysisCatalog published=(TsPublishedAnalysisCatalog)ReflectionTestUtils.getField(service,"publishedAnalysis");
        com.fasterxml.jackson.databind.ObjectMapper mapper=new com.fasterxml.jackson.databind.ObjectMapper();
        when(published.tags(eq(LIBRARY),anySet())).thenReturn(Collections.singletonMap(814L,mapper.valueToTree(com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("_code_labels",com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("app","手机银行","branch","网点")))));
        Map<String,RulePayload> populations=new LinkedHashMap<>();populations.put("target",new RulePayload());
        Map<String,Object> result=service.analysisBatch(LIBRARY,populations,Arrays.asList(com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("id","channel","operation","distribution","tag_id",814L)),Collections.singleton(814L));
        List<Map<String,Object>> facts=(List<Map<String,Object>>)result.get("facts");
        Map<String,Object> zero=facts.stream().filter(f->String.valueOf(f.get("label")).endsWith("网点")&&"人".equals(f.get("unit"))).findFirst().get();
        assertEquals(0,((Number)zero.get("value")).intValue());assertEquals(240,((Number)zero.get("sample_size")).intValue());
        assertEquals("AVAILABLE",zero.get("status"));
    }

    @BeforeEach
    void setup() throws Exception {
        url = "jdbc:h2:mem:tagstats" + UUID.randomUUID() + ";MODE=MySQL;DATABASE_TO_LOWER=TRUE";
        keeper = DriverManager.getConnection(url);
        try (Statement st = keeper.createStatement()) {
            st.execute("create table customer(customer_key varchar(16), customer_count int, aum decimal(18,2), risk_level int, channel varchar(24), note varchar(64), ratio decimal(10,6))");
        }
        try (PreparedStatement ps = keeper.prepareStatement("insert into customer values(?,?,?,?,?,?,?)")) {
            for (int i = 1; i <= 800; i++) {
                ps.setString(1, "C" + String.format("%08d", i));
                ps.setInt(2, i);
                ps.setBigDecimal(3, i <= 240 ? (i <= 120 ? new BigDecimal("200000") : new BigDecimal("800000")) : new BigDecimal("500000"));
                ps.setInt(4, 2);
                ps.setString(5, "app");
                ps.setString(6, "备注" + i);
                ps.setBigDecimal(7, new BigDecimal("0.406600"));
                ps.addBatch();
            }
            ps.executeBatch();
        }
        service = new TsTagStatsService();
        ext = mock(TlObjectGroupExtMapper.class);
        tags = mock(TlTagMapper.class);
        semantics = mock(TsTagSemanticMapper.class);
        codeOptions = mock(IDimensionCodeOptionService.class);
        DpOnlineVersionResolver versions = mock(DpOnlineVersionResolver.class);
        IRuleSqlBuilder rules = mock(IRuleSqlBuilder.class);
        JdbcConnectionFactory connections = mock(JdbcConnectionFactory.class);
        DataBrokerCryptoService crypto = mock(DataBrokerCryptoService.class);
        ReflectionTestUtils.setField(service, "ext", ext);
        ReflectionTestUtils.setField(service, "tags", tags);
        ReflectionTestUtils.setField(service, "semantics", semantics);
        ReflectionTestUtils.setField(service, "versions", versions);
        ReflectionTestUtils.setField(service, "rules", rules);
        ReflectionTestUtils.setField(service, "ruleValidator", mock(RuleTagValidator.class));
        ReflectionTestUtils.setField(service, "codeOptions", codeOptions);
        ReflectionTestUtils.setField(service, "connections", connections);
        ReflectionTestUtils.setField(service, "crypto", crypto);
        ReflectionTestUtils.setField(service, "json", new com.fasterxml.jackson.databind.ObjectMapper());
        TsPublishedAnalysisCatalog published=mock(TsPublishedAnalysisCatalog.class);
        ReflectionTestUtils.setField(service,"publishedAnalysis",published);
        when(published.tags(eq(LIBRARY),anySet())).thenAnswer(call->{
            Map<Long,com.fasterxml.jackson.databind.JsonNode> out=new LinkedHashMap<>();
            for(Long id:(Set<Long>)call.getArgument(1)) {
                TsTagSemantic semantic=semantics.selectByTagId(id);Map<String,Object> definition=new LinkedHashMap<>();
                definition.put("unit",semantic==null?null:semantic.getUnit());definition.put("unit_scale",semantic==null||semantic.getUnitScale()==null?BigDecimal.ONE:semantic.getUnitScale());
                out.put(id,new com.fasterxml.jackson.databind.ObjectMapper().valueToTree(definition));
            }
            return out;
        });
        DpResolvedVersion version = new DpResolvedVersion();
        version.setVersionId(VERSION);
        when(versions.resolve(1L)).thenReturn(version);
        when(ext.selectDatasetIdByLibrary(LIBRARY)).thenReturn(1L);
        when(ext.selectVersionDefinitionJson(VERSION)).thenReturn("{\"tableId\":9}");
        when(ext.selectTableObjectName(9L)).thenReturn("customer");
        when(rules.resolveObjectKeyColumn(eq(VERSION), any())).thenReturn("customer_key");
        when(rules.buildSql(eq(VERSION), any(), eq(IRuleSqlBuilder.MODE_IDS))).thenReturn("select customer_key from customer where customer_count<=" + COHORT);
        DpDataSource source = new DpDataSource();
        source.setPasswordCipher("encrypted");
        when(ext.selectDataSourceByDataset(1L)).thenReturn(source);
        when(crypto.decrypt("encrypted")).thenReturn("synthetic");
        when(connections.createConnection(eq(source), eq("synthetic"))).thenAnswer(a -> DriverManager.getConnection(url));
        when(ext.selectColumnNameByAlias(eq(VERSION), anyString())).thenAnswer(a -> a.getArgument(1));
        when(codeOptions.listCodeOptions(anyLong(), anyString())).thenReturn(new ArrayList<>());
    }

    @AfterEach
    void close() throws Exception {
        if (keeper != null) keeper.close();
    }

    private TlTag tag(Long id, String name, String type, String field) {
        TlTag tag = new TlTag();
        tag.setTagId(id);
        tag.setLibraryId(LIBRARY);
        tag.setStatus("2");
        tag.setSourceStatus("AVAILABLE");
        tag.setSourceVersionId(VERSION);
        tag.setTagName(name);
        tag.setTagType(type);
        tag.setDataType("数值型".equals(type) ? "decimal" : "varchar");
        tag.setFieldName(field);
        when(tags.selectTagById(id)).thenReturn(tag);
        return tag;
    }

    private void unit(Long tagId, String unit) {
        unit(tagId, unit, null);
    }

    private void unit(Long tagId, String unit, String scale) {
        TsTagSemantic semantic = new TsTagSemantic();
        semantic.setUnit(unit);
        semantic.setUnitScale(scale == null ? null : new BigDecimal(scale));
        when(semantics.selectByTagId(tagId)).thenReturn(semantic);
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> stats(Map<String, Object> result) {
        return (List<Map<String, Object>>) result.get("tag_stats");
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> entry(Map<String, Object> result, int index) {
        return stats(result).get(index);
    }

    @Test
    void numericTagProducesServerVerifiedStatisticsWithGovernedUnit() {
        tag(812L, "总资产", "数值型", "aum");
        unit(812L, "CNY");
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(812L),
            new HashSet<>(Arrays.asList(812L)), new HashSet<>(Arrays.asList(812L)));
        Map<String, Object> entry = entry(result, 0);
        assertEquals("AVAILABLE", entry.get("status"));
        assertEquals("总资产", entry.get("label"));
        assertEquals("元", entry.get("unit"));
        assertEquals("ts_tag_semantic", entry.get("unit_source"));
        assertEquals(Boolean.TRUE, entry.get("plan_tag"));
        assertEquals(COHORT, entry.get("sample_size"));
        Map<String, Object> numeric = (Map<String, Object>) entry.get("numeric");
        assertEquals(240L, ((Number) numeric.get("n")).longValue());
        assertEquals(0L, ((Number) numeric.get("missing")).longValue());
        assertEquals(0, new BigDecimal(String.valueOf(numeric.get("sum"))).compareTo(new BigDecimal("120000000")));
        assertEquals(0, new BigDecimal(String.valueOf(numeric.get("avg"))).compareTo(new BigDecimal("500000")));
        assertEquals(0, new BigDecimal(String.valueOf(numeric.get("median"))).compareTo(new BigDecimal("500000")));
        assertEquals(0, new BigDecimal(String.valueOf(numeric.get("min"))).compareTo(new BigDecimal("200000")));
        assertEquals(0, new BigDecimal(String.valueOf(numeric.get("max"))).compareTo(new BigDecimal("800000")));
    }

    @Test
    void governedUnitsMapToFactUnitsAndUnknownOnesStayUnusable() {
        tag(812L, "总资产", "数值型", "aum");
        assertUnit("RATIO", "%"); assertUnit("SHARE", "%");
        assertUnit("COUNT", "人"); assertUnit("PERSON", "人"); assertUnit("POINT", "分");
        assertUnit("MONTH", null); assertUnit("DAY", null); assertUnit("NONE", null);
    }

    private void assertUnit(String governed, String expected) {
        unit(812L, governed);
        assertEquals(expected, entry(result(812L), 0).get("unit"), governed);
    }

    private Map<String, Object> result(Long tagId) {
        return service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(tagId),
            new HashSet<>(Arrays.asList(tagId)), new HashSet<>());
    }

    @Test
    void ratioAndScaledAmountsAreConvertedToFactUnits() {
        // 比率量纲的物理值是 0.4066 的小数，事实单位是 %，必须折算成 40.66
        tag(719L, "固收类AUM占比", "数值型", "ratio");
        unit(719L, "RATIO", "1");
        Map<String, Object> entry = entry(result(719L), 0);
        assertEquals("%", entry.get("unit"));
        assertEquals(40.66d, ((Number) numeric(entry).get("avg")).doubleValue());
        assertEquals(40.66d, ((Number) numeric(entry).get("median")).doubleValue());

        // 万元量纲（unit_scale=10000）必须折算到元，而不是原样当元输出
        tag(781L, "万元口径余额", "数值型", "ratio");
        unit(781L, "CNY", "10000");
        entry = entry(result(781L), 0);
        assertEquals("元", entry.get("unit"));
        assertEquals(4066.0d, ((Number) numeric(entry).get("min")).doubleValue());
    }

    private Map<String, Object> numeric(Map<String, Object> entry) {
        return (Map<String, Object>) entry.get("numeric");
    }

    @Test
    void tagWithoutGovernedUnitIsNotUsableAsFact() {
        tag(813L, "客户评分", "数值型", "aum");
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(813L),
            new HashSet<>(Arrays.asList(813L)), new HashSet<>());
        assertNull(entry(result, 0).get("unit"));
        assertEquals("none", entry(result, 0).get("unit_source"));
        assertEquals("AVAILABLE", entry(result, 0).get("status"));
    }

    @Test
    void categoryTagProducesDistributionWithSharesAndCodeLabels() throws Exception {
        keeper.createStatement().execute("update customer set risk_level=3 where customer_count<=40");
        tag(640L, "风险等级", "选项型", "risk_level");
        unit(640L, "NONE");
        Map<String, Object> mapping = new LinkedHashMap<>();
        mapping.put("code", "2");
        mapping.put("codeDefinition", "稳健型");
        Map<String, Object> mapping3 = new LinkedHashMap<>();
        mapping3.put("code", "3");
        mapping3.put("codeDefinition", "平衡型");
        when(codeOptions.listCodeOptions(LIBRARY, "risk_level")).thenReturn(Arrays.asList(mapping, mapping3));
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(640L),
            new HashSet<>(Arrays.asList(640L)), new HashSet<>());
        Map<String, Object> entry = entry(result, 0);
        assertEquals("AVAILABLE", entry.get("status"));
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> categories = (List<Map<String, Object>>) entry.get("categories");
        assertEquals(2, categories.size());
        assertEquals("稳健型", categories.get(0).get("label"));
        assertEquals(200L, ((Number) categories.get(0).get("count")).longValue());
        assertEquals(83.3d, ((Number) categories.get(0).get("share")).doubleValue());
        assertEquals(16.7d, ((Number) categories.get(1).get("share")).doubleValue());
    }

    @Test
    void smallCategoryBucketSuppressesWholeDistribution() throws Exception {
        keeper.createStatement().execute("update customer set risk_level=3 where customer_count<=5");
        tag(640L, "风险等级", "选项型", "risk_level");
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(640L),
            new HashSet<>(Arrays.asList(640L)), new HashSet<>());
        assertEquals("SUPPRESSED", entry(result, 0).get("status"));
        assertTrue(String.valueOf(entry(result, 0).get("reason")).contains("整组已抑制"));
    }

    @Test
    void revokedOrForeignTagOnlyDegradesItsOwnEntry() {
        tag(812L, "总资产", "数值型", "aum");
        unit(812L, "CNY");
        TlTag foreign = tag(900L, "外部标签", "数值型", "aum");
        foreign.setLibraryId(108L);
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(900L, 812L),
            new HashSet<>(Arrays.asList(900L, 812L)), new HashSet<>());
        assertEquals("MISSING", entry(result, 0).get("status"));
        assertEquals("AVAILABLE", entry(result, 1).get("status"));
    }

    @Test
    void cohortCountDriftDiscardsEveryStatistic() throws Exception {
        keeper.createStatement().execute("delete from customer where customer_count<=10");
        tag(812L, "总资产", "数值型", "aum");
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(812L),
            new HashSet<>(Arrays.asList(812L)), new HashSet<>());
        assertEquals("MISSING", entry(result, 0).get("status"));
        assertTrue(String.valueOf(entry(result, 0).get("reason")).contains("人数"));
        assertNull(result.get("sample_rows"));
    }

    @Test
    void unsupportedTypeProducesNoNumbers() {
        tag(700L, "开户日期", "日期型", "note");
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(700L),
            new HashSet<>(Arrays.asList(700L)), new HashSet<>());
        assertEquals("UNSUPPORTED", entry(result, 0).get("status"));
        assertNull(entry(result, 0).get("numeric"));
    }

    @Test
    void sampleRowsMaskCustomerKeyAndKeepOnlySelectedColumns() {
        tag(812L, "总资产", "数值型", "aum");
        unit(812L, "CNY");
        tag(640L, "风险等级", "选项型", "risk_level");
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(812L, 640L),
            new HashSet<>(Arrays.asList(812L, 640L)), new HashSet<>());
        Map<String, Object> sample = (Map<String, Object>) result.get("sample_rows");
        assertEquals(Arrays.asList("总资产", "风险等级"), sample.get("columns"));
        assertEquals(100, sample.get("limit"));
        assertEquals(Boolean.TRUE, sample.get("masked"));
        @SuppressWarnings("unchecked")
        List<List<Object>> rows = (List<List<Object>>) sample.get("rows");
        assertEquals(100, rows.size());
        assertEquals(3, rows.get(0).size());
        assertEquals("C****0001", String.valueOf(rows.get(0).get(0)));
        assertEquals(0, new BigDecimal(String.valueOf(rows.get(0).get(1))).compareTo(new BigDecimal("200000")));
        assertTrue(String.valueOf(sample.get("note")).contains("脱敏"));
    }

    @Test
    void uncountedCohortExplainsWhyStatisticsAreMissing() {
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), null, Arrays.asList(812L),
            new HashSet<>(Arrays.asList(812L)), new HashSet<>());
        assertTrue(stats(result).isEmpty());
        assertNull(result.get("sample_rows"));
        assertTrue(String.valueOf(result.get("stats_note")).contains("尚未统计"));
    }

    @Test
    void cohortBelowSuppressionThresholdProducesNothing() {
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), 12L, Arrays.asList(812L),
            new HashSet<>(Arrays.asList(812L)), new HashSet<>());
        assertTrue(stats(result).isEmpty());
        assertNull(result.get("sample_rows"));
        assertTrue(String.valueOf(result.get("stats_note")).contains("不足"));
    }

    @Test
    void noSelectedTagsSkipsDatabaseEntirely() {
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, new ArrayList<>(),
            new HashSet<>(), new HashSet<>());
        assertTrue(stats(result).isEmpty());
        assertEquals("", result.get("stats_note"));
        verify(ext, never()).selectDatasetIdByLibrary(anyLong());
    }

    @Test
    void nonIdentifierColumnIsRejectedBeforeQuery() {
        tag(812L, "总资产", "数值型", "aum");
        when(ext.selectColumnNameByAlias(VERSION, "aum")).thenReturn("aum`; drop table customer; --");
        Map<String, Object> result = service.collect(LIBRARY, new RulePayload(), COHORT, Arrays.asList(812L),
            new HashSet<>(Arrays.asList(812L)), new HashSet<>());
        assertEquals("MISSING", entry(result, 0).get("status"));
    }
}
