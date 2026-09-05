package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TlTag;

public interface TlTagMapper {
    List<TlTag> selectTagList(TlTag query);

    TlTag selectTagById(Long tagId);

    TlTag selectTagByFieldName(@Param("libraryId") Long libraryId, @Param("fieldName") String fieldName);

    int insertTag(TlTag tag);

    int insertTagBatch(List<TlTag> tags);

    int updateTag(TlTag tag);

    /** 批量更新标签状态（提交/审批/下线） */
    int updateTagStatusBatch(@Param("ids") Long[] ids, @Param("status") String status, @Param("updateBy") String updateBy);

    /** 批量移动标签到其他目录 */
    int moveTagBatch(@Param("ids") Long[] ids, @Param("dirId") Long dirId, @Param("updateBy") String updateBy);

    /** 按标签库逻辑删除标签（级联删除用，del_flag 写主键ID，避开复合唯一键冲突） */
    int deleteTagByLibraryIds(Long[] libraryIds);

    /** 同步对账刷新来源观测（来源版本/快照/指纹/状态 + is_object_key 补写），不动五项人工元数据与 version */
    int updateSourceById(TlTag tag);

    /** 批量标记来源状态（字段消失/停用时置 MISSING） */
    int updateSourceStatusBatch(@Param("ids") Long[] ids, @Param("sourceStatus") String sourceStatus,
                                @Param("updateBy") String updateBy);

    /** 统计库内已上线标签数（删除校验用） */
    int countOnlineByLibraryId(Long libraryId);

    /** 行锁查询标签（元数据变更草稿/提交/审核并发控制用） */
    TlTag selectTagByIdForUpdate(Long tagId);

    /** 元数据变更审核通过后回写五个可改字段，version 由 service 传入（旧值+1），status 不变 */
    int updateMetadataById(TlTag tag);
}
