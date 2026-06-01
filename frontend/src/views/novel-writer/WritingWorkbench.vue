<!--
  多Agent协作文学作品生成系统 - 写作工作台
  
  模块: writing-engine
  文件: WritingWorkbench.vue
  功能: 多Agent写作任务的核心工作台，整合项目准备、任务创建、进度监控、知识图谱等功能
  
  依赖关系:
      - API: /api/v1/writing-tasks/*, /api/v1/novel-writer/*
      - Store: writingTask
      - 组件: TaskCreationPanel, WorkbenchHeader, KnowledgeGraphDialog
  
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

    <!-- 主内容区 -->
    <div class="workbench-layout">
      <!-- 左侧边栏：始终可见 -->
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

      <!-- 右侧主区域：条件渲染 -->
      <div class="right-main-area">
        <!-- 无任务时：任务创建面板 -->
        <TaskCreationPanel
          v-if="!writingStore.currentTask"
          :project-data="projectData"
          :display-units="displayUnits"
          :unit-label="unitLabel"
          :actual-content-type="actualContentType"
          :is-novel-type="isNovelType"
          :duration-label="durationLabel"
          :duration-hint="durationHint"
          :task-form="taskForm"
          :project-total-units="projectTotalUnits"
          :current-unit-name="currentUnitName"
          :kb-status="kbStatus"
          :building-kb="buildingKb"
          :has-outline="hasOutline"
          :has-unit-summaries="hasUnitSummaries"
          :generating-directory="generatingDirectory"
          :is-loading="writingStore.loading"
          @upload-outline="showOutlineUploadDialog = true"
          @upload-unit-summaries="showUnitSummariesUploadDialog = true"
          @generate-directory="handleGenerateDirectory"
          @show-knowledge-graph="knowledgeGraphVisible = true"
          @show-consistency-report="consistencyReportVisible = true"
          @show-settings="showSettingsDialog = true"
          @build-kb="handleBuildKnowledgeBase"
          @rebuild-global-kb="handleBuildKnowledgeBase"
          @delete-kb="handleDeleteKnowledgeBase"
          @refresh-kb="loadKbStatus"
          @create-task="handleCreateTask"
          @open-agent-config="showAgentConfigDialog = true"
        />
        
        <!-- 有任务时：工作台主体 -->
        <div v-else class="workbench-main">
      <el-row :gutter="20">
        <!-- 左侧：单元场景浏览面板（扩大区域） -->
        <el-col :span="16">
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

        <!-- 右侧：实时进度面板（缩小区域） -->
        <el-col :span="8">
          <AgentProgressPanel
            :ws-connected="writingStore.wsConnected"
            :agent-pipeline="agentPipeline"
            :workflow-steps="workflowSteps"
            :current-processing-info="currentProcessingInfo"
            :progress-messages="writingStore.progressMessages"
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

      </div>
      <!-- 关闭 right-main-area -->
    </div>
    <!-- 关闭 workbench-layout -->

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
      :total-units="projectTotalUnits || writingStore.currentTask?.total_units || 0"
      v-model:unit-count="continueUnitCount"
      @confirm="handleContinue(continueUnitCount)"
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
      :consistency-update="writingStore.consistencyReport"
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
      :is-script-type="isScriptType"
      :script-style-names="scriptStyleData.selectedNames"
      :script-style-dimensions="scriptStyleData.dimensions"
      :script-style-intensity="scriptStyleData.intensity"
      v-model:thinking-mode-enabled="thinkingModeEnabled"
      v-model:thinking-reasoning-effort="thinkingReasoningEffort"
      v-model:thinking-save-dir="thinkingSaveDir"
      @show-style-detail="showStyleDocumentDetail = true"
      @delete-style-document="handleDeleteStyleDocument"
      @show-model-config="showModelConfigDialog = true"
      @show-style-selector="showStyleSelector = true"
      @show-script-style-selector="showScriptStyleSelector = true"
      @remove-style="removeSelectedStyle"
      @remove-script-style="styleMgmt.removeScriptStyle"
      @elimination-change="handleAiEliminationChange"
      @threshold-change="handleThresholdChange"
      @upload-success="handleStyleUploadSuccess"
      @upload-error="handleStyleUploadError"
      @thinking-mode-change="handleThinkingModeChange"
    />

    <!-- 文风选择器对话框 -->
    <StyleSelectorDialog
      v-model:visible="showStyleSelector"
      :initial-style-ids="selectedStyleIds"
      :initial-intensity="styleIntensity"
      @confirm="handleStyleSelectionConfirm"
    />

    <!-- 剧集风格选择器（复用创意生成模块） -->
    <SeriesStyleSelectorDialog
      v-if="actualContentType === 'series_script'"
      v-model:visible="showScriptStyleSelector"
      :initial-selected="{
        dimensions: scriptStyleData.dimensions,
        seriesSubType: scriptStyleData.seriesSubType || 'long'
      }"
      :initial-intensity="scriptStyleData.intensity"
      :initial-type="scriptStyleData.seriesSubType || 'long'"
      @confirm="handleScriptStyleConfirm"
    />

    <!-- 电影风格选择器（复用创意生成模块） -->
    <MovieStyleSelectorDialog
      v-if="actualContentType === 'movie_script'"
      v-model:visible="showScriptStyleSelector"
      :initial-selected="{
        dimensions: scriptStyleData.dimensions
      }"
      :initial-intensity="scriptStyleData.intensity"
      @confirm="handleScriptStyleConfirm"
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

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute } from "vue-router";
import { useWritingTaskStore } from "@/stores/writingTask";
import { novelWriterApi } from "@/api/novel-writer";
import { writingTaskApi } from "@/api/writing-task";
import { ElMessage, ElMessageBox } from "element-plus";
import TaskCreationPanel from "./components/TaskCreationPanel.vue";
import ProjectSetupPanel from "./components/ProjectSetupPanel.vue";
import KnowledgeBasePanel from "./components/KnowledgeBasePanel.vue";

// 导入子组件
import KnowledgeGraphDialog from "./components/KnowledgeGraphDialog.vue";
import ConsistencyReportDialog from "./components/ConsistencyReportDialog.vue";
import ContentQualityControl from "./components/ContentQualityControl.vue";
import StyleSelectorDialog from "./components/StyleSelectorDialog.vue";
import SeriesStyleSelectorDialog from "../generate/components/SeriesStyleSelectorDialog.vue";
import MovieStyleSelectorDialog from "../generate/components/MovieStyleSelectorDialog.vue";
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
  styleUploadAction, uploadHeaders,
  showScriptStyleSelector, handleScriptStyleConfirm,
  // 剧本风格状态（需顶层解构以保证模板中 ref 自动解包）
  scriptStyleData
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

// [修复] 基于实际项目数据计算 isScriptType，而非 useStyleManagement 内部永远为 null 的 projectData
const isScriptType = computed(() => {
  return actualContentType.value === 'series_script' || actualContentType.value === 'movie_script'
})

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
  loadProjectData,
  actualContentType,
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
  restoreTaskFormConfig,
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
const hasOutline = computed(() => !!projectData.value?.outline_content || !!projectData.value?.global_outline_content)
const activeUnits = ref([]);
const interrupting = ref(false);
const knowledgeGraphVisible = ref(false);
const consistencyReportVisible = ref(false);
const showSettingsDialog = ref(false);
const showQualityControlVisualization = ref(false);

// DeepSeek 思考模式
const thinkingModeEnabled = ref(false);
const thinkingReasoningEffort = ref('high');
const thinkingSaveDir = ref('./data/thinking_logs');

// 加载思考模式配置
async function loadThinkingModeConfig() {
  try {
    const { userConfigApi } = await import('@/api')
    const res = await userConfigApi.getThinkingModeConfig()
    if (res.data) {
      thinkingModeEnabled.value = res.data.enable_thinking ?? false
      thinkingReasoningEffort.value = res.data.reasoning_effort || 'high'
      thinkingSaveDir.value = res.data.thinking_save_dir || './data/thinking_logs'
    }
  } catch (error) {
    console.error('加载思考模式配置失败:', error)
  }
}

// 思考模式变更处理
async function handleThinkingModeChange(enabled) {
  try {
    const { userConfigApi } = await import('@/api')
    await userConfigApi.setThinkingModeConfig({
      enable_thinking: enabled,
      reasoning_effort: thinkingReasoningEffort.value,
      thinking_save_dir: thinkingSaveDir.value || './data/thinking_logs'
    })
  } catch (error) {
    console.error('保存思考模式配置失败:', error)
  }
}

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
  
  // 恢复用户上次的 Agent 配置（排除 API Key）
  restoreTaskFormConfig()
  
  // 加载风格文档信息（包含AI文风消除设置）
  await styleMgmt.loadStyleDocumentInfo()
  
  // 加载思考模式配置
  await loadThinkingModeConfig()
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
      // 恢复用户上次的 Agent 配置（排除 API Key）
      restoreTaskFormConfig()
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

// 主布局：左侧边栏 + 右侧内容区
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
