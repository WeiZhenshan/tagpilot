package com.ruoyi.taglibrary.service;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.springframework.test.util.ReflectionTestUtils;
import com.fasterxml.jackson.databind.*;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;
import com.ruoyi.objectgroup.domain.RulePayload;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

/** 仅以明确指定的真实 SDK 金标产物检验 Java 编译接口；不访问客户库。 */
class TsAgentSdkGoldenSmokeTest {
    @Test
    @EnabledIfSystemProperty(named="tagpilot.sdk.smoke",matches=".+")
    void generatedB02CompilesWithPublishedEvidence() throws Exception {
        ObjectMapper json=new ObjectMapper();
        JsonNode report=json.readTree(Paths.get(System.getProperty("tagpilot.sdk.smoke")).toFile());
        JsonNode result=report.path("results").get(0);assertEquals("B02",result.path("case").asText());
        Map<String,Object> plan=json.convertValue(result.path("plan"),Map.class);
        assertEquals(Boolean.TRUE,plan.get("valid"));
        Path snapshot=Paths.get(System.getProperty("tagpilot.sdk.snapshot"));
        ITsCatalogRuntimeService catalog=mock(ITsCatalogRuntimeService.class);
        TsCatalogSnapshotMapper snapshots=mock(TsCatalogSnapshotMapper.class);
        TsSnapshotArtifactStore artifacts=mock(TsSnapshotArtifactStore.class);
        TlTagMapper tags=mock(TlTagMapper.class);
        List<Long> eligible=new ArrayList<>();
        for(String line:Files.readAllLines(snapshot,StandardCharsets.UTF_8)) {
            JsonNode row=json.readTree(line);if(!"tag".equals(row.path("kind").asText()))continue;
            long id=row.path("tag_id").asLong();eligible.add(id);
            TlTag tag=new TlTag();tag.setTagId(id);tag.setLibraryId(107L);tag.setFieldName("gold_"+id);tag.setTagName(row.path("name").asText());
            String type=row.path("semantic_type").asText();tag.setTagType(type.startsWith("NUM_")?"数值型":"BOOL".equals(type)?"布尔型":"选项型");
            when(tags.selectTagById(id)).thenReturn(tag);
        }
        when(catalog.activeBundle(107L)).thenReturn(json.convertValue(report.path("build"),Map.class));
        when(catalog.eligibleTagIds(107L,String.valueOf(plan.get("snapshot_id")))).thenReturn(eligible);
        TsCatalogSnapshot row=new TsCatalogSnapshot();when(snapshots.selectById(String.valueOf(plan.get("snapshot_id")))).thenReturn(row);
        when(artifacts.verifiedPath(row)).thenReturn(snapshot);
        TsAudiencePlanCompiler compiler=new TsAudiencePlanCompiler();
        ReflectionTestUtils.setField(compiler,"json",json);ReflectionTestUtils.setField(compiler,"catalog",catalog);
        ReflectionTestUtils.setField(compiler,"snapshots",snapshots);ReflectionTestUtils.setField(compiler,"artifacts",artifacts);ReflectionTestUtils.setField(compiler,"tags",tags);
        RulePayload rule=compiler.compile(107L,plan);
        assertEquals(4,rule.getSchemaVersion());assertEquals(3,rule.getConditions().size());
        Map<Long,RulePayload.Condition> nodes=new HashMap<>();for(RulePayload.Condition c:rule.getConditions())nodes.put(c.getTagId(),c);
        assertEquals(Arrays.asList("500000"),nodes.get(1291L).getValues());assertEquals(">=",nodes.get(1291L).getOperator());
        assertEquals(Arrays.asList("0"),nodes.get(601L).getValues());
        assertEquals(new HashSet<>(Arrays.asList("C3","C4","C5")),new HashSet<>(nodes.get(1466L).getValues()));
    }
}
