package com.ruoyi.taglibrary.service;
import java.nio.file.*;
import java.util.*;
import com.fasterxml.jackson.databind.*;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;

class TsExpressionCompilerTest {
    @Test void sharedContractMatchesPython() throws Exception {
        ObjectMapper json=new ObjectMapper();
        JsonNode fixture=json.readTree(Files.readAllBytes(Paths.get("../docs/design/agent-v3/expression-contract.json")));
        TlTagMapper mapper=mock(TlTagMapper.class);TsExpressionCompiler compiler=new TsExpressionCompiler();
        ReflectionTestUtils.setField(compiler,"json",json);ReflectionTestUtils.setField(compiler,"tags",mapper);
        Map<Long,JsonNode> published=new HashMap<>();
        for(JsonNode t:fixture.path("tags")) {
            long id=t.path("tag_id").asLong();published.put(id,t);
            TlTag tag=new TlTag();tag.setTagId(id);tag.setLibraryId(107L);tag.setTagType("数值型");tag.setFieldName("f"+id);tag.setTagName(t.path("name").asText());when(mapper.selectTagById(id)).thenReturn(tag);
        }
        for(JsonNode test:fixture.path("cases")) {
            String name=test.path("id").asText();
            if(test.path("valid").asBoolean())assertEquals(test.path("unit").asText(),compiler.compile(test.path("expression"),107L,published.keySet(),published,Collections.emptyMap()).unit,name);
            else assertThrows(RuntimeException.class,()->compiler.compile(test.path("expression"),107L,published.keySet(),published,Collections.emptyMap()),name);
        }
    }
    @Test void capabilityHashKeepsArithmeticArgumentOrder() throws Exception {
        ObjectMapper json=new ObjectMapper();
        Map a=json.readValue("{\"kind\":\"capability\",\"implementation\":{\"kind\":\"DIV\",\"args\":[{\"tag_id\":2},{\"tag_id\":1}]}}",Map.class);
        Map b=json.readValue("{\"kind\":\"capability\",\"implementation\":{\"kind\":\"DIV\",\"args\":[{\"tag_id\":1},{\"tag_id\":2}]}}",Map.class);
        assertNotEquals(TsSnapshotCanonicalizer.dumps(a),TsSnapshotCanonicalizer.dumps(b));
    }
}
