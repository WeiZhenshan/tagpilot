package com.ruoyi.objectgroup.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.objectgroup.domain.TlObjectGroup;

public interface TlObjectGroupMapper {

    List<TlObjectGroup> selectObjectGroupList(TlObjectGroup query);

    TlObjectGroup selectObjectGroupById(Long groupId);
    TlObjectGroup selectObjectGroupByIdForUpdate(Long groupId);

    /** 与索引激活共用库锁，必须先于客群行锁。 */
    Long lockLibrary(Long libraryId);

    /** 当前读：拒绝旧事务读视图/会话缓存中的发布绑定。 */
    java.util.List<java.util.Map<String, Object>> selectActiveBindingsForUpdate(Long libraryId);

    int insertObjectGroup(TlObjectGroup group);

    int updateObjectGroup(TlObjectGroup group);

    int deleteObjectGroupByIds(Long[] groupIds);

    /** 更新用户数（运行结果回写） */
    int updateUserCount(@Param("groupId") Long groupId, @Param("userCount") Long userCount);

    /** 统计关联某标签库且未删除的对象群数量（删除标签库前阻断校验） */
    int countActiveByLibraryId(Long libraryId);

    /**
     * 索引激活改绑用：锁定同库、未删除且规则文本中出现该快照号的对象群（粗筛，调用方须再按 audiencePlan.snapshot_id 精确判断）。
     * 须在激活事务内调用（FOR UPDATE），保证改绑与激活同提交、同回滚。
     */
    List<TlObjectGroup> selectPlanGroupsBySnapshotForUpdate(@Param("libraryId") Long libraryId, @Param("snapshotId") String snapshotId);
}
