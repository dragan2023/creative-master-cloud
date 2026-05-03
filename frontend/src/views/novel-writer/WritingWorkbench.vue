<!--
  多Agent协作文学作品生成系统 - 写作工作台
  
  模块: writing-engine
  文件: WritingWorkbench.vue
  功能: 多Agent写作任务的核心工作台，整合项目准备、任务创建、进度监控、知识图谱等功能
  
  依赖关系:
      - API: /api/v1/writing-tasks/*, /api/v1/novel-writer/*
      - Store: writingTask
      - 组件: ProjectSetupPanel, KnowledgeGraphDialog
  
  创建时间: 2026-03-28
  最后修改: 2026-03-30
  版本: 2.0.0
  
  [2026-03-28] 多Agent重构: Agent角色名与后端AgentRole对齐，添加中文显示名映射
  [2026-03-30] 功能整合: 合并项目详情页功能，添加大纲上传、知识图谱、左侧边栏布局
-->
<template>
  <div class="writing-workbench">
    <WorkbenchHeader
      v-model:show-continue-dialog="showContinueDialog"
      :project-title="projectData?.title || props.projectTitle || '写作工作台'"
      :content-type="actualContentType"
      :unit-label="unitLabel"
      :current-task="writingStore.currentTask"
      :progress="writingStore.progress"
      :is-completed="writingStore.isCompleted"
      :is-running="writingStore.isRunning"
      :can-resume="writingStore.canResume"
      :is-loading="writingStore.loading"
      :ws-connected="writingStore.wsConnected"
      :formatted-duration="formattedDuration"
      :display-unit-count="displayUnits.length"
      :total-tokens="writingStore.currentTask?.total_tokens || 0"
      :total-cost="writingStore.currentTask?.total_cost || 0"
      :completed-units="writingStore.currentTask?.completed_units || 0"
      :total-units="writingStore.currentTask?.total_units || 0"
      :has-generated-content="hasGeneratedContent"
      :can-continue-generate="canContinueGenerate"
      :interrupting="interrupting"
      @interrupt="handleInterrupt"
      @resume="handleResume"
      @delete="handleDelete"
      @export="handleExport"
      @open-quality-control="showQualityControlVisualization = true"
    />

    <!-- 主内容区（无任务时显示）-->
    <div v-if="!writingStore.currentTask" class="task-creation">
      <div class="workbench-layout">
        <!-- 左侧边栏：项目准备面板-->
        <div class="left-sidebar">
          <ProjectSetupPanel
            :project="projectData"
            :chapters="displayUnits"
            :unit-label="unitLabel"
            :generating-directory="generatingDirectory"
            @upload-outline="showOutlineUploadDialog = true"
            @upload-unit-summaries="showUnitSummariesUploadDialog = true"
            @generate-directory="handleGenerateDirectory"
            @show-knowledge-graph="knowledgeGraphVisible = true"
            @show-consistency-report="consistencyReportVisible = true"
            @show-settings="showSettingsDialog = true"
          />
          <!-- 架构优化：移除:chapter-outlines, @generate-chapter-outlines, @view-chapter-outlines -->
          
          <!-- 知识库面板 -->
          <KnowledgeBasePanel
            :kb-status="kbStatus"
            :has-outline="hasOutline"
            :building="buildingKb"
            @build="handleBuildKnowledgeBase"
            @rebuild-global="handleBuildKnowledgeBase"
            @show-graph="knowledgeGraphVisible = true"
            @delete="handleDeleteKnowledgeBase"
            @refresh="loadKbStatus"
          />
        </div>

        <!-- 右侧主区域-->
        <div class="right-main-area">
          <!-- 单元概述缺失提示（仅小说类型显示）-->
          <el-alert
            v-if="
              !hasUnitSummaries &&
              (actualContentType === 'novel')
            "
            type="warning"
            :closable="false"
            show-icon
            class="unit-summaries-alert"
          >
            <template #title>
              <span>缺少单元概述数据</span>
            </template>
            <div class="alert-content">
              <p>章节详细大纲功能需要先上传单元概述数据</p>
              <p style="color: #909399; font-size: 12px; margin-top: 4px">
                单元概述可从“创意生成”板块导出后上传，或直接在下方输入。
              </p>
              <el-button
                type="primary"
                size="small"
                style="margin-top: 8px"
                @click="showUnitSummariesUploadDialog = true"
              >
                <el-icon><Upload /></el-icon>
                上传单元概述
              </el-button>
            </div>
          </el-alert>

          <!-- 任务配置面板 -->
          <el-card shadow="hover" class="creation-card">
            <template #header>
              <div class="card-header">
                <span class="header-title">
                  <el-icon><EditPen /></el-icon>
                  正文生成配置
                </span>
                <div class="header-actions">
                  <el-button
                    type="primary"
                    @click="handleCreateTask"
                    :loading="writingStore.loading"
                  >
                    <el-icon><VideoPlay /></el-icon>
                    开始生成正文
                  </el-button>
                  <el-button
                    size="small"
                    type="primary"
                    plain
                    @click="showAgentConfigDialog = true"
                  >
                    <el-icon><Setting /></el-icon>
                    Agent配置
                  </el-button>
                </div>
              </div>
            </template>

            <!-- 知识库推荐提示 -->
            <el-alert
              v-if="!kbStatus || kbStatus.status !== 'ready'"
              type="info"
              :closable="true"
              show-icon
              style="margin-bottom: 12px"
            >
              <template #title>
                推荐构建知识库以提升生成质量
              </template>
              <template #default>
                知识库包含人物设定、世界观、历史事件等，可增强正文生成的一致性和质量。
                请在左侧"知识库"面板中点击"构建知识库"按钮。
              </template>
            </el-alert>

            <!-- 配置提示 -->
            <el-alert
              type="info"
              :closable="false"
              show-icon
              style="margin-bottom: 12px"
            >
              <template #title>
                点击 "Agent配置" 按钮可配置模型参数和并发设置
              </template>
            </el-alert>

            <!-- 架构优化：移除生成模式选择器，固定使用direct模式 -->

            <!-- 基本参数 -->
            <el-form :model="taskForm" label-width="80px" class="task-form">
              <el-row :gutter="20">
                <!-- 字数限制：仅小说类型显示 -->
                <el-col :span="12" v-if="isNovelType">
                  <el-form-item label="每章字数">
                    <el-input-number
                      v-model="taskForm.words_per_chapter"
                      :min="500"
                      :max="10000"
                      :step="500"
                      style="width: 150px"
                      controls-position="right"
                    />
                  </el-form-item>
                </el-col>
                <!-- 时长提示：剧本类型显示-->
                <el-col :span="12" v-else>
                  <el-form-item :label="durationLabel">
                    <el-text type="info" size="small">
                      {{ durationHint }}
                    </el-text>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="并发数">
                    <el-input-number
                      v-model="taskForm.concurrency"
                      :min="1"
                      :max="10"
                      style="width: 150px"
                      controls-position="right"
                    />
                    <span class="form-hint">写手并发数</span>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <!-- 架构优化：已移除单元大纲生成面板 -->

          <!-- 单元列表预览 -->
          <el-card class="units-panel" shadow="hover">
            <template #header>
              <div class="panel-header">
                <span>
                  <el-icon><List /></el-icon>
                  单元列表（正文生成）
                </span>
                <el-tag type="info" size="small">
                  {{ displayUnits.length }} {{ unitLabel }}
                </el-tag>
              </div>
            </template>

            <!-- 参数配置区：起始单元和生成数量（正文生成用） -->
            <div class="unit-params-bar">
              <div class="param-item-inline">
                <span class="param-label">起始单元</span>
                <div class="param-input-wrapper">
                  <el-input-number
                    v-model="taskForm.start_from"
                    :min="1"
                    :max="projectTotalUnits || 999"
                    style="width: 90px"
                    controls-position="right"
                    size="small"
                  />
                  <span class="unit-name-badge" v-if="currentUnitName">
                    {{ currentUnitName }}
                  </span>
                </div>
              </div>
              <div class="param-item-inline">
                <span class="param-label">生成数量</span>
                <el-input-number
                  v-model="taskForm.unit_count"
                  :min="1"
                  :max="projectTotalUnits || 100"
                  placeholder="全部"
                  style="width: 100px"
                  size="small"
                  controls-position="right"
                />
                <span class="param-hint">留空=全部</span>
              </div>
            </div>

            <div class="units-preview-list">
              <div
                v-for="unit in displayUnits"
                :key="unit.unit_index"
                class="unit-preview-item"
                :class="{
                  'is-selected': unit.unit_index === taskForm.start_from,
                }"
                @click="taskForm.start_from = unit.unit_index"
              >
                <span class="unit-index">#{{ unit.unit_index }}</span>
                <span class="unit-name" :title="unit.unit_title">
                  {{ unit.unit_title || `${unit.unit_index}${unitLabel}` }}
                </span>
              </div>
              <el-empty
                v-if="displayUnits.length === 0"
                description="暂无单元数据，请先在项目中创建大纲"
                :image-size="60"
              />
            </div>
          </el-card>
        </div>
      </div>
    </div>

    <!-- 主内容区（有任务时）-->
    <div v-else class="workbench-main">
      <el-row :gutter="20">
        <!-- 左侧：实时进度面板-->
        <el-col :span="14">
          <AgentProgressPanel
            :ws-connected="writingStore.wsConnected"
            :agent-pipeline="agentPipeline"
            :workflow-steps="workflowSteps"
            :current-processing-info="currentProcessingInfo"
            :progress-messages="writingStore.progressMessages"
          />
        </el-col>

        <!-- 右侧：单元场景浏览面板 -->
        <el-col :span="10">
          <UnitListPanel
            v-model:active-units="activeUnits"
            :display-units="displayUnits"
            :unit-label="unitLabel"
            :loading-scenes="loadingScenes"
            :scenes="writingStore.scenes"
            @expand-unit="handleUnitExpand"
            @export-unit="handleExportUnit"
            @scene-click="handleSceneClick"
            @show-knowledge-graph="knowledgeGraphVisible = true"
            @show-consistency-report="consistencyReportVisible = true"
            @show-quality-control="showQualityControlVisualization = true"
            @show-unit-qc="handleShowUnitQC"
          />
        </el-col>
      </el-row>

      <!-- 底部：统计仪表板 -->
      <StatsDashboard
        :stats="writingStore.stats"
        :formatted-duration="writingStore.formattedDuration"
        :current-task="writingStore.currentTask"
      />
    </div>

    <!-- 场景内容查看对话框-->
    <SceneContentDialog
      v-model:visible="sceneDialogVisible"
      :scene="selectedScene"
      :title="selectedSceneTitle"
      :status-type="getSceneStatusType(selectedScene?.status)"
      :status-label="getSceneStatusLabel(selectedScene?.status)"
    />

    <!-- 继续生成对话框-->
    <ContinueGenerateDialog
      v-model:visible="showContinueDialog"
      :completed-units="writingStore.currentTask?.completed_units || 0"
      v-model:unit-count="continueUnitCount"
      @confirm="handleContinue"
      @cancel="showContinueDialog = false"
    />

    <!-- Agent配置对话框-->
    <AgentConfigDialog
      v-model:visible="showAgentConfigDialog"
      v-model:concurrency="taskForm.concurrency"
      v-model:agent-config-ids="taskForm.agent_config_ids"
      v-model:agent-temps="taskForm.agent_temps"
      :model-configs="modelConfigs"
      :quick-apply-config-id="quickApplyConfigId"
      @quick-apply="(configId) => applyToAllAgents(configId)"
    />

    <!-- 单元概述上传对话框-->
    <UnitSummariesUploadDialog
      v-model:visible="showUnitSummariesUploadDialog"
      v-model:uploadMode="unitSummariesUploadMode"
      v-model:unitSummariesInput="unitSummariesInput"
      v-model:globalOutlineInput="globalOutlineInput"
      :uploading="uploadingUnitSummaries"
      @upload-file="handleUploadUnitSummariesFile"
      @upload-content="handleUploadUnitSummariesContent"
      @cancel="handleCancelUnitSummariesUpload"
    />

    <!-- 大纲上传弹窗 -->
    <OutlineUploadDialog
      v-model:visible="showOutlineUploadDialog"
      :uploading="uploadingOutline"
      @upload="handleUploadOutline"
    />

    <!-- 知识图谱弹窗 -->
    <KnowledgeGraphDialog
      v-model:visible="knowledgeGraphVisible"
      :project-id="projectId"
      :total-units="projectTotalUnits"
      :unit-label="unitLabel"
    />

    <!-- 一致性检查报告弹窗-->
    <ConsistencyReportDialog
      v-model:visible="consistencyReportVisible"
      :project-id="projectId"
      :total-units="projectTotalUnits"
      :unit-label="unitLabel"
    />

    <!-- 实时质控仪表盘弹窗(v2.2重构 - 正文质控组件) -->
    <ContentQualityControl
      v-model:visible="showQualityControlVisualization"
      :project-id="projectId"
      :task-id="writingStore.currentTask?.id"
      :units="writingStore.units"
      :project="projectData"
      @qc-complete="handleQCComplete"
      @unit-updated="handleQCUnitUpdated"
    />

    <!-- 项目设置弹窗 -->
    <SettingsDialog
      v-model:visible="showSettingsDialog"
      :project-data="projectData"
      :style-document-info="styleDocumentInfo"
      v-model:ai-elimination-enabled="aiEliminationEnabled"
      v-model:ai-elimination-threshold="aiEliminationThreshold"
      :selected-style-ids="selectedStyleIds"
      :selected-style-names="selectedStyleNames"
      :style-intensity="styleIntensity"
      :upload-action="styleUploadAction"
      :upload-headers="uploadHeaders"
      @show-style-detail="showStyleDocumentDetail = true"
      @delete-style-document="handleDeleteStyleDocument"
      @show-model-config="showModelConfigDialog = true"
      @show-style-selector="showStyleSelector = true"
      @remove-style="removeSelectedStyle"
      @elimination-change="handleAiEliminationChange"
      @threshold-change="handleThresholdChange"
      @upload-success="handleStyleUploadSuccess"
      @upload-error="handleStyleUploadError"
    />

    <!-- 文风选择器对话框 -->
    <StyleSelectorDialog
      v-model:visible="showStyleSelector"
      :initial-style-ids="selectedStyleIds"
      :initial-intensity="styleIntensity"
      @confirm="handleStyleSelectionConfirm"
    />

    <!-- 风格文档详情弹窗 -->
    <StyleDocumentDetailDialog
      v-model:visible="showStyleDocumentDetail"
      :style-document-info="styleDocumentInfo"
      @refresh="handleRefreshStyleDocument"
    />

    <!-- 模型配置弹窗 -->
    <ModelConfigDialog
      v-model:visible="showModelConfigDialog"
    />

    <!-- 架构优化：已移除章节大纲预览对话框和已生成大纲列表对话框 -->
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute } from "vue-router";
import { useWritingTaskStore } from "@/stores/writingTask";
import { novelWriterApi } from "@/api/novel-writer";
import { writingTaskApi } from "@/api/writing-task";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  VideoPlay,
  EditPen,
  List,
  Setting,
  Upload,
} from "@element-plus/icons-vue";

// 导入子组件
import ProjectSetupPanel from "./components/ProjectSetupPanel.vue";
import KnowledgeBasePanel from "./components/KnowledgeBasePanel.vue";
import KnowledgeGraphDialog from "./components/KnowledgeGraphDialog.vue";
import ConsistencyReportDialog from "./components/ConsistencyReportDialog.vue";
import ContentQualityControl from "./components/ContentQualityControl.vue";
import StyleSelectorDialog from "./components/StyleSelectorDialog.vue";
import AgentConfigDialog from "./components/AgentConfigDialog.vue";
import ModelConfigDialog from "./components/ModelConfigDialog.vue";
import UnitSummariesUploadDialog from "./components/UnitSummariesUploadDialog.vue";
import OutlineUploadDialog from "./components/OutlineUploadDialog.vue";
import SceneContentDialog from "./components/SceneContentDialog.vue";
import ContinueGenerateDialog from "./components/ContinueGenerateDialog.vue";
import StyleDocumentDetailDialog from "./components/StyleDocumentDetailDialog.vue";
import SettingsDialog from "./components/SettingsDialog.vue";
import WorkbenchHeader from "./components/WorkbenchHeader.vue";
import AgentProgressPanel from "./components/AgentProgressPanel.vue";
import StatsDashboard from "./components/StatsDashboard.vue";
import UnitListPanel from "./components/UnitListPanel.vue";
import { AGENT_ROLE_LABELS, agentConfigs } from "./config/agentConfig";
import { getContentTypeLabel, getContentTypeTagType, getStatusType, getStatusLabel, getSceneStatusType, getSceneStatusLabel } from "./utils/contentHelpers";
import { useStyleManagement } from './composables/useStyleManagement'
import { useWorkbenchUnits } from './composables/useWorkbenchUnits'
import { useWorkbenchTask } from './composables/useWorkbenchTask'
import { useAgentPipeline } from './composables/useAgentPipeline'

// ==================== Props ====================
const props = defineProps({
  projectId: {
    type: [Number, String],
    default: null,
  },
  projectTotalUnits: {
    type: Number,
    default: 0,
  },
  unitSummaries: {
    type: Object,
    default: () => ({}),
  },
  contentType: {
    type: String,
    default: "novel",
  },
  projectType: {
    type: String,
    default: "novel",
  },
  chapters: {
    type: Array,
    default: () => [],
  },
  projectTitle: {
    type: String,
    default: "",
  },
  projectData: {
    type: Object,
    default: () => ({}),
  },
  chapterOutlines: {
    type: Object,
    default: () => ({}),
  },
});

// ==================== Emits ====================
const emit = defineEmits(["refresh", "update-project"]);

// ==================== Store ====================
const writingStore = useWritingTaskStore();

// ==================== Route ====================
const route = useRoute();

// 计算项目ID（优先使用props，其次从路由获取）
const projectId = computed(() => {
  if (props.projectId) return Number(props.projectId);
  if (route.params.id) return Number(route.params.id);
  return null;
});

// ==================== 1. 文风管理（组合式函数）====================
const styleMgmt = useStyleManagement(projectId, ref(null))
const {
  showModelConfigDialog,
  styleDocumentInfo, showStyleDocumentDetail,
  aiEliminationEnabled, aiEliminationThreshold,
  showStyleSelector, selectedStyleIds, selectedStyleNames,
  styleIntensity, styleGuide,
  styleUploadAction, uploadHeaders
} = styleMgmt

/**
 * 处理文风选择确认
 */
function handleStyleSelectionConfirm(data) {
  styleMgmt.handleStyleSelectionConfirm(data)
}

function removeSelectedStyle(index) {
  styleMgmt.removeSelectedStyle(index)
}

// ==================== 2. 单元列表和项目数据管理（组合式函数）====================
const wbUnits = useWorkbenchUnits(props, writingStore, emit, projectId)
const {
  localProjectData,
  loadingProject,
  loadingScenes,
  sceneDialogVisible,
  selectedScene,
  selectedUnit,
  actualContentType,
  unitLabel,
  isNovelType,
  durationLabel,
  durationHint,
  projectData,
  projectTotalUnits,
  unitSummaries,
  hasUnitSummaries,
  currentUnitName,
  displayUnits,
  hasGeneratedContent,
  canContinueGenerate,
  selectedSceneTitle,
  loadProjectData,
  handleUnitExpand,
  getScenes,
  handleExportUnit,
  handleSceneClick,
  handleUnitItemClick,
  getUnitStatusType,
  getUnitStatusLabel
} = wbUnits

// 监听项目数据加载完成，恢复文风配置
watch(localProjectData, (newData) => {
  if (newData && styleMgmt.restoreStyleConfigFromProject) {
    // 更新 styleMgmt 的内部 projectData 引用
    styleMgmt.restoreStyleConfigFromProject(newData)
  }
}, { immediate: true })

// ==================== 3. 任务创建和管理（组合式函数）====================
const wbTask = useWorkbenchTask({
  writingStore,
  projectId,
  styleMgmt,
  projectTotalUnits,
  unitSummaries,
  chapters: displayUnits,
  emit,
  loadProjectData
})
const {
  taskForm,
  showOutlineUploadDialog,
  uploadingOutline,
  showUnitSummariesUploadDialog,
  unitSummariesUploadMode,
  unitSummariesInput,
  globalOutlineInput,
  uploadingUnitSummaries,
  generatingDirectory,
  showContinueDialog,
  continueUnitCount,
  // 知识库状态（P1改造新增）
  kbStatus,
  buildingKb,
  handleCreateTask,
  handleInterrupt,
  handleResume,
  handleContinue,
  handleUploadOutline,
  handleGenerateDirectory,
  handleBuildKnowledgeBase,
  handleDeleteKnowledgeBase,
  loadKbStatus,
  handleCancelUnitSummariesUpload,
  handleUploadUnitSummariesFile,
  handleUploadUnitSummariesContent, // 修复：与useWorkbenchTask返回的函数名一致
  handleDelete,
  handleExport,
} = wbTask

// ==================== 4. Agent流水线和工作流（组合式函数）====================
const wbPipeline = useAgentPipeline(writingStore, taskForm)
const {
  showAgentConfigDialog,
  quickApplyConfigId,
  availableProviders,
  loadingProviders,
  modelConfigs,
  loadingConfigs,
  formattedDuration,
  agentPipeline,
  currentProcessingInfo,
  workflowSteps,
  loadProviders,
  loadModelConfigs,
  onModelConfigChange,
  applyToAllAgents,
  handleQuickApply,
  onProviderChange,
  getProviderModels
} = wbPipeline

// ==================== 内联状态（UI相关，不适合提取）====================
const hasOutline = computed(() => !!projectData.value?.outline_content)
const activeCollapse = ref(["agents"]);
const activeUnits = ref([]);
const interrupting = ref(false);
const knowledgeGraphVisible = ref(false);
const consistencyReportVisible = ref(false);
const showSettingsDialog = ref(false);
const showQualityControlVisualization = ref(false);

// ==================== 质控相关处理 ====================

/**
 * 显示指定单元的质控报告
 */
function handleShowUnitQC(unitIndex) {
  showQualityControlVisualization.value = true
  // 新的ContentQualityControl组件会自动处理单元选择
}

/**
 * 批量质控完成处理
 */
function handleQCComplete(result) {
  console.log('[WritingWorkbench] 批量质控完成:', result)
  // 刷新项目数据以获取最新质控状态
  if (result && result.completed > 0) {
    loadProjectData()
  }
}

/**
 * 单元质控更新处理
 */
function handleQCUnitUpdated(data) {
  console.log('[WritingWorkbench] 单元质控更新:', data.unitIndex)
  // 单元数据已通过WebSocket实时更新，无需额外处理
}

// 生成任务AI文风消除开关变更
function handleTaskAiEliminationChange(value) {
  if (styleDocumentInfo.value) {
    styleMgmt.handleAiEliminationChange(value);
  }
}

// 上传请求头（已移至 useStyleManagement）

// ==================== Lifecycle ====================

onMounted(async () => {
  // 并行加载项目数据和任务数据（减少等待时间）
  if (!props.projectId && route.params.id) {
    await Promise.all([
      loadProjectData(),
      writingStore.fetchCurrentTask(projectId.value)
    ])
  } else {
    // 如果有 projectId prop，至少加载当前任务
    await writingStore.fetchCurrentTask(projectId.value)
  }
  
  // 加载预配置模型列表和可用Provider（并行）
  await Promise.all([
    loadModelConfigs(),
    loadProviders()
  ])
  
  // 加载风格文档信息（包含AI文风消除设置）
  await styleMgmt.loadStyleDocumentInfo()
})

onUnmounted(() => {
  // 断开WebSocket连接
  writingStore.disconnectWebSocket();
});

// 监听项目ID变化（路由切换时）
watch(
  () => route.params.id,
  async (newId) => {
    if (newId && !props.projectId) {
      // 并行加载项目数据和任务
      await Promise.all([
        loadProjectData(),
        writingStore.fetchCurrentTask(projectId.value)
      ])
      // 重新加载风格文档信息
      await styleMgmt.loadStyleDocumentInfo()
    }
  },
)

</script>

<style lang="scss" scoped>
.writing-workbench {
  padding: 20px;
  min-height: 600px;
}

// 任务创建面板 - 工作台布局
.task-creation {
  .workbench-layout {
    display: flex;
    gap: 20px;
    min-height: 600px;
  }

  .left-sidebar {
    width: 350px;
    flex-shrink: 0;
    min-width: 300px;
    position: sticky;
    top: 20px;
    max-height: calc(100vh - 40px);
    overflow-y: auto;
  }

  .right-main-area {
    flex: 1;
    min-width: 0;
  }

  .creation-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .header-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 16px;
        font-weight: 600;

        .el-icon {
          color: #409eff;
        }
      }

      .header-actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }
  }

  .task-form {
    padding: 10px 0;

    .form-hint {
      font-size: 12px;
      color: #909399;
      margin-left: 8px;
    }
  }
}

// 单元参数配置区
.unit-params-bar {
  display: flex;
  gap: 16px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;

  .param-item-inline {
    display: flex;
    align-items: center;
    gap: 8px;

    .param-label {
      font-size: 13px;
      color: #606266;
      white-space: nowrap;
    }

    .param-input-wrapper {
      display: flex;
      align-items: center;
      gap: 8px;

      .unit-name-badge {
        padding: 2px 8px;
        background: #f0f9eb;
        border-radius: 4px;
        font-size: 12px;
        color: #67c23a;
        white-space: nowrap;
        max-width: 120px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }

    .param-hint {
      font-size: 11px;
      color: #909399;
    }
  }
}

// 单元预览列表
.units-preview-list {
  max-height: 500px;
  overflow-y: auto;

  .unit-preview-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    margin-bottom: 8px;
    background: #f5f7fa;
    border-radius: 6px;
    transition: all 0.2s;

    &:hover {
      background: #ecf5ff;
    }

    &.is-selected {
      background: #f0f9eb;
      border-left: 3px solid #67c23a;
    }

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
      font-size: 13px;
      color: #303133;
    }
  }
}

// 主内容区（有任务时）
.workbench-main {
  // 容器本身，子组件交由各自管理
}

// 单元概述缺失提示
.unit-summaries-alert {
  margin-bottom: 16px;

  .alert-content {
    p {
      margin: 0;
      line-height: 1.6;
    }
  }
}

// 项目设置弹窗中的模型配置入口
.settings-model-config {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;

  .config-info {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #606266;

    .el-icon {
      font-size: 18px;
      color: #409eff;
    }
  }
}

// 响应式
@media (max-width: 1200px) {
  .workbench-main {
    .el-col {
      width: 100%;
      margin-bottom: 20px;
    }
  }
}

</style>
