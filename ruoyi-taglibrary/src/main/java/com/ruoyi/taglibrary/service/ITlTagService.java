package com.ruoyi.taglibrary.service;

import java.util.List;
import java.util.Map;
import com.ruoyi.taglibrary.domain.TlTag;

/**
 * 标签Service接口
 *
 * @author ruoyi
 */
public interface ITlTagService {

    List<TlTag> selectTagList(TlTag query);

    TlTag selectTagById(Long tagId);

    /** 标签管理页左侧树（tab=online 已上线 / offline 未上线） */
    List<Map<String, Object>> buildTree(Long libraryId, String tab);

    /** 编辑标签（version+1，fieldName/dataType 不可改） */
    int updateTag(TlTag tag);

    /** 批量移动目录 */
    int moveTag(Long[] tagIds, Long dirId);

    /** 批量提交审批（草稿/已下线→待审批） */
    int submit(Long[] tagIds);

    /** 批量审批（通过→已上线 / 驳回→草稿） */
    int audit(Long[] tagIds, boolean pass, String auditComment);

    /** 批量下线（已上线→已下线） */
    int offline(Long[] tagIds);
}
