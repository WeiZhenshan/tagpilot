package com.ruoyi.taglibrary.service;
import java.sql.*;
import java.util.*;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
class TsInsightSqlCompilerTest {
 private ObjectMapper json=new ObjectMapper();
 private Connection db;
 private Set<String> metrics=new HashSet<>(Arrays.asList("customer_count","aum","aum_tier","risk_level","holding","marketing_excluded","risk_mismatch","do_not_disturb","recent_contact","no_channel","value_score","demand_event","product_gap","historical_response","channel_reach","disturbance_penalty","channel"));
 @BeforeEach void setup()throws Exception {
  db=DriverManager.getConnection("jdbc:h2:mem:insight"+UUID.randomUUID()+";MODE=MySQL;DATABASE_TO_LOWER=TRUE");
  db.createStatement().execute("create table customer(customer_count int,aum decimal(18,2),aum_tier int,risk_level int,holding int,marketing_excluded int,risk_mismatch int,do_not_disturb int,recent_contact int,no_channel int,value_score int,demand_event int,product_gap int,historical_response int,channel_reach int,disturbance_penalty int,channel varchar(20))");
  try(PreparedStatement ps=db.prepareStatement("insert into customer values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")) {
   for(int i=0;i<240;i++) {
    Object[] row={i+1, i<120?200000:800000,i<120?0:1,3,i<60?1:0,i>=180?1:0,i>=220?1:0,i>=200&&i<220?1:0,i>=180&&i<200?1:0,0,i<80?1500000:i<140?500000:100000,i<80?1:0,50,i<80?1:0,1,0,"app"};
    for(int j=0;j<row.length;j++)ps.setObject(j+1,row[j]);ps.addBatch();
   }ps.executeBatch();
  }
 }
 @AfterEach void close()throws Exception{db.close();}
 private List<Map<String,Object>> query(String raw)throws Exception {
  String sql=TsInsightSqlCompiler.compile(json.readTree(raw),"select * from customer",metrics,Collections.singletonMap("wealth",3));
  List<Map<String,Object>> out=new ArrayList<>();try(ResultSet rs=db.createStatement().executeQuery(sql)){while(rs.next()){Map<String,Object> row=new LinkedHashMap<>();for(int i=1;i<=rs.getMetaData().getColumnCount();i++)row.put(rs.getMetaData().getColumnLabel(i),rs.getObject(i));out.add(row);}}return out;
 }
 @Test void aggregateAndContinuousPercentilesMatchReference()throws Exception {
  Map<String,Object> sum=query("{\"id\":\"sum\",\"node\":\"aggregate\",\"metric\":\"aum\",\"operation\":\"sum\"}").get(0);
  assertEquals(120000000.,((Number)sum.get("value")).doubleValue());
  assertEquals(500000.,((Number)query("{\"id\":\"median\",\"node\":\"aggregate\",\"metric\":\"aum\",\"operation\":\"median\"}").get(0).get("value")).doubleValue());
  assertEquals(200000.,((Number)query("{\"id\":\"p25\",\"node\":\"aggregate\",\"metric\":\"aum\",\"operation\":\"percentile\",\"percentile\":25}").get(0).get("value")).doubleValue());
 }
 @Test void bandAndFlagFunnelMatchIndependentCounts()throws Exception {
  List<Map<String,Object>> bands=query("{\"id\":\"bands\",\"node\":\"band\",\"metric\":\"aum\",\"cuts\":[300000,1000000]}");assertEquals(2,bands.size());assertEquals(240,bands.stream().mapToInt(r->((Number)r.get("value")).intValue()).sum());
  Map<String,Object> r=query("{\"id\":\"opportunity\",\"node\":\"flag_rate\",\"metric\":\"holding\",\"suitability_category\":\"wealth\",\"exclusions\":[\"marketing_excluded\"]}").get(0);
  assertEquals(60,((Number)r.get("holders")).intValue());assertEquals(180,((Number)r.get("unheld")).intValue());assertEquals(180,((Number)r.get("suitable")).intValue());assertEquals(120,((Number)r.get("opportunity")).intValue());
 }
 @Test void scoreExcludesBeforeScoringAndKeepsTwoReasons()throws Exception {
  String score="{\"id\":\"priority\",\"node\":\"score\",\"profile\":\"default_v1\",\"assumption\":true,\"reason_top_k\":2,\"exclusions\":[\"risk_mismatch\",\"do_not_disturb\",\"recent_contact\",\"no_channel\"],\"tier_cuts\":[40,70],\"components\":["+
   "{\"metric\":\"value_score\",\"weight\":1,\"bands\":[{\"upper\":300000,\"points\":5},{\"upper\":1000000,\"points\":15},{\"upper\":null,\"points\":25}]},"+
   "{\"metric\":\"demand_event\",\"weight\":1,\"bands\":[{\"upper\":1,\"points\":0},{\"upper\":null,\"points\":20}]},"+
   "{\"metric\":\"product_gap\",\"weight\":1,\"bands\":[{\"upper\":10,\"points\":0},{\"upper\":null,\"points\":20}]},"+
   "{\"metric\":\"historical_response\",\"weight\":1,\"bands\":[{\"upper\":1,\"points\":0},{\"upper\":null,\"points\":15}]},"+
   "{\"metric\":\"channel_reach\",\"weight\":1,\"bands\":[{\"upper\":1,\"points\":0},{\"upper\":null,\"points\":10}]},"+
   "{\"metric\":\"disturbance_penalty\",\"weight\":1,\"bands\":[{\"upper\":1,\"points\":0},{\"upper\":null,\"points\":-20}]}]}";
  List<Map<String,Object>> rows=query(score);Map<String,Integer> counts=new HashMap<>();for(Map<String,Object> r:rows){counts.merge(String.valueOf(r.get("d0")),((Number)r.get("n")).intValue(),Integer::sum);if("high".equals(r.get("d0"))){assertEquals("value_score",r.get("reason0"));assertEquals("demand_event",r.get("reason1"));}}
  assertEquals(80,counts.get("high"));assertEquals(60,counts.get("medium"));assertEquals(40,counts.get("low"));assertEquals(20,counts.get("excluded:risk_mismatch"));assertEquals(20,counts.get("excluded:do_not_disturb"));assertEquals(20,counts.get("excluded:recent_contact"));
 }
 @Test void smallComplementSuppressesWholeNode(){Map<String,Object> out=new HashMap<>();Map<String,Object> r=new HashMap<>();r.put("n",240);r.put("holders",235);TsInsightQueryService.suppress(out,Collections.singletonList(r));assertEquals("SUPPRESSED",out.get("status"));assertTrue(((List<?>)out.get("rows")).isEmpty());}
 @Test void injectedSqlAndUnknownMetricRejected(){assertThrows(Exception.class,()->query("{\"id\":\"x\",\"node\":\"aggregate\",\"metric\":\"aum\",\"operation\":\"sum\",\"sql\":\"select * from customer\"}"));assertThrows(Exception.class,()->query("{\"id\":\"x\",\"node\":\"aggregate\",\"metric\":\"password\",\"operation\":\"sum\"}"));}
}
