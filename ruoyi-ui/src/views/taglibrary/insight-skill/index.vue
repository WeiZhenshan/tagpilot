<template>
  <div class="app-container insight-management">
    <el-form :inline="true" @submit.native.prevent="load">
      <el-form-item label="标签库"><el-select v-model="libraryId" filterable placeholder="请选择标签库" @change="load"><el-option v-for="item in libraries" :key="item.libraryId" :label="item.libraryName" :value="item.libraryId" /></el-select></el-form-item>
      <el-button v-hasPermi="['taglibrary:insight:edit']" :disabled="!libraryId" @click="editing = !editing">登记草稿版本</el-button>
    </el-form>
    <p v-if="error" role="alert">{{ error }}</p>
    <p>技能包经代码评审，指标仅绑定已发布标签。草稿复核、评测门禁和发布相互独立；尚未完成业务复核的权重与适当性不得发布。</p>
    <el-tabs v-model="tab">
      <el-tab-pane label="技能与版本" name="skills">
        <el-table v-loading="loading" :data="skills">
          <el-table-column prop="manifest.name" label="技能" min-width="160" /><el-table-column prop="manifest.layer" label="层级" width="65" />
          <el-table-column prop="manifest.question" label="回答的问题" min-width="240" />
          <el-table-column label="所需指标" min-width="220"><template slot-scope="scope">{{ scope.row.manifest.metrics.join('、') }}</template></el-table-column>
        </el-table>
        <h3>不可变版本记录</h3>
        <el-table :data="versions">
          <el-table-column prop="skill_id" label="技能" min-width="180" /><el-table-column prop="version" label="登记版本" width="110" /><el-table-column prop="status" label="状态" width="100" />
          <el-table-column label="指标绑定" min-width="220"><template slot-scope="scope">{{ completeness(scope.row) }}</template></el-table-column>
          <el-table-column label="门禁" width="110"><template slot-scope="scope">{{ gate(scope.row) }}</template></el-table-column>
          <el-table-column label="操作" min-width="200"><template slot-scope="scope">
            <el-button type="text" @click="trial(scope.row)">合成沙盒试跑</el-button>
            <el-button v-if="scope.row.status === 'DRAFT'" v-hasPermi="['taglibrary:insight:review']" type="text" @click="review(scope.row)">复核与门禁</el-button>
            <el-button v-if="['REVIEWED', 'RETIRED'].includes(scope.row.status)" v-hasPermi="['taglibrary:insight:publish']" type="text" @click="publish(scope.row)">{{ scope.row.status === 'RETIRED' ? '回滚到此版本' : '发布' }}</el-button>
            <el-button v-if="scope.row.status === 'PUBLISHED'" v-hasPermi="['taglibrary:insight:publish']" type="text" @click="retire(scope.row)">下线</el-button>
          </template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="运行审计" name="audit"><p>最近 {{ audit.length }} 次运行，失败 {{ audit.filter(r => r.status === 'FAILED').length }} 次；平均耗时 {{ audit.length ? Math.round(audit.reduce((n, r) => n + Number(r.elapsed_ms), 0) / audit.length) : 0 }} ms。</p><el-table :data="audit"><el-table-column prop="run_id" label="运行" min-width="250" /><el-table-column prop="revision" label="方案版本" /><el-table-column prop="status" label="状态" /><el-table-column prop="elapsed_ms" label="耗时(ms)" /><el-table-column prop="rating" label="反馈评分" /><el-table-column prop="comment_text" label="反馈" min-width="180" /><el-table-column prop="create_time" label="时间" min-width="170" /></el-table><p>仅展示当前账号的运行记录；结果加密保存，客户明细不进入洞察库。</p></el-tab-pane>
    </el-tabs>
    <section v-if="editing" class="insight-draft"><h3>登记草稿配置</h3><p>按指标名填写标签 ID、单位、数据日期、绑定版本、基准定义和适当性。不得填写表名、列名或 SQL；当前仅支持同源客户宽表。</p><el-input v-model="draft" type="textarea" :rows="16" aria-label="洞察草稿JSON" /><el-button type="primary" @click="save">保存草稿</el-button></section>
    <el-dialog title="固定合成客群沙盒" :visible.sync="trialOpen" width="min(760px, 92vw)"><p>{{ trialBoundary }}</p><p>此处未查询真实客户，数值来自包内固定聚合参考；不证明此登记版本的来源、口径或实际SQL正确。</p><el-table :data="trialFacts"><el-table-column prop="label" label="事实" /><el-table-column prop="value" label="值" /><el-table-column prop="unit" label="单位" /><el-table-column prop="status" label="状态" /></el-table></el-dialog>
    <p>试运行入口：在智能体工作台选择已核验客群并统计人数后运行技能；当前草稿不允许绕过发布门禁运行真实客群。</p>
  </div>
</template>
<script>
import { listLibrary } from '@/api/taglibrary/library'
import { insightCatalog, insightAudit, saveInsightVersion, reviewInsightVersion, publishInsightVersion, retireInsight, trialInsight } from '@/api/taglibrary/insight'
export default {
  name: 'InsightSkill',
  data() { return { libraryId: undefined, libraries: [], skills: [], versions: [], audit: [], loading: false, error: '', tab: 'skills', editing: false, trialOpen: false, trialFacts: [], trialBoundary: '', draft: JSON.stringify({ skill_id: 'asset_structure_profile', version: '0.1.0', binding_version: '0.1.0', data_as_of: '', benchmark_version: '0.1.0', benchmark_definition: '', bindings: [], suitability: {} }, null, 2) } },
  created() { listLibrary({ pageNum: 1, pageSize: 1000 }).then(r => { this.libraries = r.rows }) },
  methods: {
    async load() { if (!this.libraryId) return; this.loading = true; this.error = ''; try { const r = await insightCatalog(this.libraryId); this.skills = r.data.skills; this.versions = r.data.versions; this.audit = (await insightAudit(this.libraryId)).data } catch (e) { this.error = e.message || '读取失败，请重试' } finally { this.loading = false } },
    completeness(row) { try { const d = JSON.parse(row.definition_json); const m = this.skills.find(s => s.manifest.id === row.skill_id).manifest; const bound = new Set(d.bindings.map(b => `${b.metric}:${b.category || ''}`)); const required = m.metrics.filter(k => k !== 'suitability').flatMap(k => k === 'asset_holder' ? ['asset_holder:liquid', 'asset_holder:fixed', 'asset_holder:investment'] : k === 'product_holding' ? [] : [`${k}:`]); const missing = required.filter(k => !bound.has(k)); if (m.metrics.includes('product_holding') && !['wealth', 'fund', 'insurance'].some(c => bound.has(`product_holding:${c}`))) missing.push('product_holding:至少一个品类'); const suitability = row.skill_id === 'product_holding_gap' && (!d.suitability || !Object.keys(d.suitability).length) ? '；适当性待配置，机会判定不可用' : ''; return `${bound.size} 个已绑定${missing.length ? '，待绑定：' + missing.join('、') : '，核心绑定齐全，仍需复核'}${suitability}` } catch (_) { return '绑定配置待核验' } },
    gate(row) { try { return JSON.parse(row.evaluation_json).passed ? '合成门禁通过' : '未通过' } catch (_) { return '待评测' } },
    async trial(row) { try { const r = await trialInsight(this.libraryId, row.skill_id, row.version); this.trialBoundary = r.data.boundary; this.trialFacts = r.data.report.results[0].facts; this.trialOpen = true } catch (e) { this.error = e.message || '试跑失败' } },
    async save() { try { await saveInsightVersion(this.libraryId, JSON.parse(this.draft)); this.editing = false; this.$modal.msgSuccess('草稿已登记'); await this.load() } catch (e) { this.error = e.message || '草稿格式非法' } },
    async review(row) { await this.$modal.confirm('请确认指标业务口径、数据日期、适当性与评分假设已复核。确定后执行固定合成门禁。'); await reviewInsightVersion(this.libraryId, row.skill_id, row.version); await this.load() },
    async publish(row) { await this.$modal.confirm('发布后此版本供客群洞察使用，并下线当前版本。确认执行？'); await publishInsightVersion(this.libraryId, row.skill_id, row.version); await this.load() },
    async retire(row) { await this.$modal.confirm('确认下线此技能？已保存结果保留审计，用户侧停止读取此版本报告和运行。'); await retireInsight(this.libraryId, row.skill_id); await this.load() }
  }
}
</script>
<style scoped>
.insight-management h3 { font-size: 15px; margin-top: 24px; }
.insight-management p { color: #606266; font-size: 13px; line-height: 1.7; }
.insight-draft { margin: 24px 0; max-width: 900px; }
.insight-draft .el-button { margin-top: 12px; }
</style>
