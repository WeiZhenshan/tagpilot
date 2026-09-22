package com.ruoyi.taglibrary.service;

import java.math.BigDecimal;
import java.util.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.impl.RuleExpressionSql;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/** 将逻辑指标引用编译为可信 AST；模型不能指定物理数据来源。 */
@Component
public class TsExpressionCompiler {
    @Autowired private ObjectMapper json;
    @Autowired private TlTagMapper tags;
    @Autowired private TlObjectGroupExtMapper ext;
    @Autowired private DpOnlineVersionResolver versions;
    private static final List<String> TIME=Arrays.asList("calendar_mode","time_anchor_type","time_window_unit","time_window_value",
        "time_anchor_label","time_offset_years","time_offset_months","period_edge");
    public static class Result {
        public ObjectNode node;
        public String unit, grain;
        public Map<String,String> time=new TreeMap<>();
        public Set<Long> tagIds=new HashSet<>();
    }
    public Result compile(JsonNode node, Long library, Set<Long> eligible, Map<Long,JsonNode> published, Map<String,JsonNode> capabilities) {
        return compile(node,library,eligible,published,capabilities,0,new int[]{0},new HashSet<>());
    }
    private Result compile(JsonNode n, Long library, Set<Long> eligible, Map<Long,JsonNode> published, Map<String,JsonNode> caps,
                           int depth,int[] count,Set<String> stack) {
        if(n==null || !n.isObject() || depth>8 || ++count[0]>64) fail("计算表达式格式或复杂度非法");
        for(String key:Arrays.asList("sql","field_name","table","function","column")) if(n.has(key)) fail("计算表达式不能指定物理字段或SQL");
        String kind=n.path("kind").asText(); Result r=new Result(); r.node=json.createObjectNode(); r.node.put("kind",kind);r.grain="CUSTOMER";
        if("TAG".equals(kind)) {
            long tid=n.path("tag_id").asLong(); JsonNode p=published.get(tid); TlTag tag=tags.selectTagById(tid);
            if(!eligible.contains(tid) || p==null || tag==null || !library.equals(tag.getLibraryId()) || !"数值型".equals(tag.getTagType())) fail("计算输入不是可用的数值标签");
            checkCaliber(n,p); r.unit=p.path("unit").asText("NONE");r.time=time(p);r.tagIds.add(tid);r.grain=p.path("grain").asText("CUSTOMER");
            String scale=RuleExpressionSql.number(p.path("unit_scale").asText("1"));
            if(new BigDecimal(scale).signum()<=0) fail("指标单位倍率无效");
            r.node.put("tag_id",tid).put("field_name",tag.getFieldName()).put("name",tag.getTagName()).put("unit_scale",scale).put("unit",r.unit);
            return r;
        }
        if("CONST".equals(kind)) {
            r.node.put("value",RuleExpressionSql.number(n.path("value").asText()));r.unit=n.path("unit").asText("NONE");r.grain=null;r.node.put("unit",r.unit);return r;
        }
        if("CAPABILITY".equals(kind)) {
            String id=n.path("capability_id").asText();JsonNode cap=caps.get(id);
            if(cap==null || !"REVIEWED".equals(cap.path("review_status").asText()) || !cap.path("version").asText().equals(n.path("version").asText())) fail("计算能力尚未发布或版本已变化");
            if(!stack.add(id)) fail("计算能力依赖成环");
            for(JsonNode dep:cap.path("input_tag_ids")) if(!eligible.contains(dep.asLong())) fail("计算能力依赖不在当前资格范围");
            checkCaliber(n,cap);
            String type=cap.path("capability_type").asText();
            if("DERIVED_METRIC".equals(type)) r=compile(cap.path("implementation").path("expression"),library,eligible,published,caps,depth+1,count,stack);
            else if("AGGREGATION_TEMPLATE".equals(type)) r=aggregate(cap,library);
            else fail("业务定义不能直接用作数值指标");
            Set<Long> declared=new HashSet<>();for(JsonNode dep:cap.path("input_tag_ids")) declared.add(dep.asLong());
            if(!declared.containsAll(r.tagIds)) fail("计算能力的实际依赖超出发布清单");
            r.tagIds.addAll(declared);r.time=time(cap);r.grain=cap.path("grain").asText("CUSTOMER");
            if(!Objects.equals(r.unit,cap.path("unit").asText("NONE"))) fail("计算能力输出单位与发布定义不一致");
            stack.remove(id);return r;
        }
        JsonNode args=n.path("args");
        if(!Arrays.asList("ADD","SUB","MUL","DIV","COUNT_POSITIVE").contains(kind) || !args.isArray()
                || ("COUNT_POSITIVE".equals(kind)?args.size()<1 || args.size()>12:args.size()!=2)) fail("计算算子或参数数量不受支持");
        List<Result> parts=new ArrayList<>();Set<String> grains=new HashSet<>();Set<Map<String,String>> times=new HashSet<>();
        ArrayNode out=json.createArrayNode();Set<String> unique=new HashSet<>();
        for(JsonNode a:args) {
            Result child=compile(a,library,eligible,published,caps,depth+1,count,stack);parts.add(child);out.add(child.node);r.tagIds.addAll(child.tagIds);
            if(child.grain!=null)grains.add(child.grain);if(!child.tagIds.isEmpty())times.add(child.time);
            if("COUNT_POSITIVE".equals(kind) && !unique.add(child.node.toString())) fail("类别计数包含重复输入");
        }
        if(grains.size()>1)fail("计算输入粒度不同");
        if(times.size()>1) {
            if(!"EXPLICIT_PERIODS".equals(n.path("time_alignment").asText()))fail("计算输入时间不同，需要明确跨期关系");
            for(int i=0;i<args.size();i++)if(!parts.get(i).tagIds.isEmpty() && args.get(i).path("expected_caliber").size()==0)fail("跨期计算缺少逐项时间证据");
        }
        String a=parts.get(0).unit,b=parts.size()>1?parts.get(1).unit:a;
        if(Arrays.asList("ADD","SUB","COUNT_POSITIVE").contains(kind)) {
            for(Result p:parts)if(!Objects.equals(a,p.unit))fail("计算输入单位不同");
            r.unit="COUNT_POSITIVE".equals(kind)?"COUNT":a;
        } else if("DIV".equals(kind)) {
            if(a.equals(b))r.unit="RATIO";else if(dimensionless(b))r.unit=a;else fail("不支持这种单位的除法");
        } else {
            if(dimensionless(a))r.unit=b;else if(dimensionless(b))r.unit=a;else fail("乘法需要无量纲倍率");
        }
        for(Result part:parts)if(!part.tagIds.isEmpty()){r.time=part.time;break;}r.grain=grains.isEmpty()?null:grains.iterator().next();r.node.set("args",out);r.node.put("unit",r.unit);return r;
    }
    private Result aggregate(JsonNode cap,Long library) {
        JsonNode impl=cap.path("implementation");long dataset=impl.path("dataset_id").asLong(), version=impl.path("dataset_version_id").asLong();
        DpResolvedVersion online=versions.resolve(dataset);
        if(online==null || online.getVersionId()!=version) fail("聚合数据集版本不可用或已变化");
        Long rootDataset=ext.selectDatasetIdByLibrary(library);
        com.ruoyi.databroker.domain.DpDataSource rootSource=ext.selectDataSourceByDataset(rootDataset), source=ext.selectDataSourceByDataset(dataset);
        if(rootSource==null || source==null || !Objects.equals(rootSource.getDatasourceId(),source.getDatasourceId())) fail("聚合模板必须与客户库使用同一数据源");
        String table;
        try {table=ext.selectTableObjectName(json.readTree(ext.selectVersionDefinitionJson(version)).path("tableId").asLong());}
        catch(Exception e){throw new ServiceException("无法核验聚合数据表");}
        RuleExpressionSql.identifier(table);
        Result r=new Result();r.unit=cap.path("unit").asText("NONE");r.node=json.createObjectNode();r.node.put("kind","AGGREGATE").put("table_name",table);
        r.node.put("customer_column",column(version,impl.path("customer_key").asText()));r.node.put("value_column",column(version,impl.path("value_field").asText()));
        String agg=impl.path("aggregation").asText();if(!Arrays.asList("COUNT_DISTINCT","COUNT","SUM","MAX","MIN","AVG").contains(agg))fail("聚合方式未登记");
        if(agg.startsWith("COUNT") && !"COUNT".equals(r.unit))fail("计数聚合单位必须为COUNT");
        r.node.put("aggregation",agg);String empty=impl.path("empty_policy").asText("UNKNOWN");
        if(!Arrays.asList("UNKNOWN","ZERO_WHEN_NO_ROWS").contains(empty))fail("聚合空值规则非法");
        if(("ZERO_WHEN_NO_ROWS".equals(empty) || agg.startsWith("COUNT")) && !"FULL".equals(impl.path("coverage").asText()))fail("零事件计数需要发布完整覆盖证据");
        r.node.put("empty_policy",empty);ArrayNode filters=json.createArrayNode();
        if(impl.path("filters").size()>12)fail("聚合过滤项过多");
        for(JsonNode f:impl.path("filters")) {
            ObjectNode target=json.createObjectNode();target.put("column",column(version,f.path("field").asText()));
            target.put("operator",f.path("operator").asText()).put("type",f.path("type").asText()).put("value",f.path("value").asText());filters.add(target);
        }
        r.node.set("filters",filters);return r;
    }
    private String column(Long version,String alias){String col=ext.selectColumnNameByAlias(version,alias);RuleExpressionSql.identifier(col);return col;}
    private static boolean dimensionless(String unit){return "NONE".equals(unit)||"RATIO".equals(unit);}
    private static Map<String,String> time(JsonNode p){Map<String,String> out=new TreeMap<>();for(String k:TIME)if(p.path("caliber_struct").hasNonNull(k))out.put(k,caliberValue(k,p.path("caliber_struct").get(k),p.path("caliber_struct")));return out;}
    private static String caliberValue(String key,JsonNode value,JsonNode actual) {
        String text=value==null?"":value.asText();
        if("time_anchor_label".equals(key) && Arrays.asList("当前","当前时点").contains(text)
            && "POINT".equals(actual.path("time_anchor_type").asText()) && "END".equals(actual.path("period_edge").asText()) && "EOP".equals(actual.path("statistic").asText()))return "CURRENT_POINT";
        return text;
    }
    public static void checkCaliber(JsonNode request,JsonNode published) {
        JsonNode expected=request.path("expected_caliber"), actual=published.path("caliber_struct");
        if(!request.path("time_constraint").asText().isEmpty() && (!expected.isObject()||expected.size()==0))fail("时间要求缺少可核验的解释");
        if(!expected.isMissingNode() && !expected.isNull() && !expected.isObject())fail("口径格式非法");
        expected.fields().forEachRemaining(e->{if(!e.getValue().isNull() && (!actual.hasNonNull(e.getKey()) || !caliberValue(e.getKey(),e.getValue(),actual).equals(caliberValue(e.getKey(),actual.get(e.getKey()),actual))))fail("计算输入口径不匹配或发布信息缺失");});
    }
    private static void fail(String message){throw new ServiceException(message);}
}
