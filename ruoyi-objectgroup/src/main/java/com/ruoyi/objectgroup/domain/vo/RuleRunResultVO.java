package com.ruoyi.objectgroup.domain.vo;

/**
 * 规则运行结果：count 兼容原返回语义，warning 携带版本漂移等提示信息
 */
public class RuleRunResultVO {

    private long count;
    private String warning;

    public RuleRunResultVO() {
    }

    public RuleRunResultVO(long count, String warning) {
        this.count = count;
        this.warning = warning;
    }

    public long getCount() { return count; }
    public void setCount(long count) { this.count = count; }
    public String getWarning() { return warning; }
    public void setWarning(String warning) { this.warning = warning; }
}
