package com.ruoyi.taglibrary.service.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.domain.TlTagMetadataChange;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.mapper.TlTagLibraryMapper;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.taglibrary.mapper.TlTagMetadataChangeMapper;

/**
 * 标签管理 Service 单元测试：旁路封堵（编辑/移动目录）、status=4 状态机拦截、双阶段互斥、列表排除待完善
 *
 * @author ruoyi
 */
@ExtendWith(MockitoExtension.class)
class TlTagServiceImplTest extends BaseServiceTest {

    private static final Long TAG_ID = 1L;
    private static final Long LIBRARY_ID = 10L;
    private static final Long DIR_ID = 100L;

    @Mock
    private TlTagMapper tagMapper;
    @Mock
    private TlTagDirMapper dirMapper;
    @Mock
    private TlTagLibraryMapper libraryMapper;
    @Mock
    private TlTagMetadataChangeMapper metadataChangeMapper;
    @Mock
    private AuditLogService auditLogService;

    @InjectMocks
    private TlTagServiceImpl tagService;

    /** 同步建档标签直接改名称 → 拒绝走元数据变更流程 */
    @Test
    void updateTagSyncedMetadataChangeRejected() {
        TlTag old = buildTag("同步", "0");
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(old);
        TlTag input = new TlTag();
        input.setTagId(TAG_ID);
        input.setTagName("新名称");

        ServiceException e = assertThrows(ServiceException.class, () -> tagService.updateTag(input));
        assertTrue(e.getMessage().contains("元数据变更流程"));
        verify(tagMapper, never()).updateTag(any());
    }

    /** 同步建档标签仅改非元数据字段（有效日期）→ 允许 */
    @Test
    void updateTagSyncedNonMetadataAllowed() {
        TlTag old = buildTag("同步", "0");
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(old);
        when(tagMapper.updateTag(any(TlTag.class))).thenReturn(1);
        TlTag input = new TlTag();
        input.setTagId(TAG_ID);
        input.setValidPeriod("2026-12-31");

        int rows = tagService.updateTag(input);

        assertEquals(1, rows);
        ArgumentCaptor<TlTag> captor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).updateTag(captor.capture());
        assertEquals("2026-12-31", captor.getValue().getValidPeriod());
    }

    /** 自建标签改名称 → 保持现状允许 */
    @Test
    void updateTagSelfBuiltMetadataAllowed() {
        TlTag old = buildTag("自建", "0");
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(old);
        when(tagMapper.updateTag(any(TlTag.class))).thenReturn(1);
        TlTag input = new TlTag();
        input.setTagId(TAG_ID);
        input.setTagName("新名称");

        assertEquals(1, tagService.updateTag(input));
        verify(tagMapper).updateTag(any(TlTag.class));
    }

    /** 同步建档标签直接移动目录 → 拒绝 */
    @Test
    void moveTagSyncedRejected() {
        TlTag tag = buildTag("同步", "0");
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(tag);
        when(dirMapper.selectDirById(200L)).thenReturn(buildDir(200L));

        ServiceException e = assertThrows(ServiceException.class,
                () -> tagService.moveTag(new Long[]{TAG_ID}, 200L));
        assertTrue(e.getMessage().contains("元数据变更流程"));
        verify(tagMapper, never()).moveTagBatch(any(), any(), any());
    }

    /** 自建标签移动目录 → 保持现状允许 */
    @Test
    void moveTagSelfBuiltAllowed() {
        TlTag tag = buildTag("自建", "0");
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(tag);
        when(dirMapper.selectDirById(200L)).thenReturn(buildDir(200L));
        when(tagMapper.moveTagBatch(any(), eq(200L), eq(USERNAME))).thenReturn(1);

        assertEquals(1, tagService.moveTag(new Long[]{TAG_ID}, 200L));
        verify(tagMapper).moveTagBatch(any(), eq(200L), eq(USERNAME));
    }

    /** status=4 待完善标签提交上线 → 明确拒绝 */
    @Test
    void submitIncompleteTagRejected() {
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(buildTag("同步", "4"));

        ServiceException e = assertThrows(ServiceException.class,
                () -> tagService.submit(new Long[]{TAG_ID}));
        assertTrue(e.getMessage().contains("待完善标签需先通过元数据审核"));
        verify(tagMapper, never()).updateTagStatusBatch(any(), any(), any());
    }

    /** status=4 待完善标签上线审批/下线 → 明确拒绝 */
    @Test
    void auditAndOfflineIncompleteTagRejected() {
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(buildTag("同步", "4"));

        ServiceException e1 = assertThrows(ServiceException.class,
                () -> tagService.audit(new Long[]{TAG_ID}, true, null));
        assertTrue(e1.getMessage().contains("待完善标签需先通过元数据审核"));
        ServiceException e2 = assertThrows(ServiceException.class,
                () -> tagService.offline(new Long[]{TAG_ID}));
        assertTrue(e2.getMessage().contains("待完善标签需先通过元数据审核"));
        verify(tagMapper, never()).updateTagStatusBatch(any(), any(), any());
    }

    /** 存在待审核元数据申请（PENDING）的标签不能提交上线审核（双阶段互斥） */
    @Test
    void submitWithPendingMetadataChangeRejected() {
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(buildTag("同步", "0"));
        TlTagMetadataChange pending = new TlTagMetadataChange();
        pending.setChangeId(5L);
        when(metadataChangeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList()))
                .thenReturn(Collections.singletonList(pending));

        ServiceException e = assertThrows(ServiceException.class,
                () -> tagService.submit(new Long[]{TAG_ID}));
        assertTrue(e.getMessage().contains("待审核的元数据申请"));
        verify(tagMapper, never()).updateTagStatusBatch(any(), any(), any());
        // 必须以变更申请的状态值域（PENDING）查询，而非标签状态值域（1）
        ArgumentCaptor<List<String>> statusCaptor = ArgumentCaptor.forClass(List.class);
        verify(metadataChangeMapper).selectByTagIdAndStatusIn(eq(TAG_ID), statusCaptor.capture());
        assertTrue(statusCaptor.getValue().contains("PENDING"),
                "应查询变更状态 PENDING，实际：" + statusCaptor.getValue());
    }

    /** 正常提交上线：草稿状态且无元数据申请 → 置待审批并留痕 */
    @Test
    void submitSuccess() {
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(buildTag("同步", "0"));
        when(metadataChangeMapper.selectByTagIdAndStatusIn(eq(TAG_ID), anyList()))
                .thenReturn(Collections.emptyList());
        when(tagMapper.updateTagStatusBatch(any(), eq("1"), eq(USERNAME))).thenReturn(1);

        assertEquals(1, tagService.submit(new Long[]{TAG_ID}));
        verify(tagMapper).updateTagStatusBatch(any(), eq("1"), eq(USERNAME));
        verify(auditLogService).record(any());
    }

    /** 详情：status=4 拒绝查看（引导至批量映射） */
    @Test
    void getInfoIncompleteTagRejected() {
        when(tagMapper.selectTagById(TAG_ID)).thenReturn(buildTag("同步", "4"));

        ServiceException e = assertThrows(ServiceException.class, () -> tagService.selectTagById(TAG_ID));
        assertTrue(e.getMessage().contains("批量映射"));
    }

    /** 列表：查询条件强制排除待完善标签 */
    @Test
    void listExcludesIncomplete() {
        TlTag query = new TlTag();
        query.setLibraryId(LIBRARY_ID);
        when(tagMapper.selectTagList(any(TlTag.class))).thenReturn(Collections.emptyList());

        tagService.selectTagList(query);

        ArgumentCaptor<TlTag> captor = ArgumentCaptor.forClass(TlTag.class);
        verify(tagMapper).selectTagList(captor.capture());
        assertEquals(Boolean.TRUE, captor.getValue().getExcludeIncomplete());
    }

    // ---- 测试辅助 ----

    private TlTag buildTag(String createWay, String status) {
        TlTag tag = new TlTag();
        tag.setTagId(TAG_ID);
        tag.setLibraryId(LIBRARY_ID);
        tag.setDirId(DIR_ID);
        tag.setTagName("性别");
        tag.setTagType("选项型");
        tag.setTechCaliber("tech");
        tag.setBusinessCaliber("biz");
        tag.setCreateWay(createWay);
        tag.setStatus(status);
        tag.setVersion(1);
        tag.setDelFlag("0");
        return tag;
    }

    private TlTagDir buildDir(Long dirId) {
        TlTagDir dir = new TlTagDir();
        dir.setDirId(dirId);
        dir.setLibraryId(LIBRARY_ID);
        return dir;
    }
}
