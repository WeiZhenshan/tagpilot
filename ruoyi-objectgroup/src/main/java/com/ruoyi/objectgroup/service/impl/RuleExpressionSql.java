package com.ruoyi.objectgroup.service.impl;

import java.math.BigDecimal;
import java.util.*;
import java.util.function.Function;
import com.fasterxml.jackson.databind.JsonNode;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.objectgroup.domain.RulePayload;

/** 只接收服务端重建后的 AST。所有标识符重新引用，所有值按类型验证。 */
public final class RuleExpressionSql {
    private RuleExpressionSql() { }
    public static String identifier(String value) {
        if (value == null || !value.matches("[A-Za-z_][A-Za-z0-9_]{0,127}"))
            throw new ServiceException("计算引用的标识符非法");
        return "`" + value + "`";
    }
    public static String number(String value) {
        try {
            if (value == null || value.length() > 80) throw new NumberFormatException();
            BigDecimal n = new BigDecimal(value);
            if (n.abs().compareTo(new BigDecimal("1e30")) > 0 || Math.abs(n.scale()) > 30) throw new NumberFormatException();
            return n.stripTrailingZeros().toPlainString();
        } catch (NumberFormatException e) { throw new ServiceException("计算数值非法"); }
    }
    public static String render(JsonNode node, Function<String,String> columns, String outerKey) {
        return render(node, columns, outerKey, 0, new int[]{0});
    }
    private static String render(JsonNode n, Function<String,String> columns, String outerKey, int depth, int[] count) {
        if (n == null || !n.isObject() || depth > 8 || ++count[0] > 64) throw new ServiceException("计算表达式格式或复杂度非法");
        String kind = n.path("kind").asText();
        if ("TAG".equals(kind)) {
            String col = columns.apply(n.path("field_name").asText());
            String scale = number(n.path("unit_scale").asText("1"));
            return "(" + identifier(col) + " * " + scale + ")";
        }
        if ("CONST".equals(kind)) return number(n.path("value").asText());
        if ("AGGREGATE".equals(kind)) return aggregate(n, outerKey);
        JsonNode args = n.path("args");
        if (!args.isArray() || ("COUNT_POSITIVE".equals(kind) ? args.size()<1 || args.size()>12 : args.size()!=2))
            throw new ServiceException("计算参数数量非法");
        List<String> rendered = new ArrayList<>();
        for (JsonNode a : args) rendered.add(render(a, columns, outerKey, depth+1, count));
        if ("COUNT_POSITIVE".equals(kind)) {
            List<String> missing = new ArrayList<>(), positive = new ArrayList<>();
            for (String a : rendered) { missing.add(a+" is null"); positive.add("case when "+a+" > 0 then 1 else 0 end"); }
            return "(case when " + String.join(" or ", missing) + " then null else " + String.join(" + ", positive) + " end)";
        }
        String left=rendered.get(0), right=rendered.get(1);
        if ("DIV".equals(kind)) return "(case when " + right + " > 0 then " + left + " / nullif(" + right + ",0) else null end)";
        String op="ADD".equals(kind)?"+":"SUB".equals(kind)?"-":"MUL".equals(kind)?"*":null;
        if (op==null) throw new ServiceException("计算算子不受支持");
        return "("+left+" "+op+" "+right+")";
    }
    public static String predicate(RulePayload.Condition c, Function<String,String> columns, String outerKey) {
        if (c.isScopeAll()) return "(1=1)";
        String left=render(c.getExpression(),columns,outerKey), op=c.getOperator();
        if ("is_null".equals(op)) return "("+left+" is null)";
        if ("is_not_null".equals(op)) return "("+left+" is not null)";
        if ("between".equals(op)) {
            if(c.getCompareExpression()!=null || c.getValues()==null || c.getValues().size()!=2) throw new ServiceException("计算区间需两个端点");
            String low=number(c.getValues().get(0)), high=number(c.getValues().get(1));
            if(new BigDecimal(low).compareTo(new BigDecimal(high))>0) throw new ServiceException("计算区间下限大于上限");
            return "("+left+" >= "+low+" and "+left+" <= "+high+")";
        }
        if(!Arrays.asList("=","!=",">",">=","<","<=").contains(op)) throw new ServiceException("计算比较符非法");
        String right;
        if(c.getCompareExpression()!=null) right=render(c.getCompareExpression(),columns,outerKey);
        else {
            if(c.getValues()==null || c.getValues().size()!=1) throw new ServiceException("计算比较值须为一个");
            right=number(c.getValues().get(0));
        }
        return "("+left+" "+op+" "+right+")";
    }
    private static String aggregate(JsonNode n, String outerKey) {
        String table=identifier(n.path("table_name").asText()), key=identifier(n.path("customer_column").asText());
        String function=n.path("aggregation").asText(), value=identifier(n.path("value_column").asText());
        String aggregate;
        if("COUNT_DISTINCT".equals(function)) aggregate="count(distinct _ae."+value+")";
        else if(Arrays.asList("SUM","MAX","MIN","AVG","COUNT").contains(function)) aggregate=function.toLowerCase()+"(_ae."+value+")";
        else throw new ServiceException("聚合方式未登记");
        List<String> filters=new ArrayList<>();filters.add("_ae."+key+" = "+outerKey);
        for(JsonNode filter:n.path("filters")) {
            String col="_ae."+identifier(filter.path("column").asText()), op=filter.path("operator").asText();
            if(Arrays.asList("is_null","is_not_null").contains(op)) {filters.add(col+("is_null".equals(op)?" is null":" is not null"));continue;}
            if(!Arrays.asList("=","!=",">",">=","<","<=").contains(op)) throw new ServiceException("聚合过滤符非法");
            String val=filter.path("value").asText();
            if(val.length()>200) throw new ServiceException("聚合过滤值过长");
            String literal="NUMBER".equals(filter.path("type").asText())?number(val):"'"+val.replace("\\","\\\\").replace("'","''")+"'";
            filters.add(col+" "+op+" "+literal);
        }
        aggregate="case when count(*) <> count(_ae."+value+") then null else "+aggregate+" end";
        String sql="(select "+aggregate+" from "+table+" _ae where "+String.join(" and ",filters)+")";
        // 零事件需有完整覆盖声明；SUM 不能把存在但数值缺失的事件转为零。
        if("ZERO_WHEN_NO_ROWS".equals(n.path("empty_policy").asText()) && "SUM".equals(function)) {
            String count="(select count(*) from "+table+" _ae where "+String.join(" and ",filters)+")";
            return "(case when "+count+" = 0 then 0 else "+sql+" end)";
        }
        return sql;
    }
}
