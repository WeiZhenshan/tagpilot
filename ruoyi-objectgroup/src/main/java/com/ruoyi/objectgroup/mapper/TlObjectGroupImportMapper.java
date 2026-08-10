package com.ruoyi.objectgroup.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.objectgroup.domain.TlObjectGroupImport;

public interface TlObjectGroupImportMapper {

    int insertBatch(List<TlObjectGroupImport> imports);

    /** 按批次取全部值 */
    List<String> selectValuesByBatch(@Param("importBatch") String importBatch);

    /** 保存对象群后回填归属 */
    int bindGroup(@Param("importBatch") String importBatch, @Param("groupId") Long groupId);

    /** 删除对象群时级联删导入值 */
    int deleteByGroupId(Long groupId);
}
