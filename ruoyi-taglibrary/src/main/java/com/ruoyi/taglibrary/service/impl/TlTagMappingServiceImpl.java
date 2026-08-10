package com.ruoyi.taglibrary.service.impl;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.taglibrary.domain.TlAuditLog;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagMetadataChange;
import com.ruoyi.taglibrary.domain.dto.MetadataChangeDTO;
import com.ruoyi.taglibrary.domain.vo.TagMappingVO;
import com.ruoyi.taglibrary.mapper.TlAuditLogMapper;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TlTagMetadataChangeMapper;
import com.ruoyi.taglibrary.service.ITlTagMappingService;

/**
 * 标签元数据变更（批量映射）Service业务层处理
 * 规则：同一标签同时只允许一条 DRAFT/PENDING 记录；草稿仅创建人可改；
 * 保存/提交/审核均对 tl_tag 加行锁并校验 base_version；审核通过后 tl_tag.version+1（status 不变）
 *
 * @author ruoyi
 */
@Service
public class TlTagMappingServiceImpl implements ITlTagMappingService {

    /** 变更状态 */
    private static final String STATUS_DRAFT = "DRAFT";
    private static final String STATUS_PENDING = "PENDING";
    private static final String STATUS_APPROVED = "APPROVED";
    private static final String STATUS_REJECTED = "REJECTED";

    /** 允许变更的五个元数据字段（快照 JSON 只取这几个 key，固定顺序） */
    private static final List<String> META_FIELDS = Arrays.asList(
            "tagName", "tagType", "dirId", "techCaliber", "businessCaliber");

    /** 字段中文名（changedFields 摘要用） */
    private static final Map<String, String> FIELD_LABELS = new LinkedHashMap<>();
    static {
        FIELD_LABELS.put("tagName", "标签名称");
        FIELD_LABELS.put("tagType", "标签类型");
        FIELD_LABELS.put("dirId", "标签目录");
        FIELD_LABELS.put("techCaliber", "技术口径");
        FIELD_LABELS.put("businessCaliber", "业务口径");
    }

    /** 标签类型字典固定值（dict_value 即中文） */
    private static final Set<String> TAG_TYPES = new HashSet<>(Arrays.asList(
            "选项型", "布尔型", "数值型", "文本型", "日期型"));

    @Autowired
    private TlTagMapper tagMapper;
    @Autowired
    private TlTagDirMapper dirMapper;
    @Autowired
    private TlTagMetadataChangeMapper changeMapper;
    @Autowired
    private TlAuditLogMapper auditLogMapper;

    @Override
    public List<TagMappingVO> selectMappingList(TlTag query) {
        String username = SecurityUtils.getUsername();
        // 过滤口径与 /taglibrary/tag/list 一致（del_flag='0' + 入参条件）
        List<TlTag> tags = tagMapper.selectTagList(query);
        List<TagMappingVO> rows = new ArrayList<>();
        if (tags.isEmpty()) {
            return rows;
        }
        List<Long> tagIds = tags.stream().map(TlTag::getTagId).collect(Collectors.toList());
        // 本页标签的 DRAFT/PENDING 变更（含他人，用于前端禁用行）
        Map<Long, TlTagMetadataChange> changeMap = new HashMap<>();
        for (TlTagMetadataChange change : changeMapper.selectByTagIdsAndStatusIn(tagIds,
                Arrays.asList(STATUS_DRAFT, STATUS_PENDING))) {
            changeMap.put(change.getTagId(), change);
        }
        // 当前用户的草稿（ownDraft 标记）
        Set<Long> ownDraftTagIds = new HashSet<>();
        for (TlTagMetadataChange draft : changeMapper.selectDraftByTagIdsAndCreator(tagIds, username)) {
            ownDraftTagIds.add(draft.getTagId());
        }
        for (TlTag tag : tags) {
            TagMappingVO vo = new TagMappingVO();
            BeanUtils.copyProperties(tag, vo);
            TlTagMetadataChange change = changeMap.get(tag.getTagId());
            if (change != null) {
                vo.setChangeId(change.getChangeId());
                vo.setChangeStatus(change.getStatus());
                vo.setApplyBy(change.getApplyBy());
                vo.setAfterJson(change.getAfterJson());
            }
            vo.setOwnDraft(ownDraftTagIds.contains(tag.getTagId()));
            rows.add(vo);
        }
        return rows;
    }

    @Override
    @Transactional
    public int saveDraft(List<MetadataChangeDTO> items) {
        if (items == null || items.isEmpty()) {
            throw new ServiceException("没有需要保存的映射数据");
        }
        String username = SecurityUtils.getUsername();
        int saved = 0;
        for (MetadataChangeDTO item : items) {
            // 1. 行锁锁定标签并校验入参（先锁标签，保证同标签的草稿创建互斥）
            TlTag tag = tagMapper.selectTagByIdForUpdate(item.getTagId());
            if (tag == null) {
                throw new ServiceException("标签不存在或已删除");
            }
            validateItem(tag, item);

            // 2. 同一标签同时只允许一条 DRAFT/PENDING 记录
            TlTagMetadataChange ownDraft = null;
            for (TlTagMetadataChange existing : changeMapper.selectByTagIdAndStatusIn(tag.getTagId(),
                    Arrays.asList(STATUS_DRAFT, STATUS_PENDING))) {
                if (STATUS_PENDING.equals(existing.getStatus())) {
                    throw new ServiceException("标签「" + tag.getTagName() + "」正在审核中，不能保存草稿");
                }
                if (!username.equals(existing.getApplyBy())) {
                    throw new ServiceException("标签「" + tag.getTagName() + "」存在他人草稿，不能保存");
                }
                ownDraft = existing;
            }

            // 3. 组装 before/after 快照（仅五个可改字段，前端多传的一律忽略）
            Map<String, Object> before = snapshotOf(tag);
            Map<String, Object> after = snapshotOf(item);
            if (snapshotEquals(before, after)) {
                // 与当前值一致：已有本人草稿则删除，否则不创建
                if (ownDraft != null) {
                    changeMapper.deleteById(ownDraft.getChangeId());
                }
                continue;
            }

            // 4. 有本人草稿则刷新，否则新建
            int baseVersion = tag.getVersion() == null ? 0 : tag.getVersion();
            if (ownDraft != null) {
                ownDraft.setBaseVersion(baseVersion);
                ownDraft.setBeforeJson(JSON.toJSONString(before));
                ownDraft.setAfterJson(JSON.toJSONString(after));
                ownDraft.setUpdateBy(username);
                changeMapper.updateChange(ownDraft);
            } else {
                TlTagMetadataChange change = new TlTagMetadataChange();
                change.setLibraryId(tag.getLibraryId());
                change.setTagId(tag.getTagId());
                change.setBaseVersion(baseVersion);
                change.setBeforeJson(JSON.toJSONString(before));
                change.setAfterJson(JSON.toJSONString(after));
                change.setStatus(STATUS_DRAFT);
                change.setApplyBy(username);
                change.setCreateBy(username);
                changeMapper.insertChange(change);
            }
            saved++;
        }
        return saved;
    }

    @Override
    @Transactional
    public int submit(Long[] changeIds) {
        if (changeIds == null || changeIds.length == 0) {
            return 0;
        }
        String username = SecurityUtils.getUsername();
        Date now = new Date();
        List<TlTagMetadataChange> changes = lockChanges(changeIds);
        for (TlTagMetadataChange change : changes) {
            if (!STATUS_DRAFT.equals(change.getStatus())) {
                throw new ServiceException("变更记录「" + change.getChangeId() + "」不是草稿状态，不能提交");
            }
            if (!username.equals(change.getApplyBy())) {
                throw new ServiceException("只能提交本人创建的草稿");
            }
            // 行锁锁定标签并校验基线版本未被其他链路改动
            TlTag tag = lockTag(change.getTagId());
            checkBaseVersion(change, tag);
            change.setStatus(STATUS_PENDING);
            change.setSubmitTime(now);
            change.setUpdateBy(username);
            changeMapper.updateChange(change);
            writeAuditLog(change, "提交", STATUS_DRAFT, STATUS_PENDING, change.getAfterJson(), null);
        }
        return changes.size();
    }

    @Override
    public List<TlTagMetadataChange> selectAuditList(TlTagMetadataChange query) {
        List<TlTagMetadataChange> list = changeMapper.selectAuditList(query);
        for (TlTagMetadataChange change : list) {
            change.setChangedFields(buildChangedFields(change.getBeforeJson(), change.getAfterJson()));
        }
        return list;
    }

    @Override
    @Transactional
    public int audit(Long[] changeIds, boolean pass, String auditComment) {
        if (changeIds == null || changeIds.length == 0) {
            return 0;
        }
        String username = SecurityUtils.getUsername();
        Date now = new Date();
        // 1. 锁定变更记录，要求全部待审核，否则整批不处理
        List<TlTagMetadataChange> changes = lockChanges(changeIds);
        for (TlTagMetadataChange change : changes) {
            if (!STATUS_PENDING.equals(change.getStatus())) {
                throw new ServiceException("存在非待审核记录，整批不处理");
            }
        }
        // 2. 按 tag_id 排序锁定标签（降低死锁风险），校验基线版本
        changes.sort(Comparator.comparing(TlTagMetadataChange::getTagId));
        Map<Long, TlTag> tagMap = new HashMap<>();
        for (TlTagMetadataChange change : changes) {
            TlTag tag = lockTag(change.getTagId());
            int curVersion = tag.getVersion() == null ? 0 : tag.getVersion();
            int baseVersion = change.getBaseVersion() == null ? 0 : change.getBaseVersion();
            if (curVersion != baseVersion) {
                throw new ServiceException("标签「" + tag.getTagName() + "」已被他人修改，整批不处理");
            }
            tagMap.put(change.getTagId(), tag);
        }
        // 3. 逐条处理：通过则回写 tl_tag 五字段并 version+1，驳回仅改变更记录状态
        for (TlTagMetadataChange change : changes) {
            TlTag tag = tagMap.get(change.getTagId());
            if (pass) {
                JSONObject after = JSON.parseObject(change.getAfterJson());
                TlTag update = new TlTag();
                update.setTagId(tag.getTagId());
                update.setTagName(after.getString("tagName"));
                update.setTagType(after.getString("tagType"));
                update.setDirId(after.getLong("dirId"));
                update.setTechCaliber(after.getString("techCaliber"));
                update.setBusinessCaliber(after.getString("businessCaliber"));
                int curVersion = tag.getVersion() == null ? 0 : tag.getVersion();
                update.setVersion(curVersion + 1);
                update.setUpdateBy(username);
                tagMapper.updateMetadataById(update);
            }
            change.setStatus(pass ? STATUS_APPROVED : STATUS_REJECTED);
            change.setAuditBy(username);
            change.setAuditTime(now);
            change.setAuditComment(auditComment);
            change.setUpdateBy(username);
            changeMapper.updateChange(change);
            // 审计快照 {before, after}
            JSONObject detail = new JSONObject();
            detail.put("before", JSON.parse(change.getBeforeJson()));
            detail.put("after", JSON.parse(change.getAfterJson()));
            writeAuditLog(change, pass ? "通过" : "驳回", STATUS_PENDING,
                    pass ? STATUS_APPROVED : STATUS_REJECTED, detail.toJSONString(), auditComment);
        }
        return changes.size();
    }

    @Override
    public Map<String, Object> getChangeDetail(Long changeId) {
        TlTagMetadataChange change = changeMapper.selectById(changeId);
        if (change == null) {
            throw new ServiceException("变更记录不存在");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("change", change);
        result.put("before", StringUtils.isNotEmpty(change.getBeforeJson()) ? JSON.parse(change.getBeforeJson()) : null);
        result.put("after", StringUtils.isNotEmpty(change.getAfterJson()) ? JSON.parse(change.getAfterJson()) : null);
        // 标签当前五字段值（供"当前值 → 申请值"对比展示）
        TlTag tag = tagMapper.selectTagById(change.getTagId());
        result.put("current", tag == null ? null : snapshotOf(tag));
        return result;
    }

    // ---- private helpers ----

    /** 校验草稿行：tagName 非空、tagType 合法、目录属于该标签库、口径长度限制 */
    private void validateItem(TlTag tag, MetadataChangeDTO item) {
        if (StringUtils.isEmpty(item.getTagName()) || StringUtils.isEmpty(item.getTagName().trim())) {
            throw new ServiceException("标签「" + tag.getTagName() + "」的标签名称不能为空");
        }
        item.setTagName(item.getTagName().trim());
        if (!TAG_TYPES.contains(item.getTagType())) {
            throw new ServiceException("标签「" + item.getTagName() + "」的标签类型不合法");
        }
        if (item.getDirId() == null) {
            throw new ServiceException("标签「" + item.getTagName() + "」的标签目录不能为空");
        }
        TlTagDir dir = dirMapper.selectDirById(item.getDirId());
        if (dir == null || !dir.getLibraryId().equals(tag.getLibraryId())) {
            throw new ServiceException("标签「" + item.getTagName() + "」的目标目录不存在或不属于该标签库");
        }
        if (StringUtils.isNotEmpty(item.getTechCaliber()) && item.getTechCaliber().length() > 500) {
            throw new ServiceException("标签「" + item.getTagName() + "」的技术口径最长500字");
        }
        if (StringUtils.isNotEmpty(item.getBusinessCaliber()) && item.getBusinessCaliber().length() > 500) {
            throw new ServiceException("标签「" + item.getTagName() + "」的业务口径最长500字");
        }
    }

    /** 按 change_id 排序行锁批量查询变更记录，记录缺失直接报错 */
    private List<TlTagMetadataChange> lockChanges(Long[] changeIds) {
        List<Long> ids = Arrays.stream(changeIds).distinct().sorted().collect(Collectors.toList());
        List<TlTagMetadataChange> changes = changeMapper.selectByIdsForUpdate(ids);
        Map<Long, TlTagMetadataChange> map = new HashMap<>();
        for (TlTagMetadataChange change : changes) {
            map.put(change.getChangeId(), change);
        }
        List<TlTagMetadataChange> result = new ArrayList<>();
        for (Long id : ids) {
            TlTagMetadataChange change = map.get(id);
            if (change == null) {
                throw new ServiceException("变更记录不存在：" + id);
            }
            result.add(change);
        }
        return result;
    }

    /** 行锁锁定标签 */
    private TlTag lockTag(Long tagId) {
        TlTag tag = tagMapper.selectTagByIdForUpdate(tagId);
        if (tag == null) {
            throw new ServiceException("标签不存在或已删除");
        }
        return tag;
    }

    /** 校验草稿基线版本与标签当前版本一致，不静默覆盖 */
    private void checkBaseVersion(TlTagMetadataChange change, TlTag tag) {
        int curVersion = tag.getVersion() == null ? 0 : tag.getVersion();
        int baseVersion = change.getBaseVersion() == null ? 0 : change.getBaseVersion();
        if (curVersion != baseVersion) {
            throw new ServiceException("标签已被他人修改，请重新加载后再试");
        }
    }

    /** 从标签实体取五个可改字段快照（空串归一为 null） */
    private Map<String, Object> snapshotOf(TlTag tag) {
        Map<String, Object> snap = new LinkedHashMap<>();
        snap.put("tagName", tag.getTagName());
        snap.put("tagType", tag.getTagType());
        snap.put("dirId", tag.getDirId());
        snap.put("techCaliber", emptyToNull(tag.getTechCaliber()));
        snap.put("businessCaliber", emptyToNull(tag.getBusinessCaliber()));
        return snap;
    }

    /** 从草稿行 DTO 取五个可改字段快照（仅这五个 key，其余入参忽略） */
    private Map<String, Object> snapshotOf(MetadataChangeDTO item) {
        Map<String, Object> snap = new LinkedHashMap<>();
        snap.put("tagName", item.getTagName());
        snap.put("tagType", item.getTagType());
        snap.put("dirId", item.getDirId());
        snap.put("techCaliber", emptyToNull(item.getTechCaliber()));
        snap.put("businessCaliber", emptyToNull(item.getBusinessCaliber()));
        return snap;
    }

    private String emptyToNull(String value) {
        return StringUtils.isEmpty(value) ? null : value;
    }

    /** 两个快照五字段全等（null 安全） */
    private boolean snapshotEquals(Map<String, Object> before, Map<String, Object> after) {
        for (String field : META_FIELDS) {
            if (!valueEquals(before.get(field), after.get(field))) {
                return false;
            }
        }
        return true;
    }

    private boolean valueEquals(Object a, Object b) {
        if (a == null && b == null) {
            return true;
        }
        if (a == null || b == null) {
            return false;
        }
        return String.valueOf(a).equals(String.valueOf(b));
    }

    /** 计算 before/after 差异字段中文名摘要，如"标签名称、标签类型" */
    private String buildChangedFields(String beforeJson, String afterJson) {
        if (StringUtils.isEmpty(beforeJson) || StringUtils.isEmpty(afterJson)) {
            return "";
        }
        JSONObject before = JSON.parseObject(beforeJson);
        JSONObject after = JSON.parseObject(afterJson);
        List<String> labels = new ArrayList<>();
        for (String field : META_FIELDS) {
            if (!valueEquals(before.get(field), after.get(field))) {
                labels.add(FIELD_LABELS.get(field));
            }
        }
        return String.join("、", labels);
    }

    /** 写审批留痕（biz_type='tagMeta'，request_id=变更ID，detail_json=快照）；审核动作记录审核人/时间/意见 */
    private void writeAuditLog(TlTagMetadataChange change, String action, String fromStatus, String toStatus,
                               String detailJson, String auditComment) {
        String username = SecurityUtils.getUsername();
        TlAuditLog log = new TlAuditLog();
        log.setBizType("tagMeta");
        log.setBizId(change.getTagId());
        log.setAction(action);
        log.setFromStatus(fromStatus);
        log.setToStatus(toStatus);
        log.setRequestId(String.valueOf(change.getChangeId()));
        log.setDetailJson(detailJson);
        log.setApplyBy(change.getApplyBy());
        if ("通过".equals(action) || "驳回".equals(action)) {
            log.setAuditBy(username);
            log.setAuditTime(new Date());
            log.setAuditComment(auditComment);
        }
        log.setCreateBy(username);
        auditLogMapper.insertAuditLog(log);
    }
}
