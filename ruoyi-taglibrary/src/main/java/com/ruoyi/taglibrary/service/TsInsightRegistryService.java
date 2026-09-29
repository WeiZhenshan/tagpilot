package com.ruoyi.taglibrary.service;
import java.util.*;
import java.time.LocalDate;
import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.framework.web.service.PermissionService;
import com.ruoyi.taglibrary.mapper.TsInsightMapper;

/** 包内容经代码评审，数据库只维护版本/绑定/门禁/状态；没有模型发布入口。 */
@Service
@SuppressWarnings("unchecked")
public class TsInsightRegistryService {
 @Autowired private TsInsightMapper mapper;
 @Autowired private TsAgentClient agent;
 @Autowired private ObjectMapper json;
 @Autowired private ITlTagLibraryService libraries;
 @Autowired private ITsCatalogRuntimeService catalog;
 @Autowired private PermissionService permissions;
 private void visible(Long library){if(!permissions.hasAnyPermi("taglibrary:library:list,taglibrary:library:query")||libraries.selectLibraryById(library)==null)throw new ServiceException("无权访问标签库",403);}
 public Map<String,Object> catalog(Long library){visible(library);Map<String,Object> out=agent.get("/agent/insight/catalog");List<Map<String,Object>> rows=mapper.list(library);
  if(!permissions.hasPermi("taglibrary:insight:list"))for(Map<String,Object> row:rows){row.remove("definition_json");row.remove("evaluation_json");}
  out.put("versions",rows);return out;}
 private JsonNode local(String id){for(JsonNode n:json.valueToTree(agent.get("/agent/insight/catalog")).path("skills"))if(id.equals(n.path("manifest").path("id").asText()))return n;throw new ServiceException("技能未在代码包登记");}
 public void save(Long library,Map<String,Object> body){
  visible(library);JsonNode n=json.valueToTree(body);Set<String> allowed=new HashSet<>(Arrays.asList("skill_id","version","bindings","data_as_of","binding_version","benchmark_definition","benchmark_version","suitability"));
  n.fieldNames().forEachRemaining(k->{if(!allowed.contains(k))throw new ServiceException("技能配置含非法字段");});
  JsonNode pack=local(n.path("skill_id").asText());
  if(!n.path("version").asText().matches("\\d+\\.\\d+\\.\\d+"))throw new ServiceException("版本号非法");
  validateDefinition(library,n);
  try{mapper.insert(library,n.path("skill_id").asText(),n.path("version").asText(),pack.path("pack_hash").asText(),json.writeValueAsString(body),SecurityUtils.getUsername());}
  catch(org.springframework.dao.DuplicateKeyException e){throw new ServiceException("技能版本已存在，请使用新版本号");}
  catch(java.io.IOException e){throw new ServiceException("技能配置格式错误");}
 }
 public Map<String,Object> trial(Long library,String id,String version){
  visible(library);Map<String,Object> row=mapper.version(library,id,version);if(row==null)throw new ServiceException("技能版本不存在");
  Map<String,Object> result=agent.post("/agent/insight/trial",Collections.singletonMap("skill_id",id));
  result.put("registry_version",version);result.put("boundary","固定合成客群试跑，仅核对包内模板与Guard；未执行此版本的实际指标绑定，不更新复核或发布状态。");return result;
 }
 private void validateDefinition(Long library,JsonNode n){
  try{LocalDate.parse(n.path("data_as_of").asText());}catch(Exception e){throw new ServiceException("必须登记真实数据日期");}
  for(String key:Arrays.asList("binding_version","benchmark_version"))if(!n.path(key).asText().matches("\\d+\\.\\d+\\.\\d+"))throw new ServiceException("指标或基准版本非法");
  if(n.path("benchmark_definition").asText().trim().isEmpty()||n.path("benchmark_definition").asText().length()>500)throw new ServiceException("必须登记基准定义");
  if(!n.path("bindings").isArray()||n.path("bindings").size()<1||n.path("bindings").size()>60)throw new ServiceException("指标绑定数量非法");
  JsonNode semanticCatalog=json.valueToTree(agent.get("/agent/insight/catalog")),codePack=null;
  for(JsonNode pack:semanticCatalog.path("skills"))if(n.path("skill_id").asText().equals(pack.path("manifest").path("id").asText()))codePack=pack;
  if(codePack==null)throw new ServiceException("技能未在代码包登记");
  Set<Long> eligible=new HashSet<>(catalog.eligibleTagIds(library,String.valueOf(catalog.activeBundle(library).get("snapshot_id"))));Set<String> keys=new HashSet<>();
  for(JsonNode b:n.path("bindings")) {
   b.fieldNames().forEachRemaining(k->{if(!Arrays.asList("metric","category","tag_ids","unit","kind","threshold","enum_map").contains(k))throw new ServiceException("指标绑定不能含SQL或物理字段");});
   String name=b.path("metric").asText(),category=b.path("category").asText("");
   JsonNode pack=codePack;boolean declared="org_scope".equals(name);for(JsonNode m:pack.path("manifest").path("metrics"))if(name.equals(m.asText()))declared=true;if(!declared)throw new ServiceException("指标未在技能声明");
   if("product_holding".equals(name)&&!Arrays.asList("wealth","fund","insurance").contains(category)||"asset_holder".equals(name)&&!Arrays.asList("liquid","fixed","investment").contains(category))throw new ServiceException("指标品类非法");
   if(!name.matches("[a-z][a-z0-9_.-]{0,79}")||(!category.isEmpty()&&!category.matches("[a-z][a-z0-9_]{0,23}"))||!keys.add(name+":"+category))throw new ServiceException("指标标识重复或非法");
   if(!Arrays.asList("人","元","%","pp","分").contains(b.path("unit").asText()))throw new ServiceException("绑定单位非法");
   if(!"org_scope".equals(name)){JsonNode semantic=null;for(JsonNode metric:semanticCatalog.path("metrics"))if(name.equals(metric.path("id").asText()))semantic=metric;
    if(semantic==null||!b.path("unit").asText().equals(semantic.path("unit").asText()))throw new ServiceException("绑定单位与语义指标不一致");}
   if(Arrays.asList("aum","liquid_aum","fixed_aum","investment_aum","value_score").contains(name)&&(!"DIRECT".equals(b.path("kind").asText("DIRECT"))||b.has("enum_map")))throw new ServiceException("金额指标须直接绑定同单位数值来源");
   if(Arrays.asList("product_holding","product_gap").contains(name)&&!"DIRECT".equals(b.path("kind").asText("DIRECT")))throw new ServiceException("产品持有与缺口须绑定同一持有标志映射");
   if(!Arrays.asList("DIRECT","IS_NULL","GT","RATIO_GT","RECENT_CONTACT").contains(b.path("kind").asText("DIRECT")))throw new ServiceException("绑定转换不受支持");
   if(!b.path("tag_ids").isArray()||b.path("tag_ids").size()<1||b.path("tag_ids").size()>2)throw new ServiceException("来源标签数量非法");
   if("RATIO_GT".equals(b.path("kind").asText())?b.path("tag_ids").size()!=2:b.path("tag_ids").size()!=1)throw new ServiceException("绑定来源数量与转换口径不一致");
   if(Arrays.asList("GT","RATIO_GT").contains(b.path("kind").asText())&&(!b.path("threshold").isNumber()||b.path("threshold").decimalValue().abs().compareTo(new java.math.BigDecimal("1000000000000000"))>0))throw new ServiceException("治理阈值非法");
   if(b.has("enum_map")&&(!"DIRECT".equals(b.path("kind").asText("DIRECT"))||!b.path("enum_map").isObject()||b.path("enum_map").size()<1||b.path("enum_map").size()>32||"channel".equals(name)))throw new ServiceException("治理码值映射非法");
   b.path("enum_map").fields().forEachRemaining(e->{if(!e.getKey().matches("[A-Za-z0-9_-]{1,24}")||!e.getValue().isIntegralNumber()||e.getValue().asInt()<0||e.getValue().asInt()>(Arrays.asList("risk_level","aum_tier","org_scope").contains(name)?12:1))throw new ServiceException("治理码值映射非法");});
   for(JsonNode tid:b.path("tag_ids"))if(!tid.isIntegralNumber()||!eligible.contains(tid.asLong()))throw new ServiceException("绑定标签未发布或无权限",403);
  }
  if(n.has("suitability")&&!n.path("suitability").isObject())throw new ServiceException("适当性映射须为对象");
  n.path("suitability").fields().forEachRemaining(e->{if(!Arrays.asList("wealth","fund","insurance").contains(e.getKey())||!e.getValue().isIntegralNumber()||e.getValue().asInt()<0||e.getValue().asInt()>10)throw new ServiceException("适当性映射非法");});
 }
 private void completeDefinition(JsonNode n,JsonNode pack){
  Set<String> bound=new HashSet<>();for(JsonNode b:n.path("bindings"))bound.add(b.path("metric").asText()+":"+b.path("category").asText(""));
  for(JsonNode metric:pack.path("manifest").path("metrics")){
   String m=metric.asText();if("suitability".equals(m))continue;
   if("product_holding".equals(m)){if(Collections.disjoint(bound,Arrays.asList("product_holding:wealth","product_holding:fund","product_holding:insurance")))throw new ServiceException("至少绑定一个有效产品品类");continue;}
   List<String> categories="asset_holder".equals(m)?Arrays.asList("liquid","fixed","investment"):"product_holding".equals(m)?Arrays.asList("wealth","fund","insurance"):Collections.singletonList("");
   for(String category:categories)if(!bound.contains(m+":"+category))throw new ServiceException("指标待绑定："+m+(category.isEmpty()?"":":"+category));
  }
 }
 public boolean reportVisible(Long library,Map<String,Object> report){
  try{
   JsonNode n=json.valueToTree(report),cohort=n.path("cohort");
   long age=java.time.temporal.ChronoUnit.DAYS.between(LocalDate.parse(cohort.path("data_as_of").asText()),LocalDate.now(java.time.ZoneId.of("Asia/Shanghai")));
   if(cohort.path("synthetic").asBoolean()||age<0||age>2||!Objects.equals(cohort.path("snapshot_id").asText(),String.valueOf(catalog.activeBundle(library).get("snapshot_id"))))return false;
   for(JsonNode r:n.path("results")){
    if("BLOCKED".equals(r.path("status").asText())){if(r.path("facts").size()>0||r.path("cards").size()>0||r.path("charts").size()>0)return false;continue;}
    Map<String,Object> row=published(library,r.path("skill_id").asText());JsonNode def=definition(row);
    if(!Objects.equals(row.get("version"),r.path("registry_version").asText())||!TsSnapshotCanonicalizer.sha256(String.valueOf(row.get("definition_json"))).equals(r.path("definition_hash").asText())||!Objects.equals(row.get("pack_hash"),r.path("pack_hash").asText())||!cohort.path("binding_version").asText().equals(def.path("binding_version").asText())||!cohort.path("data_as_of").asText().equals(def.path("data_as_of").asText()))return false;
   }return true;
  }catch(ServiceException|java.time.DateTimeException e){return false;}
 }
 private JsonNode definition(Map<String,Object> row){try{return json.readTree(String.valueOf(row.get("definition_json")));}catch(Exception e){throw new ServiceException("技能记录格式错误");}}
 @Transactional public void review(Long library,String id,String version){
  visible(library);Map<String,Object> row=mapper.version(library,id,version);if(row==null)throw new ServiceException("技能版本不存在");
  validateDefinition(library,definition(row));JsonNode pack=local(id);completeDefinition(definition(row),pack);if(!pack.path("pack_hash").asText().equals(row.get("pack_hash")))throw new ServiceException("代码包已变化，请登记新版本");
  Map<String,Object> gate=agent.post("/agent/insight/evaluate",Collections.singletonMap("skill_id",id));
  if(!Boolean.TRUE.equals(gate.get("passed"))||!Objects.equals(gate.get("pack_hash"),row.get("pack_hash")))throw new ServiceException("评测门禁未通过");
  try{if(mapper.review(library,id,version,json.writeValueAsString(gate),SecurityUtils.getUsername())!=1)throw new ServiceException("该版本不在草稿状态");}
  catch(java.io.IOException e){throw new ServiceException("门禁记录格式错误");}
 }
 @Transactional public void publish(Long library,String id,String version){
  visible(library);mapper.lockLibrary(library);Map<String,Object> row=mapper.version(library,id,version);if(row==null||!Arrays.asList("REVIEWED","RETIRED").contains(row.get("status")))throw new ServiceException("只有复核版本可以发布或回滚");
  JsonNode pack=local(id);if(!Objects.equals(pack.path("pack_hash").asText(),row.get("pack_hash")))throw new ServiceException("发布包hash不一致");
  validateDefinition(library,definition(row));completeDefinition(definition(row),pack);
  try{JsonNode gate=json.readTree(String.valueOf(row.get("evaluation_json")));if(!gate.path("passed").asBoolean()||!gate.path("pack_hash").asText().equals(row.get("pack_hash")))throw new ServiceException("评测门禁已失效");}
  catch(java.io.IOException e){throw new ServiceException("评测门禁缺失");}
  mapper.retire(library,id);if(mapper.publish(library,id,version,SecurityUtils.getUsername())!=1)throw new ServiceException("发布状态变化",409);
 }
 @Transactional public void retire(Long library,String id){visible(library);mapper.lockLibrary(library);mapper.retire(library,id);}
 public Map<String,Object> published(Long library,String id){visible(library);List<Map<String,Object>> rows=mapper.list(library);for(Map<String,Object> row:rows)if(id.equals(row.get("skill_id"))&&"PUBLISHED".equals(row.get("status"))){
   if(!Objects.equals(local(id).path("pack_hash").asText(),row.get("pack_hash")))throw new ServiceException("技能包变化，原发布门禁失效",409);
   validateDefinition(library,definition(row));return row;
  }throw new ServiceException("技能尚未发布，请先完成绑定和复核");}
}
