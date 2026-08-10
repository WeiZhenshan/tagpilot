package com.ruoyi.objectgroup.domain;

import com.ruoyi.common.core.domain.BaseEntity;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;

/**
 * 对象群对象 tl_object_group
 *
 * @author ruoyi
 */
public class TlObjectGroup extends BaseEntity {
    private static final long serialVersionUID = 1L;

    /** 对象群ID */
    private Long groupId;

    /** 对象群名称 */
    private String groupName;

    /** 对象群描述 */
    private String groupDesc;

    /** 关联标签库ID */
    private Long libraryId;

    /** 关联标签库名称（列表展示） */
    private String libraryName;

    /** 规则JSON */
    private String ruleJson;

    /** 最近生成的查询SQL */
    private String groupSql;

    /** 用户数 */
    private Long userCount;

    /** 删除标志（0存在 2删除） */
    private String delFlag;

    /** 使用标签（列表展示，rule_json 解析） */
    private String tagNames;

    public Long getGroupId() { return groupId; }
    public void setGroupId(Long groupId) { this.groupId = groupId; }
    public String getGroupName() { return groupName; }
    public void setGroupName(String groupName) { this.groupName = groupName; }
    public String getGroupDesc() { return groupDesc; }
    public void setGroupDesc(String groupDesc) { this.groupDesc = groupDesc; }
    public Long getLibraryId() { return libraryId; }
    public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
    public String getLibraryName() { return libraryName; }
    public void setLibraryName(String libraryName) { this.libraryName = libraryName; }
    public String getRuleJson() { return ruleJson; }
    public void setRuleJson(String ruleJson) { this.ruleJson = ruleJson; }
    public String getGroupSql() { return groupSql; }
    public void setGroupSql(String groupSql) { this.groupSql = groupSql; }
    public Long getUserCount() { return userCount; }
    public void setUserCount(Long userCount) { this.userCount = userCount; }
    public String getDelFlag() { return delFlag; }
    public void setDelFlag(String delFlag) { this.delFlag = delFlag; }
    public String getTagNames() { return tagNames; }
    public void setTagNames(String tagNames) { this.tagNames = tagNames; }

    @Override
    public String toString() {
        return new ToStringBuilder(this, ToStringStyle.MULTI_LINE_STYLE)
            .append("groupId", getGroupId())
            .append("groupName", getGroupName())
            .append("libraryId", getLibraryId())
            .append("userCount", getUserCount())
            .toString();
    }
}
