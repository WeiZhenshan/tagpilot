package com.ruoyi.taglibrary.service;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.taglibrary.domain.TsCatalogSnapshot;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class TsPublishedAnalysisCatalogTest {
    @TempDir Path directory;
    @Test void readsFrozenUnitAndCodesAndRejectsTamperedSnapshot() throws Exception {
        ObjectMapper json=new ObjectMapper();TsSnapshotArtifactStore artifacts=new TsSnapshotArtifactStore();ReflectionTestUtils.setField(artifacts,"directory",directory.toString());
        TsCatalogSnapshot snapshot=new TsCatalogSnapshot();snapshot.setSnapshotId("analysis-test");
        artifacts.write(snapshot,"{\"kind\":\"tag\",\"tag_id\":721,\"unit\":\"CNY\",\"unit_scale\":10000}\n{\"kind\":\"code_value\",\"tag_id\":721,\"code\":\"A\",\"label\":\"已登记分类\"}\n");
        ITsCatalogRuntimeService catalog=mock(ITsCatalogRuntimeService.class);when(catalog.activeSnapshot(107L)).thenReturn(snapshot);when(catalog.eligibleTagIds(107L,"analysis-test")).thenReturn(Arrays.asList(721L));
        TsPublishedAnalysisCatalog service=new TsPublishedAnalysisCatalog();ReflectionTestUtils.setField(service,"catalog",catalog);ReflectionTestUtils.setField(service,"artifacts",artifacts);ReflectionTestUtils.setField(service,"json",json);
        assertEquals(10000,service.tags(107L,Collections.singleton(721L)).get(721L).path("unit_scale").asInt());
        assertEquals("已登记分类",service.tags(107L,Collections.singleton(721L)).get(721L).path("_code_labels").path("A").asText());
        Files.write(directory.resolve("analysis-test.jsonl"),"tampered".getBytes(StandardCharsets.UTF_8));
        assertThrows(com.ruoyi.common.exception.ServiceException.class,()->service.tags(107L,Collections.singleton(721L)));
    }
}
