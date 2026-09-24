package com.ruoyi.taglibrary.domain.agent;

import java.util.*;

/** 只用于展示与执行门禁；编译器继续读取原 AudiencePlan Map 契约。 */
public class TsAgentOutcome {
    private String outcome;
    private List<Map<String,Object>> gaps = new ArrayList<>();
    private List<Map<String,Object>> questions = new ArrayList<>();
    private Map<String,Object> stats = new LinkedHashMap<>();
    public String getOutcome() { return outcome; }
    public void setOutcome(String value) { outcome=value; }
    public List<Map<String,Object>> getGaps() { return gaps; }
    public void setGaps(List<Map<String,Object>> value) { gaps=value; }
    public List<Map<String,Object>> getQuestions() { return questions; }
    public void setQuestions(List<Map<String,Object>> value) { questions=value; }
    public Map<String,Object> getStats() { return stats; }
    public void setStats(Map<String,Object> value) { stats=value; }
}
