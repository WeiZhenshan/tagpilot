package com.ruoyi.taglibrary.service;

import java.util.Objects;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.TlObjectGroup;
import com.ruoyi.objectgroup.mapper.TlObjectGroupMapper;
import com.ruoyi.taglibrary.domain.TsIndexBuild;

/**
 * 同快照换索引构建时，把已保存客群的 audiencePlan 改绑到新激活的构建。
 *
 * <p>匹配口径：按 audiencePlan.snapshot_id 等于被激活构建的快照来选客群（而不是只认“上一个 ACTIVE 构建”）。
 * 同一快照的口径树、标签资格与冻结件完全相同，构建之间只差向量索引（embedding/召回），
 * 圈选方案的编译结果与 build 无关；因此同快照任一旧 build 上的方案都可安全改绑。
 * 不同快照的客群保持原样，仍走“重新核验”。</p>
 *
 * <p>只改写 audiencePlan 的 build_id / artifact_hash（snapshot_id 本就相同），口径字段原样保留，另生成新 hash/revision 和 previous_hash 审计关系；
 * 已绑定在目标构建上的客群不写库，重复激活幂等。必须运行在激活事务内，随激活一起提交或回滚。</p>
 */
@Service
public class TsAudiencePlanRebinder {

    private static final Logger log = LoggerFactory.getLogger(TsAudiencePlanRebinder.class);
    private static final ObjectMapper MAPPER = new ObjectMapper()
            .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
            .setNodeFactory(JsonNodeFactory.withExactBigDecimals(true));
    public static final String REBIND_OPERATOR = "index-activate";

    @Autowired
    private TlObjectGroupMapper groups;

    /** @return 实际改绑的客群数（幂等重复调用返回 0） */
    @Transactional(propagation = Propagation.MANDATORY)
    public int rebindSameSnapshot(Long libraryId, TsIndexBuild build) {
        if (libraryId == null || build == null || build.getSnapshotId() == null || build.getBuildId() == null) return 0;
        if (build.getArtifactHash() == null || build.getArtifactHash().isEmpty()) {
            throw new ServiceException("索引构建缺少 artifact_hash，拒绝激活");
        }
        int changed = 0;
        for (TlObjectGroup group : groups.selectPlanGroupsBySnapshotForUpdate(libraryId, build.getSnapshotId())) {
            String rewritten = rewrite(group.getRuleJson(), build);
            if (rewritten == null) continue;
            TlObjectGroup patch = new TlObjectGroup();
            patch.setGroupId(group.getGroupId());
            patch.setRuleJson(rewritten);
            patch.getParams().put("expectedRuleJson", group.getRuleJson());
            patch.setUpdateBy(REBIND_OPERATOR);
            if (groups.updateObjectGroup(patch) != 1) throw new ServiceException("客群改绑失败：" + group.getGroupId());
            changed++;
        }
        if (changed > 0) log.info("同快照客群已改绑到新索引构建 library={} snapshot={} build={} groups={}",
                libraryId, build.getSnapshotId(), build.getBuildId(), changed);
        return changed;
    }

    /** 返回改写后的规则 JSON；不属于该快照、手工规则、无法解析或已是目标构建时返回 null（不改）。 */
    static String rewrite(String ruleJson, TsIndexBuild build) {
        if (ruleJson == null || ruleJson.isEmpty()) return null;
        JsonNode root;
        try { root = MAPPER.readTree(ruleJson); }
        catch (Exception e) { return null; }
        if (root == null || !root.isObject()) return null;
        JsonNode plan = root.get("audiencePlan");
        if (plan == null || !plan.isObject() || !plan.has("tree")) return null;
        if (!Objects.equals(text(plan, "snapshot_id"), build.getSnapshotId())) return null;
        if (Objects.equals(text(plan, "build_id"), build.getBuildId())
                && Objects.equals(text(plan, "artifact_hash"), build.getArtifactHash())) return null;
        ObjectNode target = (ObjectNode) plan;
        // 保存新内容指纹与修订号；历史 execution/count 保留原 hash，通过 previous_hash 建立审计关系。
        target.put("previous_hash", text(plan, "hash"));
        target.put("previous_build_id", text(plan, "build_id"));
        target.put("revision", plan.path("revision").asLong(0) + 1);
        target.remove("hash");
        target.put("build_id", build.getBuildId());
        target.put("artifact_hash", build.getArtifactHash());
        try {
            target.put("hash", TsSnapshotCanonicalizer.sha256(MAPPER.writeValueAsString(target)));
            return MAPPER.writeValueAsString(root);
        }
        catch (Exception e) { throw new ServiceException("客群规则序列化失败"); }
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }
}
