package com.ruoyi.taglibrary.service;

import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.math.BigDecimal;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.*;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.agent.TsPlanValidationException;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;

/** 发布快照与当前标签共同校验；不信任浏览器或模型提供的物理字段、类型、SQL。 */
@Service
public class TsAudiencePlanCompiler {
    @Autowired private ObjectMapper json;
    @Autowired private ITsCatalogRuntimeService catalog;
    @Autowired private TsCatalogSnapshotMapper snapshots;
    @Autowired private TsSnapshotArtifactStore artifacts;
    @Autowired private TlTagMapper tags;
    @Autowired private TsExpressionCompiler expressions;
    @org.springframework.beans.factory.annotation.Value("${tag.agent.expressions-enabled:true}")
    private boolean expressionsEnabled = true;

    public RulePayload compile(Long library, Map<String,Object> plan) {
        Map<String,Object> bundle = catalog.activeBundle(library);
        for (String key : Arrays.asList("build_id","snapshot_id","artifact_hash"))
            if (!Objects.equals(bundle.get(key),plan.get(key))) throw new TsPlanValidationException("VERSION_MISMATCH",null,"发布版本已变化，请重新核验方案");
        Set<Long> eligible = new HashSet<>(catalog.eligibleTagIds(library, String.valueOf(bundle.get("snapshot_id"))));
        Map<Long,JsonNode> semantic = new HashMap<>();
        Map<Long,Map<String,String>> codes = new HashMap<>();
        Map<Long,Set<String>> unknownCodes = new HashMap<>();
        Map<String,JsonNode> capabilities = new HashMap<>();
        try {
            TsCatalogSnapshot snapshot=snapshots.selectById(String.valueOf(bundle.get("snapshot_id")));
            for (String line : Files.readAllLines(artifacts.verifiedPath(snapshot), StandardCharsets.UTF_8)) {
                if (line.trim().isEmpty()) continue;
                JsonNode row=json.readTree(line);
                if ("tag".equals(row.path("kind").asText())) semantic.put(row.path("tag_id").asLong(),row);
                if ("capability".equals(row.path("kind").asText())) capabilities.put(row.path("capability_id").asText(),row);
                if ("code_value".equals(row.path("kind").asText()) && row.path("is_unknown_bucket").asInt()==1)
                    unknownCodes.computeIfAbsent(row.path("tag_id").asLong(),k->new HashSet<>()).add(row.path("code").asText());
                if ("code_value".equals(row.path("kind").asText()))
                    codes.computeIfAbsent(row.path("tag_id").asLong(),k->new HashMap<>()).put(row.path("code").asText(),row.path("label").asText());
            }
        } catch (ServiceException e) { throw e; }
        catch (Exception e) { throw new TsPlanValidationException("SCHEMA_INVALID",null,"无法读取已发布的标签证据"); }
        int schema=json.valueToTree(plan.getOrDefault("schema_version",2)).asInt();
        if(schema!=2 && schema!=3) throw new TsPlanValidationException("SCHEMA_INVALID",null,"圈选方案版本不受支持");
        if(schema==3 && !expressionsEnabled)throw new TsPlanValidationException("UNSUPPORTED_CAPABILITY",null,"新版计算能力已关闭；原方案仍可查看，请启用后重新核验");
        validateIntent(json.valueToTree(plan),capabilities,semantic,eligible);
        RulePayload rule=new RulePayload(); rule.setSchemaVersion(schema==3?4:3);
        List<RulePayload.Condition> out=new ArrayList<>();
        walk(json.valueToTree(plan.get("tree")),"AND",0,library,eligible,semantic,codes,unknownCodes,capabilities,new HashSet<>(),out,schema);
        if (out.isEmpty() || out.size()>30) throw new TsPlanValidationException("SCHEMA_INVALID",null,"方案须包含1至30项条件");
        rule.setConditions(out);
        Map<Long,RulePayload.PreviewColumn> preview=new LinkedHashMap<>();
        for(RulePayload.Condition c:out) {
            if(c.isScopeAll() || c.getExpression()!=null)continue;
            RulePayload.PreviewColumn col=new RulePayload.PreviewColumn();col.setTagId(c.getTagId());col.setFieldName(c.getFieldName());
            col.setTagName(c.getTagName());col.setTagType(c.getTagType());col.setDataType(c.getDataType());preview.put(c.getTagId(),col);
        }
        rule.setPreviewColumns(new ArrayList<>(preview.values()));
        if(schema==3) {
            if(out.stream().anyMatch(RulePayload.Condition::isScopeAll) && out.size()!=1)throw new TsPlanValidationException("SCHEMA_INVALID",null,"全量范围不能与筛选条件混合");
            rule.setAudiencePlan(json.convertValue(plan,Map.class));
        }
        return rule;
    }

    private TsExpressionCompiler.Result compileExpression(JsonNode expression,Long library,Set<Long> eligible,
            Map<Long,JsonNode> semantic,Map<String,JsonNode> capabilities,String clauseId) {
        try { return expressions.compile(expression,library,eligible,semantic,capabilities); }
        catch(TsPlanValidationException e) { throw e.atClause(clauseId); }
    }

    private void walk(JsonNode node,String connector,int depth,Long library,Set<Long> eligible,
            Map<Long,JsonNode> semantic,Map<Long,Map<String,String>> codes,Map<Long,Set<String>> unknownCodes,
            Map<String,JsonNode> capabilities,Set<String> ids,List<RulePayload.Condition> out,int schema) {
        if (node==null || !node.isObject() || depth>8 || out.size()>30) throw new TsPlanValidationException("SCHEMA_INVALID",null,"条件树格式非法");
        if (node.has("children")) {
            String logic=node.path("logic").asText(); JsonNode children=node.get("children");
            if (!Arrays.asList("AND","OR").contains(logic) || !children.isArray() || children.size()==0 || children.size()>30)
                throw new TsPlanValidationException("SCHEMA_INVALID",null,"条件组格式非法");
            int first=out.size();
            for(int i=0;i<children.size();i++) walk(children.get(i),i==0?connector:logic,depth+1,library,eligible,semantic,codes,unknownCodes,capabilities,ids,out,schema);
            RulePayload.Condition start=out.get(first), end=out.get(out.size()-1);
            start.setOpenParen(start.getOpenParen()+1); end.setCloseParen(end.getCloseParen()+1);
            return;
        }
        String id=node.path("clause_id").asText();
        if (id.isEmpty() || !ids.add(id)) throw new TsPlanValidationException("SCHEMA_INVALID",id,"条件标识缺失或重复");
        if (node.hasNonNull("unresolved") && !node.get("unresolved").asText().isEmpty()) throw new TsPlanValidationException("SCHEMA_INVALID",id,"存在未解决条件");
        String clauseState=node.path("status").asText();
        if(Arrays.asList("GAP","NEEDS_DECISION","UNRESOLVED").contains(clauseState))
            throw new TsPlanValidationException("REQUIREMENT_MISSING",id,"条件仍有缺口或待决定事项");
        if("ASSUMED".equals(clauseState) && !node.path("assumption_confirmed").asBoolean(false))
            throw new TsPlanValidationException("BUSINESS_AMBIGUITY",id,"请先确认采用的业务定义");
        String kind=node.path("kind").asText("TAG_PREDICATE");
        if("SCOPE_ALL".equals(kind) || "DERIVED_PREDICATE".equals(kind)) {
            if(schema!=3)throw new TsPlanValidationException("SCHEMA_INVALID",id,"计算条件需要新版方案契约");
            RulePayload.Condition c=new RulePayload.Condition();c.setConditionId(id);c.setConnector(connector);c.setOpenParen(0);c.setCloseParen(0);
            if("SCOPE_ALL".equals(kind)){c.setScopeAll(true);c.setTagName("当前授权范围内全部客户");out.add(c);return;}
            TsExpressionCompiler.Result left=compileExpression(node.get("expression"),library,eligible,semantic,capabilities,id);
            c.setExpression(left.node);c.setTagName(node.path("name").asText(node.path("source_span").asText("计算条件")));c.setTagType("数值型");c.setOperator(node.path("operator").asText());
            if(node.hasNonNull("compare_expression")) {
                TsExpressionCompiler.Result right=compileExpression(node.get("compare_expression"),library,eligible,semantic,capabilities,id);
                if(!Objects.equals(left.unit,right.unit))throw new TsPlanValidationException("UNIT_MISMATCH",id,"比较指标单位不同");
                if(left.grain!=null && right.grain!=null && !left.grain.equals(right.grain))throw new TsPlanValidationException("CALIBER_CONFLICT",id,"比较指标粒度不同");
                if(!left.time.equals(right.time) && !"EXPLICIT_PERIODS".equals(node.path("time_alignment").asText()))throw new TsPlanValidationException("CALIBER_CONFLICT",id,"比较指标时间不同，需要明确跨期关系");
                c.setCompareExpression(right.node);
            } else {
                if(!left.unit.equals(node.path("value_unit").asText(left.unit)) || new BigDecimal(node.path("value_scale").asText("1")).compareTo(BigDecimal.ONE)!=0)
                    throw new TsPlanValidationException("UNIT_MISMATCH",id,"计算比较值的单位或倍率未经规范化");
                List<String> values=new ArrayList<>();for(JsonNode value:node.path("values"))values.add(com.ruoyi.objectgroup.service.impl.RuleExpressionSql.number(value.asText()));c.setValues(values);
            }
            // 先检查比较形状；物理别名在真正执行时由数据集再次解析。
            if(!Arrays.asList("=","!=",">",">=","<","<=","between","is_null","is_not_null").contains(c.getOperator()))throw new TsPlanValidationException("INVALID_OPERATOR",id,"计算比较符非法");
            if(c.getCompareExpression()!=null && !Arrays.asList("=","!=",">",">=","<","<=").contains(c.getOperator()))throw new TsPlanValidationException("INVALID_OPERATOR",id,"指标比较方式非法");
            if(c.getCompareExpression()==null && !Arrays.asList("is_null","is_not_null").contains(c.getOperator()) && (c.getValues()==null || c.getValues().size()!=("between".equals(c.getOperator())?2:1)))throw new TsPlanValidationException("INVALID_VALUE",id,"计算比较值数量非法");
            out.add(c);return;
        }
        if(!"TAG_PREDICATE".equals(kind))throw new TsPlanValidationException("SCHEMA_INVALID",id,"未知条件类型");
        Long tid=node.path("tag_id").asLong(); TlTag tag=tags.selectTagById(tid);
        if (!eligible.contains(tid) || tag==null || !library.equals(tag.getLibraryId()) || !semantic.containsKey(tid))
            throw new TsPlanValidationException("INELIGIBLE_TAG",id,"条件包含不可用标签");
        String op=node.path("operator").asText(); Set<String> allowed=new HashSet<>();
        semantic.get(tid).path("allowed_operators").forEach(v->allowed.add(v.asText()));
        if (!allowed.contains(op)) throw new TsPlanValidationException("INVALID_OPERATOR",id,"标签不支持所选比较方式");
        JsonNode published=semantic.get(tid);
        try { TsExpressionCompiler.checkCaliber(node,published); }
        catch(TsPlanValidationException e) { throw e.atClause(id); }
        if ("数值型".equals(tag.getTagType())) {
            if (!Objects.equals(node.path("value_unit").asText(),published.path("unit").asText()))
                throw new TsPlanValidationException("UNIT_MISMATCH",id,"数值单位未经核验");
            try {
                if(new BigDecimal(node.path("value_scale").asText()).compareTo(new BigDecimal(published.path("unit_scale").asText("1")))!=0)
                    throw new TsPlanValidationException("UNIT_MISMATCH",id,"数值单位倍率未经核验");
            } catch(NumberFormatException e) { throw new TsPlanValidationException("UNIT_MISMATCH",id,"数值单位倍率非法"); }
        }
        List<String> values=new ArrayList<>(); JsonNode raw=node.path("values");
        if (!raw.isArray()) throw new TsPlanValidationException("INVALID_VALUE",id,"条件值必须是数组");
        raw.forEach(v->{ if (!v.isValueNode() || v.isNull()) throw new TsPlanValidationException("INVALID_VALUE",id,"条件值格式非法"); values.add(v.asText()); });
        boolean nullOp=Arrays.asList("is_null","is_not_null").contains(op);
        if (!nullOp && (values.isEmpty() || values.stream().anyMatch(String::isEmpty))) throw new TsPlanValidationException("INVALID_VALUE",id,"条件值未填写");
        if (!nullOp && !Arrays.asList("in","not_in","between").contains(op) && values.size()!=1) throw new TsPlanValidationException("INVALID_VALUE",id,"比较值数量非法");
        if ("between".equals(op) && values.size()!=2) throw new TsPlanValidationException("INVALID_VALUE",id,"区间端点数量非法");
        if(Arrays.asList("not_in","!=").contains(op) && Arrays.asList("布尔型","选项型").contains(tag.getTagType())) {
            String policy=node.path("unknown_policy").asText("EXCLUDE");
            if(!Arrays.asList("EXCLUDE","INCLUDE").contains(policy))throw new TsPlanValidationException("UNKNOWN_CODE",id,"未知码值策略非法");
            if("EXCLUDE".equals(policy) && !values.containsAll(unknownCodes.getOrDefault(tid,Collections.emptySet())))
                throw new TsPlanValidationException("UNKNOWN_CODE",id,"否定集合未排除发布为未知的码值");
        }
        List<RulePayload.CodeOptionSnapshot> labels=new ArrayList<>();
        for (String value:values) {
            if ("数值型".equals(tag.getTagType())) {
                try { new BigDecimal(value); } catch (NumberFormatException e) { throw new TsPlanValidationException("INVALID_VALUE",id,"数值格式非法"); }
            }
            if (Arrays.asList("布尔型","选项型").contains(tag.getTagType())) {
                Map<String,String> options=codes.getOrDefault(tid,Collections.emptyMap());
                if (!options.containsKey(value)) throw new TsPlanValidationException("UNKNOWN_CODE",id,"条件包含未发布码值");
                RulePayload.CodeOptionSnapshot label=new RulePayload.CodeOptionSnapshot(); label.setCode(value); label.setLabel(options.get(value)); labels.add(label);
            }
        }
        RulePayload.Condition c=new RulePayload.Condition(); c.setConditionId(id); c.setConnector(connector);
        c.setOpenParen(0); c.setCloseParen(0); c.setTagId(tid); c.setFieldName(tag.getFieldName()); c.setTagName(tag.getTagName());
        c.setTagType(tag.getTagType()); c.setDataType(tag.getDataType()); c.setOperator(op); c.setValues(values); c.setSelectedCodeOptions(labels);
        out.add(c);
    }

    private void validateIntent(JsonNode plan,Map<String,JsonNode> capabilities,Map<Long,JsonNode> semantic,Set<Long> eligible) {
        JsonNode intent=plan.path("intent_plan");
        if(intent.isMissingNode()) { if(plan.path("schema_version").asInt(2)>=3)throw new TsPlanValidationException("SCHEMA_INVALID",null,"新版方案缺少业务意图"); return; }
        Set<String> required=new HashSet<>(),covered=new HashSet<>();
        for(JsonNode r:intent.path("requirements")) {
            String id=r.path("requirement_id").asText();if(id.isEmpty()||!required.add(id))throw new TsPlanValidationException("REQUIREMENT_MISSING",null,"业务要求标识非法");
        }
        collectRequirements(plan.path("tree"),required,covered,0);
        if(required.isEmpty() || !covered.equals(required))throw new TsPlanValidationException("REQUIREMENT_MISSING",null,"执行方案没有完整覆盖业务要求");
        if(!logicSignature(intent.path("logic_tree"),false,0).equals(logicSignature(plan.path("tree"),true,0)))throw new TsPlanValidationException("LOGIC_CHANGED",null,"执行方案改变了原始 AND/OR 关系");
        for(JsonNode a:intent.path("assumptions")) {
            String status=a.path("status").asText();
            if("PUBLISHED".equals(status)) {
                JsonNode ref=a.path("definition_ref");
                if(ref.has("tag_id")) { if(!eligible.contains(ref.path("tag_id").asLong()) || !semantic.containsKey(ref.path("tag_id").asLong()))throw new TsPlanValidationException("INELIGIBLE_TAG",null,"业务解释标签不可用"); continue; }
                JsonNode cap=capabilities.get(ref.path("capability_id").asText());
                if(cap==null || !cap.path("version").asText().equals(ref.path("version").asText()))throw new TsPlanValidationException("UNSUPPORTED_CAPABILITY",null,"业务解释引用的发布定义不可用");
            } else if(!"CONFIRMED".equals(status))throw new TsPlanValidationException("BUSINESS_AMBIGUITY",null,"方案存在尚未确认的业务解释");
        }
    }
    private String logicSignature(JsonNode tree,boolean execution,int depth) {
        if(depth>8 || !tree.isObject())throw new TsPlanValidationException("SCHEMA_INVALID",null,"业务逻辑树格式非法");
        if(!tree.has("children")) {
            JsonNode refs=tree.path("requirement_ids");
            if(execution && refs.isArray() && refs.size()!=1)throw new TsPlanValidationException("REQUIREMENT_MISSING",null,"执行条件须对应一项业务要求");
            String id=execution?(refs.isArray()?refs.get(0).asText():tree.path("clause_id").asText()):tree.path("requirement_id").asText();
            if(id.isEmpty())throw new TsPlanValidationException("REQUIREMENT_MISSING",null,"业务要求标识缺失");
            return json.valueToTree(id).toString();
        }
        String logic=tree.path("logic").asText();
        if(!Arrays.asList("AND","OR").contains(logic)||!tree.path("children").isArray()||tree.path("children").size()==0)throw new TsPlanValidationException("SCHEMA_INVALID",null,"业务逻辑树格式非法");
        TreeSet<String> parts=new TreeSet<>();collectLogicParts(tree,logic,execution,depth,parts);
        return parts.size()==1?parts.first():logic+"["+String.join(",",parts)+"]";
    }
    private void collectLogicParts(JsonNode tree,String logic,boolean execution,int depth,Set<String> parts) {
        if(depth>8)throw new TsPlanValidationException("SCHEMA_INVALID",null,"业务逻辑树过深");
        for(JsonNode child:tree.path("children")) {
            if(child.has("children") && logic.equals(child.path("logic").asText()))collectLogicParts(child,logic,execution,depth+1,parts);
            else parts.add(logicSignature(child,execution,depth+1));
        }
    }
    private void collectRequirements(JsonNode tree,Set<String> required,Set<String> covered,int depth) {
        if(depth>8)throw new TsPlanValidationException("SCHEMA_INVALID",null,"意图映射过深");
        if(tree.has("children")){for(JsonNode c:tree.path("children"))collectRequirements(c,required,covered,depth+1);return;}
        if(tree.path("requirement_ids").isArray())for(JsonNode r:tree.path("requirement_ids")) {
            if(!required.contains(r.asText()))throw new TsPlanValidationException("REQUIREMENT_MISSING",null,"执行条件缺少业务来源");covered.add(r.asText());
        } else {String id=tree.path("clause_id").asText();if(!required.contains(id))throw new TsPlanValidationException("REQUIREMENT_MISSING",null,"执行条件缺少业务来源");covered.add(id);}
    }
}
