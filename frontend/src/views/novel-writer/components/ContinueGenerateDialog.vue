<!--
  继续生成对话框组件
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="继续生成"
    width="400px"
    destroy-on-close
  >
    <div class="continue-dialog-content">
      <p class="continue-hint">
        当前已完成
        <strong>{{ completedUnits }}</strong>
        个单元。
      </p>
      <el-form label-width="100px">
        <el-form-item label="生成数量">
          <el-input-number
            :model-value="unitCount"
            @update:model-value="$emit('update:unitCount', $event)"
            :min="1"
            :max="10"
            :step="1"
            style="width: 150px"
          />
          <span class="input-hint">个单元</span>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="$emit('confirm')">开始生成</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  completedUnits: {
    type: Number,
    default: 0
  },
  unitCount: {
    type: Number,
    default: 1
  }
})

defineEmits(['update:visible', 'update:unitCount', 'confirm'])
</script>

<style lang="scss" scoped>
.continue-dialog-content {
  .continue-hint {
    margin-bottom: 16px;
    font-size: 14px;
    color: #606266;
  }

  .input-hint {
    font-size: 12px;
    color: #909399;
    margin-left: 8px;
  }
}
</style>
