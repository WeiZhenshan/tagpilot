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
import com.ruoyi.objectgroup.service.ITlObjectGroupService;
import com.ruoyi.taglibrary.domain.*;
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
    @Test void staleAskCannotResumeNewInterrupt() throws Exception {
        state(map("revision",2,"status","WAITING","interrupt_id","new"));
        assertThrows(ServiceException.class,()->service.resume("owned",map("base_revision",2,"interrupt_id","old","answer","回答")));
        verifyNoInteractions(agent);
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
        when(agent.get(anyString())).thenReturn(map("status","COMPLETED","events",Collections.emptyList(),"result",map("plan",map("valid",true,"tree",map("clause_id","a")))));
        when(compiler.compile(eq(107L),any())).thenThrow(new ServiceException("发布版本已变化"));
        Map<String,Object> result=service.get("owned");
        assertEquals("COMPLETED",result.get("status"));verify(agent,never()).post(anyString(),any());
    }
}
