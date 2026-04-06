<!--
  TaskProgressMonitor.vue - 任务进度监控组件
  
  功能：
  - 实时进度面板（Agent流水线、工作流步骤、执行日志）
  - 单元/场景浏览面板
  - Agent统计仪表板
-->
<template>
  <div class="task-progress-monitor">
    <el-row :gutter="20">
      <!-- 左侧：实时进度面板 -->
      <el-col :span="14">
        <el-card class="progress-panel" shadow="hover">
          <template #header>
            <div class="panel-header">
              <span>
                <el-icon><DataLine /></el-icon>
                实时进度
              </span>
              <el-tag
                v-if="wsConnected"
                type="success"
                size="small"
                effect="plain"
              >
                <el-icon><Connection /></el-icon>
                实时连接
              </el-tag>
              <el-tag v-else type="info" size="small" effect="plain">
                <el-icon><Loading /></el-icon>
                连接中...
              </el-tag>
            </div>
          </template>

          <!-- Agent状态流水线 -->
          <div class="agent-pipeline">
            <div
              v-for="(agent, idx) in agentPipeline"
              :key="agent.role"
              class="pipeline-item"
              :class="agent.status"
            >
              <div class="pipeline-icon">
                <el-icon :size="24">
                  <component :is="getAgentIconComponent(agent.icon)" />
                </el-icon>
                <div v-if="idx < agentPipeline.length - 1" class="pipeline-arrow">
                  <el-icon><ArrowRight /></el-icon>
                </div>
              </div>
              <div class="pipeline-info">
                <span class="pipeline-name">{{ agent.label }}</span>
                <el-tag :type="agent.statusType" size="small">
                  {{ agent.statusLabel }}
                </el-tag>
              </div>
            </div>
          </div>

          <!-- 工作流步骤显示 -->
          <div v-if="workflowSteps.length > 0" class="workflow-steps-section">
            <el-divider content-position="left">执行步骤</el-divider>
            <div class="workflow-steps">
              <div
                v-for="(step, index) in workflowSteps"
                :key="`${step.step}-${index}`"
                class="workflow-step"
                :class="{
                  'is-running': step.status === 'running',
                  'is-done': step.status === 'done',
                  'is-error': step.status === 'error'
                }"
              >
                <div class="step-icon">
                  <el-icon v-if="step.status === 'running'" class="is-spinning">
                    <Loading />
                  </el-icon>
                  <el-icon v-else-if="step.status === 'done'" color="#67C23A">
                    <CircleCheck />
                  </el-icon>
                  <el-icon v-else-if="step.status === 'error'" color="#F56C6C">
                    <CircleClose />
                  </el-icon>
                  <el-icon v-else>
                    <component :is="getAgentIconComponent(step.icon)" />
                  </el-icon>
                </div>
                <div class="step-content">
                  <div class="step-message">{{ step.message }}</div>
                </div>
                <div class="step-status">
                  <el-tag v-if="step.status === 'done'" type="success" size="small"
                    >完成</el-tag
                  >
                  <el-tag
                    v-else-if="step.status === 'running'"
                    type="warning"
                    size="small"
                    >执行中</el-tag
                  >
                  <el-tag
                    v-else-if="step.status === 'error'"
                    type="danger"
                    size="small"
                    >失败</el-tag
                  >
                </div>
              </div>
            </div>
          </div>

          <!-- 当前处理信息 -->
          <div v-if="currentProcessingInfo" class="current-processing">
            <el-divider content-position="left">当前处理</el-divider>
            <div class="processing-info">
              <el-icon><Loading class="is-loading" /></el-icon>
              <span>{{ currentProcessingInfo }}</span>
            </div>
          </div>

          <!-- 进度消息列表 -->
          <div class="progress-messages">
            <el-divider content-position="left">执行日志</el-divider>
            <div class="messages-list" ref="messagesListRef">
              <div
                v-for="(msg, idx) in progressMessages"
                :key="idx"
                class="progress-item"
                :class="msg.type"
              >
                <el-tag size="small" :type="getMessageTagType(msg)" class="msg-agent">
                  {{ msg.data?.agent_name || getAgentLabel(msg.data?.agent_role) || '系统' }}
                </el-tag>
                <span class="msg-content">{{ msg.data?.message || msg.type }}</span>
                <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <el-empty
                v-if="progressMessages.length === 0"
                description="暂无进度消息"
                :image-size="60"
              />
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：单元/场景浏览面板 -->
      <el-col :span="10">
        <el-card class="units-panel" shadow="hover">
          <template #header>
            <div class="panel-header">
              <span>
                <el-icon><List /></el-icon>
                单元列表
              </span>
              <el-tag type="info" size="small"> {{ displayUnits.length }} 单元 </el-tag>
            </div>
          </template>

          <el-collapse v-model="activeUnits" class="units-collapse">
            <el-collapse-item
              v-for="unit in displayUnits"
              :key="unit.unit_index"
              :name="unit.unit_index"
              @click="handleUnitExpand(unit)"
            >
              <template #title>
                <div class="unit-title">
                  <span class="unit-index">#{{ unit.unit_index }}</span>
                  <span class="unit-name" :title="unit.unit_title">
                    {{ unit.unit_title || `单元 ${unit.unit_index}` }}
                  </span>
                  <el-tag :type="getUnitStatusType(unit.status)" size="small">
                    {{ getUnitStatusLabel(unit.status) }}
                  </el-tag>
                  <span v-if="unit.word_count > 0" class="unit-word-count">
                    {{ unit.word_count }} 字
                  </span>
                  <el-button
                    v-if="unit.status === 'completed'"
                    type="primary"
                    size="small"
                    link
                    @click.stop="$emit('export-unit', unit.unit_index)"
                  >
                    <el-icon><Download /></el-icon>
                  </el-button>
                </div>
              </template>

              <!-- 场景列表 -->
              <div class="scenes-list" v-loading="loadingScenes[unit.unit_index]">
                <div
                  v-for="scene in getScenes(unit.unit_index)"
                  :key="scene.scene_index"
                  class="scene-item"
                  @click.stop="handleSceneClick(scene, unit)"
                >
                  <div class="scene-info">
                    <span class="scene-index">场景 {{ scene.scene_index }}</span>
                    <span class="scene-title">{{ scene.scene_title || '未命名场景' }}</span>
                  </div>
                  <div class="scene-meta">
                    <el-tag :type="getSceneStatusType(scene.status)" size="small">
                      {{ getSceneStatusLabel(scene.status) }}
                    </el-tag>
                    <span v-if="scene.word_count > 0" class="scene-word-count">
                      {{ scene.word_count }} 字
                    </span>
                  </div>
                </div>
                <el-empty
                  v-if="getScenes(unit.unit_index).length === 0 && !loadingScenes[unit.unit_index]"
                  description="暂无场景"
                  :image-size="40"
                />
              </div>
            </el-collapse-item>
          </el-collapse>

          <el-empty v-if="displayUnits.length === 0" description="暂无单元数据" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 底部：统计仪表板 -->
    <el-card v-if="stats" class="stats-dashboard" shadow="hover">
      <template #header>
        <div class="panel-header">
          <span>
            <el-icon><TrendCharts /></el-icon>
            Agent统计
          </span>
        </div>
      </template>

      <el-row :gutter="20">
        <!-- 总体统计 -->
        <el-col :span="6">
          <div class="stat-card total">
            <div class="stat-icon">
              <el-icon><Coin /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">
                {{ formatNumber(stats?._summary?.total_tokens || stats?.total_tokens || 0) }}
              </div>
              <div class="stat-label">总Token数</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card cost">
            <div class="stat-icon">
              <el-icon><Money /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">
                ${{ ((stats?._summary?.total_cost || stats?.total_cost || 0)).toFixed(4) }}
              </div>
              <div class="stat-label">总费用</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card time">
            <div class="stat-icon">
              <el-icon><Timer /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ formattedDuration }}</div>
              <div class="stat-label">总耗时</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card efficiency">
            <div class="stat-icon">
              <el-icon><Odometer /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ calculateEfficiency() }}</div>
              <div class="stat-label">Token/秒</div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- Agent详细统计 -->
      <el-divider content-position="left">Agent详细统计</el-divider>
      <el-table :data="stats.by_agent || []" stripe style="width: 100%">
        <el-table-column prop="agent_name" label="Agent" width="120">
          <template #default="{ row }">
            <el-tag :type="getAgentTagType(row.agent_name)" effect="plain">
              {{ row.agent_name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_id" label="模型" min-width="150" show-overflow-tooltip />
        <el-table-column prop="call_count" label="调用次数" width="100" align="center" />
        <el-table-column prop="total_tokens" label="Token数" width="120" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.total_tokens) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_cost" label="费用" width="100" align="right">
          <template #default="{ row }">
            ${{ row.total_cost?.toFixed(4) || '0.0000' }}
          </template>
        </el-table-column>
        <el-table-column prop="total_duration_sec" label="耗时" width="100" align="right">
          <template #default="{ row }">
            {{ row.total_duration_sec?.toFixed(1) || '0.0' }}s
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 场景内容查看对话框 -->
    <el-dialog
      v-model="sceneDialogVisible"
      :title="selectedSceneTitle"
      width="800px"
      destroy-on-close
      class="scene-dialog"
    >
      <div v-if="selectedScene" class="scene-content">
        <div class="scene-meta-info">
          <el-tag :type="getSceneStatusType(selectedScene.status)">
            {{ getSceneStatusLabel(selectedScene.status) }}
          </el-tag>
          <span v-if="selectedScene.word_count > 0">
            <el-icon><Document /></el-icon>
            {{ selectedScene.word_count }} 字
          </span>
          <span v-if="selectedScene.token_count > 0">
            <el-icon><Coin /></el-icon>
            {{ formatNumber(selectedScene.token_count) }} tokens
          </span>
        </div>
        <el-divider />
        <div class="content-body">
          <pre v-if="selectedScene.final_content">{{ selectedScene.final_content }}</pre>
          <el-empty v-else description="暂无内容" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import {
  DataLine,
  Connection,
  Loading,
  ArrowRight,
  List,
  TrendCharts,
  Document,
  Coin,
  Money,
  Timer,
  Odometer,
  CircleCheck,
  CircleClose,
  Download,
  OfficeBuilding,
  EditPen,
  View,
  MagicStick,
  Warning,
  Reading,
  SetUp,
  Setting
} from '@element-plus/icons-vue'
import { useWritingTaskStore } from '@/stores/writingTask'
import { AGENT_ROLE_LABELS } from '../composables/useWritingTask'

const props = defineProps({
  // WebSocket连接状态
  wsConnected: {
    type: Boolean,
    default: false
  },
  // Agent流水线
  agentPipeline: {
    type: Array,
    default: () => []
  },
  // 工作流步骤
  workflowSteps: {
    type: Array,
    default: () => []
  },
  // 当前处理信息
  currentProcessingInfo: {
    type: String,
    default: null
  },
  // 进度消息
  progressMessages: {
    type: Array,
    default: () => []
  },
  // 显示的单元列表
  displayUnits: {
    type: Array,
    default: () => []
  },
  // 统计数据
  stats: {
    type: Object,
    default: null
  },
  // 格式化耗时
  formattedDuration: {
    type: String,
    default: '00:00:00'
  }
})

const emit = defineEmits(['export-unit', 'scene-click', 'unit-expand'])

const writingStore = useWritingTaskStore()

// 响应式状态
const messagesListRef = ref(null)
const activeUnits = ref([])
const loadingScenes = ref({})
const sceneDialogVisible = ref(false)
const selectedScene = ref(null)
const selectedUnit = ref(null)

// 计算属性
const selectedSceneTitle = computed(() => {
  if (!selectedScene.value) return ''
  const unitIdx = selectedUnit.value?.unit_index || ''
  const sceneIdx = selectedScene.value.scene_index
  const sceneTitle = selectedScene.value.scene_title || `场景 ${sceneIdx}`
  return `单元 ${unitIdx} - ${sceneTitle}`
})

// 监听进度消息，自动滚动
watch(
  () => props.progressMessages.length,
  () => {
    nextTick(() => {
      if (messagesListRef.value) {
        messagesListRef.value.scrollTop = 0
      }
    })
  }
)

// 方法
function getAgentIconComponent(iconName) {
  const iconMap = {
    Connection,
    OfficeBuilding,
    EditPen,
    View,
    MagicStick,
    Warning,
    Reading,
    SetUp,
    Setting,
    CircleCheck,
    CircleClose,
    DataLine
  }
  return iconMap[iconName] || Setting
}

function getAgentLabel(role) {
  if (!role) return ''
  if (AGENT_ROLE_LABELS[role]) {
    return AGENT_ROLE_LABELS[role].replace('Agent', '')
  }
  return role
}

function getMessageTagType(msg) {
  const agentRole = msg.data?.agent_role
  if (!agentRole) return 'info'

  const typeMap = {
    structural: 'primary',
    writer: 'success',
    logic_editor: 'warning',
    style_editor: '',
    compliance: 'danger',
    assembler: 'info'
  }
  return typeMap[agentRole] || 'info'
}

function getAgentTagType(agentName) {
  const typeMap = {
    结构师: 'primary',
    写手: 'success',
    逻辑编辑: 'warning',
    风格润色: '',
    合规审查: 'danger',
    合成: 'info'
  }
  return typeMap[agentName] || 'info'
}

function handleUnitExpand(unit) {
  if (writingStore.scenes[unit.unit_index]) return
  loadingScenes.value[unit.unit_index] = true
  emit('unit-expand', unit)
  // 异步加载后更新状态
  setTimeout(() => {
    loadingScenes.value[unit.unit_index] = false
  }, 1000)
}

function getScenes(unitIndex) {
  return writingStore.scenes[unitIndex] || []
}

function handleSceneClick(scene, unit) {
  selectedScene.value = scene
  selectedUnit.value = unit
  sceneDialogVisible.value = true
  emit('scene-click', { scene, unit })
}

function getUnitStatusType(status) {
  const typeMap = {
    pending: 'info',
    processing: 'primary',
    completed: 'success',
    failed: 'danger'
  }
  return typeMap[status] || 'info'
}

function getUnitStatusLabel(status) {
  const labelMap = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
  }
  return labelMap[status] || status
}

function getSceneStatusType(status) {
  const typeMap = {
    pending: 'info',
    writing: 'primary',
    reviewing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return typeMap[status] || 'info'
}

function getSceneStatusLabel(status) {
  const labelMap = {
    pending: '等待中',
    writing: '写作中',
    reviewing: '审阅中',
    completed: '已完成',
    failed: '失败'
  }
  return labelMap[status] || status
}

function formatNumber(num) {
  if (!num) return '0'
  return num.toLocaleString()
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function calculateEfficiency() {
  const tokens =
    props.stats?._summary?.total_tokens || props.stats?.total_tokens || 0
  const task = writingStore.currentTask
  if (!task) return '0'

  const start = task.start_time ? new Date(task.start_time) : null
  const end = task.end_time ? new Date(task.end_time) : null

  let ms = 0
  if (start && end) {
    ms = end - start
  } else if (start && writingStore.isRunning) {
    ms = Date.now() - start
  }

  const durationSec = ms / 1000
  if (durationSec === 0) return '0'
  return (tokens / durationSec).toFixed(1)
}
</script>

<style lang="scss" scoped>
.task-progress-monitor {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.progress-panel {
  height: 100%;
  min-height: 500px;

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .el-icon {
      margin-right: 4px;
    }
  }

  .agent-pipeline {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px 0;
    gap: 16px;
    flex-wrap: wrap;

    .pipeline-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 12px 20px;
      border-radius: 8px;
      background: #f5f7fa;
      transition: all 0.3s;

      &.running {
        background: #ecf5ff;
        box-shadow: 0 0 0 2px #409eff;
      }

      &.completed {
        background: #f0f9eb;
      }

      &.error {
        background: #fef0f0;
      }

      .pipeline-icon {
        position: relative;
        display: flex;
        align-items: center;

        .el-icon {
          font-size: 24px;
          color: #606266;
        }

        .pipeline-arrow {
          position: absolute;
          right: -28px;
          top: 50%;
          transform: translateY(-50%);
          color: #c0c4cc;
        }
      }

      .pipeline-info {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;

        .pipeline-name {
          font-size: 13px;
          font-weight: 500;
        }
      }
    }
  }

  .current-processing {
    margin: 16px 0;
    padding: 12px 16px;
    background: #ecf5ff;
    border-radius: 8px;
    border-left: 4px solid #409eff;

    .processing-info {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #409eff;
      font-size: 14px;

      .el-icon {
        font-size: 16px;
      }
    }
  }

  .progress-messages {
    .messages-list {
      max-height: 300px;
      overflow-y: auto;
      padding-right: 8px;

      .progress-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        border-bottom: 1px solid #ebeef5;
        font-size: 13px;

        &:hover {
          background: #f5f7fa;
        }

        .msg-agent {
          flex-shrink: 0;
          min-width: 60px;
          text-align: center;
        }

        .msg-content {
          flex: 1;
          color: #303133;
          word-break: break-all;
        }

        .msg-time {
          flex-shrink: 0;
          color: #909399;
          font-size: 12px;
        }
      }
    }
  }
}

.units-panel {
  height: 100%;
  min-height: 500px;

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .el-icon {
      margin-right: 4px;
    }
  }

  .units-collapse {
    .unit-title {
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 1;
      padding-right: 16px;

      .unit-index {
        font-weight: 600;
        color: #409eff;
        min-width: 40px;
      }

      .unit-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .unit-word-count {
        font-size: 12px;
        color: #909399;
      }
    }

    .scenes-list {
      padding: 8px 0;

      .scene-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        margin-bottom: 8px;
        background: #f5f7fa;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s;

        &:hover {
          background: #ecf5ff;
        }

        .scene-info {
          display: flex;
          flex-direction: column;
          gap: 2px;

          .scene-index {
            font-size: 12px;
            color: #909399;
          }

          .scene-title {
            font-size: 13px;
            color: #303133;
          }
        }

        .scene-meta {
          display: flex;
          align-items: center;
          gap: 8px;

          .scene-word-count {
            font-size: 12px;
            color: #909399;
          }
        }
      }
    }
  }
}

.stats-dashboard {
  margin-top: 20px;

  .panel-header {
    display: flex;
    align-items: center;

    .el-icon {
      margin-right: 4px;
    }
  }

  .stat-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    border-radius: 8px;
    background: #f5f7fa;

    &.total {
      background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
      .stat-icon {
        color: #409eff;
      }
    }

    &.cost {
      background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
      .stat-icon {
        color: #67c23a;
      }
    }

    &.time {
      background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
      .stat-icon {
        color: #e6a23c;
      }
    }

    &.efficiency {
      background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
      .stat-icon {
        color: #f56c6c;
      }
    }

    .stat-icon {
      font-size: 32px;
    }

    .stat-info {
      .stat-value {
        font-size: 20px;
        font-weight: 600;
        color: #303133;
      }

      .stat-label {
        font-size: 12px;
        color: #909399;
        margin-top: 2px;
      }
    }
  }
}

.scene-dialog {
  .scene-content {
    .scene-meta-info {
      display: flex;
      gap: 16px;
      align-items: center;
      margin-bottom: 12px;

      span {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: #606266;

        .el-icon {
          color: #409eff;
        }
      }
    }

    .content-body {
      max-height: 500px;
      overflow-y: auto;
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;

      pre {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: inherit;
        font-size: 14px;
        line-height: 1.8;
        color: #303133;
      }
    }
  }
}

// 响应式
@media (max-width: 1200px) {
  .el-col {
    width: 100%;
    margin-bottom: 20px;
  }
}

@media (max-width: 768px) {
  .agent-pipeline {
    .pipeline-item {
      .pipeline-arrow {
        display: none;
      }
    }
  }
}

// 工作流步骤样式
.workflow-steps-section {
  .workflow-steps {
    .workflow-step {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 12px;
      margin-bottom: 8px;
      background: #f5f7fa;
      border-radius: 6px;

      &.is-running {
        background: #ecf5ff;
        border-left: 3px solid #409eff;
      }

      &.is-done {
        background: #f0f9eb;
      }

      &.is-error {
        background: #fef0f0;
      }

      .step-icon {
        .is-spinning {
          animation: spin 1s linear infinite;
        }
      }

      .step-content {
        flex: 1;

        .step-message {
          font-size: 13px;
          color: #606266;
        }
      }
    }
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.is-loading {
  animation: spin 1s linear infinite;
}
</style>
