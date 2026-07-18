<template>
  <el-card class="progress-panel" shadow="hover">
    <template #header>
      <div class="panel-header">
        <span>
          <el-icon><DataLine /></el-icon>
          实时进度
        </span>
        <div class="connection-state" aria-live="polite">
          <el-tag
            :type="connectionTagType"
            size="small"
            effect="plain"
          >
            <el-icon v-if="wsStatus === 'connected'"><Connection /></el-icon>
            <el-icon v-else-if="isConnectionPending" class="is-spinning"><Loading /></el-icon>
            <el-icon v-else><Warning /></el-icon>
            {{ connectionStatusLabel }}
          </el-tag>
          <span v-if="lastUpdateLabel" class="last-update-time">{{ lastUpdateLabel }}</span>
          <el-button
            v-if="wsStatus === 'failed'"
            size="small"
            type="primary"
            @click="$emit('reconnect')"
          >
            重新连接
          </el-button>
        </div>
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
            <component :is="resolveElementIcon(agent.icon)" />
          </el-icon>
          <div v-if="idx < agentPipeline.length - 1" class="pipeline-arrow">
            <el-icon><ArrowRight /></el-icon>
          </div>
        </div>
        <div class="pipeline-info">
          <span class="pipeline-name">{{ agent.label.replace('Agent', '') }}</span>
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
            'is-error': step.status === 'error',
          }"
        >
          <div class="step-icon">
            <el-icon v-if="step.status === 'running'" class="is-spinning"
              ><Loading
            /></el-icon>
            <el-icon v-else-if="step.status === 'done'" color="#67C23A"
              ><CircleCheck
            /></el-icon>
            <el-icon v-else-if="step.status === 'error'" color="#F56C6C"
              ><CircleClose
            /></el-icon>
            <el-icon v-else><component :is="resolveElementIcon(step.icon)" /></el-icon>
          </div>
          <div class="step-content">
            <div class="step-message">{{ step.message }}</div>
          </div>
          <div class="step-status">
            <el-tag v-if="step.status === 'done'" type="success" size="small"
              >完成</el-tag
            >
            <el-tag v-else-if="step.status === 'running'" type="warning" size="small"
              >执行中</el-tag
            >
            <el-tag v-else-if="step.status === 'error'" type="danger" size="small"
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
          v-for="(msg, idx) in filteredProgressMessages"
          :key="idx"
          class="progress-item"
          :class="msg.type"
        >
          <el-tag
            size="small"
            :type="getMessageTagType(msg)"
            class="msg-agent"
          >
            {{
              msg.data?.agent_name ||
              getAgentLabel(msg.data?.agent_role) ||
              "系统"
            }}
          </el-tag>
          <span class="msg-content">{{
            msg.data?.message || msg.type
          }}</span>
          <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
        </div>
        <el-empty
          v-if="filteredProgressMessages.length === 0"
          description="暂无进度消息"
          :image-size="60"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, watch, nextTick } from "vue";
import {
  DataLine,
  Connection,
  Loading,
  ArrowRight,
  CircleCheck,
  CircleClose,
  OfficeBuilding,
  View,
  SetUp,
  MagicStick,
  Warning,
  Reading,
} from "@element-plus/icons-vue";
import { formatTime } from "../utils/contentHelpers";
import { AGENT_ROLE_LABELS, agentConfigs } from "../config/agentConfig";
import { resolveElementIcon } from "@/utils/elementIcons";

const props = defineProps({
  /** WebSocket连接状态枚举: idle/connecting/connected/offline/reconnecting/failed/closed */
  wsStatus: { type: String, default: "idle" },
  /** 最近一次收到WebSocket消息的时间戳（毫秒） */
  wsLastMessageAt: { type: Number, default: null },
  agentPipeline: { type: Array, default: () => [] },
  workflowSteps: { type: Array, default: () => [] },
  currentProcessingInfo: { type: String, default: null },
  progressMessages: { type: Array, default: () => [] },
});

defineEmits(["reconnect"]);

/** 连接状态展示文案（离线/重连提示经aria-live=polite播报，不使用Toast轰炸） */
const WS_STATUS_LABELS = {
  idle: "未连接",
  connecting: "连接中…",
  connected: "实时连接",
  offline: "网络离线，恢复后自动重连",
  reconnecting: "连接中断，正在重连…",
  failed: "连接失败",
  closed: "连接已关闭",
};

const WS_STATUS_TAG_TYPES = {
  idle: "info",
  connecting: "info",
  connected: "success",
  offline: "warning",
  reconnecting: "warning",
  failed: "danger",
  closed: "info",
};

const connectionStatusLabel = computed(
  () => WS_STATUS_LABELS[props.wsStatus] || WS_STATUS_LABELS.idle
);

const connectionTagType = computed(
  () => WS_STATUS_TAG_TYPES[props.wsStatus] || "info"
);

/** 连接中/重连中显示旋转图标 */
const isConnectionPending = computed(() =>
  ["connecting", "reconnecting"].includes(props.wsStatus)
);

/** 最后更新时间标签（无消息时不显示） */
const lastUpdateLabel = computed(() => {
  if (!props.wsLastMessageAt) return "";
  return `最后更新 ${formatTime(props.wsLastMessageAt)}`;
});

const messagesListRef = ref(null);

/** 过滤后的进度消息：仅保留有业务含义的中文日志，排除系统级技术消息 */
const filteredProgressMessages = computed(() => {
  return props.progressMessages.filter((msg) => {
    // 排除纯技术性的 status_change（任务状态变更通知）
    if (msg.type === "status_change") return false;
    // 排除纯技术性的 mode_decision（模式决策日志）
    if (msg.type === "mode_decision") return false;

    // 对于 task_progress 消息，只保留带有 agent_name 的（有业务含义的Agent进度）
    // 纯数字进度（如 "已完成 5/10 单元"）缺少 agent 标识，归为系统消息
    if (msg.type === "task_progress") {
      const hasAgentName = msg.agent_name || msg.data?.agent_name;
      if (!hasAgentName) return false;
    }

    // 排除无 agent_name 且无 agent_role 的消息（显示为"系统"的纯技术消息）
    const agentLabel = msg.data?.agent_name || msg.data?.agent_role;
    const hasMeaningfulMessage =
      msg.data?.message &&
      typeof msg.data.message === "string" &&
      msg.data.message.trim().length > 0;
    
    // 无 agent 标识且无有意义消息内容 → 过滤
    if (!agentLabel && !hasMeaningfulMessage) return false;

    return true;
  });
});

function getMessageTagType(msg) {
  const agentRole = msg.data?.agent_role;
  if (!agentRole) return "info";

  const typeMap = {
    structural: "primary",
    writer: "success",
    logic_editor: "warning",
    style_editor: "",
    compliance: "danger",
    assembler: "info",
  };
  return typeMap[agentRole] || "info";
}

function getAgentLabel(role) {
  if (AGENT_ROLE_LABELS[role]) {
    return AGENT_ROLE_LABELS[role].replace("Agent", "");
  }
  const agent = agentConfigs.find((a) => a.role === role);
  return agent?.label || role;
}

// 监听过滤后的进度消息，自动滚动到顶部
watch(
  () => filteredProgressMessages.value.length,
  () => {
    nextTick(() => {
      if (messagesListRef.value) {
        messagesListRef.value.scrollTop = 0;
      }
    });
  },
);
</script>

<style lang="scss" scoped>
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

    .connection-state {
      display: flex;
      align-items: center;
      gap: 8px;

      .last-update-time {
        font-size: 12px;
        color: #909399;
        white-space: nowrap;
      }

      .is-spinning {
        animation: spin 1s linear infinite;
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

  .agent-pipeline {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px 0;
    gap: 12px;
    flex-wrap: wrap;

    .pipeline-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      width: 90px;
      min-width: 80px;
      max-width: 110px;
      padding: 10px 6px;
      border-radius: 8px;
      background: #f5f7fa;
      transition: all 0.3s;
      box-sizing: border-box;

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
        flex-shrink: 0;

        .el-icon {
          font-size: 24px;
          color: #606266;
        }

        .pipeline-arrow {
          position: absolute;
          right: -16px;
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
        width: 100%;
        text-align: center;

        .pipeline-name {
          font-size: 12px;
          font-weight: 500;
          color: #303133;
          line-height: 1.3;
          // 自适应字体大小：长标签自动缩小
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          width: 100%;
          // 对于较长的Agent标签（如"合规审查Agent"），自动缩小字号
          max-lines: 1;
        }

        .el-tag {
          white-space: nowrap;
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
</style>
