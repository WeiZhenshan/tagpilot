package com.ruoyi.taglibrary.service.impl;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
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
import com.ruoyi.taglibrary.domain.vo.DatasetFieldVO;
import com.ruoyi.taglibrary.domain.vo.DatasetVO;
import com.ruoyi.taglibrary.mapper.TlAuditLogMapper;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.service.ITlTagLibraryService;

/**
 * 标签库Service业务层处理（含元数据同步与状态机）
 *
 * @author ruoyi
 */
@Service
public class TlTagLibraryServiceImpl implements ITlTagLibraryService {

    /** 状态：0草稿 1待审批 2已上线 3已下线 */
    private static final String STATUS_DRAFT = "0";
    private static final String STATUS_PENDING = "1";
    private static final String STATUS_ONLINE = "2";
    private static final String STATUS_OFFLINE = "3";

    private static final String DEFAULT_DIR_NAME = "默认目录";

    private static final Set<String> DATE_TYPES =
            new HashSet<>(Arrays.asList("date", "datetime", "timestamp", "time", "year"));
    private static final Set<String> NUMBER_TYPES =
            new HashSet<>(Arrays.asList("tinyint", "int", "bigint", "smallint", "mediumint", "decimal", "float", "double", "numeric"));

    @Autowired
    private TlTagLibraryMapper libraryMapper;
    @Autowired
    private TlTagDirMapper dirMapper;
    @Autowired
    private TlTagMapper tagMapper;
    @Autowired
    private TlAuditLogMapper auditLogMapper;

    @Override
    public List<TlTagLibrary> selectLibraryList(TlTagLibrary query) {
        return libraryMapper.selectLibraryList(query);
    }

    @Override
    public TlTagLibrary selectLibraryById(Long libraryId) {
        return libraryMapper.selectLibraryById(libraryId);
    }

    @Override
    public List<DatasetVO> listOnlineDatasets() {
        return libraryMapper.selectOnlineDatasets();
    }

    @Override
    @Transactional
    public int insertLibrary(TlTagLibrary library) {
        if (library.getDatasetId() == null) {
            throw new ServiceException("请选择关联数据集");
        }
        if (libraryMapper.selectLibraryByCode(library.getLibraryCode()) != null) {
            throw new ServiceException("标签库编码已存在");
        }
        library.setStatus(STATUS_DRAFT);
        library.setCreateBy(SecurityUtils.getUsername());
        int rows = libraryMapper.insertLibrary(library);

        // 建默认目录
        createDefaultDir(library.getLibraryId());

        // 同步数据集启用字段快照（草稿）
        syncFields(library.getLibraryId());
        return rows;
    }

    @Override
    public int updateLibrary(TlTagLibrary library) {
        library.setUpdateBy(SecurityUtils.getUsername());
        return libraryMapper.updateLibrary(library);
    }

    @Override
    @Transactional
    public int deleteLibraryByIds(Long[] libraryIds) {
        if (libraryIds == null || libraryIds.length == 0) {
            return 0;
        }
        for (Long id : libraryIds) {
            TlTagLibrary library = libraryMapper.selectLibraryById(id);
            if (library == null) {
                continue;
            }
            if (STATUS_PENDING.equals(library.getStatus()) || STATUS_ONLINE.equals(library.getStatus())) {
                throw new ServiceException("已上线或待审批的标签库不能删除");
            }
            if (tagMapper.countOnlineByLibraryId(id) > 0) {
                throw new ServiceException("库内存在已上线标签，不能删除");
            }
        }
        // 级联逻辑删目录+标签
        for (Long id : libraryIds) {
            List<TlTagDir> dirs = dirMapper.selectDirList(id);
            for (TlTagDir dir : dirs) {
                dirMapper.deleteDirById(dir.getDirId());
            }
        }
        tagMapper.deleteTagByLibraryIds(libraryIds);
        return libraryMapper.deleteLibraryByIds(libraryIds);
    }

    @Override
    @Transactional
    public int syncFields(Long libraryId) {
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        if (library.getDatasetId() == null) {
            throw new ServiceException("该标签库未关联数据集");
        }
        Long versionId = libraryMapper.selectOnlineVersionId(library.getDatasetId());
        if (versionId == null) {
            throw new ServiceException("关联数据集不存在或未上线");
        }
        List<DatasetFieldVO> fields = libraryMapper.selectDatasetFields(versionId);
        if (fields == null || fields.isEmpty()) {
            throw new ServiceException("数据集无启用字段");
        }

        // 该库现有 field_name 集合，增量过滤
        TlTag query = new TlTag();
        query.setLibraryId(libraryId);
        List<TlTag> existTags = tagMapper.selectTagList(query);
        Set<String> existFields = new HashSet<>();
        for (TlTag tag : existTags) {
            if (tag.getFieldName() != null) {
                existFields.add(tag.getFieldName());
            }
        }

        Long defaultDirId = getOrCreateDefaultDir(libraryId);
        String username = SecurityUtils.getUsername();

        List<TlTag> newTags = new ArrayList<>();
        for (DatasetFieldVO field : fields) {
            if (existFields.contains(field.getFieldName())) {
                continue;
            }
            TlTag tag = new TlTag();
            tag.setLibraryId(libraryId);
            tag.setDirId(defaultDirId);
            tag.setFieldName(field.getFieldName());
            tag.setTagName(field.getFieldName());
            tag.setDataType(field.getDataType());
            tag.setTagType(inferTagType(field.getDataType()));
            tag.setCreateWay("同步");
            tag.setStatus(STATUS_DRAFT);
            tag.setVersion(1);
            tag.setCreateBy(username);
            newTags.add(tag);
        }
        if (newTags.isEmpty()) {
            return 0;
        }
        tagMapper.insertTagBatch(newTags);
        return newTags.size();
    }

    @Override
    @Transactional
    public int submit(Long libraryId) {
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        if (!STATUS_DRAFT.equals(library.getStatus()) && !STATUS_OFFLINE.equals(library.getStatus())) {
            throw new ServiceException("当前状态不允许该操作");
        }
        int rows = libraryMapper.updateLibraryStatus(libraryId, STATUS_PENDING, SecurityUtils.getUsername());
        writeAuditLog(libraryId, "提交", library.getStatus(), STATUS_PENDING, null);
        return rows;
    }

    @Override
    @Transactional
    public int audit(Long libraryId, boolean pass, String auditComment) {
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        if (!STATUS_PENDING.equals(library.getStatus())) {
            throw new ServiceException("当前状态不允许该操作");
        }
        String toStatus = pass ? STATUS_ONLINE : STATUS_DRAFT;
        int rows = libraryMapper.updateLibraryStatus(libraryId, toStatus, SecurityUtils.getUsername());
        writeAuditLog(libraryId, pass ? "通过" : "驳回", library.getStatus(), toStatus, auditComment);
        return rows;
    }

    @Override
    @Transactional
    public int offline(Long libraryId) {
        TlTagLibrary library = libraryMapper.selectLibraryById(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        if (!STATUS_ONLINE.equals(library.getStatus())) {
            throw new ServiceException("当前状态不允许该操作");
        }
        int rows = libraryMapper.updateLibraryStatus(libraryId, STATUS_OFFLINE, SecurityUtils.getUsername());
        writeAuditLog(libraryId, "下线", library.getStatus(), STATUS_OFFLINE, null);
        return rows;
    }

    // ---- private helpers ----

    /** 写审批留痕；auditComment 非空视为审批动作（记录审批人/审批时间） */
    private void writeAuditLog(Long libraryId, String action, String fromStatus, String toStatus, String auditComment) {
        String username = SecurityUtils.getUsername();
        TlAuditLog log = new TlAuditLog();
        log.setBizType("library");
        log.setBizId(libraryId);
        log.setAction(action);
        log.setFromStatus(fromStatus);
        log.setToStatus(toStatus);
        log.setApplyBy(username);
        if (auditComment != null || "通过".equals(action) || "驳回".equals(action)) {
            log.setAuditBy(username);
            log.setAuditTime(new Date());
            log.setAuditComment(auditComment);
        }
        log.setCreateBy(username);
        auditLogMapper.insertAuditLog(log);
    }

    /** 取默认目录（parent_id=0 且 dir_name='默认目录' 的第一条），没有则建 */
    private Long getOrCreateDefaultDir(Long libraryId) {
        List<TlTagDir> dirs = dirMapper.selectDirList(libraryId);
        for (TlTagDir dir : dirs) {
            if (dir.getParentId() != null && dir.getParentId() == 0L
                    && DEFAULT_DIR_NAME.equals(dir.getDirName())) {
                return dir.getDirId();
            }
        }
        TlTagDir dir = createDefaultDir(libraryId);
        return dir.getDirId();
    }

    private TlTagDir createDefaultDir(Long libraryId) {
        TlTagDir dir = new TlTagDir();
        dir.setLibraryId(libraryId);
        dir.setParentId(0L);
        dir.setDirName(DEFAULT_DIR_NAME);
        dir.setOrderNum(0);
        dir.setCreateBy(SecurityUtils.getUsername());
        dirMapper.insertDir(dir);
        return dir;
    }

    /** 按源字段数据类型推断标签类型（先归一化：小写、截括号、去 unsigned/zerofill） */
    private static String inferTagType(String dataType) {
        String dt = dataType == null ? "" : dataType.toLowerCase();
        int paren = dt.indexOf('(');
        if (paren >= 0) {
            dt = dt.substring(0, paren);
        }
        dt = dt.replace("unsigned", "").replace("zerofill", "").trim();
        if (DATE_TYPES.contains(dt)) {
            return "日期型";
        }
        if (NUMBER_TYPES.contains(dt)) {
            return "数值型";
        }
        return "文本型";
    }
}
