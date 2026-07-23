package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDatasetCatalog;

public interface DpDatasetCatalogMapper {
    List<DpDatasetCatalog> selectCatalogList(DpDatasetCatalog catalog);
    DpDatasetCatalog selectCatalogById(Long catalogId);
    int insertCatalog(DpDatasetCatalog catalog);
    int updateCatalog(DpDatasetCatalog catalog);
    int deleteCatalogById(Long catalogId);

    /** 查询某父目录下的直接子目录数量（用于删除/新增校验） */
    int hasChildByParentId(Long parentId);

    /** 查询某目录的所有子孙（ancestors 中含 catalogId） */
    List<DpDatasetCatalog> selectChildrenById(Long catalogId);

    /** 批量更新子孙目录的 ancestors（父级变更时级联） */
    int updateChildren(List<DpDatasetCatalog> catalogs);

    /** 更新目录排序（拖拽排序用） */
    int updateCatalogOrder(DpDatasetCatalog catalog);
}
