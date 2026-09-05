package com.ruoyi.taglibrary.service;

import java.util.List;
import java.util.Map;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.domain.TlTagMetadataChange;
import com.ruoyi.taglibrary.domain.dto.MetadataChangeDTO;
import com.ruoyi.taglibrary.domain.vo.TagMappingVO;

/**
 * 标签元数据变更（批量映射）Service接口
 *
 * @author ruoyi
 */
public interface ITlTagMappingService {

    /** 批量映射分页列表（标签信息合并草稿/待审核状态） */
    List<TagMappingVO> selectMappingList(TlTag query);

    /** 批量保存草稿（整批原子，任一校验失败全部回滚；返回每条保存后的 changeId 与 revision） */
    List<MetadataChangeDTO> saveDraft(List<MetadataChangeDTO> items);

    /** 批量提交审核（仅本人草稿可提交；提交时强校验五项完整性与来源未漂移） */
    int submit(Long[] changeIds);

    /** 待审核变更分页列表（含变更字段摘要） */
    List<TlTagMetadataChange> selectAuditList(TlTagMetadataChange query);

    /** 批量审核（pass=true 通过并按变更类型回写 tl_tag，false 驳回；整批原子） */
    int audit(Long[] changeIds, boolean pass, String auditComment);

    /** 批量撤回（申请人将本人 PENDING 申请撤回为 DRAFT；整批原子） */
    int withdraw(Long[] changeIds);

    /** 变更差异详情（变更记录 + before/after 快照 + 标签当前值） */
    Map<String, Object> getChangeDetail(Long changeId);
}
