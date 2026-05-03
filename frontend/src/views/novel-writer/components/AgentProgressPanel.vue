<template>
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
            <component :is="agent.icon" />
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
            <el-icon v-else><component :is="step.icon" /></el-icon>
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
          v-for="(msg, idx) in progressMessages"
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
          v-if="progressMessages.length === 0"
          description="暂无进度消息"
          :image-size="60"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, watch, nextTick } from "vue";
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

const props = defineProps({
  wsConnected: { type: Boolean, default: false },
  agentPipeline: { type: Array, default: () => [] },
  workflowSteps: { type: Array, default: () => [] },
  currentProcessingInfo: { type: String, default: null },
  progressMessages: { type: Array, default: () => [] },
});

const messagesListRef = ref(null);

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

// 监听进度消息，自动滚动到顶部
watch(
  () => props.progressMessages.length,
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
</style>
