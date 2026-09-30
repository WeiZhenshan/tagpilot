package com.ruoyi.taglibrary.service.impl;

import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.mapper.TsAgentSkillMapper;
import com.ruoyi.taglibrary.service.TsAgentSkillService;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

@ExtendWith(MockitoExtension.class)
class TsAgentSkillServiceTest extends BaseServiceTest {
    @Mock TsAgentSkillMapper mapper;
    @Spy ObjectMapper json=new ObjectMapper();
    @InjectMocks TsAgentSkillService service;
    Map<String,Object> draft() {return map("name","test-analysis","display_name","合成测试技能","description","自动化测试用途","instructions","仅使用当前客群事实。","category","fact","version","1.0.0","row_version",0,"allowed_tools",Arrays.asList("Read","Skill"),"resources",new ArrayList<>());}
    @Test void standardMarkdownAndOptionalDraftFields() {
        Map<String,Object> definition=service.validate(draft(),true);
        assertTrue(String.valueOf(definition.get("skill_md")).contains("user-invocable: true"));
        assertFalse(String.valueOf(definition.get("skill_md")).contains("display_name"));
        Map<String,Object> d=draft();d.put("description","");assertThrows(ServiceException.class,()->service.validate(d,true));assertDoesNotThrow(()->service.validate(d,false));
    }
    @Test void unsafeResourcesAndPreprocessorsAreRejected() {
        for(String path:Arrays.asList("references/../../secret","scripts/a/../x","assets//x","assets/x/")) {
            Map<String,Object> d=draft();d.put("resources",Arrays.asList(map("path",path,"content","测试")));assertThrows(ServiceException.class,()->service.validate(d,true));
        }
        for(String field:Arrays.asList("instructions","description","argument_hint")) {
            Map<String,Object> d=draft();d.put(field,"!`cat secret`");assertThrows(ServiceException.class,()->service.validate(d,true));
        }
        Map<String,Object> invalid=draft();invalid.put("allowed_tools",Arrays.asList("Bash"));assertThrows(ServiceException.class,()->service.validate(invalid,true));
    }
    @Test void publishedSnapshotSurvivesDraftChangesAndRuntimeOmitsResources() throws Exception {
        Map<String,Object> d=draft(),published=service.validate(d,true);d.put("instructions","待发布修改");
        String draftJson=json.writeValueAsString(d),publishedJson=json.writeValueAsString(published);
        when(mapper.list()).thenReturn(Arrays.asList(map("draft_json",draftJson,"published_json",publishedJson,"row_version",3)));
        assertEquals("仅使用当前客群事实。",service.published().get(0).get("instructions"));
        assertFalse(service.list(true).get(0).containsKey("instructions"));assertFalse(service.list(true).get(0).containsKey("resources"));
    }
    @Test void optimisticSaveCannotOverwriteConcurrentDraft() throws Exception {
        Map<String,Object> d=draft();d.put("row_version",2);
        when(mapper.lock("test-analysis")).thenReturn(map("row_version",3));
        assertThrows(ServiceException.class,()->service.save(d));
        verify(mapper).save(eq("test-analysis"),anyString(),eq(2L),anyString());verify(mapper,never()).insert(anyString(),anyString(),anyString());
    }
    @Test void reservedCommandsAndXmlDescriptionAreRejected() {
        for(String name:Arrays.asList("clear","init","synced","anthropic-skills","claude-helper")) {
            Map<String,Object> d=draft();d.put("name",name);assertThrows(ServiceException.class,()->service.validate(d,true));
        }
        Map<String,Object> d=draft();d.put("description","<xml>用途</xml>");assertThrows(ServiceException.class,()->service.validate(d,true));
    }
    @Test void publishingSameVersionIsRejected() throws Exception {
        Map<String,Object> d=draft();String encoded=json.writeValueAsString(d);
        when(mapper.lock("test-analysis")).thenReturn(map("draft_json",encoded,"published_json",encoded,"row_version",2));
        assertThrows(ServiceException.class,()->service.publish("test-analysis",map("row_version",2)));
        verify(mapper,never()).publish(anyString(),anyString(),anyLong(),anyString());
    }
}
