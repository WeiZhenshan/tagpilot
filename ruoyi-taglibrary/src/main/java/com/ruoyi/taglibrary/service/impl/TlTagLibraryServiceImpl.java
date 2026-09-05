package com.ruoyi.taglibrary.service.impl;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.databroker.util.DpSourceFingerprint;
import com.ruoyi.objectgroup.mapper.TlObjectGroupMapper;
import com.ruoyi.objectgroup.mapper.TlTagCodeValueMapper;
import com.ruoyi.taglibrary.domain.TlAuditLog;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.vo.DatasetVO;
import com.ruoyi.taglibrary.domain.vo.TagSyncResultVO;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryDimensionMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TlTagMetadataChangeMapper;
import com.ruoyi.taglibrary.service.ITlTagLibraryService;

/**
 * 标签库Service业务层处理（含元数据同步与状态机）
 *
 * @author ruoyi
 */
@Service
public class TlTagLibraryServiceImpl implements ITlTagLibraryService {

    /** 状态：0草稿 1待审批 2已上线 3已下线 4待完善 */
    private static final String STATUS_DRAFT = "0";
    private static final String STATUS_PENDING = "1";
    private static final String STATUS_ONLINE = "2";
    private static final String STATUS_OFFLINE = "3";
    private static final String STATUS_INCOMPLETE = "4";

    /** 来源状态 */
    private static final String SOURCE_AVAILABLE = "AVAILABLE";
    private static final String SOURCE_MISSING = "MISSING";
    private static final String SOURCE_CHANGED = "CHANGED";

    /** 创建方式：同步建档 */
    private static final String CREATE_WAY_SYNC = "同步";

    private static final String DEFAULT_DIR_NAME = "默认目录";

    private static final Set<String> DATE_TYPES =
            new HashSet<>(Arrays.asList("date", "datetime", "timestamp", "time", "year"));
    private static final Set<String> NUMBER_TYPES =
            new HashSet<>(Arrays.asList("tinyint", "int", "bigint", "smallint", "mediumint", "decimal", "float", "double", "numeric"));

    /** 元数据变更未终态状态：草稿与待审核（删除标签库时清理，终态留作审批留痕） */
    private static final List<String> UNFINAL_CHANGE_STATUSES = Arrays.asList("DRAFT", "PENDING");

    @Autowired
    private TlTagLibraryMapper libraryMapper;
    @Autowired
    private TlTagDirMapper dirMapper;
    @Autowired
    private TlTagMapper tagMapper;
    @Autowired
    private AuditLogService auditLogService;
    @Autowired
    private TlTagLibraryDimensionMapper dimensionMapper;
    @Autowired
    private TlObjectGroupMapper objectGroupMapper;
    @Autowired
    private TlTagCodeValueMapper codeValueMapper;
    @Autowired
    private TlTagMetadataChangeMapper metadataChangeMapper;
    @Autowired
    private DpOnlineVersionResolver versionResolver;

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
        // 状态只能经 提交/审核/上下线 流程流转，禁止普通编辑直接改写，防止绕过审批
        library.setStatus(null);
        // 已设置默认码表的标签库禁止变更关联数据集（默认码表与数据集数据源绑定）
        if (library.getDatasetId() != null) {
            TlTagLibrary old = libraryMapper.selectLibraryById(library.getLibraryId());
            if (old != null && !library.getDatasetId().equals(old.getDatasetId())
                    && dimensionMapper.countByLibraryId(library.getLibraryId()) > 0) {
                throw new ServiceException("已设置默认码表，请先清空默认码表后再变更关联数据集");
            }
        }
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
            int groupCount = objectGroupMapper.countActiveByLibraryId(id);
            if (groupCount > 0) {
                throw new ServiceException("标签库[" + library.getLibraryName() + "]仍被 " + groupCount
                        + " 个对象群使用，不能删除");
            }
        }
        // 级联逻辑删目录+标签，物理清理默认码表关系/码值/未终态元数据变更
        for (Long id : libraryIds) {
            List<TlTagDir> dirs = dirMapper.selectDirList(id);
            for (TlTagDir dir : dirs) {
                dirMapper.deleteDirById(dir.getDirId());
            }
            dimensionMapper.deleteByLibraryId(id);
            codeValueMapper.deleteByLibraryId(id);
            metadataChangeMapper.deleteUnfinalByLibraryId(id, UNFINAL_CHANGE_STATUSES);
        }
        tagMapper.deleteTagByLibraryIds(libraryIds);
        return libraryMapper.deleteLibraryByIds(libraryIds);
    }

    @Override
    @Transactional
    public TagSyncResultVO syncFields(Long libraryId) {
        // 行锁串行化并发同步（uk_tl_tag_field 兜底重复建档）
        TlTagLibrary library = libraryMapper.selectLibraryByIdForUpdate(libraryId);
        if (library == null) {
            throw new ServiceException("标签库不存在");
        }
        if (library.getDatasetId() == null) {
            throw new ServiceException("该标签库未关联数据集");
        }
        // 每次同步只解析一次版本
        DpResolvedVersion version = versionResolver.resolve(library.getDatasetId());
        if (version == null) {
            throw new ServiceException("关联数据集不存在或未上线");
        }
        List<DpResolvedField> fields = versionResolver.listEnabledFields(version.getVersionId());
        if (fields == null || fields.isEmpty()) {
            throw new ServiceException("数据集无启用字段");
        }

        TlTag query = new TlTag();
        query.setLibraryId(libraryId);
        List<TlTag> existTags = tagMapper.selectTagList(query);
        Map<String, TlTag> existByField = new HashMap<>();
        for (TlTag tag : existTags) {
            if (tag.getFieldName() != null) {
                existByField.put(tag.getFieldName(), tag);
            }
        }

        Long defaultDirId = getOrCreateDefaultDir(libraryId);
        String username = SecurityUtils.getUsername();

        int added = 0;
        int changed = 0;
        int restored = 0;
        List<TlTag> newTags = new ArrayList<>();
        Set<String> currentAliases = new HashSet<>();
        for (DpResolvedField field : fields) {
            // 字段别名（引用名）为空时无法生成有效标签，跳过
            if (StringUtils.isEmpty(field.getFieldAlias())) {
                continue;
            }
            currentAliases.add(field.getFieldAlias());
            // 主键口径沿用现有规则：元数据主键或字段对象键任一标记即视为对象键
            String isPk = "1".equals(field.getIsPk()) || "1".equals(field.getIsObjectKey()) ? "1" : "0";
            field.setIsPk(isPk);
            String observed = DpSourceFingerprint.of(field.getDatasourceId(), field.getTableName(),
                    field.getFieldName(), field.getDataType(), isPk);
            String snapshot = DpSourceFingerprint.buildSnapshot(field);

            TlTag exist = existByField.get(field.getFieldAlias());
            if (exist == null) {
                // 新字段：建档为待完善，待首次元数据审核
                newTags.add(buildSyncedTag(libraryId, defaultDirId, version, field, snapshot, observed, isPk, username));
                added++;
                continue;
            }
            String confirmed = exist.getConfirmedFingerprint();
            String oldSourceStatus = exist.getSourceStatus();
            boolean sameStructure = confirmed != null ? confirmed.equals(observed)
                    : Objects.equals(exist.getSourceFingerprint(), observed);
            if (sameStructure) {
                // 同名同结构：保留标签ID/状态/五项人工元数据/草稿，仅刷新来源观测；缺失/变更恢复可用
                refreshSource(exist, version, snapshot, observed, SOURCE_AVAILABLE, isPk, username);
                if (!SOURCE_AVAILABLE.equals(oldSourceStatus)) {
                    restored++;
                }
            } else if (confirmed != null) {
                // 已确认来源后结构变化：标记来源变更待确认，不覆盖元数据，上线状态保持原值
                refreshSource(exist, version, snapshot, observed, SOURCE_CHANGED, isPk, username);
                if (!SOURCE_CHANGED.equals(oldSourceStatus)) {
                    changed++;
                }
            } else {
                // 未通过首次审核：结构变化不算变更，直接更新观测快照保持可用
                refreshSource(exist, version, snapshot, observed, SOURCE_AVAILABLE, isPk, username);
                if (!SOURCE_AVAILABLE.equals(oldSourceStatus)) {
                    restored++;
                }
            }
        }
        if (!newTags.isEmpty()) {
            tagMapper.insertTagBatch(newTags);
        }

        // 字段消失或停用：标记来源缺失，保留标签、元数据和审核历史（自建标签不参与对账）
        List<Long> missingIds = new ArrayList<>();
        for (TlTag tag : existTags) {
            if (!CREATE_WAY_SYNC.equals(tag.getCreateWay()) || tag.getFieldName() == null
                    || currentAliases.contains(tag.getFieldName()) || SOURCE_MISSING.equals(tag.getSourceStatus())) {
                continue;
            }
            missingIds.add(tag.getTagId());
        }
        if (!missingIds.isEmpty()) {
            tagMapper.updateSourceStatusBatch(missingIds.toArray(new Long[0]), SOURCE_MISSING, username);
        }

        libraryMapper.updateLastSync(libraryId, version.getVersionId(), username);

        TagSyncResultVO result = new TagSyncResultVO();
        result.setLibraryId(libraryId);
        result.setVersionId(version.getVersionId());
        result.setVersionNo(version.getVersionNo());
        result.setVersionName(version.getVersionName());
        result.setReason(version.getReason());
        result.setAddedCount(added);
        result.setMissingCount(missingIds.size());
        result.setRestoredCount(restored);
        result.setChangedCount(changed);
        result.setSyncTime(new Date());
        return result;
    }

    /** 构造同步建档标签（待完善，写入来源版本/快照/指纹，已确认指纹留空待首次审核写入） */
    private TlTag buildSyncedTag(Long libraryId, Long dirId, DpResolvedVersion version, DpResolvedField field,
                                 String snapshot, String fingerprint, String isPk, String username) {
        TlTag tag = new TlTag();
        tag.setLibraryId(libraryId);
        tag.setDirId(dirId);
        tag.setFieldName(field.getFieldAlias());
        tag.setTagName(tagNameFromComment(field.getColumnComment(), field.getFieldAlias()));
        tag.setDataType(field.getDataType());
        tag.setIsObjectKey(isPk);
        tag.setTagType(inferTagType(field.getDataType()));
        tag.setCreateWay(CREATE_WAY_SYNC);
        tag.setStatus(STATUS_INCOMPLETE);
        tag.setVersion(1);
        tag.setSourceVersionId(version.getVersionId());
        tag.setSourceSnapshot(snapshot);
        tag.setSourceFingerprint(fingerprint);
        tag.setSourceStatus(SOURCE_AVAILABLE);
        tag.setCreateBy(username);
        return tag;
    }

    /** 刷新标签来源观测（来源版本/快照/指纹/状态 + is_object_key 补写），不动元数据与 version */
    private void refreshSource(TlTag tag, DpResolvedVersion version, String snapshot, String fingerprint,
                               String sourceStatus, String isPk, String username) {
        tag.setSourceVersionId(version.getVersionId());
        tag.setSourceSnapshot(snapshot);
        tag.setSourceFingerprint(fingerprint);
        tag.setSourceStatus(sourceStatus);
        tag.setIsObjectKey(isPk);
        tag.setUpdateBy(username);
        tagMapper.updateSourceById(tag);
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
        auditLogService.record(log);
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

    /** 从源字段中文注释生成标签名：取括号前内容去空白，注释为空时回退字段名 */
    private static String tagNameFromComment(String comment, String fieldName) {
        if (comment == null || comment.trim().isEmpty()) {
            return fieldName;
        }
        String name = comment.trim();
        int paren = name.indexOf('(');
        if (paren > 0) {
            name = name.substring(0, paren);
        }
        return name.trim().isEmpty() ? fieldName : name.trim();
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
