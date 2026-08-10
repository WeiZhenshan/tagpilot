package com.ruoyi.databroker.service;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataset;
import com.ruoyi.databroker.domain.DpDatasetLog;
import com.ruoyi.databroker.domain.DpDatasetVersion;
import com.ruoyi.databroker.domain.DpMetaColumn;
import com.ruoyi.databroker.domain.DpMetaTable;
import com.ruoyi.databroker.domain.dto.CopyVersionRequest;
import com.ruoyi.databroker.domain.dto.PreviewRequest;
import com.ruoyi.databroker.domain.dto.PublishRequest;
import com.ruoyi.databroker.domain.dto.SaveDraftRequest;
import com.ruoyi.databroker.domain.dto.TreeNode;
import com.ruoyi.databroker.domain.vo.PreviewResultVO;

public interface IDpDatasetService {
    // Tree
    List<TreeNode> buildTree();

    // CRUD
    DpDataset selectDatasetById(Long datasetId);
    int insertDataset(DpDataset dataset);
    int updateDataset(DpDataset dataset);
    int deleteDatasetByIds(Long[] datasetIds);

    /** 更新数据集排序/所属目录（拖拽排序用） */
    int updateDatasetOrder(DpDataset dataset);

    // 版本
    List<DpDatasetVersion> selectVersionList(Long datasetId);
    DpDatasetVersion selectVersionDetail(Long versionId);
    DpDatasetVersion saveDraft(SaveDraftRequest request);
    DpDatasetVersion copyVersion(Long datasetId, CopyVersionRequest request);
    int publishVersion(Long versionId, PublishRequest request);
    int offlineVersion(Long versionId);

    /** 将已发布（ONLINE）版本设为默认版本 */
    int setDefaultVersion(Long versionId);

    // 数据预览
    PreviewResultVO preview(PreviewRequest request);

    // 透传元数据
    List<DpMetaTable> listTables(Long datasourceId, DpMetaTable query);
    List<DpMetaColumn> listColumns(Long tableId);

    // Logs
    List<DpDatasetLog> listLogs(Long datasetId, DpDatasetLog query);
}
