<!--
  继续生成对话框组件
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="继续生成"
    width="450px"
    destroy-on-close
  >
    <div class="continue-dialog-content">
      <p class="continue-hint">
        当前已完成
        <strong>{{ completedUnits }}</strong>
        个单元，项目总计
        <strong>{{ totalUnits }}</strong>
        个单元。
      </p>
      
      <el-alert
        v-if="maxAllowedUnits === 0"
        type="success"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        所有章节已生成完成！
      </el-alert>
      
      <el-form v-else label-width="100px">
        <el-form-item label="生成数量">
          <el-input-number
            :model-value="unitCount"
            @update:model-value="handleUnitCountChange"
            :min="1"
            :max="maxAllowedUnits"
            :step="1"
            style="width: 150px"
          />
          <span class="input-hint">个单元（最多{{ maxAllowedUnits }}个）</span>
        </el-form-item>
        <el-form-item>
          <el-alert
            v-if="unitCount > maxAllowedUnits"
            type="warning"
            :closable="false"
            show-icon
          >
            生成数量不能超过剩余单元数
          </el-alert>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button 
        type="primary" 
        @click="handleConfirm"
        :disabled="maxAllowedUnits === 0 || unitCount < 1 || unitCount > maxAllowedUnits"
      >
        开始生成
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  completedUnits: {
    type: Number,
    default: 0
  },
  totalUnits: {
    type: Number,
    default: 0
  },
  unitCount: {
    type: Number,
    default: 1
  }
})

const emit = defineEmits(['update:visible', 'update:unitCount', 'confirm'])

// 计算剩余可用单元数
const maxAllowedUnits = computed(() => {
  const remaining = props.totalUnits - props.completedUnits
  // 如果已经没有剩余单元，返回0
  return Math.max(0, remaining)
})

// 处理输入变化
function handleUnitCountChange(value) {
  console.log('[继续生成] 输入变化:', { value, type: typeof value })
  
  // 确保是正整数
  const intValue = Math.floor(Number(value))
  console.log('[继续生成] 转换后:', { intValue, isNaN: isNaN(intValue) })
  
  if (isNaN(intValue) || intValue < 1) {
    console.log('[继续生成] 值无效，设置为1')
    emit('update:unitCount', 1)
    return
  }
  
  // 不能超过最大允许值
  if (intValue > maxAllowedUnits.value) {
    console.log('[继续生成] 超过最大值，设置为:', maxAllowedUnits.value)
    ElMessage.warning(`最多只能生成 ${maxAllowedUnits.value} 个单元`)
    emit('update:unitCount', maxAllowedUnits.value)
    return
  }
  
  console.log('[继续生成] 更新为:', intValue)
  emit('update:unitCount', intValue)
}

// 确认生成
function handleConfirm() {
  console.log('[继续生成] 验证:', {
    unitCount: props.unitCount,
    unitCountType: typeof props.unitCount,
    maxAllowedUnits: maxAllowedUnits.value,
    maxAllowedUnitsType: typeof maxAllowedUnits.value,
    totalUnits: props.totalUnits,
    completedUnits: props.completedUnits,
    comparison: props.unitCount > maxAllowedUnits.value
  })
  
  if (maxAllowedUnits.value === 0) {
    ElMessage.warning('所有章节已生成完成，无需继续生成')
    return
  }
  
  // 确保类型正确
  const unitCountNum = Number(props.unitCount)
  if (isNaN(unitCountNum) || unitCountNum < 1 || unitCountNum > maxAllowedUnits.value) {
    ElMessage.warning(`请输入有效的生成数量（1-${maxAllowedUnits.value}）`)
    return
  }
  emit('confirm')
}
</script>

<style lang="scss" scoped>
.continue-dialog-content {
  .continue-hint {
    margin-bottom: 16px;
    font-size: 14px;
    color: #606266;
    line-height: 1.6;

    strong {
      color: #409eff;
      font-weight: 600;
    }
  }

  .input-hint {
    font-size: 12px;
    color: #909399;
    margin-left: 8px;
  }
}
</style>
