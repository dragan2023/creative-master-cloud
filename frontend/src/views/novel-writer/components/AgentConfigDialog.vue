<!--
  组件: AgentConfigDialog
  Agent配置弹窗
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="Agent配置"
    width="950px"
    destroy-on-close
    class="agent-config-dialog"
  >
    <AgentConfigPanel
      :concurrency="concurrency"
      @update:concurrency="$emit('update:concurrency', $event)"
      :agent-config-ids="agentConfigIds"
      @update:agent-config-ids="$emit('update:agentConfigIds', $event)"
      :agent-temps="agentTemps"
      @update:agent-temps="$emit('update:agentTemps', $event)"
      :model-configs="modelConfigs"
      :quick-apply-config-id="quickApplyConfigId"
      @quick-apply="$emit('quick-apply', $event)"
    />
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="$emit('update:visible', false)">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import AgentConfigPanel from './AgentConfigPanel.vue'

defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  concurrency: {
    type: Number,
    default: 3
  },
  agentConfigIds: {
    type: Object,
    default: () => ({})
  },
  agentTemps: {
    type: Object,
    default: () => ({})
  },
  modelConfigs: {
    type: Array,
    default: () => []
  },
  quickApplyConfigId: {
    type: [Number, String],
    default: null
  }
})

defineEmits(['update:visible', 'update:concurrency', 'update:agentConfigIds', 'update:agentTemps', 'quick-apply'])
</script>
