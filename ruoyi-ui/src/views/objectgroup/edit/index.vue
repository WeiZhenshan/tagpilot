<template>
  <div class="rule-editor">
    <!-- 左侧：标签库 + 标签树 -->
    <div class="left-panel">
      <el-select v-model="libraryId" placeholder="请选择标签库" size="small" style="width: 100%; margin-bottom: 8px;" @change="handleLibraryChange">
        <el-option v-for="lib in libraryOptions" :key="lib.libraryId" :label="lib.libraryName" :value="lib.libraryId" />
      </el-select>
      <el-input v-model="searchText" placeholder="搜索标签" clearable size="small" prefix-icon="el-icon-search" style="margin-bottom: 8px;" />
      <el-tree ref="tree" :data="treeData" node-key="id" :props="treeProps" highlight-current v-loading="treeLoading"
        default-expand-all :filter-node-method="filterNode">
        <span class="tree-node" slot-scope="{ data }">
          <draggable v-if="isTagDraggable(data)" :list="[data]" :group="dragGroup" :clone="cloneCondition" :sort="false" class="tree-drag">
            <span class="node-content">
              <span v-if="data.tagType" class="tag-dot" :style="{background: tagTypeColor(data.tagType)}"></span>
              <span>{{ data.label }}</span>
              <span v-if="data.isObjectKey === '1'" class="obj-key-badge">客户号</span>
            </span>
          </draggable>
          <span v-else class="node-content" :class="{ 'node-disabled': isTagNode(data) }">
            <span v-if="isTagNode(data) && data.tagType" class="tag-dot" :style="{background: tagTypeColor(data.tagType)}"></span>
            <span>{{ data.label }}</span>
            <el-tooltip v-if="isTagNode(data)" :content="tagDragBlockReason(data)" placement="top">
              <span class="node-status-badge">{{ tagDragBlockReason(data) }}</span>
            </el-tooltip>
            <span v-else-if="data.count !== undefined" class="node-count">[{{ data.count }}]</span>
          </span>
        </span>
      </el-tree>
    </div>

    <!-- 右侧：规则展示区 -->
    <div class="right-panel">
      <!-- 第一部分：工具栏 -->
      <div class="toolbar">
        <el-button size="small" type="primary" icon="el-icon-video-play" @click="handleRun" v-hasPermi="['objectgroup:group:run']">运行</el-button>
        <span class="user-count-label">用户数</span>
        <span class="user-count-num">{{ userCount }}</span>
        <el-button size="small" icon="el-icon-document" @click="handleSqlPreview" v-hasPermi="['objectgroup:group:run']">SQL预览</el-button>
        <el-button size="small" icon="el-icon-delete" @click="handleClear">清空</el-button>
        <el-button size="small" icon="el-icon-view" @click="handleSamplePreview" v-hasPermi="['objectgroup:group:preview']">样例预览</el-button>
        <div class="toolbar-right">
          <el-button size="small" @click="handleBack">返回</el-button>
          <el-button size="small" type="success" icon="el-icon-check" @click="handleSave">保存</el-button>
        </div>
      </div>

      <!-- 预览列区（拖入标签加入样例预览列） -->
      <div class="preview-col-area">
        <span class="area-label">预览列</span>
        <draggable :list="previewColumns" :group="previewGroup" class="preview-col-list" @add="onPreviewColAdd">
          <el-tag v-for="col in previewColumns" :key="col.tagId" closable size="small" class="preview-col-tag" @close="removePreviewCol(col)">{{ col.tagName }}</el-tag>
        </draggable>
        <span v-if="previewColumns.length === 0" class="area-hint">拖入标签，样例预览时展示对应列数据</span>
      </div>

      <!-- 第二部分：规则编辑区 -->
      <div class="rule-area">
        <draggable :list="conditions" group="ruleGroup" class="rule-list" :animation="200" @add="onRuleAdd">
          <div v-for="(cond, index) in conditions" :key="cond.conditionId" class="rule-row"
            :class="{ 'is-active': activeConditionId === cond.conditionId, 'is-invalid': !isConditionValid(cond) }"
            @click="activeConditionId = cond.conditionId">
            <div class="rule-row-header">
              <span class="row-index">{{ index + 1 }}</span>
              <span class="row-connector">
                <el-select v-model="cond.connector" size="mini" :disabled="index === 0" style="width: 70px;">
                  <el-option label="且" value="AND" />
                  <el-option label="或" value="OR" />
                </el-select>
              </span>
              <span class="row-name">{{ cond.tagName }}</span>
              <el-tag size="mini" class="row-type">{{ cond.tagType }}</el-tag>
              <span class="row-parens">
                <span v-if="cond.openParen > 0" class="paren-chip">( ×{{ cond.openParen }}</span>
                <span v-if="cond.closeParen > 0" class="paren-chip">) ×{{ cond.closeParen }}</span>
              </span>
              <el-button type="text" size="mini" icon="el-icon-close" class="row-delete" @click.stop="removeCondition(cond)" />
            </div>
            <div class="rule-row-body">
              <!-- 客户号（主键）特殊控件 -->
              <template v-if="cond.tagType === '客户号'">
                <el-radio-group v-model="cond.matchType" size="small" @change="onMatchTypeChange(cond)">
                  <el-radio-button label="exact">精准匹配</el-radio-button>
                  <el-radio-button label="like">模糊匹配</el-radio-button>
                  <el-radio-button label="import">导入关联</el-radio-button>
                </el-radio-group>
                <el-input v-if="cond.matchType !== 'import'" v-model="cond.values[0]" size="small" placeholder="请输入客户号" style="width: 180px;" />
                <span v-if="cond.matchType === 'import'" class="import-area">
                  <el-upload :action="uploadUrl" :show-file-list="false" accept=".txt,.csv"
                    :before-upload="beforeImport" :on-success="(res, file) => onImportSuccess(res, file, cond)" name="file"
                    :data="{ fieldName: cond.fieldName }" v-hasPermi="['objectgroup:group:import']">
                    <el-button size="small" icon="el-icon-upload2">上传文件</el-button>
                  </el-upload>
                  <span v-if="cond.importedCount" class="import-hint">已导入 {{ cond.importedCount }} 条</span>
                  <span class="import-note">txt/csv 格式，最大 5M，单列客户号</span>
                </span>
              </template>
              <!-- 布尔型 -->
              <el-radio-group v-else-if="cond.tagType === '布尔型'" v-model="cond.values[0]" size="small">
                <el-radio-button v-for="opt in codeOptions(cond)" :key="opt.code" :label="opt.code">{{ opt.codeDefinition || opt.code }}</el-radio-button>
              </el-radio-group>
              <!-- 选项型 -->
              <el-select v-else-if="cond.tagType === '选项型'" v-model="cond.values" multiple size="small" placeholder="请选择选项" style="width: 280px;">
                <el-option v-for="opt in codeOptions(cond)" :key="opt.code" :label="opt.codeDefinition || opt.code" :value="opt.code" />
              </el-select>
              <!-- 数值型 -->
              <template v-else-if="cond.tagType === '数值型'">
                <span class="range-label">最小</span>
                <el-input-number v-model="cond.values[0]" size="small" :controls="false" style="width: 110px;" placeholder="可留空" />
                <span class="range-label">最大</span>
                <el-input-number v-model="cond.values[1]" size="small" :controls="false" style="width: 110px;" placeholder="可留空" />
              </template>
              <!-- 文本型 -->
              <template v-else-if="cond.tagType === '文本型'">
                <el-select v-model="cond.operator" size="small" style="width: 90px;">
                  <el-option label="精准匹配" value="eq" />
                  <el-option label="模糊匹配" value="like" />
                </el-select>
                <el-input v-model="cond.values[0]" size="small" placeholder="请输入文本" style="width: 160px;" />
              </template>
              <!-- 日期型 -->
              <el-date-picker v-else-if="cond.tagType === '日期型'" v-model="cond.dateRange" type="daterange"
                size="small" value-format="yyyy-MM-dd" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 260px;"
                @change="val => onDateRangeChange(cond, val)" />
              <!-- 已保存码值在当前选项中不存在时给出失效警告（不自动删除，values 原样保留） -->
              <el-tooltip v-if="invalidCodes(cond).length > 0" :content="'已失效码值：' + invalidCodes(cond).join('、')" placement="top">
                <el-tag type="warning" size="mini">已保存码值已失效</el-tag>
              </el-tooltip>
            </div>
          </div>
        </draggable>
        <div v-if="conditions.length === 0" class="rule-empty">
          <el-icon class="empty-icon"><el-icon-drag></el-icon-drag></el-icon>
          <p>从左侧拖入标签构建规则</p>
        </div>
      </div>

      <!-- 第三部分：逻辑关系区 -->
      <div class="logic-area">
        <span class="area-label">逻辑关系</span>
        <el-button size="mini" icon="el-icon-arrow-left" @click="addParen('open')">左括号</el-button>
        <el-button size="mini" icon="el-icon-arrow-right" @click="addParen('close')">右括号</el-button>
        <el-button size="mini" icon="el-icon-document-copy" @click="handleFormat">格式化</el-button>
        <el-button size="mini" icon="el-icon-delete" @click="handleClear">清空</el-button>
        <span v-if="activeConditionId" class="logic-hint">已选中第 {{ activeIndex + 1 }} 行：{{ activeCondName }}</span>
        <span v-else class="logic-hint">点击规则行后设置括号</span>
      </div>

      <!-- 样例预览面板（顶部下拉，覆盖右侧全部区域） -->
      <transition name="sample-slide">
        <div v-show="sampleVisible" class="sample-panel">
          <div class="sample-panel-header">
            <span class="sample-panel-title">样例预览（前 100 行）</span>
            <el-radio-group v-model="sampleDisplay" size="mini" style="margin-right: 10px;">
              <el-radio-button :label="true">中文显示</el-radio-button>
              <el-radio-button :label="false">原始编码</el-radio-button>
            </el-radio-group>
            <el-button size="mini" icon="el-icon-top" title="上卷" @click="sampleVisible = false" />
          </div>
          <div v-if="sampleNotes.length > 0" class="sample-notes">
            <div v-for="(note, i) in sampleNotes" :key="i" class="sample-note-item">
              <i class="el-icon-warning-outline"></i>
              <span>{{ note.column }}：{{ note.message }}</span>
            </div>
          </div>
          <div class="preview-col-area">
            <span class="area-label">预览列</span>
            <draggable :list="previewColumns" :group="previewGroup" class="preview-col-list" @add="onPreviewColAdd">
              <el-tag v-for="col in previewColumns" :key="col.tagId" closable size="small" class="preview-col-tag" @close="removePreviewCol(col)">{{ col.tagName }}</el-tag>
            </draggable>
            <span v-if="previewColumns.length === 0" class="area-hint">从左侧标签树拖入标签，相应列将加入预览</span>
          </div>
          <div class="sample-panel-body" v-loading="sampleLoading">
            <el-table :data="sampleRows" size="small" border>
              <el-table-column v-for="col in sampleColumns" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
            </el-table>
          </div>
        </div>
      </transition>
    </div>

    <!-- SQL 预览弹窗 -->
    <el-dialog title="SQL 预览" :visible.sync="sqlVisible" width="680px" append-to-body>
      <pre class="sql-block">{{ sqlText }}</pre>
      <div slot="footer">
        <el-button size="small" icon="el-icon-document-copy" @click="copySql">复制</el-button>
        <el-button size="small" @click="sqlVisible = false">关闭</el-button>
      </div>
    </el-dialog>

    <!-- 格式化弹窗 -->
    <el-dialog title="规则格式化" :visible.sync="formatVisible" width="680px" append-to-body>
      <pre class="sql-block">{{ formatText }}</pre>
      <div slot="footer">
        <el-button size="small" icon="el-icon-document-copy" @click="copyFormat">复制</el-button>
        <el-button size="small" @click="formatVisible = false">关闭</el-button>
      </div>
    </el-dialog>

    <!-- 保存对象群弹窗 -->
    <el-dialog title="保存对象群" :visible.sync="saveVisible" width="480px" append-to-body>
      <el-form ref="saveForm" :model="saveForm" :rules="saveRules" label-width="90px">
        <el-form-item label="对象群名称" prop="groupName">
          <el-input v-model="saveForm.groupName" placeholder="请输入对象群名称" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="对象群描述" prop="groupDesc">
          <el-input v-model="saveForm.groupDesc" type="textarea" :rows="3" placeholder="请输入对象群描述" maxlength="200" show-word-limit />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" type="primary" icon="el-icon-check" :loading="saveLoading" @click="confirmSave">保存</el-button>
        <el-button size="small" @click="saveVisible = false">取消</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import draggable from 'vuedraggable'
import { listLibrary } from '@/api/taglibrary/library'
import { tagTree } from '@/api/taglibrary/tag'
import { getGroup, addGroup, updateGroup, runGroup, previewSql, previewGroup, getCodeOptions } from '@/api/objectgroup/group'

let uuidSeq = 0

export default {
  name: 'ObjectGroupEdit',
  components: { draggable },
  data() {
    return {
      // 表单
      groupId: undefined,
      groupName: '',
      groupDesc: '',
      // 标签库 + 树
      libraryOptions: [],
      libraryId: undefined,
      searchText: '',
      treeData: [],
      treeLoading: false,
      treeProps: { label: 'label', children: 'children' },
      // 规则
      conditions: [],
      previewColumns: [],
      activeConditionId: undefined,
      objectKeyField: undefined,
      userCount: 0,
      // 码值缓存 { 'libraryId:fieldName': [options] }，键含标签库避免切库串数据
      codeCache: {},
      // 码值请求序号 { 'libraryId:fieldName': n }，丢弃过期响应
      codeReqSeq: {},
      // 弹窗
      sqlVisible: false,
      sqlText: '',
      sampleVisible: false,
      sampleLoading: false,
      sampleColumns: [],
      sampleRawRows: [],
      sampleCnRows: [],
      // true 展示中文副本 displayRows，false 展示原始编码 rows
      sampleDisplay: true,
      sampleNotes: [],
      formatVisible: false,
      formatText: '',
      // 保存弹窗
      saveVisible: false,
      saveLoading: false,
      lastRouteKey: '',
      saveForm: {
        groupName: '',
        groupDesc: ''
      },
      saveRules: {
        groupName: [{ required: true, message: '对象群名称不能为空', trigger: 'blur' }]
      },
      uploadUrl: process.env.VUE_APP_BASE_API + '/objectgroup/group/import/parse'
    }
  },
  computed: {
    dragGroup() {
      return { name: 'ruleGroup', pull: 'clone', put: false }
    },
    previewGroup() {
      // 允许从标签树（ruleGroup，clone 语义）拖入；预览列本身不向外拖出
      return { name: 'previewGroup', pull: false, put: ['ruleGroup'] }
    },
    activeIndex() {
      return this.conditions.findIndex(c => c.conditionId === this.activeConditionId)
    },
    activeCondName() {
      const c = this.conditions[this.activeIndex]
      return c ? c.tagName : ''
    },
    sampleRows() {
      return this.sampleDisplay ? this.sampleCnRows : this.sampleRawRows
    }
  },
  watch: {
    searchText(val) {
      this.$refs.tree.filter(val)
    }
  },
  created() {
    this.init()
  },
  activated() {
    // 组件被 keep-alive 缓存时 created 不会重复执行，路由变化需重新初始化
    if (this.$route.fullPath !== this.lastRouteKey) {
      this.init()
    }
  },
  methods: {
    // ==================== 数据加载 ====================
    init() {
      this.lastRouteKey = this.$route.fullPath
      this.resetState()
      if (this.$route.query.groupId) {
        this.groupId = Number(this.$route.query.groupId)
        this.loadGroup()
      }
      this.loadLibraries()
    },
    resetState() {
      this.groupId = undefined
      this.groupName = ''
      this.groupDesc = ''
      this.conditions = []
      this.previewColumns = []
      this.activeConditionId = undefined
      this.objectKeyField = undefined
      this.userCount = 0
      this.codeCache = {}
      this.codeReqSeq = {}
    },
    loadLibraries() {
      listLibrary({ pageNum: 1, pageSize: 100 }).then(response => {
        this.libraryOptions = response.rows || []
        if (this.libraryOptions.length > 0 && !this.libraryId) {
          this.libraryId = this.libraryOptions[0].libraryId
          this.loadTree()
        }
      })
    },
    loadGroup() {
      getGroup(this.groupId).then(response => {
        const g = response.data
        this.groupName = g.groupName
        this.groupDesc = g.groupDesc
        this.libraryId = g.libraryId
        if (g.ruleJson) {
          const rule = JSON.parse(g.ruleJson)
          this.conditions = rule.conditions || []
          this.previewColumns = rule.previewColumns || []
          this.objectKeyField = rule.objectKeyField
        }
        this.loadTree()
        this.loadCodeValues()
      })
    },
    handleLibraryChange() {
      this.conditions = []
      this.previewColumns = []
      this.userCount = 0
      this.objectKeyField = undefined
      this.codeCache = {}
      this.codeReqSeq = {}
      this.loadTree()
    },
    loadTree() {
      if (!this.libraryId) return
      this.treeLoading = true
      // 对象群编辑需能选到全部状态的标签（含已上线）
      tagTree(this.libraryId, 'all').then(response => {
        this.treeData = response.data || []
        this.treeLoading = false
        // 识别客户号字段（仅已上线且来源可用的标签）
        const walk = nodes => {
          for (const n of nodes || []) {
            if (this.isTagDraggable(n) && n.isObjectKey === '1') {
              this.objectKeyField = n.fieldName
              return
            }
            walk(n.children)
          }
        }
        walk(this.treeData)
      }).catch(() => { this.treeLoading = false })
    },
    loadCodeValues() {
      // 编辑回显时批量加载条件行码值
      this.conditions.forEach(c => {
        if (c.tagType === '选项型' || c.tagType === '布尔型') {
          this.fetchCodeOptions(c)
        }
      })
    },
    /** 码值缓存键：标签库 + 字段别名，切库后互不干扰 */
    codeKey(fieldName) {
      return this.libraryId + ':' + fieldName
    },
    fetchCodeOptions(cond) {
      // 新码值链路：维表合并后的码值选项（无关联维表时返回空数组）
      const libraryId = this.libraryId
      const key = libraryId + ':' + cond.fieldName
      const seq = (this.codeReqSeq[key] || 0) + 1
      this.$set(this.codeReqSeq, key, seq)
      getCodeOptions({ libraryId: libraryId, fieldName: cond.fieldName }).then(response => {
        // 切库或同字段有新请求时丢弃过期响应
        if (libraryId !== this.libraryId || this.codeReqSeq[key] !== seq) return
        this.$set(this.codeCache, key, response.data || [])
      }).catch(() => {})
    },
    codeOptions(cond) {
      const options = this.codeCache[this.codeKey(cond.fieldName)] || []
      // 旧规则兼容：已保存但当前选项中不存在的 code 补伪选项，用快照中文回显并标注失效
      const missing = this.invalidCodes(cond)
      if (missing.length === 0) return options
      return options.concat(missing.map(v => {
        const snapshot = (cond.selectedCodeOptions || []).find(s => String(s.code) === String(v))
        const label = snapshot && snapshot.label ? snapshot.label : String(v)
        return { code: v, codeDefinition: label + '（已失效）' }
      }))
    },
    /** 已保存 values 中不在当前码值选项里的 code（码值未加载完成前不判定） */
    invalidCodes(cond) {
      if (cond.tagType !== '选项型' && cond.tagType !== '布尔型') return []
      const key = this.codeKey(cond.fieldName)
      if (!(key in this.codeCache)) return []
      const options = this.codeCache[key] || []
      return (cond.values || []).filter(v =>
        v !== undefined && v !== null && v !== '' && !options.some(o => String(o.code) === String(v))
      )
    },
    /** 码值中文显示：优先码表定义，回退已选快照，最后原码 */
    codeLabel(cond, code) {
      const options = this.codeCache[this.codeKey(cond.fieldName)] || []
      const opt = options.find(o => String(o.code) === String(code))
      if (opt) return opt.codeDefinition || opt.code
      const snapshot = (cond.selectedCodeOptions || []).find(s => String(s.code) === String(code))
      return snapshot && snapshot.label ? snapshot.label : String(code)
    },
    // ==================== 树 ====================
    isTagNode(data) {
      return data && String(data.id).indexOf('tag-') === 0
    },
    /** 仅已上线且来源可用的标签允许拖入规则区/预览列 */
    isTagDraggable(data) {
      return this.isTagNode(data) && data.status === '2'
        && (!data.sourceStatus || data.sourceStatus === 'AVAILABLE')
    },
    /** 不可拖拽标签的原因说明 */
    tagDragBlockReason(data) {
      if (data.status !== '2') {
        const map = { '0': '未上线', '1': '上线审核中', '3': '已下线' }
        return map[data.status] || '未上线'
      }
      if (data.sourceStatus === 'MISSING') return '来源缺失'
      if (data.sourceStatus === 'CHANGED') return '来源变更待确认'
      return '不可用'
    },
    parseNodeId(id) {
      return String(id).split('-')[1]
    },
    filterNode(value, data) {
      if (!value) return true
      return data.label.indexOf(value) !== -1
    },
    tagTypeColor(tagType) {
      const map = { '选项型': '#67C23A', '布尔型': '#E6A23C', '数值型': '#409EFF', '文本型': '#909399', '日期型': '#F56C6C' }
      return map[tagType] || '#909399'
    },
    // ==================== 拖拽 ====================
    cloneCondition(data) {
      if (!this.isTagNode(data)) return null
      const type = data.isObjectKey === '1' ? '客户号' : data.tagType
      return {
        conditionId: 'c' + (++uuidSeq),
        connector: 'AND',
        openParen: 0,
        closeParen: 0,
        tagId: Number(this.parseNodeId(data.id)),
        fieldName: data.fieldName,
        tagName: data.label,
        tagType: type,
        dataType: data.dataType,
        operator: type === '文本型' ? 'eq' : type === '客户号' ? 'eq' : 'between',
        values: [],
        dateRange: [],
        matchType: 'exact',
        importBatchNo: undefined,
        importedCount: undefined
      }
    },
    onRuleAdd(evt) {
      // 克隆语义下 vuedraggable 已插入到 evt.newIndex；针对实际新增行加载码值选项
      const item = this.conditions[evt.newIndex]
      if (item && (item.tagType === '选项型' || item.tagType === '布尔型')) {
        this.fetchCodeOptions(item)
      }
    },
    // ==================== 规则行操作 ====================
    removeCondition(cond) {
      this.conditions = this.conditions.filter(c => c.conditionId !== cond.conditionId)
      if (this.activeConditionId === cond.conditionId) {
        this.activeConditionId = undefined
      }
    },
    isConditionValid(cond) {
      if (cond.tagType === '客户号') {
        if (cond.matchType === 'import') return !!cond.importedCount
        return !!(cond.values && cond.values[0])
      }
      if (cond.tagType === '选项型') return !!(cond.values && cond.values.length > 0)
      if (cond.tagType === '布尔型') return !!(cond.values && cond.values[0])
      if (cond.tagType === '数值型') return !!((cond.values && cond.values[0]) || (cond.values && cond.values[1]))
      if (cond.tagType === '日期型') return !!(cond.dateRange && cond.dateRange.length === 2)
      return !!(cond.values && cond.values[0])
    },
    onDateRangeChange(cond, val) {
      cond.values = val || []
    },
    onMatchTypeChange(cond) {
      cond.values = []
      if (cond.matchType !== 'import') {
        cond.values = ['']
      }
    },
    beforeImport(file) {
      const sizeOk = file.size / 1024 / 1024 <= 5
      if (!sizeOk) {
        this.$modal.msgError('文件大小不能超过 5M')
        return false
      }
      const name = file.name.toLowerCase()
      if (!name.endsWith('.txt') && !name.endsWith('.csv')) {
        this.$modal.msgError('仅支持 txt/csv 文件')
        return false
      }
      return true
    },
    onImportSuccess(res, file, cond) {
      if (res.code !== 200) {
        this.$modal.msgError(res.msg || '导入失败')
        return
      }
      cond.importBatchNo = res.data.batchNo
      cond.importedCount = res.data.total
      this.$modal.msgSuccess('已导入 ' + res.data.total + ' 条')
    },
    // ==================== 逻辑关系区 ====================
    addParen(type) {
      if (!this.activeConditionId) {
        this.$modal.msgWarning('请先选中一个规则行')
        return
      }
      const cond = this.conditions.find(c => c.conditionId === this.activeConditionId)
      if (type === 'open') cond.openParen = (cond.openParen || 0) + 1
      else cond.closeParen = (cond.closeParen || 0) + 1
    },
    handleFormat() {
      const lines = this.conditions.map((c, i) => {
        const connector = i === 0 ? '' : (c.connector === 'AND' ? ' 且 ' : ' 或 ')
        const parenOpen = '('.repeat(c.openParen || 0)
        const parenClose = ')'.repeat(c.closeParen || 0)
        let expr = c.tagName
        switch (c.tagType) {
          case '数值型':
            expr += ' 在 ' + (c.values[0] || '无下限') + ' 至 ' + (c.values[1] || '无上限') + ' 之间'
            break
          case '选项型':
            expr += ' 属于 ' + (c.values || []).map(v => this.codeLabel(c, v)).join('/')
            break
          case '布尔型':
            expr += ' 为 ' + (c.values && c.values[0] !== undefined && c.values[0] !== '' ? this.codeLabel(c, c.values[0]) : '?')
            break
          case '文本型':
            expr += ' ' + (c.operator === 'like' ? '模糊匹配' : '精准匹配') + ' ' + (c.values[0] || '?')
            break
          case '日期型':
            expr += ' 在 ' + (c.dateRange ? c.dateRange.join(' 至 ') : '?') + ' 之间'
            break
          case '客户号':
            if (c.matchType === 'import') expr += ' 属于导入列表(' + (c.importedCount || 0) + ' 条)'
            else expr += ' ' + (c.matchType === 'like' ? '模糊匹配' : '精准匹配') + ' ' + (c.values[0] || '?')
            break
        }
        return parenOpen + expr + parenClose
      })
      this.formatText = lines.join('\n')
      this.formatVisible = true
    },
    handleClear() {
      this.$confirm('确认清空全部规则？', '提示', { type: 'warning' }).then(() => {
        this.conditions = []
        this.previewColumns = []
        this.userCount = 0
      }).catch(() => {})
    },
    // ==================== 工具栏 ====================
    buildRule() {
      return {
        schemaVersion: 2,
        objectKeyField: this.objectKeyField,
        conditions: this.conditions.map(c => this.buildCondition(c)),
        previewColumns: this.previewColumns
      }
    },
    /** 选项型/布尔型条件补 selectedCodeOptions（label 取当前选项显示文字，values 仍存真实 code） */
    buildCondition(c) {
      if (c.tagType !== '选项型' && c.tagType !== '布尔型') return c
      const options = this.codeCache[this.codeKey(c.fieldName)] || []
      const selectedCodeOptions = (c.values || []).map(code => {
        const opt = options.find(o => String(o.code) === String(code))
        return { code: code, label: opt ? (opt.codeDefinition || opt.code) : String(code) }
      })
      return Object.assign({}, c, { selectedCodeOptions: selectedCodeOptions })
    },
    /** 失效编码检查：已保存码值不在当前码表中的条件，修正前禁止保存/运行 */
    checkInvalidCodes() {
      const stale = this.conditions.filter(c => this.invalidCodes(c).length > 0)
      if (stale.length > 0) {
        this.$modal.msgWarning('存在已失效码值，请修正后再操作：' + stale.map(c => c.tagName).join('、'))
        return false
      }
      return true
    },
    validateRule() {
      if (this.conditions.length === 0) {
        this.$modal.msgWarning('请先拖入标签构建规则')
        return false
      }
      const invalid = this.conditions.filter(c => !this.isConditionValid(c))
      if (invalid.length > 0) {
        this.$modal.msgWarning('存在未填写完整的规则行：' + invalid.map(c => c.tagName).join('、'))
        return false
      }
      return this.checkInvalidCodes()
    },
    handleRun() {
      if (!this.validateRule()) return
      runGroup({ groupId: this.groupId, libraryId: this.libraryId, rule: this.buildRule() }).then(response => {
        this.userCount = response.data.count
        const warning = response.data.warning
        if (warning) {
          this.$modal.msgWarning('运行完成，用户数 ' + this.userCount + '；' + warning)
        } else {
          this.$modal.msgSuccess('运行完成，用户数 ' + this.userCount)
        }
      }).catch(() => {})
    },
    handleSqlPreview() {
      if (!this.validateRule()) return
      previewSql({ libraryId: this.libraryId, rule: this.buildRule() }).then(response => {
        this.sqlText = response.data
        this.sqlVisible = true
      }).catch(() => {})
    },
    handleSamplePreview() {
      if (!this.validateRule()) return
      this.sampleVisible = true
      this.fetchSamplePreview()
    },
    fetchSamplePreview() {
      this.sampleLoading = true
      previewGroup({ groupId: this.groupId, libraryId: this.libraryId, rule: this.buildRule() }).then(response => {
        this.sampleColumns = response.data.columns || []
        this.sampleRawRows = response.data.rows || []
        // 后端中文副本；缺省（旧接口）回退原始编码
        this.sampleCnRows = response.data.displayRows || this.sampleRawRows
        this.sampleNotes = response.data.mappingNotes || []
        this.sampleLoading = false
      }).catch(() => { this.sampleLoading = false })
    },
    onPreviewColAdd(evt) {
      // 拖入的是 cloneCondition 产出的规则对象，归一化为预览列 { tagId, fieldName, tagName, tagType, dataType }
      const item = this.previewColumns[evt.newIndex]
      if (!item) return
      const col = { tagId: item.tagId, fieldName: item.fieldName, tagName: item.tagName, tagType: item.tagType, dataType: item.dataType }
      this.previewColumns.splice(evt.newIndex, 1, col)
      const dupIndex = this.previewColumns.findIndex((c, i) => i !== evt.newIndex && c.tagId === col.tagId)
      if (dupIndex !== -1) {
        this.previewColumns.splice(evt.newIndex, 1)
        this.$modal.msgWarning('该标签已在预览列中')
        return
      }
      // 预览面板下拉展示中：拖入新列后立即刷新预览数据
      if (this.sampleVisible) {
        this.fetchSamplePreview()
      }
    },
    removePreviewCol(col) {
      this.previewColumns = this.previewColumns.filter(c => c.tagId !== col.tagId)
      // 预览面板下拉展示中：移除列后同步刷新预览数据
      if (this.sampleVisible) {
        this.fetchSamplePreview()
      }
    },
    // ==================== 保存/返回 ====================
    handleSave() {
      if (!this.libraryId) {
        this.$modal.msgWarning('请选择标签库')
        return
      }
      // 失效编码未修正前禁止保存
      if (!this.checkInvalidCodes()) return
      // 编辑已有对象群：名称/描述已存在，直接保存；新建时才弹窗录入
      if (this.groupId) {
        this.doSave(this.groupName, this.groupDesc)
        return
      }
      this.saveForm.groupName = this.groupName
      this.saveForm.groupDesc = this.groupDesc
      this.saveVisible = true
      this.$nextTick(() => {
        if (this.$refs.saveForm) this.$refs.saveForm.clearValidate()
      })
    },
    confirmSave() {
      this.$refs.saveForm.validate(valid => {
        if (!valid) return
        this.doSave(this.saveForm.groupName, this.saveForm.groupDesc)
      })
    },
    doSave(groupName, groupDesc) {
      this.groupName = groupName
      this.groupDesc = groupDesc
      const payload = {
        groupId: this.groupId,
        groupName: this.groupName,
        groupDesc: this.groupDesc,
        libraryId: this.libraryId,
        ruleJson: JSON.stringify(this.buildRule())
      }
      this.saveLoading = true
      const api = this.groupId ? updateGroup(payload) : addGroup(payload)
      api.then(() => {
        this.saveLoading = false
        this.saveVisible = false
        this.$modal.msgSuccess('保存成功')
        this.handleBack()
      }).catch(() => { this.saveLoading = false })
    },
    handleBack() {
      this.$router.push('/objectgroup/group')
    },
    copySql() {
      this.copyText(this.sqlText)
    },
    copyFormat() {
      this.copyText(this.formatText)
    },
    copyText(text) {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      this.$modal.msgSuccess('已复制')
    }
  }
}
</script>

<style scoped>
.rule-editor {
  display: flex;
  height: calc(100vh - 84px);
  gap: 12px;
  overflow: hidden;
}

/* 左侧面板 */
.left-panel {
  width: 320px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e6ebf5;
  border-radius: 4px;
  padding: 12px;
  overflow-y: auto;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.tree-node {
  display: flex;
  align-items: center;
  width: 100%;
}

.tree-drag {
  flex: 1;
  cursor: grab;
}

.node-content {
  display: flex;
  align-items: center;
  flex: 1;
  font-size: 13px;
}

.tree-drag:hover .node-content {
  color: #409eff;
}

.tag-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 7px;
  flex-shrink: 0;
}

.node-count {
  margin-left: 4px;
  font-size: 12px;
  color: #909399;
}

.obj-key-badge {
  margin-left: 6px;
  padding: 0 6px;
  font-size: 11px;
  line-height: 15px;
  border-radius: 8px;
  background: #f56c6c;
  color: #fff;
  flex-shrink: 0;
}

/* 不可拖拽标签（未上线/来源不可用） */
.node-disabled {
  color: #c0c4cc;
  cursor: not-allowed;
}

.node-status-badge {
  margin-left: 6px;
  padding: 0 6px;
  font-size: 11px;
  line-height: 15px;
  border-radius: 8px;
  background: #f0f2f5;
  color: #909399;
  flex-shrink: 0;
}

/* 样例预览映射提示 */
.sample-notes {
  padding: 8px 14px;
  background: #fdf6ec;
  border-bottom: 1px solid #faecd8;
  font-size: 12px;
  color: #e6a23c;
}

.sample-note-item {
  display: flex;
  align-items: center;
  gap: 4px;
  line-height: 20px;
}

/* 右侧面板 */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e6ebf5;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  overflow: hidden;
  position: relative;
}

/* 样例预览面板（顶部下拉，覆盖右侧全部区域） */
.sample-panel {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.sample-panel-header {
  display: flex;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid #ebeef5;
  background: #fafbfc;
}

.sample-panel-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.sample-panel-body {
  flex: 1;
  overflow: auto;
  padding: 12px 14px;
}

/* 下拉/上卷动画 */
.sample-slide-enter-active,
.sample-slide-leave-active {
  transition: transform 0.3s ease;
}

.sample-slide-enter,
.sample-slide-leave-to {
  transform: translateY(-100%);
}

/* 工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #ebeef5;
  background: #fafbfc;
  flex-wrap: wrap;
}

.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.user-count-label {
  font-size: 13px;
  color: #909399;
}

.user-count-num {
  font-size: 20px;
  font-weight: 700;
  color: #409eff;
  margin-right: 8px;
}

/* 预览列区 */
.preview-col-area {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-bottom: 1px solid #ebeef5;
  background: #f5f7fa;
  min-height: 42px;
}

.preview-col-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  flex: 1;
  min-height: 24px;
}

.preview-col-tag {
  cursor: grab;
}

.area-label {
  font-size: 12px;
  color: #606266;
  font-weight: 600;
  flex-shrink: 0;
}

.area-hint {
  font-size: 12px;
  color: #c0c4cc;
}

/* 规则编辑区 */
.rule-area {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 120px;
}

.rule-row {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.rule-row:hover {
  border-color: #c6e2ff;
}

.rule-row.is-active {
  border-color: #409eff;
  box-shadow: 0 0 0 1px #409eff;
}

.rule-row.is-invalid {
  border-left: 3px solid #f56c6c;
}

.rule-row-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.row-index {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.row-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.row-type {
  flex-shrink: 0;
}

.row-parens {
  display: flex;
  gap: 4px;
}

.paren-chip {
  font-size: 11px;
  color: #e6a23c;
  background: #fdf6ec;
  padding: 0 6px;
  border-radius: 4px;
}

.row-delete {
  margin-left: auto;
}

.rule-row-body {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.range-label {
  font-size: 12px;
  color: #909399;
}

.rule-empty {
  text-align: center;
  padding: 60px 0;
  color: #c0c4cc;
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
}

.rule-empty p {
  margin: 8px 0 0;
  font-size: 13px;
}

.import-area {
  display: flex;
  align-items: center;
  gap: 8px;
}

.import-hint {
  font-size: 12px;
  color: #67c23a;
}

.import-note {
  font-size: 12px;
  color: #909399;
}

/* 逻辑关系区 */
.logic-area {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid #ebeef5;
  background: #fafbfc;
}

.logic-hint {
  margin-left: auto;
  font-size: 12px;
  color: #909399;
}

/* SQL 块 */
.sql-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 14px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
}
</style>
