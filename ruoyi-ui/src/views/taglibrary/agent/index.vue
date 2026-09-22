<template>
  <div class="agent-workbench-shell">
    <iframe
      ref="frame"
      :key="iframeSrc"
      @load="sendTheme"
      class="agent-workbench-frame"
      :src="iframeSrc"
      title="智能体工作台"
      allow="clipboard-read; clipboard-write"
    />
  </div>
</template>

<script>
import { AGENT_WORKBENCH_BACK_MESSAGE, AGENT_WORKBENCH_DEFAULT_FROM, AGENT_WORKBENCH_LOGOUT_MESSAGE, parseAgentBackPath } from '@/utils/agentWorkbench'

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
  watch: {
    '$store.state.settings.theme'() { this.sendTheme() },
    '$store.state.user.id'() {
      if (this.$refs.frame) this.$refs.frame.contentWindow.postMessage({ type: 'tagpilot-agent:identity-changed' }, window.location.origin)
    }
  },
  created() {
    window.addEventListener('message', this.handleAgentMessage)
  },
  beforeDestroy() {
    window.removeEventListener('message', this.handleAgentMessage)
  },
  methods: {
    sendTheme() {
      if (this.$refs.frame) this.$refs.frame.contentWindow.postMessage({ type: 'tagpilot-agent:theme', color: this.$store.state.settings.theme }, window.location.origin)
    },
    handleAgentMessage(event) {
      if (event.origin !== window.location.origin || !this.$refs.frame || event.source !== this.$refs.frame.contentWindow) return
      const data = event.data || {}
      if (data.type === 'tagpilot-agent:ready') { this.sendTheme(); return }
      if (data.type === AGENT_WORKBENCH_LOGOUT_MESSAGE) {
        const goLogin = () => { location.href = '/login' }
        this.$store.dispatch('LogOut').then(() => {
          goLogin()
        }).catch(() => this.$store.dispatch('FedLogOut').then(goLogin))
        return
      }
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
  background: #ffffff;
}
.agent-workbench-frame {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: #ffffff;
}
</style>
