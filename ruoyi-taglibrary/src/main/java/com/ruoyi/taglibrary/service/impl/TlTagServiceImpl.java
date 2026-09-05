package com.ruoyi.taglibrary.service.impl;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.taglibrary.domain.TlAuditLog;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TlTagMetadataChangeMapper;
import com.ruoyi.taglibrary.service.ITlTagService;

/**
 * 标签Service业务层处理（含状态机与审批留痕）
 *
 * @author ruoyi
 */
@Service
public class TlTagServiceImpl implements ITlTagService {

    /** 状态：0草稿 1待审批 2已上线 3已下线 4待完善 */
    private static final String STATUS_DRAFT = "0";
    private static final String STATUS_PENDING = "1";
    private static final String STATUS_ONLINE = "2";
    private static final String STATUS_OFFLINE = "3";
    private static final String STATUS_INCOMPLETE = "4";
    /** 元数据变更申请的待审核状态（tl_tag_metadata_change.status，与标签状态值域不同） */
    private static final String CHANGE_PENDING = "PENDING";

    /** 创建方式：同步建档（其五项元数据只能走批量映射变更流程） */
    private static final String CREATE_WAY_SYNC = "同步";

    @Autowired
    private TlTagMapper tagMapper;
    @Autowired
    private TlTagDirMapper dirMapper;
    @Autowired
    private TlTagLibraryMapper libraryMapper;
    @Autowired
    private TlTagMetadataChangeMapper metadataChangeMapper;
    @Autowired
    private AuditLogService auditLogService;

    @Override
    public List<TlTag> selectTagList(TlTag query) {
        // 标签管理列表排除待完善标签（仅批量映射可见）
        query.setExcludeIncomplete(true);
        return tagMapper.selectTagList(query);
    }

    @Override
    public TlTag selectTagById(Long tagId) {
        TlTag tag = tagMapper.selectTagById(tagId);
        if (tag != null && STATUS_INCOMPLETE.equals(tag.getStatus())) {
            throw new ServiceException("待完善标签请在批量映射中维护");
        }
        return tag;
    }

    @Override
    public List<Map<String, Object>> buildTree(Long libraryId, String tab) {
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }

        // tab=online → 已上线；tab=offline → 草稿/待审批/已下线；tab=all → 全部状态；待完善标签只在批量映射可见
        TlTag query = new TlTag();
        query.setLibraryId(libraryId);
        List<TlTag> allTags = tagMapper.selectTagList(query);
        Set<String> offlineStatuses = new HashSet<>(Arrays.asList(STATUS_DRAFT, STATUS_PENDING, STATUS_OFFLINE));
        List<TlTag> tags = new ArrayList<>();
        for (TlTag tag : allTags) {
            if (STATUS_INCOMPLETE.equals(tag.getStatus())) {
                continue;
            }
            if ("all".equals(tab) ? true
                    : "online".equals(tab) ? STATUS_ONLINE.equals(tag.getStatus())
                            : offlineStatuses.contains(tag.getStatus())) {
                tags.add(tag);
            }
        }

        // 二层目录节点
        List<TlTagDir> dirs = dirMapper.selectDirList(libraryId);
        Map<Long, Map<String, Object>> dirNodeMap = new LinkedHashMap<>();
        List<Map<String, Object>> dirNodes = new ArrayList<>();
        for (TlTagDir dir : dirs) {
            Map<String, Object> node = new LinkedHashMap<>();
            node.put("id", "dir-" + dir.getDirId());
            node.put("label", dir.getDirName());
            node.put("count", 0);
            node.put("children", new ArrayList<Map<String, Object>>());
            dirNodeMap.put(dir.getDirId(), node);
            dirNodes.add(node);
        }

        // 标签挂到对应目录
        for (TlTag tag : tags) {
            Map<String, Object> dirNode = dirNodeMap.get(tag.getDirId());
            if (dirNode == null) {
                continue;
            }
            Map<String, Object> node = new LinkedHashMap<>();
            node.put("id", "tag-" + tag.getTagId());
            node.put("label", tag.getTagName());
            node.put("tagType", tag.getTagType());
            node.put("status", tag.getStatus());
            node.put("sourceStatus", tag.getSourceStatus());
            node.put("dataType", tag.getDataType());
            node.put("fieldName", tag.getFieldName());
            node.put("isObjectKey", tag.getIsObjectKey());
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> children = (List<Map<String, Object>>) dirNode.get("children");
            children.add(node);
            dirNode.put("count", children.size());
        }

        // 根节点（库）
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("id", "lib-" + library.getLibraryId());
        root.put("label", library.getLibraryName());
        root.put("count", tags.size());
        root.put("children", dirNodes);

        List<Map<String, Object>> tree = new ArrayList<>();
        tree.add(root);
        return tree;
    }

    @Override
    public int updateTag(TlTag tag) {
        TlTag old = tagMapper.selectTagById(tag.getTagId());
        if (old == null) {
            throw new ServiceException("标签不存在");
        }
        // 同步建档标签的五项元数据只能走批量映射变更流程，禁止直接编辑绕过审核；其余字段（有效日期/更新周期/备注等）仍可改
        if (CREATE_WAY_SYNC.equals(old.getCreateWay()) && metadataChanged(old, tag)) {
            throw new ServiceException("同步建档标签的名称/类型/目录/口径请在批量映射中通过元数据变更流程修改");
        }
        // fieldName/dataType 为源字段快照，不允许修改；status 只能走状态机流转
        tag.setFieldName(null);
        tag.setDataType(null);
        tag.setStatus(null);
        tag.setVersion(old.getVersion() == null ? 1 : old.getVersion() + 1);
        tag.setUpdateBy(SecurityUtils.getUsername());
        return tagMapper.updateTag(tag);
    }

    /** 判断入参是否试图修改五项人工元数据（null 表示不修改该字段） */
    private boolean metadataChanged(TlTag old, TlTag tag) {
        if (tag.getTagName() != null && !tag.getTagName().equals(old.getTagName())) {
            return true;
        }
        if (tag.getTagType() != null && !tag.getTagType().equals(old.getTagType())) {
            return true;
        }
        if (tag.getDirId() != null && !tag.getDirId().equals(old.getDirId())) {
            return true;
        }
        if (tag.getTechCaliber() != null && !tag.getTechCaliber().equals(old.getTechCaliber())) {
            return true;
        }
        return tag.getBusinessCaliber() != null && !tag.getBusinessCaliber().equals(old.getBusinessCaliber());
    }

    @Override
    public int moveTag(Long[] tagIds, Long dirId) {
        if (tagIds == null || tagIds.length == 0) {
            return 0;
        }
        // 目标目录必须存在且与标签同属一个标签库；同步建档标签的目录调整只能走元数据草稿流程
        TlTag first = tagMapper.selectTagById(tagIds[0]);
        if (first == null) {
            throw new ServiceException("标签不存在");
        }
        TlTagDir dir = dirMapper.selectDirById(dirId);
        if (dir == null || !dir.getLibraryId().equals(first.getLibraryId())) {
            throw new ServiceException("目标目录不存在或不属于该标签库");
        }
        for (Long id : tagIds) {
            TlTag tag = tagMapper.selectTagById(id);
            if (tag != null && CREATE_WAY_SYNC.equals(tag.getCreateWay())) {
                throw new ServiceException("同步建档标签「" + tag.getTagName() + "」请在批量映射中通过元数据变更流程调整目录");
            }
        }
        return tagMapper.moveTagBatch(tagIds, dirId, SecurityUtils.getUsername());
    }

    @Override
    @Transactional
    public int submit(Long[] tagIds) {
        if (tagIds == null || tagIds.length == 0) {
            return 0;
        }
        List<TlTag> tags = new ArrayList<>();
        for (Long id : tagIds) {
            TlTag tag = tagMapper.selectTagById(id);
            if (tag == null) {
                continue;
            }
            if (STATUS_INCOMPLETE.equals(tag.getStatus())) {
                throw new ServiceException("待完善标签需先通过元数据审核");
            }
            if (!STATUS_DRAFT.equals(tag.getStatus()) && !STATUS_OFFLINE.equals(tag.getStatus())) {
                throw new ServiceException("当前状态不允许该操作");
            }
            // 元数据审核中的标签不能同时提交上线审核，避免两个审核针对不同内容
            if (!metadataChangeMapper.selectByTagIdAndStatusIn(tag.getTagId(),
                    Collections.singletonList(CHANGE_PENDING)).isEmpty()) {
                throw new ServiceException("标签「" + tag.getTagName() + "」存在待审核的元数据申请，不能提交上线审核");
            }
            tags.add(tag);
        }
        int rows = tagMapper.updateTagStatusBatch(tagIds, STATUS_PENDING, SecurityUtils.getUsername());
        for (TlTag tag : tags) {
            writeAuditLog(tag.getTagId(), "提交", tag.getStatus(), STATUS_PENDING, null);
        }
        return rows;
    }

    @Override
    @Transactional
    public int audit(Long[] tagIds, boolean pass, String auditComment) {
        if (tagIds == null || tagIds.length == 0) {
            return 0;
        }
        List<TlTag> tags = new ArrayList<>();
        for (Long id : tagIds) {
            TlTag tag = tagMapper.selectTagById(id);
            if (tag == null) {
                continue;
            }
            if (STATUS_INCOMPLETE.equals(tag.getStatus())) {
                throw new ServiceException("待完善标签需先通过元数据审核");
            }
            if (!STATUS_PENDING.equals(tag.getStatus())) {
                throw new ServiceException("当前状态不允许该操作");
            }
            tags.add(tag);
        }
        String toStatus = pass ? STATUS_ONLINE : STATUS_DRAFT;
        int rows = tagMapper.updateTagStatusBatch(tagIds, toStatus, SecurityUtils.getUsername());
        for (TlTag tag : tags) {
            writeAuditLog(tag.getTagId(), pass ? "通过" : "驳回", tag.getStatus(), toStatus, auditComment);
        }
        return rows;
    }

    @Override
    @Transactional
    public int offline(Long[] tagIds) {
        if (tagIds == null || tagIds.length == 0) {
            return 0;
        }
        List<TlTag> tags = new ArrayList<>();
        for (Long id : tagIds) {
            TlTag tag = tagMapper.selectTagById(id);
            if (tag == null) {
                continue;
            }
            if (STATUS_INCOMPLETE.equals(tag.getStatus())) {
                throw new ServiceException("待完善标签需先通过元数据审核");
            }
            if (!STATUS_ONLINE.equals(tag.getStatus())) {
                throw new ServiceException("当前状态不允许该操作");
            }
            tags.add(tag);
        }
        int rows = tagMapper.updateTagStatusBatch(tagIds, STATUS_OFFLINE, SecurityUtils.getUsername());
        for (TlTag tag : tags) {
            writeAuditLog(tag.getTagId(), "下线", tag.getStatus(), STATUS_OFFLINE, null);
        }
        return rows;
    }

    // ---- private helpers ----

    /** 写审批留痕；审批动作（通过/驳回）记录审批人/审批时间/审批意见 */
    private void writeAuditLog(Long tagId, String action, String fromStatus, String toStatus, String auditComment) {
        String username = SecurityUtils.getUsername();
        TlAuditLog log = new TlAuditLog();
        log.setBizType("tag");
        log.setBizId(tagId);
        log.setAction(action);
        log.setFromStatus(fromStatus);
        log.setToStatus(toStatus);
        log.setApplyBy(username);
        if ("通过".equals(action) || "驳回".equals(action)) {
            log.setAuditBy(username);
            log.setAuditTime(new Date());
            log.setAuditComment(auditComment);
        }
        log.setCreateBy(username);
        auditLogService.record(log);
    }
}
