package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
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
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.util.DpSourceFingerprint;
import com.ruoyi.taglibrary.domain.TlAuditLog;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.TlTagMetadataChange;
import com.ruoyi.taglibrary.domain.dto.MetadataChangeDTO;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TlTagMetadataChangeMapper;

/**
 * 标签元数据变更（草稿/提交/审核/撤回）Service 单元测试（纯 Mockito，不起 Spring 上下文）
 *
 * @author ruoyi
 */
@ExtendWith(MockitoExtension.class)
class TlTagMappingServiceImplTest extends BaseServiceTest {

    private static final Long TAG_ID = 1L;
    private static final Long LIBRARY_ID = 10L;
    private static final Long DIR_ID = 100L;

    @Mock
    private TlTagMapper tagMapper;
    @Mock
    private TlTagDirMapper dirMapper;
    @Mock
    private TlTagMetadataChangeMapper changeMapper;
    @Mock
    private TlTagLibraryMapper libraryMapper;
    @Mock
    private AuditLogService auditLogService;

    @InjectMocks
    private TlTagMappingServiceImpl mappingService;

    /** 草稿保存成功：insertChange 被调用，status=DRAFT，changeType=METADATA，revision=1，快照仅含五字段，响应回填申请标识 */
    @Test
    void saveDraftSuccess() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList())).thenReturn(new ArrayList<>());
        when(changeMapper.insertChange(any(TlTagMetadataChange.class))).thenAnswer(inv -> {
            TlTagMetadataChange c = inv.getArgument(0);
            c.setChangeId(5L);
            return 1;
        });
        MetadataChangeDTO item = buildItem(TAG_ID, "新名称", "数值型", DIR_ID, "tech2", "biz2");

        List<MetadataChangeDTO> saved = mappingService.saveDraft(Collections.singletonList(item));

        assertEquals(1, saved.size());
        assertEquals(5L, saved.get(0).getChangeId());
        assertEquals(Integer.valueOf(1), saved.get(0).getRevision());
        ArgumentCaptor<TlTagMetadataChange> captor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).insertChange(captor.capture());
        TlTagMetadataChange change = captor.getValue();
        assertEquals("DRAFT", change.getStatus());
        assertEquals("METADATA", change.getChangeType());
        assertEquals(Integer.valueOf(1), change.getRevision());
        assertEquals(Integer.valueOf(3), change.getBaseVersion());
        assertEquals(USERNAME, change.getApplyBy());
        assertEquals(LIBRARY_ID, change.getLibraryId());
        assertEquals(TAG_ID, change.getTagId());
        JSONObject after = JSON.parseObject(change.getAfterJson());
        assertEquals(5, after.size());
        assertFalse(after.containsKey("fieldName"));
        assertEquals("新名称", after.getString("tagName"));
        assertEquals("数值型", after.getString("tagType"));
        assertEquals(DIR_ID, after.getLong("dirId"));
        JSONObject before = JSON.parseObject(change.getBeforeJson());
        assertEquals("性别", before.getString("tagName"));
        assertEquals("选项型", before.getString("tagType"));
    }

    /** 首次建档：待完善标签即使与预填值一致也允许直接存草稿，changeType=FIRST */
    @Test
    void saveDraftFirstPrefillNoChangeStillCreates() {
        TlTag tag = buildTag(TAG_ID, 1);
        tag.setStatus("4");
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList())).thenReturn(new ArrayList<>());
        // 与当前五字段完全一致（确认预填信息）
        MetadataChangeDTO item = buildItem(TAG_ID, "性别", "选项型", DIR_ID, "tech", "biz");
        item.setBaseVersion(1);

        List<MetadataChangeDTO> saved = mappingService.saveDraft(Collections.singletonList(item));

        assertEquals(1, saved.size());
        ArgumentCaptor<TlTagMetadataChange> captor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).insertChange(captor.capture());
        assertEquals("FIRST", captor.getValue().getChangeType());
        assertEquals("DRAFT", captor.getValue().getStatus());
        verify(changeMapper, never()).deleteById(anyLong());
    }

    /** 来源变更待确认的标签保存草稿：changeType=SOURCE，来源前后快照落记录 */
    @Test
    void saveDraftSourceChangeTypeWithSnapshots() {
        TlTag tag = buildTag(TAG_ID, 3);
        tag.setStatus("2");
        tag.setSourceStatus("CHANGED");
        tag.setSourceFingerprint("fp-new");
        tag.setSourceSnapshot(sourceSnapshotJson("varchar(16)"));
        tag.setConfirmedFingerprint("fp-old");
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        TlTagMetadataChange approved = buildChange(9L, TAG_ID, "APPROVED", USERNAME, 2);
        approved.setSourceAfter(sourceSnapshotJson("varchar(8)"));
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList())).thenAnswer(inv -> {
            List<String> statuses = inv.getArgument(1);
            return statuses.contains("APPROVED") ? Collections.singletonList(approved) : new ArrayList<>();
        });
        MetadataChangeDTO item = buildItem(TAG_ID, "新名称", "选项型", DIR_ID, "tech", "biz");

        mappingService.saveDraft(Collections.singletonList(item));

        ArgumentCaptor<TlTagMetadataChange> captor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).insertChange(captor.capture());
        TlTagMetadataChange change = captor.getValue();
        assertEquals("SOURCE", change.getChangeType());
        // 已确认快照已被同步覆盖，回查最近通过申请的观测快照作为 source_before
        assertEquals(sourceSnapshotJson("varchar(8)"), change.getSourceBefore());
        assertEquals(sourceSnapshotJson("varchar(16)"), change.getSourceAfter());
    }

    /** 刷新本人草稿：revision 一致 → 更新且 revision+1 */
    @Test
    void saveDraftRefreshOwnDraftIncrementsRevision() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        TlTagMetadataChange ownDraft = buildChange(5L, TAG_ID, "DRAFT", USERNAME, 3);
        ownDraft.setRevision(2);
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList()))
                .thenReturn(Collections.singletonList(ownDraft));
        MetadataChangeDTO item = buildItem(TAG_ID, "新名称", "数值型", DIR_ID, "tech2", "biz2");
        item.setRevision(2);

        List<MetadataChangeDTO> saved = mappingService.saveDraft(Collections.singletonList(item));

        assertEquals(1, saved.size());
        assertEquals(Integer.valueOf(3), saved.get(0).getRevision());
        ArgumentCaptor<TlTagMetadataChange> captor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).updateChange(captor.capture());
        assertEquals(Integer.valueOf(3), captor.getValue().getRevision());
        verify(changeMapper, never()).insertChange(any());
    }

    /** 校验失败：tagType 非法值 → ServiceException */
    @Test
    void saveDraftInvalidTagTypeRejected() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        MetadataChangeDTO item = buildItem(TAG_ID, "名称", "非法类型", DIR_ID, null, null);

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.saveDraft(Collections.singletonList(item)));
        assertTrue(e.getMessage().contains("标签类型不合法"));
        verify(changeMapper, never()).insertChange(any());
    }

    /** 校验失败：dirId 不属于该标签库 → ServiceException */
    @Test
    void saveDraftCrossLibraryDirRejected() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, 99L));
        MetadataChangeDTO item = buildItem(TAG_ID, "名称", "选项型", DIR_ID, null, null);

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.saveDraft(Collections.singletonList(item)));
        assertTrue(e.getMessage().contains("不属于该标签库"));
        verify(changeMapper, never()).insertChange(any());
    }

    /** 基线版本过期：item.baseVersion ≠ tl_tag.version → ServiceException */
    @Test
    void saveDraftBaseVersionMismatchRejected() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        MetadataChangeDTO item = buildItem(TAG_ID, "新名称", "选项型", DIR_ID, "tech", "biz");
        item.setBaseVersion(2);

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.saveDraft(Collections.singletonList(item)));
        assertTrue(e.getMessage().contains("已被他人修改"));
        verify(changeMapper, never()).insertChange(any());
    }

    /** 草稿修订号过期：已有草稿 revision=2，入参 revision=1 → ServiceException */
    @Test
    void saveDraftRevisionMismatchRejected() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        TlTagMetadataChange ownDraft = buildChange(5L, TAG_ID, "DRAFT", USERNAME, 3);
        ownDraft.setRevision(2);
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList()))
                .thenReturn(Collections.singletonList(ownDraft));
        MetadataChangeDTO item = buildItem(TAG_ID, "新名称", "数值型", DIR_ID, "tech2", "biz2");
        item.setRevision(1);

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.saveDraft(Collections.singletonList(item)));
        assertTrue(e.getMessage().contains("草稿已过期"));
        verify(changeMapper, never()).updateChange(any());
        verify(changeMapper, never()).insertChange(any());
    }

    /** 上线审核中（status='1'）的标签禁止创建元数据草稿（双阶段互斥） */
    @Test
    void saveDraftWhileOnlineAuditPendingRejected() {
        TlTag tag = buildTag(TAG_ID, 3);
        tag.setStatus("1");
        stubSaveDraftLocks(tag);
        MetadataChangeDTO item = buildItem(TAG_ID, "新名称", "选项型", DIR_ID, "tech", "biz");

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.saveDraft(Collections.singletonList(item)));
        assertTrue(e.getMessage().contains("上线审核中"));
        verify(changeMapper, never()).insertChange(any());
    }

    /** 无变化不建草稿：提交值与当前 tl_tag 完全一致且无已有草稿 → insertChange 不被调用 */
    @Test
    void saveDraftNoChangeNoInsert() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList())).thenReturn(new ArrayList<>());
        MetadataChangeDTO item = buildItem(TAG_ID, "性别", "选项型", DIR_ID, "tech", "biz");

        List<MetadataChangeDTO> saved = mappingService.saveDraft(Collections.singletonList(item));

        assertEquals(0, saved.size());
        verify(changeMapper, never()).insertChange(any());
        verify(changeMapper, never()).updateChange(any());
        verify(changeMapper, never()).deleteById(anyLong());
    }

    /** 无变化删草稿：提交值与当前一致但已有本人 DRAFT → deleteById 被调用 */
    @Test
    void saveDraftNoChangeDeletesOwnDraft() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        TlTagMetadataChange ownDraft = buildChange(5L, TAG_ID, "DRAFT", USERNAME, 3);
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList()))
                .thenReturn(Collections.singletonList(ownDraft));
        MetadataChangeDTO item = buildItem(TAG_ID, "性别", "选项型", DIR_ID, "tech", "biz");
        item.setRevision(1);

        List<MetadataChangeDTO> saved = mappingService.saveDraft(Collections.singletonList(item));

        assertEquals(0, saved.size());
        verify(changeMapper).deleteById(5L);
        verify(changeMapper, never()).insertChange(any());
        verify(changeMapper, never()).updateChange(any());
    }

    /** 他人草稿不可改：该标签已有 apply_by=他人的 DRAFT → ServiceException */
    @Test
    void saveDraftOthersDraftRejected() {
        TlTag tag = buildTag(TAG_ID, 3);
        stubSaveDraftLocks(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        TlTagMetadataChange othersDraft = buildChange(5L, TAG_ID, "DRAFT", "lisi", 3);
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList()))
                .thenReturn(Collections.singletonList(othersDraft));
        MetadataChangeDTO item = buildItem(TAG_ID, "新名称", "选项型", DIR_ID, "tech", "biz");

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.saveDraft(Collections.singletonList(item)));
        assertTrue(e.getMessage().contains("他人草稿"));
        verify(changeMapper, never()).insertChange(any());
        verify(changeMapper, never()).updateChange(any());
    }

    /** 提交校验：changeIds 含他人草稿 → ServiceException，整批不处理 */
    @Test
    void submitOthersDraftRejected() {
        TlTagMetadataChange othersDraft = buildChange(1L, TAG_ID, "DRAFT", "lisi", 3);
        stubAuditLocks(othersDraft);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(othersDraft));

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.submit(new Long[]{1L}));
        assertTrue(e.getMessage().contains("只能提交本人"));
        verify(changeMapper, never()).updateChange(any());
        verify(auditLogService, never()).record(any());
    }

    /** 提交校验：changeIds 含非 DRAFT 记录 → ServiceException，整批不处理 */
    @Test
    void submitNonDraftRejected() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.submit(new Long[]{1L}));
        assertTrue(e.getMessage().contains("不是草稿状态"));
        verify(changeMapper, never()).updateChange(any());
        verify(auditLogService, never()).record(any());
    }

    /** 提交校验：五项元数据不完整（缺技术口径）→ ServiceException */
    @Test
    void submitIncompleteMetadataRejected() {
        TlTagMetadataChange draft = buildChange(1L, TAG_ID, "DRAFT", USERNAME, 3);
        draft.setAfterJson("{\"tagName\":\"性别\",\"tagType\":\"选项型\",\"dirId\":100,"
                + "\"techCaliber\":null,\"businessCaliber\":\"b\"}");
        stubAuditLocks(draft);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(draft));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(buildTag(TAG_ID, 3));
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.submit(new Long[]{1L}));
        assertTrue(e.getMessage().contains("技术口径未完善"));
        verify(changeMapper, never()).updateChange(any());
    }

    /** 提交校验：草稿期间来源被再次同步（观测指纹变化）→ 申请过期拒绝 */
    @Test
    void submitSourceStaleRejected() {
        TlTagMetadataChange draft = buildChange(1L, TAG_ID, "DRAFT", USERNAME, 3);
        draft.setAfterJson("{\"tagName\":\"性别\",\"tagType\":\"选项型\",\"dirId\":100,"
                + "\"techCaliber\":\"t\",\"businessCaliber\":\"b\"}");
        draft.setSourceAfter(sourceSnapshotJson("varchar(8)"));
        stubAuditLocks(draft);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(draft));
        TlTag tag = buildTag(TAG_ID, 3);
        tag.setSourceFingerprint(DpSourceFingerprint.of(101L, "indiv_cust", "gender", "varchar(16)", "0"));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.submit(new Long[]{1L}));
        assertTrue(e.getMessage().contains("已过期"));
        verify(changeMapper, never()).updateChange(any());
    }

    /** 提交成功：本人 DRAFT 且版本一致、五项完整 → 置 PENDING 并写审计日志 */
    @Test
    void submitSuccess() {
        TlTagMetadataChange draft = buildChange(1L, TAG_ID, "DRAFT", USERNAME, 3);
        draft.setAfterJson("{\"tagName\":\"性别\",\"tagType\":\"选项型\",\"dirId\":100,"
                + "\"techCaliber\":\"t\",\"businessCaliber\":\"b\"}");
        stubAuditLocks(draft);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(draft));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(buildTag(TAG_ID, 3));
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));

        int submitted = mappingService.submit(new Long[]{1L});

        assertEquals(1, submitted);
        ArgumentCaptor<TlTagMetadataChange> changeCaptor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).updateChange(changeCaptor.capture());
        assertEquals("PENDING", changeCaptor.getValue().getStatus());
        assertNotNull(changeCaptor.getValue().getSubmitTime());
        ArgumentCaptor<TlAuditLog> logCaptor = ArgumentCaptor.forClass(TlAuditLog.class);
        verify(auditLogService).record(logCaptor.capture());
        TlAuditLog log = logCaptor.getValue();
        assertEquals("提交", log.getAction());
        assertEquals("DRAFT", log.getFromStatus());
        assertEquals("PENDING", log.getToStatus());
        assertEquals("tagMeta", log.getBizType());
    }

    /** 审批通过（METADATA）：tl_tag updateMetadataById 且 version=old+1，不置状态/来源，变更置 APPROVED */
    @Test
    void auditApproveSuccess() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
        pending.setChangeType("METADATA");
        pending.setAfterJson("{\"tagName\":\"新名称\",\"tagType\":\"数值型\",\"dirId\":100,"
                + "\"techCaliber\":\"t2\",\"businessCaliber\":\"b2\"}");
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));
        TlTag tag = buildTag(TAG_ID, 3);
        tag.setStatus("2");
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);

        int audited = mappingService.audit(new Long[]{1L}, true, "同意");

        assertEquals(1, audited);
        ArgumentCaptor<TlTag> tagCaptor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateMetadataById(tagCaptor.capture());
        TlTag update = tagCaptor.getValue();
        assertEquals(TAG_ID, update.getTagId());
        assertEquals(Integer.valueOf(4), update.getVersion());
        assertEquals("新名称", update.getTagName());
        assertEquals("数值型", update.getTagType());
        assertEquals(DIR_ID, update.getDirId());
        // METADATA 通过不动状态与来源（保持上线）
        assertNull(update.getStatus());
        assertNull(update.getConfirmedFingerprint());
        assertNull(update.getSourceStatus());
        ArgumentCaptor<TlTagMetadataChange> changeCaptor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).updateChange(changeCaptor.capture());
        assertEquals("APPROVED", changeCaptor.getValue().getStatus());
        assertEquals(USERNAME, changeCaptor.getValue().getAuditBy());
        assertEquals("同意", changeCaptor.getValue().getAuditComment());
        ArgumentCaptor<TlAuditLog> logCaptor = ArgumentCaptor.forClass(TlAuditLog.class);
        verify(auditLogService).record(logCaptor.capture());
        assertEquals("通过", logCaptor.getValue().getAction());
    }

    /** 审批通过（FIRST）：回写五字段 + 确认来源指纹 + 来源可用 + 状态 4→0 + version+1 */
    @Test
    void auditApproveFirstCreatesFormalTag() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 1);
        pending.setChangeType("FIRST");
        pending.setAfterJson("{\"tagName\":\"性别\",\"tagType\":\"选项型\",\"dirId\":100,"
                + "\"techCaliber\":\"t\",\"businessCaliber\":\"b\"}");
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));
        TlTag tag = buildTag(TAG_ID, 1);
        tag.setStatus("4");
        tag.setSourceFingerprint("fp-observed");
        tag.setSourceStatus("AVAILABLE");
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);

        mappingService.audit(new Long[]{1L}, true, null);

        ArgumentCaptor<TlTag> tagCaptor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateMetadataById(tagCaptor.capture());
        TlTag update = tagCaptor.getValue();
        assertEquals(Integer.valueOf(2), update.getVersion());
        assertEquals("0", update.getStatus());
        assertEquals("fp-observed", update.getConfirmedFingerprint());
        assertEquals("AVAILABLE", update.getSourceStatus());
    }

    /** 审批通过（SOURCE）：确认新来源指纹并恢复可用，上线状态保持原值（不置 status） */
    @Test
    void auditApproveSourceConfirmsNewSource() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
        pending.setChangeType("SOURCE");
        pending.setAfterJson("{\"tagName\":\"性别\",\"tagType\":\"选项型\",\"dirId\":100,"
                + "\"techCaliber\":\"t\",\"businessCaliber\":\"b\"}");
        pending.setSourceAfter(sourceSnapshotJson("varchar(16)"));
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));
        TlTag tag = buildTag(TAG_ID, 3);
        tag.setStatus("2");
        tag.setSourceStatus("CHANGED");
        tag.setSourceFingerprint(DpSourceFingerprint.of(101L, "indiv_cust", "gender", "varchar(16)", "0"));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);

        mappingService.audit(new Long[]{1L}, true, "确认新来源");

        ArgumentCaptor<TlTag> tagCaptor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateMetadataById(tagCaptor.capture());
        TlTag update = tagCaptor.getValue();
        assertEquals(Integer.valueOf(4), update.getVersion());
        assertNull(update.getStatus());
        assertEquals(tag.getSourceFingerprint(), update.getConfirmedFingerprint());
        assertEquals("AVAILABLE", update.getSourceStatus());
    }

    /** 来源过期：审核期间又同步/切版本 → 禁止通过 */
    @Test
    void auditApproveSourceStaleRejected() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
        pending.setChangeType("SOURCE");
        pending.setAfterJson("{\"tagName\":\"性别\",\"tagType\":\"选项型\",\"dirId\":100,"
                + "\"techCaliber\":\"t\",\"businessCaliber\":\"b\"}");
        pending.setSourceAfter(sourceSnapshotJson("varchar(16)"));
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));
        TlTag tag = buildTag(TAG_ID, 3);
        tag.setSourceFingerprint(DpSourceFingerprint.of(101L, "indiv_cust", "gender", "varchar(32)", "0"));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.audit(new Long[]{1L}, true, null));
        assertTrue(e.getMessage().contains("已过期"));
        verify(tagMapper, never()).updateMetadataById(any());
        verify(changeMapper, never()).updateChange(any());
    }

    /** 来源过期：允许驳回（仅改记录状态，不回写标签） */
    @Test
    void auditRejectStaleAllowed() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
        pending.setChangeType("SOURCE");
        pending.setAfterJson("{\"tagName\":\"性别\",\"tagType\":\"选项型\",\"dirId\":100,"
                + "\"techCaliber\":\"t\",\"businessCaliber\":\"b\"}");
        pending.setSourceAfter(sourceSnapshotJson("varchar(16)"));
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));
        TlTag tag = buildTag(TAG_ID, 3);
        tag.setSourceFingerprint(DpSourceFingerprint.of(101L, "indiv_cust", "gender", "varchar(32)", "0"));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);

        int audited = mappingService.audit(new Long[]{1L}, false, "来源已变化");

        assertEquals(1, audited);
        verify(tagMapper, never()).updateMetadataById(any());
        ArgumentCaptor<TlTagMetadataChange> changeCaptor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).updateChange(changeCaptor.capture());
        assertEquals("REJECTED", changeCaptor.getValue().getStatus());
    }

    /** 审批驳回：tl_tag 的 updateMetadataById 不被调用，变更置 REJECTED */
    @Test
    void auditRejectSuccess() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(buildTag(TAG_ID, 3));

        int audited = mappingService.audit(new Long[]{1L}, false, "口径不明确");

        assertEquals(1, audited);
        verify(tagMapper, never()).updateMetadataById(any());
        ArgumentCaptor<TlTagMetadataChange> changeCaptor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).updateChange(changeCaptor.capture());
        assertEquals("REJECTED", changeCaptor.getValue().getStatus());
        ArgumentCaptor<TlAuditLog> logCaptor = ArgumentCaptor.forClass(TlAuditLog.class);
        verify(auditLogService).record(logCaptor.capture());
        assertEquals("驳回", logCaptor.getValue().getAction());
    }

    /** 版本冲突整批回滚：一条 base_version≠tag.version → ServiceException，任何一条都未被更新 */
    @Test
    void auditVersionConflictRejectsWholeBatch() {
        TlTagMetadataChange c1 = buildChange(1L, 1L, "PENDING", USERNAME, 3);
        TlTagMetadataChange c2 = buildChange(2L, 2L, "PENDING", USERNAME, 3);
        stubAuditLocks(c1);
        when(changeMapper.selectByIdsForUpdate(anyList())).thenReturn(Arrays.asList(c1, c2));
        when(tagMapper.selectTagByIdForUpdate(1L)).thenReturn(buildTag(1L, 3));
        when(tagMapper.selectTagByIdForUpdate(2L)).thenReturn(buildTag(2L, 9));

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.audit(new Long[]{1L, 2L}, true, null));
        assertTrue(e.getMessage().contains("已被他人修改"));
        verify(tagMapper, never()).updateMetadataById(any());
        verify(changeMapper, never()).updateChange(any());
        verify(auditLogService, never()).record(any());
    }

    /** 撤回：本人 PENDING 申请撤回为 DRAFT 并写留痕 */
    @Test
    void withdrawOwnPendingSuccess() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));

        int withdrawn = mappingService.withdraw(new Long[]{1L});

        assertEquals(1, withdrawn);
        ArgumentCaptor<TlTagMetadataChange> changeCaptor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).updateChange(changeCaptor.capture());
        assertEquals("DRAFT", changeCaptor.getValue().getStatus());
        ArgumentCaptor<TlAuditLog> logCaptor = ArgumentCaptor.forClass(TlAuditLog.class);
        verify(auditLogService).record(logCaptor.capture());
        assertEquals("撤回", logCaptor.getValue().getAction());
        assertEquals("PENDING", logCaptor.getValue().getFromStatus());
        assertEquals("DRAFT", logCaptor.getValue().getToStatus());
    }

    /** 撤回：他人申请拒绝 */
    @Test
    void withdrawOthersRejected() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", "lisi", 3);
        stubAuditLocks(pending);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.withdraw(new Long[]{1L}));
        assertTrue(e.getMessage().contains("只能撤回本人"));
        verify(changeMapper, never()).updateChange(any());
    }

    // ---- 测试辅助 ----

    /** saveDraft 前置锁定桩：库行锁 peek（未锁查标签）+ 库行锁 + 标签行锁 */
    private void stubSaveDraftLocks(TlTag tag) {
        when(tagMapper.selectTagById(tag.getTagId())).thenReturn(tag);
        when(libraryMapper.selectLibraryByIdForUpdate(LIBRARY_ID)).thenReturn(new TlTagLibrary());
        when(tagMapper.selectTagByIdForUpdate(tag.getTagId())).thenReturn(tag);
    }

    /** submit/audit/withdraw 前置锁定桩：库行锁 peek（按变更记录）+ 库行锁 */
    private void stubAuditLocks(TlTagMetadataChange firstChange) {
        when(changeMapper.selectById(firstChange.getChangeId())).thenReturn(firstChange);
        when(libraryMapper.selectLibraryByIdForUpdate(LIBRARY_ID)).thenReturn(new TlTagLibrary());
    }

    /** 构造当前标签：五字段固定值，version 可调 */
    private TlTag buildTag(Long tagId, int version) {
        TlTag tag = new TlTag();
        tag.setTagId(tagId);
        tag.setLibraryId(LIBRARY_ID);
        tag.setDirId(DIR_ID);
        tag.setTagName("性别");
        tag.setTagType("选项型");
        tag.setTechCaliber("tech");
        tag.setBusinessCaliber("biz");
        tag.setVersion(version);
        tag.setDelFlag("0");
        return tag;
    }

    private MetadataChangeDTO buildItem(Long tagId, String tagName, String tagType, Long dirId,
                                        String techCaliber, String businessCaliber) {
        MetadataChangeDTO item = new MetadataChangeDTO();
        item.setTagId(tagId);
        item.setTagName(tagName);
        item.setTagType(tagType);
        item.setDirId(dirId);
        item.setTechCaliber(techCaliber);
        item.setBusinessCaliber(businessCaliber);
        item.setBaseVersion(3);
        return item;
    }

    private TlTagDir buildDir(Long dirId, Long libraryId) {
        TlTagDir dir = new TlTagDir();
        dir.setDirId(dirId);
        dir.setLibraryId(libraryId);
        return dir;
    }

    private TlTagMetadataChange buildChange(Long changeId, Long tagId, String status, String applyBy, int baseVersion) {
        TlTagMetadataChange change = new TlTagMetadataChange();
        change.setChangeId(changeId);
        change.setTagId(tagId);
        change.setLibraryId(LIBRARY_ID);
        change.setStatus(status);
        change.setApplyBy(applyBy);
        change.setBaseVersion(baseVersion);
        change.setBeforeJson("{}");
        change.setAfterJson("{}");
        return change;
    }

    /** 来源快照 JSON（指纹分量：数据源101/indiv_cust/gender/指定类型/非主键） */
    private String sourceSnapshotJson(String dataType) {
        JSONObject snapshot = new JSONObject();
        snapshot.put("datasourceId", 101L);
        snapshot.put("tableName", "indiv_cust");
        snapshot.put("columnName", "gender");
        snapshot.put("dataType", dataType);
        snapshot.put("isPk", "0");
        snapshot.put("fieldAlias", "gender");
        return snapshot.toJSONString();
    }
}
