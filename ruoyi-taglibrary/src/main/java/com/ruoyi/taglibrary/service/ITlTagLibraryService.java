package com.ruoyi.taglibrary.service;

import java.util.List;
import com.ruoyi.taglibrary.domain.TlTagLibrary;

/**
 * 标签库Service接口
 *
 * @author ruoyi
 */
public interface ITlTagLibraryService {

    /** 标签库列表（含标签统计） */
    List<TlTagLibrary> selectLibraryList(TlTagLibrary query);

    TlTagLibrary selectLibraryById(Long libraryId);

    /** 可选业务表列表（新建弹窗选表用） */
    List<String> listBusinessTables();

    /** 新增标签库（事务：编码查重→insert→建默认目录→同步源表字段快照） */
    int insertLibrary(TlTagLibrary library);

    int updateLibrary(TlTagLibrary library);

    /** 批量删除（校验：已上线/待审批拒绝、含已上线标签拒绝；级联逻辑删目录+标签） */
    int deleteLibraryByIds(Long[] libraryIds);

    /** 增量同步源表字段，返回新增快照数 */
    int syncFields(Long libraryId);

    /** 提交审批（草稿/已下线→待审批） */
    int submit(Long libraryId);

    /** 审批（通过→已上线 / 驳回→草稿） */
    int audit(Long libraryId, boolean pass, String auditComment);

    /** 下线（已上线→已下线） */
    int offline(Long libraryId);
}
