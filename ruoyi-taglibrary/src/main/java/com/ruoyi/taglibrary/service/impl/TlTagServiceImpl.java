package com.ruoyi.taglibrary.service.impl;

import java.util.ArrayList;
import java.util.Arrays;
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
import com.ruoyi.taglibrary.service.ITlTagService;

/**
 * 标签Service业务层处理（含状态机与审批留痕）
 *
 * @author ruoyi
 */
@Service
public class TlTagServiceImpl implements ITlTagService {

    /** 状态：0草稿 1待审批 2已上线 3已下线 */
    private static final String STATUS_DRAFT = "0";
    private static final String STATUS_PENDING = "1";
    private static final String STATUS_ONLINE = "2";
    private static final String STATUS_OFFLINE = "3";

    @Autowired
    private TlTagMapper tagMapper;
    @Autowired
    private TlTagDirMapper dirMapper;
    @Autowired
    private TlTagLibraryMapper libraryMapper;
    @Autowired
    private AuditLogService auditLogService;

    @Override
    public List<TlTag> selectTagList(TlTag query) {
        return tagMapper.selectTagList(query);
    }

    @Override
    public TlTag selectTagById(Long tagId) {
        return tagMapper.selectTagById(tagId);
    }

    @Override
    public List<Map<String, Object>> buildTree(Long libraryId, String tab) {
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }

        // tab=online → 已上线；tab=offline → 草稿/待审批/已下线；tab=all → 全部状态
        TlTag query = new TlTag();
        query.setLibraryId(libraryId);
        List<TlTag> allTags = tagMapper.selectTagList(query);
        Set<String> offlineStatuses = new HashSet<>(Arrays.asList(STATUS_DRAFT, STATUS_PENDING, STATUS_OFFLINE));
        List<TlTag> tags = new ArrayList<>();
        for (TlTag tag : allTags) {
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
        // fieldName/dataType 为源字段快照，不允许修改；status 只能走状态机流转
        tag.setFieldName(null);
        tag.setDataType(null);
        tag.setStatus(null);
        tag.setVersion(old.getVersion() == null ? 1 : old.getVersion() + 1);
        tag.setUpdateBy(SecurityUtils.getUsername());
        return tagMapper.updateTag(tag);
    }

    @Override
    public int moveTag(Long[] tagIds, Long dirId) {
        if (tagIds == null || tagIds.length == 0) {
            return 0;
        }
        // 目标目录必须存在且与标签同属一个标签库
        TlTag first = tagMapper.selectTagById(tagIds[0]);
        if (first == null) {
            throw new ServiceException("标签不存在");
        }
        TlTagDir dir = dirMapper.selectDirById(dirId);
        if (dir == null || !dir.getLibraryId().equals(first.getLibraryId())) {
            throw new ServiceException("目标目录不存在或不属于该标签库");
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
            if (!STATUS_DRAFT.equals(tag.getStatus()) && !STATUS_OFFLINE.equals(tag.getStatus())) {
                throw new ServiceException("当前状态不允许该操作");
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
