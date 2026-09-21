package com.ruoyi.taglibrary.service;

import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.math.BigDecimal;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.*;
import com.ruoyi.common.exception.ServiceException;
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

    public RulePayload compile(Long library, Map<String,Object> plan) {
        Map<String,Object> bundle = catalog.activeBundle(library);
        for (String key : Arrays.asList("build_id","snapshot_id","artifact_hash"))
            if (!Objects.equals(bundle.get(key),plan.get(key))) throw new ServiceException("发布版本已变化，请重新核验方案");
        Set<Long> eligible = new HashSet<>(catalog.eligibleTagIds(library, String.valueOf(bundle.get("snapshot_id"))));
        Map<Long,JsonNode> semantic = new HashMap<>();
        Map<Long,Map<String,String>> codes = new HashMap<>();
        Map<Long,Set<String>> unknownCodes = new HashMap<>();
        try {
            TsCatalogSnapshot snapshot=snapshots.selectById(String.valueOf(bundle.get("snapshot_id")));
            for (String line : Files.readAllLines(artifacts.verifiedPath(snapshot), StandardCharsets.UTF_8)) {
                if (line.trim().isEmpty()) continue;
                JsonNode row=json.readTree(line);
                if ("tag".equals(row.path("kind").asText())) semantic.put(row.path("tag_id").asLong(),row);
                if ("code_value".equals(row.path("kind").asText()) && row.path("is_unknown_bucket").asInt()==1)
                    unknownCodes.computeIfAbsent(row.path("tag_id").asLong(),k->new HashSet<>()).add(row.path("code").asText());
                if ("code_value".equals(row.path("kind").asText()))
                    codes.computeIfAbsent(row.path("tag_id").asLong(),k->new HashMap<>()).put(row.path("code").asText(),row.path("label").asText());
            }
        } catch (ServiceException e) { throw e; }
        catch (Exception e) { throw new ServiceException("无法读取已发布的标签证据"); }
        RulePayload rule=new RulePayload(); rule.setSchemaVersion(3);
        List<RulePayload.Condition> out=new ArrayList<>();
        walk(json.valueToTree(plan.get("tree")),"AND",0,library,eligible,semantic,codes,unknownCodes,new HashSet<>(),out);
        if (out.isEmpty() || out.size()>30) throw new ServiceException("方案须包含1至30项条件");
        rule.setConditions(out);
        Map<Long,RulePayload.PreviewColumn> preview=new LinkedHashMap<>();
        for(RulePayload.Condition c:out) {
            RulePayload.PreviewColumn col=new RulePayload.PreviewColumn();col.setTagId(c.getTagId());col.setFieldName(c.getFieldName());
            col.setTagName(c.getTagName());col.setTagType(c.getTagType());col.setDataType(c.getDataType());preview.put(c.getTagId(),col);
        }
        rule.setPreviewColumns(new ArrayList<>(preview.values()));
        return rule;
    }

    private void walk(JsonNode node,String connector,int depth,Long library,Set<Long> eligible,
            Map<Long,JsonNode> semantic,Map<Long,Map<String,String>> codes,Map<Long,Set<String>> unknownCodes,Set<String> ids,List<RulePayload.Condition> out) {
        if (node==null || !node.isObject() || depth>8 || out.size()>30) throw new ServiceException("条件树格式非法");
        if (node.has("children")) {
            String logic=node.path("logic").asText(); JsonNode children=node.get("children");
            if (!Arrays.asList("AND","OR").contains(logic) || !children.isArray() || children.size()==0 || children.size()>30)
                throw new ServiceException("条件组格式非法");
            int first=out.size();
            for(int i=0;i<children.size();i++) walk(children.get(i),i==0?connector:logic,depth+1,library,eligible,semantic,codes,unknownCodes,ids,out);
            RulePayload.Condition start=out.get(first), end=out.get(out.size()-1);
            start.setOpenParen(start.getOpenParen()+1); end.setCloseParen(end.getCloseParen()+1);
            return;
        }
        String id=node.path("clause_id").asText();
        if (id.isEmpty() || !ids.add(id)) throw new ServiceException("条件标识缺失或重复");
        if (node.hasNonNull("unresolved") && !node.get("unresolved").asText().isEmpty()) throw new ServiceException("存在未解决条件");
        Long tid=node.path("tag_id").asLong(); TlTag tag=tags.selectTagById(tid);
        if (!eligible.contains(tid) || tag==null || !library.equals(tag.getLibraryId()) || !semantic.containsKey(tid))
            throw new ServiceException("条件包含不可用标签");
        String op=node.path("operator").asText(); Set<String> allowed=new HashSet<>();
        semantic.get(tid).path("allowed_operators").forEach(v->allowed.add(v.asText()));
        if (!allowed.contains(op)) throw new ServiceException("标签不支持所选比较方式");
        JsonNode expected=node.path("expected_caliber"), published=semantic.get(tid), caliber=published.path("caliber_struct");
        if (!node.path("time_constraint").asText().isEmpty() && (!expected.isObject() || expected.size()==0))
            throw new ServiceException("时间条件缺少可验证的发布口径");
        if (expected.isObject()) {
            Iterator<Map.Entry<String,JsonNode>> fields=expected.fields();
            while(fields.hasNext()) {
                Map.Entry<String,JsonNode> field=fields.next();
                if (!field.getValue().isNull() && !Objects.equals(field.getValue().asText(),caliber.path(field.getKey()).asText()))
                    throw new ServiceException("所选标签的时间或统计口径与需求不一致");
            }
        }
        if ("数值型".equals(tag.getTagType())) {
            if (!Objects.equals(node.path("value_unit").asText(),published.path("unit").asText()))
                throw new ServiceException("数值单位未经核验");
            try {
                if(new BigDecimal(node.path("value_scale").asText()).compareTo(new BigDecimal(published.path("unit_scale").asText("1")))!=0)
                    throw new ServiceException("数值单位倍率未经核验");
            } catch(NumberFormatException e) { throw new ServiceException("数值单位倍率非法"); }
        }
        List<String> values=new ArrayList<>(); JsonNode raw=node.path("values");
        if (!raw.isArray()) throw new ServiceException("条件值必须是数组");
        raw.forEach(v->{ if (!v.isValueNode() || v.isNull()) throw new ServiceException("条件值格式非法"); values.add(v.asText()); });
        boolean nullOp=Arrays.asList("is_null","is_not_null").contains(op);
        if (!nullOp && (values.isEmpty() || values.stream().anyMatch(String::isEmpty))) throw new ServiceException("条件值未填写");
        if (!nullOp && !Arrays.asList("in","not_in","between").contains(op) && values.size()!=1) throw new ServiceException("比较值数量非法");
        if ("between".equals(op) && values.size()!=2) throw new ServiceException("区间端点数量非法");
        if(Arrays.asList("not_in","!=").contains(op) && Arrays.asList("布尔型","选项型").contains(tag.getTagType())) {
            String policy=node.path("unknown_policy").asText("EXCLUDE");
            if(!Arrays.asList("EXCLUDE","INCLUDE").contains(policy))throw new ServiceException("未知码值策略非法");
            if("EXCLUDE".equals(policy) && !values.containsAll(unknownCodes.getOrDefault(tid,Collections.emptySet())))
                throw new ServiceException("否定集合未排除发布为未知的码值");
        }
        List<RulePayload.CodeOptionSnapshot> labels=new ArrayList<>();
        for (String value:values) {
            if ("数值型".equals(tag.getTagType())) {
                try { new BigDecimal(value); } catch (NumberFormatException e) { throw new ServiceException("数值格式非法"); }
            }
            if (Arrays.asList("布尔型","选项型").contains(tag.getTagType())) {
                Map<String,String> options=codes.getOrDefault(tid,Collections.emptyMap());
                if (!options.containsKey(value)) throw new ServiceException("条件包含未发布码值");
                RulePayload.CodeOptionSnapshot label=new RulePayload.CodeOptionSnapshot(); label.setCode(value); label.setLabel(options.get(value)); labels.add(label);
            }
        }
        RulePayload.Condition c=new RulePayload.Condition(); c.setConditionId(id); c.setConnector(connector);
        c.setOpenParen(0); c.setCloseParen(0); c.setTagId(tid); c.setFieldName(tag.getFieldName()); c.setTagName(tag.getTagName());
        c.setTagType(tag.getTagType()); c.setDataType(tag.getDataType()); c.setOperator(op); c.setValues(values); c.setSelectedCodeOptions(labels);
        out.add(c);
    }
}
