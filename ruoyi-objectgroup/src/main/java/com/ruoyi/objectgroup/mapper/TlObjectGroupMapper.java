package com.ruoyi.objectgroup.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.objectgroup.domain.TlObjectGroup;

public interface TlObjectGroupMapper {

    List<TlObjectGroup> selectObjectGroupList(TlObjectGroup query);

    TlObjectGroup selectObjectGroupById(Long groupId);

    int insertObjectGroup(TlObjectGroup group);

    int updateObjectGroup(TlObjectGroup group);

    int deleteObjectGroupByIds(Long[] groupIds);

    /** 更新用户数（运行结果回写） */
    int updateUserCount(@Param("groupId") Long groupId, @Param("userCount") Long userCount);

    /** 统计关联某标签库且未删除的对象群数量（删除标签库前阻断校验） */
    int countActiveByLibraryId(Long libraryId);
}
