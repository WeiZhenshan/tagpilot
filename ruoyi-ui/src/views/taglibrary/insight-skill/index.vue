<template>
  <div class="app-container skill-management" v-loading="loading">
    <header class="skill-header">
      <div><h2>洞察技能</h2><p>登记分析方法与参考资料，发布后由智能体按需调用。</p></div>
      <el-button v-hasPermi="['taglibrary:insight:edit']" type="primary" icon="el-icon-plus" aria-label="创建技能" :disabled="loading" @click="create">创建技能</el-button>
    </header>
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon /><el-button v-if="loadError" type="text" @click="load">重新加载</el-button>
    <template v-if="!active">
      <el-form :inline="true" class="skill-filters" @submit.native.prevent>
        <el-form-item label="搜索技能"><el-input v-model="keyword" clearable placeholder="名称或用途描述" prefix-icon="el-icon-search" /></el-form-item>
        <el-form-item label="分类"><el-select v-model="category" clearable placeholder="全部分类"><el-option v-for="(label, value) in categories" :key="value" :value="value" :label="label" /></el-select></el-form-item>
        <el-form-item label="状态"><el-select v-model="status" clearable placeholder="全部状态"><el-option label="草稿" value="draft" /><el-option label="已发布" value="published" /><el-option label="待发布修改" value="changed" /></el-select></el-form-item>
      </el-form>
      <el-table v-if="filtered.length" :data="filtered" class="skill-table">
        <el-table-column label="技能" min-width="220"><template slot-scope="scope"><button class="skill-link" @click="view(scope.row)">{{ scope.row.display_name }}</button><div class="skill-secondary">/{{ scope.row.name }}</div></template></el-table-column>
        <el-table-column prop="description" label="用途与触发场景" min-width="280" show-overflow-tooltip />
        <el-table-column label="分类" min-width="130"><template slot-scope="scope">{{ categories[scope.row.category] }}</template></el-table-column>
        <el-table-column label="状态 / 版本" min-width="160"><template slot-scope="scope"><el-tag size="small" :type="scope.row.published ? 'success' : 'info'">{{ stateLabel(scope.row) }}</el-tag><div class="skill-secondary">{{ scope.row.published ? scope.row.published.version : scope.row.version }}</div></template></el-table-column>
        <el-table-column label="操作" width="150"><template slot-scope="scope"><el-button type="text" @click="view(scope.row)">查看</el-button><el-button v-hasPermi="['taglibrary:insight:edit']" type="text" @click="edit(scope.row)">编辑</el-button></template></el-table-column>
      </el-table>
      <div v-else-if="!loading && !loadError" class="skill-empty"><h3>{{ rows.length ? '没有匹配的技能' : '还没有登记技能' }}</h3><p>{{ rows.length ? '调整搜索词或筛选条件后重试。' : '先登记技能的用途和指令，再发布到智能体。基础事实、诊断分析、行动决策与通用图表均可在这里管理。' }}</p><el-button v-if="!rows.length" v-hasPermi="['taglibrary:insight:edit']" @click="create">创建第一个技能</el-button></div>
    </template>
    <section v-else class="skill-detail" :class="{ 'skill-reading': !editing }">
      <header class="skill-detail-heading"><el-button icon="el-icon-back" :disabled="saving" @click="back">返回列表</el-button><div><h3>{{ editing ? (form.row_version ? '编辑技能' : '创建技能') : form.display_name }}</h3><p>{{ editing ? '编辑草稿后保存，发布前检查完整内容。' : '查看草稿与已发布版本，核对智能体实际使用的内容。' }}</p></div></header>
      <div v-if="!editing" class="skill-version-switch"><el-radio-group v-model="source" size="small" @change="switchSource"><el-radio-button label="draft">当前草稿</el-radio-button><el-radio-button v-if="active.published" label="published">已发布 {{ active.published.version }}</el-radio-button></el-radio-group><el-button v-hasPermi="['taglibrary:insight:edit']" size="small" @click="edit(active)">编辑草稿</el-button></div>
      <el-tabs v-model="tab">
        <el-tab-pane label="基本信息" name="basic">
          <el-form ref="form" :model="form" label-position="top" :disabled="!editing || saving" class="skill-form">
            <div class="skill-form-grid">
              <el-form-item label="展示名称" required><el-input v-model="form.display_name" maxlength="100" placeholder="业务可读的技能名称" /></el-form-item>
              <el-form-item label="技能名称（name）" required><el-input v-model="form.name" :disabled="!!form.row_version" maxlength="64" placeholder="例如 customer-profile" /><p class="skill-help">小写字母、数字和连接符，发布后通过 /名称 调用。</p></el-form-item>
              <el-form-item label="登记分类"><el-select v-model="form.category"><el-option v-for="(label, value) in categories" :key="value" :label="label" :value="value" /></el-select></el-form-item>
              <el-form-item label="版本号" required><el-input v-model="form.version" placeholder="1.0.0" /><p class="skill-help">修改已发布内容后使用新的版本号。</p></el-form-item>
            </div>
            <el-form-item label="用途与触发场景（description）" required><el-input v-model="form.description" type="textarea" :rows="3" maxlength="1024" show-word-limit placeholder="说明这个技能能做什么，以及什么情况下应调用它。智能体会依据此描述选择技能。" /></el-form-item>
            <el-form-item label="调用参数提示（argument-hint）"><el-input v-model="form.argument_hint" maxlength="200" placeholder="例如 [分析目标] [补充要求]" /></el-form-item>
            <el-form-item label="调用方式"><template v-if="editing"><el-checkbox v-model="form.user_invocable">允许用户通过 / 调用</el-checkbox><el-checkbox v-model="form.disable_model_invocation">仅手动调用，禁止智能体自动选择</el-checkbox></template><div v-else class="skill-reading-options"><span>{{ form.user_invocable ? '允许用户通过 / 调用' : '不允许用户通过 / 调用' }}</span><span>{{ form.disable_model_invocation ? '仅手动调用，禁止智能体自动选择' : '允许智能体按用途自动调用' }}</span></div></el-form-item>
            <el-form-item label="允许的工具（allowed-tools）"><el-checkbox-group v-if="editing" v-model="form.allowed_tools"><el-checkbox label="Read">读取技能参考资料</el-checkbox><el-checkbox label="Skill">调用关联技能</el-checkbox></el-checkbox-group><div v-else class="skill-reading-options"><span>{{ form.allowed_tools.includes('Read') ? '可读取技能参考资料' : '未声明读取参考资料' }}</span><span>{{ form.allowed_tools.includes('Skill') ? '可调用关联技能' : '未声明调用关联技能' }}</span></div><p class="skill-help">本阶段开放参考资料读取与技能组合。脚本可登记为资源，暂不执行；技能声明不会扩大运行权限。</p></el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="技能指令" name="instructions"><p class="skill-help">用 Markdown 编写分析步骤、证据要求、输出格式与适用边界。需要图表时可指示智能体调用已发布的图表技能。</p><el-input v-model="form.instructions" type="textarea" :rows="18" :readonly="!editing" :disabled="saving" maxlength="60000" placeholder="登记实际技能指令，不会自动生成或预置技能内容。" label="技能指令" /></el-tab-pane>
        <el-tab-pane label="支持资源" name="resources">
          <p class="skill-help">按需读取的 references/、scripts/ 和 assets/ 文件。当前支持文本资源；此处的脚本不会自动执行。</p>
          <div v-for="(resource, index) in form.resources" :key="index" class="skill-resource"><div class="skill-resource-heading"><el-input v-model="resource.path" :readonly="!editing" :disabled="saving" placeholder="references/analysis-guide.md" :label="'资源' + (index + 1) + '路径'" /><el-button v-if="editing" :disabled="saving" type="text" @click="form.resources.splice(index, 1)">移除</el-button></div><el-input v-model="resource.content" type="textarea" :rows="6" :readonly="!editing" :disabled="saving" :label="'资源' + (index + 1) + '内容'" placeholder="文件内容" /></div>
          <el-button v-if="editing" :disabled="saving || form.resources.length >= 30" icon="el-icon-plus" aria-label="添加文本资源" @click="form.resources.push({ path: '', content: '' })">添加文本资源</el-button><p v-if="!editing && !form.resources.length" class="skill-help">没有支持资源。</p>
        </el-tab-pane>
        <el-tab-pane label="SKILL.md 预览" name="preview"><p class="skill-help">发布后加载的标准技能文件。展示名称、分类与版本是平台登记信息，不写入 Skill frontmatter。</p><pre class="skill-source">{{ markdown }}</pre><el-button @click="download">下载 SKILL.md</el-button></el-tab-pane>
      </el-tabs>
      <p v-if="error" role="alert" class="skill-error">{{ error }}</p>
      <footer class="skill-actions">
        <span class="skill-help">{{ active.published ? '已发布 v' + active.published.version + '；编辑草稿不会影响正在使用的版本。' : '尚未发布，智能体暂不可调用。' }}</span>
        <el-button v-if="editing" :disabled="saving" @click="back">取消</el-button><el-button v-if="editing" type="primary" :loading="saving" @click="save">保存草稿</el-button>
        <template v-else><el-button v-if="active.published" v-hasPermi="['taglibrary:insight:publish']" :disabled="saving" @click="retire">下线技能</el-button><el-button v-hasPermi="['taglibrary:insight:publish']" type="primary" :disabled="saving" @click="openPublish">检查并发布</el-button></template>
      </footer>
    </section>
    <el-dialog title="发布技能" :visible.sync="publishOpen" width="560px" custom-class="skill-publish-dialog" :close-on-click-modal="false">
      <template v-if="active"><p>将 {{ active.display_name }} v{{ active.version }} 发布到智能体。</p><ul class="skill-publish-checks"><li>用途描述和技能指令完整</li><li>名称与资源路径符合技能文件规范</li><li>{{ active.user_invocable ? '出现在 / 调用列表' : '仅供智能体自动选择' }}</li><li>{{ active.disable_model_invocation ? '不允许智能体自动调用' : '允许智能体按用途自动调用' }}</li></ul><p class="skill-help">运行时携带当前客群条件与有效人数，不改变圈选方案。仅允许读取技能资源、调用已发布的关联技能。</p><p v-if="error" role="alert" class="skill-error">{{ error }}</p></template>
      <span slot="footer"><el-button :disabled="saving" @click="publishOpen = false">取消</el-button><el-button type="primary" :loading="saving" @click="publish">确认发布</el-button></span>
    </el-dialog>
  </div>
</template>

<script>
import { listAgentSkills, saveAgentSkill, publishAgentSkill, retireAgentSkill } from '@/api/taglibrary/agentSkill'
const empty = () => ({ name: '', display_name: '', category: 'general', description: '', version: '1.0.0', argument_hint: '', user_invocable: true, disable_model_invocation: false, allowed_tools: ['Read', 'Skill'], instructions: '', resources: [], row_version: 0 })
const copy = value => JSON.parse(JSON.stringify(value))
export default {
  name: 'InsightSkillManagement',
  data() { return { rows: [], loading: false, saving: false, loadError: '', error: '', keyword: '', category: '', status: '', active: null, form: empty(), editing: false, source: 'draft', tab: 'basic', publishOpen: false, categories: { fact: '基础事实', diagnosis: '诊断分析', decision: '行动决策', chart: '通用数据图表', general: '通用技能' } } },
  computed: {
    filtered() { return this.rows.filter(row => (!this.keyword.trim() || (row.name + row.display_name + row.description).toLowerCase().includes(this.keyword.trim().toLowerCase())) && (!this.category || row.category === this.category) && (!this.status || this.status === 'draft' && !row.published || this.status === 'published' && row.published || this.status === 'changed' && this.changed(row))) },
    markdown() { const f = this.form; return '---\nname: ' + JSON.stringify(f.name) + '\ndescription: ' + JSON.stringify(f.description) + '\nargument-hint: ' + JSON.stringify(f.argument_hint) + '\nuser-invocable: ' + f.user_invocable + '\ndisable-model-invocation: ' + f.disable_model_invocation + '\nallowed-tools: ' + JSON.stringify(f.allowed_tools) + '\n---\n\n' + f.instructions + '\n' }
  },
  created() { this.load() },
  methods: {
    async load() { this.loading = true; this.loadError = ''; try { const r = await listAgentSkills(); this.rows = r.data || [] } catch (e) { this.loadError = e.message || '技能列表加载失败，请重试。' } finally { this.loading = false } },
    changed(row) { if (!row.published) return false; return ['name', 'display_name', 'category', 'description', 'version', 'argument_hint', 'user_invocable', 'disable_model_invocation', 'allowed_tools', 'instructions', 'resources'].some(key => JSON.stringify(row[key]) !== JSON.stringify(row.published[key])) },
    stateLabel(row) { return this.changed(row) ? '待发布修改' : row.published ? '已发布' : '草稿' },
    create() { this.active = empty(); this.form = empty(); this.editing = true; this.error = ''; this.tab = 'basic' },
    view(row) { this.active = row; this.form = copy(row); this.editing = false; this.source = 'draft'; this.error = ''; this.tab = 'basic' },
    edit(row) { this.view(row); this.editing = true },
    switchSource() { this.form = copy(this.source === 'published' ? this.active.published : this.active) },
    async back() { if (this.editing) { try { await this.$confirm('离开后未保存的编辑会丢失。', '离开技能编辑', { confirmButtonText: '离开', cancelButtonText: '继续编辑' }) } catch (_) { return } } this.active = null; this.error = '' },
    validate(publish) { const f = this.form; if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(f.name) || f.name.length > 64) throw new Error('技能名称须为小写字母、数字和连接符。'); if (!f.display_name.trim()) throw new Error('请填写展示名称。'); if (!/^\d+\.\d+\.\d+$/.test(f.version)) throw new Error('版本号须为三段数字，例如 1.0.0。'); if (publish && (!f.description.trim() || !f.instructions.trim())) throw new Error('发布前请填写用途描述与技能指令。'); if (publish && !f.user_invocable && f.disable_model_invocation) throw new Error('至少开启一种调用方式。'); const paths = new Set(); f.resources.forEach(r => { if (!/^(references|scripts|assets)\/[A-Za-z0-9_./-]+$/.test(r.path) || r.path.includes('..') || r.path.includes('//') || r.path.endsWith('/') || paths.has(r.path) || !r.content.trim()) throw new Error('请检查资源路径、重复文件或空内容。'); paths.add(r.path) }) },
    async refreshActive(name) { await this.load(); const row = this.rows.find(r => r.name === name); if (!row || this.loadError) { this.active = null; return } this.view(row) },
    async save() { this.error = ''; try { this.validate(false); this.saving = true; const name = this.form.name; await saveAgentSkill(this.form); this.editing = false; await this.refreshActive(name); this.$modal.msgSuccess('草稿已保存') } catch (e) { this.error = e.message || '保存失败，请重试。' } finally { this.saving = false } },
    openPublish() { this.form = copy(this.active); this.source = 'draft'; this.error = ''; try { this.validate(true); if (this.active.published && this.active.published.version === this.active.version) throw new Error('发布修改前请编辑草稿并使用新版本号。'); this.publishOpen = true } catch (e) { this.error = e.message } },
    async publish() { this.error = ''; this.saving = true; try { const name = this.active.name; await publishAgentSkill(name, this.active.row_version); this.publishOpen = false; await this.refreshActive(name); this.$modal.msgSuccess('技能已发布，可由智能体调用') } catch (e) { this.error = e.message || '发布失败，请重试。' } finally { this.saving = false } },
    async retire() { try { await this.$confirm('下线后，新运行将不再加载该技能。', '下线技能', { confirmButtonText: '下线', cancelButtonText: '取消' }) } catch (_) { return } this.saving = true; try { const name = this.active.name; await retireAgentSkill(name, this.active.row_version); await this.refreshActive(name); this.$modal.msgSuccess('技能已下线') } catch (e) { this.error = e.message || '下线失败，请重试。' } finally { this.saving = false } },
    download() { const url = URL.createObjectURL(new Blob([this.markdown], { type: 'text/markdown;charset=utf-8' })); const a = document.createElement('a'); a.href = url; a.download = 'SKILL.md'; a.click(); URL.revokeObjectURL(url) }
  }
}
</script>

<style scoped>
.skill-management { color: #303133; max-width: 1440px; margin: auto; }
.skill-header, .skill-detail-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.skill-header h2 { font-size: 22px; font-weight: 600; margin: 0 0 8px; }
.skill-header p, .skill-detail-heading p { color: #606266; font-size: 14px; line-height: 1.7; margin: 0; }
.skill-filters { margin: 20px 0 4px; }
.skill-link { border: 0; padding: 4px 0; background: transparent; color: #1769b0; cursor: pointer; text-align: left; font: inherit; }
.skill-secondary, .skill-help { color: #606266; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.skill-help { margin: 8px 0 16px; }
.skill-empty { text-align: center; padding: 72px 20px; max-width: 620px; margin: auto; }
.skill-empty h3 { font-size: 18px; font-weight: 500; }
.skill-empty p { color: #606266; line-height: 1.8; margin-bottom: 24px; }
.skill-detail-heading { justify-content: flex-start; }
.skill-detail-heading h3 { font-size: 18px; margin: 0 0 6px; }
.skill-version-switch { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 20px; }
.skill-form { max-width: 960px; }
.skill-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
.skill-form .el-select { width: 100%; }
.skill-resource { padding: 16px 0; border-bottom: 1px solid #e7e9ed; margin-bottom: 16px; }
.skill-resource-heading { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.skill-source { margin: 16px 0; padding: 20px; white-space: pre-wrap; overflow-wrap: anywhere; background: #f6f7f9; color: #303133; font-size: 13px; line-height: 1.8; max-height: 55vh; overflow: auto; }
.skill-actions { display: flex; align-items: center; justify-content: flex-end; gap: 12px; border-top: 1px solid #e7e9ed; padding: 20px 0; margin-top: 24px; flex-wrap: wrap; }
.skill-actions .skill-help { margin: 0 auto 0 0; }
.skill-actions .el-button + .el-button { margin-left: 0; }
.skill-reading ::v-deep .el-input.is-disabled .el-input__inner, .skill-reading ::v-deep .el-textarea.is-disabled .el-textarea__inner { color: #303133; -webkit-text-fill-color: #303133; background: #f6f7f9; }
.skill-reading-options { display: flex; flex-wrap: wrap; gap: 8px 24px; color: #303133; font-size: 14px; line-height: 1.8; }
.skill-error { color: #b42318; font-size: 14px; }
.skill-publish-checks { padding-left: 20px; line-height: 2; }
.skill-management ::v-deep .el-button--primary { background: #1769b0; border-color: #1769b0; }
.skill-management ::v-deep .el-button--text { color: #1769b0; }
.skill-management ::v-deep .el-textarea__inner { line-height: 1.8; }
.skill-management ::v-deep .el-input__inner::placeholder, .skill-management ::v-deep .el-textarea__inner::placeholder { color: #75777d; }
.skill-management ::v-deep .el-dialog { max-width: calc(100vw - 32px); }
.skill-management button:focus-visible { outline: 2px solid #1769b0; outline-offset: 3px; }
@media (max-width: 760px) {
  .skill-header { align-items: flex-start; flex-wrap: wrap; gap: 16px; }
  .skill-form-grid { grid-template-columns: minmax(0, 1fr); }
  .skill-detail-heading { align-items: flex-start; gap: 12px; }
  .skill-detail-heading p { display: none; }
  .skill-version-switch { flex-wrap: wrap; }
  .skill-table { overflow-x: auto; }
  .skill-filters ::v-deep .el-form-item { display: block; margin-right: 0; }
  .skill-filters ::v-deep .el-form-item__content { max-width: 100%; }
  .skill-form ::v-deep .el-checkbox { display: block; margin: 0 0 12px; white-space: normal; }
}
</style>
