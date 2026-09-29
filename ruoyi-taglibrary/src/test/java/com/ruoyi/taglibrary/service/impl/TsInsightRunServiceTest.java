package com.ruoyi.taglibrary.service.impl;
import java.util.*;
import java.time.LocalDate;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.taglibrary.mapper.TsInsightMapper;
import com.ruoyi.taglibrary.service.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

/** 验证跨阶段授权失效会丢弃整份结果，而非保留旧事实或重复追加BLOCKED。 */
@ExtendWith(MockitoExtension.class)
class TsInsightRunServiceTest extends BaseServiceTest {
 @Mock TsAgentWorkbenchService workbench; @Mock TsInsightRegistryService registry;
 @Mock TsInsightQueryService queries; @Mock ITsCatalogRuntimeService catalog;
 @Mock TsAgentClient agent; @Mock TsInsightMapper mapper;
 @Mock TsInsightPersistenceService persistence; @Spy ObjectMapper json=new ObjectMapper();
 @InjectMocks TsInsightRunService service;
 String g1="asset_structure_profile",g2="product_holding_gap";
 Map<String,Object> request,row,ctx;
 @BeforeEach void setup()throws Exception{
  request=map("base_revision",1,"plan_hash","hash","skill_ids",Collections.singletonList(g1));
  ctx=map("library_id",107L,"revision",1L,"name","测试客群","rule",new RulePayload(),"plan",map("hash","hash","snapshot_id","snapshot"),"count",map("value",240));
  when(workbench.insightContext("thread",request)).thenReturn(ctx);
  row=map("version","0.1.0","pack_hash",String.join("",Collections.nCopies(64,"a")),"definition_json",json.writeValueAsString(map("data_as_of",LocalDate.now().toString(),"binding_version","0.1.0","bindings",Collections.emptyList())));
  lenient().when(registry.published(107L,g1)).thenReturn(row);
  lenient().when(registry.reportVisible(eq(107L),anyMap())).thenReturn(true);
  lenient().when(catalog.eligibleTagIds(107L,"snapshot")).thenReturn(Collections.emptyList());
  lenient().when(agent.post(eq("/agent/insight/plan"),anyMap())).thenAnswer(inv->map("status","BLOCKED","skill_id",((Map<?,?>)inv.getArgument(1)).get("skill_id")));
  lenient().when(agent.get(startsWith("/agent/v2/runs/"))).thenAnswer(inv->map("status","COMPLETED","result",map("results",Collections.singletonList(map("skill_id",g1,"status","COMPLETE","facts",Collections.emptyList(),"cards",Collections.emptyList(),"charts",Collections.emptyList())))));
 }
 @Test void retiredDuringWorkerCannotLeakCompletedResult(){
  when(registry.published(107L,g1)).thenReturn(row).thenThrow(new ServiceException("技能尚未发布"));
  ServiceException error=assertThrows(ServiceException.class,()->service.run("thread",request));assertEquals(409,error.getCode());
  verify(persistence,never()).success(any(),anyMap(),anyMap(),any(),any(),any(),anyLong());
  verify(persistence).failure(anyString(),eq(107L),eq("thread"),eq(1L),eq("hash"),anyLong());
 }
 @Test void revisionChangesBeforeFinalSaveDiscardsReport(){
  when(workbench.insightContext("thread",request)).thenReturn(ctx).thenThrow(new ServiceException("方案已变化",409));
  assertThrows(ServiceException.class,()->service.run("thread",request));
  verify(persistence,never()).success(any(),anyMap(),anyMap(),any(),any(),any(),anyLong());
 }
 @Test void earlierSkillRevokedWhileLaterStageRunsDiscardsWholePack(){
  when(registry.reportVisible(eq(107L),anyMap())).thenReturn(false);
  ServiceException error=assertThrows(ServiceException.class,()->service.run("thread",request));assertEquals(409,error.getCode());
  verify(persistence,never()).success(any(),anyMap(),anyMap(),any(),any(),any(),anyLong());
 }
 @Test void ordinaryUnavailableSkillKeepsOneBlockedResultAndOtherResult(){
  request.put("skill_ids",Arrays.asList(g1,g2));when(registry.published(107L,g2)).thenThrow(new ServiceException("尚未发布"));
  when(agent.get("/agent/insight/catalog")).thenReturn(map("skills",Collections.singletonList(map("manifest",map("id",g2,"version","0.1.0"),"pack_hash",row.get("pack_hash")))));
  Map<String,Object> report=service.run("thread",request);List<?> results=(List<?>)report.get("results");
  assertEquals(2,results.size());assertEquals("L2",report.get("level"));assertEquals(g1,((Map<?,?>)results.get(0)).get("skill_id"));assertEquals(g2,((Map<?,?>)results.get(1)).get("skill_id"));assertEquals("BLOCKED",((Map<?,?>)results.get(1)).get("status"));
  verify(persistence).success(eq("thread"),eq(request),eq(report),eq(107L),eq(1L),eq("hash"),anyLong());
 }
}
