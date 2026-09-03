package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
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
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.TlAuditLog;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagMetadataChange;
import com.ruoyi.taglibrary.domain.dto.MetadataChangeDTO;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TlTagMetadataChangeMapper;

/**
 * 标签元数据变更（草稿/提交/审核）Service 单元测试（纯 Mockito，不起 Spring 上下文）
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
    private AuditLogService auditLogService;

    @InjectMocks
    private TlTagMappingServiceImpl mappingService;

    /** 草稿保存成功：insertChange 被调用，status=DRAFT，base_version=当前 version，快照仅含五字段 */
    @Test
    void saveDraftSuccess() {
        TlTag tag = buildTag(TAG_ID, 3);
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList())).thenReturn(new ArrayList<>());
        MetadataChangeDTO item = buildItem(TAG_ID, "新名称", "数值型", DIR_ID, "tech2", "biz2");

        int saved = mappingService.saveDraft(Collections.singletonList(item));

        assertEquals(1, saved);
        ArgumentCaptor<TlTagMetadataChange> captor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).insertChange(captor.capture());
        TlTagMetadataChange change = captor.getValue();
        assertEquals("DRAFT", change.getStatus());
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

    /** 校验失败：tagType 非法值 → ServiceException */
    @Test
    void saveDraftInvalidTagTypeRejected() {
        TlTag tag = buildTag(TAG_ID, 3);
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);
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
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, 99L));
        MetadataChangeDTO item = buildItem(TAG_ID, "名称", "选项型", DIR_ID, null, null);

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.saveDraft(Collections.singletonList(item)));
        assertTrue(e.getMessage().contains("不属于该标签库"));
        verify(changeMapper, never()).insertChange(any());
    }

    /** 无变化不建草稿：提交值与当前 tl_tag 完全一致且无已有草稿 → insertChange 不被调用 */
    @Test
    void saveDraftNoChangeNoInsert() {
        TlTag tag = buildTag(TAG_ID, 3);
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList())).thenReturn(new ArrayList<>());
        MetadataChangeDTO item = buildItem(TAG_ID, "性别", "选项型", DIR_ID, "tech", "biz");

        int saved = mappingService.saveDraft(Collections.singletonList(item));

        assertEquals(0, saved);
        verify(changeMapper, never()).insertChange(any());
        verify(changeMapper, never()).updateChange(any());
        verify(changeMapper, never()).deleteById(anyLong());
    }

    /** 无变化删草稿：提交值与当前一致但已有本人 DRAFT → deleteById 被调用 */
    @Test
    void saveDraftNoChangeDeletesOwnDraft() {
        TlTag tag = buildTag(TAG_ID, 3);
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);
        when(dirMapper.selectDirById(DIR_ID)).thenReturn(buildDir(DIR_ID, LIBRARY_ID));
        TlTagMetadataChange ownDraft = buildChange(5L, TAG_ID, "DRAFT", USERNAME, 3);
        when(changeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList()))
                .thenReturn(Collections.singletonList(ownDraft));
        MetadataChangeDTO item = buildItem(TAG_ID, "性别", "选项型", DIR_ID, "tech", "biz");

        int saved = mappingService.saveDraft(Collections.singletonList(item));

        assertEquals(0, saved);
        verify(changeMapper).deleteById(5L);
        verify(changeMapper, never()).insertChange(any());
        verify(changeMapper, never()).updateChange(any());
    }

    /** 他人草稿不可改：该标签已有 apply_by=他人的 DRAFT → ServiceException */
    @Test
    void saveDraftOthersDraftRejected() {
        TlTag tag = buildTag(TAG_ID, 3);
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(tag);
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
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));

        ServiceException e = assertThrows(ServiceException.class,
                () -> mappingService.submit(new Long[]{1L}));
        assertTrue(e.getMessage().contains("不是草稿状态"));
        verify(changeMapper, never()).updateChange(any());
        verify(auditLogService, never()).record(any());
    }

    /** 提交成功：本人 DRAFT 且版本一致 → 置 PENDING 并写审计日志 */
    @Test
    void submitSuccess() {
        TlTagMetadataChange draft = buildChange(1L, TAG_ID, "DRAFT", USERNAME, 3);
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(draft));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(buildTag(TAG_ID, 3));

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

    /** 审批通过：PENDING + 版本一致 → tl_tag updateMetadataById 且 version=old+1，变更置 APPROVED */
    @Test
    void auditApproveSuccess() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
        pending.setAfterJson("{\"tagName\":\"新名称\",\"tagType\":\"数值型\",\"dirId\":100,"
                + "\"techCaliber\":\"t2\",\"businessCaliber\":\"b2\"}");
        when(changeMapper.selectByIdsForUpdate(anyList()))
                .thenReturn(Collections.singletonList(pending));
        when(tagMapper.selectTagByIdForUpdate(TAG_ID)).thenReturn(buildTag(TAG_ID, 3));

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
        ArgumentCaptor<TlTagMetadataChange> changeCaptor = ArgumentCaptor.forClass(TlTagMetadataChange.class);
        verify(changeMapper).updateChange(changeCaptor.capture());
        assertEquals("APPROVED", changeCaptor.getValue().getStatus());
        assertEquals(USERNAME, changeCaptor.getValue().getAuditBy());
        assertEquals("同意", changeCaptor.getValue().getAuditComment());
        ArgumentCaptor<TlAuditLog> logCaptor = ArgumentCaptor.forClass(TlAuditLog.class);
        verify(auditLogService).record(logCaptor.capture());
        assertEquals("通过", logCaptor.getValue().getAction());
    }

    /** 审批驳回：tl_tag 的 updateMetadataById 不被调用，变更置 REJECTED */
    @Test
    void auditRejectSuccess() {
        TlTagMetadataChange pending = buildChange(1L, TAG_ID, "PENDING", USERNAME, 3);
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

    // ---- 测试辅助 ----

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
}
