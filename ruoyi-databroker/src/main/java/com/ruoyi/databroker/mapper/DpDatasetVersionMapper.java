package com.ruoyi.databroker.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.databroker.domain.DpDatasetVersion;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;

public interface DpDatasetVersionMapper {
    /** 版本列表（不含 definition_json） */
    List<DpDatasetVersion> selectVersionListByDatasetId(Long datasetId);
    DpDatasetVersion selectVersionById(Long versionId);

    /** 查询数据集的草稿版本（至多一个） */
    DpDatasetVersion selectDraftByDatasetId(Long datasetId);

    /** 统计数据集的草稿版本数量（复制版本前置校验） */
    int countDraftByDatasetId(Long datasetId);

    /** 查询数据集最新的 ONLINE 版本 ID，可排除指定版本 */
    Long selectLatestOnlineVersionId(@Param("datasetId") Long datasetId,
                                     @Param("excludeVersionId") Long excludeVersionId);

    /** 解析在线版本（默认版本在线优先，否则版本号最大），无在线版本或数据集不可用返回 null */
    DpResolvedVersion selectResolvedOnlineVersion(Long datasetId);

    int insertVersion(DpDatasetVersion version);
    int updateVersion(DpDatasetVersion version);
}
