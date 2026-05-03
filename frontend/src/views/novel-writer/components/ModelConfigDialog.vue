<!--
  组件: ModelConfigDialog
  LLM模型配置管理弹窗
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="LLM模型配置管理"
    width="90%"
    top="5vh"
    destroy-on-close
  >
    <ModelConfigPanel />
    <template #footer>
      <el-button type="primary" @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import ModelConfigPanel from '../ModelConfigPanel.vue'

defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:visible'])
</script>
