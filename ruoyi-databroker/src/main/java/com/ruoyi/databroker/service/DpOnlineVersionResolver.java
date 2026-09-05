package com.ruoyi.databroker.service;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.databroker.domain.vo.DpResolvedField;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.mapper.DpDatasetFieldMapper;
import com.ruoyi.databroker.mapper.DpDatasetVersionMapper;

/**
 * 数据集在线版本共用解析服务。
 * 解析规则：默认 ONLINE 版本优先；默认版本为空或已下线时，回退取版本号最大的 ONLINE 版本。
 * 标签同步与对象群查询统一经此处解析，消除重复 SQL；解析失败（数据集不存在或无在线版本）返回 null，由调用方报错。
 *
 * @author ruoyi
 */
@Service
public class DpOnlineVersionResolver {

    /** 选择原因：默认在线版本 */
    public static final String REASON_DEFAULT = "默认在线版本";

    /** 选择原因：默认版本不可用回退 */
    public static final String REASON_FALLBACK = "默认版本不可用，回退至最大版本号在线版本";

    @Autowired
    private DpDatasetVersionMapper versionMapper;
    @Autowired
    private DpDatasetFieldMapper fieldMapper;

    /** 解析数据集当前在线版本（含选择原因），无在线版本或数据集不存在返回 null */
    public DpResolvedVersion resolve(Long datasetId) {
        if (datasetId == null) {
            return null;
        }
        DpResolvedVersion version = versionMapper.selectResolvedOnlineVersion(datasetId);
        if (version == null) {
            return null;
        }
        version.setReason(Boolean.TRUE.equals(version.getIsDefault()) ? REASON_DEFAULT : REASON_FALLBACK);
        return version;
    }

    /** 查询指定版本的启用输出字段（含来源表/列快照信息，按 order_num 排序） */
    public List<DpResolvedField> listEnabledFields(Long versionId) {
        return fieldMapper.selectEnabledResolvedFields(versionId);
    }
}
