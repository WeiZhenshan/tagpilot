package com.ruoyi.taglibrary.service;
import java.nio.file.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;
import com.ruoyi.taglibrary.domain.TsCatalogSnapshot;
import static org.junit.jupiter.api.Assertions.*;

class TsSnapshotArtifactStoreTest {
    @TempDir Path directory;
    @Test void persistsVerifiesAndRejectsOverwriteOrTamper() throws Exception {
        TsSnapshotArtifactStore store = new TsSnapshotArtifactStore(); ReflectionTestUtils.setField(store, "directory", directory.toString());
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot(); snapshot.setSnapshotId("L107-ARTIFACT-001");
        String jsonl = "{\"kind\":\"meta\",\"library_id\":107}\n";
        store.write(snapshot, jsonl);
        Path file = store.verifiedPath(snapshot);
        assertArrayEquals(jsonl.getBytes(java.nio.charset.StandardCharsets.UTF_8), Files.readAllBytes(file));
        assertEquals(TsSnapshotCanonicalizer.sha256(jsonl), snapshot.getFileSha256());
        assertThrows(com.ruoyi.common.exception.ServiceException.class, () -> store.write(snapshot, jsonl));
        Files.write(file, "tampered".getBytes());
        assertThrows(com.ruoyi.common.exception.ServiceException.class, () -> store.verifiedPath(snapshot));
    }
    @Test void rejectsPathTraversal() {
        TsSnapshotArtifactStore store = new TsSnapshotArtifactStore(); ReflectionTestUtils.setField(store, "directory", directory.toString());
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot(); snapshot.setSnapshotId("../escape");
        assertThrows(com.ruoyi.common.exception.ServiceException.class, () -> store.write(snapshot, "x"));
    }
    @Test void allSemanticMapperXmlLoads() throws Exception {
        org.apache.ibatis.session.Configuration configuration = new org.apache.ibatis.session.Configuration();
        configuration.getTypeAliasRegistry().registerAliases("com.ruoyi.taglibrary.domain");
        org.springframework.core.io.Resource[] resources = new org.springframework.core.io.support.PathMatchingResourcePatternResolver().getResources("classpath*:mapper/taglibrary/Ts*Mapper.xml");
        assertTrue(resources.length >= 11);
        for (org.springframework.core.io.Resource resource : resources) {
            try (java.io.InputStream stream = resource.getInputStream()) {
                new org.apache.ibatis.builder.xml.XMLMapperBuilder(stream, configuration, resource.toString(), configuration.getSqlFragments()).parse();
            }
        }
    }
}
