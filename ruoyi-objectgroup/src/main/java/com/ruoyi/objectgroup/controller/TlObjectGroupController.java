package com.ruoyi.objectgroup.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.objectgroup.domain.RulePayload;
import com.ruoyi.objectgroup.domain.TlObjectGroup;
import com.ruoyi.objectgroup.domain.TlTagCodeValue;
import com.ruoyi.objectgroup.domain.vo.CodeValueSyncVO;
import com.ruoyi.objectgroup.service.ICodeValueService;
import com.ruoyi.objectgroup.service.IDimensionCodeOptionService;
import com.ruoyi.objectgroup.service.ITlObjectGroupService;

/**
 * 对象群管理 Controller
 *
 * @author ruoyi
 */
@RestController
@RequestMapping("/objectgroup/group")
public class TlObjectGroupController extends BaseController {

    @Autowired
    private ITlObjectGroupService groupService;
    @Autowired
    private ICodeValueService codeValueService;
    @Autowired
    private IDimensionCodeOptionService dimensionCodeOptionService;

    /** 对象群分页列表 */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:list')")
    @GetMapping("/list")
    public TableDataInfo list(TlObjectGroup query) {
        startPage();
        return getDataTable(groupService.selectObjectGroupList(query));
    }

    /** 对象群详情 */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:query')")
    @GetMapping("/{groupId}")
    public AjaxResult getInfo(@PathVariable Long groupId) {
        return success(groupService.selectObjectGroupById(groupId));
    }

    /** 新建对象群 */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:add')")
    @PostMapping
    public AjaxResult add(@RequestBody TlObjectGroup group) {
        return toAjax(groupService.insertObjectGroup(group));
    }

    /** 修改对象群 */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:edit')")
    @PutMapping
    public AjaxResult edit(@RequestBody TlObjectGroup group) {
        return toAjax(groupService.updateObjectGroup(group));
    }

    /** 删除对象群 */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:remove')")
    @DeleteMapping("/{groupIds}")
    public AjaxResult remove(@PathVariable Long[] groupIds) {
        return toAjax(groupService.deleteObjectGroupByIds(groupIds));
    }

    /** 生成规则 SQL（预览弹窗） */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:run')")
    @PostMapping("/sql")
    public AjaxResult sql(@RequestBody RuleRequest request) {
        return AjaxResult.success("操作成功", groupService.buildRuleSql(request.getLibraryId(), request.getRule()));
    }

    /** 运行规则（COUNT），有 groupId 时回写用户数 */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:run')")
    @PostMapping("/run")
    public AjaxResult run(@RequestBody RuleRequest request) {
        long count = groupService.runRule(request.getGroupId(), request.getLibraryId(), request.getRule());
        return success(count);
    }

    /** 样例预览（客户号 + 预览列 LIMIT 100） */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:preview')")
    @PostMapping("/preview")
    public AjaxResult preview(@RequestBody RuleRequest request) {
        return success(groupService.previewRule(request.getGroupId(), request.getLibraryId(), request.getRule()));
    }

    /** 导入关联文件解析（txt/csv 单列 ≤5M ≤5万条） */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:import')")
    @PostMapping("/import/parse")
    public AjaxResult importParse(@RequestPart("file") MultipartFile file,
                                  @RequestParam(value = "fieldName", required = false) String fieldName) {
        return success(groupService.parseImportFile(file, fieldName));
    }

    // ==================== 码值 ====================

    /** 码值选项（标签库默认码表实时查询，只读） */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:query')")
    @GetMapping("/code-options")
    public AjaxResult codeOptions(@RequestParam Long libraryId, @RequestParam String fieldName) {
        return success(dimensionCodeOptionService.listCodeOptions(libraryId, fieldName));
    }

    /** 码值分页/查询 */
    @PreAuthorize("@ss.hasPermi('objectgroup:group:list')")
    @GetMapping("/codevalue/list")
    public TableDataInfo codeValueList(TlTagCodeValue query) {
        startPage();
        return getDataTable(codeValueService.selectCodeValueList(query));
    }

    /** 码值同步（宽表 DISTINCT） */
    @PreAuthorize("@ss.hasPermi('objectgroup:codevalue:sync')")
    @PostMapping("/codevalue/sync")
    public AjaxResult codeValueSync(@RequestBody TlTagCodeValue query) {
        CodeValueSyncVO result = codeValueService.syncCodeValue(query.getLibraryId(), query.getFieldName());
        if (result.isTruncated()) {
            return success("宽表码值超出同步上限，已同步前 " + result.getSyncedCount()
                    + " 个（未清理其余码值）");
        }
        return success("同步 " + result.getSyncedCount() + " 个码值，并清理宽表中已不存在的码值");
    }

    /** 码值新增 */
    @PreAuthorize("@ss.hasPermi('objectgroup:codevalue:edit')")
    @PostMapping("/codevalue")
    public AjaxResult codeValueAdd(@RequestBody TlTagCodeValue codeValue) {
        return toAjax(codeValueService.insertCodeValue(codeValue));
    }

    /** 码值修改 */
    @PreAuthorize("@ss.hasPermi('objectgroup:codevalue:edit')")
    @PutMapping("/codevalue")
    public AjaxResult codeValueEdit(@RequestBody TlTagCodeValue codeValue) {
        return toAjax(codeValueService.updateCodeValue(codeValue));
    }

    /** 码值删除 */
    @PreAuthorize("@ss.hasPermi('objectgroup:codevalue:edit')")
    @DeleteMapping("/codevalue/{valueIds}")
    public AjaxResult codeValueRemove(@PathVariable Long[] valueIds) {
        return toAjax(codeValueService.deleteCodeValueByIds(valueIds));
    }

    /** 规则请求体（运行/预览/SQL 生成共用） */
    public static class RuleRequest {
        private Long groupId;
        private Long libraryId;
        private RulePayload rule;

        public Long getGroupId() { return groupId; }
        public void setGroupId(Long groupId) { this.groupId = groupId; }
        public Long getLibraryId() { return libraryId; }
        public void setLibraryId(Long libraryId) { this.libraryId = libraryId; }
        public RulePayload getRule() { return rule; }
        public void setRule(RulePayload rule) { this.rule = rule; }
    }
}
