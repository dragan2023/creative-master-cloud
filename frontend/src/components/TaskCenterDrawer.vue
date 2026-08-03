<template>
  <el-drawer
    v-model="visible"
    :title="drawerTitle"
    direction="rtl"
    size="420px"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    :destroy-on-close="false"
    class="task-center-drawer"
    @open="handleOpen"
    @closed="handleClosed"
  >
    <!-- 快捷操作区 -->
    <div class="drawer-quick-actions" aria-label="任务中心快捷操作">
      <el-radio-group
        v-model="filterMode"
        size="small"
        @change="handleFilterChange"
        aria-label="任务筛选"
      >
        <el-radio-button value="active">
          <el-icon><Loading /></el-icon>
          进行中 ({{ activeTasks.length }})
        </el-radio-button>
        <el-radio-button value="completed">
          <el-icon><CircleCheck /></el-icon>
          已完成 ({{ completedTasks.length }})
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- 任务列表 -->
    <div class="task-list" role="list" aria-label="任务列表">
      <!-- 空状态 -->
      <el-empty
        v-if="displayTasks.length === 0"
        :description="emptyDescription"
        :image-size="120"
      />

      <!-- 任务卡片 -->
      <div
        v-for="task in displayTasks"
        :key="task.id"
        class="task-card"
        :class="`task-card--${task.status}`"
        role="listitem"
        :aria-label="`任务: ${taskLabel(task)}`"
        @click="handleCardClick(task)"
        @keydown.enter="handleCardClick(task)"
      >
        <!-- 卡片头部 -->
        <div class="card-header">
          <div class="card-phase">
            <el-icon :size="16">
              <component :is="getPhaseIcon(task)" />
            </el-icon>
            <span class="phase-label">{{ getPhaseLabel(task) }}</span>
          </div>
          <el-tag
            :type="getStatusTagType(task.status)"
            size="small"
            effect="plain"
          >
            {{ getStatusLabel(task.status) }}
          </el-tag>
        </div>

        <!-- 卡片主体 -->
        <div class="card-body">
          <div class="task-title" :title="taskLabel(task)">
            {{ taskLabel(task) }}
          </div>
          <div v-if="task.message" class="task-message">
            {{ task.message }}
          </div>
        </div>

        <!-- 进度条 -->
        <div v-if="isActiveStatus(task.status) && task.totalUnits > 0" class="card-progress">
          <el-progress
            :percentage="task.progress || computeProgress(task)"
            :status="task.status === 'failed' ? 'exception' : undefined"
            :stroke-width="6"
            :show-text="true"
          />
          <span class="progress-detail">
            {{ getProgressSummary(task) }}
          </span>
        </div>

        <!-- 卡片操作区 -->
        <div
          v-if="getAvailableActions(task.status).length > 0"
          class="card-actions"
          @click.stop
        >
          <el-button
            v-for="action in getAvailableActions(task.status)"
            :key="action"
            :type="getActionType(action)"
            size="small"
            :icon="getActionIcon(action)"
            @click="handleAction(action, task)"
          >
            {{ getActionLabel(action) }}
          </el-button>
        </div>

        <!-- 时间戳 -->
        <div class="card-footer">
          <span class="task-time">
            {{ formatTime(task.updatedAt || task.createdAt) }}
          </span>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Loading, CircleCheck, Setting, Document, MagicStick, View, Download,
  Folder, Memo, List, Edit, Trophy, VideoPlay, Refresh, CircleClose,
} from '@element-plus/icons-vue'
import {
  TASK_STATUS,
  STATUS_LABELS,
  STATUS_TAG_TYPES,
  STATUS_ACTIONS,
  ACTION_CONFIG,
  ACTIVE_STATUSES,
  TERMINAL_STATUSES,
  GENERAL_PHASES,
  LONG_FORM_PHASES,
  getStatusLabel,
  getStatusTagType,
  getAvailableActions,
  getProgressSummary,
  isActiveStatus,
  isTerminalStatus,
  toTaskPresentation,
} from '@/domain/taskPresentation'
import { useWritingTaskStore } from '@/stores/writingTask'

// ==================== Props & Emits ====================

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

// ==================== Store ====================

const writingStore = useWritingTaskStore()
const router = useRouter()

// ==================== 本地状态 ====================

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const filterMode = ref('active')

// ==================== 计算属性 ====================

/** 来源: store 统一任务列表 + 当前进行中的任务 */
const allTasks = computed(() => {
  const tasks = []
  // 当前正在执行的任务 (来自 writingStore)
  const current = writingStore.currentTask
  if (current) {
    const t = toTaskPresentation({
      task_id: current.id,
      project_id: current.project_id,
      status: current.status,
      type: current.content_type === 'novel' ? 'writing' : 'generate',
      progress: (current.completed_units || 0) / Math.max(current.total_units || 1, 1),
      message: current.status_message || '',
      content_type: current.content_type || 'novel',
      completed_units: current.completed_units || 0,
      total_units: current.total_units || 0,
      created_at: current.created_at,
      updated_at: current.updated_at,
    })
    if (t) tasks.push(t)
  }
  // 历史任务列表
  const list = writingStore.taskList || []
  for (const item of list) {
    const t = toTaskPresentation(item)
    if (t && t.id !== (current?.id)) {
      tasks.push(t)
    }
  }
  return tasks
})

/** 活跃任务 */
const activeTasks = computed(() =>
  allTasks.value.filter((t) => isActiveStatus(t.status))
)

/** 已完成/终态任务 */
const completedTasks = computed(() =>
  allTasks.value.filter((t) => isTerminalStatus(t.status))
)

/** 当前显示的任务列表 */
const displayTasks = computed(() =>
  filterMode.value === 'active' ? activeTasks.value : completedTasks.value
)

/** 抽屉标题 */
const drawerTitle = computed(() =>
  filterMode.value === 'active' ? '任务中心 · 进行中' : '任务中心 · 已完成'
)

/** 空状态描述 */
const emptyDescription = computed(() =>
  filterMode.value === 'active' ? '暂无进行中的任务' : '暂无已完成的任务'
)

// ==================== 方法 ====================

function handleOpen() {
  // 打开时刷新任务列表
  writingStore.fetchTaskList?.()
}

function handleClosed() {
  // 关闭时不需要特别处理
}

function handleFilterChange() {
  // 筛选模式切换
}

/** 获取任务标题 */
function taskLabel(task) {
  if (task.contentType === 'novel' || task.contentType === 'series_script' || task.contentType === 'movie_script') {
    return `长篇写作 · ${task.id}`
  }
  return `创意生成 · ${task.id}`
}

/** 获取阶段图标名 */
function getPhaseIcon(task) {
  if (task.contentType === 'novel' || task.contentType === 'series_script' || task.contentType === 'movie_script') {
    const phase = LONG_FORM_PHASES.find((p) => p.key === task.phase)
    return phase?.icon || 'Edit'
  }
  const phase = GENERAL_PHASES.find((p) => p.key === task.phase)
  return phase?.icon || 'MagicStick'
}

/** 获取阶段标签 */
function getPhaseLabel(task) {
  if (task.contentType === 'novel' || task.contentType === 'series_script' || task.contentType === 'movie_script') {
    return '长篇写作'
  }
  return '创意生成'
}

/** 计算进度百分比 */
function computeProgress(task) {
  const total = task.totalUnits || 0
  const completed = task.completedUnits || 0
  return total > 0 ? Math.round((completed / total) * 100) : 0
}

/** 格式化时间 */
function formatTime(timeStr) {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diffMs = now - date
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}小时前`
  return date.toLocaleDateString()
}

/** 获取操作按钮类型 */
function getActionType(action) {
  return ACTION_CONFIG[action]?.type || 'default'
}

/** 获取操作图标 */
function getActionIcon(action) {
  const iconMap = {
    open_result: View,
    continue: VideoPlay,
    retry: Refresh,
    cancel: CircleClose,
    export: Download,
  }
  return iconMap[action]
}

/** 获取操作标签 */
function getActionLabel(action) {
  return ACTION_CONFIG[action]?.label || action
}

// ==================== 事件处理 ====================

/** 卡片点击 → 导航到对应页面 */
function handleCardClick(task) {
  if (!task.route) return
  if (task.route.name) {
    router.push(task.route)
  } else if (task.route.path) {
    router.push(task.route.path)
  }
  visible.value = false
}

/** 操作按钮点击 */
async function handleAction(action, task) {
  switch (action) {
    case 'open_result':
      handleCardClick(task)
      break

    case 'cancel':
      try {
        await ElMessageBox.confirm('确定要取消此任务吗？', '取消任务', {
          confirmButtonText: '确认取消',
          cancelButtonText: '返回',
          type: 'warning',
        })
        if (writingStore.interruptTask) {
          await writingStore.interruptTask(task.id)
        }
        ElMessage.success('任务已取消')
      } catch {
        // 用户取消操作
      }
      break

    case 'retry':
      if (task.route) {
        handleCardClick(task)
      }
      break

    case 'continue':
      handleCardClick(task)
      break

    case 'export':
      if (writingStore.exportTask) {
        await writingStore.exportTask(task.id)
      }
      break
  }
}
</script>

<style lang="scss" scoped>
.task-center-drawer {
  :deep(.el-drawer__header) {
    margin-bottom: 0;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f0f0;
  }

  :deep(.el-drawer__body) {
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    height: calc(100% - 53px);
    overflow: hidden;
  }
}

.drawer-quick-actions {
  margin-bottom: 16px;

  :deep(.el-radio-group) {
    width: 100%;

    .el-radio-button {
      flex: 1;

      .el-radio-button__inner {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
      }
    }
  }
}

.task-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: #f5f7fa;
    border-radius: 2px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c0c4cc;
    border-radius: 2px;
  }
}

.task-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.25s ease;

  &:hover {
    border-color: #409eff;
    box-shadow: 0 4px 16px rgba(64, 158, 255, 0.12);
    transform: translateY(-1px);
  }

  &:focus-visible {
    outline: 2px solid #409eff;
    outline-offset: 2px;
  }

  &--generating,
  &--running {
    border-left: 3px solid #e6a23c;
  }

  &--interrupted,
  &--failed {
    border-left: 3px solid #f56c6c;
  }

  &--completed {
    border-left: 3px solid #67c23a;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;

    .card-phase {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #606266;
      font-size: 13px;

      .el-icon {
        color: #409eff;
      }

      .phase-label {
        font-weight: 500;
      }
    }
  }

  .card-body {
    margin-bottom: 10px;

    .task-title {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      line-height: 1.4;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .task-message {
      font-size: 12px;
      color: #909399;
      margin-top: 4px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .card-progress {
    margin-bottom: 10px;

    .progress-detail {
      display: block;
      font-size: 12px;
      color: #909399;
      margin-top: 4px;
    }
  }

  .card-actions {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }

  .card-footer {
    .task-time {
      font-size: 11px;
      color: #c0c4cc;
    }
  }
}

// ==================== 响应式: 窄屏 ====================

@media (max-width: 768px) {
  .task-center-drawer {
    :deep(.el-drawer) {
      width: 100% !important;
      max-width: 420px;
    }

    :deep(.el-drawer__body) {
      padding: 12px 12px;
    }
  }

  .task-card {
    padding: 10px 12px;

    .card-actions {
      .el-button {
        font-size: 12px;
        padding: 4px 10px;
      }
    }
  }
}

@media (max-width: 390px) {
  .task-center-drawer {
    :deep(.el-drawer) {
      width: 100% !important;
    }

    :deep(.el-drawer__body) {
      padding: 8px 10px;
    }
  }
}
</style>
