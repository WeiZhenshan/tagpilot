package com.ruoyi.taglibrary.mapper;
import com.ruoyi.taglibrary.domain.TsRetrievalFeedback;
import org.apache.ibatis.annotations.Param;
public interface TsRetrievalFeedbackMapper {
    int insert(TsRetrievalFeedback row);
    TsRetrievalFeedback selectTrace(@Param("traceId") String traceId, @Param("userId") Long userId);
}
