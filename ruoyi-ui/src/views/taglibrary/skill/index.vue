<template>
  <div class="app-container">
    <!-- 搜索 -->
    <el-form :inline="true" size="small" @submit.native.prevent="loadSkills">
      <el-form-item label="技能">
        <el-input v-model="query.keyword" placeholder="名称或描述" clearable style="width: 200px"
          prefix-icon="el-icon-search" @keyup.enter.native="loadSkills" @clear="loadSkills" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="query.category" placeholder="全部" clearable style="width: 150px" @change="loadSkills">
          <el-option v-for="item in categories" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" placeholder="全部" clearable style="width: 150px" @change="loadSkills">
          <el-option v-for="item in statuses" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="el-icon-search" :loading="loading" @click="loadSkills">查询</el-button>
        <el-button icon="el-icon-refresh" @click="resetQuery">刷新</el-button>
      </el-form-item>
    </el-form>

    <!-- 技能列表 -->
    <el-table v-loading="loading" :data="skills" size="small" border
      empty-text="暂无技能，请确认洞察技能服务已启动">
      <el-table-column label="技能名称" min-width="180" show-overflow-tooltip>
        <template slot-scope="s">
          <div class="skill-name">{{ s.row.name }}</div>
          <div class="skill-id">{{ s.row.skill_id }}</div>
        </template>
      </el-table-column>
      <el-table-column label="分类" width="190">
        <template slot-scope="s">
          <el-tag size="mini" :type="categoryTag(s.row.category)">{{ categoryLabel(s.row.category) }}</el-tag>
          <el-tag size="mini" type="info" class="gap-left">{{ s.row.layer || '-' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="80" align="center" />
      <el-table-column label="状态" width="90" align="center">
        <template slot-scope="s">
          <el-tag size="mini" :type="statusTag(s.row.status)">{{ statusLabel(s.row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="owner" label="负责人" width="120" show-overflow-tooltip />
      <el-table-column prop="default_benchmark" label="默认基准" width="150" show-overflow-tooltip />
      <el-table-column label="所需权限" min-width="170" show-overflow-tooltip>
        <template slot-scope="s">{{ (s.row.required_permissions || []).join('、') || '-' }}</template>
      </el-table-column>
      <el-table-column label="更新时间" width="150" align="center">
        <template slot-scope="s">{{ formatTime(s.row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template slot-scope="s">
          <el-button type="text" size="mini" v-hasPermi="['taglibrary:skill:query']" @click="openDetail(s.row)">详情</el-button>
          <el-button v-if="s.row.status !== 'published'" type="text" size="mini"
            v-hasPermi="['taglibrary:skill:publish']" @click="openAction(s.row, 'publish')">发布</el-button>
          <el-button v-if="s.row.status === 'published'" type="text" size="mini"
            v-hasPermi="['taglibrary:skill:publish']" @click="openAction(s.row, 'offline')">下线</el-button>
          <el-button type="text" size="mini" v-hasPermi="['taglibrary:skill:run']" @click="openRun(s.row)">试运行</el-button>
          <el-button type="text" size="mini" @click="openRuns(s.row)">运行历史</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 详情抽屉 -->
    <el-drawer title="技能详情" :visible.sync="detailVisible" size="62%" append-to-body>
      <div v-loading="detailLoading" class="drawer-body">
        <template v-if="detail">
          <div class="detail-head">
            <span class="detail-name">{{ detail.name }}</span>
            <el-tag size="mini" :type="statusTag(detail.status)">{{ statusLabel(detail.status) }}</el-tag>
            <el-tag size="mini" type="info">{{ detail.layer || '-' }}</el-tag>
            <el-tag size="mini" :type="categoryTag(detail.category)">{{ categoryLabel(detail.category) }}</el-tag>
          </div>
          <div class="detail-sub">{{ detail.skill_id }} · v{{ detail.version }} · {{ detail.owner || '-' }}</div>
          <p class="detail-desc">{{ detail.description || '暂无描述' }}</p>

          <el-divider content-position="left">Manifest 关键契约</el-divider>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="必需输入">
              {{ (detail.required_inputs || []).join('、') || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="适用对象">
              {{ (detail.applicable_objects || []).join('、') || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="所需指标">
              {{ (detail.required_metrics || []).join('、') || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="默认基准">{{ detail.default_benchmark || '-' }}</el-descriptions-item>
            <el-descriptions-item label="可选基准">
              {{ (detail.allowed_benchmarks || []).join('、') || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="场景包">
              {{ (detail.scenario_packs || []).join('、') || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="前置条件">
              最少客户数 {{ (detail.preconditions || {}).min_customer_count || '-' }} ·
              数据新鲜度 {{ (detail.preconditions || {}).max_data_age_days || '-' }} 天
            </el-descriptions-item>
            <el-descriptions-item label="所需权限">
              {{ ((detail.preconditions || {}).required_permissions || []).join('、') || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="执行器">
              {{ (detail.executor || {}).type || '-' }} / {{ (detail.executor || {}).operation || '-' }}
              （超时 {{ (detail.executor || {}).timeout_seconds || '-' }}s）
            </el-descriptions-item>
            <el-descriptions-item label="产出结构">{{ detail.output_schema || '-' }}</el-descriptions-item>
            <el-descriptions-item label="人工复核">{{ detail.human_review_required ? '需要' : '不需要' }}</el-descriptions-item>
            <el-descriptions-item label="评测集">{{ detail.evaluation_suite || '-' }}</el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">校验器</el-divider>
          <el-tag v-for="v in (detail.validators || [])" :key="v" size="mini" class="gap-right">{{ v }}</el-tag>
          <span v-if="!(detail.validators || []).length" class="muted">-</span>

          <el-divider content-position="left">图表意图</el-divider>
          <el-table :data="detail.visualizations || []" size="mini" border>
            <el-table-column prop="chart_skill" label="图表能力" min-width="220" />
            <el-table-column prop="preferred_mark" label="偏好图元" width="140" />
          </el-table>

          <el-divider content-position="left">版本与生命周期</el-divider>
          <el-timeline>
            <el-timeline-item v-for="(item, index) in lifecycle" :key="index" :timestamp="formatTime(item.changed_at)"
              placement="top" :color="statusColor(item.status)">
              <div class="timeline-line">
                <span class="timeline-version">v{{ item.version }}</span>
                <el-tag size="mini" :type="statusTag(item.status)">{{ statusLabel(item.status) }}</el-tag>
                <span class="muted">{{ item.reason || '-' }}</span>
              </div>
              <div class="muted">操作人：{{ item.operator_id || '-' }}</div>
            </el-timeline-item>
          </el-timeline>
          <div v-if="!lifecycle.length" class="muted">暂无生命周期记录</div>
        </template>
      </div>
    </el-drawer>

    <!-- 状态流转确认 -->
    <el-dialog :title="actionTitle" :visible.sync="actionVisible" width="480px" append-to-body>
      <el-form label-width="80px" size="small">
        <el-form-item label="技能">
          <span>{{ actionForm.name }}（{{ actionForm.skillId }} v{{ actionForm.version }}）</span>
        </el-form-item>
        <el-form-item label="动作">
          <el-tag size="small">{{ actionLabel(actionForm.action) }}</el-tag>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="actionForm.reason" type="textarea" :rows="3" maxlength="200" show-word-limit
            placeholder="请填写操作原因，将写入审计" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button size="small" @click="actionVisible = false">取消</el-button>
        <el-button type="primary" size="small" :loading="actionLoading" @click="submitAction">确认</el-button>
      </div>
    </el-dialog>

    <!-- 试运行 -->
    <el-dialog title="技能试运行" :visible.sync="runVisible" width="920px" top="5vh" append-to-body>
      <el-form :inline="true" size="small">
        <el-form-item label="技能">
          <span>{{ runForm.name }}（{{ runForm.skillId }}）</span>
        </el-form-item>
        <el-form-item label="客群">
          <el-select v-model="runForm.groupId" filterable placeholder="请选择客群" style="width: 240px">
            <el-option v-for="g in groups" :key="g.groupId" :label="g.groupName" :value="g.groupId" />
          </el-select>
        </el-form-item>
        <el-form-item label="基准类型">
          <el-select v-model="runForm.benchmarkType" placeholder="缺省基准" clearable style="width: 170px">
            <el-option v-for="b in benchmarks" :key="b.value" :label="b.label" :value="b.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据日期">
          <el-date-picker v-model="runForm.asOfDate" type="date" value-format="yyyy-MM-dd" placeholder="缺省今天"
            style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="small" :loading="runLoading" :disabled="!runForm.groupId"
            @click="submitRun">开始试运行</el-button>
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" class="run-tip"
        title="成员名单由服务端按客群规则解析（上限 10 万），图表只展示已聚合、已校验的数据。" />

      <div v-if="runResult" class="run-result">
        <el-descriptions :column="4" size="small" border>
          <el-descriptions-item label="状态">
            <el-tag size="mini" :type="runResult.status === 'succeeded' ? 'success' : 'warning'">
              {{ runResult.status === 'succeeded' ? '运行成功' : '已阻断' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="客群人数">{{ audienceCount }}</el-descriptions-item>
          <el-descriptions-item label="数据截至">{{ runResult.data_as_of || '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ runResult.duration_ms || 0 }} ms</el-descriptions-item>
          <el-descriptions-item label="运行ID" :span="2">{{ runResult.run_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="技能版本">{{ runResult.skill_version || '-' }}</el-descriptions-item>
          <el-descriptions-item label="基准">
            {{ (runResult.benchmark || {}).name || (runResult.benchmark || {}).type || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-alert v-if="runResult.blocked_reason" type="warning" :closable="false" class="gap-top"
          :title="'已阻断：' + runResult.blocked_reason" />

        <!-- 关键指标 -->
        <section v-if="kpiMetrics.length" class="block">
          <h4 class="block-title">关键指标</h4>
          <el-row :gutter="12">
            <el-col v-for="m in kpiMetrics" :key="m.id" :span="6">
              <div class="kpi-card">
                <div class="kpi-value">{{ m.value }}<span class="kpi-unit">{{ m.unit }}</span></div>
                <div class="kpi-label">{{ m.name }}</div>
                <div v-if="m.definition" class="kpi-def">{{ m.definition }}</div>
              </div>
            </el-col>
          </el-row>
        </section>

        <!-- 洞察卡 -->
        <section v-if="insightCards.length" class="block">
          <h4 class="block-title">洞察卡</h4>
          <el-card v-for="card in insightCards" :key="card.card_id" shadow="never" class="insight-card">
            <div class="ic-title">{{ card.title }}</div>
            <div v-if="card.fact" class="ic-row">
              <span class="ic-label ic-fact">事实</span><span class="ic-text">{{ card.fact.text }}</span>
            </div>
            <div v-if="card.benchmark" class="ic-row">
              <span class="ic-label ic-benchmark">对比</span><span class="ic-text">{{ card.benchmark.text }}</span>
            </div>
            <div v-if="card.diagnosis" class="ic-row">
              <span class="ic-label ic-diagnosis">诊断</span><span class="ic-text">{{ card.diagnosis.text }}</span>
              <el-tag v-if="card.diagnosis.confidence" size="mini" type="info" class="gap-left">
                置信度 {{ Math.round(card.diagnosis.confidence * 100) }}%
              </el-tag>
            </div>
            <div v-if="card.action" class="ic-row">
              <span class="ic-label ic-action">行动</span><span class="ic-text">{{ card.action.recommendation }}</span>
              <el-tag v-if="card.action.priority" size="mini" :type="priorityTag(card.action.priority)" class="gap-left">
                优先级 {{ card.action.priority }}
              </el-tag>
              <span v-if="card.action.eligible_customer_count !== undefined" class="ic-eligible">
                可触达 {{ card.action.eligible_customer_count }} 人
              </span>
            </div>
            <div v-if="card.boundary" class="ic-row">
              <span class="ic-label ic-boundary">边界</span><span class="ic-text">{{ card.boundary.text }}</span>
            </div>
            <div v-if="card.provenance" class="ic-foot">
              来源：{{ card.provenance.skill_id }}@{{ card.provenance.skill_version }} · 数据截至 {{ card.provenance.data_as_of }}
            </div>
          </el-card>
        </section>

        <!-- 图表 -->
        <section v-if="chartViews.length" class="block">
          <h4 class="block-title">图表</h4>
          <el-card v-for="(view, index) in chartViews" :key="index" shadow="never" class="chart-card">
            <div class="chart-head">
              <span class="chart-title">{{ view.title || '图表' }}</span>
              <el-tag size="mini" type="info">{{ view.mark }}</el-tag>
            </div>
            <insight-chart v-if="view.kind === 'echarts'" :option="view.option" />
            <el-row v-else-if="view.kind === 'kpi'" :gutter="12">
              <el-col v-for="(item, i) in view.items" :key="i" :span="6">
                <div class="kpi-card">
                  <div class="kpi-value">{{ item.value }}<span class="kpi-unit">{{ item.unit }}</span></div>
                  <div class="kpi-label">{{ item.label }}</div>
                </div>
              </el-col>
            </el-row>
            <el-table v-else :data="view.rows" size="mini" border>
              <el-table-column v-for="col in view.columns" :key="col.prop" :prop="col.prop"
                :label="col.label + (col.unit ? '(' + col.unit + ')' : '')" min-width="120" show-overflow-tooltip />
            </el-table>
            <div v-if="view.summary" class="chart-summary">{{ view.summary }}</div>
            <div v-if="view.notes.length" class="chart-notes">
              <div v-for="(note, i) in view.notes" :key="i">· {{ note }}</div>
            </div>
            <el-collapse v-if="view.kind === 'echarts' && view.dataTable && view.rows.length" class="chart-table">
              <el-collapse-item title="查看数据表">
                <el-table :data="view.rows" size="mini" border max-height="260">
                  <el-table-column v-for="col in view.columns" :key="col.prop" :prop="col.prop"
                    :label="col.label + (col.unit ? '(' + col.unit + ')' : '')" min-width="110" show-overflow-tooltip />
                </el-table>
              </el-collapse-item>
            </el-collapse>
          </el-card>
        </section>

        <!-- 证据 -->
        <section v-if="evidenceRows.length" class="block">
          <h4 class="block-title">证据</h4>
          <el-table :data="evidenceRows" size="mini" border max-height="260">
            <el-table-column v-for="key in evidenceKeys" :key="key" :prop="key" :label="key" min-width="130"
              show-overflow-tooltip :formatter="formatCell" />
          </el-table>
        </section>

        <!-- 校验器结果 -->
        <section v-if="validationRows.length" class="block">
          <h4 class="block-title">校验器结果</h4>
          <el-table :data="validationRows" size="mini" border>
            <el-table-column prop="name" label="校验项" min-width="200" />
            <el-table-column label="结果" width="90" align="center">
              <template slot-scope="s">
                <el-tag size="mini" :type="s.row.passed ? 'success' : 'danger'">{{ s.row.passed ? '通过' : '未通过' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="detail" label="说明" min-width="240" show-overflow-tooltip />
          </el-table>
        </section>

        <!-- 诊断 -->
        <section v-if="diagnostics.length" class="block">
          <h4 class="block-title">诊断信息</h4>
          <div v-for="(d, i) in diagnostics" :key="i" class="diagnostic" :class="'level-' + (d.level || 'info')">
            <el-tag size="mini" :type="d.level === 'warn' ? 'warning' : 'info'">{{ d.level || 'info' }}</el-tag>
            <span class="diagnostic-code">{{ d.code }}</span>
            <span>{{ d.message }}</span>
          </div>
        </section>
      </div>
    </el-dialog>

    <!-- 运行历史 -->
    <el-drawer title="运行历史" :visible.sync="runsVisible" size="70%" append-to-body>
      <div class="drawer-body">
        <el-table v-loading="runsLoading" :data="runs" size="small" border empty-text="暂无运行记录">
          <el-table-column prop="createTime" label="时间" width="160" />
          <el-table-column prop="skillId" label="技能" min-width="170" show-overflow-tooltip />
          <el-table-column prop="skillVersion" label="版本" width="80" align="center" />
          <el-table-column prop="audienceName" label="客群" min-width="150" show-overflow-tooltip />
          <el-table-column prop="customerCount" label="人数" width="80" align="center" />
          <el-table-column label="状态" width="90" align="center">
            <template slot-scope="s">
              <el-tag size="mini" :type="runTag(s.row.status)">{{ runStatusLabel(s.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="durationMs" label="耗时(ms)" width="95" align="center" />
          <el-table-column prop="operatorName" label="操作人" width="110" show-overflow-tooltip />
          <el-table-column prop="blockedReason" label="阻断原因" min-width="180" show-overflow-tooltip />
        </el-table>
        <pagination v-show="runsTotal > 0" :total="runsTotal" :page.sync="runsQuery.pageNum"
          :limit.sync="runsQuery.pageSize" @pagination="loadRuns" />
      </div>
    </el-drawer>
  </div>
</template>

<script>
import {
  listSkill, getSkill, changeSkillStatus, runSkill, listSkillRuns
} from '@/api/taglibrary/skill'
import { listGroup } from '@/api/objectgroup/group'
import { buildChartViews } from './chartSpecAdapter'
import InsightChart from './InsightChart'

const CATEGORIES = [
  { value: 'fact', label: '事实类' },
  { value: 'diagnostic', label: '诊断类' },
  { value: 'action', label: '行动类' }
]

const STATUSES = [
  { value: 'draft', label: '草稿' },
  { value: 'published', label: '已发布' },
  { value: 'deprecated', label: '已废弃' },
  { value: 'offline', label: '已下线' }
]

const BENCHMARKS = [
  { value: 'ALL_BRANCH', label: '全部客户' },
  { value: 'SAME_AUM_BAND', label: '同AUM层级客户' },
  { value: 'SAME_RISK_LEVEL', label: '同风险等级客户' }
]

const METRIC_LABELS = {
  customer_count: '客群客户数',
  liquid_asset_ratio: '活期及短期存款占比',
  aum_band: 'AUM层级',
  risk_level: '风险等级',
  product_holding_matrix: '产品持有矩阵',
  wealth_product_holding_rate: '理财产品持有率'
}

const ACTION_LABELS = {
  publish: '发布',
  offline: '下线',
  deprecate: '废弃',
  draft: '转草稿'
}

export default {
  name: 'TagSkillManage',
  components: { InsightChart },
  data() {
    return {
      categories: CATEGORIES,
      statuses: STATUSES,
      benchmarks: BENCHMARKS,
      loading: false,
      skills: [],
      query: { keyword: '', category: undefined, status: undefined },
      // 详情
      detailVisible: false,
      detailLoading: false,
      detail: null,
      // 状态流转
      actionVisible: false,
      actionLoading: false,
      actionTitle: '',
      actionForm: { skillId: '', name: '', version: '', action: 'publish', reason: '' },
      // 试运行
      runVisible: false,
      runLoading: false,
      groups: [],
      runForm: { skillId: '', name: '', groupId: undefined, benchmarkType: undefined, asOfDate: undefined },
      runResult: null,
      // 运行历史
      runsVisible: false,
      runsLoading: false,
      runs: [],
      runsTotal: 0,
      runsQuery: { pageNum: 1, pageSize: 10, skillId: undefined }
    }
  },
  computed: {
    lifecycle() {
      return (this.detail && this.detail.lifecycle) || []
    },
    audienceCount() {
      const audience = (this.runResult && this.runResult.audience) || {}
      return audience.customer_count === undefined ? '-' : audience.customer_count
    },
    kpiMetrics() {
      const metrics = (this.runResult && this.runResult.metrics) || {}
      return Object.keys(metrics).map(id => {
        const metric = metrics[id] || {}
        return {
          id,
          name: METRIC_LABELS[metric.metric_id || id] || metric.metric_id || id,
          value: metric.value === null || metric.value === undefined ? '-' : metric.value,
          unit: metric.unit || '',
          definition: metric.definition || ''
        }
      })
    },
    insightCards() {
      return (this.runResult && this.runResult.insight_cards) || []
    },
    chartViews() {
      return buildChartViews((this.runResult && this.runResult.charts) || [])
    },
    evidenceRows() {
      return (this.runResult && this.runResult.evidence) || []
    },
    evidenceKeys() {
      const keys = []
      this.evidenceRows.forEach(row => {
        Object.keys(row || {}).forEach(key => {
          if (keys.indexOf(key) === -1) keys.push(key)
        })
      })
      return keys
    },
    validationRows() {
      if (!this.runResult) return []
      return [].concat(this.runResult.validations || [], this.runResult.chart_validations || [])
    },
    diagnostics() {
      return (this.runResult && this.runResult.diagnostics) || []
    }
  },
  created() {
    this.loadSkills()
  },
  methods: {
    async loadSkills() {
      this.loading = true
      try {
        const response = await listSkill({
          status: this.query.status,
          category: this.query.category,
          keyword: this.query.keyword,
          limit: 200,
          offset: 0
        })
        const data = response.data || {}
        this.skills = data.items || []
      } catch (e) {
        this.skills = []
      } finally {
        this.loading = false
      }
    },
    resetQuery() {
      this.query = { keyword: '', category: undefined, status: undefined }
      this.loadSkills()
    },
    categoryLabel(value) {
      const found = CATEGORIES.find(item => item.value === value)
      return found ? found.label : (value || '-')
    },
    categoryTag(value) {
      return { fact: 'info', diagnostic: 'warning', action: 'success' }[value] || 'info'
    },
    statusLabel(value) {
      const found = STATUSES.find(item => item.value === value)
      return found ? found.label : (value || '-')
    },
    statusTag(value) {
      return {
        draft: 'info', published: 'success', deprecated: 'warning', offline: 'danger'
      }[value] || 'info'
    },
    statusColor(value) {
      return {
        draft: '#909399', published: '#67C23A', deprecated: '#E6A23C', offline: '#F56C6C'
      }[value] || '#909399'
    },
    priorityTag(priority) {
      return { high: 'danger', medium: 'warning', low: 'info' }[priority] || 'info'
    },
    runTag(status) {
      return { succeeded: 'success', blocked: 'warning', failed: 'danger' }[status] || 'info'
    },
    runStatusLabel(status) {
      return { succeeded: '成功', blocked: '已阻断', failed: '失败' }[status] || (status || '-')
    },
    formatTime(value) {
      if (!value) return '-'
      return String(value).replace('T', ' ').replace(/(\+|-)\d{2}:\d{2}$/, '').substring(0, 19)
    },
    formatCell(row, column, cellValue) {
      if (cellValue === null || cellValue === undefined) return '-'
      return typeof cellValue === 'object' ? JSON.stringify(cellValue) : cellValue
    },
    actionLabel(action) {
      return ACTION_LABELS[action] || action
    },
    async openDetail(row) {
      this.detail = null
      this.detailVisible = true
      this.detailLoading = true
      try {
        const response = await getSkill(row.skill_id)
        this.detail = response.data || {}
      } catch (e) {
        this.detail = null
      } finally {
        this.detailLoading = false
      }
    },
    openAction(row, action) {
      this.actionForm = {
        skillId: row.skill_id,
        name: row.name,
        version: row.version,
        action,
        reason: ''
      }
      this.actionTitle = this.actionLabel(action) + '技能'
      this.actionVisible = true
    },
    async submitAction() {
      if (!this.actionForm.reason || !this.actionForm.reason.trim()) {
        this.$modal.msgWarning('请填写操作原因')
        return
      }
      this.actionLoading = true
      try {
        await changeSkillStatus(this.actionForm.skillId, {
          action: this.actionForm.action,
          version: this.actionForm.version,
          reason: this.actionForm.reason.trim()
        })
        this.$modal.msgSuccess(this.actionLabel(this.actionForm.action) + '成功')
        this.actionVisible = false
        this.loadSkills()
      } finally {
        this.actionLoading = false
      }
    },
    async openRun(row) {
      this.runForm = {
        skillId: row.skill_id,
        name: row.name,
        groupId: undefined,
        benchmarkType: row.default_benchmark,
        asOfDate: undefined
      }
      this.runResult = null
      this.runVisible = true
      if (!this.groups.length) {
        try {
          const response = await listGroup({ pageNum: 1, pageSize: 200 })
          this.groups = response.rows || []
        } catch (e) {
          this.groups = []
        }
      }
    },
    async submitRun() {
      this.runLoading = true
      try {
        const response = await runSkill(this.runForm.skillId, {
          groupId: this.runForm.groupId,
          benchmarkType: this.runForm.benchmarkType || undefined,
          asOfDate: this.runForm.asOfDate || undefined
        })
        this.runResult = response.data || {}
      } finally {
        this.runLoading = false
      }
    },
    openRuns(row) {
      this.runsQuery = { pageNum: 1, pageSize: 10, skillId: row.skill_id }
      this.runsVisible = true
      this.loadRuns()
    },
    async loadRuns() {
      this.runsLoading = true
      try {
        const response = await listSkillRuns({
          skillId: this.runsQuery.skillId,
          pageNum: this.runsQuery.pageNum,
          pageSize: this.runsQuery.pageSize
        })
        this.runs = response.rows || []
        this.runsTotal = response.total || 0
      } catch (e) {
        this.runs = []
        this.runsTotal = 0
      } finally {
        this.runsLoading = false
      }
    }
  }
}
</script>

<style scoped>
.skill-name { font-weight: 600; }
.skill-id { color: #909399; font-size: 12px; }
.gap-left { margin-left: 6px; }
.gap-right { margin-right: 6px; }
.gap-top { margin-top: 12px; }
.muted { color: #909399; font-size: 12px; }
.drawer-body { padding: 0 20px 24px; }
.detail-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.detail-name { font-size: 16px; font-weight: 600; }
.detail-sub { color: #909399; font-size: 12px; margin: 6px 0; }
.detail-desc { color: #606266; line-height: 1.7; }
.timeline-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.timeline-version { font-weight: 600; }
.run-tip { margin-bottom: 12px; }
.run-result { max-height: 62vh; overflow-y: auto; padding-right: 6px; }
.block { margin-top: 18px; }
.block-title { font-size: 14px; margin-bottom: 10px; color: #303133; border-left: 3px solid #409EFF; padding-left: 8px; }
.kpi-card { background: #f7f9fc; border-radius: 6px; padding: 12px; margin-bottom: 12px; min-height: 74px; }
.kpi-value { font-size: 22px; font-weight: 600; color: #409EFF; }
.kpi-unit { font-size: 12px; color: #909399; margin-left: 4px; }
.kpi-label { font-size: 12px; color: #606266; margin-top: 4px; }
.kpi-def { font-size: 11px; color: #a0a4ad; margin-top: 4px; line-height: 1.5; }
.insight-card { margin-bottom: 12px; }
.ic-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.ic-row { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; line-height: 1.7; }
.ic-label { flex: 0 0 40px; font-size: 12px; color: #fff; text-align: center; border-radius: 3px; padding: 1px 0; }
.ic-fact { background: #409EFF; }
.ic-benchmark { background: #E6A23C; }
.ic-diagnosis { background: #9B59B6; }
.ic-action { background: #67C23A; }
.ic-boundary { background: #909399; }
.ic-text { flex: 1; color: #303133; }
.ic-eligible { color: #F56C6C; font-size: 12px; }
.ic-foot { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #ebeef5; color: #909399; font-size: 12px; }
.chart-card { margin-bottom: 12px; }
.chart-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.chart-title { font-weight: 600; color: #303133; }
.chart-summary { margin-top: 8px; color: #606266; font-size: 12px; background: #f7f9fc; padding: 8px 10px; border-radius: 4px; }
.chart-notes { margin-top: 6px; color: #E6A23C; font-size: 12px; line-height: 1.8; }
.chart-table { margin-top: 6px; }
.diagnostic { display: flex; align-items: baseline; gap: 8px; padding: 6px 0; color: #606266; font-size: 12px; }
.diagnostic-code { color: #909399; font-family: monospace; }
.level-warn { color: #E6A23C; }
</style>
