<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="逻辑问题详情"
    width="600px"
  >
    <div class="logic-issues-dialog">
      <div v-for="(issue, index) in issues" :key="index" class="issue-item">
        <div class="issue-header">
          <el-tag :type="issue.severity === 'high' ? 'danger' : issue.severity === 'medium' ? 'warning' : 'info'">
            {{ issue.type }}
          </el-tag>
          <span class="issue-unit">单元 {{ issue.unit_number }}</span>
        </div>
        <p class="issue-description">{{ issue.description }}</p>
      </div>
    </div>
    <template #footer>
      <el-button type="primary" @click="$emit('update:modelValue', false)">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  issues: { type: Array, default: () => [] }
})

defineEmits(['update:modelValue'])
</script>
