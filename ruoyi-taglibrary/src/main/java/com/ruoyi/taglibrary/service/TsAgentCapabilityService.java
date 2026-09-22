package com.ruoyi.taglibrary.service;

import java.util.*;
import com.fasterxml.jackson.databind.*;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.taglibrary.mapper.TsAgentCapabilityMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/** 能力编辑/复核与快照发布分离；已有版本只读，不自动复核业务口径。 */
@Service
public class TsAgentCapabilityService {
    @Autowired private TsAgentCapabilityMapper mapper;
    @Autowired private ObjectMapper json;
    @Autowired private ITlTagLibraryService libraries;
    @Autowired private com.ruoyi.framework.web.service.PermissionService permissions;
    private void visible(Long library) {
        if(library==null || !permissions.hasAnyPermi("taglibrary:library:list,taglibrary:library:query") || libraries.selectLibraryById(library)==null)
            throw new ServiceException("无权访问该标签库",403);
    }
    public void save(Long library,Map<String,Object> body) {
        visible(library);
        JsonNode n=json.valueToTree(body);validate(n,null);
        try {mapper.insert(library,n.path("capability_id").asText(),n.path("version").asInt(),json.writeValueAsString(body),SecurityUtils.getUsername());}
        catch(org.springframework.dao.DuplicateKeyException e){throw new ServiceException("该能力版本已存在，请使用新版本号");}
        catch(com.fasterxml.jackson.core.JsonProcessingException e){throw new ServiceException("能力定义格式错误");}
    }
    public void review(Long library,String id,Integer version) {
        visible(library);
        String raw=mapper.definition(library,id,version);if(raw==null)throw new ServiceException("能力版本不存在");
        try {validate(json.readTree(raw),null);}catch(java.io.IOException e){throw new ServiceException("能力定义格式错误");}
        if(mapper.review(library,id,version,SecurityUtils.getUsername())!=1)throw new ServiceException("该版本已经复核或不可修改");
    }
    public List<Map<String,Object>> publishedRows(Long library,Set<Long> available) {
        List<Map<String,Object>> rows=new ArrayList<>();
        for(String raw:mapper.reviewed(library)) {
            try {
                JsonNode n=json.readTree(raw);validate(n,available);
                Map<String,Object> row=json.convertValue(n,Map.class);row.put("kind","capability");row.put("review_status","REVIEWED");rows.add(row);
            } catch(java.io.IOException e){throw new ServiceException("已复核能力定义格式错误");}
        }
        return rows;
    }
    public static void validate(JsonNode n,Set<Long> available) {
        if(!n.path("capability_id").asText().matches("[A-Za-z][A-Za-z0-9_.-]{0,95}") || n.path("version").asInt()<=0)
            throw new ServiceException("能力标识或版本非法");
        if(!Arrays.asList("BUSINESS_DEFINITION","DERIVED_METRIC","AGGREGATION_TEMPLATE").contains(n.path("capability_type").asText()))throw new ServiceException("能力类型非法");
        for(String key:Arrays.asList("name","definition","applicability","source_ref"))if(n.path(key).asText().trim().isEmpty())throw new ServiceException("能力缺少"+key);
        if(!n.path("input_tag_ids").isArray())throw new ServiceException("能力须列出依赖标签");
        for(JsonNode dep:n.path("input_tag_ids"))if(!dep.isIntegralNumber() || dep.asLong()<=0 || (available!=null && !available.contains(dep.asLong())))throw new ServiceException("能力依赖的标签未通过发布门禁");
        if(n.has("aliases")) {
            if(!n.path("aliases").isArray())throw new ServiceException("能力别名须为字符串数组");
            for(JsonNode alias:n.path("aliases"))if(!alias.isTextual())throw new ServiceException("能力别名须为字符串数组");
        }
        String type=n.path("capability_type").asText();
        if("BUSINESS_DEFINITION".equals(type)) {
            if(!n.path("plan_template").isObject())throw new ServiceException("业务定义缺少方案模板");
        } else {
            if(!n.path("implementation").isObject() || n.path("unit").asText().isEmpty() || !"CUSTOMER".equals(n.path("grain").asText()))throw new ServiceException("计算能力缺少实现、单位或客户粒度");
            if("DERIVED_METRIC".equals(type) && !n.path("implementation").path("expression").isObject())throw new ServiceException("派生能力缺少表达式");
            if("AGGREGATION_TEMPLATE".equals(type)) {
                JsonNode i=n.path("implementation");
                if(i.path("dataset_id").asLong()<=0 || i.path("dataset_version_id").asLong()<=0 || i.path("customer_key").asText().isEmpty() || i.path("value_field").asText().isEmpty())throw new ServiceException("聚合模板缺少数据集版本或关联字段");
            }
        }
        // SQL永远不是能力配置的一部分；聚合实现由固定算子与元数据绑定生成。
        rejectSql(n,0);
    }
    private static void rejectSql(JsonNode n,int depth) {
        if(depth>16)throw new ServiceException("能力定义过深");
        if(n.isObject())n.fields().forEachRemaining(e->{if(Arrays.asList("sql","table","table_name","field_name","column","function").contains(e.getKey()))throw new ServiceException("能力不能包含自由SQL或物理查询实现");rejectSql(e.getValue(),depth+1);});
        else if(n.isArray())for(JsonNode child:n)rejectSql(child,depth+1);
    }
}
