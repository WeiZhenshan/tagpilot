package com.ruoyi.taglibrary.service.impl;

import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.taglibrary.domain.TlTagDir;
import com.ruoyi.taglibrary.mapper.TlTagDirMapper;
import com.ruoyi.taglibrary.service.ITlTagDirService;

/**
 * 标签目录Service业务层处理
 *
 * @author ruoyi
 */
@Service
public class TlTagDirServiceImpl implements ITlTagDirService {

    @Autowired
    private TlTagDirMapper dirMapper;

    @Override
    public List<TlTagDir> selectDirList(Long libraryId) {
        return dirMapper.selectDirList(libraryId);
    }

    @Override
    public int insertDir(TlTagDir dir) {
        dir.setCreateBy(SecurityUtils.getUsername());
        return dirMapper.insertDir(dir);
    }

    @Override
    public int updateDir(TlTagDir dir) {
        // 不允许修改所属标签库
        dir.setLibraryId(null);
        dir.setUpdateBy(SecurityUtils.getUsername());
        return dirMapper.updateDir(dir);
    }

    @Override
    public int deleteDirById(Long dirId) {
        if (dirMapper.countTagByDirId(dirId) > 0) {
            throw new ServiceException("目录下存在标签，不能删除");
        }
        return dirMapper.deleteDirById(dirId);
    }
}
