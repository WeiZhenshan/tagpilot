package com.ruoyi.taglibrary.service;

import java.sql.*;
import java.util.*;
import com.fasterxml.jackson.databind.*;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.databroker.metadata.JdbcConnectionFactory;
import com.ruoyi.databroker.service.DpOnlineVersionResolver;
import com.ruoyi.databroker.domain.DpDataSource;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.mapper.TlObjectGroupExtMapper;
import com.ruoyi.objectgroup.service.IRuleSqlBuilder;
import com.ruoyi.taglibrary.domain.TlTag;
import com.ruoyi.taglibrary.mapper.TlTagMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import static com.ruoyi.taglibrary.service.TsSnapshotAssembler.map;

/** 权威绑定→SQL→聚合结果。Python/浏览器不能传入SQL；同一只读事务中读取全部节点。 */
@Service
public class TsInsightQueryService {
    @Autowired private TlObjectGroupExtMapper ext;
    @Autowired private TlTagMapper tags;
    @Autowired private DpOnlineVersionResolver versions;
    @Autowired private IRuleSqlBuilder rules;
    @Autowired private com.ruoyi.objectgroup.service.impl.RuleTagValidator ruleValidator;
    @Autowired private JdbcConnectionFactory connections;
    @Autowired private DataBrokerCryptoService crypto;
    @Autowired private ObjectMapper json;
    @org.springframework.beans.factory.annotation.Value("${tagpilot.insight.benchmark-cache-seconds:60}") private long cacheSeconds=60;
    private final ThreadLocal<Long> queryDeadline=new ThreadLocal<>();
    private final java.util.concurrent.ConcurrentMap<String,CacheEntry> benchmarkCache=new java.util.concurrent.ConcurrentHashMap<>();
    private static final class CacheEntry {final long until;final String rows;CacheEntry(long until,String rows){this.until=until;this.rows=rows;}}
    @SuppressWarnings("unchecked") private List<Map<String,Object>> benchmarkRows(Connection connection,String sql,String key)throws Exception {
        long now=System.currentTimeMillis();CacheEntry cached=benchmarkCache.get(key);
        if(cacheSeconds>0&&cached!=null&&cached.until>now)return json.readValue(cached.rows,List.class);
        List<Map<String,Object>> rows=read(connection,sql);
        if(cacheSeconds>0){benchmarkCache.entrySet().removeIf(e->e.getValue().until<=now);if(benchmarkCache.size()>=64)benchmarkCache.clear();benchmarkCache.put(key,new CacheEntry(now+Math.min(cacheSeconds,86400)*1000,json.writeValueAsString(rows)));}
        return rows;
    }

    private static String quote(String name) {
        if(name==null||!name.matches("[A-Za-z_][A-Za-z0-9_]{0,127}"))throw new ServiceException("洞察来源字段非法");
        return "`"+name+"`";
    }
    private String source(Long library,Long version,JsonNode binding,Set<Long> eligible) {
        List<String> columns=new ArrayList<>();List<Boolean> numeric=new ArrayList<>();
        for(JsonNode tid:binding.path("tag_ids")) {
            if(!tid.isIntegralNumber()||!eligible.contains(tid.asLong()))throw new ServiceException("洞察依赖标签无权限",403);
            TlTag tag=tags.selectTagById(tid.asLong());
            if(tag==null||!Objects.equals(tag.getLibraryId(),library)||!"2".equals(tag.getStatus())||!"AVAILABLE".equals(tag.getSourceStatus())||!Objects.equals(tag.getSourceVersionId(),version))
                throw new ServiceException("洞察标签来源或发布版本已变化",409);
            columns.add(quote(ext.selectColumnNameByAlias(version,tag.getFieldName())));
            numeric.add(tag.getDataType()!=null&&tag.getDataType().toLowerCase(Locale.ROOT).matches("(tinyint|smallint|mediumint|int|integer|bigint|decimal|numeric|float|double|real|number)(\\(.*\\))?( unsigned)?"));
        }
        String kind=binding.path("kind").asText("DIRECT");
        if(columns.size()<1||columns.size()>2)throw new ServiceException("绑定须含一或两个来源标签");
        if(binding.path("enum_map").isObject()) {
            if(!"DIRECT".equals(kind)||"channel".equals(binding.path("metric").asText()))throw new ServiceException("码值映射只适用声明的直接指标");
            StringBuilder mapped=new StringBuilder("case ");
            binding.path("enum_map").fields().forEachRemaining(e->{
                if(!e.getKey().matches("[A-Za-z0-9_-]{1,24}")||!e.getValue().isIntegralNumber()||e.getValue().asInt()<0||e.getValue().asInt()>12)throw new ServiceException("治理码值映射非法");
                mapped.append("when ").append(columns.get(0)).append("='").append(e.getKey()).append("' then ").append(e.getValue().asInt()).append(" ");
            });
            return mapped+"else null end";
        }
        if(columns.size()<1||columns.size()>2)throw new ServiceException("绑定须含一或两个来源标签");
        String column=columns.get(0);
        if(Arrays.asList("GT","RATIO_GT").contains(kind)&&numeric.contains(false))throw new ServiceException("数值比较来源须为已发布数值字段");
        if("DIRECT".equals(kind)&&Arrays.asList("aum","liquid_aum","fixed_aum","investment_aum","value_score").contains(binding.path("metric").asText())&&!numeric.get(0))throw new ServiceException("资产或价值指标来源须为已发布数值字段");
        if("DIRECT".equals(kind)) {
            String metric=binding.path("metric").asText();
            if("org_scope".equals(metric))return "case when cast("+column+" as char) regexp '^[A-Za-z0-9_-]{1,24}$' then "+column+" else null end";
            if("channel".equals(metric))return "case when "+column+" in ('phone','app','branch','manager') then "+column+" else null end";
            if(Arrays.asList("risk_level","aum_tier").contains(metric)){if(!numeric.get(0))throw new ServiceException("等级文本须登记治理码值映射");return "case when "+column+">=0 and "+column+"<=12 and "+column+"=floor("+column+") then cast("+column+" as signed) else null end";}
            if(metric.startsWith("product_holding")||"product_gap".equals(metric)||Arrays.asList("risk_mismatch","marketing_excluded","do_not_disturb","no_channel","channel_reach","demand_event","historical_response","disturbance_penalty").contains(metric))return numeric.get(0)?"case when "+column+"=0 then 0 when "+column+"=1 then 1 else null end":"case when cast("+column+" as char)='0' then 0 when cast("+column+" as char)='1' then 1 else null end";
            return column;
        }
        if("RECENT_CONTACT".equals(kind))return column;
        if("IS_NULL".equals(kind))return "case when "+column+" is null then 1 else 0 end";
        if("GT".equals(kind))return "case when "+column+" is null then null when "+column+">"+number(binding.path("threshold"))+" then 1 else 0 end";
        if("RATIO_GT".equals(kind)&&columns.size()==2)return "case when "+column+" is null or "+columns.get(1)+" is null or "+columns.get(1)+"<=0 then null when "+column+"/"+columns.get(1)+">"+number(binding.path("threshold"))+" then 1 else 0 end";
        throw new ServiceException("指标绑定转换不受支持");
    }
    private String number(JsonNode n) {
        if(!n.isNumber()||n.decimalValue().abs().compareTo(new java.math.BigDecimal("1000000000000000"))>0)throw new ServiceException("治理阈值非法");
        return n.decimalValue().toPlainString();
    }
    public Map<String,Object> execute(Long library,RulePayload rule,JsonNode plan,JsonNode definition,Set<Long> eligible) {
        Long dataset=ext.selectDatasetIdByLibrary(library);
        com.ruoyi.databroker.domain.vo.DpResolvedVersion resolved=versions.resolve(dataset);
        if(resolved==null)throw new ServiceException("洞察数据集没有在线版本");
        Long version=resolved.getVersionId();
        ruleValidator.validateRule(library,version,rule);
        ruleValidator.validateCodeValues(library,rule);
        String key=rules.resolveObjectKeyColumn(version,rule);
        // 调用既有规则构建器重新验证字段/条件；禁止使用带limit的样例SQL。
        String cohortIds=rules.buildSql(version,rule,IRuleSqlBuilder.MODE_IDS);
        JsonNode versionDefinition;
        try {versionDefinition=json.readTree(ext.selectVersionDefinitionJson(version));}catch(Exception e){throw new ServiceException("数据集定义格式错误");}
        String table=quote(ext.selectTableObjectName(versionDefinition.path("tableId").asLong()));
        Set<String> available=new LinkedHashSet<>();List<String> projections=new ArrayList<>();
        for(JsonNode binding:definition.path("bindings")) {
            String name=binding.path("metric").asText();String category=binding.path("category").asText("");
            if(!category.isEmpty())name+="_"+category;
            if(!available.add(name))throw new ServiceException("指标绑定重复");
            String expression=source(library,version,binding,eligible);
            if("product_gap".equals(name)&&definition.has("_g2_gap"))expression="case when "+expression+" is null then null when "+expression+"=0 then "+number(definition.path("_g2_gap"))+" else 0 end";
            if("recent_contact".equals(name)&&"RECENT_CONTACT".equals(binding.path("kind").asText())) {
                java.time.LocalDate asOf=java.time.LocalDate.parse(plan.path("cohort").path("data_as_of").asText());
                int days=plan.path("parameters").path("recent_contact_days").asInt(7);
                expression="case when "+expression+" is null then null when "+expression+">='"+asOf.minusDays(days)+"' then 1 else 0 end";
            }
            projections.add(expression+" as "+TsInsightSqlCompiler.id(name));
        }
        if(projections.isEmpty()||projections.size()>60)throw new ServiceException("洞察绑定数量非法");
        String base="select "+String.join(",",projections)+" from "+table;
        String cohort=base+" where "+quote(key)+" in ("+cohortIds+")";
        String benchmark=base;
        String benchmarkType=plan.path("parameters").path("benchmark_type").asText("standardized");
        if("same_aum".equals(benchmarkType)) {
            if(!available.contains("aum_tier"))throw new ServiceException("同层级基准缺少AUM层级绑定");
            benchmark="select * from ("+base+") _peer where `aum_tier` in (select distinct `aum_tier` from ("+cohort+") _cohort)";
        }
        if("same_org".equals(benchmarkType)) {
            if(!available.contains("org_scope"))throw new ServiceException("同机构基准须登记权威机构范围绑定");
            benchmark="select * from ("+base+") _peer where `org_scope` in (select distinct `org_scope` from ("+cohort+") _cohort)";
        }
        Map<String,Integer> suitability=new LinkedHashMap<>();
        definition.path("suitability").fields().forEachRemaining(e->{if(!e.getValue().canConvertToInt()||e.getValue().asInt()<0||e.getValue().asInt()>10)throw new ServiceException("适当性等级非法");suitability.put(e.getKey(),e.getValue().asInt());});
        List<Map<String,Object>> aggregates=new ArrayList<>();
        DpDataSource ds=ext.selectDataSourceByDataset(dataset);if(ds==null)throw new ServiceException("数据源不可用");
        queryDeadline.set(System.nanoTime()+60_000_000_000L);
        try(Connection connection=connections.createConnection(ds,ds.getPasswordCipher()==null?"":crypto.decrypt(ds.getPasswordCipher()))) {
            connection.setReadOnly(true);connection.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ);connection.setAutoCommit(false);
            // 原始客户键唯一性在Java内验证，重复行不能被当作更多客户。
            try(Statement st=connection.createStatement()) {
                st.setQueryTimeout(30);
                try(ResultSet rs=st.executeQuery("select count(*) as n,count(distinct "+quote(key)+") as keys_n from "+table)) {
                    if(!rs.next()||rs.getLong("n")!=rs.getLong("keys_n"))throw new ServiceException("客户键非唯一或存在空值，不能聚合");
                }
            }
            if("same_org".equals(benchmarkType))try(Statement st=connection.createStatement()){
                st.setQueryTimeout(30);try(ResultSet rs=st.executeQuery("select count(distinct `org_scope`) as orgs,count(*)-count(`org_scope`) as missing from ("+cohort+") _org")){
                    if(!rs.next()||rs.getLong("orgs")!=1||rs.getLong("missing")!=0)throw new ServiceException("客群机构不唯一或缺失，不能使用同机构基准");
                }
            }
            for(JsonNode query:plan.path("queries")) {
                if(System.nanoTime()>=queryDeadline.get())throw new ServiceException("洞察取数预算耗尽，请缩小已确认范围或稍后重试");
                List<String> categories=new ArrayList<>();String metric=query.path("metric").asText();
                if("product_holding".equals(metric)||"suitability".equals(metric))for(JsonNode c:plan.path("parameters").path("categories"))categories.add(c.asText());
                else if("asset_holder".equals(metric))categories.addAll(Arrays.asList("liquid","fixed","investment"));
                else categories.add("");
                for(String category:categories) {
                    com.fasterxml.jackson.databind.node.ObjectNode q=query.deepCopy();String id=q.path("id").asText();
                    Map<String,Object> output=map("query_id",id,"evidence_id",UUID.randomUUID().toString(),"status","AVAILABLE","rows",new ArrayList<>(),"reason","");
                    if(!category.isEmpty()) {output.put("category",category);q.put("metric",("suitability".equals(metric)?"product_holding":metric)+"_"+category);}
                    if(!"score".equals(q.path("node").asText())&&!available.contains(q.path("metric").asText())){output.put("status","MISSING");output.put("reason","请求品类尚未绑定");aggregates.add(output);continue;}
                    if(Arrays.asList("suitable","opportunity").contains(id))q.put("suitability_category",category);
                    if(q.hasNonNull("suitability_category")&&!suitability.containsKey(q.path("suitability_category").asText())) {
                        output.put("status","MISSING");output.put("reason","品类适当性映射未复核");aggregates.add(output);continue;
                    }
                    boolean peer="benchmark".equals(q.path("population").asText());String sql=TsInsightSqlCompiler.compile(q,peer?benchmark:cohort,available,suitability);
                    String cacheKey=TsSnapshotCanonicalizer.sha256(library+":"+com.ruoyi.common.utils.SecurityUtils.getUserId()+":"+version+":"+definition.toString()+":"+plan.path("pack_hash").asText()+":"+plan.path("snapshot_id").asText()+":"+plan.path("binding_version").asText()+":"+plan.path("cohort").path("data_as_of").asText()+":"+sql);
                    List<Map<String,Object>> rows=peer?benchmarkRows(connection,sql,cacheKey):read(connection,sql);
                    if(Arrays.asList("coverage","benchmark_coverage").contains(id)&&q.path("dimensions").size()==2)output.put("rows",rows);else suppress(output,rows);aggregates.add(output);
                }
            }
            fallbackCoverage(aggregates);
            connection.rollback();
            if(!Objects.equals(versions.resolve(dataset).getVersionId(),version))throw new ServiceException("数据集在线版本已变化",409);
        }catch(ServiceException e){throw e;}catch(Exception e){ServiceException error=new ServiceException("洞察聚合查询失败，请检查数据源与版本");error.initCause(e);throw error;}finally{queryDeadline.remove();}
        Map<String,Object> result=map("skill_id",plan.path("skill_id").asText(),"pack_hash",plan.path("pack_hash").asText(),"snapshot_id",plan.path("snapshot_id").asText(),"binding_version",plan.path("binding_version").asText(),"plan_hash",plan.path("cohort").path("plan_hash").asText(),"data_as_of",plan.path("cohort").path("data_as_of").asText(),"queries",aggregates,
            "benchmark_definition",("same_aum".equals(benchmarkType)?"同AUM层级":"same_org".equals(benchmarkType)?"同机构":"all_customers".equals(benchmarkType)?"授权总体":"结构标准化基准")+"；"+definition.path("benchmark_definition").asText(),"benchmark_version",definition.path("benchmark_version").asText(),"scope_hash",definition.path("scope_hash").asText());
        return result;
    }
    private List<Map<String,Object>> read(Connection c,String sql)throws SQLException {
        List<Map<String,Object>> rows=new ArrayList<>();
        try(Statement st=c.createStatement()) {
            long remaining=queryDeadline.get()==null?30:(queryDeadline.get()-System.nanoTime())/1_000_000_000L;if(remaining<1)throw new ServiceException("洞察取数预算耗尽");
            st.setQueryTimeout((int)Math.min(30,remaining));st.setMaxRows(145);
            try(ResultSet rs=st.executeQuery(sql)) {
                while(rs.next()) {
                    if(rows.size()>=144)throw new ServiceException("洞察分类数量过多，需要治理合并");
                    Map<String,Object> row=map("status","AVAILABLE");List<String> dims=new ArrayList<>(),reasons=new ArrayList<>();Map<String,Object> contributions=new LinkedHashMap<>();
                    for(int i=1;i<=rs.getMetaData().getColumnCount();i++) {
                        String label=rs.getMetaData().getColumnLabel(i).toLowerCase(Locale.ROOT);Object value=rs.getObject(i);
                        if(label.matches("d[01]"))dims.add(value==null?"unknown":String.valueOf(value));
                        else if(label.matches("reason[01]"))reasons.add(String.valueOf(value));
                        else if(label.startsWith("c_"))contributions.put(label.substring(2),value);
                        else if(Arrays.asList("n","value","holders","missing","unheld","suitable","opportunity").contains(label))row.put(label,value);
                        else throw new ServiceException("聚合输出字段非法");
                    }
                    row.put("dimensions",dims);
                    if(!contributions.isEmpty()&&!dims.get(0).startsWith("excluded:")){row.put("contributions",contributions);row.put("reasons",reasons);}
                    rows.add(row);
                }
            }
        }return rows;
    }
    @SuppressWarnings("unchecked") private static void fallbackCoverage(List<Map<String,Object>> outputs){
        Map<String,Map<String,Object>> cohort=new HashMap<>(),baseline=new HashMap<>();
        for(Map<String,Object> q:outputs){if("coverage".equals(q.get("query_id")))cohort.put(String.valueOf(q.get("category")),q);if("benchmark_coverage".equals(q.get("query_id")))baseline.put(String.valueOf(q.get("category")),q);}
        for(String category:cohort.keySet()){
            Map<String,Object> c=cohort.get(category),b=baseline.get(category);if(b==null)continue;
            List<Map<String,Object>> cr=(List<Map<String,Object>>)c.get("rows"),br=(List<Map<String,Object>>)b.get("rows");
            String mode="aum_risk";
            if(!comparable(cr,br))for(int axis=0;axis<2;axis++){
                List<Map<String,Object>> cc=collapseCoverage(cr,axis),bb=collapseCoverage(br,axis);
                if(comparable(cc,bb)){cr=cc;br=bb;mode=axis==0?"aum":"risk";break;}
            }
            c.put("standardization_mode",mode);b.put("standardization_mode",mode);suppress(c,cr);suppress(b,br);
        }
    }
    @SuppressWarnings("unchecked") private static boolean comparable(List<Map<String,Object>> c,List<Map<String,Object>> b){
        if(c.isEmpty()||b.isEmpty())return false;Map<String,Long> baseline=new HashMap<>();
        for(Map<String,Object> r:b){List<String> dims=(List<String>)r.get("dimensions");if(dims.contains("unknown"))return false;baseline.put(dims.toString(),validSample(r));}
        for(Map<String,Object> r:c){List<String> dims=(List<String>)r.get("dimensions");if(dims.contains("unknown")||validSample(r)<30||baseline.getOrDefault(dims.toString(),0L)<30)return false;}return true;
    }
    private static long validSample(Map<String,Object> r){return ((Number)r.get("n")).longValue()-(r.get("missing")==null?0:((Number)r.get("missing")).longValue());}
    @SuppressWarnings("unchecked") private static List<Map<String,Object>> collapseCoverage(List<Map<String,Object>> rows,int axis){
        Map<String,Map<String,Object>> merged=new TreeMap<>();for(Map<String,Object> r:rows){List<String> dims=(List<String>)r.get("dimensions");if(dims.size()!=2||dims.contains("unknown"))return Collections.emptyList();String key=dims.get(axis);
            Map<String,Object> out=merged.computeIfAbsent(key,k->map("status","AVAILABLE","dimensions",axis==0?Arrays.asList(k,"all"):Arrays.asList("all",k)));
            for(String field:Arrays.asList("n","holders","missing","unheld","suitable","opportunity"))if(r.get(field)!=null)out.put(field,((Number)r.get(field)).longValue()+(out.get(field)==null?0:((Number)out.get(field)).longValue()));
        }return new ArrayList<>(merged.values());
    }
    /** 发现小格时整组抑制，阻断从合计减去其余格恢复小格。漏斗差额也执行互补格检查。 */
    static void suppress(Map<String,Object> output,List<Map<String,Object>> rows) {
        boolean small=false;
        for(Map<String,Object> row:rows) {
            long n=row.get("n")==null?0:((Number)row.get("n")).longValue();
            if(n<20)small=true;
            for(String key:Arrays.asList("holders","missing","unheld","suitable","opportunity")) {
                if(row.get(key)!=null){long v=((Number)row.get(key)).longValue();if((v>0&&v<20)||(n-v>0&&n-v<20))small=true;}
            }
            List<Long> stages=new ArrayList<>();for(String key:Arrays.asList("n","unheld","suitable","opportunity"))if(row.get(key)!=null)stages.add(((Number)row.get(key)).longValue());
            for(int i=1;i<stages.size();i++){long delta=stages.get(i-1)-stages.get(i);if(delta>0&&delta<20)small=true;}
        }
        if(small){output.put("status","SUPPRESSED");output.put("reason","小样本或互补格已抑制");output.put("rows",Collections.emptyList());}
        else output.put("rows",rows);
    }
}
