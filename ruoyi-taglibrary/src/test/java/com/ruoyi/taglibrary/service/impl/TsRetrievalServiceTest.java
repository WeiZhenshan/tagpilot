package com.ruoyi.taglibrary.service.impl;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.context.SecurityContextHolder;
import com.ruoyi.common.core.domain.model.LoginUser;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;
import com.ruoyi.taglibrary.service.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;

@ExtendWith(MockitoExtension.class)
class TsRetrievalServiceTest extends BaseServiceTest {
    @Mock ITsCatalogRuntimeService catalog;
    @Mock TsRuntimeClient runtime;
    @Mock TsRetrievalFeedbackMapper feedback;
    @Mock TsCatalogSnapshotMapper snapshots;
    @Mock TsIndexBuildMapper builds;
    @InjectMocks TsRetrievalService service;
    private void identify() { ((LoginUser)SecurityContextHolder.getContext().getAuthentication().getPrincipal()).setUserId(2L); }
    @Test void tracePinsBuildAndDoesNotRetainRawQuery() {
        identify();
        when(catalog.activeBundle(107L)).thenReturn(map("snapshot_id", "s1", "build_id", "b1", "store_type", "LOCAL", "artifact_hash", "hash"));
        when(catalog.eligibleTagIds(107L, "s1")).thenReturn(Arrays.asList(1L));
        when(runtime.post(eq("/agent/query"), any())).thenReturn(map("snapshot_id", "s1", "build_id", "b1", "store_type", "LOCAL", "artifact_hash", "hash", "candidates", Arrays.asList(map("tag_id", 1))));
        service.retrieve(107L, "客户张三的手机13800138000");
        ArgumentCaptor<TsRetrievalFeedback> captor = ArgumentCaptor.forClass(TsRetrievalFeedback.class);
        verify(feedback).insert(captor.capture());
        assertEquals(2L, captor.getValue().getUserId());
        assertTrue(captor.getValue().getQueryText().startsWith("sha256:"));
        assertFalse(captor.getValue().getRankFeatures().contains("13800138000"));
    }
    @Test void rejectsOutOfEligibilityRuntimeResponse() {
        when(catalog.activeBundle(107L)).thenReturn(map("snapshot_id", "s1", "build_id", "b1", "store_type", "LOCAL"));
        when(catalog.eligibleTagIds(107L, "s1")).thenReturn(Arrays.asList(1L));
        when(runtime.post(eq("/agent/query"), any())).thenReturn(map("snapshot_id", "s1", "build_id", "b1", "store_type", "LOCAL", "candidates", Arrays.asList(map("tag_id", 2))));
        assertThrows(ServiceException.class, () -> service.retrieve(107L, "女性"));
        verify(feedback, never()).insert(any());
    }
    @Test void ignoresForgedFeedbackIdentityAndChecksOriginalTrace() {
        identify();
        TsRetrievalFeedback request = new TsRetrievalFeedback(); request.setTraceId("trace"); request.setUserId(999L); request.setAction("ACCEPT"); request.setFinalTagId(1L);
        TsRetrievalFeedback trace = new TsRetrievalFeedback(); trace.setTraceId("trace"); trace.setBuildId("b1"); trace.setSnapshotId("s1"); trace.setRankFeatures(json(map("candidates", Arrays.asList(map("tag_id", 1)))));
        when(feedback.selectTrace("trace", 2L)).thenReturn(trace);
        TsCatalogSnapshot snapshot = new TsCatalogSnapshot(); snapshot.setLibraryId(107L); when(snapshots.selectById("s1")).thenReturn(snapshot);
        when(catalog.eligibleTagIds(107L, "s1")).thenReturn(Arrays.asList(1L));
        service.feedback(request);
        ArgumentCaptor<TsRetrievalFeedback> captor = ArgumentCaptor.forClass(TsRetrievalFeedback.class); verify(feedback).insert(captor.capture());
        assertEquals(2L, captor.getValue().getUserId()); assertEquals("b1", captor.getValue().getBuildId());
    }
}
