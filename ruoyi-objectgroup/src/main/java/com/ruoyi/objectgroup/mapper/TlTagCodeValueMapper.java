package com.ruoyi.objectgroup.mapper;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import com.ruoyi.objectgroup.domain.TlTagCodeValue;

public interface TlTagCodeValueMapper {

    List<TlTagCodeValue> selectCodeValueList(TlTagCodeValue query);

    List<TlTagCodeValue> selectCodeValueByField(@Param("libraryId") Long libraryId, @Param("fieldName") String fieldName);

    TlTagCodeValue selectCodeValueById(Long valueId);

    int insertCodeValue(TlTagCodeValue codeValue);

    int updateCodeValue(TlTagCodeValue codeValue);

    int deleteCodeValueByIds(Long[] valueIds);

    /** 物理删除某标签库全部码值（删除标签库时级联清理） */
    int deleteByLibraryId(Long libraryId);

    /** 幂等写入（唯一键冲突时更新定义/排序） */
    int upsertCodeValue(TlTagCodeValue codeValue);
}
