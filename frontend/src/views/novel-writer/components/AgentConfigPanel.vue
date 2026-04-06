<!--
  AgentConfigPanel.vue - Agent配置对话框组件
  
  功能：
  - 并发配置
  - 一键应用模型配置
  - Agent配置列表（模型选择、温度设置）
-->
<template>
  <div class="agent-config-panel">
    <!-- 并发配置 -->
    <div class="concurrency-section">
      <div class="section-header">
        <el-icon><Setting /></el-icon>
        <span>并发配置</span>
      </div>
      <div class="concurrency-config">
        <div class="config-item">
          <span class="config-label">并发写手数量：</span>
          <el-slider
            :model-value="concurrency"
            @change="$emit('update:concurrency', $event)"
            :min="1"
            :max="10"
            show-stops
            show-input
            style="width: 300px"
          />
        </div>
        <div class="config-hint">
          同时运行的写手Agent数量，建议根据API速率限制调整
        </div>
      </div>
    </div>

    <el-divider />

    <!-- 一键应用区域 -->
    <div class="quick-apply-section">
      <span class="section-label">快速配置：</span>
      <el-select
        v-model="localQuickApplyConfigId"
        placeholder="选择模型配置，一键应用到所有Agent"
        style="width: 300px"
        clearable
      >
        <el-option
          v-for="config in activeModelConfigs"
          :key="config.id"
          :label="`${config.name} (${config.provider_display || config.provider} / ${config.model_id})`"
          :value="config.id"
        />
      </el-select>
      <el-button
        type="primary"
        :disabled="!localQuickApplyConfigId"
        @click="handleQuickApply"
      >
        应用到全部
      </el-button>
    </div>

    <el-divider />

    <!-- Agent配置列表 -->
    <div class="agent-list">
      <div v-for="agent in configurableAgents" :key="agent.role" class="agent-item">
        <div class="agent-header">
          <el-icon :size="20">
            <component :is="getAgentIconComponent(agent.role)" />
          </el-icon>
          <span class="agent-name">{{ agent.label }}</span>
          <el-tooltip :content="agent.description" placement="top">
            <el-icon class="info-icon"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="agent-config-row">
          <el-select
            :model-value="agentConfigIds[agent.role]"
            placeholder="选择预配置模型"
            style="width: 250px"
            clearable
            @change="(val) => onConfigChange(agent.role, val)"
          >
            <el-option
              v-for="config in activeModelConfigs"
              :key="config.id"
              :label="`${config.name} (${config.provider_display || config.provider})`"
              :value="config.id"
            />
            <el-option label="自定义配置..." value="custom" />
          </el-select>
          <div class="temp-slider">
            <span class="temp-label">温度:</span>
            <el-slider
              :model-value="agentTemps[agent.role]"
              @change="(val) => onTempChange(agent.role, val)"
              :min="0"
              :max="2"
              :step="0.1"
              style="width: 120px"
            />
            <span class="temp-value">{{ agentTemps[agent.role] }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  Setting,
  InfoFilled,
  Connection,
  OfficeBuilding,
  EditPen,
  View,
  MagicStick,
  Warning,
  Reading,
  SetUp
} from '@element-plus/icons-vue'
import { agentConfigs } from '../composables/useWritingTask'

const props = defineProps({
  // 并发数
  concurrency: {
    type: Number,
    default: 3
  },
  // Agent配置IDs
  agentConfigIds: {
    type: Object,
    default: () => ({})
  },
  // Agent温度
  agentTemps: {
    type: Object,
    default: () => ({})
  },
  // 模型配置列表
  modelConfigs: {
    type: Array,
    default: () => []
  },
  // 快速应用配置ID
  quickApplyConfigId: {
    type: [Number, String],
    default: null
  }
})

const emit = defineEmits([
  'update:concurrency',
  'update:agentConfigIds',
  'update:agentTemps',
  'update:quickApplyConfigId',
  'quick-apply',
  'config-change',
  'temp-change'
])

// 本地快速应用配置ID
const localQuickApplyConfigId = ref(props.quickApplyConfigId)

// 监听props变化
watch(
  () => props.quickApplyConfigId,
  (val) => {
    localQuickApplyConfigId.value = val
  }
)

// 可配置的Agent列表
const configurableAgents = computed(() => {
  return agentConfigs.filter((agent) => agent.configurable !== false)
})

// 活跃的模型配置
const activeModelConfigs = computed(() => {
  return props.modelConfigs.filter((c) => c.is_active)
})

// 方法
function getAgentIconComponent(role) {
  const iconMap = {
    orchestrator: Connection,
    structural: OfficeBuilding,
    writer: EditPen,
    logic_editor: View,
    style_editor: MagicStick,
    compliance: Warning,
    knowledge: Reading,
    assembler: SetUp
  }
  return iconMap[role] || Setting
}

function onConfigChange(role, configId) {
  const newConfigIds = { ...props.agentConfigIds, [role]: configId }
  emit('update:agentConfigIds', newConfigIds)
  emit('config-change', role, configId)
}

function onTempChange(role, temp) {
  const newTemps = { ...props.agentTemps, [role]: temp }
  emit('update:agentTemps', newTemps)
  emit('temp-change', role, temp)
}

function handleQuickApply() {
  emit('update:quickApplyConfigId', localQuickApplyConfigId.value)
  emit('quick-apply', localQuickApplyConfigId.value)
}
</script>

<style lang="scss" scoped>
.agent-config-panel {
  .concurrency-section {
    padding: 16px;
    background: #f5f7fa;
    border-radius: 8px;
    margin-bottom: 16px;

    .section-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 12px;
    }

    .concurrency-config {
      .config-item {
        display: flex;
        align-items: center;
        gap: 16px;
      }

      .config-label {
        font-size: 14px;
        color: #606266;
        white-space: nowrap;
      }

      .config-hint {
        margin-top: 8px;
        font-size: 12px;
        color: #909399;
      }
    }
  }

  .quick-apply-section {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 8px;
    margin-bottom: 16px;

    .section-label {
      font-size: 14px;
      color: #606266;
      white-space: nowrap;
    }
  }

  .agent-list {
    max-height: 500px;
    overflow-y: auto;

    .agent-item {
      padding: 12px 16px;
      background: #fafafa;
      border-radius: 8px;
      margin-bottom: 12px;
      transition: all 0.2s;

      &:hover {
        background: #f0f9eb;
      }

      .agent-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;

        .agent-name {
          font-size: 14px;
          font-weight: 600;
          color: #303133;
        }

        .info-icon {
          color: #909399;
          cursor: help;
        }
      }

      .agent-config-row {
        display: flex;
        align-items: center;
        gap: 16px;

        .temp-slider {
          display: flex;
          align-items: center;
          gap: 8px;

          .temp-label {
            font-size: 12px;
            color: #909399;
          }

          .temp-value {
            font-size: 12px;
            color: #409eff;
            min-width: 24px;
          }
        }
      }
    }
  }
}
</style>
