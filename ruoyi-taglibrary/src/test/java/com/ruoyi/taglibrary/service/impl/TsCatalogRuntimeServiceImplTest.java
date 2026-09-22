package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.TsCatalogSnapshot;
import com.ruoyi.taglibrary.domain.TsConcept;
import com.ruoyi.taglibrary.domain.TsIndexBuild;
import com.ruoyi.taglibrary.domain.TsTagSemantic;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TsCatalogSnapshotMapper;
import com.ruoyi.taglibrary.mapper.TsConceptMapper;
import com.ruoyi.taglibrary.mapper.TsIndexBuildMapper;
import com.ruoyi.taglibrary.mapper.TsTagSemanticMapper;

@ExtendWith(MockitoExtension.class)
class TsCatalogRuntimeServiceImplTest extends BaseServiceTest {

    @Mock private com.ruoyi.taglibrary.service.TsSnapshotAssembler assembler;
    @Mock private com.ruoyi.taglibrary.service.TsSnapshotArtifactStore artifacts;
    @Mock private com.ruoyi.taglibrary.service.TsRuntimeClient runtime;
    @Mock private com.ruoyi.taglibrary.service.TsIndexMaintenanceService maintenance;
    @Mock private TlTagLibraryMapper libraryMapper;
    @Mock private TlTagMapper tagMapper;
    @Mock private TsTagSemanticMapper tagSemanticMapper;
    @Mock private TsConceptMapper conceptMapper;
    @Mock private TsCatalogSnapshotMapper snapshotMapper;
    @Mock private TsIndexBuildMapper indexBuildMapper;
    @Mock private DpOnlineVersionResolver versionResolver;

    @InjectMocks
    private TsCatalogRuntimeServiceImpl runtimeService;

    @TempDir
    Path tempDir;

    @Test
    void publishSkipsDraftAndRequiresReviewedConcept() {
        when(libraryMapper.selectLibraryById(107L)).thenReturn(library());
        com.ruoyi.taglibrary.service.TsSnapshotAssembler.Result assembled = new com.ruoyi.taglibrary.service.TsSnapshotAssembler.Result();
        assembled.tagIds.add(709L);
        assembled.rows.add(com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("kind", "meta", "library_id", 107L));
        assembled.report.put("excluded", "NOT_REVIEWED");
        when(assembler.assemble(107L, "试点 31/969 ≈ 3.2%" )).thenReturn(assembled);
        when(snapshotMapper.selectMaxSnapshotNo(107L)).thenReturn(null);
        when(snapshotMapper.insertSnapshot(any(TsCatalogSnapshot.class))).thenReturn(1);

        TsCatalogSnapshot snapshot = runtimeService.publish(107L, "试点 31/969 ≈ 3.2%");
        assertEquals("PUBLISHED", snapshot.getStatus());
        assertEquals(Integer.valueOf(1), snapshot.getTagCount());
        assertTrue(snapshot.getQualityReport().contains("NOT_REVIEWED"));
    }

    @Test
    void eligibleTagsRejectsEmpty() {
        when(libraryMapper.selectLibraryById(107L)).thenReturn(library());
        DpResolvedVersion version = new DpResolvedVersion();
        version.setVersionId(12L);
        when(versionResolver.resolve(6L)).thenReturn(version);
        when(versionResolver.listEnabledFields(12L)).thenReturn(Collections.emptyList());
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(onlineTag()));
        ServiceException ex = assertThrows(ServiceException.class, () -> runtimeService.eligibleTagIds(107L, null));
        assertEquals("无法取得资格，拒绝服务", ex.getMessage());
    }

    @Test
    void localDemoFreezeUsesHashPinnedJavaExportWithoutSourceDatasource() throws Exception {
        String jsonl = "{\"kind\":\"meta\",\"library_id\":107,\"source_manifest\":{\"dataset_id\":6},\"counts\":{\"tag\":1,\"code_value\":0}}\n"
                + "{\"kind\":\"tag\",\"tag_id\":526,\"field_name\":\"GENDER\"}\n";
        Path freeze = tempDir.resolve("current-freeze.jsonl");
        Files.write(freeze, jsonl.getBytes(StandardCharsets.UTF_8));
        ReflectionTestUtils.setField(runtimeService, "localDemoCurrentFreeze", freeze.toString());
        ReflectionTestUtils.setField(runtimeService, "localDemoCurrentFreezeSha256",
                com.ruoyi.taglibrary.service.TsSnapshotCanonicalizer.sha256(jsonl));
        when(libraryMapper.selectLibraryById(107L)).thenReturn(library());
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(onlineTag()));

        assertEquals(Collections.singletonList(526L), runtimeService.eligibleTagIds(107L, null));
        verifyNoInteractions(versionResolver);
    }

    @Test
    void activateRequiresReady() {
        TsIndexBuild build = new TsIndexBuild();
        build.setBuildId("b1");
        build.setStatus("BUILDING");
        when(indexBuildMapper.selectById("b1")).thenReturn(build);
        ServiceException ex = assertThrows(ServiceException.class, () -> runtimeService.activate("b1"));
        assertEquals("仅 READY 构建可以激活", ex.getMessage());
    }

    @Test
    void activateSwitchesActive() {
        TsIndexBuild build = new TsIndexBuild();
        build.setBuildId("b1");
        build.setSnapshotId("L107-1");
        build.setStatus("READY");
        when(indexBuildMapper.selectById("b1")).thenReturn(build);
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot();
        snapshot.setSnapshotId("L107-1");
        snapshot.setLibraryId(107L);
        when(snapshotMapper.selectById("L107-1")).thenReturn(snapshot);
        build.setDocIdHash("hash"); build.setStoreType("LOCAL");
        when(runtime.get("/stats?build_id=b1")).thenReturn(com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("id_reconciled", true, "doc_id_hash", "hash"));
        TsIndexBuild activated = runtimeService.activate("b1");
        assertEquals("ACTIVE", activated.getStatus());
        verify(snapshotMapper).retireActive(107L, "L107-1");
        verify(indexBuildMapper).retireActiveByLibraryId(107L);
        ArgumentCaptor<TsIndexBuild> captor = ArgumentCaptor.forClass(TsIndexBuild.class);
        verify(indexBuildMapper).updateBuild(captor.capture());
        assertEquals("ACTIVE", captor.getValue().getStatus());
    }

    @Test
    void firstActivationTimeoutRegistersCompensationBeforeRpc() {
        TsIndexBuild build = new TsIndexBuild();
        build.setBuildId("b1"); build.setSnapshotId("s1"); build.setStatus("READY");
        build.setStoreType("MILVUS"); build.setDocIdHash("hash");
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot(); snapshot.setSnapshotId("s1"); snapshot.setLibraryId(107L);
        when(indexBuildMapper.selectById("b1")).thenReturn(build);
        when(snapshotMapper.selectById("s1")).thenReturn(snapshot);
        when(runtime.get("/stats?build_id=b1")).thenReturn(com.ruoyi.taglibrary.service.TsSnapshotAssembler.map("id_reconciled", true, "doc_id_hash", "hash"));
        when(runtime.post(org.mockito.ArgumentMatchers.eq("/activate"), any())).thenThrow(new ServiceException("RPC timeout after alias changed"));
        org.springframework.transaction.support.TransactionSynchronizationManager.initSynchronization();
        try {
            assertThrows(ServiceException.class, () -> runtimeService.activate("b1"));
            for (org.springframework.transaction.support.TransactionSynchronization sync : org.springframework.transaction.support.TransactionSynchronizationManager.getSynchronizations())
                sync.afterCompletion(org.springframework.transaction.support.TransactionSynchronization.STATUS_ROLLED_BACK);
            verify(maintenance).reconcile(107L);
            org.mockito.Mockito.verify(indexBuildMapper, org.mockito.Mockito.never()).retireActiveByLibraryId(any());
        } finally { org.springframework.transaction.support.TransactionSynchronizationManager.clearSynchronization(); }
    }

    @Test
    void cannotSetActiveViaStatusApi() {
        TsIndexBuild build = new TsIndexBuild();
        build.setBuildId("b1");
        build.setStatus("READY");
        when(indexBuildMapper.selectById("b1")).thenReturn(build);
        ServiceException ex = assertThrows(ServiceException.class,
                () -> runtimeService.updateBuildStatus("b1", "ACTIVE", null));
        assertEquals("不能通过状态接口直接设置为 ACTIVE", ex.getMessage());
    }

    private TlTagLibrary library() {
        TlTagLibrary library = new TlTagLibrary();
        library.setLibraryId(107L);
        library.setDatasetId(6L);
        library.setLibraryName("个人客户经营标签库");
        return library;
    }

    private TsTagSemantic semantic(Long tagId, String review, Long conceptId) {
        TsTagSemantic row = new TsTagSemantic();
        row.setTagId(tagId);
        row.setReviewStatus(review);
        row.setConceptId(conceptId);
        row.setSemanticType("BOOL");
        row.setFamilyKey("X|FLAG|ALL|NONE|NONE|BASE");
        row.setFieldName("F" + tagId);
        row.setTagName("N" + tagId);
        return row;
    }

    private TlTag onlineTag() {
        TlTag tag = new TlTag();
        tag.setTagId(526L);
        tag.setFieldName("GENDER");
        tag.setStatus("2");
        tag.setSourceStatus("AVAILABLE");
        tag.setIsObjectKey("0");
        return tag;
    }
}
