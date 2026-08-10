package com.ruoyi.objectgroup.service;

import java.util.List;
import java.util.Map;
import org.springframework.web.multipart.MultipartFile;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.domain.TlObjectGroup;

public interface ITlObjectGroupService {

    List<TlObjectGroup> selectObjectGroupList(TlObjectGroup query);

    TlObjectGroup selectObjectGroupById(Long groupId);

    int insertObjectGroup(TlObjectGroup group);

    int updateObjectGroup(TlObjectGroup group);

    int deleteObjectGroupByIds(Long[] groupIds);

    /** 生成规则 SQL（预览弹窗） */
    String buildRuleSql(Long libraryId, RulePayload rule);

    /** 执行 COUNT 并返回用户数；有 groupId 时回写 */
    long runRule(Long groupId, Long libraryId, RulePayload rule);

    /** 样例预览：客户号 + 预览列，LIMIT 100 */
    Map<String, Object> previewRule(Long groupId, Long libraryId, RulePayload rule);

    /** 解析导入文件（txt/csv 单列 ≤5M ≤5万条） */
    Map<String, Object> parseImportFile(MultipartFile file, String fieldName);
}
