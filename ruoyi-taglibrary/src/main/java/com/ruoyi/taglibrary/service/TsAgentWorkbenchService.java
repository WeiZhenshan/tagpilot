package com.ruoyi.taglibrary.service;

import java.util.*;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.taglibrary.domain.agent.TsPlanValidationException;
import com.ruoyi.taglibrary.domain.agent.TsAgentOutcome;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.framework.web.service.PermissionService;
import com.ruoyi.objectgroup.domain.*;
import com.ruoyi.objectgroup.domain.vo.RuleRunResultVO;
import com.ruoyi.objectgroup.service.ITlObjectGroupService;
import com.ruoyi.taglibrary.domain.*;
import com.ruoyi.taglibrary.mapper.*;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;

/** 业务状态由 Java 保存，Python 负责可恢复的编排与事件。每次操作重新校验归属和版本。 */
@Service
@SuppressWarnings("unchecked")
public class TsAgentWorkbenchService {
    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(TsAgentWorkbenchService.class);
    @Autowired private TsAgentThreadMapper threads;
    @Autowired private ObjectMapper json;
    @Autowired private DataBrokerCryptoService crypto;
    @Autowired private PermissionService permissions;
    @Autowired private ITlTagLibraryService libraries;
    @Autowired private ITsCatalogRuntimeService catalog;
    @Autowired private TsAgentClient agent;
    @Autowired private TsAudiencePlanCompiler compiler;
    @Autowired private ITlObjectGroupService groups;
    @Autowired private ITlTagService tags;
    @Autowired private TsInsightRegistryService insightRegistry;
    @Autowired private TsAgentSkillService agentSkills;
    @Autowired private TsTagStatsService tagStats;

    private Long uid() { return SecurityUtils.getUserId(); }
    private String id() { return UUID.randomUUID().toString(); }
    private long number(Object n) { return n==null?0:Long.parseLong(String.valueOf(n)); }
    private Map<String,Object> obj(Object value) { return value instanceof Map?(Map<String,Object>)value:new LinkedHashMap<>(); }
    private List<Map<String,Object>> list(Object value) { return value instanceof List?(List<Map<String,Object>>)value:new ArrayList<>(); }
    private String encode(Object value) { try{return json.writeValueAsString(value);}catch(Exception e){throw new ServiceException("状态序列化失败");} }
    private Map<String,Object> data(TsAgentThread row) { try{return json.readValue(crypto.decrypt(row.getPayload()),Map.class);}catch(Exception e){throw new ServiceException("会话读取失败，请检查存储密钥");} }
    private void save(TsAgentThread row,Map<String,Object> state) {
        row.setPayload(crypto.encrypt(encode(state)));
        if (threads.update(row)!=1) throw new ServiceException("会话已在其他页面更新，请刷新",409);
        row.setRowVersion(row.getRowVersion()+1);
    }
    private void visible(Long library) {
        if (!permissions.hasAnyPermi("taglibrary:library:list,taglibrary:library:query") || libraries.selectLibraryById(library)==null)
            throw new ServiceException("无权访问该标签库",403);
    }
    private TsAgentThread owned(String thread) {
        TsAgentThread row=threads.lock(thread,uid());
        if(row==null)throw new ServiceException("会话不存在或无权访问",404);
        visible(row.getLibraryId()); return row;
    }
    private void revision(Map<String,Object> state,Map<String,Object> request) {
        if(!request.containsKey("base_revision") || number(request.get("base_revision"))!=number(state.get("revision")))
            throw new ServiceException("方案已更新，请刷新后重试",409);
    }
    private void idle(Map<String,Object> state) {
        if(Arrays.asList("RUNNING","WAITING","SUBMITTING").contains(String.valueOf(state.get("status"))))
            throw new ServiceException("请先完成或停止当前运行",409);
    }
    private void applyPlan(Map<String,Object> state,Map<String,Object> plan) {
        long next=number(state.get("revision"))+1;
        plan.remove("hash");plan.put("revision",next);plan.put("hash",TsSnapshotCanonicalizer.sha256(encode(plan)));
        state.put("revision",next);state.put("plan",plan);state.remove("live_plan");state.remove("count");state.remove("execution");
        if(Boolean.TRUE.equals(plan.get("valid")))state.remove("source_requires_validation");
        List<Map<String,Object>> versions=list(state.get("versions"));versions.add(plan);state.put("versions",versions);
    }
    private void savedConfirmations(Map<String,Object> node,Set<String> ids) {
        if(node.containsKey("children")) {for(Map<String,Object> child:list(node.get("children")))savedConfirmations(child,ids);}
        else if(Boolean.TRUE.equals(node.get("assumption_confirmed")) && node.get("clause_id")!=null)ids.add(String.valueOf(node.get("clause_id")));
    }
    private Map<String,Object> view(TsAgentThread row,Map<String,Object> state) {
        Map<String,Object> out=new LinkedHashMap<>(state);
        out.putAll(map("thread_id",row.getThreadId(),"library_id",row.getLibraryId(),"title",row.getTitle(),"archived","1".equals(row.getArchived()),"pinned","1".equals(row.getPinned()),
            "capabilities",map("insight",permissions.hasPermi("taglibrary:insight:run"),"count",permissions.hasPermi("objectgroup:group:run"),"create",permissions.hasPermi("objectgroup:group:add"),"update",permissions.hasPermi("objectgroup:group:edit"),"preview",permissions.hasPermi("objectgroup:group:preview"))));
        if(!permissions.hasPermi("taglibrary:insight:run") || (out.get("insight_report") instanceof Map && !insightRegistry.reportVisible(row.getLibraryId(),obj(out.get("insight_report")))))out.remove("insight_report");
        out.remove("run_request");out.remove("source_plan"); return out;
    }
    /** 仅暴露当前发布且仍可执行的轻量标签树，不要求标签管理权限。 */
    public List<Map<String,Object>> tagTree(Long library) {
        visible(library);
        Map<String,Object> bundle=catalog.activeBundle(library);
        Set<Long> eligible=new HashSet<>(catalog.eligibleTagIds(library,String.valueOf(bundle.get("snapshot_id"))));
        return pruneTags(tags.buildTree(library,"online"),eligible,"");
    }
    private List<Map<String,Object>> pruneTags(List<Map<String,Object>> nodes,Set<Long> eligible,String path) {
        List<Map<String,Object>> out=new ArrayList<>();
        for(Map<String,Object> node:nodes) {
            String key=String.valueOf(node.get("id")),label=String.valueOf(node.get("label"));
            if(key.startsWith("tag-")) {
                Long tagId=Long.valueOf(key.substring(4));
                if(eligible.contains(tagId))out.add(map("id",key,"tagId",tagId,"label",label,"tagType",node.get("tagType"),"dirPath",path));
            } else {
                List<Map<String,Object>> children=pruneTags(list(node.get("children")),eligible,path.isEmpty()?label:path+" / "+label);
                if(!children.isEmpty())out.add(map("id",key,"label",label,"children",children));
            }
        }
        return out;
    }
    private List<Long> contextIds(Map<String,Object> request) {
        Object raw=request.get("context_tag_ids");
        if(raw==null)return new ArrayList<>();
        if(!(raw instanceof List) || ((List<?>)raw).size()>5)throw new ServiceException("每轮最多选择5个标签");
        Set<Long> ids=new TreeSet<>();
        for(Object value:(List<?>)raw) {
            if(!(value instanceof Number) || !String.valueOf(value).matches("[1-9][0-9]*"))throw new ServiceException("标签编号非法");
            ids.add(number(value));
        }
        return new ArrayList<>(ids);
    }
    /** 请求里的 baseline_group_id 与已持久化请求里的 cohort_context.baseline.group_id 指向同一编号。 */
    private String baselineOf(Map<String,Object> source) {
        Object direct=source.get("baseline_group_id");
        Object groupId=direct!=null?direct:obj(obj(source.get("cohort_context")).get("baseline")).get("group_id");
        return groupId==null?null:String.valueOf(groupId);
    }
    public List<TsAgentThread> listThreads(boolean archived) {
        return threads.list(uid(),archived?"1":"0");
    }
    @Transactional
    public Map<String,Object> create(Long library) {
        visible(library); TsAgentThread row=new TsAgentThread();
        row.setThreadId(id());row.setUserId(uid());row.setLibraryId(library);row.setTitle("新的圈选");row.setArchived("0");row.setPinned("0");row.setRowVersion(0L);
        Map<String,Object> state=map("revision",0,"messages",new ArrayList<>(),"versions",new ArrayList<>(),"events",new ArrayList<>(),"status","IDLE");
        row.setPayload(crypto.encrypt(encode(state)));threads.insert(row);return view(row,state);
    }
    @Transactional
    public Map<String,Object> get(String thread) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        sync(row,state);return view(row,state);
    }
    private void sync(TsAgentThread row,Map<String,Object> state) {
        String run=(String)state.get("run_id");
        if(run==null || Arrays.asList("COMPLETED","CANCELLED","IDLE").contains(String.valueOf(state.get("status"))))return;
        Map<String,Object> remote=agent.get("/agent/v2/runs/"+run+"?owner_id="+uid()+"&after="+number(state.get("cursor")));
        List<Map<String,Object>> events=list(state.get("events"));
        for(Map<String,Object> event:list(remote.get("events"))) {
            events.add(event); state.put("cursor",event.get("seq"));
            if(event.get("plan") instanceof Map)state.put("live_plan",event.get("plan"));
        }
        state.put("events",events);state.put("status",remote.get("status"));state.put("error",remote.get("error"));
        Map<String,Object> result=obj(remote.get("result"));
        String resultKey=run+":"+remote.get("status")+":"+TsSnapshotCanonicalizer.sha256(encode(result));
        if(!"RUNNING".equals(remote.get("status")) && !result.isEmpty() && !resultKey.equals(state.get("applied_result"))) {
            if("skill".equals(obj(state.get("run_request")).get("profile"))) {
                List<Map<String,Object>> messages=list(state.get("messages"));
                String answer=String.valueOf(result.getOrDefault("skill_output","技能运行结束，请查看处理记录。"));
                messages.add(map("id",id(),"role","assistant","text",answer,"revision",state.get("revision"),"run_id",run,"created_at",Instant.now().toString()));
                state.put("messages",messages);
                Map<String,Object> report=skillReport(row,state,result,run);
                if(report!=null)state.put("skill_report",report);
                state.put("applied_result",resultKey);save(row,state);return;
            }
            Map<String,Object> plan=obj(result.get("plan"));
            if(plan.containsKey("tree")) {
                try { if(Boolean.TRUE.equals(plan.get("valid"))) groups.buildRuleSql(row.getLibraryId(),compiler.compile(row.getLibraryId(),plan)); }
                catch(ServiceException e) {
                    plan.put("valid",false);plan.put("plan_status","DRAFT");
                    String code=e instanceof TsPlanValidationException?((TsPlanValidationException)e).getDiagnosticCode():"AUTHORITATIVE_VALIDATION";
                    String clauseId=e instanceof TsPlanValidationException?((TsPlanValidationException)e).getClauseId():null;
                    List<Map<String,Object>> errors=Arrays.asList(map("code",code,"clause_id",clauseId,"message",e.getMessage(),"source","JAVA_AUTHORITY","user_decision_required",false));
                    plan.remove("validation_errors");plan.put("diagnostics",errors);
                    if(number(state.get("authority_repairs"))<2 && !Arrays.asList("VERSION_MISMATCH","INELIGIBLE_TAG","PERMISSION_DENIED","BUSINESS_AMBIGUITY").contains(code)) {
                        try {
                            agent.post("/agent/v2/runs/"+run+"/repair",map("owner_id",String.valueOf(uid()),"diagnostics",errors,"confirmed_clause_ids",state.getOrDefault("confirmed_clause_ids",new ArrayList<>()),
                                "eligible_tag_ids",catalog.eligibleTagIds(row.getLibraryId(),String.valueOf(plan.get("snapshot_id")))));
                            state.put("authority_repairs",number(state.get("authority_repairs"))+1);state.put("status","RUNNING");
                        } catch(ServiceException repairError) { /* 原方案及权威诊断已保留，不阻塞会话读取。 */ }
                    }
                }
                applyPlan(state,plan);
            }
            if(result.get("outcome") instanceof Map) {
                TsAgentOutcome outcome=json.convertValue(result.get("outcome"),TsAgentOutcome.class);
                outcome.setQuestions(list(result.get("questions")));state.put("outcome",json.convertValue(outcome,Map.class));
            }
            state.put("questions",result.get("questions"));state.put("interrupt_id",result.get("interrupt_id"));state.put("applied_result",resultKey);
            if(result.get("clarification_state") instanceof Map)state.put("clarification_state",result.get("clarification_state"));
            List<Map<String,Object>> messages=list(state.get("messages"));
            messages.add(map("id",id(),"role","assistant","text","RUNNING".equals(state.get("status"))?"正在根据服务端核验结果继续修复方案。":"WAITING".equals(remote.get("status"))?"有一项业务解释需要你决定，请在下方选择或补充。":Boolean.TRUE.equals(plan.get("valid"))?"圈选方案已生成，可以核对条件并统计人数。":"CAPABILITY_GAP".equals(plan.get("plan_status"))?"需求已保留，当前数据或计算能力还不能覆盖全部条件。右侧列出了具体缺口。":"方案和处理进度已保留，右侧列出了尚未完成的条件。",
                "revision",state.get("revision"),"run_id",run,"created_at",Instant.now().toString()));state.put("messages",messages);
        }
        save(row,state);
    }
    private static final List<String> SKILL_STATUSES=Arrays.asList("COMPLETE","PARTIAL","BLOCKED");
    private static final List<String> SKILL_UNITS=Arrays.asList("人","元","%","pp","分");
    private static final List<String> SKILL_KINDS=Arrays.asList("kpi","table","bar","stacked_bar","heatmap","funnel");
    private static final List<String> SKILL_BASIS=Arrays.asList("RULE","STAT","HYPOTHESIS");
    private static final List<String> SKILL_PRIORITIES=Arrays.asList("HIGH","MEDIUM","LOW","NONE");
    private static final Pattern SKILL_FACT_ID=Pattern.compile("[a-z][a-z0-9_.-]{0,79}");
    private static final Pattern SKILL_FACT_REF=Pattern.compile("\\{fact:([a-z][a-z0-9_.-]{0,79})\\}");

    /** 技能结果块经服务端校验后组装为洞察面板可渲染的报告；校验不通过的部分按条丢弃。 */
    private Map<String,Object> skillReport(TsAgentThread row,Map<String,Object> state,Map<String,Object> result,String run) {
        if(!(result.get("skill_result") instanceof Map))return null;
        Map<String,Object> skill=obj(result.get("skill_result"));
        String status=String.valueOf(skill.get("status"));
        if(!SKILL_STATUSES.contains(status) || encode(skill).length()>200000)return null;
        Map<String,Object> request=obj(state.get("run_request")),cohort=obj(request.get("cohort_context")),plan=obj(cohort.get("plan")),count=obj(cohort.get("count"));
        Map<String,Object> pack=null;
        for(Map<String,Object> entry:list(request.get("skill_packages")))if(Objects.equals(entry.get("name"),request.get("skill_name")))pack=entry;
        if(pack==null)return null;
        List<Map<String,Object>> facts=new ArrayList<>();Map<String,Map<String,Object>> factIndex=new LinkedHashMap<>();
        Map<String,Double> allowedTagStats=allowedTagStats(cohort);
        for(Map<String,Object> fact:list(skill.get("facts"))) {
            String factId=String.valueOf(fact.get("id")),factStatus=String.valueOf(fact.get("status"));
            if(facts.size()>=300 || !SKILL_FACT_ID.matcher(factId).matches() || factIndex.containsKey(factId))continue;
            if(!Arrays.asList("AVAILABLE","SUPPRESSED","MISSING").contains(factStatus) || !SKILL_UNITS.contains(String.valueOf(fact.get("unit"))))continue;
            Object value=fact.get("value");
            if("AVAILABLE".equals(factStatus)) { if(!(value instanceof Number) || !Double.isFinite(((Number)value).doubleValue()))continue; }
            else if(value!=null)continue;
            if(!tagStatMatches(fact,allowedTagStats))continue;
            facts.add(fact);factIndex.put(factId,fact);
        }
        List<Map<String,Object>> charts=new ArrayList<>();
        for(Map<String,Object> chart:list(skill.get("charts")))if(charts.size()<30 && SKILL_KINDS.contains(String.valueOf(chart.get("kind"))))charts.add(chart);
        String version=String.valueOf(pack.getOrDefault("version","")),dataAsOf=dataAsOf(count);
        if(dataAsOf.isEmpty())dataAsOf=dataAsOf(obj(state.get("count")));
        List<Map<String,Object>> cards=new ArrayList<>();
        for(Map<String,Object> card:list(skill.get("cards"))) {
            if(cards.size()>=30)break;
            Map<String,Object> diagnosis=obj(card.get("diagnosis")),action=obj(card.get("action"));
            if(!skillStatement(card.get("facts"),factIndex) || !skillStatement(card.get("comparison"),factIndex) || !skillStatement(diagnosis,factIndex) || !skillStatement(action,factIndex))continue;
            if(!SKILL_BASIS.contains(String.valueOf(diagnosis.get("basis"))) || !SKILL_PRIORITIES.contains(String.valueOf(action.getOrDefault("priority","NONE"))))continue;
            if(!(card.get("boundary") instanceof Map) || !(obj(card.get("boundary")).get("text") instanceof String))continue;
            Map<String,Object> boundary=obj(card.get("boundary"));
            boundary.put("skill_version",version);boundary.put("data_as_of",dataAsOf);
            boundary.put("metric_definitions",strings(boundary.get("metric_definitions")));
            cards.add(card);
        }
        if(facts.isEmpty() && cards.isEmpty() && charts.isEmpty())return null;
        String level="COMPLETE".equals(status)?null:"BLOCKED".equals(status)?"L4":"L2";
        Map<String,Object> entry=map("skill_id",request.get("skill_name"),"display_name",pack.getOrDefault("display_name",request.get("skill_name")),
            "skill_version",version,"pack_hash",TsSnapshotCanonicalizer.sha256(encode(pack)),
            "registry_version",null,"definition_hash",null,"level",level,"status",status,
            "reasons",strings(skill.get("reasons")),"facts",facts,"cards",cards,"charts",charts,"followups",strings(skill.get("followups")));
        return map("schema_version",1,"run_id",run,"level",level,
            "cohort",map("audience_id",row.getThreadId(),"audience_name",cohort.get("name")!=null?cohort.get("name"):row.getTitle(),
                "library_id",row.getLibraryId(),"revision",state.get("revision"),"plan_hash",plan.get("hash"),"snapshot_id",plan.get("snapshot_id"),
                "count",count.get("value"),"data_as_of",dataAsOf,"reference_date",request.get("reference_date"),"binding_version","未接入指标绑定",
                "declared_context",String.valueOf(request.getOrDefault("requirement","")),"synthetic",false),
            "results",new ArrayList<>(Arrays.asList(entry)));
    }
    /**
     * 事实白名单：客群统计原样引用 tagstat.*；对照客群统计引用 benchmark.*；两侧同口径的差值引用 diff.*。
     * 命中这些前缀的事实取值必须与白名单一致（挂名改数的整条丢弃）；其余 query_id 维持原有校验，不误杀派生值。
     */
    private Map<String,Double> allowedTagStats(Map<String,Object> cohort) {
        Map<String,Double> target=statsValues(cohort.get("tag_stats"));
        Map<String,Double> baseline=statsValues(obj(cohort.get("baseline")).get("tag_stats"));
        Map<String,Double> allowed=new LinkedHashMap<>();
        for(Map.Entry<String,Double> entry:target.entrySet())allowed.put("tagstat."+entry.getKey(),entry.getValue());
        for(Map.Entry<String,Double> entry:baseline.entrySet())allowed.put("benchmark."+entry.getKey(),entry.getValue());
        Object baselineCount=obj(cohort.get("baseline")).get("count");
        if(baselineCount instanceof Number)allowed.put("benchmark.count",((Number)baselineCount).doubleValue());
        for(Map.Entry<String,Double> entry:target.entrySet()) {
            Double other=baseline.get(entry.getKey());
            if(other==null)continue;
            allowed.put("diff."+entry.getKey(),Math.round((entry.getValue()-other)*100d)/100d);
        }
        return allowed;
    }
    /**
     * tag_stats 条目 → 「&lt;tag_id&gt;.&lt;统计名&gt;」值表：分布计数与占比的单位是天然的「人」「%」，
     * 与标签量纲无关；数值统计则必须有已登记单位，未登记或已抑制的统计量不进入白名单。
     */
    private Map<String,Double> statsValues(Object rawStats) {
        Map<String,Double> values=new LinkedHashMap<>();
        for(Map<String,Object> entry:list(rawStats)) {
            if(!"AVAILABLE".equals(entry.get("status")))continue;
            String prefix=entry.get("tag_id")+".";
            for(Map<String,Object> row:list(entry.get("categories"))) {
                Object code=row.get("code");
                if(row.get("count") instanceof Number)values.put(prefix+"cat."+code,((Number)row.get("count")).doubleValue());
                if(row.get("share") instanceof Number)values.put(prefix+"share."+code,((Number)row.get("share")).doubleValue());
            }
            if(entry.get("unit")==null)continue;
            Map<String,Object> numeric=obj(entry.get("numeric"));
            for(String key:Arrays.asList("n","missing","min","max","sum","avg","median"))
                if(numeric.get(key) instanceof Number)values.put(prefix+key,((Number)numeric.get(key)).doubleValue());
        }
        return values;
    }
    private static final List<String> STAT_QUERY_PREFIXES=Arrays.asList("tagstat.","benchmark.","diff.");
    private boolean tagStatMatches(Map<String,Object> fact,Map<String,Double> allowed) {
        String queryId=String.valueOf(fact.get("query_id"));
        if(STAT_QUERY_PREFIXES.stream().noneMatch(queryId::startsWith))return true;
        Double expected=allowed.get(queryId);
        if(expected==null || !"AVAILABLE".equals(fact.get("status")))return false;
        Object value=fact.get("value");
        return value instanceof Number && Math.abs(((Number)value).doubleValue()-expected)<=Math.max(0.05,Math.abs(expected)*1e-9);
    }
    /**
     * 陈述段引用的每个 {fact:} 都必须是可用事实，否则该卡片会被前端拒绝渲染；
     * 引用了已通过校验的可用事实、只是漏登记进 fact_ids 的，按引用补齐——数值本身已在事实层逐条复核。
     */
    private boolean skillStatement(Object raw,Map<String,Map<String,Object>> facts) {
        if(!(raw instanceof Map) || !(obj(raw).get("text") instanceof String))return false;
        Map<String,Object> statement=obj(raw);Set<String> declared=new LinkedHashSet<>();
        for(Object value:list(statement.get("fact_ids")))declared.add(String.valueOf(value));
        Matcher matcher=SKILL_FACT_REF.matcher((String)statement.get("text"));
        while(matcher.find()) {
            Map<String,Object> fact=facts.get(matcher.group(1));
            if(fact==null || !"AVAILABLE".equals(fact.get("status")))return false;
            declared.add(matcher.group(1));
        }
        statement.put("fact_ids",new ArrayList<>(declared));
        return true;
    }
    private String dataAsOf(Map<String,Object> count) {
        Object value=count.get("data_as_of");
        if(value instanceof String && !((String)value).isEmpty())return (String)value;
        Object executed=count.get("executed_at");
        return executed instanceof String && ((String)executed).length()>=10?((String)executed).substring(0,10):"";
    }
    private List<String> strings(Object raw) {
        List<String> out=new ArrayList<>();
        if(raw instanceof List)for(Object value:(List<?>)raw)if(value instanceof String && out.size()<12)out.add((String)value);
        return out;
    }
    @Transactional
    public Map<String,Object> rename(String thread,Map<String,Object> request) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        if(request.containsKey("title")) {
            String title=String.valueOf(request.get("title")).trim();if(title.isEmpty()||title.length()>120)throw new ServiceException("标题须为1至120字");row.setTitle(title);
        }
        if(request.containsKey("archived")) {
            String status=String.valueOf(state.get("status"));
            if(Arrays.asList("RUNNING","SUBMITTING").contains(status)) idle(state);
            else if(Boolean.TRUE.equals(request.get("archived")) && Arrays.asList("WAITING","INTERRUPTED","FAILED").contains(status)) stopRun(row,state);
            boolean archived=Boolean.TRUE.equals(request.get("archived"));row.setArchived(archived?"1":"0");
            if(archived)row.setPinned("0");
        }
        if(request.containsKey("pinned")) {
            if("1".equals(row.getArchived()))throw new ServiceException("请先恢复已归档会话",409);
            row.setPinned(Boolean.TRUE.equals(request.get("pinned"))?"1":"0");
        }
        save(row,state);return view(row,state);
    }
    @Transactional
    public void delete(String thread) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        if(!"1".equals(row.getArchived()))throw new ServiceException("请先归档会话",409);
        idle(state);
        agent.delete("/agent/v2/threads/"+thread+"?owner_id="+uid());
        threads.deleteExecutions(thread,uid());
        if(threads.deleteThread(thread,uid(),row.getRowVersion())!=1)
            throw new ServiceException("会话已在其他页面更新，请刷新",409);
    }
    @Transactional
    public Map<String,Object> start(String thread,Map<String,Object> request) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        List<Long> pinned=contextIds(request);
        if(Boolean.TRUE.equals(request.get("context_only")) && pinned.isEmpty())throw new ServiceException("请先选择标签");
        String client=String.valueOf(request.get("client_request_id"));
        if(!client.matches("[a-zA-Z0-9-]{16,64}"))throw new ServiceException("请求编号非法");
        if(client.equals(state.get("run_id"))) {
            Map<String,Object> original=obj(state.get("run_request"));
            if(!Objects.equals(original.get("requirement"),request.getOrDefault("message","编辑圈选条件")) || !Objects.equals(original.get("edited_plan"),request.get("plan"))
                || !Objects.equals(contextIds(map("context_tag_ids",original.get("pinned_tag_ids"))),pinned)
                || !Objects.equals(original.getOrDefault("pinned_only",false),Boolean.TRUE.equals(request.get("context_only")))
                || !Objects.equals(original.get("skill_name"),request.get("skill_name"))
                || !Objects.equals(baselineOf(original),baselineOf(request)))
                throw new ServiceException("重复请求内容不一致",409);
            return view(row,state);
        }
        revision(state,request);idle(state);
        if("1".equals(row.getArchived()))throw new ServiceException("请先恢复已归档会话");
        String text=String.valueOf(request.getOrDefault("message","编辑圈选条件"));
        if(text.trim().isEmpty()||text.length()>2000)throw new ServiceException("消息须为1至2000字");
        if(list(state.get("messages")).size()>500)throw new ServiceException("会话已达到500条消息，请新建圈选");
        if(request.get("confirmed_clause_ids") instanceof List) {
            Set<String> assumed=new HashSet<>();collectAssumed(obj(obj(state.get("plan")).get("tree")),assumed);
            List<String> confirmed=new ArrayList<>();for(Object value:(List<?>)request.get("confirmed_clause_ids"))if(assumed.contains(String.valueOf(value)))confirmed.add(String.valueOf(value));
            state.put("confirmed_clause_ids",confirmed);
        }
        Map<String,Object> bundle=catalog.activeBundle(row.getLibraryId());
        List<Long> eligible=catalog.eligibleTagIds(row.getLibraryId(),String.valueOf(bundle.get("snapshot_id")));
        String skillName=request.get("skill_name") instanceof String?(String)request.get("skill_name"):null;
        Map<String,Object> cohort=null;List<Map<String,Object>> skillPackages=null;
        if(skillName!=null) {
            if(!permissions.hasPermi("taglibrary:insight:run"))throw new ServiceException("没有技能运行权限",403);
            if(request.get("plan")!=null)throw new ServiceException("技能运行请使用当前已核验客群条件");
            if(Boolean.TRUE.equals(request.get("context_only")))throw new ServiceException("技能运行需要写明分析目标");
            Map<String,Object> plan=currentPlan(state,request);
            if(!Objects.equals(plan.get("build_id"),bundle.get("build_id")) || !Objects.equals(plan.get("snapshot_id"),bundle.get("snapshot_id")))throw new ServiceException("客群发布版本已变化，请重新核验",409);
            skillPackages=agentSkills.published();boolean found=false;
            for(Map<String,Object> skill:skillPackages)if(skillName.equals(skill.get("name")) && Boolean.TRUE.equals(skill.get("user_invocable")))found=true;
            if(!found)throw new ServiceException("技能已下线或不允许手动调用，请刷新",409);
            Map<String,Object> count=obj(state.get("count"));boolean counted=number(count.get("revision"))==number(state.get("revision")) && Objects.equals(count.get("plan_hash"),plan.get("hash"));
            cohort=map("name",row.getTitle(),"revision",state.get("revision"),"plan_hash",plan.get("hash"),"plan",plan,"count",counted?count:null,"group_id",obj(state.get("execution")).get("group_id"),"status",counted?"COUNTED":"CONDITIONS_ONLY");
            // 标签 chip 的统计以已核验人数为分母与漂移基准；未统计人数时只说明原因，不取数。
            if(!pinned.isEmpty()) {
                try {
                    cohort.putAll(tagStats.collect(row.getLibraryId(),compiler.compile(row.getLibraryId(),plan),
                        counted?number(count.get("value")):null,pinned,new HashSet<>(eligible),planTagIds(plan)));
                } catch(Exception e) {
                    log.warn("技能标签取数失败 thread={}: {}",thread,e.getMessage());
                    cohort.putAll(map("tag_stats",new ArrayList<>(),"sample_rows",null,"stats_note","标签统计取数失败，本轮不提供标签统计"));
                }
            }
            Map<String,Object> baseline=baseline(request,row,pinned,eligible);
            if(baseline!=null) cohort.put("baseline",baseline);
        }
        List<Map<String,Object>> contextTags=new ArrayList<>();
        for(Long tagId:pinned) {
            TlTag tag=tags.selectTagById(tagId);
            if(tag==null || !Objects.equals(tag.getLibraryId(),row.getLibraryId()) || !eligible.contains(tagId))
                throw new ServiceException("所选标签已不可用或不属于当前标签库，请重新选择",409);
            contextTags.add(map("id",tagId,"name",tag.getTagName()));
        }
        Map<String,Object> req=map("run_id",client,"owner_id",String.valueOf(uid()),"thread_id",thread,"library_id",row.getLibraryId(),
            "build_id",bundle.get("build_id"),"snapshot_id",bundle.get("snapshot_id"),"artifact_hash",bundle.get("artifact_hash"),
            "eligible_tag_ids",eligible,"pinned_tag_ids",pinned,"pinned_only",Boolean.TRUE.equals(request.get("context_only")),"requirement",text,
            "previous_plan",obj(state.get("plan")),"edited_plan",request.get("plan"),"confirmed_clause_ids",state.getOrDefault("confirmed_clause_ids",new ArrayList<>()));
        // 基准日由服务端注入并随运行持久化，恢复时沿用；明确写出的年份优先。
        req.put("reference_date",LocalDate.now(ZoneId.of("Asia/Shanghai")).toString());
        // 客群保存的已核验条件是服务端来源，不能从浏览器请求伪造。
        if(state.containsKey("source_plan"))req.put("source_plan",state.get("source_plan"));
        req.put("timezone","Asia/Shanghai");
        if(skillName!=null)req.putAll(map("profile","skill","skill_name",skillName,"skill_packages",skillPackages,"cohort_context",cohort));
        if(state.get("clarification_state") instanceof Map)req.put("clarification_state",state.get("clarification_state"));
        if(state.get("run_id")!=null)req.put("continuation_of",state.get("run_id"));
        List<Map<String,Object>> priorRuns=list(state.get("run_history"));
        if(state.get("run_id")!=null)priorRuns.add(map("run_id",state.get("run_id"),"events",state.get("events"),"profile",state.get("run_profile")));
        state.put("run_history",priorRuns);
        List<Map<String,Object>> history=list(state.get("messages"));req.put("history",history.subList(Math.max(0,history.size()-12),history.size()));
        agent.post("/agent/v2/runs",req);
        List<Map<String,Object>> messages=new ArrayList<>(history);messages.add(map("id",id(),"role","user","text",text,"context_tags",contextTags,"run_id",client,"created_at",Instant.now().toString()));
        if("新的圈选".equals(row.getTitle()))row.setTitle(text.substring(0,Math.min(40,text.length())));
        state.putAll(map("run_id",client,"run_profile",skillName==null?"audience":"skill","run_request",req,"status","RUNNING","cursor",0,"events",new ArrayList<>(),"messages",messages,"questions",new ArrayList<>()));
        state.remove("error");state.remove("authority_repairs");state.remove("live_plan");
        if(skillName==null){state.remove("count");state.remove("execution");}else{state.remove("outcome");state.remove("interrupt_id");}
        save(row,state);return view(row,state);
    }
    @Transactional
    public Map<String,Object> resume(String thread,Map<String,Object> request) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);revision(state,request);
        if(!Arrays.asList("WAITING","FAILED","INTERRUPTED").contains(state.get("status")))throw new ServiceException("当前运行不能恢复",409);
        if("WAITING".equals(state.get("status")) && !Objects.equals(state.get("interrupt_id"),request.get("interrupt_id")))throw new ServiceException("问题已失效",409);
        Map<String,Object> old=obj(state.get("run_request")), active=catalog.activeBundle(row.getLibraryId());
        if("skill".equals(old.get("profile")))throw new ServiceException("技能运行请重新选择技能并发送，以重新核验发布版本与客群上下文",409);
        if(!Objects.equals(old.get("build_id"),active.get("build_id"))) {
            stopRun(row,state);
            state.put("error","发布版本已更新，当前运行已停止，请重新发送需求核验");
            save(row,state);return view(row,state);
        }
        Object answer=request.get("answer");
        if(answer!=null && encode(answer).length()>100000)throw new ServiceException("补充信息过长");
        if("WAITING".equals(state.get("status")) && (answer==null || String.valueOf(answer).trim().isEmpty()))throw new ServiceException("请填写回答");
        agent.post("/agent/v2/runs/"+state.get("run_id")+"/resume",map("owner_id",String.valueOf(uid()),"answer",answer,"confirmed_clause_ids",state.getOrDefault("confirmed_clause_ids",new ArrayList<>()),
            "eligible_tag_ids",catalog.eligibleTagIds(row.getLibraryId(),String.valueOf(active.get("snapshot_id")))));
        if(answer!=null && !list(state.get("questions")).isEmpty()) {
            Map<String,Object> clarification=new LinkedHashMap<>(obj(state.get("clarification_state")));
            List<Map<String,Object>> records=new ArrayList<>(list(clarification.get("records")));
            records.add(map("questions",state.get("questions"),"answer",answer));
            clarification.put("records",new ArrayList<>(records.subList(Math.max(0,records.size()-20),records.size())));
            clarification.put("pending_questions",new ArrayList<>());state.put("clarification_state",clarification);
        }
        List<Map<String,Object>> messages=list(state.get("messages"));messages.add(map("id",id(),"role","user","text",answer instanceof Map?"已更新圈选条件":answer==null?"继续处理":String.valueOf(answer),"created_at",Instant.now().toString()));
        state.put("messages",messages);state.put("status","RUNNING");state.put("questions",new ArrayList<>());state.remove("error");save(row,state);return view(row,state);
    }
    @Transactional
    public Map<String,Object> cancel(String thread) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        if(!Arrays.asList("RUNNING","WAITING","INTERRUPTED","FAILED").contains(state.get("status")))return view(row,state);
        stopRun(row,state);save(row,state);return view(row,state);
    }
    private void stopRun(TsAgentThread row,Map<String,Object> state) {
        if(state.get("run_id")!=null) agent.post("/agent/v2/runs/"+state.get("run_id")+"/cancel",map("owner_id",String.valueOf(uid())));
        if(state.get("live_plan") instanceof Map){
            Map<String,Object> partial=obj(state.get("live_plan"));partial.put("valid",false);applyPlan(state,partial);
        }
        List<Map<String,Object>> events=list(state.get("events"));events.add(map("seq",-1,"type","run.cancelled","message","已停止；已完成条件保留"));state.put("events",events);
        state.put("status","CANCELLED");state.put("questions",new ArrayList<>());
    }
    /** 方案中已作为条件使用的标签：这些列被条件截断，统计口径要在报告里声明。 */
    private Set<Long> planTagIds(Map<String,Object> plan) {
        Set<Long> ids=new LinkedHashSet<>();collectTagIds(plan.get("tree"),ids);return ids;
    }
    /**
     * 对照客群（基准）：只接受同库、带已发布方案（schemaVersion≥4）的保存对象群；按其保存条件重新编译取数。
     * 选择本身不合法（不存在、跨库、手工规则、发布版本不一致）直接拒绝；取数期故障按降级处理，随 stats_note 说明。
     */
    private Map<String,Object> baseline(Map<String,Object> request,TsAgentThread row,List<Long> pinned,List<Long> eligible) {
        Object raw=request.get("baseline_group_id");
        if(raw==null)return null;
        if(!(raw instanceof Number) || !String.valueOf(raw).matches("[1-9][0-9]*"))throw new ServiceException("对照客群编号非法");
        Long groupId=Long.valueOf(String.valueOf(raw));
        TlObjectGroup group=groups.selectObjectGroupById(groupId);
        if(group==null)throw new ServiceException("对照客群不存在",404);
        if(!Objects.equals(group.getLibraryId(),row.getLibraryId()))throw new ServiceException("对照客群不属于当前标签库",403);
        Map<String,Object> saved=null;
        try {saved=obj(json.readValue(group.getRuleJson(),Map.class).get("audiencePlan"));}
        catch(Exception e) {throw new ServiceException("对照客群规则无法读取");}
        if(saved.isEmpty() || !saved.containsKey("tree"))throw new ServiceException("对照客群为手工规则，不能作为分析基准");
        RulePayload rule;
        try {rule=compiler.compile(row.getLibraryId(),saved);}
        catch(TsPlanValidationException e) {throw new ServiceException("对照客群与当前发布版本不一致，请重新核验后再选择");}
        Map<String,Object> out=map("group_id",groupId,"name",group.getGroupName());
        try {
            RuleRunResultVO counted=groups.runRule(null,row.getLibraryId(),rule);
            long count=counted.getCount();
            out.put("count",count);
            Map<String,Object> stats=tagStats.collect(row.getLibraryId(),rule,count,pinned,new HashSet<>(eligible),planTagIds(saved));
            out.put("tag_stats",stats.get("tag_stats"));out.put("stats_note",stats.get("stats_note"));
        } catch(Exception e) {
            log.warn("对照客群取数失败 group={}: {}",groupId,e.getMessage());
            out.put("count",null);out.put("tag_stats",new ArrayList<>());out.put("stats_note","对照客群取数失败，本轮不提供基准");
        }
        return out;
    }
    /** 可作对照的已保存客群：同库、带已发布方案且方案与当前发布版本一致，选择后不会因版本漂移失败。 */
    public List<Map<String,Object>> baselineGroups(Long library) {
        visible(library);
        Map<String,Object> bundle=catalog.activeBundle(library);
        TlObjectGroup query=new TlObjectGroup();query.setLibraryId(library);
        List<Map<String,Object>> out=new ArrayList<>();
        for(TlObjectGroup group:groups.selectObjectGroupList(query)) {
            Map<String,Object> saved=null;
            try {saved=obj(json.readValue(group.getRuleJson(),Map.class).get("audiencePlan"));}
            catch(Exception e) {continue;}
            if(saved.isEmpty() || !saved.containsKey("tree"))continue;
            if(!Objects.equals(saved.get("build_id"),bundle.get("build_id")) || !Objects.equals(saved.get("snapshot_id"),bundle.get("snapshot_id")) || !Objects.equals(saved.get("artifact_hash"),bundle.get("artifact_hash")))continue;
            out.add(map("group_id",group.getGroupId(),"group_name",group.getGroupName(),"user_count",group.getUserCount()));
        }
        return out;
    }
    private void collectTagIds(Object node,Set<Long> result) {
        if(node instanceof Map) {
            Map<String,Object> map=obj(node);
            if(map.get("tag_id")!=null)result.add(number(map.get("tag_id")));
            for(Object value:map.values())collectTagIds(value,result);
        } else if(node instanceof List) {
            for(Object value:(List<?>)node)collectTagIds(value,result);
        }
    }
    private void collectAssumed(Map<String,Object> node,Set<String> result) {        if(node.containsKey("children")){for(Map<String,Object> child:list(node.get("children")))collectAssumed(child,result);}
        else if("ASSUMED".equals(node.get("status")) || node.get("assumption") instanceof Map)result.add(String.valueOf(node.get("clause_id")));
    }

    private void checkClauseState(Map<String,Object> node,Set<String> confirmed) {
        if(node.containsKey("children")){for(Map<String,Object> child:list(node.get("children")))checkClauseState(child,confirmed);return;}
        String status=String.valueOf(node.get("status")),id=String.valueOf(node.get("clause_id"));
        if(Arrays.asList("GAP","NEEDS_DECISION","UNRESOLVED").contains(status))throw new ServiceException("请先处理条件缺口与业务选择");
        if("ASSUMED".equals(status) && !confirmed.contains(id))throw new ServiceException("请先确认采用的业务定义");
    }

    private Map<String,Object> currentPlan(Map<String,Object> state,Map<String,Object> request) {
        revision(state,request);idle(state);Map<String,Object> plan=obj(state.get("plan"));
        if(Boolean.TRUE.equals(state.get("source_requires_validation")))throw new ServiceException("请先按最新发布版本重新核验原客群条件");
        if(!Boolean.TRUE.equals(plan.get("valid")))throw new ServiceException("圈选条件尚未校验通过");
        checkClauseState(obj(plan.get("tree")),new HashSet<>((List<String>)state.getOrDefault("confirmed_clause_ids",new ArrayList<>())));
        if(!Objects.equals(plan.get("hash"),request.get("plan_hash")))throw new ServiceException("确认的方案已变化",409);
        return plan;
    }
    @Transactional
    public Map<String,Object> count(String thread,Map<String,Object> request) {
        if(!permissions.hasPermi("objectgroup:group:run"))throw new ServiceException("没有人数统计权限",403);
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);Map<String,Object> plan=currentPlan(state,request);
        RuleRunResultVO count=groups.runRule(null,row.getLibraryId(),compiler.compile(row.getLibraryId(),plan));
        state.put("count",map("value",count.getCount(),"revision",state.get("revision"),"plan_hash",plan.get("hash"),"executed_at",Instant.now().toString(),"data_as_of",null,"warning",count.getWarning()));
        save(row,state);return view(row,state);
    }
    /** 洞察仅从当前已核验、已统计的快照进入，不接受浏览器传入客群规则或人数。 */
    @Transactional
    public Map<String,Object> insightContext(String thread,Map<String,Object> request) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);Map<String,Object> plan=currentPlan(state,request);
        Map<String,Object> count=obj(state.get("count"));
        if(number(count.get("revision"))!=number(state.get("revision")) || !Objects.equals(count.get("plan_hash"),plan.get("hash")))
            throw new ServiceException("请先统计当前方案人数",409);
        return map("library_id",row.getLibraryId(),"name",row.getTitle(),"revision",state.get("revision"),"plan",plan,"count",count,
            "rule",compiler.compile(row.getLibraryId(),plan),"report",state.get("insight_report"));
    }
    @Transactional
    public void saveInsight(String thread,Map<String,Object> request,Map<String,Object> report) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);Map<String,Object> plan=currentPlan(state,request);
        Map<String,Object> cohort=obj(report.get("cohort"));
        if(number(cohort.get("revision"))!=number(state.get("revision"))||!Objects.equals(cohort.get("plan_hash"),plan.get("hash")))throw new ServiceException("洞察完成时方案已变化",409);
        state.put("insight_report",report);save(row,state);
    }
    @Transactional
    public Map<String,Object> preview(String thread,Map<String,Object> request) {
        if(!permissions.hasPermi("objectgroup:group:preview"))throw new ServiceException("没有样例查看权限",403);
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);Map<String,Object> plan=currentPlan(state,request);
        return groups.previewRule(null,row.getLibraryId(),compiler.compile(row.getLibraryId(),plan));
    }
    @Autowired private com.ruoyi.taglibrary.mapper.TsCatalogSnapshotMapper saveSnapshots;

    @Transactional
    public Map<String,Object> createGroup(String thread,Map<String,Object> request) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        boolean updating=state.get("source_group_id")!=null;
        if(!permissions.hasPermi(updating?"objectgroup:group:edit":"objectgroup:group:add"))throw new ServiceException(updating?"没有更新客群权限":"没有创建客群权限",403);
        if("1".equals(row.getArchived()))throw new ServiceException("请先恢复已归档会话",409);
        Map<String,Object> plan=currentPlan(state,request);
        Map<String,Object> previous=threads.execution(thread,uid(),number(state.get("revision")));
        if(previous!=null)return previous;
        String name=String.valueOf(request.getOrDefault("name","" )).trim();if(name.isEmpty()||name.length()>100)throw new ServiceException("客群名称须为1至100字");
        if(saveSnapshots.lockLibrary(row.getLibraryId())==null)throw new ServiceException("标签库不存在",409);
        TlObjectGroup source=null;
        if(updating) {
            source=groups.selectObjectGroupByIdForUpdate(number(state.get("source_group_id")));
            if(source==null || !Objects.equals(source.getLibraryId(),row.getLibraryId()))throw new ServiceException("原客群不存在或所属标签库已变化",409);
            if(!Objects.equals(state.get("source_rule_hash"),TsSnapshotCanonicalizer.sha256(source.getRuleJson()))
                || (state.containsKey("source_group_name") && !Objects.equals(state.get("source_group_name"),source.getGroupName())))
                throw new ServiceException("原客群已被其他操作更新，请从客群列表重新进入",409);
        }
        RulePayload rule=compiler.compileForSave(row.getLibraryId(),plan);String sql=groups.buildRuleSql(row.getLibraryId(),rule);
        TlObjectGroup group=new TlObjectGroup();group.setLibraryId(row.getLibraryId());group.setGroupName(name);group.setRuleJson(encode(rule));
        if(updating) {
            group.setGroupId(source.getGroupId());group.setGroupSql(sql);
            // 上方已验证用户进入工作台时的 source_rule_hash，并在库锁内读取原文。
            group.getParams().put("expectedRuleJson", source.getRuleJson());
            Map<String,Object> count=obj(state.get("count"));
            group.setUserCount(number(count.get("revision"))==number(state.get("revision"))?number(count.get("value")):0L);
            if(groups.updateObjectGroup(group)!=1)throw new ServiceException("原客群更新失败",409);
            state.put("source_rule_hash",TsSnapshotCanonicalizer.sha256(group.getRuleJson()));state.put("source_group_name",name);
        } else {
            group.setGroupDesc("圈选会话 "+thread+" / 方案 v"+state.get("revision"));groups.insertObjectGroup(group);
        }
        String eid=id();threads.executionInsert(eid,thread,uid(),number(state.get("revision")),String.valueOf(plan.get("hash")),group.getGroupId());
        Map<String,Object> result=map("execution_id",eid,"group_id",group.getGroupId(),"revision",state.get("revision"),"plan_hash",plan.get("hash"),"updated",updating);
        state.put("execution",result);save(row,state);return result;
    }
    @Transactional
    public Map<String,Object> execution(String thread) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        Map<String,Object> found=threads.execution(thread,uid(),number(state.get("revision")));return found==null?map("status","NOT_CREATED"):found;
    }
    /** 客群的保存方案是回灌来源；其他用户的会话、历史版本及删除会话均不直接复用。 */
    @Transactional
    public Map<String,Object> fromGroup(Long groupId) {
        if(!permissions.hasPermi("objectgroup:group:edit"))throw new ServiceException("没有编辑客群权限",403);
        TlObjectGroup group=groups.selectObjectGroupById(groupId);
        if(group==null)throw new ServiceException("客群不存在",404);
        visible(group.getLibraryId());
        Map<String,Object> rule;
        try {rule=json.readValue(group.getRuleJson(),Map.class);}catch(Exception e){throw new ServiceException("客群规则无法读取");}
        Map<String,Object> saved=obj(rule.get("audiencePlan"));
        if(number(rule.get("schemaVersion"))<4 || !saved.containsKey("tree"))throw new ServiceException("手工规则客群请使用规则编辑器");
        String sourceHash=TsSnapshotCanonicalizer.sha256(group.getRuleJson());
        // 刷新或再次进入时恢复本人正在编辑的草稿，不重置条件、Ask 或运行进度。
        for(TsAgentThread item:threads.list(uid(),"0")) {
            if(!Objects.equals(item.getLibraryId(),group.getLibraryId()))continue;
            TsAgentThread editing=threads.lock(item.getThreadId(),uid());
            if(editing==null || "1".equals(editing.getArchived()))continue;
            Map<String,Object> editingState=data(editing);
            if(number(editingState.get("source_group_id"))==groupId && Objects.equals(sourceHash,editingState.get("source_rule_hash"))) {
                editingState.put("source_thread_reused",true);
                if(!editingState.containsKey("source_plan"))editingState.put("source_plan",saved);
                save(editing,editingState);return view(editing,editingState);
            }
        }
        TsAgentThread row=null;Map<String,Object> state=null;
        for(Map<String,Object> execution:threads.executionsForGroup(groupId,uid())) {
            TsAgentThread candidate=threads.lock(String.valueOf(execution.get("thread_id")),uid());
            if(candidate==null || "1".equals(candidate.getArchived()) || !Objects.equals(candidate.getLibraryId(),group.getLibraryId()))continue;
            Map<String,Object> candidateState=data(candidate),candidatePlan=obj(candidateState.get("plan"));
            if(Arrays.asList("RUNNING","WAITING","SUBMITTING").contains(candidateState.get("status")))continue;
            if(!Objects.equals(saved.get("hash"),execution.get("plan_hash")) || !saved.equals(candidatePlan))continue;
            if(candidateState.get("source_group_id")!=null && number(candidateState.get("source_group_id"))!=groupId)continue;
            row=candidate;state=candidateState;break;
        }
        boolean reused=row!=null;
        if(!reused) {
            Map<String,Object> created=create(group.getLibraryId());row=owned(String.valueOf(created.get("thread_id")));state=data(row);
            row.setTitle("编辑："+group.getGroupName().substring(0,Math.min(100,group.getGroupName().length())));
        }
        state.put("source_group_id",groupId);state.put("source_group_name",group.getGroupName());
        state.put("source_rule_hash",sourceHash);state.put("source_thread_reused",reused);state.put("source_plan",saved);
        state.put("source_requires_validation",true);state.put("status","IDLE");
        Set<String> confirmed=new LinkedHashSet<>();savedConfirmations(obj(saved.get("tree")),confirmed);
        state.put("confirmed_clause_ids",new ArrayList<>(confirmed));
        Map<String,Object> plan=json.convertValue(saved,Map.class);plan.put("valid",false);plan.put("plan_status","DRAFT");
        plan.put("diagnostics",Arrays.asList(map("code","REVALIDATION_REQUIRED","message","请按最新发布版本重新核验保存的客群条件")));
        applyPlan(state,plan);
        list(state.get("messages")).add(map("id",id(),"role","assistant","text",reused?"已载入客群保存的条件，请按最新发布版本重新核验。":"已根据客群保存的条件建立编辑会话，请按最新发布版本重新核验。","created_at",Instant.now().toString()));
        save(row,state);return view(row,state);
    }
}
