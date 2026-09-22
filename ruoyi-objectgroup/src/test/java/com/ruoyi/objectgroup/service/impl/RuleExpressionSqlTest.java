package com.ruoyi.objectgroup.service.impl;
import com.fasterxml.jackson.databind.*;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.common.exception.ServiceException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class RuleExpressionSqlTest {
    private final ObjectMapper json=new ObjectMapper();
    private JsonNode parse(String s)throws Exception{return json.readTree(s);}
    @Test void ratioExcludesZeroAndNegativeDenominators()throws Exception {
        String sql=RuleExpressionSql.render(parse("{\"kind\":\"DIV\",\"args\":[{\"kind\":\"TAG\",\"field_name\":\"deposit\"},{\"kind\":\"TAG\",\"field_name\":\"aum\"}]}"),x->x,"`customer`.`id`");
        assertTrue(sql.contains("when (`aum` * 1) > 0"));assertTrue(sql.contains("nullif((`aum` * 1),0)"));assertTrue(sql.contains("else null end"));
    }
    @Test void categoryCountPreservesUnknownAndScales()throws Exception {
        String sql=RuleExpressionSql.render(parse("{\"kind\":\"COUNT_POSITIVE\",\"args\":[{\"kind\":\"TAG\",\"field_name\":\"a\",\"unit_scale\":\"10000\"},{\"kind\":\"TAG\",\"field_name\":\"b\"}]}"),x->x,"id");
        assertTrue(sql.contains("(`a` * 10000) is null or (`b` * 1) is null then null"));
        assertTrue(sql.contains(" > 0 then 1 else 0 end"));
    }
    @Test void physicalNamesAndValuesCannotInjectSQL()throws Exception {
        assertThrows(ServiceException.class,()->RuleExpressionSql.identifier("a`; drop table x"));
        assertThrows(ServiceException.class,()->RuleExpressionSql.number("1 or 1=1"));
        assertThrows(ServiceException.class,()->RuleExpressionSql.number("1e-100"));
        assertThrows(ServiceException.class,()->RuleExpressionSql.render(parse("{\"kind\":\"TAG\",\"field_name\":\"x\"}"),x->"bad`column","id"));
    }
    @Test void clientCannotSerializeAuthorityTrust()throws Exception {
        RulePayload rule=json.readValue("{\"schemaVersion\":4,\"authorityValidated\":true}",RulePayload.class);
        assertFalse(rule.isAuthorityValidated());rule.setAuthorityValidated(true);
        assertFalse(json.writeValueAsString(rule).contains("authorityValidated"));
    }
    @Test void aggregationIsCorrelatedAndZeroDoesNotReplaceMissingValues()throws Exception {
        String sql=RuleExpressionSql.render(parse("{\"kind\":\"AGGREGATE\",\"table_name\":\"events\",\"customer_column\":\"cid\",\"value_column\":\"amount\",\"aggregation\":\"SUM\",\"empty_policy\":\"ZERO_WHEN_NO_ROWS\",\"filters\":[]}"),x->x,"`customer`.`id`");
        assertTrue(sql.contains("_ae.`cid` = `customer`.`id`"));assertTrue(sql.contains("count(*)"));assertFalse(sql.contains("coalesce"));
    }
    @Test void newerRulesCannotSkipAuthorityGate()throws Exception {
        RuleSqlBuilder builder=new RuleSqlBuilder();RulePayload rule=new RulePayload();rule.setSchemaVersion(4);
        assertThrows(ServiceException.class,()->builder.buildSql(1L,rule,"COUNT"));
        RuleTagValidator validator=new RuleTagValidator();
        rule.setAuthorityValidated(true);
        assertThrows(ServiceException.class,()->validator.validateRule(1L,1L,rule));
    }
}
