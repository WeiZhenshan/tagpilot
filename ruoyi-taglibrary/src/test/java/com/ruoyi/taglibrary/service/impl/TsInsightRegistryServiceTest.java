package com.ruoyi.taglibrary.service.impl;
import java.util.*;
import java.time.LocalDate;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.framework.web.service.PermissionService;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.mapper.TsInsightMapper;
import com.ruoyi.taglibrary.service.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;
@ExtendWith(MockitoExtension.class)
class TsInsightRegistryServiceTest extends BaseServiceTest {
 @Mock TsInsightMapper mapper;@Mock TsAgentClient agent;@Spy ObjectMapper json=new ObjectMapper();
 @Mock ITlTagLibraryService libraries;@Mock ITsCatalogRuntimeService catalog;@Mock PermissionService permissions;
 @InjectMocks TsInsightRegistryService service;
 String id="asset_structure_profile",hash=String.join("",Collections.nCopies(64,"a"));Map<String,Object> config,row;
 @BeforeEach void setup()throws Exception{
  lenient().when(permissions.hasAnyPermi(anyString())).thenReturn(true);lenient().when(libraries.selectLibraryById(107L)).thenReturn(new TlTagLibrary());
  lenient().when(catalog.activeBundle(107L)).thenReturn(map("snapshot_id","snap"));lenient().when(catalog.eligibleTagIds(107L,"snap")).thenReturn(Arrays.asList(1L,2L));
  Map<String,Object> manifest=map("id",id,"metrics",Arrays.asList("aum"));lenient().when(agent.get("/agent/insight/catalog")).thenReturn(map("skills",Collections.singletonList(map("manifest",manifest,"pack_hash",hash)),"metrics",Collections.singletonList(map("id","aum","unit","元"))));
  config=map("skill_id",id,"version","0.1.0","binding_version","0.1.0","data_as_of",LocalDate.now().toString(),"benchmark_definition","业务复核总体","benchmark_version","0.1.0","bindings",Collections.singletonList(map("metric","aum","tag_ids",Collections.singletonList(1L),"unit","元")));
  row=map("skill_id",id,"version","0.1.0","status","DRAFT","pack_hash",hash,"definition_json",json.writeValueAsString(config));
 }
 @Test void browserCannotForgePublicationOrSql(){config.put("passed",true);assertThrows(ServiceException.class,()->service.save(107L,config));verify(mapper,never()).insert(any(),any(),any(),any(),any(),any());config.remove("passed");((Map<String,Object>)((List<?>)config.get("bindings")).get(0)).put("sql","select *");assertThrows(ServiceException.class,()->service.save(107L,config));}
 @Test void wrongSemanticUnitCannotBeRegistered(){((Map<String,Object>)((List<?>)config.get("bindings")).get(0)).put("unit","人");assertThrows(ServiceException.class,()->service.save(107L,config));verify(mapper,never()).insert(any(),any(),any(),any(),any(),any());}
 @Test void unboundVersionCannotPassReview()throws Exception{config.put("bindings",Collections.singletonList(map("metric","org_scope","tag_ids",Collections.singletonList(1L),"unit","人")));row.put("definition_json",json.writeValueAsString(config));when(mapper.version(107L,id,"0.1.0")).thenReturn(row);assertThrows(ServiceException.class,()->service.review(107L,id,"0.1.0"));verify(agent,never()).post(eq("/agent/insight/evaluate"),any());}
 @Test void evaluationHashMismatchRejectsReview(){when(mapper.version(107L,id,"0.1.0")).thenReturn(row);when(agent.post(eq("/agent/insight/evaluate"),any())).thenReturn(map("passed",true,"pack_hash","different"));assertThrows(ServiceException.class,()->service.review(107L,id,"0.1.0"));verify(mapper,never()).review(any(),any(),any(),any(),any());}
 @Test void publishRequiresReviewAndSerializesLibrary(){when(mapper.version(107L,id,"0.1.0")).thenReturn(row);assertThrows(ServiceException.class,()->service.publish(107L,id,"0.1.0"));verify(mapper).lockLibrary(107L);verify(mapper,never()).publish(any(),any(),any(),any());}
 @Test void retiredVersionWithValidGateCanRollback()throws Exception{row.put("status","RETIRED");row.put("evaluation_json",json.writeValueAsString(map("passed",true,"pack_hash",hash)));when(mapper.version(107L,id,"0.1.0")).thenReturn(row);when(mapper.publish(107L,id,"0.1.0",USERNAME)).thenReturn(1);service.publish(107L,id,"0.1.0");InOrder order=inOrder(mapper);order.verify(mapper).lockLibrary(107L);order.verify(mapper).version(107L,id,"0.1.0");order.verify(mapper).retire(107L,id);order.verify(mapper).publish(107L,id,"0.1.0",USERNAME);}
 @Test void permissionRevocationHidesPreviouslySavedReport()throws Exception{row.put("status","PUBLISHED");when(mapper.list(107L)).thenReturn(Collections.singletonList(row));Map<String,Object> report=map("cohort",map("snapshot_id","snap","data_as_of",config.get("data_as_of"),"binding_version","0.1.0","synthetic",false),"results",Collections.singletonList(map("skill_id",id,"registry_version","0.1.0","definition_hash",TsSnapshotCanonicalizer.sha256(String.valueOf(row.get("definition_json"))),"pack_hash",hash)));assertTrue(service.reportVisible(107L,report));when(catalog.eligibleTagIds(107L,"snap")).thenReturn(Collections.emptyList());assertFalse(service.reportVisible(107L,report));}
}
