<template>
  <div class="recoverable-error" role="alert">
    <!-- 网络错误 -->
    <el-result
      v-if="kind === 'network'"
      icon="warning"
      title="网络连接失败"
      sub-title="请检查您的网络连接后重试"
    >
      <template #extra>
        <el-button type="primary" @click="$emit('retry')" aria-label="重试连接">
          <el-icon><Refresh /></el-icon>重试
        </el-button>
        <el-button @click="$emit('cancel')">返回工作台</el-button>
      </template>
    </el-result>

    <!-- 认证过期 -->
    <el-result
      v-else-if="kind === 'unauthorized'"
      icon="warning"
      title="登录已过期"
      sub-title="您的登录凭证已失效，请重新登录"
    >
      <template #extra>
        <el-button type="primary" @click="$emit('relogin')" aria-label="重新登录">
          <el-icon><Key /></el-icon>重新登录
        </el-button>
      </template>
    </el-result>

    <!-- 限流 -->
    <el-result
      v-else-if="kind === 'rate-limited'"
      icon="warning"
      title="请求过于频繁"
      :sub-title="subtitle || '您的操作频率过高，请稍后重试'"
    >
      <template #extra>
        <el-button type="primary" @click="$emit('retry-after', retryAfterSeconds || 15)" :disabled="countdownRemaining > 0">
          <el-icon><Clock /></el-icon>
          {{ countdownRemaining > 0 ? `请等待 ${countdownRemaining} 秒` : '重试' }}
        </el-button>
        <el-button @click="$emit('cancel')">取消</el-button>
      </template>
    </el-result>

    <!-- 模型不可用 -->
    <el-result
      v-else-if="kind === 'model-unavailable'"
      icon="warning"
      title="AI 模型暂不可用"
      :sub-title="subtitle || '当前使用的 AI 模型暂时无法响应，请稍后再试或切换模型'"
    >
      <template #extra>
        <el-button type="primary" @click="$emit('retry')" aria-label="重试">
          <el-icon><Refresh /></el-icon>重试
        </el-button>
        <el-button @click="$emit('cancel')">返回工作台</el-button>
      </template>
    </el-result>

    <!-- 任务已中断 -->
    <el-result
      v-else-if="kind === 'task-interrupted'"
      icon="warning"
      title="任务已中断"
      :sub-title="subtitle || '当前任务在服务器端已中断，您可以恢复或重新开始'"
    >
      <template #extra>
        <el-button type="primary" @click="$emit('recover')" aria-label="恢复任务">
          <el-icon><RefreshRight /></el-icon>恢复任务
        </el-button>
        <el-button @click="$emit('cancel')">返回工作台</el-button>
        <el-button @click="$emit('view-tasks')" aria-label="查看任务中心">
          <el-icon><List /></el-icon>查看任务中心
        </el-button>
      </template>
    </el-result>

    <!-- 通用错误 -->
    <el-result
      v-else
      icon="error"
      :title="title"
      :sub-title="subtitle || '操作未成功，请稍后重试'"
    >
      <template #extra>
        <el-button type="primary" @click="$emit('retry')" aria-label="重试">
          <el-icon><Refresh /></el-icon>重试
        </el-button>
        <el-button @click="$emit('cancel')">返回工作台</el-button>
        <el-button v-if="showTaskCenter" @click="$emit('view-tasks')" aria-label="查看任务中心">
          <el-icon><List /></el-icon>查看任务中心
        </el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup>
/**
 * RecoverableErrorState - 统一可恢复错误状态组件
 *
 * 根据错误类型（网络、认证、限流、模型不可用、任务中断、通用错误）
 * 展示结构化的错误标题、说明和可执行的恢复操作。
 *
 * Events:
 *   @retry           - 用户点击重试
 *   @retry-after     - 限流错误，用户等待后重试，参数: seconds
 *   @relogin         - 认证过期，跳转登录
 *   @recover         - 任务中断，恢复任务
 *   @cancel          - 返回工作台
 *   @view-tasks      - 查看任务中心
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Refresh, Clock, RefreshRight, Key, List } from '@element-plus/icons-vue'

const props = defineProps({
  /** 错误类型 */
  kind: {
    type: String,
    default: 'error',
    validator: (v) => ['network', 'unauthorized', 'rate-limited', 'model-unavailable', 'task-interrupted', 'error'].includes(v)
  },
  /** 错误标题（仅通用错误类型使用） */
  title: {
    type: String,
    default: '操作失败'
  },
  /** 错误详细说明 */
  subtitle: {
    type: String,
    default: ''
  },
  /** 限流重试等待秒数 */
  retryAfterSeconds: {
    type: Number,
    default: 15
  },
  /** 是否显示"查看任务中心"按钮 */
  showTaskCenter: {
    type: Boolean,
    default: false
  }
})

defineEmits(['retry', 'retry-after', 'relogin', 'recover', 'cancel', 'view-tasks'])

// 限流倒计时
const countdownRemaining = ref(0)
let countdownTimer = null

onMounted(() => {
  if (props.kind === 'rate-limited' && props.retryAfterSeconds > 0) {
    startCountdown()
  }
})

onBeforeUnmount(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})

function startCountdown() {
  countdownRemaining.value = props.retryAfterSeconds
  countdownTimer = setInterval(() => {
    if (countdownRemaining.value > 0) {
      countdownRemaining.value--
    } else {
      clearInterval(countdownTimer)
    }
  }, 1000)
}
</script>

<style lang="scss" scoped>
.recoverable-error {
  padding: 24px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
}

// 响应式：窄屏缩小 padding
@media (max-width: 768px) {
  .recoverable-error {
    padding: 16px;
    min-height: 220px;
  }
}

@media (max-width: 390px) {
  .recoverable-error {
    padding: 12px;
    min-height: 200px;
  }
}
</style>
