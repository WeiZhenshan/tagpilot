package com.ruoyi.taglibrary.controller;

import java.lang.reflect.Field;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.*;
import org.springframework.security.config.annotation.method.configuration.EnableGlobalMethodSecurity;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import com.ruoyi.common.core.domain.model.LoginUser;
import com.ruoyi.common.core.domain.entity.SysUser;
import com.ruoyi.framework.web.service.PermissionService;
import com.ruoyi.framework.web.exception.GlobalExceptionHandler;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.service.*;
import com.ruoyi.taglibrary.domain.dto.BootstrapImportRequest;
import com.ruoyi.objectgroup.service.IDimensionCodeOptionService;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/** 真正经过 Spring 方法鉴权与 MVC；不伪称数据库角色/浏览器登录验收。 */
class TsSemanticPermissionTest {
    @Configuration
    @EnableGlobalMethodSecurity(prePostEnabled = true, proxyTargetClass = true)
    static class SecurityConfig {
        @Bean TsSemanticController controller() { return new TsSemanticController(); }
        @Bean(name = "ss") PermissionService permissions() { return new PermissionService(); }
    }
    private AnnotationConfigApplicationContext context;
    private MockMvc mvc;

    @BeforeEach void setup() {
        context = new AnnotationConfigApplicationContext();
        for (Field field : TsSemanticController.class.getDeclaredFields()) {
            if (field.isAnnotationPresent(Autowired.class)) {
                context.getBeanFactory().registerSingleton(field.getName(), mock(field.getType()));
            }
        }
        context.register(SecurityConfig.class);
        context.refresh();
        mvc = MockMvcBuilders.standaloneSetup(context.getBean(TsSemanticController.class))
                .setControllerAdvice(new GlobalExceptionHandler()).build();
        when(context.getBean(ITsSemanticService.class).saveTagSemantic(any())).thenReturn(1);
        when(context.getBean(ITsSemanticService.class).reviewTagSemantic(anyLong(), any())).thenReturn(1);
        TlTag tag = new TlTag(); tag.setTagId(526L); tag.setLibraryId(107L); tag.setFieldName("GENDER");
        when(context.getBean(TlTagMapper.class).selectTagById(526L)).thenReturn(tag);
        Map<String, Object> source = new LinkedHashMap<>();
        source.put("code", "01"); source.put("codeDefinition", "来源中文含义"); source.put("dimensionId", 2L);
        when(context.getBean(IDimensionCodeOptionService.class).listCodeOptions(107L, "GENDER"))
                .thenReturn(Collections.singletonList(source));
    }

    private void login(String role) {
        SysUser user = new SysUser(); user.setUserId(2L); user.setUserName("permission-test");
        LoginUser login = new LoginUser(); login.setUser(user); login.setUserId(2L);
        login.setPermissions("none".equals(role) ? Collections.emptySet() :
                Collections.singleton("all".equals(role) ? "*:*:*" : "taglibrary:semantic:" + role));
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(login, null, Collections.emptyList()));
    }

    @AfterEach void close() { SecurityContextHolder.clearContext(); context.close(); }

    @ParameterizedTest
    @ValueSource(strings = {"none", "list", "edit", "review", "bootstrap", "publish", "all"})
    void permissionsRemainSeparated(String role) throws Exception {
        login(role);
        String prefix = "/taglibrary/semantic";
        MockHttpServletRequestBuilder[] requests = {
            get(prefix + "/tag/526"),
            get(prefix + "/code-value/526/source"),
            put(prefix + "/tag").contentType("application/json").content("{\"tagId\":526}"),
            post(prefix + "/tag/526/review").contentType("application/json").content("{\"sourceRef\":\"test\"}"),
            post(prefix + "/snapshot/publish").param("libraryId", "107"),
            post(prefix + "/index-build/start").param("snapshotId", "test").param("storeType", "MILVUS"),
            post(prefix + "/index-build/test/activate")
        };
        String[] permissions = {"list", "list", "edit", "review", "publish", "bootstrap", "publish"};
        for (int i = 0; i < requests.length; i++) {
            mvc.perform(requests[i]).andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("all".equals(role) || permissions[i].equals(role) ? 200 : 403));
        }
    }

    @Test void sourceMeaningUsesAuthorityAndPreservesLeadingZero() throws Exception {
        login("list");
        mvc.perform(get("/taglibrary/semantic/code-value/526/source"))
            .andExpect(jsonPath("$.data[0].code").value("01"))
            .andExpect(jsonPath("$.data[0].codeDefinition").value("来源中文含义"));
        verify(context.getBean(IDimensionCodeOptionService.class)).listCodeOptions(107L, "GENDER");
        verifyNoInteractions(context.getBean(ITsBootstrapService.class));
    }

    @Test void expandDraftRequiresBootstrapPermission() throws Exception {
        login("list");
        mvc.perform(post("/taglibrary/semantic/bootstrap/expand").contentType("application/json").content("{\"libraryId\":107}"))
            .andExpect(jsonPath("$.code").value(403));
        verifyNoInteractions(context.getBean(TsRuntimeClient.class));
    }

    @Test void expandDraftImportsRuntimeDraft() throws Exception {
        login("bootstrap");
        com.ruoyi.taglibrary.domain.dto.BootstrapExportResult freeze = new com.ruoyi.taglibrary.domain.dto.BootstrapExportResult();
        freeze.setLibraryId(107L);
        freeze.setJsonl("{\"kind\":\"meta\"}\n");
        when(context.getBean(ITsBootstrapService.class).exportFreeze(any())).thenReturn(freeze);
        Map<String, Object> expanded = new LinkedHashMap<>();
        expanded.put("jsonl", "{\"kind\":\"concept\"}\n{\"kind\":\"tag_semantic\"}\n");
        expanded.put("unresolved", 2);
        expanded.put("coverage_note", "1/1（仅规则草稿生成，非复核发布覆盖）");
        when(context.getBean(TsRuntimeClient.class).post(eq("/bootstrap/expand"), any())).thenReturn(expanded);
        com.ruoyi.taglibrary.domain.dto.BootstrapImportResult imported = new com.ruoyi.taglibrary.domain.dto.BootstrapImportResult();
        imported.setImportedConceptCount(1);
        imported.setImportedTagCount(3);
        imported.setImportedCodeCount(4);
        when(context.getBean(ITsBootstrapService.class).importDrafts(any())).thenReturn(imported);
        mvc.perform(post("/taglibrary/semantic/bootstrap/expand").contentType("application/json").content("{\"libraryId\":107}"))
            .andExpect(jsonPath("$.code").value(200))
            .andExpect(jsonPath("$.data.importedTagCount").value(3))
            .andExpect(jsonPath("$.data.importedConceptCount").value(1))
            .andExpect(jsonPath("$.data.unresolved").value(2));
        verify(context.getBean(ITsBootstrapService.class)).importDrafts(argThat(request ->
            request != null && Long.valueOf(107L).equals(request.getLibraryId())
                && request.getJsonl().contains("tag_semantic")));
    }

    @Test void expandDraftStopsWhenFreezeHasIssues() throws Exception {
        login("bootstrap");
        com.ruoyi.taglibrary.domain.dto.BootstrapExportResult freeze = new com.ruoyi.taglibrary.domain.dto.BootstrapExportResult();
        freeze.setJsonl("{\"kind\":\"meta\"}\n");
        freeze.getIssues().add(Collections.singletonMap("code", "DIM_DISABLED"));
        when(context.getBean(ITsBootstrapService.class).exportFreeze(any())).thenReturn(freeze);
        mvc.perform(post("/taglibrary/semantic/bootstrap/expand").contentType("application/json").content("{\"libraryId\":107}"))
            .andExpect(jsonPath("$.code").value(500));
        verifyNoInteractions(context.getBean(TsRuntimeClient.class));
    }
}
