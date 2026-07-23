package com.ruoyi.taglibrary.service;

import java.util.List;
import com.ruoyi.taglibrary.domain.TlTagDir;

/**
 * 标签目录Service接口
 *
 * @author ruoyi
 */
public interface ITlTagDirService {

    List<TlTagDir> selectDirList(Long libraryId);

    int insertDir(TlTagDir dir);

    int updateDir(TlTagDir dir);

    /** 删除目录（目录下存在标签时拒绝） */
    int deleteDirById(Long dirId);
}
