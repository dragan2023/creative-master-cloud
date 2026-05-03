<template>
  <div class="workbench-header">
    <!-- 项目标题区域 -->
    <div class="project-title-section">
      <el-tag
        :type="getContentTypeTagType(contentType)"
        size="large"
        effect="plain"
      >
        {{ getContentTypeLabel(contentType) }}
      </el-tag>
      <span class="project-title">{{ projectTitle || "写作工作台" }}</span>
    </div>

    <!-- 任务状态信息（有任务时显示） -->
    <div v-if="currentTask" class="task-status-section">
      <el-tag
        :type="getStatusType(currentTask?.status)"
        size="large"
        effect="dark"
      >
        {{ getStatusLabel(currentTask?.status) }}
      </el-tag>
      <div class="progress-wrapper">
        <el-progress
          :percentage="progress"
          :stroke-width="10"
          :status="isCompleted ? 'success' : ''"
        />
        <span class="progress-text">
          {{ completedUnits || 0 }} / {{ totalUnits || 0 }} 单元
        </span>
      </div>
      <div class="quick-stats">
        <el-tooltip content="总耗时">
          <span class="stat-item">
            <el-icon><Timer /></el-icon>
            {{ formattedDuration }}
          </span>
        </el-tooltip>
        <el-tooltip content="Token消耗">
          <span class="stat-item">
            <el-icon><Coin /></el-icon>
            {{ formatNumber(totalTokens || 0) }}
          </span>
        </el-tooltip>
        <el-tooltip content="预估费用">
          <span class="stat-item">
            <el-icon><Money /></el-icon>
            ${{ (totalCost || 0).toFixed(4) }}
          </span>
        </el-tooltip>
      </div>
    </div>
    <!-- 单元概览（无任务时显示） -->
    <div v-else class="unit-overview-section">
      <el-tag type="info" size="large" effect="plain">
        <el-icon><List /></el-icon>
        共 {{ displayUnitCount }} {{ unitLabel }}
      </el-tag>
      <span class="overview-hint">选择起始单元和生成数量，开始创作</span>
    </div>
    <div class="task-actions">
      <!-- 任务控制按钮（有任务时显示） -->
      <template v-if="currentTask">
        <el-button
          v-if="isRunning"
          type="warning"
          @click="$emit('interrupt')"
          :loading="interrupting"
        >
          <el-icon><VideoPause /></el-icon>
          中断
        </el-button>
        <el-button
          v-if="canResume"
          type="success"
          @click="$emit('resume')"
          :loading="isLoading"
        >
          <el-icon><VideoPlay /></el-icon>
          续传
        </el-button>
        <el-button
          v-if="isCompleted"
          type="primary"
          @click="$emit('update:showContinueDialog', true)"
          :disabled="!canContinueGenerate"
        >
          <el-icon><Plus /></el-icon>
          继续生成
        </el-button>
        <el-button
          v-if="!isRunning"
          type="danger"
          plain
          @click="$emit('delete')"
        >
          <el-icon><Delete /></el-icon>
          删除
        </el-button>
      </template>
      <!-- 下载全文按钮（始终显示） -->
      <el-button
        type="success"
        @click="$emit('export')"
        :disabled="!hasGeneratedContent"
      >
        <el-icon><Download /></el-icon>
        下载全文
      </el-button>
      <!-- 质控检测按钮 -->
      <el-button type="warning" @click="$emit('open-quality-control')">
        <el-icon><Monitor /></el-icon>
        质控检测
      </el-button>
    </div>
  </div>
</template>

<script setup>
import {
  Timer,
  Coin,
  Money,
  List,
  VideoPause,
  VideoPlay,
  Plus,
  Delete,
  Download,
  Monitor,
} from "@element-plus/icons-vue";
import {
  getContentTypeTagType,
  getContentTypeLabel,
  getStatusType,
  getStatusLabel,
  formatNumber,
} from "../utils/contentHelpers";

const props = defineProps({
  projectTitle: { type: String, default: "" },
  contentType: { type: String, default: "novel" },
  unitLabel: { type: String, default: "章" },
  currentTask: { type: Object, default: null },
  progress: { type: Number, default: 0 },
  isCompleted: { type: Boolean, default: false },
  isRunning: { type: Boolean, default: false },
  canResume: { type: Boolean, default: false },
  isLoading: { type: Boolean, default: false },
  wsConnected: { type: Boolean, default: false },
  formattedDuration: { type: String, default: "00:00:00" },
  displayUnitCount: { type: Number, default: 0 },
  totalTokens: { type: Number, default: 0 },
  totalCost: { type: Number, default: 0 },
  completedUnits: { type: Number, default: 0 },
  totalUnits: { type: Number, default: 0 },
  hasGeneratedContent: { type: Boolean, default: false },
  canContinueGenerate: { type: Boolean, default: false },
  interrupting: { type: Boolean, default: false },
  showContinueDialog: { type: Boolean, default: false },
});

defineEmits([
  "interrupt",
  "resume",
  "delete",
  "export",
  "open-quality-control",
  "update:showContinueDialog",
]);
</script>

<style lang="scss" scoped>
.workbench-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);

  .project-title-section {
    display: flex;
    align-items: center;
    gap: 12px;

    .project-title {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
  }

  .task-status-section {
    display: flex;
    align-items: center;
    gap: 20px;
    flex: 1;

    .progress-wrapper {
      flex: 1;
      max-width: 300px;

      .progress-text {
        display: block;
        margin-top: 4px;
        font-size: 12px;
        color: #606266;
        text-align: center;
      }
    }

    .quick-stats {
      display: flex;
      gap: 16px;

      .stat-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: #606266;

        .el-icon {
          font-size: 14px;
          color: #409eff;
        }
      }
    }
  }

  .task-actions {
    display: flex;
    gap: 10px;
  }

  .unit-overview-section {
    display: flex;
    align-items: center;
    gap: 16px;
    flex: 1;

    .overview-hint {
      font-size: 13px;
      color: #909399;
    }
  }
}
</style>
