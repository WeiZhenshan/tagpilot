package com.ruoyi.taglibrary.service;

import java.time.Instant;
import java.util.*;
import java.util.regex.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.framework.web.service.PermissionService;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.taglibrary.domain.TsAgentThread;
import com.ruoyi.taglibrary.domain.TlTag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;

/** Java 在当前登录请求中处理 Agent 的分析请求；模型只能引用证据，不能提供 SQL 或事实值。 */
@Service
@SuppressWarnings("unchecked")
public class TsConversationAnalysisService {
    @Autowired private TsAudiencePlanCompiler compiler;
    @Autowired private TsTagStatsService stats;
    @Autowired private ITsCatalogRuntimeService catalog;
    @Autowired private ITlTagService tags;
    @Autowired private PermissionService permissions;
    @Autowired private ObjectMapper json;
    private static final Pattern REF=Pattern.compile("\\{fact:([a-z][a-z0-9_.-]{0,79})\\}");
    private Map<String,Object> obj(Object raw){return raw instanceof Map?(Map<String,Object>)raw:new LinkedHashMap<>();}
    private List<Map<String,Object>> rows(Object raw){return raw instanceof List?(List<Map<String,Object>>)raw:new ArrayList<>();}
    private String encode(Object raw){try{return json.writeValueAsString(raw);}catch(Exception e){throw new IllegalArgumentException("分析内容格式错误");}}
    private Map<String,Object> copy(Map<String,Object> raw){try{return json.readValue(encode(raw),Map.class);}catch(Exception e){throw new IllegalArgumentException("分析内容格式错误");}}
    private boolean stale(Map<String,Object> artifact,Map<String,Object> state) {
        return artifact.get("base_revision")!=null && !String.valueOf(artifact.get("base_revision")).equals(String.valueOf(state.get("revision")));
    }

    public Map<String,Object> begin(Map<String,Object> state,Map<String,Object> request) {
        Map<String,Object> session=map("queries",new ArrayList<>(),"query_calls",0,"query_ms",0,"blocks",new ArrayList<>(),"started_at",System.currentTimeMillis());
        String reply=request.get("reply_to_message_id") instanceof String?(String)request.get("reply_to_message_id"):null;
        List<Map<String,Object>> messages=rows(state.get("messages"));
        if(reply!=null && messages.stream().noneMatch(m->reply.equals(m.get("id"))))throw new ServiceException("引用的消息不属于当前会话",409);
        Map<String,Object> artifacts=obj(state.get("analysis_artifacts"));
        if(request.get("target_artifact_id")!=null) {
            String key=request.get("target_artifact_id")+"@"+request.get("target_artifact_version");
            Map<String,Object> target=obj(artifacts.get(key));
            if(target.isEmpty())throw new ServiceException("引用的图表不存在，请重新选择",409);
            session.put("target",copy(target));
        } else {
            for(int i=messages.size()-1;i>=0;i--) {
                Map<String,Object> message=messages.get(i);
                if(reply!=null&&!reply.equals(message.get("id")))continue;
                List<Map<String,Object>> charts=new ArrayList<>();
                for(Map<String,Object> part:rows(message.get("parts")))if("chart".equals(part.get("type"))) {
                    Map<String,Object> a=obj(artifacts.get(part.get("artifact_id")+"@"+part.get("artifact_version")));
                    // 客群已重新核验时，旧图只是历史证据；新问题按当前客群重新分析，不能因自动引用历史图而阻断。
                    if(!a.isEmpty() && !stale(a,state))charts.add(a);
                }
                if(charts.size()==1)session.put("target",copy(charts.get(0)));
                if(!charts.isEmpty()){session.put("artifact_choices",charts.stream().map(a->map("id",a.get("id"),"version",a.get("version"),"title",obj(a.get("spec")).get("title"))).collect(java.util.stream.Collectors.toList()));break;}
                if(reply!=null)break;
            }
        }
        Map<String,Object> prior=obj(state.get("analysis_state"));
        Map<String,Object> scope=obj(prior.get("plan"));
        if(scope.isEmpty())scope=obj(state.get("plan"));
        if(Boolean.TRUE.equals(scope.get("valid")))session.put("plan",copy(scope));
        Map<String,Object> target=obj(session.get("target"));
        if(!target.isEmpty()) {
            if(stale(target,state))throw new ServiceException("当前客群已变化，请重新分析后再调整图表",409);
            if(!obj(target.get("plan")).isEmpty())session.put("plan",copy(obj(target.get("plan"))));
            if(!obj(target.get("bundle")).isEmpty())session.put("bundle",copy(obj(target.get("bundle"))));
            if(target.get("query_plan") instanceof List)session.put("queries",copy(map("v",target.get("query_plan"))).get("v"));
        }
        return session;
    }

    public Map<String,Object> handle(TsAgentThread row,Map<String,Object> state,String tool,Map<String,Object> args) {
        if(!permissions.hasPermi("taglibrary:insight:run"))throw new ServiceException("没有洞察运行权限",403);
        Map<String,Object> request=obj(state.get("run_request")),session=obj(state.get("analysis_session"));
        if(session.isEmpty() || !"conversation".equals(request.get("profile")) || !"RUNNING".equals(state.get("status")))throw new ServiceException("分析运行已结束",409);
        Map<String,Object> active=catalog.activeBundle(row.getLibraryId());
        for(String key:Arrays.asList("build_id","snapshot_id","artifact_hash"))if(!Objects.equals(active.get(key),request.get(key)))throw new ServiceException("发布版本已变化，请重新运行",409);
        if(encode(args).length()>60000)throw new IllegalArgumentException("分析请求过大");
        if("get_analysis_context".equals(tool))return context(row,state,session,args);
        if("query_aggregates".equals(tool))return query(row,state,session,args);
        if("derive_facts".equals(tool))return derive(session,args);
        if("submit_insight_result".equals(tool))return submit(row,state,session,args);
        throw new IllegalArgumentException("分析工具未开放");
    }

    private Map<String,Object> context(TsAgentThread row,Map<String,Object> state,Map<String,Object> session,Map<String,Object> args) {
        if(args.get("target_artifact_id")!=null) {
            Map<String,Object> request=obj(state.get("run_request"));
            if(request.get("target_artifact_id")!=null && (!Objects.equals(request.get("target_artifact_id"),args.get("target_artifact_id")) || !String.valueOf(request.get("target_artifact_version")).equals(String.valueOf(args.get("target_artifact_version")))))throw new IllegalArgumentException("不能覆盖用户显式引用的图表");
            Map<String,Object> target=obj(obj(state.get("analysis_artifacts")).get(args.get("target_artifact_id")+"@"+args.get("target_artifact_version")));
            if(target.isEmpty())throw new IllegalArgumentException("图表不属于当前会话或版本不存在");
            if(target.get("base_revision")!=null&&!String.valueOf(target.get("base_revision")).equals(String.valueOf(state.get("revision"))))throw new IllegalArgumentException("该图属于历史客群，请先重新分析");
            session.put("target",copy(target));
            if(!obj(target.get("bundle")).isEmpty())session.put("bundle",copy(obj(target.get("bundle"))));
            if(!obj(target.get("plan")).isEmpty())session.put("plan",copy(obj(target.get("plan"))));
            if(target.get("query_plan") instanceof List)session.put("queries",copy(map("v",target.get("query_plan"))).get("v"));
        }
        if(args.get("plan") instanceof Map) {
            Map<String,Object> proposed=copy(obj(args.get("plan")));
            compiler.compile(row.getLibraryId(),proposed);proposed.put("valid",true);
            Map<String,Object> existing=obj(session.get("plan"));
            if(!existing.isEmpty()) {
                List<Map<String,Object>> parents=new ArrayList<>(rows(session.get("privacy_plans")));parents.add(copy(existing));
                if(parents.size()>6)parents.remove(0);session.put("privacy_plans",parents);
            }
            if("subset".equals(args.get("scope")) && !existing.isEmpty()) {
                if("SCOPE_ALL".equals(obj(existing.get("tree")).get("kind"))) { /* 全量的子集直接使用新条件。 */ }
                else {proposed=intersect(existing,proposed);compiler.compile(row.getLibraryId(),proposed);}
            }
            session.put("plan",proposed);session.remove("bundle");session.put("queries",new ArrayList<>());
        } else if("all".equals(args.get("scope"))) {
            session.put("plan",allPlan(obj(state.get("run_request"))));session.remove("bundle");session.put("queries",new ArrayList<>());
        }
        Map<String,Object> plan=obj(session.get("plan"));
        if(!plan.isEmpty())compiler.compile(row.getLibraryId(),plan);
        List<Map<String,Object>> suggestions=new ArrayList<>();
        List<?> requested=args.get("tag_ids") instanceof List?(List<?>)args.get("tag_ids"):Collections.emptyList();
        if(requested.size()>10)throw new IllegalArgumentException("每次最多核对10个标签");
        Set<Long> eligible=new HashSet<>(catalog.eligibleTagIds(row.getLibraryId(),String.valueOf(obj(state.get("run_request")).get("snapshot_id"))));
        for(Object raw:requested) {
            if(!(raw instanceof Number))throw new IllegalArgumentException("标签编号非法");Long id=((Number)raw).longValue();TlTag tag=tags.selectTagById(id);
            if(!eligible.contains(id)||tag==null||!row.getLibraryId().equals(tag.getLibraryId()))throw new ServiceException("分析标签无权限或已下线",403);
            suggestions.add(map("tag_id",id,"label",tag.getTagName(),"tag_type",tag.getTagType()));
        }
        Map<String,Object> target=obj(session.get("target"));
        return map("ok",true,"scope_ready",!plan.isEmpty(),"plan",plan,"selection_plan","selection".equals(args.get("scope"))&&args.get("plan") instanceof Map?plan:null,"tags",suggestions,"target",target.isEmpty()?null:map("id",target.get("id"),"version",target.get("version"),"spec",target.get("spec")),"artifact_choices",session.get("artifact_choices"),
            "bundle",session.get("bundle"),"query_plan",session.get("queries"),"max_tags",5,"max_dimensions",2,
            "note","使用find_tags和get_tag_details匹配指标与维度；无范围时先澄清。只读分析不改变圈选方案。当前不提供历史趋势、显著性检验或营销规则。");
    }
    private Map<String,Object> intersect(Map<String,Object> existing,Map<String,Object> incoming) {
        Map<String,Object> added=copy(incoming);String prefix="sub-"+UUID.randomUUID().toString().substring(0,6)+"-";
        rename(obj(added.get("tree")),prefix);
        Map<String,Object> ai=obj(added.get("intent_plan")),ei=obj(existing.get("intent_plan"));
        for(Map<String,Object> r:rows(ai.get("requirements")))r.put("requirement_id",prefix+r.get("requirement_id"));
        renameIntent(obj(ai.get("logic_tree")),prefix);
        for(Map<String,Object> a:rows(ai.get("assumptions")))a.put("requirement_id",prefix+a.get("requirement_id"));
        List<Map<String,Object>> requirements=new ArrayList<>(rows(ei.get("requirements")));requirements.addAll(rows(ai.get("requirements")));
        List<Map<String,Object>> assumptions=new ArrayList<>(rows(ei.get("assumptions")));assumptions.addAll(rows(ai.get("assumptions")));
        ai.put("requirements",requirements);ai.put("assumptions",assumptions);ai.put("logic_tree",map("logic","AND","children",Arrays.asList(ei.get("logic_tree"),ai.get("logic_tree"))));
        ai.put("original_request",String.valueOf(ei.get("original_request"))+"；并且 "+ai.get("original_request"));
        added.put("tree",map("logic","AND","children",Arrays.asList(existing.get("tree"),added.get("tree"))));
        added.put("summary",ai.get("original_request"));return added;
    }
    private void rename(Map<String,Object> node,String prefix) {
        if(node.containsKey("children")){for(Map<String,Object> child:rows(node.get("children")))rename(child,prefix);return;}
        node.put("clause_id",prefix+node.get("clause_id"));List<String> ids=new ArrayList<>();
        for(Object id:(List<?>)node.getOrDefault("requirement_ids",Collections.emptyList()))ids.add(prefix+id);node.put("requirement_ids",ids);
    }
    private void renameIntent(Map<String,Object> node,String prefix) {
        if(node.containsKey("children")){for(Map<String,Object> child:rows(node.get("children")))renameIntent(child,prefix);}
        else node.put("requirement_id",prefix+node.get("requirement_id"));
    }
    private Map<String,Object> allPlan(Map<String,Object> request) {
        return map("schema_version",3,"valid",true,"build_id",request.get("build_id"),"snapshot_id",request.get("snapshot_id"),"artifact_hash",request.get("artifact_hash"),
            "tree",map("kind","SCOPE_ALL","clause_id","analysis-all","source_span","当前授权范围全部客户","requirement_ids",Arrays.asList("analysis-all")),
            "intent_plan",map("original_request","当前授权范围全部客户","requirements",Arrays.asList(map("requirement_id","analysis-all","source_spans",Arrays.asList("当前授权范围全部客户"),"business_meaning","当前授权范围全部客户","origin","USER")),"logic_tree",map("requirement_id","analysis-all"),"assumptions",new ArrayList<>()));
    }
    private Map<String,Object> query(TsAgentThread row,Map<String,Object> state,Map<String,Object> session,Map<String,Object> args) {
        if(!permissions.hasPermi("objectgroup:group:run"))throw new ServiceException("没有聚合统计权限",403);
        Map<String,Object> plan=obj(session.get("plan"));if(plan.isEmpty())throw new IllegalArgumentException("请先确定分析客群");
        List<Map<String,Object>> added=rows(args.get("queries"));if(added.isEmpty())throw new IllegalArgumentException("请提供声明式查询");
        List<Map<String,Object>> active=new ArrayList<>(rows(session.get("queries")));
        for(Map<String,Object> q:added) {active.removeIf(v->Objects.equals(v.get("id"),q.get("id")));active.add(q);}
        if(encode(active).equals(encode(session.get("queries"))) && session.get("bundle") instanceof Map)return map("ok",true,"bundle",session.get("bundle"),"cached",true);
        int calls=((Number)session.getOrDefault("query_calls",0)).intValue();long elapsed=((Number)session.getOrDefault("query_ms",0)).longValue();
        if(calls>=6||elapsed>=30000||System.currentTimeMillis()-((Number)session.get("started_at")).longValue()>125000)throw new IllegalArgumentException("查询预算已用完，请提交已获得的证据");
        session.put("query_calls",calls+1);long started=System.currentTimeMillis();
        try {
            Map<String,RulePayload> scopes=new LinkedHashMap<>();scopes.put("target",compiler.compile(row.getLibraryId(),plan));
            int pi=0;for(Map<String,Object> parent:rows(session.get("privacy_plans")))scopes.put("privacy-"+pi++,compiler.compile(row.getLibraryId(),parent));
            if(active.stream().anyMatch(q->"all".equals(q.get("population"))))scopes.put("all",compiler.compile(row.getLibraryId(),allPlan(obj(state.get("run_request")))));
            Set<Long> eligible=new HashSet<>(catalog.eligibleTagIds(row.getLibraryId(),String.valueOf(obj(state.get("run_request")).get("snapshot_id"))));
            Map<String,Object> bundle=stats.analysisBatch(row.getLibraryId(),scopes,active,eligible);
            Map<String,Object> after=catalog.activeBundle(row.getLibraryId());
            for(String key:Arrays.asList("build_id","snapshot_id","artifact_hash"))if(!Objects.equals(after.get(key),obj(state.get("run_request")).get(key)))throw new ServiceException("发布版本在查询期间发生变化，请重新运行",409);
            session.put("queries",active);session.put("bundle",bundle);
            return map("ok",true,"bundle",bundle,"note","本批重算了全部活动查询；仅使用此snapshot_id的证据，不得混入上一批派生值");
        } finally {session.put("query_ms",elapsed+System.currentTimeMillis()-started);}
    }
    private Map<String,Object> derive(Map<String,Object> session,Map<String,Object> args) {
        Map<String,Object> bundle=obj(session.get("bundle"));Map<String,Map<String,Object>> facts=index(bundle);
        String id=String.valueOf(args.get("id")),op=String.valueOf(args.get("operation"));
        if(!id.matches("f-[a-z][a-z0-9-]{0,50}")||facts.containsKey(id))throw new IllegalArgumentException("派生事实标识非法或重复");
        List<?> refs=args.get("fact_ids") instanceof List?(List<?>)args.get("fact_ids"):Collections.emptyList();
        if(refs.size()!=2)throw new IllegalArgumentException("派生计算需要两个事实");
        Map<String,Object> a=facts.get(String.valueOf(refs.get(0))),b=facts.get(String.valueOf(refs.get(1)));
        if(a==null||b==null)throw new IllegalArgumentException("派生来源不属于当前证据批次");
        double x=((Number)a.get("value")).doubleValue(),y=((Number)b.get("value")).doubleValue(),value;String unit=String.valueOf(a.get("unit"));
        if(!Objects.equals(a.get("unit"),b.get("unit")))throw new IllegalArgumentException("派生来源单位不同");
        if("difference".equals(op)&&(a.get("definition_key")==null||!Objects.equals(a.get("definition_key"),b.get("definition_key"))))throw new IllegalArgumentException("差值来源不是同口径指标或旧证据缺少口径标识，请重新取数后比较");
        if("ratio".equals(op)&&(!String.valueOf(b.get("query_id")).endsWith(".total")||!String.valueOf(a.get("query_id")).startsWith(String.valueOf(b.get("query_id")).replace(".total","."))))throw new IllegalArgumentException("比例须引用同一查询的分子与总体人数");
        if("difference".equals(op)){value=x-y;if("%".equals(unit))unit="pp";}
        else if("ratio".equals(op)){if(y<=0||x<0||x>y||!Objects.equals(a.get("role"),b.get("role")))throw new IllegalArgumentException("比例分母或范围非法");value=x/y*100;unit="%";}
        else throw new IllegalArgumentException("派生操作未开放");
        if(!Double.isFinite(value))throw new IllegalArgumentException("派生计算结果超出数值范围");
        Map<String,Object> fact=map("id",id,"metric","derived."+id,"label",plain(args.get("label"),80),"value",Math.round(value*100d)/100d,"unit",unit,"sample_size",Math.min(((Number)a.get("sample_size")).longValue(),((Number)b.get("sample_size")).longValue()),
            "status","AVAILABLE","query_id","derived."+id,"evidence",Arrays.asList("服务端同批证据确定性计算"),"role","DERIVED","denominator_id","ratio".equals(op)?refs.get(1):null,"derived_from","ratio".equals(op)?Arrays.asList(refs.get(0)):refs,"exclusions_applied",new ArrayList<>());
        rows(bundle.get("facts")).add(fact);return map("ok",true,"fact",fact,"snapshot_id",bundle.get("snapshot_id"));
    }
    private Map<String,Map<String,Object>> index(Map<String,Object> bundle) {
        Map<String,Map<String,Object>> out=new LinkedHashMap<>();for(Map<String,Object> f:rows(bundle.get("facts")))out.put(String.valueOf(f.get("id")),f);return out;
    }
    private String plain(Object raw,int limit) {
        if(!(raw instanceof String)||((String)raw).trim().isEmpty()||((String)raw).length()>limit||Pattern.compile("<[a-zA-Z!/]").matcher((String)raw).find())throw new IllegalArgumentException("展示文字缺失、过长或包含未允许标记");
        return ((String)raw).trim();
    }
    private String bindLiteralFacts(String text,Map<String,Map<String,Object>> facts) {
        if(text==null||text.isEmpty())return text;
        String out=text;
        List<Map.Entry<String,Map<String,Object>>> ordered=new ArrayList<>(facts.entrySet());
        ordered.sort((a,b)->Integer.compare(replacementPriority(b.getValue()),replacementPriority(a.getValue())));
        for(Map.Entry<String,Map<String,Object>> entry:ordered) {
            Map<String,Object> fact=entry.getValue();
            if(!"AVAILABLE".equals(fact.get("status"))||!(fact.get("value") instanceof Number))continue;
            String id=entry.getKey(),placeholder="{fact:"+id+"}";
            if(out.contains(placeholder))continue;
            double raw=((Number)fact.get("value")).doubleValue();
            String unit=String.valueOf(fact.get("unit"));
            String plain=new java.math.BigDecimal(String.valueOf(fact.get("value"))).stripTrailingZeros().toPlainString();
            LinkedHashSet<String> literals=new LinkedHashSet<>();
            literals.add(plain+unit);literals.add(plain);
            if("人".equals(unit)) {literals.add(plain+"名");literals.add(plain+"人");}
            if("元".equals(unit)&&raw>=10000) {
                long wan=Math.round(raw/10000d);
                if(Math.abs(wan*10000-raw)<1)literals.add(wan+"万元");
            }
            List<String> ranked=new ArrayList<>(literals);
            ranked.sort((a,b)->Integer.compare(b.length(),a.length()));
            for(String literal:ranked) {
                if(literal.length()<2||!out.contains(literal))continue;
                out=out.replace(literal,placeholder);
                break;
            }
        }
        return out;
    }
    private int replacementPriority(Map<String,Object> fact) {
        Object value=fact.get("value");
        return value instanceof Number?String.valueOf(((Number)value).longValue()).length():0;
    }
    private String statement(Object raw,Map<String,Map<String,Object>> facts) {
        String text=bindLiteralFacts(plain(raw,3000),facts);Matcher match=REF.matcher(text);StringBuffer out=new StringBuffer();
        while(match.find()) {
            Map<String,Object> fact=facts.get(match.group(1));if(fact==null)throw new IllegalArgumentException("陈述引用了不存在的证据");
            String unit=String.valueOf(fact.get("unit"));
            String value=new java.math.BigDecimal(String.valueOf(fact.get("value"))).stripTrailingZeros().toPlainString();
            boolean suppliedUnit=text.startsWith(unit,match.end()) || "%".equals(unit)&&text.startsWith("％",match.end());
            match.appendReplacement(out,Matcher.quoteReplacement(value+(suppliedUnit?"":unit)));
        }
        match.appendTail(out);
        String unbound=REF.matcher(text).replaceAll("");
        // 已核验指标名中的“近30天”等数字属于口径，不能迫使模型改写为“近一个月”。
        Set<String> metricNames=new TreeSet<>((a,b)->a.length()==b.length()?a.compareTo(b):Integer.compare(b.length(),a.length()));
        for(Map<String,Object> fact:facts.values())if(Arrays.asList("OBSERVED","BENCHMARK").contains(fact.get("role")) && fact.get("label") instanceof String)
            for(String name:((String)fact.get("label")).split("\\s*·\\s*"))if(name.length()>=4)metricNames.add(name);
        for(String name:metricNames)unbound=unbound.replace(name,"");
        if(Pattern.compile("[0-9０-９]|[零一二三四五六七八九十百千万亿两]+(?:成|人|元|万元|亿元)").matcher(unbound).find())throw new IllegalArgumentException("业务数字必须使用{fact:id}引用");
        return out.toString();
    }
    private Map<String,Object> submit(TsAgentThread row,Map<String,Object> state,Map<String,Object> session,Map<String,Object> args) {
        if(Boolean.TRUE.equals(session.get("submitted")))throw new IllegalArgumentException("本轮已提交");
        List<Map<String,Object>> candidates=rows(args.get("blocks"));if(candidates.isEmpty()||candidates.size()>12)throw new IllegalArgumentException("每次提交1至12个内容块");
        Map<String,Object> bundle=obj(session.get("bundle"));Map<String,Map<String,Object>> facts=index(bundle);
        List<Map<String,Object>> parts=new ArrayList<>();Map<String,Object> staged=new LinkedHashMap<>();
        Map<String,Object> stored=obj(state.get("analysis_artifacts"));
        for(Map<String,Object> block:candidates) {
            String type=String.valueOf(block.get("type"));Map<String,Object> part=map("id",UUID.randomUUID().toString(),"type",type,"status","COMPLETE","version",1);
            if("text".equals(type)) {
                String basis=String.valueOf(block.getOrDefault("basis","OBSERVED"));if(!Arrays.asList("OBSERVED","HYPOTHESIS").contains(basis))throw new IllegalArgumentException("当前没有规则或统计检验依据");
                String text=statement(block.get("text"),facts);
                if("OBSERVED".equals(basis)&&Pattern.compile("因为|导致|显著|必然|转化率将|预计收益|右偏|左偏|长尾").matcher(text).find())throw new IllegalArgumentException("原因或分布形态解释须标记为待验证假设，不能声称显著或收益");
                part.put("text",("HYPOTHESIS".equals(basis)?"待验证假设：":"")+("HYPOTHESIS".equals(basis)?text.replaceFirst("^(待验证假设|待验证解释|假设)[：:]\\s*",""):text));
            } else if("clarification".equals(type)) {
                part.put("prompt",plain(block.get("prompt"),500));List<String> options=new ArrayList<>();
                for(Object option:(List<?>)block.getOrDefault("options",Collections.emptyList())){if(options.size()>=6)break;options.add(plain(option,150));}part.put("options",options);
            } else if(Arrays.asList("chart","table").contains(type)) {
                Map<String,Object> artifact;
                if(Boolean.TRUE.equals(block.get("view_only")))artifact=edit(session,block,stored);
                else {
                    if(bundle.isEmpty())throw new IllegalArgumentException("尚无可用数据，不能绘图");
                    Map<String,Object> spec=chart(bundle,block);
                    artifact=map("id",UUID.randomUUID().toString(),"version",1,"spec",spec,"facts",bundle.get("facts"),"bundle",copy(bundle),"plan",session.get("plan"),"query_plan",session.get("queries"),"snapshot_id",bundle.get("snapshot_id"),"created_at",Instant.now().toString(),"parent_id",obj(session.get("target")).get("id"),
                        "base_revision",state.get("revision"),"base_plan_hash",obj(state.get("plan")).get("hash"),"context",obj(session.get("plan")).getOrDefault("summary",obj(obj(session.get("plan")).get("intent_plan")).getOrDefault("original_request","当前已核验客群")));
                }
                String key=artifact.get("id")+"@"+artifact.get("version");staged.put(key,artifact);part.put("artifact_id",artifact.get("id"));part.put("artifact_version",artifact.get("version"));
            } else throw new IllegalArgumentException("内容块类型未开放");
            parts.add(part);
        }
        if(stored.size()+staged.size()>200)throw new IllegalArgumentException("会话图表已达上限，请新建会话");
        List<Map<String,Object>> accumulated=new ArrayList<>(rows(session.get("blocks")));accumulated.addAll(parts);
        if(accumulated.size()>30)throw new IllegalArgumentException("本轮内容块已达上限");
        stored.putAll(staged);state.put("analysis_artifacts",stored);session.put("blocks",accumulated);
        boolean complete=!Boolean.FALSE.equals(args.get("complete"));session.put("submitted",complete);
        state.put("analysis_state",map("plan",session.get("plan"),"query_plan",session.get("queries"),"snapshot_id",bundle.get("snapshot_id")));
        return map("ok",true,"parts",parts,"complete",complete);
    }
    private Map<String,Object> edit(Map<String,Object> session,Map<String,Object> block,Map<String,Object> stored) {
        Map<String,Object> target=obj(session.get("target"));if(target.isEmpty())throw new IllegalArgumentException("请先选择要调整的图表，多张图时不能猜测");
        Map<String,Object> result=copy(target),spec=obj(result.get("spec"));String kind=String.valueOf(block.getOrDefault("kind",spec.get("kind")));
        if(!Arrays.asList("bar","table").contains(kind)||!Arrays.asList("bar","table").contains(spec.get("kind")))throw new IllegalArgumentException("此图暂只支持条形图和数据表互换");
        spec.put("kind",kind);String orientation=String.valueOf(block.getOrDefault("orientation",spec.get("orientation")));
        if(!Arrays.asList("horizontal","vertical").contains(orientation))throw new IllegalArgumentException("图表方向非法");spec.put("orientation",orientation);
        if("descending".equals(block.get("sort"))) {
            List<Map<String,Object>> series=rows(spec.get("series"));Map<String,Double> weights=new HashMap<>();
            for(Map<String,Object> s:series)for(Map<String,Object> p:rows(s.get("points")))weights.merge(String.valueOf(p.get("category")),((Number)p.get("value")).doubleValue(),Double::sum);
            for(Map<String,Object> s:series)rows(s.get("points")).sort((a,b)->Double.compare(weights.get(String.valueOf(b.get("category"))),weights.get(String.valueOf(a.get("category")))));
        }
        int version=((Number)target.get("version")).intValue()+1;while(stored.containsKey(target.get("id")+"@"+version))version++;
        result.put("version",version);result.put("parent_version",target.get("version"));result.put("created_at",Instant.now().toString());return result;
    }
    private Map<String,Object> chart(Map<String,Object> bundle,Map<String,Object> block) {
        Map<String,Map<String,Object>> queries=new LinkedHashMap<>();for(Map<String,Object> q:rows(bundle.get("queries")))queries.put(String.valueOf(q.get("id")),q);
        List<?> requested=block.get("query_ids") instanceof List?(List<?>)block.get("query_ids"):Collections.emptyList();
        if(requested.isEmpty()||requested.size()>8)throw new IllegalArgumentException("图表须引用1至8个查询");
        boolean share=Boolean.TRUE.equals(block.get("share"));List<Map<String,Object>> series=new ArrayList<>();String unit=null,label="";boolean matrix=false;int pointCount=0;
        Map<String,Map<String,Object>> facts=index(bundle);
        if("stacked_bar".equals(block.get("kind")))return composition(bundle,block,requested,queries,facts);
        for(Object id:requested) {
            Map<String,Object> q=queries.get(String.valueOf(id));if(q==null||!"AVAILABLE".equals(q.get("status")))throw new IllegalArgumentException("图表引用了缺失或被抑制的查询");
            String u=share?"%":String.valueOf(q.get("unit"));if(unit!=null&&!unit.equals(u))throw new IllegalArgumentException("图表系列单位不同");unit=u;label=String.valueOf(q.get("metric_label"));
            List<Map<String,Object>> points=new ArrayList<>();List<String> fids=new ArrayList<>();
            for(Map<String,Object> r:rows(q.get("rows"))) {
                String fid=String.valueOf(r.get(share?"share_fact_id":"fact_id"));Map<String,Object> f=facts.get(fid);if(f==null)throw new IllegalArgumentException("图表缺少可用事实或占比分母");
                points.add(map("category",shortLabel(r.get("category")),"column",r.get("column")==null?null:shortLabel(r.get("column")),"fact_id",fid,"value",f.get("value")));fids.add(fid);matrix|=r.get("column")!=null;pointCount++;
            }
            if(points.isEmpty())throw new IllegalArgumentException("查询没有可绘制的数值");
            series.add(map("name",shortLabel(("all".equals(q.get("population"))?"全量客户":"当前客群")+(requested.size()>1?" · "+q.get("metric_label"):"")),"fact_ids",fids,"points",points));
        }
        String kind=String.valueOf(block.getOrDefault("kind","table".equals(block.get("type"))?"table":matrix?"heatmap":pointCount==1?"kpi":"bar"));
        if(!Arrays.asList("kpi","table","bar","heatmap").contains(kind))throw new IllegalArgumentException("当前证据支持KPI、表格、条形图或热力图");
        if(matrix&&!("heatmap".equals(kind)||"table".equals(kind)))throw new IllegalArgumentException("二维查询须用热力图或表格");
        if("heatmap".equals(kind)&&(!matrix||series.size()!=1)||"kpi".equals(kind)&&pointCount!=1)throw new IllegalArgumentException("图型与证据结构不符");
        String orientation=String.valueOf(block.getOrDefault("orientation","vertical"));if(!Arrays.asList("horizontal","vertical").contains(orientation))throw new IllegalArgumentException("方向非法");
        return map("schema_version",1,"id","chart-"+UUID.randomUUID().toString().substring(0,8),"title",statement(block.get("title"),facts),"kind",kind,"intent",matrix?"show_matrix":pointCount==1?"single_value":"compare_categories",
            "unit",unit,"metric_label",share?"客户占比":shortLabel(label),"series",series,"annotations",new ArrayList<>(),"reconcile",new ArrayList<>(),"zero_baseline",true,"orientation",orientation);
    }
    private String shortLabel(Object raw){String text=String.valueOf(raw);if(text.isEmpty())return "未登记";return text.length()>24?text.substring(0,23)+"…":text;}
    private Map<String,Object> composition(Map<String,Object> bundle,Map<String,Object> block,List<?> requested,Map<String,Map<String,Object>> queries,Map<String,Map<String,Object>> facts) {
        if(requested.size()!=1)throw new IllegalArgumentException("构成图须来自同一组互斥分类查询");
        Map<String,Object> q=queries.get(String.valueOf(requested.get(0)));
        if(q==null||!"AVAILABLE".equals(q.get("status"))||!Arrays.asList("count","distribution").contains(q.get("operation")))throw new IllegalArgumentException("不能堆叠非互斥指标或均值");
        List<?> dims=q.get("dimensions") instanceof List?(List<?>)q.get("dimensions"):Collections.emptyList();
        boolean share=Boolean.TRUE.equals(block.get("share"));if(dims.size()!=1)throw new IllegalArgumentException("构成图目前只支持单维度完整分类");
        List<Map<String,Object>> series=new ArrayList<>();List<String> ids=new ArrayList<>();
        for(Map<String,Object> r:rows(q.get("rows"))) {
            String fid=String.valueOf(r.get(share?"share_fact_id":"fact_id"));Map<String,Object> fact=facts.get(fid);if(fact==null)throw new IllegalArgumentException("构成图缺少事实或分母");
            ids.add(fid);series.add(map("name",shortLabel(r.get("category")),"fact_ids",Arrays.asList(fid),"points",Arrays.asList(map("category","客群构成","column",null,"fact_id",fid,"value",fact.get("value")))));
        }
        if(series.isEmpty()||series.size()>8)throw new IllegalArgumentException("构成图最多展示8个完整分类，不能静默省略其他类别");
        return map("schema_version",1,"id","chart-"+UUID.randomUUID().toString().substring(0,8),"title",statement(block.get("title"),facts),"kind","stacked_bar","intent","show_composition","unit",share?"%":"人","metric_label",share?"客户占比":"客户数","series",series,
            "annotations",new ArrayList<>(),"reconcile",Arrays.asList(map("kind",share?"percentage":"sum","fact_ids",ids,"total_fact_id",share?null:q.get("total_fact_id"),"tolerance",.05)),"zero_baseline",true,"orientation","horizontal");
    }
}
