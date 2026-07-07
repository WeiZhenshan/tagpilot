package com.ruoyi.databroker.service.impl;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.constant.UserConstants;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.StringUtils;
import com.ruoyi.databroker.domain.DpDataSourceCatalog;
import com.ruoyi.databroker.mapper.DpDataSourceCatalogMapper;
import com.ruoyi.databroker.mapper.DpDataSourceMapper;
import com.ruoyi.databroker.service.IDpDataSourceCatalogService;

@Service
public class DpDataSourceCatalogServiceImpl implements IDpDataSourceCatalogService {

    @Autowired
    private DpDataSourceCatalogMapper catalogMapper;
    @Autowired
    private DpDataSourceMapper dataSourceMapper;

    @Override
    public List<DpDataSourceCatalog> selectCatalogList(DpDataSourceCatalog catalog) {
        return catalogMapper.selectCatalogList(catalog);
    }

    @Override
    public DpDataSourceCatalog selectCatalogById(Long catalogId) {
        return catalogMapper.selectCatalogById(catalogId);
    }

    /**
     * 新增目录：根据父目录计算 ancestors 祖先链。
     * 父目录为空或 0 表示根目录，ancestors 设为 "0"；否则 ancestors = 父ancestors + "," + parentId。
     */
    @Override
    public int insertCatalog(DpDataSourceCatalog catalog) {
        if (catalog.getParentId() == null || catalog.getParentId() == 0L) {
            catalog.setParentId(0L);
            catalog.setAncestors("0");
        } else {
            DpDataSourceCatalog parent = catalogMapper.selectCatalogById(catalog.getParentId());
            if (parent == null) {
                throw new ServiceException("父目录不存在");
            }
            if (UserConstants.DEPT_DISABLE.equals(parent.getStatus())) {
                throw new ServiceException("父目录停用，不允许新增子目录");
            }
            catalog.setAncestors(parent.getAncestors() + "," + catalog.getParentId());
        }
        return catalogMapper.insertCatalog(catalog);
    }

    /**
     * 修改目录：父级变更时重算 ancestors，并级联更新所有子孙目录的 ancestors 前缀。
     */
    @Override
    public int updateCatalog(DpDataSourceCatalog catalog) {
        DpDataSourceCatalog newParent = catalog.getParentId() == null || catalog.getParentId() == 0L
            ? null : catalogMapper.selectCatalogById(catalog.getParentId());
        DpDataSourceCatalog oldCatalog = catalogMapper.selectCatalogById(catalog.getCatalogId());
        if (StringUtils.isNotNull(newParent) && StringUtils.isNotNull(oldCatalog)) {
            String newAncestors = newParent.getAncestors() + "," + newParent.getCatalogId();
            String oldAncestors = oldCatalog.getAncestors();
            catalog.setAncestors(newAncestors);
            updateCatalogChildren(catalog.getCatalogId(), newAncestors, oldAncestors);
        } else if (oldCatalog != null && (catalog.getParentId() == null || catalog.getParentId() == 0L)) {
            // 父级改为根
            String oldAncestors = oldCatalog.getAncestors();
            catalog.setAncestors("0");
            updateCatalogChildren(catalog.getCatalogId(), "0", oldAncestors);
        }
        return catalogMapper.updateCatalog(catalog);
    }

    /**
     * 级联更新子孙目录的 ancestors：将旧前缀替换为新前缀。
     */
    private void updateCatalogChildren(Long catalogId, String newAncestors, String oldAncestors) {
        List<DpDataSourceCatalog> children = catalogMapper.selectChildrenById(catalogId);
        for (DpDataSourceCatalog child : children) {
            child.setAncestors(child.getAncestors().replaceFirst(oldAncestors, newAncestors));
        }
        if (children.size() > 0) {
            catalogMapper.updateChildren(children);
        }
    }

    /**
     * 删除目录：删除前校验是否存在子目录或该目录下的数据源。
     */
    @Override
    public int deleteCatalogById(Long catalogId) {
        if (catalogMapper.hasChildByParentId(catalogId) > 0) {
            throw new ServiceException("该目录下存在子目录，不允许删除");
        }
        if (dataSourceMapper.countByCatalogId(catalogId) > 0) {
            throw new ServiceException("该目录下存在数据源，不允许删除");
        }
        return catalogMapper.deleteCatalogById(catalogId);
    }
}
