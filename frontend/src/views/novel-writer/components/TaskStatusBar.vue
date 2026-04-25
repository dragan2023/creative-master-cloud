<template>
  <div class="task-status-bar" v-if="effectiveTaskStore?.hasTask">
    <div class="status-content">
      <el-icon class="status-icon" :size="16"><Loading /></el-icon>
      <span class="status-text">{{ effectiveTaskStore.currentTaskMessage || '任务进行中...' }}</span>
      <el-button size="small" type="danger" plain @click="onCancel" :loading="cancelling">
        终止任务
      </el-button>
    </div>
    <el-progress
      v-if="effectiveTaskStore.currentTaskProgress > 0"
      :percentage="effectiveTaskStore.currentTaskProgress"
      :stroke-width="4"
      :show-text="true"
      style="margin-top: 4px;"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { useTaskStore } from '@/stores/task'

const props = defineProps({
  onCancel: { type: Function, default: null },
  taskStore: { type: Object, default: null }
})

// 优先使用prop传入的taskStore,否则从store获取
const localTaskStore = useTaskStore()
const effectiveTaskStore = computed(() => props.taskStore || localTaskStore)

const cancelling = ref(false)

const onCancel = async () => {
  if (cancelling.value) return
  cancelling.value = true
  try {
    if (props.onCancel) {
      await props.onCancel()
    }
  } finally {
    cancelling.value = false
  }
}
</script>

<style lang="scss" scoped>
.task-status-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #e6f4ff;
  border: 1px solid #91caff;
  border-radius: 6px;
  padding: 10px 16px;
  margin-bottom: 12px;

  .status-content {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .status-icon {
    color: #1677ff;
    animation: rotating 1.5s linear infinite;
  }

  .status-text {
    flex: 1;
    font-size: 13px;
    color: #333;
  }
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
