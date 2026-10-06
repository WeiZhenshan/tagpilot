package com.ruoyi.taglibrary.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.Arrays;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.TlObjectGroup;
import com.ruoyi.objectgroup.mapper.TlObjectGroupMapper;
import com.ruoyi.taglibrary.domain.TsIndexBuild;

/** 同快照换构建时客群方案改绑：只改 build_id/artifact_hash，不同快照与手工规则不动，重复调用幂等。 */
@ExtendWith(MockitoExtension.class)
class TsAudiencePlanRebinderTest {

    @Mock private TlObjectGroupMapper groups;
    @InjectMocks private TsAudiencePlanRebinder rebinder;
    private final ObjectMapper json = new ObjectMapper();

    static TsIndexBuild build(String id, String snapshot, String hash) {
        TsIndexBuild b = new TsIndexBuild(); b.setBuildId(id); b.setSnapshotId(snapshot); b.setArtifactHash(hash); return b;
    }

    static TlObjectGroup group(long id, String snapshot, String build, String hash) {
        TlObjectGroup g = new TlObjectGroup(); g.setGroupId(id); g.setLibraryId(107L);
        g.setRuleJson("{\"schemaVersion\":4,\"conditions\":[{\"tagId\":7,\"ratio\":0.406600}],\"audiencePlan\":{\"schema_version\":3,"
                + "\"snapshot_id\":\"" + snapshot + "\",\"build_id\":\"" + build + "\",\"artifact_hash\":\"" + hash + "\","
                + "\"hash\":\"plan-h\",\"revision\":3,\"tree\":{\"kind\":\"SCOPE_ALL\"}}}");
        return g;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> plan(String ruleJson) throws Exception {
        return (Map<String, Object>) json.readValue(ruleJson, Map.class).get("audiencePlan");
    }

    @Test
    void sameSnapshotGroupsAreReboundToActivatedBuild() throws Exception {
        when(groups.selectPlanGroupsBySnapshotForUpdate(107L, "S6")).thenReturn(Arrays.asList(group(132, "S6", "p3g", "h-old")));
        when(groups.updateObjectGroup(any())).thenReturn(1);

        assertEquals(1, rebinder.rebindSameSnapshot(107L, build("sf1", "S6", "h-new")));

        ArgumentCaptor<TlObjectGroup> captor = ArgumentCaptor.forClass(TlObjectGroup.class);
        verify(groups).updateObjectGroup(captor.capture());
        TlObjectGroup patch = captor.getValue();
        assertEquals(Long.valueOf(132), patch.getGroupId());
        assertEquals(TsAudiencePlanRebinder.REBIND_OPERATOR, patch.getUpdateBy());
        assertNull(patch.getGroupName()); assertNull(patch.getGroupSql());
        Map<String, Object> p = plan(patch.getRuleJson());
        assertEquals("sf1", p.get("build_id"));
        assertEquals("h-new", p.get("artifact_hash"));
        assertEquals("S6", p.get("snapshot_id"));
        // 其余字段原样保留（含方案 hash、修订号、小数精度）
        assertEquals("plan-h", p.get("previous_hash"));
        org.junit.jupiter.api.Assertions.assertNotEquals("plan-h", p.get("hash"));
        assertEquals(4, p.get("revision"));
        assertEquals(true, patch.getRuleJson().contains("\"ratio\":0.406600"));
    }

    @Test
    void otherSnapshotAndManualRulesAreUntouched() {
        TlObjectGroup otherSnapshot = group(120, "S2", "r3", "h2");
        TlObjectGroup manual = new TlObjectGroup(); manual.setGroupId(90L); manual.setRuleJson("{\"schemaVersion\":3,\"conditions\":[],\"remark\":\"S6\"}");
        TlObjectGroup broken = new TlObjectGroup(); broken.setGroupId(91L); broken.setRuleJson("not-json S6");
        when(groups.selectPlanGroupsBySnapshotForUpdate(107L, "S6")).thenReturn(Arrays.asList(otherSnapshot, manual, broken));

        assertEquals(0, rebinder.rebindSameSnapshot(107L, build("sf1", "S6", "h-new")));
        verify(groups, never()).updateObjectGroup(any());
    }

    @Test
    void repeatedActivationIsIdempotent() {
        when(groups.selectPlanGroupsBySnapshotForUpdate(107L, "S6")).thenReturn(Arrays.asList(group(132, "S6", "sf1", "h-new")));
        assertEquals(0, rebinder.rebindSameSnapshot(107L, build("sf1", "S6", "h-new")));
        assertEquals(0, rebinder.rebindSameSnapshot(107L, build("sf1", "S6", "h-new")));
        verify(groups, never()).updateObjectGroup(any());
    }

    @Test
    void sameBuildWithStaleArtifactHashIsRepaired() {
        assertEquals(true, TsAudiencePlanRebinder.rewrite(group(1, "S6", "sf1", "stale").getRuleJson(), build("sf1", "S6", "h-new")).contains("h-new"));
    }

    @Test
    void missingArtifactHashRejectsActivation() {
        assertThrows(ServiceException.class, () -> rebinder.rebindSameSnapshot(107L, build("sf1", "S6", null)));
        verify(groups, never()).selectPlanGroupsBySnapshotForUpdate(any(), any());
    }

    @Test
    void lostUpdateFailsActivation() {
        when(groups.selectPlanGroupsBySnapshotForUpdate(107L, "S6")).thenReturn(Arrays.asList(group(132, "S6", "p3g", "h-old")));
        when(groups.updateObjectGroup(any())).thenReturn(0);
        assertThrows(ServiceException.class, () -> rebinder.rebindSameSnapshot(107L, build("sf1", "S6", "h-new")));
    }
}
