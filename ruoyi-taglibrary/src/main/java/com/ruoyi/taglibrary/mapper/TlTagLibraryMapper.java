package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.vo.MetaColumnVO;

public interface TlTagLibraryMapper {
    /** 标签库列表（联表统计标签数量） */
    List<TlTagLibrary> selectLibraryList(TlTagLibrary query);

    TlTagLibrary selectLibraryById(Long libraryId);

    TlTagLibrary selectLibraryByCode(String libraryCode);

    int insertLibrary(TlTagLibrary library);

    int updateLibrary(TlTagLibrary library);

    /** 逻辑删除（del_flag='2'） */
    int deleteLibraryByIds(Long[] libraryIds);

    /** 状态机流转（草稿/待审批/已上线/已下线） */
    int updateLibraryStatus(@Param("id") Long id, @Param("status") String status, @Param("updateBy") String updateBy);

    /** 查询源表字段元数据（information_schema.columns） */
    List<MetaColumnVO> selectTableColumns(String tableName);

    /** 可选业务表列表（排除系统表，新建弹窗选表用） */
    List<String> selectBusinessTables();
}
