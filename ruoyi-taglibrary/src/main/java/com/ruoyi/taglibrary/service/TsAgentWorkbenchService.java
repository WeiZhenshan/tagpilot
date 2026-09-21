package com.ruoyi.taglibrary.service;

import java.util.*;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.exception.ServiceException;
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
    @Autowired private TsAgentThreadMapper threads;
    @Autowired private ObjectMapper json;
    @Autowired private DataBrokerCryptoService crypto;
    @Autowired private PermissionService permissions;
    @Autowired private ITlTagLibraryService libraries;
    @Autowired private ITsCatalogRuntimeService catalog;
    @Autowired private TsAgentClient agent;
    @Autowired private TsAudiencePlanCompiler compiler;
    @Autowired private ITlObjectGroupService groups;

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
        List<Map<String,Object>> versions=list(state.get("versions"));versions.add(plan);state.put("versions",versions);
    }
    private Map<String,Object> view(TsAgentThread row,Map<String,Object> state) {
        Map<String,Object> out=new LinkedHashMap<>(state);
        out.putAll(map("thread_id",row.getThreadId(),"library_id",row.getLibraryId(),"title",row.getTitle(),"archived","1".equals(row.getArchived()),
            "capabilities",map("count",permissions.hasPermi("objectgroup:group:run"),"create",permissions.hasPermi("objectgroup:group:add"),"preview",permissions.hasPermi("objectgroup:group:preview"))));
        out.remove("run_request"); return out;
    }
    public List<TsAgentThread> listThreads(boolean archived,int page) {
        return threads.list(uid(),archived?"1":"0",30,Math.max(0,Math.min(page,10000)-1)*30);
    }
    @Transactional
    public Map<String,Object> create(Long library) {
        visible(library); TsAgentThread row=new TsAgentThread();
        row.setThreadId(id());row.setUserId(uid());row.setLibraryId(library);row.setTitle("新的圈选");row.setArchived("0");row.setRowVersion(0L);
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
        if(!result.isEmpty() && !resultKey.equals(state.get("applied_result"))) {
            Map<String,Object> plan=obj(result.get("plan"));
            if(plan.containsKey("tree")) {
                try { if(Boolean.TRUE.equals(plan.get("valid"))) groups.buildRuleSql(row.getLibraryId(),compiler.compile(row.getLibraryId(),plan)); }
                catch(ServiceException e) {plan.put("valid",false);plan.put("validation_errors",Arrays.asList(map("message",e.getMessage())));}
                applyPlan(state,plan);
            }
            state.put("questions",result.get("questions"));state.put("interrupt_id",result.get("interrupt_id"));state.put("applied_result",resultKey);
            List<Map<String,Object>> messages=list(state.get("messages"));
            messages.add(map("id",id(),"role","assistant","text","WAITING".equals(remote.get("status"))?"有条件需要补充，请在下方回答或编辑右侧方案。":Boolean.TRUE.equals(plan.get("valid"))?"圈选方案已生成，可以核对条件并统计人数。":"方案已保留，仍有条件需要修正。",
                "revision",state.get("revision"),"run_id",run,"created_at",Instant.now().toString()));state.put("messages",messages);
        }
        save(row,state);
    }
    @Transactional
    public Map<String,Object> rename(String thread,Map<String,Object> request) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        if(request.containsKey("title")) {
            String title=String.valueOf(request.get("title")).trim();if(title.isEmpty()||title.length()>120)throw new ServiceException("标题须为1至120字");row.setTitle(title);
        }
        if(request.containsKey("archived")) {idle(state);row.setArchived(Boolean.TRUE.equals(request.get("archived"))?"1":"0");}
        save(row,state);return view(row,state);
    }
    @Transactional
    public Map<String,Object> start(String thread,Map<String,Object> request) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        String client=String.valueOf(request.get("client_request_id"));
        if(!client.matches("[a-zA-Z0-9-]{16,64}"))throw new ServiceException("请求编号非法");
        if(client.equals(state.get("run_id"))) {
            Map<String,Object> original=obj(state.get("run_request"));
            if(!Objects.equals(original.get("requirement"),request.getOrDefault("message","编辑圈选条件")) || !Objects.equals(original.get("edited_plan"),request.get("plan")))
                throw new ServiceException("重复请求内容不一致",409);
            return view(row,state);
        }
        revision(state,request);idle(state);
        if("1".equals(row.getArchived()))throw new ServiceException("请先恢复已归档会话");
        String text=String.valueOf(request.getOrDefault("message","编辑圈选条件"));
        if(text.trim().isEmpty()||text.length()>2000)throw new ServiceException("消息须为1至2000字");
        if(list(state.get("messages")).size()>500)throw new ServiceException("会话已达到500条消息，请新建圈选");
        Map<String,Object> bundle=catalog.activeBundle(row.getLibraryId());
        Map<String,Object> req=map("run_id",client,"owner_id",String.valueOf(uid()),"thread_id",thread,"library_id",row.getLibraryId(),
            "build_id",bundle.get("build_id"),"snapshot_id",bundle.get("snapshot_id"),"artifact_hash",bundle.get("artifact_hash"),
            "eligible_tag_ids",catalog.eligibleTagIds(row.getLibraryId(),String.valueOf(bundle.get("snapshot_id"))),"requirement",text,
            "previous_plan",obj(state.get("plan")),"edited_plan",request.get("plan"));
        List<Map<String,Object>> priorRuns=list(state.get("run_history"));
        if(state.get("run_id")!=null)priorRuns.add(map("run_id",state.get("run_id"),"events",state.get("events")));
        state.put("run_history",priorRuns);
        List<Map<String,Object>> history=list(state.get("messages"));req.put("history",history.subList(Math.max(0,history.size()-12),history.size()));
        agent.post("/agent/v2/runs",req);
        List<Map<String,Object>> messages=new ArrayList<>(history);messages.add(map("id",id(),"role","user","text",text,"run_id",client,"created_at",Instant.now().toString()));
        if("新的圈选".equals(row.getTitle()))row.setTitle(text.substring(0,Math.min(40,text.length())));
        state.putAll(map("run_id",client,"run_request",req,"status","RUNNING","cursor",0,"events",new ArrayList<>(),"messages",messages,"questions",new ArrayList<>()));
        state.remove("error");state.remove("live_plan");state.remove("count");state.remove("execution");save(row,state);return view(row,state);
    }
    @Transactional
    public Map<String,Object> resume(String thread,Map<String,Object> request) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);revision(state,request);
        if(!Arrays.asList("WAITING","FAILED","INTERRUPTED").contains(state.get("status")))throw new ServiceException("当前运行不能恢复",409);
        if("WAITING".equals(state.get("status")) && !Objects.equals(state.get("interrupt_id"),request.get("interrupt_id")))throw new ServiceException("问题已失效",409);
        Map<String,Object> old=obj(state.get("run_request")), active=catalog.activeBundle(row.getLibraryId());
        if(!Objects.equals(old.get("build_id"),active.get("build_id")))throw new ServiceException("发布版本已更新，请停止后重新核验",409);
        Object answer=request.get("answer");
        if(answer!=null && encode(answer).length()>100000)throw new ServiceException("补充信息过长");
        if("WAITING".equals(state.get("status")) && (answer==null || String.valueOf(answer).trim().isEmpty()))throw new ServiceException("请填写回答");
        agent.post("/agent/v2/runs/"+state.get("run_id")+"/resume",map("owner_id",String.valueOf(uid()),"answer",answer,
            "eligible_tag_ids",catalog.eligibleTagIds(row.getLibraryId(),String.valueOf(active.get("snapshot_id")))));
        List<Map<String,Object>> messages=list(state.get("messages"));messages.add(map("id",id(),"role","user","text",answer instanceof Map?"已更新圈选条件":answer==null?"继续处理":String.valueOf(answer),"created_at",Instant.now().toString()));
        state.put("messages",messages);state.put("status","RUNNING");state.put("questions",new ArrayList<>());state.remove("error");save(row,state);return view(row,state);
    }
    @Transactional
    public Map<String,Object> cancel(String thread) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        if(!Arrays.asList("RUNNING","WAITING","INTERRUPTED","FAILED").contains(state.get("status")))return view(row,state);
        if(state.get("run_id")!=null) agent.post("/agent/v2/runs/"+state.get("run_id")+"/cancel",map("owner_id",String.valueOf(uid())));
        if(state.get("live_plan") instanceof Map){
            Map<String,Object> partial=obj(state.get("live_plan"));partial.put("valid",false);applyPlan(state,partial);
        }
        List<Map<String,Object>> events=list(state.get("events"));events.add(map("seq",-1,"type","run.cancelled","message","已停止；已完成条件保留"));state.put("events",events);
        state.put("status","CANCELLED");state.put("questions",new ArrayList<>());save(row,state);return view(row,state);
    }
    private Map<String,Object> currentPlan(Map<String,Object> state,Map<String,Object> request) {
        revision(state,request);idle(state);Map<String,Object> plan=obj(state.get("plan"));
        if(!Boolean.TRUE.equals(plan.get("valid")))throw new ServiceException("圈选条件尚未校验通过");
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
    @Transactional
    public Map<String,Object> preview(String thread,Map<String,Object> request) {
        if(!permissions.hasPermi("objectgroup:group:preview"))throw new ServiceException("没有样例查看权限",403);
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);Map<String,Object> plan=currentPlan(state,request);
        return groups.previewRule(null,row.getLibraryId(),compiler.compile(row.getLibraryId(),plan));
    }
    @Transactional
    public Map<String,Object> createGroup(String thread,Map<String,Object> request) {
        if(!permissions.hasPermi("objectgroup:group:add"))throw new ServiceException("没有创建客群权限",403);
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);Map<String,Object> plan=currentPlan(state,request);
        Map<String,Object> previous=threads.execution(thread,uid(),number(state.get("revision")));
        if(previous!=null)return previous;
        String name=String.valueOf(request.getOrDefault("name","" )).trim();if(name.isEmpty()||name.length()>100)throw new ServiceException("客群名称须为1至100字");
        RulePayload rule=compiler.compile(row.getLibraryId(),plan);groups.buildRuleSql(row.getLibraryId(),rule);
        TlObjectGroup group=new TlObjectGroup();group.setLibraryId(row.getLibraryId());group.setGroupName(name);group.setRuleJson(encode(rule));
        group.setGroupDesc("圈选会话 "+thread+" / 方案 v"+state.get("revision"));groups.insertObjectGroup(group);
        String eid=id();threads.executionInsert(eid,thread,uid(),number(state.get("revision")),String.valueOf(plan.get("hash")),group.getGroupId());
        Map<String,Object> result=map("execution_id",eid,"group_id",group.getGroupId(),"revision",state.get("revision"),"plan_hash",plan.get("hash"));
        state.put("execution",result);save(row,state);return result;
    }
    @Transactional
    public Map<String,Object> execution(String thread) {
        TsAgentThread row=owned(thread);Map<String,Object> state=data(row);
        Map<String,Object> found=threads.execution(thread,uid(),number(state.get("revision")));return found==null?map("status","NOT_CREATED"):found;
    }
}
