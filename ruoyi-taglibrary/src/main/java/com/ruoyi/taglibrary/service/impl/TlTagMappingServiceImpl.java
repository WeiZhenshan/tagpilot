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
import java.util.Collections;
import java.util.stream.Collectors;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.github.pagehelper.Page;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.databroker.util.DpSourceFingerprint;
import com.ruoyi.taglibrary.domain.TlAuditLog;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagMetadataChange;
import com.ruoyi.taglibrary.domain.dto.MetadataChangeDTO;
import com.ruoyi.taglibrary.domain.vo.TagMappingVO;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TlTagMetadataChangeMapper;
import com.ruoyi.taglibrary.service.ITlTagMappingService;

/**
 * 标签元数据变更（批量映射）Service业务层处理
 * 规则：同一标签同时只允许一条 DRAFT/PENDING 记录；草稿仅创建人可改；
 * 变更类型区分 FIRST首次建档/METADATA元数据修改/SOURCE来源变更确认；
 * 保存校验 baseVersion 与草稿 revision，提交/通过时校验来源未漂移；
 * 加锁顺序：库行锁 → 按 tag_id 排序锁标签 → 按 change_id 排序锁变更
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

    /** 变更类型 */
    private static final String CHANGE_FIRST = "FIRST";
    private static final String CHANGE_METADATA = "METADATA";
    private static final String CHANGE_SOURCE = "SOURCE";

    /** 标签状态：1待审批（上线审核中） 4待完善 */
    private static final String TAG_STATUS_PENDING = "1";
    private static final String TAG_STATUS_INCOMPLETE = "4";

    /** 来源状态：变更待确认 */
    private static final String SOURCE_CHANGED = "CHANGED";

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
    private TlTagLibraryMapper libraryMapper;
    @Autowired
    private AuditLogService auditLogService;

    @Override
    public List<TagMappingVO> selectMappingList(TlTag query) {
        String username = SecurityUtils.getUsername();
        // 过滤口径与 /taglibrary/tag/list 一致（del_flag='0' + 入参条件）
        List<TlTag> tags = tagMapper.selectTagList(query);
        // 用 Page 承载结果以保留分页 total（重新包装成普通 List 会使 total 退化为当前页行数）
        Page<TagMappingVO> rows = new Page<>();
        if (tags instanceof Page) {
            Page<TlTag> page = (Page<TlTag>) tags;
            rows.setTotal(page.getTotal());
            rows.setPageNum(page.getPageNum());
            rows.setPageSize(page.getPageSize());
        }
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
                vo.setChangeType(change.getChangeType());
                vo.setRevision(change.getRevision());
                vo.setBaseVersion(change.getBaseVersion());
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
    public List<MetadataChangeDTO> saveDraft(List<MetadataChangeDTO> items) {
        if (items == null || items.isEmpty()) {
            throw new ServiceException("没有需要保存的映射数据");
        }
        String username = SecurityUtils.getUsername();
        // 库行锁（加锁顺序：库 → 标签 → 变更）；按 tag_id 排序处理，降低死锁风险
        lockLibraryByTag(items.get(0).getTagId());
        List<MetadataChangeDTO> sorted = new ArrayList<>(items);
        sorted.sort(Comparator.comparing(MetadataChangeDTO::getTagId));
        List<MetadataChangeDTO> saved = new ArrayList<>();
        for (MetadataChangeDTO item : sorted) {
            // 1. 行锁锁定标签并校验入参（先锁标签，保证同标签的草稿创建互斥）
            TlTag tag = tagMapper.selectTagByIdForUpdate(item.getTagId());
            if (tag == null) {
                throw new ServiceException("标签不存在或已删除");
            }
            // 上线审核中的标签暂停创建新的元数据申请，避免两个审核针对不同内容
            if (TAG_STATUS_PENDING.equals(tag.getStatus())) {
                throw new ServiceException("标签「" + tag.getTagName() + "」正在上线审核中，不能保存元数据草稿");
            }
            // 客户端元数据基线必须与当前版本一致，防止基于旧值编辑
            int baseVersion = tag.getVersion() == null ? 0 : tag.getVersion();
            if (item.getBaseVersion() == null || item.getBaseVersion() != baseVersion) {
                throw new ServiceException("标签「" + tag.getTagName() + "」已被他人修改，请刷新后重新编辑");
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
            // 已有草稿时校验修订号，防止并发保存互相覆盖
            int curRevision = 0;
            if (ownDraft != null) {
                curRevision = ownDraft.getRevision() == null ? 1 : ownDraft.getRevision();
                if (item.getRevision() == null || item.getRevision() != curRevision) {
                    throw new ServiceException("标签「" + tag.getTagName() + "」的草稿已过期，请刷新后重新编辑");
                }
            }

            // 3. 组装 before/after 快照（仅五个可改字段，前端多传的一律忽略）
            Map<String, Object> before = snapshotOf(tag);
            Map<String, Object> after = snapshotOf(item);
            String changeType = resolveChangeType(tag);
            if (!CHANGE_FIRST.equals(changeType) && snapshotEquals(before, after)) {
                // 与当前值一致：已有本人草稿则删除，否则不创建；首次建档允许确认预填信息直接存草稿，不适用该跳过
                if (ownDraft != null) {
                    changeMapper.deleteById(ownDraft.getChangeId());
                }
                continue;
            }

            // 4. 有本人草稿则刷新（revision+1），否则新建；同时记录来源前后快照
            String sourceBefore = confirmedSnapshotOf(tag);
            String sourceAfter = tag.getSourceSnapshot();
            if (ownDraft != null) {
                ownDraft.setBaseVersion(baseVersion);
                ownDraft.setChangeType(changeType);
                ownDraft.setBeforeJson(JSON.toJSONString(before));
                ownDraft.setAfterJson(JSON.toJSONString(after));
                ownDraft.setSourceBefore(sourceBefore);
                ownDraft.setSourceAfter(sourceAfter);
                ownDraft.setRevision(curRevision + 1);
                ownDraft.setUpdateBy(username);
                changeMapper.updateChange(ownDraft);
                item.setChangeId(ownDraft.getChangeId());
                item.setRevision(ownDraft.getRevision());
            } else {
                TlTagMetadataChange change = new TlTagMetadataChange();
                change.setLibraryId(tag.getLibraryId());
                change.setTagId(tag.getTagId());
                change.setBaseVersion(baseVersion);
                change.setChangeType(changeType);
                change.setBeforeJson(JSON.toJSONString(before));
                change.setAfterJson(JSON.toJSONString(after));
                change.setSourceBefore(sourceBefore);
                change.setSourceAfter(sourceAfter);
                change.setRevision(1);
                change.setStatus(STATUS_DRAFT);
                change.setApplyBy(username);
                change.setCreateBy(username);
                changeMapper.insertChange(change);
                item.setChangeId(change.getChangeId());
                item.setRevision(change.getRevision());
            }
            saved.add(item);
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
        lockLibraryByChange(changeIds[0]);
        List<TlTagMetadataChange> changes = lockChanges(changeIds);
        // 按 tag_id 排序锁定标签（加锁顺序：库 → 标签 → 变更）
        changes.sort(Comparator.comparing(TlTagMetadataChange::getTagId));
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
            // 提交时五项元数据必须完整；来源在草稿期间发生变化则申请过期，需重新保存
            validateComplete(tag, change);
            checkSourceFresh(change, tag);
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
        lockLibraryByChange(changeIds[0]);
        // 1. 锁定变更记录，要求全部待审核，否则整批不处理
        List<TlTagMetadataChange> changes = lockChanges(changeIds);
        for (TlTagMetadataChange change : changes) {
            if (!STATUS_PENDING.equals(change.getStatus())) {
                throw new ServiceException("存在非待审核记录，整批不处理");
            }
        }
        // 2. 按 tag_id 排序锁定标签（降低死锁风险），校验基线版本；通过时还需校验来源未漂移（过期申请可驳回不可通过）
        changes.sort(Comparator.comparing(TlTagMetadataChange::getTagId));
        Map<Long, TlTag> tagMap = new HashMap<>();
        for (TlTagMetadataChange change : changes) {
            TlTag tag = lockTag(change.getTagId());
            int curVersion = tag.getVersion() == null ? 0 : tag.getVersion();
            int baseVersion = change.getBaseVersion() == null ? 0 : change.getBaseVersion();
            if (curVersion != baseVersion) {
                throw new ServiceException("标签「" + tag.getTagName() + "」已被他人修改，整批不处理");
            }
            if (pass) {
                checkSourceFresh(change, tag);
            }
            tagMap.put(change.getTagId(), tag);
        }
        // 3. 逐条处理：通过则按变更类型回写 tl_tag（version+1），驳回仅改变更记录状态
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
                if (CHANGE_FIRST.equals(change.getChangeType()) || CHANGE_SOURCE.equals(change.getChangeType())) {
                    // 首次建档/来源变更确认：记录已确认来源指纹并恢复来源可用（观测指纹已经过期校验与申请一致）
                    update.setConfirmedFingerprint(tag.getSourceFingerprint());
                    update.setSourceStatus("AVAILABLE");
                }
                if (CHANGE_FIRST.equals(change.getChangeType())) {
                    // 首次审核通过：待完善 → 草稿（未上线）
                    update.setStatus("0");
                }
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
    @Transactional
    public int withdraw(Long[] changeIds) {
        if (changeIds == null || changeIds.length == 0) {
            return 0;
        }
        String username = SecurityUtils.getUsername();
        lockLibraryByChange(changeIds[0]);
        List<TlTagMetadataChange> changes = lockChanges(changeIds);
        for (TlTagMetadataChange change : changes) {
            if (!STATUS_PENDING.equals(change.getStatus())) {
                throw new ServiceException("变更记录「" + change.getChangeId() + "」不是待审核状态，不能撤回");
            }
            if (!username.equals(change.getApplyBy())) {
                throw new ServiceException("只能撤回本人创建的申请");
            }
            change.setStatus(STATUS_DRAFT);
            change.setUpdateBy(username);
            changeMapper.updateChange(change);
            writeAuditLog(change, "撤回", STATUS_PENDING, STATUS_DRAFT, null, null);
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

    /** 校验草稿行：允许暂缺内容，仅在有值时校验名称空白/类型合法/目录归属/口径长度；完整性在提交时强校验 */
    private void validateItem(TlTag tag, MetadataChangeDTO item) {
        if (item.getTagName() != null) {
            item.setTagName(item.getTagName().trim());
            if (item.getTagName().isEmpty()) {
                item.setTagName(null);
            }
        }
        if (StringUtils.isNotEmpty(item.getTagType()) && !TAG_TYPES.contains(item.getTagType())) {
            throw new ServiceException("标签「" + displayName(tag, item) + "」的标签类型不合法");
        }
        if (item.getDirId() != null) {
            TlTagDir dir = dirMapper.selectDirById(item.getDirId());
            if (dir == null || !dir.getLibraryId().equals(tag.getLibraryId())) {
                throw new ServiceException("标签「" + displayName(tag, item) + "」的目标目录不存在或不属于该标签库");
            }
        }
        if (StringUtils.isNotEmpty(item.getTechCaliber()) && item.getTechCaliber().length() > 500) {
            throw new ServiceException("标签「" + displayName(tag, item) + "」的技术口径最长500字");
        }
        if (StringUtils.isNotEmpty(item.getBusinessCaliber()) && item.getBusinessCaliber().length() > 500) {
            throw new ServiceException("标签「" + displayName(tag, item) + "」的业务口径最长500字");
        }
    }

    /** 提交时强校验：五项元数据必须完整、类型限五类、目录属当前库（来源校验另见 checkSourceFresh） */
    private void validateComplete(TlTag tag, TlTagMetadataChange change) {
        JSONObject after = JSON.parseObject(change.getAfterJson());
        String tagName = after.getString("tagName");
        String tagType = after.getString("tagType");
        Long dirId = after.getLong("dirId");
        if (StringUtils.isEmpty(tagName) || StringUtils.isEmpty(tagName.trim())) {
            throw new ServiceException("标签「" + tag.getTagName() + "」的标签名称未完善，不能提交");
        }
        if (!TAG_TYPES.contains(tagType)) {
            throw new ServiceException("标签「" + tagName.trim() + "」的标签类型未完善或不合法，不能提交");
        }
        if (dirId == null) {
            throw new ServiceException("标签「" + tagName.trim() + "」的标签目录未完善，不能提交");
        }
        TlTagDir dir = dirMapper.selectDirById(dirId);
        if (dir == null || !dir.getLibraryId().equals(tag.getLibraryId())) {
            throw new ServiceException("标签「" + tagName.trim() + "」的目标目录不存在或不属于该标签库");
        }
        if (StringUtils.isEmpty(after.getString("techCaliber"))) {
            throw new ServiceException("标签「" + tagName.trim() + "」的技术口径未完善，不能提交");
        }
        if (StringUtils.isEmpty(after.getString("businessCaliber"))) {
            throw new ServiceException("标签「" + tagName.trim() + "」的业务口径未完善，不能提交");
        }
    }

    /** 校验来源未漂移：申请时观测指纹（source_after 快照重算）与当前观测指纹不一致则申请过期 */
    private void checkSourceFresh(TlTagMetadataChange change, TlTag tag) {
        if (StringUtils.isEmpty(change.getSourceAfter())) {
            // 自建标签无来源快照，不参与来源校验
            return;
        }
        JSONObject snapshot = DpSourceFingerprint.parseSnapshot(change.getSourceAfter());
        if (snapshot == null) {
            return;
        }
        String applied = DpSourceFingerprint.of(snapshot.getLong("datasourceId"), snapshot.getString("tableName"),
                snapshot.getString("columnName"), snapshot.getString("dataType"), snapshot.getString("isPk"));
        if (!applied.equals(tag.getSourceFingerprint())) {
            throw new ServiceException("标签「" + tag.getTagName() + "」的来源已变更，该申请已过期，请驳回或撤回后重新编辑");
        }
    }

    /** 判定变更类型：待完善→首次建档；来源变更待确认→来源确认；其余→元数据修改 */
    private String resolveChangeType(TlTag tag) {
        if (TAG_STATUS_INCOMPLETE.equals(tag.getStatus())) {
            return CHANGE_FIRST;
        }
        if (SOURCE_CHANGED.equals(tag.getSourceStatus())) {
            return CHANGE_SOURCE;
        }
        return CHANGE_METADATA;
    }

    /**
     * 取已确认来源快照：已确认指纹与当前观测一致时即当前快照；
     * 已被同步覆盖（CHANGED）时回查最近一条已通过申请的观测快照；无已确认来源返回 null
     */
    private String confirmedSnapshotOf(TlTag tag) {
        if (tag.getConfirmedFingerprint() == null) {
            return null;
        }
        if (tag.getConfirmedFingerprint().equals(tag.getSourceFingerprint())) {
            return tag.getSourceSnapshot();
        }
        List<TlTagMetadataChange> approved = changeMapper.selectByTagIdAndStatusIn(tag.getTagId(),
                Collections.singletonList(STATUS_APPROVED));
        for (TlTagMetadataChange change : approved) {
            if (StringUtils.isNotEmpty(change.getSourceAfter())) {
                return change.getSourceAfter();
            }
        }
        return null;
    }

    /** 库行锁（由标签定位所属库，批量操作统一先锁库串行化） */
    private void lockLibraryByTag(Long tagId) {
        TlTag tag = tagMapper.selectTagById(tagId);
        if (tag != null) {
            libraryMapper.selectLibraryByIdForUpdate(tag.getLibraryId());
        }
    }

    /** 库行锁（由变更记录定位所属库） */
    private void lockLibraryByChange(Long changeId) {
        TlTagMetadataChange change = changeMapper.selectById(changeId);
        if (change != null) {
            libraryMapper.selectLibraryByIdForUpdate(change.getLibraryId());
        }
    }

    private String displayName(TlTag tag, MetadataChangeDTO item) {
        return StringUtils.isNotEmpty(item.getTagName()) ? item.getTagName() : tag.getTagName();
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
        auditLogService.record(log);
    }
}
