package com.ruoyi.taglibrary.service;
import java.util.*;
import java.time.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.taglibrary.mapper.TsInsightMapper;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;

/** Java编排单向plan→聚合→compose；逐阶段复核客群/权限/发布版本，不执行营销写动作。 */
@Service
@SuppressWarnings("unchecked")
public class TsInsightRunService {
 @Autowired private TsAgentWorkbenchService workbench;
 @Autowired private TsInsightRegistryService registry;
 @Autowired private TsInsightQueryService queries;
 @Autowired private ITsCatalogRuntimeService catalog;
 @Autowired private TsAgentClient agent;
 @Autowired private TsInsightMapper mapper;
 @Autowired private ObjectMapper json;
 @Autowired private TsInsightPersistenceService persistence;
 private JsonNode definition(Map<String,Object> row){try{return json.readTree(String.valueOf(row.get("definition_json")));}catch(Exception e){throw new ServiceException("洞察定义格式错误");}}
 private Map<String,Object> await(String id) {
  long deadline=System.nanoTime()+55_000_000_000L;
  while(System.nanoTime()<deadline) {
   Map<String,Object> state=agent.get("/agent/v2/runs/"+id+"?owner_id="+SecurityUtils.getUserId());
   String status=String.valueOf(state.get("status"));
   if("COMPLETED".equals(status))return (Map<String,Object>)state.get("result");
   if(Arrays.asList("FAILED","CANCELLED","INTERRUPTED").contains(status))throw new ServiceException("洞察计算未完成，请重新运行");
   try{Thread.sleep(100);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new ServiceException("洞察等待中断");}
  }
  agent.post("/agent/v2/runs/"+id+"/cancel",map("owner_id",String.valueOf(SecurityUtils.getUserId())));
  throw new ServiceException("洞察计算超时，请稍后重试");
 }
 public Map<String,Object> run(String thread,Map<String,Object> request){
  for(String k:request.keySet())if(!Arrays.asList("base_revision","plan_hash","skill_ids","parameters","narrate").contains(k))throw new ServiceException("洞察请求含非法字段");
  List<String> ids=new ArrayList<>();JsonNode req=json.valueToTree(request);
  if(!req.path("skill_ids").isArray()||req.path("skill_ids").size()<1||req.path("skill_ids").size()>3)throw new ServiceException("请选择技能或场景包");
  for(JsonNode id:req.path("skill_ids")){if(!Arrays.asList("asset_structure_profile","product_holding_gap","opportunity_priority").contains(id.asText())||ids.contains(id.asText()))throw new ServiceException("技能标识重复或未登记");ids.add(id.asText());}
  if(ids.contains("opportunity_priority")&&!ids.contains("product_holding_gap"))ids.add("product_holding_gap");
  ids.sort(Comparator.comparingInt(id->Arrays.asList("asset_structure_profile","product_holding_gap","opportunity_priority").indexOf(id)));
  // 每次使用技能时刷新当前已确认方案人数，禁止沿用上次统计值。
  long started=System.nanoTime();workbench.count(thread,request);Map<String,Object> ctx=workbench.insightContext(thread,request);Long library=((Number)ctx.get("library_id")).longValue();
  Map<String,Object> audience=(Map<String,Object>)ctx.get("plan"),count=(Map<String,Object>)ctx.get("count");
  String run=UUID.randomUUID().toString(),dataDate=null,bindingVersion=null;List<Object> results=new ArrayList<>();Map<String,Object> cohort=null,g2=null;JsonNode g2Config=null;
  try {
  for(String id:ids) {
   try {
   Map<String,Object> registered=registry.published(library,id);JsonNode config=definition(registered);
   if(dataDate==null){dataDate=config.path("data_as_of").asText();bindingVersion=config.path("binding_version").asText();}
   if(!dataDate.equals(config.path("data_as_of").asText())||!bindingVersion.equals(config.path("binding_version").asText()))throw new ServiceException("场景包指标绑定版本或数据日期不一致",409);
   cohort=map("audience_id",thread,"audience_name",ctx.get("name"),"library_id",library,"revision",ctx.get("revision"),"plan_hash",audience.get("hash"),"snapshot_id",audience.get("snapshot_id"),"count",count.get("value"),"data_as_of",dataDate,"reference_date",LocalDate.now(ZoneId.of("Asia/Shanghai")).toString(),"binding_version",bindingVersion,"declared_context",String.valueOf(audience.getOrDefault("original_request",json.valueToTree(audience).path("intent_plan").path("original_request").asText(""))),"synthetic",false);
   Set<Long> eligible=new HashSet<>(catalog.eligibleTagIds(library,String.valueOf(audience.get("snapshot_id"))));List<Object> bindings=new ArrayList<>();
   for(JsonNode b:config.path("bindings")) {
    if("customer_count".equals(b.path("metric").asText()))continue;
    Map<String,Object> binding=map("metric",b.path("metric").asText(),"version",bindingVersion,"tag_id",b.path("tag_ids").get(0).asLong(),"snapshot_id",audience.get("snapshot_id"),"unit",b.path("unit").asText(),"status","PUBLISHED");
    if(b.hasNonNull("category"))binding.put("category",b.path("category").asText());bindings.add(binding);
   }
   Map<String,Object> plan=agent.post("/agent/insight/plan",map("skill_id",id,"cohort",cohort,"bindings",bindings,"eligible_tag_ids",eligible,"parameters",req.path("parameters").path(id).isObject()?json.convertValue(req.path("parameters").path(id),Map.class):new LinkedHashMap<>(),"published_hash",registered.get("pack_hash")));
   List<Object> batches=new ArrayList<>();
   if("READY".equals(plan.get("status"))) {
    ObjectNode effective=(ObjectNode)config.deepCopy();effective.put("scope_hash",TsSnapshotCanonicalizer.sha256(library+":"+new java.util.TreeSet<>(eligible).toString()));
    if("opportunity_priority".equals(id)) {
     JsonNode prior=json.valueToTree(g2);double gap=0;
     if(!"BLOCKED".equals(prior.path("status").asText()))for(JsonNode card:prior.path("cards"))if("wealth_findings".equals(card.path("id").asText())&&"STAT".equals(card.path("diagnosis").path("basis").asText()))for(JsonNode f:prior.path("facts"))if("wealth_gap".equals(f.path("id").asText())&&"AVAILABLE".equals(f.path("status").asText()))gap=f.path("value").asDouble();
     boolean opportunity=false;for(JsonNode f:prior.path("facts"))if("wealth_opportunity".equals(f.path("id").asText())&&"AVAILABLE".equals(f.path("status").asText())&&f.path("value").asDouble()>=20)opportunity=true;
     JsonNode sourceTag=null,scoreTag=null,sourceBinding=null,scoreBinding=null;
     if(g2Config!=null)for(JsonNode b:g2Config.path("bindings"))if("product_holding".equals(b.path("metric").asText())&&"wealth".equals(b.path("category").asText())){sourceTag=b.path("tag_ids");sourceBinding=b;}
     for(JsonNode b:config.path("bindings"))if("product_gap".equals(b.path("metric").asText())){scoreTag=b.path("tag_ids");scoreBinding=b;}
     if(sourceTag==null||!sourceTag.equals(scoreTag)||!sourceBinding.path("enum_map").equals(scoreBinding.path("enum_map"))||!sourceBinding.path("kind").asText("DIRECT").equals(scoreBinding.path("kind").asText("DIRECT")))throw new ServiceException("评分缺口须绑定到前置G2同品类的持有来源");
     if(gap<=0||!opportunity){plan.put("status","BLOCKED");plan.put("reasons",Collections.singletonList("前置理财缺口未通过统计或适当性门禁"));plan.put("queries",Collections.emptyList());}
     else effective.put("_g2_gap",gap);
    }
    if("READY".equals(plan.get("status")))batches.add(queries.execute(library,(RulePayload)ctx.get("rule"),json.valueToTree(plan),effective,eligible));
   }
   String child=UUID.randomUUID().toString();agent.post("/agent/insight/runs",map("run_id",child,"thread_id",thread,"owner_id",String.valueOf(SecurityUtils.getUserId()),"plans",Collections.singletonList(plan),"aggregates",batches,"narrate",Boolean.TRUE.equals(request.get("narrate"))));
   Map<String,Object> report=await(child);Map<String,Object> result=(Map<String,Object>)((List<?>)report.get("results")).get(0);
   result.put("registry_version",registered.get("version"));result.put("definition_hash",TsSnapshotCanonicalizer.sha256(String.valueOf(registered.get("definition_json"))));
   // 治理配置或方案在运行过程中变化时，不把旧结果交给用户。
   Map<String,Object> currentVersion;
   try{currentVersion=registry.published(library,id);}catch(ServiceException revoked){throw new ServiceException("洞察发布状态或权限已变化",409);}
   if(!Objects.equals(currentVersion.get("version"),registered.get("version")) || !Objects.equals(currentVersion.get("definition_json"),registered.get("definition_json")))throw new ServiceException("洞察发布版本已变化",409);
   workbench.insightContext(thread,request);
   if("product_holding_gap".equals(id)){g2=result;g2Config=config;}
   results.add(result);
   }catch(ServiceException e){
    if(Arrays.asList(401,403,409).contains(e.getCode()))throw e;
    JsonNode local=null;for(JsonNode item:json.valueToTree(agent.get("/agent/insight/catalog")).path("skills"))if(id.equals(item.path("manifest").path("id").asText()))local=item;
    if(local==null)throw e;
    results.add(map("skill_id",id,"skill_version",local.path("manifest").path("version").asText(),"pack_hash",local.path("pack_hash").asText(),"status","BLOCKED","level","L4","reasons",Collections.singletonList(e.getMessage()),"facts",Collections.emptyList(),"cards",Collections.emptyList(),"charts",Collections.emptyList()));
    if("product_holding_gap".equals(id)){g2=null;g2Config=null;}workbench.insightContext(thread,request);
   }
  }
  if(cohort==null)throw new ServiceException("所选技能均未发布，请先完成绑定、复核与发布");
  Map<String,Object> report=map("schema_version",1,"run_id",run,"cohort",cohort,"results",results);
  long usable=results.stream().filter(r->!"BLOCKED".equals(((Map<String,Object>)r).get("status"))).count();
  if(usable==0)report.put("level","L4");else if(usable<results.size()||results.stream().anyMatch(r->"PARTIAL".equals(((Map<String,Object>)r).get("status"))))report.put("level","L2");
  if(!registry.reportVisible(library,report))throw new ServiceException("洞察授权或发布版本已变化，请重新运行",409);
  workbench.insightContext(thread,request);
  persistence.success(thread,request,report,library,((Number)ctx.get("revision")).longValue(),String.valueOf(audience.get("hash")),(System.nanoTime()-started)/1_000_000L);
  return report;
  }catch(RuntimeException e){persistence.failure(run,library,thread,((Number)ctx.get("revision")).longValue(),String.valueOf(audience.get("hash")),(System.nanoTime()-started)/1_000_000L);throw e;}
 }
 public Map<String,Object> route(String thread,Map<String,Object> request){workbench.insightContext(thread,request);return agent.post("/agent/insight/route",map("utterance",request.get("utterance"),"owner_id",String.valueOf(SecurityUtils.getUserId())));}
 public Map<String,Object> edit(String thread,Map<String,Object> request){
  Map<String,Object> ctx=workbench.insightContext(thread,request);Map<String,Object> report=(Map<String,Object>)ctx.get("report");if(report==null)throw new ServiceException("当前客群尚无洞察报告");
  if(!registry.reportVisible(((Number)ctx.get("library_id")).longValue(),report))throw new ServiceException("报告授权或发布版本已变化，请重新运行",409);
  Map<String,Object> hashes=new LinkedHashMap<>();for(Object item:(List<?>)report.get("results")){Map<String,Object> r=(Map<String,Object>)item;hashes.put(String.valueOf(r.get("skill_id")),r.get("pack_hash"));}
  Map<String,Object> changed=agent.post("/agent/insight/edit",map("owner_id",String.valueOf(SecurityUtils.getUserId()),"published_hashes",hashes,"report",report,"skill_id",request.get("skill_id"),"chart_id",request.get("chart_id"),"utterance",request.get("utterance")));
  if(Boolean.FALSE.equals(changed.get("requires_confirmation")))workbench.saveInsight(thread,request,(Map<String,Object>)changed.get("report"));return changed;
 }
 public List<Map<String,Object>> audit(Long library){registry.catalog(library);return mapper.audit(library,SecurityUtils.getUserId());}
 public void feedback(String id,Map<String,Object> body){Map<String,Object> row=mapper.ownedRun(id,SecurityUtils.getUserId());if(row==null)throw new ServiceException("运行不存在或无权访问",404);int rating=json.valueToTree(body).path("rating").asInt();String category=String.valueOf(body.get("category")),comment=String.valueOf(body.getOrDefault("comment",""));if(rating<1||rating>5||!Arrays.asList("ACCURACY","USEFULNESS","BOUNDARY","CHART").contains(category)||comment.length()>500)throw new ServiceException("反馈格式非法");mapper.feedback(id,SecurityUtils.getUserId(),rating,category,comment);}
}
