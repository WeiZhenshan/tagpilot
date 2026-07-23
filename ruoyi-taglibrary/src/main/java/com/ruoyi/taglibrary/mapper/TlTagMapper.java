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
    int updateTagStatusBatch(@Param("ids") Long[] ids, @Param("status") String status);

    /** 批量移动标签到其他目录 */
    int moveTagBatch(@Param("ids") Long[] ids, @Param("dirId") Long dirId);

    /** 按标签库逻辑删除标签（级联删除用，del_flag='2'） */
    int deleteTagByLibraryIds(Long[] libraryIds);

    /** 统计库内已上线标签数（删除校验用） */
    int countOnlineByLibraryId(Long libraryId);
}
