package com.ruoyi.databroker.mapper;

import java.util.List;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;

public interface DpDataSourceCatalogMapper {
    List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog);
    DpDataSourceCatalog selectCatalogById(Long catalogId);
    int insertCatalog(DpDataSourceCatalog catalog);
    int updateCatalog(DpDataSourceCatalog catalog);
    int deleteCatalogById(Long catalogId);

    /** 查询某父目录下的直接子目录数量（用于删除/新增校验） */
    int hasChildByParentId(Long parentId);

    /** 查询某目录的所有子孙（ancestors 中含 catalogId） */
    List<DpDataSourceCatalog> selectChildrenById(Long catalogId);

    /** 批量更新子孙目录的 ancestors（父级变更时级联） */
    int updateChildren(List<DpDataSourceCatalog> catalogs);
}
