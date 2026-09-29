package com.ruoyi.taglibrary.service;
import java.sql.*;
import java.util.*;
import java.nio.file.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.domain.*;
import com.ruoyi.databroker.domain.vo.DpResolvedVersion;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;
import com.ruoyi.objectgroup.service.impl.RuleTagValidator;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import org.junit.jupiter.api.*;
import org.springframework.test.util.ReflectionTestUtils;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;
/** 发布元数据由mock提供，客户行只在合成H2中，执行真实QueryService与SQL。 */
class TsInsightQueryServiceTest extends com.ruoyi.taglibrary.service.impl.BaseServiceTest {
 private ObjectMapper json=new ObjectMapper();private TsInsightQueryService service;
 private TlTagMapper tags;private DpOnlineVersionResolver versions;private TlObjectGroupExtMapper ext;
 private String url;private Connection keeper;private DpResolvedVersion version;private Set<Long> eligible=new HashSet<>();
 private Map<String,Long> sourceIds=new LinkedHashMap<>();private JsonNode plans;
 @BeforeEach void setup()throws Exception{
  String input=System.getProperty("insight.test.plans");plans=input==null?json.readTree(getClass().getResourceAsStream("/insight/metric-plans.json")):json.readTree(Files.readAllBytes(Paths.get(input)));
  url="jdbc:h2:mem:query"+UUID.randomUUID()+";MODE=MySQL;DATABASE_TO_LOWER=TRUE";keeper=DriverManager.getConnection(url);
  String[] names={"customer_count","aum","aum_tier","risk_level","liquid_aum","fixed_aum","investment_aum","holding","marketing_excluded","value_score","demand_event","historical_response","channel_reach","disturbance_penalty","risk_mismatch","do_not_disturb","recent_contact","no_channel","channel","org_scope"};
  List<String> defs=new ArrayList<>();for(String n:names)defs.add(n+(Arrays.asList("channel","org_scope").contains(n)?" varchar(24)":" decimal(18,2)"));keeper.createStatement().execute("create table customer("+String.join(",",defs)+")");
  try(PreparedStatement ps=keeper.prepareStatement("insert into customer values("+String.join(",",Collections.nCopies(names.length,"?"))+")")){
   for(int i=0;i<800;i++){
    int aum=i<240?(i<120?200000:800000):500000,tier=i<240?(i<120?0:1):(i<520?0:1);
    int holding=i<240?(i<60?1:0):(i<480||i>=520&&i<780?1:0);
    Object[] row={i+1,aum,tier,3,aum*.6,aum*.2,aum*.2,holding,i>=180&&i<240?1:0,i<80?1500000:i<140?500000:100000,i<80?1:0,i<80?1:0,1,0,i>=220&&i<240?1:0,i>=200&&i<220?1:0,i>=180&&i<200?1:0,0,"app","ORG_A"};
    for(int j=0;j<row.length;j++)ps.setObject(j+1,row[j]);ps.addBatch();
   }ps.executeBatch();
  }
  service=new TsInsightQueryService();ext=mock(TlObjectGroupExtMapper.class);tags=mock(TlTagMapper.class);versions=mock(DpOnlineVersionResolver.class);
  IRuleSqlBuilder rules=mock(IRuleSqlBuilder.class);JdbcConnectionFactory connections=mock(JdbcConnectionFactory.class);DataBrokerCryptoService crypto=mock(DataBrokerCryptoService.class);
  ReflectionTestUtils.setField(service,"ext",ext);ReflectionTestUtils.setField(service,"tags",tags);ReflectionTestUtils.setField(service,"versions",versions);ReflectionTestUtils.setField(service,"rules",rules);ReflectionTestUtils.setField(service,"ruleValidator",mock(RuleTagValidator.class));ReflectionTestUtils.setField(service,"connections",connections);ReflectionTestUtils.setField(service,"crypto",crypto);ReflectionTestUtils.setField(service,"json",json);
  version=new DpResolvedVersion();version.setVersionId(7L);when(versions.resolve(1L)).thenReturn(version);when(ext.selectDatasetIdByLibrary(107L)).thenReturn(1L);when(ext.selectVersionDefinitionJson(7L)).thenReturn("{\"tableId\":9}");when(ext.selectTableObjectName(9L)).thenReturn("customer");
  when(rules.resolveObjectKeyColumn(eq(7L),any())).thenReturn("customer_count");when(rules.buildSql(eq(7L),any(),eq(IRuleSqlBuilder.MODE_IDS))).thenReturn("select customer_count from customer where customer_count<=240");
  DpDataSource ds=new DpDataSource();ds.setPasswordCipher("encrypted");when(ext.selectDataSourceByDataset(1L)).thenReturn(ds);when(crypto.decrypt("encrypted")).thenReturn("synthetic");when(connections.createConnection(eq(ds),eq("synthetic"))).thenAnswer(a->DriverManager.getConnection(url));
  for(String name:names){long id=sourceIds.size()+1;sourceIds.put(name,id);eligible.add(id);TlTag t=new TlTag();t.setTagId(id);t.setLibraryId(107L);t.setStatus("2");t.setSourceStatus("AVAILABLE");t.setSourceVersionId(7L);t.setFieldName(name);t.setDataType(Arrays.asList("channel","org_scope").contains(name)?"varchar":"decimal");when(tags.selectTagById(id)).thenReturn(t);when(ext.selectColumnNameByAlias(7L,name)).thenReturn(name);}
 }
 @AfterEach void close()throws Exception{if(keeper!=null)keeper.close();}
 private ObjectNode definition(JsonNode plan){
  ObjectNode d=json.createObjectNode();d.put("benchmark_definition","同数据日已复核合成总体");d.put("benchmark_version","0.1.0");d.put("scope_hash",String.join("",Collections.nCopies(64,"b")));d.put("_g2_gap",45);
  ObjectNode suitability=d.putObject("suitability");for(String c:Arrays.asList("wealth","fund","insurance"))suitability.put(c,3);
  ArrayNode bindings=d.putArray("bindings");
  for(String name:sourceIds.keySet())if(!"holding".equals(name)){ObjectNode b=bindings.addObject();b.put("metric",name);b.putArray("tag_ids").add(sourceIds.get(name));}
  for(String c:Arrays.asList("wealth","fund","insurance")){ObjectNode b=bindings.addObject();b.put("metric","product_holding");b.put("category",c);b.putArray("tag_ids").add(sourceIds.get("holding"));}
  for(String c:Arrays.asList("liquid","fixed","investment")){ObjectNode b=bindings.addObject();b.put("metric","asset_holder");b.put("category",c);b.put("kind","GT");b.put("threshold",0);b.putArray("tag_ids").add(sourceIds.get(c+"_aum"));}
  ObjectNode missing=bindings.addObject();missing.put("metric","aum_missing");missing.put("kind","IS_NULL");missing.putArray("tag_ids").add(sourceIds.get("aum"));
  ObjectNode share=bindings.addObject();share.put("metric","liquid_share");share.put("kind","RATIO_GT");share.put("threshold",.5);share.putArray("tag_ids").add(sourceIds.get("liquid_aum")).add(sourceIds.get("aum"));
  ObjectNode gap=bindings.addObject();gap.put("metric","product_gap");gap.putArray("tag_ids").add(sourceIds.get("holding"));return d;
 }
 @Test void javaAggregateOutputsCrossLanguageReference()throws Exception{
  ArrayNode outputs=json.createArrayNode();for(JsonNode plan:plans){Map<String,Object> batch=service.execute(107L,new RulePayload(),plan,definition(plan),eligible);JsonNode q=json.valueToTree(batch);assertTrue(q.path("queries").size()>0);for(JsonNode row:q.path("queries"))assertEquals("AVAILABLE",row.path("status").asText());outputs.addObject().set("plan",plan);((ObjectNode)outputs.get(outputs.size()-1)).set("batch",q);}
  String output=System.getProperty("insight.test.output");if(output!=null)Files.write(Paths.get(output),json.writerWithDefaultPrettyPrinter().writeValueAsBytes(outputs));
 }
 @Test void sparseCellsCollapseInsideJavaBeforePrivacySuppression()throws Exception{
  keeper.createStatement().execute("update customer set risk_level=2 where customer_count<=20");JsonNode plan=null;for(JsonNode p:plans)if("product_holding_gap".equals(p.path("skill_id").asText()))plan=p;
  JsonNode out=json.valueToTree(service.execute(107L,new RulePayload(),plan,definition(plan),eligible));for(JsonNode q:out.path("queries"))if(Arrays.asList("coverage","benchmark_coverage").contains(q.path("query_id").asText())){assertEquals("aum",q.path("standardization_mode").asText());assertEquals("AVAILABLE",q.path("status").asText());assertEquals(2,q.path("rows").size());}
 }
 @Test void benchmarkCacheDoesNotReuseAnotherScope()throws Exception{
  JsonNode plan=null;for(JsonNode p:plans)if("product_holding_gap".equals(p.path("skill_id").asText()))plan=p;
  ObjectNode def=definition(plan);service.execute(107L,new RulePayload(),plan,def,eligible);keeper.createStatement().execute("update customer set holding=0 where customer_count>240");def.put("scope_hash",String.join("",Collections.nCopies(64,"c")));
  JsonNode out=json.valueToTree(service.execute(107L,new RulePayload(),plan,def,eligible));for(JsonNode q:out.path("queries"))if("benchmark_coverage".equals(q.path("query_id").asText())){long held=0;for(JsonNode row:q.path("rows"))held+=row.path("holders").asLong();assertEquals(60,held);}
 }
 @Test void revokedDependencyStopsBeforeOpeningConnection(){eligible.remove(sourceIds.get("aum"));assertThrows(ServiceException.class,()->service.execute(107L,new RulePayload(),plans.get(0),definition(plans.get(0)),eligible));}
 @Test void duplicateOrNullCustomerKeyBlocksAllAggregates()throws Exception{keeper.createStatement().execute("update customer set customer_count=1 where customer_count=2");assertThrows(ServiceException.class,()->service.execute(107L,new RulePayload(),plans.get(0),definition(plans.get(0)),eligible));}
 @Test void onlineVersionChangeDiscardsAggregates(){DpResolvedVersion changed=new DpResolvedVersion();changed.setVersionId(8L);when(versions.resolve(1L)).thenReturn(version,changed);assertThrows(ServiceException.class,()->service.execute(107L,new RulePayload(),plans.get(0),definition(plans.get(0)),eligible));}
 @Test void missingSuitabilityKeepsCoverageAndNoOpportunity(){JsonNode plan=plans.findValue("no-such-plan");for(JsonNode p:plans)if("product_holding_gap".equals(p.path("skill_id").asText()))plan=p;ObjectNode def=definition(plan);def.set("suitability",json.createObjectNode());JsonNode batch=json.valueToTree(service.execute(107L,new RulePayload(),plan,def,eligible));for(JsonNode q:batch.path("queries"))assertEquals(Arrays.asList("suitable","opportunity").contains(q.path("query_id").asText())?"MISSING":"AVAILABLE",q.path("status").asText());}
}
