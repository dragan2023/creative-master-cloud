<template>
  <div class="project-detail-page" v-loading="loading">
    <!-- 任务状态条 -->
    <TaskStatusBar v-show="taskStore.hasTask" :on-cancel="handleCancelTask" />

    <!-- 页面头部 -->
    <ProjectHeader
      :project="project"
      :on-back="() => router.back()"
      :on-settings="showSettingsDialog"
      :on-export="showExportDialog"
      :on-sync-content-status="handleSyncContentStatus"
      :on-clear-all-outlines="handleClearAllOutlines"
      :on-clear-all-content="handleClearAllContent"
      :on-clear-all="handleClearAll"
      :on-delete="handleDelete"
    />

    <!-- 项目信息卡片 -->
    <el-row :gutter="16" v-if="project">
      <el-col :span="14">
        <el-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>{{ unitLabel }}列表</span>
              <div class="header-actions">
                <el-button size="small" @click="showOutlineUpload" v-if="!project.outline_content">
                  上传大纲
                </el-button>
              </div>
            </div>
          </template>

          <!-- 大纲上传区域 -->
          <OutlineUploadSection
            :project="project"
            :chapters="chapters"
            :unit-label="unitLabel"
            :loading="generatingDirectory"
            :on-upload="handleOutlineUpload"
            :on-generate-directory="handleGenerateDirectory"
            v-model:unit-count="manualUnitCount"
          />

          <!-- 单元概述区域 -->
          <UnitSummariesSection
            :project="project"
            :quality-control-loading="qualityControlLoading"
            :on-show-upload-dialog="() => showUnitSummariesUploadDialog = true"
            :on-quality-control="handleTriggerQualityControl"
          />

          <!-- 详细大纲区域（根据内容类型显示不同区域） -->
          <DetailedOutlineSection
            :content-type="project.content_type"
            :chapters="chapters"
            :episode-outlines="episodeOutlines"
            :chapter-outlines="chapterOutlines"
            :scene-outlines="sceneOutlines"
            :generated-episode-count="generatedEpisodeCount"
            :total-episode-count="totalEpisodeCount"
            :generated-chapter-outline-count="generatedChapterOutlineCount"
            :total-chapter-outline-count="totalChapterOutlineCount"
            :generated-scene-outline-count="generatedSceneOutlineCount"
            :total-scene-outline-count="totalSceneOutlineCount"
            :generating-episode-outlines="generatingEpisodeOutlines"
            :generating-chapter-outlines="generatingChapterOutlines"
            :generating-scene-outlines="generatingSceneOutlines"
            :task-store="taskStore"
            :generating="generating"
            :selected-episode="selectedEpisode"
            :generating-single-episode="generatingSingleEpisode"
            :generating-single-chapter-outline="generatingSingleChapterOutline"
            :generating-single-scene-outline="generatingSingleSceneOutline"
            :selected-chapter="selectedChapter"
            :selected-scene="selectedScene"
            :editing-episode-title="editingEpisodeTitle"
            :edit-episode-title-value="editEpisodeTitleValue"
            :editing-chapter-outline-title="editingChapterOutlineTitle"
            :edit-chapter-outline-title-value="editChapterOutlineTitleValue"
            :editing-scene-outline-title="editingSceneOutlineTitle"
            :edit-scene-outline-title-value="editSceneOutlineTitleValue"
            @generate-all-episode-outlines="handleGenerateAllEpisodeOutlines()"
            @generate-single-episode-outline="handleGenerateSingleEpisodeOutline"
            @show-episode-outline-detail="showEpisodeOutlineDetail"
            @download-episode-outline="downloadEpisodeOutline"
            @download-all-episode-outlines="downloadAllEpisodeOutlines"
            @generate-episode-content="generateEpisodeContent"
            @stop-generation="handleStopGeneration"
            @delete-episode-content="handleDeleteEpisodeContent"
            @delete-episode-outline="handleDeleteEpisodeOutline"
            @edit-episode-title="startEditEpisodeTitle"
            @save-episode-title="saveEpisodeTitle"
            @cancel-edit-episode-title="cancelEditEpisodeTitle"
            @generate-all-chapter-outlines="handleGenerateAllChapterOutlines()"
            @generate-single-chapter-outline="handleGenerateSingleChapterOutline"
            @show-chapter-outline-detail="showChapterOutlineDetail"
            @download-chapter-outline="downloadChapterOutline"
            @download-all-chapter-outlines="downloadAllChapterOutlines"
            @generate-chapter-content="generateChapterContent"
            @regenerate-chapter-outline="(num) => handleGenerateSingleChapterOutline(num, true)"
            @delete-chapter-content="handleDeleteChapterContent"
            @delete-chapter-outline="handleDeleteChapterOutline"
            @edit-chapter-outline-title="startEditChapterOutlineTitle"
            @save-chapter-outline-title="saveChapterOutlineTitle"
            @cancel-edit-chapter-outline-title="cancelEditChapterOutlineTitle"
            @generate-all-scene-outlines="handleGenerateAllSceneOutlines()"
            @generate-single-scene-outline="handleGenerateSingleSceneOutline"
            @show-scene-outline-detail="showSceneOutlineDetail"
            @download-scene-outline="downloadSceneOutline"
            @download-all-scene-outlines="downloadAllSceneOutlines"
            @generate-scene-content="generateSceneContent"
            @delete-scene-content="handleDeleteSceneContent"
            @delete-scene-outline="handleDeleteSceneOutline"
            @edit-scene-outline-title="startEditSceneOutlineTitle"
            @save-scene-outline-title="saveSceneOutlineTitle"
            @cancel-edit-scene-outline-title="cancelEditSceneOutlineTitle"
            @update:edit-episode-title-value="(val) => editEpisodeTitleValue = val"
            @update:edit-chapter-outline-title-value="(val) => editChapterOutlineTitleValue = val"
            @update:edit-scene-outline-title-value="(val) => editSceneOutlineTitleValue = val"
            @open-batch-dialog="openBatchCountDialog"
          />


          <!-- 章节列表 -->
          <ChapterList
            :chapters="chapters"
            :selected-chapter="selectedChapter"
            :content-type="project.content_type"
            :unit-label="unitLabel"
            :episode-outlines="episodeOutlines"
            :chapter-outlines="chapterOutlines"
            :scene-outlines="sceneOutlines"
            :loading-directory="generatingDirectory"
            :loading-names="regeneratingNames"
            :loading-all-content="generatingAllContent"
            :batch-content-type="batchContentType"
            :task-store="taskStore"
            :editing-chapter="editingChapter"
            :edit-title-value="editTitleValue"
            @select="selectChapter"
            @edit-title="startEditTitle"
            @save-title="handleEnterSaveTitle"
            @cancel-edit="cancelEditTitle"
            @update:edit-title-value="(val) => editTitleValue = val"
            @regenerate-directory="handleRegenerateDirectory"
            @regenerate-names="handleRegenerateNames"
            @show-compliance="showComplianceDetail"
            @open-batch-dialog="openBatchCountDialog"
            @generate-all-episode-content="handleGenerateAllEpisodeContent"
            @download-all-episode-content="downloadAllEpisodeContent"
            @generate-all-chapter-content="handleGenerateAllChapterContent"
            @download-all-chapter-content="downloadAllChapterContent"
            @generate-all-scene-content="handleGenerateAllSceneContent"
            @download-all-scene-content="downloadAllSceneContent"
          />
        </el-card>

        <!-- 章节内容预览 -->
        <ChapterContentPreview
          :selected-chapter="selectedChapter"
          :content="chapterContent"
          :unit-label="unitLabel"
          :revision-info="chapterRevisionInfo"
          :compliance-marking="chapterComplianceMarking"
          :loading="generatingChapter"
          @generate="generateSingleChapter"
          @save="saveChapterContent"
          @update:content="(val) => chapterContent = val"
          @show-revision-compare="showRevisionCompareDialog"
          @show-compliance-detail="showComplianceDetail"
          @download="handleDownloadChapter"
        />
      </el-col>

      <el-col :span="10">
        <!-- 项目状态面板 -->
        <ProjectStatusPanel
          :project="project"
          :unit-label="unitLabel"
          :total-words="totalWords"
        />

        <!-- 知识库面板 -->
        <KnowledgeBasePanel
          :kb-status="kbStatus"
          :has-outline="!!project.outline_content"
          :loading-status="loadingKbStatus"
          :building="buildingKb"
          :resetting="resettingKbStatus"
          @build="handleBuildKnowledgeBase"
          @rebuild-global="handleBuildKnowledgeBase"
          @refresh="refreshKnowledgeBaseStatus"
          @reset="handleResetKbStatus"
          @delete="handleDeleteKnowledgeBase"
          @show-graph="showKnowledgeGraphDialog"
          @unit-graph-command="knowledgeGraphVisible = true"
        />
      </el-col>
    </el-row>
    <!-- 知识图谱弹窗 -->
    <KnowledgeGraphDialog
      v-model:visible="knowledgeGraphVisible"
      :project-id="project?.id"
      :total-units="project?.total_chapters || 0"
      :unit-label="unitLabel"
    />

    <!-- 修正对比弹窗 -->
        <RevisionCompareDialog
      v-model:visible="revisionCompareVisible"
      :revisionInfo="chapterRevisionInfo"
      :originalContent="originalDraftContent"
      :revisedContent="revisedContent"
      :diffHtml="revisionDiffHtml"
      :wordChange="revisionWordChange"
          />

    <!-- 合规审核详情弹窗 -->
        <ComplianceDetailDialog
      v-model:visible="complianceDetailVisible"
      :complianceData="complianceDetailData"
          />

    <!-- 设置对话框 -->
        <ProjectSettingsDialog
      v-model:visible="settingsVisible"
      :project="project"
      :settingsForm="settingsForm"
      :kbStatus="kbStatus"
      :buildingKb="buildingKb"
      :savingSettings="savingSettings"
            @save="saveSettings"
    />

    <!-- 导出对话框 -->
        <ExportDialog
      v-model:visible="exportVisible"
      :exportForm="exportForm"
      :exporting="exporting"
            @export="handleExport"
    />

    <!-- 分集大纲详情弹窗 -->
        <EpisodeOutlineDetailDialog
      v-model:visible="outlineDetailVisible"
      :outline="currentOutlineDetail"
      :editMode="outlineEditMode"
      :editTitle="outlineEditTitle"
      :editContent="outlineEditContent"
      :saving="savingOutlineEdit"
      :renderedContent="renderedOutlineContent"
            @start-edit="startEditOutline"
      @save="saveSettings"
      @cancel-edit="cancelEditOutline"
      @download="downloadSingleEpisodeOutline"
    />

    <!-- 章节大纲详情弹窗 -->
        <ChapterOutlineDetailDialog
      v-model:visible="chapterOutlineDetailVisible"
      :outline="currentChapterOutlineDetail"
      :editMode="chapterOutlineEditMode"
      :editTitle="chapterOutlineEditTitle"
      :editContent="chapterOutlineEditContent"
      :saving="savingChapterOutlineEdit"
      :renderedContent="renderedChapterOutlineContent"
            @start-edit="startEditOutline"
      @save="saveSettings"
      @cancel-edit="cancelEditOutline"
      @download="downloadSingleEpisodeOutline"
      @show-revision-compare="showChapterOutlineRevisionCompare"
    />

    <!-- 章节大纲修正对比弹窗 -->
        <ChapterOutlineRevisionCompareDialog
      v-model:visible="chapterOutlineRevisionCompareVisible"
      :revisionInfo="chapterOutlineRevisionInfo"
      :originalContent="chapterOutlineOriginalContent"
      :revisedContent="chapterOutlineRevisedContent"
      :diffHtml="chapterOutlineRevisionDiffHtml"
      :wordChange="chapterOutlineRevisionWordChange"
          />

    <!-- 场景大纲详情弹窗 -->
        <SceneOutlineDetailDialog
      v-model:visible="sceneOutlineDetailVisible"
      :outline="currentSceneOutlineDetail"
      :editMode="sceneOutlineEditMode"
      :editTitle="sceneOutlineEditTitle"
      :editContent="sceneOutlineEditContent"
      :saving="savingSceneOutlineEdit"
      :renderedContent="renderedSceneOutlineContent"
            @start-edit="startEditOutline"
      @save="saveSettings"
      @cancel-edit="cancelEditOutline"
      @download="downloadSingleEpisodeOutline"
    />

    <!-- 用户干预对话框 -->
        <InterventionDialog
      v-model:visible="interventionDialogVisible"
      :interventionData="interventionData"
      :interventionOptions="interventionOptions"
      :loading="interventionLoading"
      v-model:userChoice="interventionUserChoice"
      v-model:userGuidance="interventionUserGuidance"
      @confirm="handleInterventionConfirm"
      @cancel="handleInterventionCancel"
    />

    <!-- 单元概述上传对话框 -->
    <UnitSummariesUploadDialog
      v-model:visible="showUnitSummariesUploadDialog"
      v-model:uploadMode="unitSummariesUploadMode"
      v-model:unitSummariesInput="unitSummariesInput"
      v-model:globalOutlineInput="globalOutlineInput"
      :uploading="uploadingUnitSummaries"
      @upload-file="handleUnitSummariesFileUpload"
      @upload-content="handleUploadUnitSummariesContent"
    />

    <!-- 指定数量生成对话框 -->
        <BatchCountDialog
      v-model:visible="showBatchCountDialog"
      :config="batchCountConfig"
      :loading="batchCountLoading"
            @execute="executeBatchCountGenerate"
    />

    <!-- 质控结果对话框 -->
    <QualityControlResultDialog
      v-model:visible="showQualityControlResultDialog"
      :quality-report="qualityControlResult?.qualityReport"
      :revision-summary="qualityControlResult?.revisionSummary || []"
      :revised-count="qualityControlResult?.revisedCount || 0"
      :message="qualityControlResult?.message"
      :loading="false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useOutlineStore } from '@/stores/outline'
import { storeToRefs } from 'pinia'
import { useKnowledgeBase } from './composables/useKnowledgeBase'

// 导入子组件
import QualityControlResultDialog from './components/QualityControlResultDialog.vue'
import TaskStatusBar from './components/TaskStatusBar.vue'
import ProjectHeader from './components/ProjectHeader.vue'
import OutlineUploadSection from './components/OutlineUploadSection.vue'
import UnitSummariesSection from './components/UnitSummariesSection.vue'
import DetailedOutlineSection from './components/DetailedOutlineSection.vue'
import ChapterList from './components/ChapterList.vue'
import ChapterContentPreview from './components/ChapterContentPreview.vue'
import ProjectStatusPanel from './components/ProjectStatusPanel.vue'
import KnowledgeBasePanel from './components/KnowledgeBasePanel.vue'
import KnowledgeGraphDialog from './components/KnowledgeGraphDialog.vue'
import RevisionCompareDialog from './components/RevisionCompareDialog.vue'
import ComplianceDetailDialog from './components/ComplianceDetailDialog.vue'
import ProjectSettingsDialog from './components/ProjectSettingsDialog.vue'
import ExportDialog from './components/ExportDialog.vue'
import EpisodeOutlineDetailDialog from './components/EpisodeOutlineDetailDialog.vue'
import ChapterOutlineDetailDialog from './components/ChapterOutlineDetailDialog.vue'
import ChapterOutlineRevisionCompareDialog from './components/ChapterOutlineRevisionCompareDialog.vue'
import SceneOutlineDetailDialog from './components/SceneOutlineDetailDialog.vue'
import InterventionDialog from './components/InterventionDialog.vue'
import UnitSummariesUploadDialog from './components/UnitSummariesUploadDialog.vue'
import BatchCountDialog from './components/BatchCountDialog.vue'

// 导入组合式函数
import { useProjectDetailState } from './composables/useProjectDetailState'
import { useQualityControl } from './composables/useQualityControl'
import { useContentGeneration } from './composables/useContentGeneration'
import { useRevisionAndCompliance } from './composables/useRevisionAndCompliance'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const projectId = computed(() => parseInt(route.params.id))

// ============ Step 1: 创建核心状态（带可变 callbacks 对象解决循环依赖） ============
const _refreshCallbacks = {}
const state = useProjectDetailState(_refreshCallbacks)

// 解构所有状态 refs（大纲相关已迁移至 useOutlineStore）
const {
  loading, project, chapters, selectedChapter, chapterContent,
  generatingDirectory, regeneratingNames, manualUnitCount,
  abortController, taskPollingTimer, TASK_POLLING_INTERVAL,
  sseConnection, sseReconnectTimer, SSE_RECONNECT_DELAY,
  showUnitSummariesUploadDialog, unitSummariesUploadMode,
  unitSummariesInput, globalOutlineInput, uploadingUnitSummaries,
  editingChapter, editTitleValue,
  knowledgeGraphVisible,
  generatingAllContent, batchContentType, batchProgress,
  showBatchCountDialog, batchCountLoading, batchCountConfig,
  generating, generatingChapter,
  // Computed
  canGenerate, totalWords,
  renderedOutlineContent,
  renderedChapterOutlineContent,
  renderedSceneOutlineContent,
  getTypeLabel, getTypeTagType, getDisplaySteps,
  // Core methods
  loadProject, loadChapters, selectChapter,
  handleOutlineUpload, handleUploadUnitSummariesContent, handleUnitSummariesFileUpload,
  handleGenerateDirectory, handleRegenerateNames, handleRegenerateDirectory,
  cleanChapterTitle, startEditTitle, handleEnterSaveTitle, handleBlurSaveTitle,
  saveChapterTitle, cancelEditTitle,
  startGenerate, generateSingleChapter, saveChapterContent,
  handleDownloadChapter,
  showSettingsDialog, saveSettings, showExportDialog, handleExport, handleDelete,
  handleDeleteChapterContent: stateDeleteChapterContent, handleSyncContentStatus,
  handleClearAllOutlines, handleClearAllContent, handleClearAll,
  getStatusType, getStatusText, getChapterStatusType, getChapterStatusText,
  formatDateTime, getStepIcon, formatDuration, showOutlineUpload,
  startSSEConnection, stopSSEConnection,
  startTaskMonitoring, stopTaskMonitoring,
  startTaskPolling, stopTaskPolling, refreshListByTaskType,
  // Revision & Compliance state
  revisionCompareVisible, originalDraftContent, revisedContent,
  chapterRevisionInfo, revisionViewMode,
  complianceDetailVisible, complianceDetailData, chapterComplianceMarking,
  ISSUE_TYPE_LABELS, getIssueTypeLabel, showComplianceDetail,
  revisionWordChange, revisionDiffHtml,
  chapterOutlineRevisionWordChange, chapterOutlineRevisionDiffHtml,
  settingsForm, exportForm,
  computeDiffHtml, findLCS, escapeHtml
} = state

// ============ Step 2: 知识库状态 ============
const {
  kbStatus, loadingKbStatus, buildingKb, resettingKbStatus,
  loadKnowledgeBaseStatus, refreshKnowledgeBaseStatus,
  handleBuildKnowledgeBase, handleDeleteKnowledgeBase, handleResetKbStatus
} = useKnowledgeBase(projectId)

// ============ Step 3: 创建大纲管理（Pinia Store） ============
const outlineStore = useOutlineStore()
outlineStore.initProject({
  projectId, project, taskStore, abortController,
  loadProject, loadChapters,
  startTaskPolling, stopTaskPolling
})

// 从 store 解构响应式状态（替代原来从 useProjectDetailState 传入的 30+ 参数）
const {
  episodeOutlines, generatingEpisodeOutlines, generatingSingleEpisode,
  outlineDetailVisible, currentOutlineDetail, outlineEditMode,
  outlineEditContent, outlineEditTitle, savingOutlineEdit,
  editingEpisodeTitle, editEpisodeTitleValue,
  chapterOutlines, generatingChapterOutlines, generatingSingleChapterOutline,
  chapterOutlineDetailVisible, currentChapterOutlineDetail,
  chapterOutlineRevisionCompareVisible, chapterOutlineOriginalContent,
  chapterOutlineRevisedContent, chapterOutlineRevisionInfo,
  chapterOutlineRevisionViewMode,
  chapterOutlineEditMode, chapterOutlineEditContent,
  chapterOutlineEditTitle, savingChapterOutlineEdit,
  editingChapterOutlineTitle, editChapterOutlineTitleValue,
  sceneOutlines, generatingSceneOutlines, generatingSingleSceneOutline,
  sceneOutlineDetailVisible, currentSceneOutlineDetail,
  sceneOutlineEditMode, sceneOutlineEditContent,
  sceneOutlineEditTitle, savingSceneOutlineEdit,
  editingSceneOutlineTitle, editSceneOutlineTitleValue,
  interventionDialogVisible, interventionData, interventionLoading,
  interventionUserChoice, interventionUserGuidance, interventionOptions,
  totalEpisodeCount, totalChapterOutlineCount, totalSceneOutlineCount,
  generatedEpisodeCount, generatedChapterOutlineCount, generatedSceneOutlineCount,
  generatedEpisodeContentCount, generatedChapterContentCount, generatedSceneContentCount,
  unitLabel
} = storeToRefs(outlineStore)

// 从 store 解构方法
const {
  loadEpisodeOutlines,
  handleGenerateAllEpisodeOutlines,
  handleGenerateSingleEpisodeOutline,
  showEpisodeOutlineDetail,
  startEditOutline, cancelEditOutline, saveOutlineEdit,
  downloadSingleEpisodeOutline, downloadEpisodeOutline,
  downloadAllEpisodeOutlines, downloadAllEpisodeContent,
  startEditEpisodeTitle, cancelEditEpisodeTitle, saveEpisodeTitle,
  handleDeleteEpisodeContent, handleDeleteEpisodeOutline,
  loadChapterOutlines,
  handleGenerateAllChapterOutlines,
  handleGenerateSingleChapterOutline,
  showInterventionDialog, handleInterventionConfirm, handleInterventionCancel,
  showChapterOutlineDetail, showChapterOutlineRevisionCompare,
  startEditChapterOutline, cancelEditChapterOutline, saveChapterOutlineEdit,
  downloadSingleChapterOutline, downloadChapterOutline,
  downloadAllChapterOutlines, downloadAllChapterContent,
  startEditChapterOutlineTitle, cancelEditChapterOutlineTitle,
  saveChapterOutlineTitle,
  handleDeleteChapterContent, handleDeleteChapterOutline,
  loadSceneOutlines,
  handleGenerateAllSceneOutlines,
  handleGenerateSingleSceneOutline,
  showSceneOutlineDetail,
  startEditSceneOutline, cancelEditSceneOutline, saveSceneOutlineEdit,
  downloadSingleSceneOutline, downloadSceneOutline,
  downloadAllSceneOutlines, downloadAllSceneContent,
  startEditSceneOutlineTitle, cancelEditSceneOutlineTitle,
  saveSceneOutlineTitle,
  handleDeleteSceneContent, handleDeleteSceneOutline,
  downloadBlob
} = outlineStore

// ============ Step 4: 设置 refreshCallbacks（让 SSE/轮询能刷新大纲） ============
_refreshCallbacks.loadEpisodeOutlines = loadEpisodeOutlines
_refreshCallbacks.loadChapterOutlines = loadChapterOutlines
_refreshCallbacks.loadSceneOutlines = loadSceneOutlines

// ============ Step 5: 创建内容生成管理 ============
const contentGen = useContentGeneration({
  projectId, project, chapters, selectedChapter, chapterContent,
  episodeOutlines, chapterOutlines, sceneOutlines,
  taskStore, abortController,
  loadProject, loadChapters,
  loadEpisodeOutlines, loadChapterOutlines, loadSceneOutlines,
  selectChapter,
  // 传入共享 ref，避免重复定义
  generating, generatingChapter, generatingAllContent,
  showBatchCountDialog, batchCountLoading, batchCountConfig,
  batchContentType, batchProgress
})

// 解构内容生成
const {
  selectedEpisode, selectedScene,
  generateEpisodeContent, generateChapterContent, generateSceneContent,
  handleStopGeneration,
  handleGenerateAllEpisodeContent, handleGenerateAllChapterContent,
  handleGenerateAllSceneContent,
  handleStopBatchGeneration,
  openBatchCountDialog, executeBatchCountGenerate,
  handleCancelTask
} = contentGen

// ============ Step 6: 创建质控 ============
const qc = useQualityControl(projectId, project, loadProject)
const {
  qualityControlLoading, showQualityControlResultDialog, qualityControlResult,
  handleTriggerQualityControl
} = qc

// ============ Step 7: 创建修正对比与合规 ============
// Note: showRevisionCompareDialog 已从 useProjectDetailState 中获取
// useRevisionAndCompliance 目前功能较少，后续可扩展
useRevisionAndCompliance({
  projectId, project,
  revisionCompareVisible, originalDraftContent, revisedContent,
  chapterRevisionInfo, revisionViewMode,
  complianceDetailVisible, complianceDetailData, chapterComplianceMarking,
  showComplianceDetail
})

// ============ 生命周期钩子 ============
onMounted(async () => {
  await loadProject()
  await loadChapters()

  // 加载完成后启动SSE连接或轮询
  startTaskMonitoring()
})

onUnmounted(() => {
  stopTaskMonitoring()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

// 处理页面可见性变化
function handleVisibilityChange() {
  if (!document.hidden) {
    taskStore.fetchTaskStatus(projectId.value).then(task => {
      if (task && task.status === 'running') {
        if (!sseConnection.value && !taskPollingTimer.value) {
          taskStore.setTask(task)
          startTaskMonitoring()
        }
      } else if (task && (task.status === 'failed' || task.status === 'cancelled' || task.status === 'completed')) {
        taskStore.clearTask()
      }
    })
  }
}

// 添加页面可见性监听
document.addEventListener('visibilitychange', handleVisibilityChange)

// 监听项目变化，加载相应类型的大纲
watch(() => project.value, (newVal) => {
  if (!newVal) return

  if (newVal.content_type === 'movie_script') {
    loadSceneOutlines()
  } else if (newVal.content_type === 'series_script') {
    loadEpisodeOutlines()
  } else if (newVal.content_type === 'novel') {
    loadChapterOutlines()
  } else if (newVal.project_type === 'script') {
    loadEpisodeOutlines()
  }
}, { immediate: true })

</script>

<style lang="scss" scoped>
.project-detail-page {
  &.is-completed {
    background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
    animation: none;
  }

  &.is-cancelled {
    background: linear-gradient(135deg, #909399 0%, #a6a9ad 100%);
    animation: none;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;

  &.warn {
    color: #e6a23c;
  }
}
</style>
