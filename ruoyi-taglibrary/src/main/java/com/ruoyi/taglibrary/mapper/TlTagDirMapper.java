package com.ruoyi.taglibrary.mapper;

import java.util.List;
import com.ruoyi.taglibrary.domain.TlTagDir;

public interface TlTagDirMapper {
    List<TlTagDir> selectDirList(Long libraryId);

    TlTagDir selectDirById(Long dirId);

    int insertDir(TlTagDir dir);

    int updateDir(TlTagDir dir);

    int deleteDirById(Long dirId);

    /** 统计目录下的标签数量（用于删除目录校验） */
    int countTagByDirId(Long dirId);
}
