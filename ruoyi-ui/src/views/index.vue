<template>
  <div class="app-container home-screen">
    <!-- 头部 -->
    <div class="screen-header">
      <div class="header-title">
        <h2>数据资产总览</h2>
        <p>数据源 · 数据集 · 标签库 · 标签 统计一览</p>
      </div>
      <div class="header-actions">
        <span v-if="lastUpdateTime" class="update-time">更新于 {{ lastUpdateTime }}</span>
        <el-button
          size="small"
          icon="el-icon-refresh"
          :loading="loading"
          @click="loadAll"
        >刷新</el-button>
      </div>
    </div>

    <!-- 指标卡 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="12" :md="6">
        <div class="stat-card" v-loading="firstLoading">
          <div class="stat-icon" style="background: rgba(64, 158, 255, 0.12); color: #409eff">
            <i class="el-icon-coin" />
          </div>
          <div class="stat-body">
            <div class="stat-label">数据源</div>
            <div class="stat-value">{{ fmt(display.datasource, ds.failed) }}</div>
            <div class="stat-sub" v-if="!ds.failed">正常 {{ ds.enabled }} · 停用 {{ ds.disabled }}</div>
            <div class="stat-sub is-failed" v-else>加载失败或暂无权限</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <div class="stat-card" v-loading="firstLoading">
          <div class="stat-icon" style="background: rgba(103, 194, 58, 0.12); color: #67c23a">
            <i class="el-icon-files" />
          </div>
          <div class="stat-body">
            <div class="stat-label">数据集</div>
            <div class="stat-value">{{ fmt(display.dataset, dataset.failed) }}</div>
            <div class="stat-sub" v-if="!dataset.failed">正常 {{ dataset.enabled }} · 停用 {{ dataset.disabled }}</div>
            <div class="stat-sub is-failed" v-else>加载失败或暂无权限</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <div class="stat-card" v-loading="firstLoading">
          <div class="stat-icon" style="background: rgba(230, 162, 60, 0.12); color: #e6a23c">
            <i class="el-icon-collection" />
          </div>
          <div class="stat-body">
            <div class="stat-label">标签库</div>
            <div class="stat-value">{{ fmt(display.library, lib.failed) }}</div>
            <div class="stat-sub" v-if="!lib.failed">已上线 {{ lib.online }} · 待审核 {{ lib.pending }}</div>
            <div class="stat-sub is-failed" v-else>加载失败或暂无权限</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <div class="stat-card" v-loading="firstLoading">
          <div class="stat-icon" style="background: rgba(245, 108, 108, 0.12); color: #f56c6c">
            <i class="el-icon-price-tag" />
          </div>
          <div class="stat-body">
            <div class="stat-label">标签</div>
            <div class="stat-value">{{ fmt(display.tag, tag.failed) }}</div>
            <div class="stat-sub" v-if="!tag.failed">已上线 {{ tag.online }} · 待审核 {{ tag.pending }}</div>
            <div class="stat-sub is-failed" v-else>加载失败或暂无权限</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 分布图表 -->
    <el-row :gutter="16">
      <el-col :xs="24" :sm="24" :md="8">
        <div class="chart-panel">
          <div class="panel-header">
            <span class="panel-title">数据源类型分布</span>
            <span class="panel-total">共 {{ ds.failed ? '--' : ds.total }} 个</span>
          </div>
          <div class="panel-body">
            <div ref="dsType" class="chart chart-donut" />
            <div v-if="ds.failed" class="chart-empty">暂无访问权限或数据加载失败</div>
            <div v-else-if="chartEmpty(ds.typeData)" class="chart-empty">暂无数据</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="24" :md="8">
        <div class="chart-panel">
          <div class="panel-header">
            <span class="panel-title">标签状态分布</span>
            <span class="panel-total">共 {{ tag.failed ? '--' : tag.total }} 个</span>
          </div>
          <div class="panel-body">
            <div ref="tagStatus" class="chart chart-donut" />
            <div v-if="tag.failed" class="chart-empty">暂无访问权限或数据加载失败</div>
            <div v-else-if="chartEmpty(tag.statusData)" class="chart-empty">暂无数据</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="24" :md="8">
        <div class="chart-panel">
          <div class="panel-header">
            <span class="panel-title">标签库状态分布</span>
            <span class="panel-total">共 {{ lib.failed ? '--' : lib.total }} 个</span>
          </div>
          <div class="panel-body">
            <div ref="libStatus" class="chart chart-donut" />
            <div v-if="lib.failed" class="chart-empty">暂无访问权限或数据加载失败</div>
            <div v-else-if="chartEmpty(lib.statusData)" class="chart-empty">暂无数据</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 标签库标签量排行 -->
    <el-row :gutter="16">
      <el-col :span="24">
        <div class="chart-panel">
          <div class="panel-header">
            <span class="panel-title">各标签库标签数量 TOP10</span>
            <span class="panel-total" v-if="!lib.failed">已上线 {{ tagOnlineInTop }} / {{ tagTotalInTop }}</span>
          </div>
          <div class="panel-body">
            <div ref="libTop" class="chart chart-bar" />
            <div v-if="lib.failed" class="chart-empty">暂无访问权限或数据加载失败</div>
            <div v-else-if="lib.topData.length === 0" class="chart-empty">暂无数据</div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import resize from '@/views/dashboard/mixins/resize'
import { treeDataSource } from '@/api/databroker/datasource'
import { treeDataset } from '@/api/databroker/dataset'
import { listLibrary } from '@/api/taglibrary/library'
import { listTag } from '@/api/taglibrary/tag'

// 标签/标签库状态:0 草稿、1 待审核、2 已上线、3 已下线
const STATUS_META = [
  { value: '0', label: '草稿', color: '#909399' },
  { value: '1', label: '待审核', color: '#e6a23c' },
  { value: '2', label: '已上线', color: '#67c23a' },
  { value: '3', label: '已下线', color: '#f56c6c' }
]
const CHART_PALETTE = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#79bbff']

export default {
  name: 'Index',
  mixins: [resize],
  data() {
    return {
      loading: false,
      firstLoading: true,
      lastUpdateTime: '',
      reducedMotion: false,
      display: { datasource: null, dataset: null, library: null, tag: null },
      ds: { failed: false, total: 0, enabled: 0, disabled: 0, typeData: [] },
      dataset: { failed: false, total: 0, enabled: 0, disabled: 0 },
      lib: { failed: false, total: 0, online: 0, pending: 0, statusData: [], topData: [] },
      tag: { failed: false, total: 0, online: 0, pending: 0, statusData: [] },
      charts: {}
    }
  },
  computed: {
    tagOnlineInTop() {
      return this.lib.topData.reduce((sum, r) => sum + (r.onlineCount || 0), 0)
    },
    tagTotalInTop() {
      return this.lib.topData.reduce((sum, r) => sum + (r.tagCount || 0), 0)
    }
  },
  mounted() {
    this.reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    this.loadAll()
  },
  beforeDestroy() {
    Object.keys(this.charts).forEach(key => {
      this.charts[key] && this.charts[key].dispose()
    })
    this.charts = {}
  },
  methods: {
    resize() {
      Object.keys(this.charts).forEach(key => {
        this.charts[key] && this.charts[key].resize()
      })
    },
    loadAll() {
      this.loading = true
      const done = () => {
        this.loading = false
        this.firstLoading = false
        this.lastUpdateTime = this.parseTime(new Date(), '{y}-{m}-{d} {h}:{i}:{s}')
      }
      Promise.all([
        this.loadDatasources(),
        this.loadDatasets(),
        this.loadLibraries(),
        this.loadTags()
      ]).then(done, done)
    },
    // 数据源
    loadDatasources() {
      return treeDataSource().then(res => {
        const nodes = this.flattenTree(res.data || [], 'datasource')
        const typeMap = {}
        let enabled = 0
        nodes.forEach(n => {
          const type = n.sourceType || '未知'
          typeMap[type] = (typeMap[type] || 0) + 1
          if (n.status === '0') enabled++
        })
        this.ds = {
          failed: false,
          total: nodes.length,
          enabled,
          disabled: nodes.length - enabled,
          typeData: Object.keys(typeMap).map(k => ({ name: k, value: typeMap[k] }))
        }
        this.animateCount('datasource', nodes.length)
        this.updateChart('dsType', this.donutOption(this.ds.typeData))
      }).catch(() => {
        this.ds = Object.assign({}, this.ds, { failed: true })
      })
    },
    // 数据集
    loadDatasets() {
      return treeDataset().then(res => {
        const nodes = this.flattenTree(res.data || [], 'dataset')
        const enabled = nodes.filter(n => n.status === '0').length
        this.dataset = {
          failed: false,
          total: nodes.length,
          enabled,
          disabled: nodes.length - enabled
        }
        this.animateCount('dataset', nodes.length)
      }).catch(() => {
        this.dataset = Object.assign({}, this.dataset, { failed: true })
      })
    },
    // 标签库
    loadLibraries() {
      return listLibrary({ pageNum: 1, pageSize: 9999 }).then(res => {
        const rows = res.rows || []
        const statusMap = { '0': 0, '1': 0, '2': 0, '3': 0 }
        rows.forEach(r => {
          const key = Object.prototype.hasOwnProperty.call(statusMap, r.status) ? r.status : '0'
          statusMap[key]++
        })
        const top = rows.slice()
          .sort((a, b) => (b.tagCount || 0) - (a.tagCount || 0))
          .slice(0, 10)
        this.lib = {
          failed: false,
          total: res.total || 0,
          online: statusMap['2'],
          pending: statusMap['1'],
          statusData: STATUS_META.map(m => ({
            name: m.label,
            value: statusMap[m.value],
            itemStyle: { color: m.color }
          })),
          topData: top
        }
        this.animateCount('library', res.total || 0)
        this.updateChart('libStatus', this.donutOption(this.lib.statusData))
        this.updateChart('libTop', this.topBarOption(top))
      }).catch(() => {
        this.lib = Object.assign({}, this.lib, { failed: true })
      })
    },
    // 标签(按状态统计,pageSize=1 仅取 total)
    loadTags() {
      const countByStatus = s => listTag({ pageNum: 1, pageSize: 1, status: s }).then(r => r.total || 0)
      return Promise.all([
        listTag({ pageNum: 1, pageSize: 1 }).then(r => r.total || 0),
        ...STATUS_META.map(m => countByStatus(m.value))
      ]).then(([total, ...counts]) => {
        this.tag = {
          failed: false,
          total,
          online: counts[2],
          pending: counts[1],
          statusData: STATUS_META.map((m, i) => ({
            name: m.label,
            value: counts[i],
            itemStyle: { color: m.color }
          }))
        }
        this.animateCount('tag', total)
        this.updateChart('tagStatus', this.donutOption(this.tag.statusData))
      }).catch(() => {
        this.tag = Object.assign({}, this.tag, { failed: true })
      })
    },
    // 展开树节点,收集指定 nodeType 的节点
    flattenTree(nodes, type) {
      const out = []
      const walk = list => {
        list.forEach(n => {
          if (n.nodeType === type) out.push(n)
          if (n.children && n.children.length) walk(n.children)
        })
      }
      walk(Array.isArray(nodes) ? nodes : [])
      return out
    },
    // 环形图
    donutOption(data) {
      return {
        color: CHART_PALETTE,
        animation: !this.reducedMotion,
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: {
          bottom: 0,
          left: 'center',
          icon: 'circle',
          itemWidth: 8,
          itemHeight: 8,
          itemGap: 16,
          textStyle: { color: '#606266', fontSize: 12 }
        },
        series: [{
          type: 'pie',
          radius: ['46%', '68%'],
          center: ['50%', '44%'],
          itemStyle: { borderColor: '#fff', borderWidth: 2 },
          label: { show: false },
          emphasis: { scale: true, scaleSize: 6 },
          data
        }]
      }
    },
    // 标签库 TOP10 横向堆叠条形图
    topBarOption(rows) {
      const names = rows.map(r => r.libraryName).reverse()
      const online = rows.map(r => r.onlineCount || 0).reverse()
      const others = rows.map(r => Math.max((r.tagCount || 0) - (r.onlineCount || 0), 0)).reverse()
      return {
        animation: !this.reducedMotion,
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
          formatter: params => {
            const i = params[0].dataIndex
            return `${names[i]}<br/>标签总数:${online[i] + others[i]}<br/>已上线:${online[i]}`
          }
        },
        legend: {
          bottom: 0,
          left: 'center',
          icon: 'circle',
          itemWidth: 8,
          itemHeight: 8,
          itemGap: 16,
          textStyle: { color: '#606266', fontSize: 12 },
          data: ['已上线', '未上线']
        },
        grid: { left: 8, right: 48, top: 12, bottom: 36, containLabel: true },
        xAxis: {
          type: 'value',
          minInterval: 1,
          splitLine: { lineStyle: { color: '#ebeef5' } },
          axisLabel: { color: '#909399', fontSize: 12 }
        },
        yAxis: {
          type: 'category',
          data: names,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: '#606266',
            fontSize: 12,
            formatter: v => (v && v.length > 10 ? v.slice(0, 10) + '…' : v)
          }
        },
        series: [
          {
            name: '已上线',
            type: 'bar',
            stack: 'total',
            barWidth: 14,
            itemStyle: { color: '#67c23a' },
            data: online
          },
          {
            name: '未上线',
            type: 'bar',
            stack: 'total',
            barWidth: 14,
            itemStyle: { color: '#a0cfff', borderRadius: [0, 3, 3, 0] },
            label: {
              show: true,
              position: 'right',
              color: '#909399',
              fontSize: 12,
              formatter: p => online[p.dataIndex] + others[p.dataIndex]
            },
            data: others
          }
        ]
      }
    },
    updateChart(name, option) {
      this.$nextTick(() => {
        const el = this.$refs[name]
        if (!el) return
        if (!this.charts[name]) {
          this.charts[name] = echarts.init(el)
        }
        this.charts[name].setOption(option, true)
      })
    },
    // 数字滚动动画
    animateCount(key, target) {
      if (this.reducedMotion) {
        this.$set(this.display, key, target)
        return
      }
      const duration = 700
      const start = performance.now()
      const step = now => {
        const p = Math.min(1, (now - start) / duration)
        const eased = 1 - Math.pow(1 - p, 4)
        this.$set(this.display, key, Math.round(target * eased))
        if (p < 1) requestAnimationFrame(step)
      }
      requestAnimationFrame(step)
    },
    fmt(val, failed) {
      if (failed || val === null || val === undefined) return '--'
      return val
    },
    chartEmpty(data) {
      return !data || data.length === 0 || data.every(d => !d.value)
    }
  }
}
</script>

<style lang="scss" scoped>
.home-screen {
  .screen-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    .header-title {
      h2 {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
        color: #303133;
      }

      p {
        margin: 4px 0 0;
        font-size: 13px;
        color: #909399;
      }
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;

      .update-time {
        font-size: 12px;
        color: #909399;
      }
    }
  }

  .stat-row {
    margin-bottom: 8px;
  }

  .stat-card {
    display: flex;
    align-items: center;
    gap: 14px;
    background: #fff;
    border: 1px solid #ebeef5;
    border-radius: 8px;
    padding: 18px 20px;
    margin-bottom: 16px;

    .stat-icon {
      flex: none;
      width: 48px;
      height: 48px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
    }

    .stat-body {
      min-width: 0;
    }

    .stat-label {
      font-size: 13px;
      color: #909399;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 600;
      line-height: 1.25;
      color: #303133;
      font-variant-numeric: tabular-nums;
    }

    .stat-sub {
      font-size: 12px;
      color: #909399;

      &.is-failed {
        color: #e6a23c;
      }
    }
  }

  .chart-panel {
    background: #fff;
    border: 1px solid #ebeef5;
    border-radius: 8px;
    margin-bottom: 16px;

    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px;
      border-bottom: 1px solid #ebeef5;

      .panel-title {
        font-size: 15px;
        font-weight: 600;
        color: #303133;
      }

      .panel-total {
        font-size: 12px;
        color: #909399;
      }
    }

    .panel-body {
      position: relative;
      padding: 8px 8px 4px;
    }

    .chart {
      width: 100%;

      &.chart-donut {
        height: 260px;
      }

      &.chart-bar {
        height: 320px;
      }
    }

    .chart-empty {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      color: #909399;
      background: rgba(255, 255, 255, 0.6);
    }
  }
}

@media (max-width: 768px) {
  .home-screen {
    .screen-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }

    .stat-card {
      padding: 14px;

      .stat-icon {
        width: 40px;
        height: 40px;
        font-size: 20px;
      }

      .stat-value {
        font-size: 22px;
      }
    }
  }
}
</style>
