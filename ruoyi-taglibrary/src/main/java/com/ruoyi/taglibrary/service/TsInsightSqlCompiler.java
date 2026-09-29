package com.ruoyi.taglibrary.service;

import java.math.BigDecimal;
import java.util.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.ruoyi.common.exception.ServiceException;

/** 四个白名单节点编译器。baseSql及逻辑列只能由服务端已发布绑定生成，客户级中间量留在SQL内。 */
public final class TsInsightSqlCompiler {
    private TsInsightSqlCompiler() { }
    static String id(String id) {
        if (id == null || !id.matches("[a-z][a-z0-9_.-]{0,79}")) throw new ServiceException("洞察指标标识非法");
        return "`" + id + "`";
    }
    private static String metric(JsonNode q, String key, Set<String> available) {
        String name=q.path(key).asText();
        if (!available.contains(name)) throw new ServiceException("洞察指标未绑定："+name);
        return id(name);
    }
    private static String decimal(JsonNode n) {
        if (!n.isNumber()) throw new ServiceException("洞察阈值必须为有限数值");
        BigDecimal v=n.decimalValue();
        if (v.abs().compareTo(new BigDecimal("1000000000000000"))>0) throw new ServiceException("洞察阈值超过范围");
        return v.stripTrailingZeros().toPlainString();
    }
    public static String compile(JsonNode q,String baseSql,Set<String> available,Map<String,Integer> suitability) {
        String node=q.path("node").asText();
        Set<String> allowed=new HashSet<>(Arrays.asList("id","node","population","dimensions","metric"));
        if("aggregate".equals(node))allowed.addAll(Arrays.asList("operation","percentile"));
        else if("band".equals(node))allowed.add("cuts");
        else if("flag_rate".equals(node))allowed.addAll(Arrays.asList("exclusions","suitability_category"));
        else if("score".equals(node))allowed.addAll(Arrays.asList("profile","assumption","exclusions","components","tier_cuts","reason_top_k"));
        else throw new ServiceException("洞察节点不在白名单内");
        q.fieldNames().forEachRemaining(k->{if(!allowed.contains(k))throw new ServiceException("洞察节点含非法字段");});
        List<String> dims=new ArrayList<>(),labels=new ArrayList<>();
        if(q.path("dimensions").size()>2)throw new ServiceException("洞察维度超过限制");
        for(JsonNode d:q.path("dimensions")) {
            if(!available.contains(d.asText()))throw new ServiceException("洞察维度未绑定");
            dims.add(id(d.asText()));labels.add(id(d.asText())+" as d"+(labels.size()));
        }
        String group=dims.isEmpty()?"":" group by "+String.join(",",dims);
        String select=labels.isEmpty()?"":String.join(",",labels)+",";
        String from=" from ("+baseSql+") _b";
        if("score".equals(node))return score(q,baseSql,available);
        String m=metric(q,"metric",available);
        if("band".equals(node)) {
            if(q.path("cuts").size()<1||q.path("cuts").size()>12)throw new ServiceException("分箱数量非法");
            StringBuilder band=new StringBuilder("case ");BigDecimal prior=null;int i=0;
            for(JsonNode cut:q.path("cuts")) {
                BigDecimal v=new BigDecimal(decimal(cut));
                if(prior!=null&&v.compareTo(prior)<=0)throw new ServiceException("分箱边界必须递增");
                band.append("when ").append(m).append(" < ").append(v.toPlainString()).append(" then '").append(i++).append("' ");prior=v;
            }
            band.append("else '").append(i).append("' end");
            return "select "+band+" as d0,count(*) as n,count(*) as `value`"+from+" where "+m+" is not null group by "+band;
        }
        if("flag_rate".equals(node)) {
            String unheld=m+"=0",suitable=unheld;List<String> exclusions=new ArrayList<>();
            if(q.hasNonNull("suitability_category")) {
                Integer minimum=suitability.get(q.path("suitability_category").asText());
                if(minimum==null)throw new ServiceException("品类适当性未复核");
                if(!available.contains("risk_level"))throw new ServiceException("风险等级未绑定");
                suitable+=" and `risk_level` >= "+minimum;
            }
            for(JsonNode e:q.path("exclusions")) {
                if("missing_aum".equals(e.asText())&&available.contains("aum")){exclusions.add("`aum`>0");continue;}
                if("risk_mismatch".equals(e.asText())&&q.hasNonNull("suitability_category"))continue;
                if(!available.contains(e.asText()))throw new ServiceException("硬排除指标未绑定");
                exclusions.add(id(e.asText())+"=0"); // NULL不视为可营销
            }
            String opportunity=suitable+(exclusions.isEmpty()?"":" and "+String.join(" and ",exclusions));
            return "select "+select+"count(*) as n,sum(case when "+m+"=1"+(q.path("exclusions").toString().contains("missing_aum")?" and `aum`>0":"")+" then 1 else 0 end) as holders,"+
                "sum(case when "+m+" is null then 1 else 0 end) as missing,"+
                "sum(case when "+unheld+" then 1 else 0 end) as unheld,"+
                "sum(case when "+suitable+" then 1 else 0 end) as suitable,"+
                "sum(case when "+opportunity+" then 1 else 0 end) as opportunity"+from+group;
        }
        String op=q.path("operation").asText();
        if(Arrays.asList("count","sum","avg").contains(op)) {
            String expr="count".equals(op)?"count("+m+")":op+"("+m+")";
            return "select "+select+"count(*) as n,"+expr+" as `value`"+from+group;
        }
        if(!Arrays.asList("median","percentile").contains(op)||!dims.isEmpty())throw new ServiceException("分位数暂只支持总体，不能静默忽略维度");
        BigDecimal p="median".equals(op)?new BigDecimal("0.5"):new BigDecimal(decimal(q.path("percentile"))).divide(new BigDecimal("100"));
        if(p.signum()<0||p.compareTo(BigDecimal.ONE)>0)throw new ServiceException("百分位非法");
        String rank="(1+(n-1)*"+p.toPlainString()+")";
        // 连续百分位线性插值；偶数中位数不是取任一中间客户。
        return "select max(n) as n, max(case when r=floor("+rank+") then v end)*(1-(max("+rank+")-floor(max("+rank+"))))"+
            "+max(case when r=ceil("+rank+") then v end)*(max("+rank+")-floor(max("+rank+"))) as `value` from "+
            "(select "+m+" as v,row_number() over(order by "+m+") as r,count(*) over() as n"+from+" where "+m+" is not null) _r";
    }
    private static String score(JsonNode q,String base,Set<String> available) {
        List<String> exclusionNames=new ArrayList<>();for(JsonNode e:q.path("exclusions"))exclusionNames.add(e.asText());
        if(!exclusionNames.containsAll(Arrays.asList("risk_mismatch","do_not_disturb","recent_contact","no_channel"))||!q.path("assumption").asBoolean()||q.path("reason_top_k").asInt()!=2)
            throw new ServiceException("评分必须声明假设且保留全部硬排除");
        StringBuilder excluded=new StringBuilder("case ");
        for(String name:exclusionNames) {
            if(!available.contains(name))throw new ServiceException("评分硬排除未绑定");
            excluded.append("when ").append(id(name)).append(" is null or ").append(id(name)).append("<>0 then '").append(name).append("' ");
        }
        List<String> metrics=new ArrayList<>(),computed=new ArrayList<>();
        for(JsonNode c:q.path("components")) {
            String name=c.path("metric").asText();if(!available.contains(name)||metrics.contains(name))throw new ServiceException("评分分项未绑定或重复");
            metrics.add(name);StringBuilder b=new StringBuilder("case ");BigDecimal prior=null;int idx=0,size=c.path("bands").size();
            if(size<1||size>12)throw new ServiceException("评分分档数量非法");
            BigDecimal weight=new BigDecimal(decimal(c.path("weight")));
            if(weight.signum()<=0||weight.compareTo(new BigDecimal("100"))>0)throw new ServiceException("评分权重非法");
            for(JsonNode band:c.path("bands")) {
                BigDecimal points=new BigDecimal(decimal(band.path("points")));
                if(points.abs().compareTo(new BigDecimal("100"))>0)throw new ServiceException("评分点数非法");
                String amount=points.multiply(weight).toPlainString();
                if(++idx==size) {if(!band.path("upper").isNull())throw new ServiceException("评分末档须无上限");b.append("else ").append(amount);}
                else {BigDecimal cut=new BigDecimal(decimal(band.path("upper")));if(prior!=null&&cut.compareTo(prior)<=0)throw new ServiceException("评分分档须递增");prior=cut;b.append("when ").append(id(name)).append("<").append(cut.toPlainString()).append(" then ").append(amount).append(" ");}
            }
            computed.add(b+" end as "+id("c_"+name));
            // 分项缺失也先排除，不能将未知值套入最高分档。
            excluded.append("when ").append(id(name)).append(" is null then 'missing_score' ");
        }
        if(metrics.size()<2||metrics.size()>8||!available.contains("channel"))throw new ServiceException("评分分项或渠道不足");
        excluded.append("when `channel` is null then 'no_channel' else null end as excluded");
        String scored="select *,"+excluded+","+String.join(",",computed)+" from ("+base+") _s";
        List<String> contributions=new ArrayList<>();for(String m:metrics)contributions.add(id("c_"+m));
        if(q.path("tier_cuts").size()!=2)throw new ServiceException("评分必须分三档");
        BigDecimal low=new BigDecimal(decimal(q.path("tier_cuts").get(0))), high=new BigDecimal(decimal(q.path("tier_cuts").get(1)));
        if(low.compareTo(high)>=0)throw new ServiceException("评分档阈值颠倒");
        String tier="case when excluded is not null then concat('excluded:',excluded) when "+String.join("+",contributions)+"<"+low+" then 'low' when "+String.join("+",contributions)+"<"+high+" then 'medium' else 'high' end";
        // 相等贡献按声明顺序稳定选择，负贡献不是主因；不足正贡献则标注unknown。
        List<String> reasons=new ArrayList<>();
        for(int k=0;k<2;k++) {
            StringBuilder code=new StringBuilder("case ");
            for(int i=0;i<metrics.size();i++) {
                List<String> better=new ArrayList<>();for(int j=0;j<metrics.size();j++)if(i!=j)better.add("case when "+contributions.get(j)+(j<i?">=":">")+contributions.get(i)+" then 1 else 0 end");
                code.append("when ").append(contributions.get(i)).append(">0 and (").append(String.join("+",better)).append(")=").append(k).append(" then '").append(metrics.get(i)).append("' ");
            }
            reasons.add(code+"else 'unknown' end");
        }
        String grouped="select "+tier+" as d0,case when excluded is null then `channel` else 'none' end as d1,"+
            "case when excluded is null then "+reasons.get(0)+" else 'unknown' end as reason0,case when excluded is null then "+reasons.get(1)+" else 'unknown' end as reason1,"+String.join(",",contributions)+" from ("+scored+") _c";
        List<String> averages=new ArrayList<>();for(String m:metrics)averages.add("avg("+id("c_"+m)+") as "+id("c_"+m));
        return "select d0,d1,reason0,reason1,count(*) as n,"+String.join(",",averages)+" from ("+grouped+") _g group by d0,d1,reason0,reason1 order by d0,d1,reason0,reason1";
    }
}
