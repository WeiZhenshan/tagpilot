package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.databroker.util.DpSourceFingerprint;
import com.ruoyi.objectgroup.mapper.TlObjectGroupMapper;
import com.ruoyi.objectgroup.mapper.TlTagCodeValueMapper;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.vo.TagSyncResultVO;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryDimensionMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TlTagMetadataChangeMapper;

/**
 * 标签库字段同步对账 Service 单元测试（纯 Mockito，不起 Spring 上下文）
 *
 * @author ruoyi
 */
@ExtendWith(MockitoExtension.class)
class TlTagLibrarySyncTest extends BaseServiceTest {

    private static final Long LIBRARY_ID = 10L;
    private static final Long DATASET_ID = 4L;
    private static final Long VERSION_ID = 7L;
    private static final Long DIR_ID = 100L;

    @Mock
    private TlTagLibraryMapper libraryMapper;
    @Mock
    private TlTagDirMapper dirMapper;
    @Mock
    private TlTagMapper tagMapper;
    @Mock
    private AuditLogService auditLogService;
    @Mock
    private TlTagLibraryDimensionMapper dimensionMapper;
    @Mock
    private TlObjectGroupMapper objectGroupMapper;
    @Mock
    private TlTagCodeValueMapper codeValueMapper;
    @Mock
    private TlTagMetadataChangeMapper metadataChangeMapper;
    @Mock
    private DpOnlineVersionResolver versionResolver;

    @InjectMocks
    private TlTagLibraryServiceImpl libraryService;

    /** 新字段：建档 status='4' 待完善，写来源版本/快照/指纹，已确认指纹为 null */
    @Test
    void 同步_新字段_建档待完善并写来源信息() {
        stubLibrary();
        stubVersion();
        DpResolvedField gender = buildField("gender", "gender", "varchar(8)", "0", null, "性别(码表)");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(gender));
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(new ArrayList<>());
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        ArgumentCaptor<List<TlTag>> captor = listCaptor();
        verify(tagMapper).insertTagBatch(captor.capture());
        TlTag tag = captor.getValue().get(0);
        assertEquals("4", tag.getStatus());
        assertEquals("同步", tag.getCreateWay());
        assertEquals(Integer.valueOf(1), tag.getVersion());
        assertEquals(DIR_ID, tag.getDirId());
        assertEquals("gender", tag.getFieldName());
        assertEquals("性别", tag.getTagName());
        assertEquals(VERSION_ID, tag.getSourceVersionId());
        assertEquals("AVAILABLE", tag.getSourceStatus());
        assertNull(tag.getConfirmedFingerprint());
        assertEquals(fingerprintOf(gender), tag.getSourceFingerprint());
        assertTrue(tag.getSourceSnapshot().contains("indiv_cust"));
        assertEquals(1, result.getAddedCount());
        assertEquals(0, result.getMissingCount());
        assertEquals(0, result.getRestoredCount());
        assertEquals(0, result.getChangedCount());
        assertEquals(VERSION_ID, result.getVersionId());
        assertEquals(Integer.valueOf(2), result.getVersionNo());
        assertEquals(DpOnlineVersionResolver.REASON_DEFAULT, result.getReason());
        verify(libraryMapper).updateLastSync(LIBRARY_ID, VERSION_ID, USERNAME);
    }

    /** 同名同结构：保留标签ID/状态/元数据/version，仅刷新来源观测，统计无变化 */
    @Test
    void 同步_同名同结构_保留元数据不递增version() {
        stubLibrary();
        stubVersion();
        DpResolvedField gender = buildField("gender", "gender", "varchar(8)", "0", null, "性别(码表)");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(gender));
        TlTag exist = buildTag(1L, "gender", "同步");
        exist.setStatus("2");
        exist.setVersion(5);
        exist.setTagName("客户性别");
        exist.setSourceFingerprint(fingerprintOf(gender));
        exist.setConfirmedFingerprint(fingerprintOf(gender));
        exist.setSourceStatus("AVAILABLE");
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(exist));
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        verify(tagMapper, never()).insertTagBatch(anyList());
        ArgumentCaptor<TlTag> captor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateSourceById(captor.capture());
        TlTag update = captor.getValue();
        assertEquals(1L, update.getTagId());
        assertEquals(Integer.valueOf(5), update.getVersion());
        assertEquals("2", update.getStatus());
        assertEquals("客户性别", update.getTagName());
        assertEquals("AVAILABLE", update.getSourceStatus());
        assertEquals(VERSION_ID, update.getSourceVersionId());
        assertEquals(0, result.getAddedCount());
        assertEquals(0, result.getChangedCount());
        assertEquals(0, result.getRestoredCount());
        assertEquals(0, result.getMissingCount());
    }

    /** 字段消失：标记 MISSING，保留标签与元数据 */
    @Test
    void 同步_字段消失_标记来源缺失() {
        stubLibrary();
        stubVersion();
        DpResolvedField age = buildField("age", "age", "int", "0", null, "年龄");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(age));
        TlTag gone = buildTag(1L, "gender", "同步");
        gone.setSourceStatus("AVAILABLE");
        TlTag kept = buildTag(2L, "age", "同步");
        kept.setSourceStatus("AVAILABLE");
        kept.setSourceFingerprint(fingerprintOf(age));
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Arrays.asList(gone, kept));
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        ArgumentCaptor<Long[]> captor = ArgumentCaptor.forClass(Long[].class);
        verify(tagMapper).updateSourceStatusBatch(captor.capture(), eq("MISSING"), eq(USERNAME));
        assertEquals(1, captor.getValue().length);
        assertEquals(1L, captor.getValue()[0]);
        assertEquals(1, result.getMissingCount());
    }

    /** 已确认来源后结构变化：标记 CHANGED，不覆盖元数据，上线状态保持原值 */
    @Test
    void 同步_确认后结构变化_标记来源变更() {
        stubLibrary();
        stubVersion();
        DpResolvedField gender = buildField("gender", "gender", "varchar(16)", "0", null, "性别(码表)");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(gender));
        TlTag exist = buildTag(1L, "gender", "同步");
        exist.setStatus("2");
        exist.setVersion(5);
        exist.setSourceFingerprint("old-fp");
        exist.setConfirmedFingerprint("old-fp");
        exist.setSourceStatus("AVAILABLE");
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(exist));
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        ArgumentCaptor<TlTag> captor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateSourceById(captor.capture());
        TlTag update = captor.getValue();
        assertEquals("CHANGED", update.getSourceStatus());
        assertEquals(fingerprintOf(gender), update.getSourceFingerprint());
        assertEquals("2", update.getStatus());
        assertEquals(Integer.valueOf(5), update.getVersion());
        assertEquals("性别", update.getTagName());
        assertEquals(1, result.getChangedCount());
        verify(tagMapper, never()).insertTagBatch(anyList());
    }

    /** 未通过首次审核（已确认指纹为 null）：结构变化不算 CHANGED，直接更新观测保持 AVAILABLE */
    @Test
    void 同步_未确认结构变化_保持可用() {
        stubLibrary();
        stubVersion();
        DpResolvedField gender = buildField("gender", "gender", "varchar(16)", "0", null, "性别(码表)");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(gender));
        TlTag exist = buildTag(1L, "gender", "同步");
        exist.setStatus("4");
        exist.setSourceFingerprint("old-fp");
        exist.setConfirmedFingerprint(null);
        exist.setSourceStatus("AVAILABLE");
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(exist));
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        ArgumentCaptor<TlTag> captor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateSourceById(captor.capture());
        assertEquals("AVAILABLE", captor.getValue().getSourceStatus());
        assertEquals(fingerprintOf(gender), captor.getValue().getSourceFingerprint());
        assertEquals(0, result.getChangedCount());
        assertEquals(0, result.getRestoredCount());
    }

    /** 字段恢复且观测指纹与已确认指纹一致：MISSING 恢复 AVAILABLE */
    @Test
    void 同步_字段恢复_恢复可用() {
        stubLibrary();
        stubVersion();
        DpResolvedField gender = buildField("gender", "gender", "varchar(8)", "0", null, "性别(码表)");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(gender));
        TlTag exist = buildTag(1L, "gender", "同步");
        exist.setStatus("2");
        exist.setSourceFingerprint(fingerprintOf(gender));
        exist.setConfirmedFingerprint(fingerprintOf(gender));
        exist.setSourceStatus("MISSING");
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(exist));
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        ArgumentCaptor<TlTag> captor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateSourceById(captor.capture());
        assertEquals("AVAILABLE", captor.getValue().getSourceStatus());
        assertEquals("2", captor.getValue().getStatus());
        assertEquals(1, result.getRestoredCount());
    }

    /** 恢复后结构仍与已确认指纹不一致：保持 CHANGED 待审核 */
    @Test
    void 同步_字段恢复但结构不一致_仍为来源变更() {
        stubLibrary();
        stubVersion();
        DpResolvedField gender = buildField("gender", "gender", "varchar(16)", "0", null, "性别(码表)");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(gender));
        TlTag exist = buildTag(1L, "gender", "同步");
        exist.setSourceFingerprint("old-fp");
        exist.setConfirmedFingerprint("old-fp");
        exist.setSourceStatus("MISSING");
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(exist));
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        ArgumentCaptor<TlTag> captor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateSourceById(captor.capture());
        assertEquals("CHANGED", captor.getValue().getSourceStatus());
        assertEquals(0, result.getRestoredCount());
        assertEquals(1, result.getChangedCount());
    }

    /** 重复同步幂等：第二次不重复建档、统计全为 0 */
    @Test
    void 同步_重复执行_幂等() {
        stubLibrary();
        stubVersion();
        DpResolvedField gender = buildField("gender", "gender", "varchar(8)", "0", null, "性别(码表)");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(gender));
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(new ArrayList<>());
        stubDefaultDir();

        libraryService.syncFields(LIBRARY_ID);

        // 第二次同步：库里已有同结构标签
        TlTag exist = buildTag(1L, "gender", "同步");
        exist.setStatus("4");
        exist.setSourceFingerprint(fingerprintOf(gender));
        exist.setSourceStatus("AVAILABLE");
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.singletonList(exist));

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        verify(tagMapper, times(1)).insertTagBatch(anyList());
        assertEquals(0, result.getAddedCount());
        assertEquals(0, result.getMissingCount());
        assertEquals(0, result.getRestoredCount());
        assertEquals(0, result.getChangedCount());
        verify(tagMapper, never()).updateSourceStatusBatch(any(), any(), any());
    }

    /** 自建标签不参与对账：字段名不在当前版本也不标记 MISSING */
    @Test
    void 同步_自建标签_不标记缺失() {
        stubLibrary();
        stubVersion();
        DpResolvedField age = buildField("age", "age", "int", "0", null, "年龄");
        when(versionResolver.listEnabledFields(VERSION_ID)).thenReturn(Collections.singletonList(age));
        TlTag selfBuilt = buildTag(1L, "custom_col", "自建");
        selfBuilt.setSourceStatus("AVAILABLE");
        TlTag kept = buildTag(2L, "age", "同步");
        kept.setSourceStatus("AVAILABLE");
        kept.setSourceFingerprint(fingerprintOf(age));
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Arrays.asList(selfBuilt, kept));
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        verify(tagMapper, never()).updateSourceStatusBatch(any(), any(), any());
        assertEquals(0, result.getMissingCount());
    }

    /** 混合场景统计：新增1 失效1 恢复1 来源变更1 */
    @Test
    void 同步_混合场景_统计正确() {
        stubLibrary();
        stubVersion();
        DpResolvedField same = buildField("same_f", "same_c", "int", "0", null, "同结构");
        DpResolvedField changed = buildField("changed_f", "changed_c", "bigint", "0", null, "结构变");
        DpResolvedField restored = buildField("restored_f", "restored_c", "varchar(8)", "0", null, "恢复");
        DpResolvedField added = buildField("added_f", "added_c", "date", "0", null, "新增");
        when(versionResolver.listEnabledFields(VERSION_ID))
                .thenReturn(Arrays.asList(same, changed, restored, added));

        TlTag sameTag = buildTag(1L, "same_f", "同步");
        sameTag.setSourceFingerprint(fingerprintOf(same));
        sameTag.setConfirmedFingerprint(fingerprintOf(same));
        sameTag.setSourceStatus("AVAILABLE");
        TlTag changedTag = buildTag(2L, "changed_f", "同步");
        changedTag.setSourceFingerprint("old-fp");
        changedTag.setConfirmedFingerprint("old-fp");
        changedTag.setSourceStatus("AVAILABLE");
        TlTag restoredTag = buildTag(3L, "restored_f", "同步");
        restoredTag.setSourceFingerprint(fingerprintOf(restored));
        restoredTag.setConfirmedFingerprint(fingerprintOf(restored));
        restoredTag.setSourceStatus("MISSING");
        TlTag goneTag = buildTag(4L, "gone_f", "同步");
        goneTag.setSourceStatus("AVAILABLE");
        when(tagMapper.selectTagList(any(TlTag.class)))
                .thenReturn(Arrays.asList(sameTag, changedTag, restoredTag, goneTag));
        stubDefaultDir();

        TagSyncResultVO result = libraryService.syncFields(LIBRARY_ID);

        assertEquals(1, result.getAddedCount());
        assertEquals(1, result.getMissingCount());
        assertEquals(1, result.getRestoredCount());
        assertEquals(1, result.getChangedCount());
    }

    /** 无在线版本：抛 ServiceException("关联数据集不存在或未上线") */
    @Test
    void 同步_无在线版本_报错() {
        stubLibrary();
        when(versionResolver.resolve(DATASET_ID)).thenReturn(null);

        ServiceException e = assertThrows(ServiceException.class, () -> libraryService.syncFields(LIBRARY_ID));
        assertTrue(e.getMessage().contains("关联数据集不存在或未上线"));
        verify(tagMapper, never()).insertTagBatch(anyList());
    }

    /** 标签库不存在：抛 ServiceException */
    @Test
    void 同步_标签库不存在_报错() {
        when(libraryMapper.selectLibraryByIdForUpdate(LIBRARY_ID)).thenReturn(null);

        ServiceException e = assertThrows(ServiceException.class, () -> libraryService.syncFields(LIBRARY_ID));
        assertTrue(e.getMessage().contains("标签库不存在"));
    }

    // ---- 测试辅助 ----

    private void stubLibrary() {
        TlTagLibrary library = new TlTagLibrary();
        library.setLibraryId(LIBRARY_ID);
        library.setDatasetId(DATASET_ID);
        library.setStatus("0");
        when(libraryMapper.selectLibraryByIdForUpdate(LIBRARY_ID)).thenReturn(library);
    }

    private void stubVersion() {
        DpResolvedVersion version = new DpResolvedVersion();
        version.setDatasetId(DATASET_ID);
        version.setVersionId(VERSION_ID);
        version.setVersionNo(2);
        version.setVersionName("V2");
        version.setIsDefault(true);
        version.setReason(DpOnlineVersionResolver.REASON_DEFAULT);
        when(versionResolver.resolve(DATASET_ID)).thenReturn(version);
    }

    private void stubDefaultDir() {
        TlTagDir dir = new TlTagDir();
        dir.setDirId(DIR_ID);
        dir.setLibraryId(LIBRARY_ID);
        dir.setParentId(0L);
        dir.setDirName("默认目录");
        when(dirMapper.selectDirList(LIBRARY_ID)).thenReturn(Collections.singletonList(dir));
    }

    /** 构造解析字段（数据源101、物理表 indiv_cust） */
    private DpResolvedField buildField(String alias, String columnName, String dataType, String isPk,
                                       String isObjectKey, String comment) {
        DpResolvedField field = new DpResolvedField();
        field.setFieldId(1L);
        field.setFieldAlias(alias);
        field.setFieldName(columnName);
        field.setDataType(dataType);
        field.setIsPk(isPk);
        field.setIsObjectKey(isObjectKey);
        field.setColumnComment(comment);
        field.setSourceTableId(10L);
        field.setSourceColumnId(20L);
        field.setTableName("indiv_cust");
        field.setDatasourceId(101L);
        return field;
    }

    /** 与服务同口径的预期指纹：元数据主键或字段对象键任一标记即视为对象键 */
    private String fingerprintOf(DpResolvedField field) {
        String isPk = "1".equals(field.getIsPk()) || "1".equals(field.getIsObjectKey()) ? "1" : "0";
        return DpSourceFingerprint.of(field.getDatasourceId(), field.getTableName(),
                field.getFieldName(), field.getDataType(), isPk);
    }

    private TlTag buildTag(Long tagId, String fieldName, String createWay) {
        TlTag tag = new TlTag();
        tag.setTagId(tagId);
        tag.setLibraryId(LIBRARY_ID);
        tag.setDirId(DIR_ID);
        tag.setFieldName(fieldName);
        tag.setTagName("性别");
        tag.setTagType("选项型");
        tag.setCreateWay(createWay);
        tag.setStatus("0");
        tag.setVersion(1);
        tag.setDelFlag("0");
        return tag;
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private ArgumentCaptor<List<TlTag>> listCaptor() {
        return (ArgumentCaptor) ArgumentCaptor.forClass(List.class);
    }
}
