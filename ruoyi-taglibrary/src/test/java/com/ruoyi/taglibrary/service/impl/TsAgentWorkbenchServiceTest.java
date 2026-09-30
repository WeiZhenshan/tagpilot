package com.ruoyi.taglibrary.service.impl;

import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.context.SecurityContextHolder;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.core.domain.model.LoginUser;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.framework.web.service.PermissionService;
import com.ruoyi.objectgroup.domain.*;
import com.ruoyi.objectgroup.domain.vo.RuleRunResultVO;
import com.ruoyi.objectgroup.service.ITlObjectGroupService;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.domain.agent.TsPlanValidationException;
import com.ruoyi.taglibrary.mapper.*;
import com.ruoyi.taglibrary.service.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(MockitoExtension.class)
class TsAgentWorkbenchServiceTest extends BaseServiceTest {
    @Mock TsAgentThreadMapper threads;
    @Spy ObjectMapper json=new ObjectMapper();
    @Mock DataBrokerCryptoService crypto;
    @Mock PermissionService permissions;
    @Mock ITlTagLibraryService libraries;
    @Mock ITsCatalogRuntimeService catalog;
    @Mock TsAgentClient agent;
    @Mock TsAudiencePlanCompiler compiler;
    @Mock ITlObjectGroupService groups;
    @Mock ITlTagService tags;
    @Mock TsAgentSkillService agentSkills;
    @InjectMocks TsAgentWorkbenchService service;
    TsAgentThread row;
    @BeforeEach void setup() throws Exception {
        ((LoginUser)SecurityContextHolder.getContext().getAuthentication().getPrincipal()).setUserId(2L);
        row=new TsAgentThread();row.setThreadId("owned");row.setUserId(2L);row.setLibraryId(107L);row.setRowVersion(0L);row.setTitle("测试");row.setArchived("0");row.setPinned("0");
        lenient().when(threads.lock("owned",2L)).thenReturn(row);
        lenient().when(permissions.hasAnyPermi(anyString())).thenReturn(true);
        lenient().when(permissions.hasPermi(anyString())).thenReturn(true);
        lenient().when(libraries.selectLibraryById(107L)).thenReturn(new TlTagLibrary());
        lenient().when(crypto.encrypt(anyString())).thenAnswer(i->i.getArgument(0));
        lenient().when(crypto.decrypt(anyString())).thenAnswer(i->i.getArgument(0));
        lenient().when(threads.update(any())).thenReturn(1);
        state(map("revision",2,"status","COMPLETED","plan",map("valid",true,"hash","h"),"messages",new ArrayList<>()));
    }
    void state(Map<String,Object> s) throws Exception {row.setPayload(json.writeValueAsString(s));}
    Map<String,Object> confirmation(){return map("base_revision",2,"plan_hash","h","name","测试客群");}
    void activeTags() {
        when(catalog.activeBundle(107L)).thenReturn(map("build_id","build","snapshot_id","snapshot","artifact_hash","hash"));
        when(catalog.eligibleTagIds(107L,"snapshot")).thenReturn(Arrays.asList(1L,2L));
    }
    TlTag tag(Long id,Long library,String name) {TlTag tag=new TlTag();tag.setTagId(id);tag.setLibraryId(library);tag.setTagName(name);return tag;}
    @Test void tagTreePrunesIneligibleLeavesAndPhysicalMetadata() {
        activeTags();
        when(tags.buildTree(107L,"online")).thenReturn(Arrays.asList(map("id","lib-107","label","库","children",Arrays.asList(
            map("id","dir-1","label","目录","children",Arrays.asList(map("id","tag-1","label","余额","tagType","数值型","fieldName","secret_column"),map("id","tag-3","label","不可执行"))),
            map("id","dir-2","label","空目录","children",Arrays.asList(map("id","tag-9","label","未发布")))))));
        String result=json.valueToTree(service.tagTree(107L)).toString();
        assertTrue(result.contains("tag-1"));assertFalse(result.contains("tag-3"));assertFalse(result.contains("空目录"));assertFalse(result.contains("secret_column"));
    }
    @Test void contextTagsAreValidatedForwardedAndSavedWithoutChangingText() {
        activeTags();when(tags.selectTagById(1L)).thenReturn(tag(1L,107L,"余额"));
        Map<String,Object> result=service.start("owned",map("base_revision",2,"client_request_id","context-request-001","message","请帮我梳理", "context_tag_ids",Arrays.asList(1),"context_only",true));
        ArgumentCaptor<Map> req=ArgumentCaptor.forClass(Map.class);verify(agent).post(eq("/agent/v2/runs"),req.capture());
        assertEquals(Arrays.asList(1L),req.getValue().get("pinned_tag_ids"));assertEquals(true,req.getValue().get("pinned_only"));
        assertEquals("请帮我梳理",req.getValue().get("requirement"));
        Map message=(Map)((List)result.get("messages")).get(0);assertEquals("余额",((Map)((List)message.get("context_tags")).get(0)).get("name"));
        // 相同编号的标签顺序、Jackson Integer/Long 差异不能破坏幂等。
        service.start("owned",map("client_request_id","context-request-001","message","请帮我梳理","context_tag_ids",Arrays.asList(1),"context_only",true));
        assertThrows(ServiceException.class,()->service.start("owned",map("client_request_id","context-request-001","message","请帮我梳理","context_tag_ids",Arrays.asList(2),"context_only",true)));
        verify(agent,times(1)).post(eq("/agent/v2/runs"),any());
    }
    @Test void rejectsOversizedInvalidAndWrongLibraryContextBeforeAgent() {
        assertThrows(ServiceException.class,()->service.start("owned",map("context_tag_ids",Arrays.asList(1,2,3,4,5,6))));
        assertThrows(ServiceException.class,()->service.start("owned",map("context_tag_ids",Arrays.asList(-1))));
        assertThrows(ServiceException.class,()->service.start("owned",map("context_tag_ids",Arrays.asList("1"))));
        activeTags();when(tags.selectTagById(1L)).thenReturn(tag(1L,108L,"其他库"));
        assertThrows(ServiceException.class,()->service.start("owned",map("base_revision",2,"client_request_id","context-request-002","message","需求","context_tag_ids",Arrays.asList(1))));
        verifyNoInteractions(agent);
    }
    @Test void skillRunUsesServerCohortAndPreservesCountAndExecution() throws Exception {
        activeTags();
        Map<String,Object> plan=map("valid",true,"hash","h","build_id","build","snapshot_id","snapshot","tree",map("clause_id","all","status","BOUND"));
        state(map("revision",2,"status","COMPLETED","plan",plan,"count",map("value",240,"revision",2,"plan_hash","h"),"execution",map("group_id",90),"messages",new ArrayList<>()));
        when(agentSkills.published()).thenReturn(Arrays.asList(map("name","test-analysis","user_invocable",true,"version","1.0.0")));
        Map<String,Object> result=service.start("owned",map("base_revision",2,"plan_hash","h","client_request_id","skill-request-001","message","合成分析", "skill_name","test-analysis","cohort_context",map("count",999)));
        ArgumentCaptor<Map> req=ArgumentCaptor.forClass(Map.class);verify(agent).post(eq("/agent/v2/runs"),req.capture());
        Map cohort=(Map)req.getValue().get("cohort_context");assertEquals(240,((Map)cohort.get("count")).get("value"));
        assertEquals("skill",req.getValue().get("profile"));assertEquals(2,result.get("revision"));assertNotNull(result.get("count"));assertNotNull(result.get("execution"));
    }
    @Test void skillRunOmitsStaleCountsAndRejectsRetiredSkills() throws Exception {
        activeTags();
        Map<String,Object> plan=map("valid",true,"hash","h","build_id","build","snapshot_id","snapshot","tree",map("clause_id","all","status","BOUND"));
        state(map("revision",2,"status","COMPLETED","plan",plan,"count",map("value",240,"revision",1,"plan_hash","old"),"messages",new ArrayList<>()));
        when(agentSkills.published()).thenReturn(new ArrayList<>());
        Map<String,Object> request=map("base_revision",2,"plan_hash","h","client_request_id","skill-request-002","message","合成分析", "skill_name","test-analysis");
        assertThrows(ServiceException.class,()->service.start("owned",request));verifyNoInteractions(agent);
        when(agentSkills.published()).thenReturn(Arrays.asList(map("name","test-analysis","user_invocable",true)));
        service.start("owned",request);
        ArgumentCaptor<Map> req=ArgumentCaptor.forClass(Map.class);verify(agent).post(eq("/agent/v2/runs"),req.capture());
        assertNull(((Map)req.getValue().get("cohort_context")).get("count"));
    }
    Map<String,Object> skillSyncState() throws Exception {
        Map<String,Object> plan=map("valid",true,"hash","h","build_id","build","snapshot_id","snapshot","tree",map("clause_id","all","status","BOUND"));
        state(map("revision",2,"status","RUNNING","run_id","r","messages",new ArrayList<>(),"events",new ArrayList<>(),"plan",plan,
            "count",map("value",240,"revision",2,"plan_hash","h","executed_at","2026-09-30T10:00:00Z"),
            "run_request",map("profile","skill","skill_name","test-analysis","requirement","分析这批客户","reference_date","2026-09-30",
                "skill_packages",Arrays.asList(map("name","test-analysis","display_name","测试分析","version","1.2.0","instructions","x")),
                "cohort_context",map("name","测试客群","plan",plan,"count",map("value",240)))));
        return plan;
    }
    Map<String,Object> availableFact() {
        return map("id","f-count","metric","customer_count","label","客群规模","value",240,"unit","人","sample_size",240,"status","AVAILABLE",
            "query_id","cohort.count","evidence",Arrays.asList("服务端核验"),"role","OBSERVED","denominator_id",null,"derived_from",Arrays.asList(),"exclusions_applied",Arrays.asList());
    }
    Map<String,Object> validCard() {
        return map("id","card-1","title","客群概况",
            "facts",map("text","共 {fact:f-count}。","fact_ids",Arrays.asList("f-count")),
            "comparison",map("text","无基准。","fact_ids",Arrays.asList(),"benchmark_fact_ids",Arrays.asList(),"difference_fact_ids",Arrays.asList()),
            "diagnosis",map("text","未形成诊断。","fact_ids",Arrays.asList(),"basis","RULE"),
            "action",map("text","不产出行动对象。","fact_ids",Arrays.asList(),"population_fact_id",null,"priority","NONE"),
            "boundary",map("text","仅覆盖规模。","data_as_of","","skill_version","","sample_fact_id","f-count","metric_definitions",Arrays.asList("customer_count：客户数")));
    }
    @Test void skillRunBuildsPanelReportWithServerMetadata() throws Exception {
        skillSyncState();
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),"result",map("skill_output","分析正文。",
            "skill_result",map("status","PARTIAL","reasons",Arrays.asList("指标未接入"),"facts",Arrays.asList(availableFact()),"cards",Arrays.asList(validCard()),
                "charts",Arrays.asList(map("schema_version",1,"id","chart-scale","title","客群规模","kind","kpi")),"followups",Arrays.asList("接入指标后重跑")))));
        Map<String,Object> result=service.get("owned");
        assertEquals("分析正文。",((Map)((List)result.get("messages")).get(0)).get("text"));
        Map<String,Object> report=(Map<String,Object>)result.get("skill_report");
        assertNotNull(report);assertEquals("r",report.get("run_id"));assertEquals("L2",report.get("level"));
        Map<String,Object> cohort=(Map<String,Object>)report.get("cohort");
        assertEquals("测试客群",cohort.get("audience_name"));assertEquals(240,cohort.get("count"));
        assertEquals("h",cohort.get("plan_hash"));assertEquals("2026-09-30",cohort.get("data_as_of"));assertEquals(107L,cohort.get("library_id"));
        Map<String,Object> entry=(Map<String,Object>)((List<?>)report.get("results")).get(0);
        assertEquals("test-analysis",entry.get("skill_id"));assertEquals("1.2.0",entry.get("skill_version"));assertEquals("测试分析",entry.get("display_name"));
        assertNotNull(entry.get("pack_hash"));assertEquals(1,((List<?>)entry.get("charts")).size());
        Map<String,Object> card=(Map<String,Object>)((List<?>)entry.get("cards")).get(0);
        assertEquals("1.2.0",((Map<String,Object>)card.get("boundary")).get("skill_version"));
        assertEquals("2026-09-30",((Map<String,Object>)card.get("boundary")).get("data_as_of"));
    }
    @Test void skillRunDropsCardsChartsAndResultsThatBreakRendering() throws Exception {
        skillSyncState();
        Map<String,Object> badCard=validCard();((Map<String,Object>)badCard.get("facts")).put("text","共 {fact:f-missing}。");
        Map<String,Object> undeclared=validCard();((Map<String,Object>)undeclared.get("comparison")).put("text","对比 {fact:f-count}。");
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),"result",map("skill_output","正文。",
            "skill_result",map("status","PARTIAL","reasons",Arrays.asList("指标未接入"),"facts",Arrays.asList(availableFact()),
                "cards",Arrays.asList(badCard,undeclared,validCard()),
                "charts",Arrays.asList(map("id","no-kind"),map("kind","bar","id","chart-ok")),"followups",Arrays.asList()))));
        Map<String,Object> result=service.get("owned");
        Map<String,Object> entry=(Map<String,Object>)((List<?>)((Map<String,Object>)result.get("skill_report")).get("results")).get(0);
        List<?> cards=(List<?>)entry.get("cards");assertEquals(1,cards.size());
        assertEquals("card-1",((Map<?,?>)cards.get(0)).get("id"));
        List<?> charts=(List<?>)entry.get("charts");assertEquals(1,charts.size());
        assertEquals("chart-ok",((Map<?,?>)charts.get(0)).get("id"));

        skillSyncState();
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),"result",map("skill_output","正文。","skill_result",map("status","WHAT"))));
        assertFalse(service.get("owned").containsKey("skill_report"));
    }
    @Test void skillRunWithoutStructuredResultKeepsTextMessageOnly() throws Exception {
        skillSyncState();
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),"result",map("skill_output","纯文本回答。")));
        Map<String,Object> result=service.get("owned");
        assertFalse(result.containsKey("skill_report"));
        assertEquals("纯文本回答。",((Map)((List)result.get("messages")).get(0)).get("text"));
    }
    TlObjectGroup source(Map<String,Object> plan) throws Exception {
        TlObjectGroup group=new TlObjectGroup();group.setGroupId(90L);group.setLibraryId(107L);group.setGroupName("原客群");
        group.setRuleJson(json.writeValueAsString(map("schemaVersion",4,"audiencePlan",plan)));
        return group;
    }
    void allowNewThread() {
        doAnswer(i->{TsAgentThread created=i.getArgument(0);when(threads.lock(created.getThreadId(),2L)).thenReturn(created);return 1;}).when(threads).insert(any());
    }
    @Test void fromGroupReusesOnlyMatchingOwnIdlePlanAndRequiresRevalidation() throws Exception {
        Map<String,Object> plan=map("hash","h","valid",true,"tree",map("clause_id","a","tag_id",1));
        state(map("revision",2,"status","COMPLETED","plan",plan,"messages",new ArrayList<>(),"versions",new ArrayList<>()));
        TlObjectGroup group=source(plan);when(groups.selectObjectGroupById(90L)).thenReturn(group);
        when(threads.executionsForGroup(90L,2L)).thenReturn(Arrays.asList(map("thread_id","owned","plan_hash","h")));
        Map<String,Object> result=service.fromGroup(90L);
        assertEquals("owned",result.get("thread_id"));assertEquals(true,result.get("source_thread_reused"));assertEquals(true,result.get("source_requires_validation"));
        assertEquals(90L,result.get("source_group_id"));assertFalse((Boolean)((Map)result.get("plan")).get("valid"));
        assertThrows(ServiceException.class,()->service.createGroup("owned",map("base_revision",3,"plan_hash",((Map)result.get("plan")).get("hash"),"name","更新")));
        verifyNoInteractions(agent);verify(threads,never()).insert(any());
    }
    @Test void fromGroupCopiesSavedConditionsWhenConversationDivergedOrDeleted() throws Exception {
        Map<String,Object> saved=map("hash","original","valid",true,"tree",map("clause_id","saved","tag_id",1,"assumption_confirmed",true));
        TlObjectGroup group=source(saved);when(groups.selectObjectGroupById(90L)).thenReturn(group);
        when(threads.executionsForGroup(90L,2L)).thenReturn(Arrays.asList(map("thread_id","owned","plan_hash","original"),map("thread_id","deleted","plan_hash","original")));
        allowNewThread();Map<String,Object> result=service.fromGroup(90L);
        assertNotEquals("owned",result.get("thread_id"));assertEquals(false,result.get("source_thread_reused"));
        assertEquals("saved",((Map)((Map)result.get("plan")).get("tree")).get("clause_id"));verifyNoInteractions(agent);
        assertEquals(Arrays.asList("saved"),result.get("confirmed_clause_ids"));
    }
    @Test void fromGroupRejectsMissingPermissionAndManualRules() throws Exception {
        when(permissions.hasPermi("objectgroup:group:edit")).thenReturn(false);
        assertThrows(ServiceException.class,()->service.fromGroup(90L));verifyNoInteractions(groups);
        when(permissions.hasPermi("objectgroup:group:edit")).thenReturn(true);
        TlObjectGroup manual=source(Collections.emptyMap());manual.setRuleJson("{\"schemaVersion\":3,\"conditions\":[]}");
        when(groups.selectObjectGroupById(90L)).thenReturn(manual);
        assertThrows(ServiceException.class,()->service.fromGroup(90L));verify(threads,never()).insert(any());
    }
    @Test void fromGroupRestoresExistingEditWithoutCreatingOrResettingProgress() throws Exception {
        Map<String,Object> saved=map("hash","saved","valid",true,"tree",map("clause_id","old","tag_id",1));
        TlObjectGroup group=source(saved);when(groups.selectObjectGroupById(90L)).thenReturn(group);
        Map<String,Object> draft=map("valid",false,"tree",map("clause_id","new","tag_id",2));
        state(map("revision",4,"status","WAITING","plan",draft,"source_group_id",90,"source_rule_hash",TsSnapshotCanonicalizer.sha256(group.getRuleJson()),
            "questions",Arrays.asList(map("prompt","待补充值")),"messages",new ArrayList<>(),"versions",new ArrayList<>()));
        when(threads.list(2L,"0")).thenReturn(Arrays.asList(row));
        Map<String,Object> first=service.fromGroup(90L),again=service.fromGroup(90L);
        assertEquals("owned",first.get("thread_id"));assertEquals(first.get("thread_id"),again.get("thread_id"));
        assertEquals("WAITING",again.get("status"));assertEquals(4,((Number)again.get("revision")).intValue());
        assertEquals(draft,again.get("plan"));assertFalse(again.containsKey("source_plan"));
        verify(threads,never()).insert(any());verifyNoInteractions(agent);
    }
    @Test void startUsesServerSavedSourceAndIgnoresBrowserSourceForgery() throws Exception {
        activeTags();Map<String,Object> saved=map("valid",true,"tree",map("clause_id","old"));
        state(map("revision",2,"status","IDLE","source_plan",saved,"messages",new ArrayList<>(),"versions",new ArrayList<>()));
        service.start("owned",map("base_revision",2,"client_request_id","saved-source-001","message","新增标签条件","source_plan",map("forged",true)));
        verify(agent).post(eq("/agent/v2/runs"),argThat(r->r instanceof Map && saved.equals(((Map)r).get("source_plan"))));
    }
    @Test void updatesOriginalGroupWithEditPermissionAndConflictProtection() throws Exception {
        TlObjectGroup source=source(map("tree",map("clause_id","a")));
        state(map("revision",2,"status","COMPLETED","plan",map("valid",true,"hash","h"),"source_group_id",90,
            "source_rule_hash",TsSnapshotCanonicalizer.sha256(source.getRuleJson()),"messages",new ArrayList<>()));
        when(groups.selectObjectGroupByIdForUpdate(90L)).thenReturn(source);
        when(threads.execution(eq("owned"),eq(2L),anyLong())).thenReturn(null);
        when(compiler.compile(eq(107L),any())).thenReturn(new RulePayload());when(groups.updateObjectGroup(any())).thenReturn(1);
        assertEquals(90L,service.createGroup("owned",confirmation()).get("group_id"));
        verify(groups).updateObjectGroup(argThat(g->g.getGroupId()==90L && "测试客群".equals(g.getGroupName())));verify(groups,never()).insertObjectGroup(any());
        verify(permissions,never()).hasPermi("objectgroup:group:add");
        state(map("revision",3,"status","COMPLETED","plan",map("valid",true,"hash","h"),"source_group_id",90,"source_rule_hash","stale"));
        assertThrows(ServiceException.class,()->service.createGroup("owned",map("base_revision",3,"plan_hash","h","name","更新")));
        verify(groups,times(1)).updateObjectGroup(any());
    }
    @Test void deniesOtherUsersThreadWithoutCallingAgent() {
        assertThrows(ServiceException.class,()->service.get("someone-elses-thread"));
        verifyNoInteractions(agent);
    }
    @Test void rejectsOldRevisionAndForgedHashBeforeExecution() {
        assertThrows(ServiceException.class,()->service.count("owned",map("base_revision",1,"plan_hash","h")));
        assertThrows(ServiceException.class,()->service.count("owned",map("base_revision",2,"plan_hash","forged")));
        verifyNoInteractions(groups,compiler);
    }
    @Test void deniesExecutionPermissionEvenForOwnedThread() {
        when(permissions.hasPermi("objectgroup:group:run")).thenReturn(false);
        assertThrows(ServiceException.class,()->service.count("owned",confirmation()));
        verifyNoInteractions(groups,compiler);
    }
    @Test void createIsIdempotentForConfirmedRevision() {
        when(threads.execution("owned",2L,2L)).thenReturn(map("group_id",90L,"revision",2));
        assertEquals(90L,service.createGroup("owned",confirmation()).get("group_id"));
        verifyNoInteractions(groups,compiler);
    }
    @Test void createsUsingTrustedCompilerAndRecordsExecution() {
        when(threads.execution("owned",2L,2L)).thenReturn(null);
        when(compiler.compile(eq(107L),any())).thenReturn(new RulePayload());
        doAnswer(i->{((TlObjectGroup)i.getArgument(0)).setGroupId(91L);return 1;}).when(groups).insertObjectGroup(any());
        assertEquals(91L,service.createGroup("owned",confirmation()).get("group_id"));
        verify(threads).executionInsert(anyString(),eq("owned"),eq(2L),eq(2L),eq("h"),eq(91L));
    }
    @Test void cancelledPartialPlanGetsNewVersionAndInvalidatesCount() throws Exception {
        state(map("revision",2,"status","RUNNING","run_id","r","count",map("value",100),"live_plan",map("tree",map("clause_id","a")),"versions",new ArrayList<>()));
        Map<String,Object> result=service.cancel("owned");
        assertEquals("CANCELLED",result.get("status"));assertEquals(3L,result.get("revision"));
        assertFalse(result.containsKey("count"));assertFalse((Boolean)((Map)result.get("plan")).get("valid"));
    }
    @Test void replayedStartCannotChangeRequestContent() throws Exception {
        state(map("revision",2,"status","RUNNING","run_id","same-request-00001","run_request",map("requirement","原需求","edited_plan",null)));
        assertThrows(ServiceException.class,()->service.start("owned",map("client_request_id","same-request-00001","message","篡改需求")));
        verifyNoInteractions(agent);
    }
    @Test void startSuppliesServerDateContextForOmittedYears() {
        when(catalog.activeBundle(107L)).thenReturn(map("build_id","build","snapshot_id","snapshot","artifact_hash","hash"));
        when(catalog.eligibleTagIds(107L,"snapshot")).thenReturn(Arrays.asList(858L,859L,601L));
        java.time.LocalDate before=java.time.LocalDate.now(java.time.ZoneId.of("Asia/Shanghai"));
        service.start("owned",map("base_revision",2,"client_request_id","date-request-00001","message","9月19号到2026-09-30到期", "reference_date","1900-01-01"));
        ArgumentCaptor<Map> request=ArgumentCaptor.forClass(Map.class);
        verify(agent).post(eq("/agent/v2/runs"),request.capture());
        java.time.LocalDate actual=java.time.LocalDate.parse(String.valueOf(request.getValue().get("reference_date")));
        assertFalse(actual.isBefore(before));
        assertFalse(actual.isAfter(java.time.LocalDate.now(java.time.ZoneId.of("Asia/Shanghai"))));
        assertEquals("Asia/Shanghai",request.getValue().get("timezone"));
    }
    @Test void clarifiedAnswerSurvivesCancelAndNextRun() throws Exception {
        Map<String,Object> question=map("requirement_id","R1","prompt","采用哪个指标", "options",Arrays.asList("客户等级","潜力等级"),"reason","MULTIPLE_PUBLISHED_DEFINITIONS");
        state(map("revision",2,"status","WAITING","interrupt_id","ask","run_id","previous-run",
            "run_request",map("build_id","build"),"messages",new ArrayList<>(),"events",new ArrayList<>(),"questions",Arrays.asList(question)));
        when(catalog.activeBundle(107L)).thenReturn(map("build_id","build","snapshot_id","snapshot","artifact_hash","hash"));
        when(catalog.eligibleTagIds(107L,"snapshot")).thenReturn(Arrays.asList(1L));
        service.resume("owned",map("base_revision",2,"interrupt_id","ask","answer","客户等级"));
        service.cancel("owned");
        service.start("owned",map("base_revision",2,"client_request_id","continue-request-001","message","请继续补全尚未确定的条件"));
        ArgumentCaptor<Map> request=ArgumentCaptor.forClass(Map.class);
        verify(agent).post(eq("/agent/v2/runs"),request.capture());
        assertEquals("previous-run",request.getValue().get("continuation_of"));
        Map clarification=(Map)request.getValue().get("clarification_state");
        Map record=(Map)((List)clarification.get("records")).get(0);
        assertEquals("客户等级",record.get("answer"));
        assertEquals("采用哪个指标",((Map)((List)record.get("questions")).get(0)).get("prompt"));
        verifyNoInteractions(groups,compiler);
    }
    @Test void staleAskCannotResumeNewInterrupt() throws Exception {
        state(map("revision",2,"status","WAITING","interrupt_id","new"));
        assertThrows(ServiceException.class,()->service.resume("owned",map("base_revision",2,"interrupt_id","old","answer","回答")));
        verifyNoInteractions(agent);
    }
    @Test void resumeVersionMismatchStopsWaitingInsteadOfLeavingStuck() throws Exception {
        state(map("revision",2,"status","WAITING","interrupt_id","ask","run_id","run-1",
            "run_request",map("build_id","old","snapshot_id","s"),"messages",new ArrayList<>(),
            "events",new ArrayList<>(),"questions",Arrays.asList(map("prompt","?"))));
        when(catalog.activeBundle(107L)).thenReturn(map("build_id","new","snapshot_id","s","artifact_hash","h"));
        Map<String,Object> result=service.resume("owned",map("base_revision",2,"interrupt_id","ask","answer","采用已发布口径"));
        assertEquals("CANCELLED",result.get("status"));
        assertTrue(String.valueOf(result.get("error")).contains("发布版本已更新"));
        assertEquals(0,((List<?>)result.get("questions")).size());
        verify(agent).post(eq("/agent/v2/runs/run-1/cancel"),any());
        verify(agent,never()).post(eq("/agent/v2/runs/run-1/resume"),any());
    }
    @Test void archivingWaitingConversationStopsThenArchives() throws Exception {
        state(map("revision",2,"status","WAITING","run_id","run-1","messages",new ArrayList<>(),"events",new ArrayList<>()));
        Map<String,Object> result=service.rename("owned",map("archived",true));
        assertEquals(true,result.get("archived"));
        assertEquals("CANCELLED",result.get("status"));
        verify(agent).post(eq("/agent/v2/runs/run-1/cancel"),any());
    }
    @Test void pinIsPersistedAndArchivingClearsIt() {
        Map<String,Object> pinned=service.rename("owned",map("pinned",true));
        assertEquals(true,pinned.get("pinned"));
        assertEquals("1",row.getPinned());
        Map<String,Object> archived=service.rename("owned",map("archived",true));
        assertEquals(true,archived.get("archived"));
        assertEquals(false,archived.get("pinned"));
    }
    @Test void deleteRequiresArchivedIdleConversation() throws Exception {
        assertThrows(ServiceException.class,()->service.delete("owned"));
        verify(agent,never()).delete(anyString());
        row.setArchived("1");state(map("revision",2,"status","WAITING"));
        assertThrows(ServiceException.class,()->service.delete("owned"));
        verify(agent,never()).delete(anyString());
    }
    @Test void deletesArchivedConversationAndItsAgentState() {
        row.setArchived("1");
        when(agent.delete("/agent/v2/threads/owned?owner_id=2")).thenReturn(map("deleted_runs",1));
        when(threads.deleteThread("owned",2L,0L)).thenReturn(1);
        service.delete("owned");
        verify(threads).deleteExecutions("owned",2L);
        verify(threads).deleteThread("owned",2L,0L);
    }
    @Test void agentCleanupFailureKeepsBusinessConversation() {
        row.setArchived("1");
        when(agent.delete(anyString())).thenThrow(new ServiceException("编排层暂不可用"));
        assertThrows(ServiceException.class,()->service.delete("owned"));
        verify(threads,never()).deleteExecutions(anyString(),anyLong());
        verify(threads,never()).deleteThread(anyString(),anyLong(),anyLong());
    }
    @Test void authoritativeFailureStartsBoundedRepairAndKeepsDraft() throws Exception {
        state(map("revision",2,"status","RUNNING","run_id","r","messages",new ArrayList<>(),"events",new ArrayList<>()));
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),"result",map("plan",map("valid",true,"tree",map("clause_id","a"),"snapshot_id","s1"))));
        when(compiler.compile(eq(107L),any())).thenThrow(new ServiceException("比较值数量非法"));
        when(catalog.eligibleTagIds(107L,"s1")).thenReturn(Arrays.asList(1L));
        Map<String,Object> result=service.get("owned");
        assertEquals("RUNNING",result.get("status"));assertFalse((Boolean)((Map)result.get("plan")).get("valid"));
        verify(agent).post(eq("/agent/v2/runs/r/repair"),any());
    }
    @Test void publishedVersionFailureDoesNotTriggerStaleRepair() throws Exception {
        state(map("revision",2,"status","RUNNING","run_id","r","messages",new ArrayList<>(),"events",new ArrayList<>()));
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),"result",map("plan",map("valid",true,"tree",map("clause_id","a"),"snapshot_id","s1"))));
        when(compiler.compile(eq(107L),any())).thenThrow(new TsPlanValidationException("VERSION_MISMATCH",null,"发布版本已变化，请重新核验方案"));
        Map<String,Object> result=service.get("owned");
        assertEquals("COMPLETED",result.get("status"));verify(agent,never()).post(anyString(),any());
        Map<String,Object> plan=(Map<String,Object>)result.get("plan");
        assertEquals(false,plan.get("valid"));
        assertEquals("VERSION_MISMATCH",((List<Map<String,Object>>)plan.get("diagnostics")).get(0).get("code"));
    }
    @Test void structuredDiagnosticsAreReplayedWithClauseIdAndSource() throws Exception {
        state(map("revision",2,"status","RUNNING","run_id","r","messages",new ArrayList<>(),"events",new ArrayList<>()));
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),"result",map("plan",map("valid",true,"tree",map("clause_id","a"),"snapshot_id","s1"))));
        when(compiler.compile(eq(107L),any())).thenThrow(new TsPlanValidationException("UNIT_MISMATCH","a","数值单位未经核验"));
        when(catalog.eligibleTagIds(107L,"s1")).thenReturn(Arrays.asList(1L));
        Map<String,Object> result=service.get("owned");
        assertEquals("RUNNING",result.get("status"));
        Map<String,Object> plan=(Map<String,Object>)result.get("plan");
        assertEquals(false,plan.get("valid"));
        List<Map<String,Object>> diagnostics=(List<Map<String,Object>>)plan.get("diagnostics");
        assertEquals("UNIT_MISMATCH",diagnostics.get(0).get("code"));
        assertEquals("a",diagnostics.get(0).get("clause_id"));
        assertEquals("JAVA_AUTHORITY",diagnostics.get(0).get("source"));
        ArgumentCaptor<Map<String,Object>> body=ArgumentCaptor.forClass(Map.class);
        verify(agent).post(eq("/agent/v2/runs/r/repair"),body.capture());
        assertEquals("UNIT_MISMATCH",((List<Map<String,Object>>)body.getValue().get("diagnostics")).get(0).get("code"));
        assertEquals("a",((List<Map<String,Object>>)body.getValue().get("diagnostics")).get(0).get("clause_id"));
        assertEquals(1L,result.get("authority_repairs"));
    }
    @Test void agentOutcomeAndGapsAreSurfacedForDisplay() throws Exception {
        state(map("revision",2,"status","RUNNING","run_id","r","messages",new ArrayList<>(),"events",new ArrayList<>()));
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),
            "result",map("plan",map("valid",true,"tree",map("clause_id","a"),"snapshot_id","s1"),"questions",Collections.emptyList(),
                "outcome",map("outcome","CAPABILITY_GAP","gaps",Arrays.asList(map("requirement_id","R1","reason","NO_PUBLISHED_TAG","nearest_tag_ids",Arrays.asList(1))),"stats",map("deep",2)))));
        Map<String,Object> result=service.get("owned");
        Map<String,Object> outcome=(Map<String,Object>)result.get("outcome");
        assertEquals("CAPABILITY_GAP",outcome.get("outcome"));
        assertEquals(1,((List<?>)outcome.get("gaps")).size());
        assertEquals(2,((Map<?,?>)outcome.get("stats")).get("deep"));
    }
    @Test void executionGateBlocksGapAndUnconfirmedAssumedCondition() throws Exception {
        state(map("revision",2,"status","COMPLETED","plan",map("valid",true,"hash","h","tree",map("clause_id","a","status","GAP")),"messages",new ArrayList<>()));
        assertThrows(ServiceException.class,()->service.count("owned",confirmation()));
        state(map("revision",2,"status","COMPLETED","plan",map("valid",true,"hash","h","tree",map("clause_id","a","status","ASSUMED")),"messages",new ArrayList<>()));
        assertThrows(ServiceException.class,()->service.count("owned",confirmation()));
        verifyNoInteractions(groups);

        state(map("revision",2,"status","COMPLETED","plan",map("valid",true,"hash","h","tree",map("clause_id","a","status","ASSUMED")),"confirmed_clause_ids",Arrays.asList("a"),"messages",new ArrayList<>()));
        when(compiler.compile(eq(107L),any())).thenReturn(new RulePayload());
        when(groups.runRule(isNull(),eq(107L),any())).thenReturn(new RuleRunResultVO(203,null));
        Map<String,Object> result=service.count("owned",confirmation());
        assertEquals(203L,((Map<String,Object>)result.get("count")).get("value"));
    }
}
