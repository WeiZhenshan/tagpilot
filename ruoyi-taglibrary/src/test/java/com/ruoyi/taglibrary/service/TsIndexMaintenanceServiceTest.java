package com.ruoyi.taglibrary.service;

import java.util.*;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(MockitoExtension.class)
class TsIndexMaintenanceServiceTest {
    @Mock TsCatalogSnapshotMapper snapshots;
    @Mock TsIndexBuildMapper builds;
    @Mock TsRuntimeClient runtime;
    @InjectMocks TsIndexMaintenanceService service;

    private TsIndexBuild build(String id, String store, String status) {
        TsIndexBuild b = new TsIndexBuild(); b.setBuildId(id); b.setSnapshotId("s"); b.setStoreType(store); b.setStatus(status); return b;
    }
    @Test void firstActivationRollbackRemovesOnlyKnownRoutableMilvusBuilds() {
        when(snapshots.lockLibrary(107L)).thenReturn(107L);
        when(builds.selectByLibraryId(107L)).thenReturn(Arrays.asList(build("ready", "MILVUS", "READY"),
                build("purged", "MILVUS", "PURGED"), build("loading", "MILVUS", "BUILDING"), build("local", "LOCAL", "READY")));
        assertEquals("NO_ACTIVE", service.reconcile(107L).get("status"));
        verify(runtime).post(eq("/deactivate"), argThat(p -> "ready".equals(((Map<?, ?>) p).get("build_id"))));
        verifyNoMoreInteractions(runtime);
    }
    @Test void reconciliationRestoresCurrentDatabaseAuthority() {
        when(snapshots.lockLibrary(107L)).thenReturn(107L);
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot(); snapshot.setSnapshotId("current");
        when(snapshots.selectActiveByLibraryId(107L)).thenReturn(snapshot);
        when(builds.selectActiveBySnapshotId("current")).thenReturn(build("newer", "MILVUS", "ACTIVE"));
        service.reconcile(107L);
        InOrder order = inOrder(snapshots, runtime);
        order.verify(snapshots).lockLibrary(107L);
        order.verify(snapshots).selectActiveByLibraryId(107L);
        order.verify(runtime).post(eq("/activate"), argThat(p -> "newer".equals(((Map<?, ?>) p).get("build_id")) && "current".equals(((Map<?, ?>) p).get("snapshot_id"))));
        verifyNoMoreInteractions(runtime);
    }
    @Test void localAuthorityClearsOrphanMilvusAliasBeforeActivation() {
        when(snapshots.lockLibrary(107L)).thenReturn(107L);
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot(); snapshot.setSnapshotId("s");
        when(snapshots.selectActiveByLibraryId(107L)).thenReturn(snapshot);
        when(builds.selectActiveBySnapshotId("s")).thenReturn(build("local", "LOCAL", "ACTIVE"));
        when(builds.selectByLibraryId(107L)).thenReturn(Collections.singletonList(build("orphan", "MILVUS", "READY")));
        service.reconcile(107L);
        InOrder order = inOrder(runtime);
        order.verify(runtime).post(eq("/deactivate"), any());
        order.verify(runtime).post(eq("/activate"), argThat(p -> "local".equals(((Map<?, ?>) p).get("build_id"))));
    }
}
