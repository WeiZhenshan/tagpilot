<template>
  <section>
    <el-button v-hasPermi="['taglibrary:semantic:edit']" size="small" type="primary" plain icon="el-icon-plus" @click="edit()">新增{{ title }}</el-button>
    <el-table v-loading="loading" :data="rows" size="small" empty-text="尚无记录，可先创建草稿再复核">
      <el-table-column v-for="field in fields.filter(f => !f.hidden)" :key="field.key" :prop="field.key" :label="field.label" min-width="120" show-overflow-tooltip />
      <el-table-column label="复核状态" width="100"><template slot-scope="s"><el-tag size="mini" :type="s.row.reviewStatus === 'REVIEWED' ? 'success' : 'info'">{{ s.row.reviewStatus === 'REVIEWED' ? '已复核' : '草稿' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="130"><template slot-scope="s">
        <el-button v-hasPermi="['taglibrary:semantic:edit']" type="text" size="small" @click="edit(s.row)">编辑</el-button>
        <el-button v-if="s.row.reviewStatus !== 'REVIEWED'" v-hasPermi="['taglibrary:semantic:review']" type="text" size="small" @click="review(s.row)">复核</el-button>
      </template></el-table-column>
    </el-table>
    <pagination v-if="total > pageSize" :total="total" :page.sync="page" :limit.sync="pageSize" @pagination="load" />
    <el-dialog :title="title + '草稿'" :visible.sync="visible" width="640px" append-to-body :close-on-click-modal="false">
      <el-alert title="保存修改后回到草稿状态，需重新复核才可发布。" type="info" :closable="false" />
      <el-form label-width="110px" class="record-form">
        <el-form-item v-for="field in fields.filter(f => !f.readonly)" :key="field.key" :label="field.label" :required="field.required">
          <el-select v-if="field.options" v-model="form[field.key]" style="width:100%"><el-option v-for="option in field.options" :key="option" :label="option" :value="option" /></el-select>
          <el-input-number v-else-if="field.number" v-model="form[field.key]" :controls="false" />
          <el-input v-else v-model="form[field.key]" :type="field.multiline ? 'textarea' : 'text'" :rows="3" :disabled="field.immutable && !!form[idKey]" />
        </el-form-item>
      </el-form>
      <span slot="footer"><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存草稿</el-button></span>
    </el-dialog>
  </section>
</template>
<script>
import { semanticList, semanticDetail, semanticCodeSource, saveSemantic, reviewSemantic } from '@/api/taglibrary/semantic'
export default {
  name: 'SemanticRecords',
  props: { resource: String, title: String, fields: Array, idKey: String, query: Object, defaults: Object, detailId: [Number, String] },
  data() { return { rows: [], loading: false, saving: false, visible: false, form: {}, page: 1, pageSize: 20, total: 0 } },
  watch: { query: { deep: true, handler() { this.page = 1; this.load() } }, detailId() { this.load() } },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true
      const id = this.detailId
      try {
        const result = id ? await semanticDetail(this.resource, id) : await semanticList(this.resource, { ...this.query, pageNum: this.page, pageSize: this.pageSize })
        let rows = result.rows || result.data || []
        if (this.resource === 'code-value' && rows.length) {
          const source = await semanticCodeSource(id)
          const definitions = new Map((source.data || []).map(item => [String(item.code), item]))
          rows = rows.map(row => { const origin = definitions.get(String(row.code)); return { ...row, codeDefinition: origin ? origin.codeDefinition : '来源已缺失，需重新核对', dimensionId: origin ? origin.dimensionId : null } })
        }
        if (id !== this.detailId) return
        this.rows = rows; this.total = result.total || rows.length
      } catch (error) { this.rows = []; this.total = 0; throw error } finally { this.loading = false }
    },
    edit(row) { this.form = { ...this.defaults, ...(row || {}) }; this.visible = true },
    async save() {
      if (this.fields.some(f => f.required && (this.form[f.key] === undefined || this.form[f.key] === null || this.form[f.key] === ''))) { this.$modal.msgError('请填写必填项'); return }
      for (const key of ['options', 'expectedCondition']) {
        if (this.form[key]) { try { JSON.parse(this.form[key]) } catch (_) { this.$modal.msgError('请填写合法 JSON'); return } }
      }
      this.saving = true
      const payload = { ...this.form }
      this.fields.filter(f => f.readonly).forEach(f => { delete payload[f.key] })
      try { await saveSemantic(this.resource, payload); this.visible = false; this.$modal.msgSuccess('草稿已保存'); await this.load(); this.$emit('changed') } finally { this.saving = false }
    },
    async review(row) {
      try {
        const { value } = await this.$prompt('请填写复核依据（文档或工单编号）', '确认业务复核', { inputValidator: v => !!(v && v.trim()) || '复核依据不能为空' })
        await reviewSemantic(this.resource, row[this.idKey], value, this.resource === 'code-value' ? row.code : undefined)
        this.$modal.msgSuccess('复核完成'); await this.load(); this.$emit('changed')
      } catch (error) { if (error !== 'cancel' && error !== 'close') this.$emit('review-error', error) }
    }
  }
}
</script>
<style scoped>.record-form { margin-top: 20px; }</style>
