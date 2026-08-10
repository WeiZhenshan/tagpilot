package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TlTagMetadataChange;

public interface TlTagMetadataChangeMapper {

    int insertChange(TlTagMetadataChange change);

    /** 按ID更新（草稿刷新/提交/审核共用，动态列） */
    int updateChange(TlTagMetadataChange change);

    TlTagMetadataChange selectById(Long changeId);

    /** 查某标签指定状态（如 DRAFT/PENDING）的变更记录 */
    List<TlTagMetadataChange> selectByTagIdAndStatusIn(@Param("tagId") Long tagId, @Param("statuses") List<String> statuses);

    /** 批量查多个标签指定状态的变更记录（列表合并用） */
    List<TlTagMetadataChange> selectByTagIdsAndStatusIn(@Param("tagIds") List<Long> tagIds, @Param("statuses") List<String> statuses);

    /** 批量查当前用户对指定标签集的草稿（ownDraft 标记用） */
    List<TlTagMetadataChange> selectDraftByTagIdsAndCreator(@Param("tagIds") List<Long> tagIds, @Param("creator") String creator);

    /** 按ID批量行锁查询（提交/审核并发控制用，按 change_id 排序锁定） */
    List<TlTagMetadataChange> selectByIdsForUpdate(@Param("changeIds") List<Long> changeIds);

    /** 待审核变更分页列表（联标签/标签库取展示名） */
    List<TlTagMetadataChange> selectAuditList(TlTagMetadataChange query);

    /** 删除草稿 */
    int deleteById(Long changeId);
}
