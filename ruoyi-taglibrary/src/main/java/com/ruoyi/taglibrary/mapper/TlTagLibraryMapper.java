package com.ruoyi.taglibrary.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.taglibrary.domain.TlTagLibrary;
import com.ruoyi.taglibrary.domain.vo.DatasetFieldVO;
import com.ruoyi.taglibrary.domain.vo.DatasetVO;

public interface TlTagLibraryMapper {
    /** 标签库列表（联表统计标签数量） */
    List<TlTagLibrary> selectLibraryList(TlTagLibrary query);

    TlTagLibrary selectLibraryById(Long libraryId);

    TlTagLibrary selectLibraryByCode(String libraryCode);

    int insertLibrary(TlTagLibrary library);

    int updateLibrary(TlTagLibrary library);

    /** 逻辑删除（del_flag 写主键ID，避开 uk(library_code, del_flag) 复合唯一键冲突） */
    int deleteLibraryByIds(Long[] libraryIds);

    /** 状态机流转（草稿/待审批/已上线/已下线） */
    int updateLibraryStatus(@Param("id") Long id, @Param("status") String status, @Param("updateBy") String updateBy);

    /** 已上线数据集列表（默认版本 ONLINE，新建弹窗选用） */
    List<DatasetVO> selectOnlineDatasets();

    /** 数据集默认在线版本ID，未上线返回 null */
    Long selectOnlineVersionId(Long datasetId);

    /** 数据集指定版本的启用输出字段（按 order_num 排序） */
    List<DatasetFieldVO> selectDatasetFields(Long versionId);
}
