<template>
  <div class="creation-step-bar" role="navigation" aria-label="创作进度">
    <el-steps
      :active="activeIndex"
      :align-center="true"
      :space="stepSpace"
      finish-status="success"
      process-status="process"
    >
      <el-step
        v-for="(step, index) in steps"
        :key="step.key"
        :title="step.label"
        :status="getStepStatus(index)"
        :icon="getStepIcon(index)"
      >
        <template v-if="step.actionLabel && index === activeIndex" #description>
          <span class="step-action-hint">{{ step.actionLabel }}</span>
        </template>
      </el-step>
    </el-steps>

    <!-- 步骤引导操作区 -->
    <div v-if="showActions" class="step-actions">
      <div class="step-actions-inner">
        <!-- 主操作按钮 -->
        <el-button
          v-if="primaryAction"
          :type="primaryAction.type || 'primary'"
          :icon="primaryAction.icon"
          :loading="primaryAction.loading"
          :disabled="primaryAction.disabled"
          @click="primaryAction.onClick"
        >
          {{ primaryAction.label }}
        </el-button>

        <!-- 次级操作 -->
        <el-button
          v-for="(action, idx) in secondaryActions"
          :key="idx"
          :type="action.type || 'default'"
          :icon="action.icon"
          :disabled="action.disabled"
          @click="action.onClick"
        >
          {{ action.label }}
        </el-button>
      </div>

      <!-- 当前步骤提示 -->
      <div v-if="currentHint" class="step-hint">
        <el-icon><InfoFilled /></el-icon>
        <span>{{ currentHint }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Setting, Document, MagicStick, View, Download,
  Folder, Memo, List, Edit, CircleCheck, Trophy,
  InfoFilled,
} from '@element-plus/icons-vue'

// ==================== Props ====================

const props = defineProps({
  /** 步骤定义数组: [{ key, label, description, status }] */
  steps: { type: Array, default: () => [] },
  /** 当前激活步骤索引 (0-based) */
  currentStep: { type: Number, default: 0 },
  /** 主操作按钮配置 { label, icon, type, loading, disabled, onClick } */
  primaryAction: { type: Object, default: null },
  /** 次级操作按钮列表 [{ label, icon, type, disabled, onClick }] */
  secondaryActions: { type: Array, default: () => [] },
  /** 当前步骤提示文本 */
  currentHint: { type: String, default: '' },
})

// ==================== 计算属性 ====================

/** 激活步骤索引 */
const activeIndex = computed(() => {
  // 在当前步骤之前的都标记为完成
  return props.currentStep
})

/** 是否显示操作区 */
const showActions = computed(() => {
  return props.primaryAction || props.secondaryActions.length > 0 || props.currentHint
})

/**
 * 根据容器宽度动态调整步骤间距
 * 窄屏时压缩以便完整显示
 */
const stepSpace = computed(() => {
  if (typeof window !== 'undefined' && window.innerWidth < 480) {
    return Math.max(60, Math.floor((window.innerWidth - 40) / props.steps.length))
  }
  return undefined // 默认等分
})

// ==================== 方法 ====================

const iconMap = {
  Setting, Document, MagicStick, View, Download,
  Folder, Memo, List, Edit, CircleCheck, Trophy,
}

/** 获取步骤状态 */
function getStepStatus(index) {
  if (index < activeIndex.value) return 'success'
  if (index === activeIndex.value) return 'process'
  return 'wait'
}

/** 获取步骤图标 */
function getStepIcon(index) {
  const step = props.steps[index]
  if (!step?.icon) return undefined
  const IconComp = iconMap[step.icon]
  return IconComp || undefined
}
</script>

<style lang="scss" scoped>
.creation-step-bar {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(64, 158, 255, 0.08);

  :deep(.el-steps) {
    .el-step__title {
      font-size: 13px;
      font-weight: 500;
    }

    .el-step__head {
      &.is-process {
        color: #409eff;
        border-color: #409eff;
      }
    }

    .step-action-hint {
      font-size: 12px;
      color: #409eff;
      margin-top: 2px;
    }
  }

  .step-actions {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #f0f0f0;

    .step-actions-inner {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .step-hint {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 10px;
      padding: 8px 12px;
      background: #f0f9ff;
      border-radius: 6px;
      font-size: 13px;
      color: #606266;

      .el-icon {
        color: #409eff;
        flex-shrink: 0;
      }
    }
  }
}

// ==================== 响应式 ====================

@media (max-width: 768px) {
  .creation-step-bar {
    padding: 14px 12px;

    :deep(.el-steps) {
      .el-step__title {
        font-size: 11px;
      }

      .el-step__icon {
        width: 24px;
        height: 24px;
        font-size: 12px;
      }
    }

    .step-actions {
      .step-actions-inner {
        gap: 6px;
      }
    }
  }
}

@media (max-width: 390px) {
  .creation-step-bar {
    padding: 10px 8px;

    :deep(.el-steps) {
      .el-step__title {
        font-size: 10px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .el-step__icon {
        width: 20px;
        height: 20px;
        font-size: 10px;
      }
    }

    .step-actions {
      .step-actions-inner {
        flex-direction: column;
        align-items: stretch;

        .el-button {
          width: 100%;
        }
      }
    }
  }
}
</style>
