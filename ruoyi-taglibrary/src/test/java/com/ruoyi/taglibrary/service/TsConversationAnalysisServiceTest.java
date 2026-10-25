package com.ruoyi.taglibrary.service;

import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.framework.web.service.PermissionService;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.taglibrary.domain.TsAgentThread;
import org.junit.jupiter.api.*;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;

@SuppressWarnings("unchecked")
class TsConversationAnalysisServiceTest {
    TsConversationAnalysisService service;
    TsTagStatsService stats;
    TsAudiencePlanCompiler compiler;
    PermissionService permissions;
    TsAgentThread row;
    Map<String,Object> state;
    Map<String,Object> plan;
    Map<String,Object> bundle;

    @BeforeEach void setup() {
        service=new TsConversationAnalysisService();stats=mock(TsTagStatsService.class);compiler=mock(TsAudiencePlanCompiler.class);permissions=mock(PermissionService.class);
        ITsCatalogRuntimeService catalog=mock(ITsCatalogRuntimeService.class);
        ReflectionTestUtils.setField(service,"stats",stats);ReflectionTestUtils.setField(service,"compiler",compiler);ReflectionTestUtils.setField(service,"permissions",permissions);
        ReflectionTestUtils.setField(service,"catalog",catalog);ReflectionTestUtils.setField(service,"json",new ObjectMapper());
        when(permissions.hasPermi(anyString())).thenReturn(true);when(compiler.compile(eq(107L),anyMap())).thenReturn(new RulePayload());
        when(catalog.activeBundle(107L)).thenReturn(map("build_id","b","snapshot_id","s","artifact_hash","a"));when(catalog.eligibleTagIds(107L,"s")).thenReturn(Arrays.asList(1L));
        row=new TsAgentThread();row.setLibraryId(107L);row.setThreadId("t");
        plan=map("valid",true,"build_id","b","snapshot_id","s","artifact_hash","a","summary","合成测试客群");
        state=map("revision",2,"plan",plan,"run_id","run","status","RUNNING","messages",new ArrayList<>(),"run_request",map("profile","conversation","build_id","b","snapshot_id","s","artifact_hash","a"));
        state.put("analysis_session",service.begin(state,map()));
        Map<String,Object> total=fact("f-a-total",240,"人",null),first=fact("f-a-0",200000,"元",null),second=fact("f-a-1",800000,"元",null);
        bundle=map("snapshot_id","data-batch","facts",new ArrayList<>(Arrays.asList(total,first,second)),"queries",Arrays.asList(map("id","a","status","AVAILABLE","unit","元","metric_label","资产均值","population","target","rows",Arrays.asList(map("category","南京","column",null,"fact_id","f-a-0"),map("category","苏州","column",null,"fact_id","f-a-1")))));
        when(stats.analysisBatch(eq(107L),anyMap(),anyList(),anySet())).thenReturn(bundle);
    }
    Map<String,Object> fact(String id,Number value,String unit,String denominator) {return map("id",id,"value",value,"unit",unit,"sample_size",240,"status","AVAILABLE","query_id","analysis.a."+id,"definition_key","same-metric","role","OBSERVED","denominator_id",denominator,"derived_from",new ArrayList<>(),"exclusions_applied",new ArrayList<>());}
    Map<String,Object> query(){return service.handle(row,state,"query_aggregates",map("queries",Arrays.asList(map("id","a","tag_id",1,"operation","avg"))));}
    Map<String,Object> chart(){return map("type","chart","title","机构资产均值","query_ids",Arrays.asList("a"),"kind","bar");}

    @Test void bindsWanYuanAndCountLiteralsToFactReferences() {
        query();
        Map<String,Object> result=service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(
            map("type","text","text","资产均值为20万元，覆盖240名客户。")),"complete",false));
        assertEquals("资产均值为200000元，覆盖240人客户。",((List<Map<String,Object>>)result.get("parts")).get(0).get("text"));
    }
    @Test void publishesValidatedBlocksAndRejectsUnboundNumbersWithoutPartialMutation() {
        query();
        assertThrows(IllegalArgumentException.class,()->service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(chart(),map("type","text","text","共999人")))));
        assertFalse(state.containsKey("analysis_artifacts"));
        Map<String,Object> result=service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(map("type","text","text","资产均值为{fact:f-a-0}。"),chart()),"complete",false));
        assertEquals("资产均值为200000元。",((List<Map<String,Object>>)result.get("parts")).get(0).get("text"));
        assertEquals(false,result.get("complete"));assertEquals(1,((Map)state.get("analysis_artifacts")).size());
    }
    @Test void verifiedMetricWindowCanBeNamedWithoutAllowingUnboundValues() {
        ((List<Map<String,Object>>)bundle.get("facts")).get(1).put("label","近30天异名跨行转入金额 · 均值");
        query();
        Map<String,Object> result=service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(
            map("type","text","text","近30天异名跨行转入金额均值为{fact:f-a-0}。")),"complete",false));
        assertEquals("近30天异名跨行转入金额均值为200000元。",((List<Map<String,Object>>)result.get("parts")).get(0).get("text"));
        assertThrows(IllegalArgumentException.class,()->service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(
            map("type","text","text","近30天异名跨行转入金额为999万元")))));
        assertThrows(IllegalArgumentException.class,()->service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(
            map("type","text","text","近7天异名跨行转入金额为{fact:f-a-0}")))));
    }
    @Test void chartViewChangeKeepsEvidenceAndOriginalVersionWithoutQuerying() {
        query();service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(chart())));
        Map<String,Object> artifacts=(Map<String,Object>)state.get("analysis_artifacts");Map<String,Object> original=(Map<String,Object>)artifacts.values().iterator().next();
        state.put("analysis_session",service.begin(state,map("target_artifact_id",original.get("id"),"target_artifact_version",1)));
        clearInvocations(stats);
        service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(map("type","chart","view_only",true,"kind","bar","orientation","horizontal","sort","descending"))));
        verifyNoInteractions(stats);
        Map<String,Object> edited=(Map<String,Object>)artifacts.get(original.get("id")+"@2");
        assertEquals("vertical",((Map)original.get("spec")).get("orientation"));assertEquals("horizontal",((Map)edited.get("spec")).get("orientation"));
        assertEquals(original.get("snapshot_id"),edited.get("snapshot_id"));assertEquals(original.get("facts"),edited.get("facts"));
    }
    @Test void identicalQueryUsesCacheAndPermissionsAreCheckedAgain() {
        query();query();verify(stats,times(1)).analysisBatch(anyLong(),anyMap(),anyList(),anySet());
        when(permissions.hasPermi("taglibrary:insight:run")).thenReturn(false);
        assertThrows(com.ruoyi.common.exception.ServiceException.class,()->query());
    }
    @Test void referencedFactsRenderUnitsOnlyOnceAndRejectUnsupportedShapeClaims() {
        query();
        assertThrows(IllegalArgumentException.class,()->service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(map("type","text","text","均值高于中位数说明分布右偏")))));
        Map<String,Object> result=service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(map("type","text","text","规模{fact:f-a-total}人，均值{fact:f-a-0}元。"))));
        assertEquals("规模240人，均值200000元。",((List<Map<String,Object>>)result.get("parts")).get(0).get("text"));
    }
    @Test void scopeChangeAndNewSnapshotInvalidateOldDerivedFacts() {
        query();service.handle(row,state,"derive_facts",map("id","f-diff","label","差值","operation","difference","fact_ids",Arrays.asList("f-a-1","f-a-0")));
        assertTrue(((List<Map<String,Object>>)bundle.get("facts")).stream().anyMatch(f->"f-diff".equals(f.get("id"))));
        Map<String,Object> replacement=new LinkedHashMap<>(bundle);replacement.put("facts",new ArrayList<>(Arrays.asList(fact("f-new",40,"人",null))));replacement.put("snapshot_id","new-batch");
        when(stats.analysisBatch(eq(107L),anyMap(),anyList(),anySet())).thenReturn(replacement);
        service.handle(row,state,"query_aggregates",map("queries",Arrays.asList(map("id","b","operation","count"))));
        assertThrows(IllegalArgumentException.class,()->service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(map("type","text","text","差值为{fact:f-diff}")))));
    }
    @Test void crossThreadAndStaleChartReferencesAreRejected() {
        assertThrows(com.ruoyi.common.exception.ServiceException.class,()->service.begin(state,map("target_artifact_id","other-thread","target_artifact_version",1)));
        query();service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(chart())));
        Map<String,Object> artifact=(Map<String,Object>)((Map)state.get("analysis_artifacts")).values().iterator().next();state.put("revision",3);
        assertThrows(com.ruoyi.common.exception.ServiceException.class,()->service.begin(state,map("target_artifact_id",artifact.get("id"),"target_artifact_version",1)));
    }
    @Test void latestChartOnCurrentRevisionStaysAvailableAsImplicitTarget() {
        query();service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(chart())));
        Map<String,Object> artifact=(Map<String,Object>)((Map)state.get("analysis_artifacts")).values().iterator().next();
        state.put("messages",Arrays.asList(map("id","a1","role","assistant","parts",Arrays.asList(map("id","p1","type","chart","artifact_id",artifact.get("id"),"artifact_version",artifact.get("version"))))));
        Map<String,Object> session=service.begin(state,map());
        assertFalse(((Map<String,Object>)session.get("target")).isEmpty());
    }
    @Test void newQuestionAfterCohortRevalidationSkipsStaleChartInsteadOfFailing() {
        query();service.handle(row,state,"submit_insight_result",map("blocks",Arrays.asList(chart())));
        Map<String,Object> artifact=(Map<String,Object>)((Map)state.get("analysis_artifacts")).values().iterator().next();
        state.put("messages",Arrays.asList(map("id","a1","role","assistant","parts",Arrays.asList(map("id","p1","type","chart","artifact_id",artifact.get("id"),"artifact_version",artifact.get("version"))))));
        state.put("revision",3);
        Map<String,Object> session=service.begin(state,map());
        assertFalse(session.containsKey("target"));
        assertFalse(session.containsKey("artifact_choices"));
    }
}
