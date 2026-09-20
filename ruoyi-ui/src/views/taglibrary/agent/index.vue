<template>
  <div class="agent-workbench-shell">
    <iframe
      :key="iframeSrc"
      class="agent-workbench-frame"
      :src="iframeSrc"
      title="智能体工作台"
      allow="clipboard-read; clipboard-write"
    />
  </div>
</template>

<script>
import { AGENT_WORKBENCH_BACK_MESSAGE, AGENT_WORKBENCH_DEFAULT_FROM, parseAgentBackPath } from '@/utils/agentWorkbench'

export default {
  name: 'AgentWorkbench',
  computed: {
    iframeSrc() {
      const query = this.$route.query || {}
      const params = new URLSearchParams()
      if (query.libraryId) params.set('libraryId', String(query.libraryId))
      if (query.libraryName) params.set('libraryName', String(query.libraryName))
      params.set('from', query.from || AGENT_WORKBENCH_DEFAULT_FROM)
      const qs = params.toString()
      return '/agent-ui/' + (qs ? '?' + qs : '')
    }
  },
  created() {
    window.addEventListener('message', this.handleAgentMessage)
  },
  beforeDestroy() {
    window.removeEventListener('message', this.handleAgentMessage)
  },
  methods: {
    handleAgentMessage(event) {
      if (event.origin !== window.location.origin) return
      const data = event.data || {}
      if (data.type !== AGENT_WORKBENCH_BACK_MESSAGE) return
      this.$router.push(parseAgentBackPath(data))
    }
  }
}
</script>

<style scoped>
.agent-workbench-shell {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: #f7f5f2;
}
.agent-workbench-frame {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: #f7f5f2;
}
</style>
