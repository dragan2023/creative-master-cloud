<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="从指定单元重新生成"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="start-unit-dialog-content">
      <p class="start-unit-tip">
        选择从哪个单元开始重新生成。该单元及之后的所有单元概述将被重新生成，之前的单元概述将保留。
      </p>
      <el-form-item label="起始单元编号">
        <el-input-number
          :model-value="startFromUnit"
          @update:model-value="$emit('update:startFromUnit', $event)"
          :min="1"
          :max="maxUnit"
          :step="1"
        />
      </el-form-item>
      <p class="start-unit-warning">
        <el-icon><WarningFilled /></el-icon>
        注意：从第 {{ startFromUnit }} 单元开始的所有内容将被覆盖
      </p>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="$emit('generate')" :loading="loading">
        开始生成
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { WarningFilled } from '@element-plus/icons-vue'

defineProps({
  modelValue: { type: Boolean, default: false },
  startFromUnit: { type: Number, default: 1 },
  maxUnit: { type: Number, default: 50 },
  loading: { type: Boolean, default: false }
})

defineEmits(['update:modelValue', 'update:startFromUnit', 'generate'])
</script>
