<template>
  <div ref="chart" class="insight-chart" />
</template>

<script>
import * as echarts from 'echarts'

/**
 * 单张 InsightChartSpec 的 ECharts 渲染器。
 * 只吃 chartSpecAdapter 生成的 option，不做任何数据加工。
 */
export default {
  name: 'InsightChart',
  props: {
    option: { type: Object, required: true }
  },
  data() {
    return { chart: null }
  },
  watch: {
    option: {
      deep: true,
      handler() { this.render() }
    }
  },
  mounted() {
    this.render()
    window.addEventListener('resize', this.resize)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resize)
    if (this.chart) {
      this.chart.dispose()
      this.chart = null
    }
  },
  methods: {
    render() {
      if (!this.$refs.chart) return
      if (!this.chart) {
        this.chart = echarts.init(this.$refs.chart)
      }
      this.chart.setOption(this.option, true)
      this.chart.resize()
    },
    resize() {
      if (this.chart) this.chart.resize()
    }
  }
}
</script>

<style scoped>
.insight-chart {
  width: 100%;
  height: 320px;
}
</style>
