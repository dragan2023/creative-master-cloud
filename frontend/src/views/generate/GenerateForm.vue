<template>
  <div class="generate-form-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-top-row">
        <el-button text @click="router.push('/generate')">
          <el-icon><ArrowLeft /></el-icon>
          返回选择
        </el-button>
        <div class="header-actions">
          <el-button size="small" @click="exportConfig">
            <el-icon><Download /></el-icon>
            导出配置
          </el-button>
          <el-button size="small" @click="triggerImport">
            <el-icon><Upload /></el-icon>
            导入配置
          </el-button>
          <input ref="importInputRef" type="file" accept=".json" style="display:none" @change="importConfig" />
        </div>
      </div>
      <div class="header-info">
        <el-icon :size="32" :style="{ color: currentModule?.color }">
          <component :is="currentModule?.icon" />
        </el-icon>
        <h1>{{ currentModule?.title }}</h1>
      </div>
      <p>{{ currentModule?.description }}</p>
    </div>
    
    <!-- 创作步骤条 -->
    <CreationStepBar
      :steps="creationPhases"
      :current-step="currentPhaseIndex"
      :primary-action="phasePrimaryAction"
      :secondary-actions="phaseSecondaryActions"
      :current-hint="phaseHint"
    />

    <!-- 主体区域：左右分栏 -->
    <div class="main-container">
      <!-- 左侧：表单区域 -->
      <div class="left-panel">
        <div class="form-container">
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            size="large"
          >
            <!-- 表单字段区域 -->
            <FormFieldsSection
              ref="formFieldsSectionRef"
              :form="form"
              :type="type"
              :optimizing="optimizing"
              :optimize-target="optimizeTarget"
              :upload-url="uploadUrl"
              :upload-headers="uploadHeaders"
              :uploading-outline="uploading_outline"
              :outline-upload-progress="outline_upload_progress"
              :uploading-reference-materials="uploading_reference_materials"
              :reference-materials-upload-progress="reference_materials_upload_progress"
              :uploading-ref-doc="uploading_reference_doc"
              :ref-doc-upload-progress="reference_doc_upload_progress"
              :series-duration-hint="seriesDurationHint"
              :movie-duration-hint="movieDurationHint"
              :series-episode-duration-hint="seriesEpisodeDurationHint"
              :image-file-list="imageFileList"
              :image-url-input="imageUrlInput"
              @update:form="handleFormFieldsUpdate"
              @optimize="handleOptimizePrompt"
              @series-type-change="handleSeriesTypeChange"
              @movie-type-change="handleMovieTypeChange"
              @series-outline-type-change="handleSeriesOutlineTypeChange"
              @outline-upload-success="handleOutlineUploadSuccess"
              @outline-upload-error="handleOutlineUploadError"
              @outline-progress="handleOutlineProgress"
              @remove-outline="removeOutlineFile"
              @reference-upload-success="handleReferenceMaterialsUploadSuccess"
              @reference-upload-error="handleReferenceMaterialsUploadError"
              @remove-reference-file="removeReferenceMaterialsFile"
              @ref-doc-upload-success="handleReferenceDocUploadSuccess"
              @ref-doc-upload-error="handleReferenceDocUploadError"
              @ref-doc-progress="handleReferenceDocProgress"
              @remove-ref-doc="removeReferenceDocFile"
              @image-upload-success="handleUploadSuccess"
              @image-upload-error="handleUploadError"
              @parse-image-urls="parseImageUrls"
              @update:style-data="handleStyleDataUpdate"
              @update:title-style-data="handleTitleStyleDataUpdate"
            />
            
            <!-- 知识库增强区域 -->
            <KnowledgeBaseSection ref="knowledgeBaseSectionRef" :storage-key="`user_config_generate_${type}_kb`" />
            
            <!-- 提交按钮 -->
            <div class="form-actions">
              <el-button @click="resetForm">重置</el-button>
              <!-- 两阶段大纲生成模式：显示导入按钮 -->
              <el-button v-if="useTwoStageMode" @click="openImportDialog">
                <el-icon><Upload /></el-icon>
                导入已有大纲
              </el-button>
              <el-button v-if="useTwoStageMode" type="success" @click="openImportUnitSummariesDialog">
                <el-icon><Upload /></el-icon>
                导入已有单元概述
              </el-button>
              <el-button type="primary" :loading="generating" @click="handleGenerate" :disabled="generating">
                <el-icon v-if="!generating"><MagicStick /></el-icon>
                {{ generating ? '生成中...' : '开始生成' }}
              </el-button>
              <el-button v-if="generating" type="danger" @click="handleStop">
                <el-icon><CircleClose /></el-icon>
                中断生成
              </el-button>
            </div>
          </el-form>
        </div>
      </div>
      
      <!-- 右侧：工作流程展示 -->
      <div class="right-panel">
        <WorkflowProgress
          :generating="generating"
          :workflow-steps="workflowSteps"
          :workflow-complete="workflowComplete"
        />
      </div>
    </div>
    
    <!-- 底部：生成结果 -->
    <ResultViewer
      :show-result="showResult"
      :use-two-stage-mode="useTwoStageMode"
      :outline-stage="outlineStage"
      :global-outline-generating="globalOutlineGenerating"
      :unit-summaries-generating="unitSummariesGenerating"
      :knowledge-revising="knowledgeRevising"
      :logic-checking="logicChecking"
      :logic-check-result="logicCheckResult"
      :generation-duration="generationDuration"
      :editing-global-outline="editingGlobalOutline"
      :editing-global-outline-content="editingGlobalOutlineContent"
      :editing-unit-number="editingUnitNumber"
      :editing-unit-content="editingUnitContent"
      :unit-summaries="unitSummaries"
      :global-outline-content="globalOutlineContent"
      :generated-content="generatedContent"
      :generating="generating"
      :content-type="type"
      :expected-unit-count="expectedUnitCount"
      :is-revision-mode="isRevisionMode"
      :current-revision-round="currentRevisionRound"
      :revision-content="revisionContent"
      :revision-messages="revisionMessages"
      :revision-history="revisionHistory"
      :revising="revising"
      :revision-input="revisionInput"
      :quality-report="qualityReport"
      :project-id="generationId"
      :global-outline-q-c-report="globalOutlineQCReport"
      :global-outline-q-c-loading="globalOutlineQCLoading"
      :qc-progress="qcProgress"
      :revising-issue-id="revisingIssueId"
      :qc-applied="qcApplied"
      :issues-fixed="issuesFixed"
      :qc-report-data="qcReportData"
      :imported-outline="importedOutline"
      :imported-unit-summaries="importedUnitSummaries"
      :auto-q-c-loading="autoQCLoading"
      :unit-summaries-q-c-loading="unitSummariesQCLoading"
      :unit-summaries-q-c-report="qcReportData"
      :truncation-info="truncationInfo"
      :is-continuing="isContinuing"
      :backend-resume-info="backendResumeInfo"
      :creating-writing-project="creatingWritingProject"
      @stop="handleStop"
      @generate-unit-summaries="handleGenerateUnitSummaries"
      @cancel-unit-summaries="cancelUnitSummariesGeneration"
      @download-outline="downloadOutline"
      @continue-generation="handleContinueGeneration"
      @open-start-unit-dialog="openStartUnitDialog"
      @resume-unit-summaries="handleResumeUnitSummaries"
      @reset-two-stage="resetTwoStageOutline"
      @copy="copyResult"
      @download="downloadResult"
      @regenerate="regenerate"
      @start-edit-global="startEditGlobalOutline"
      @save-global-edit="saveGlobalOutlineEdit"
      @cancel-global-edit="cancelEditGlobalOutline"
      @update:editingGlobalOutlineContent="editingGlobalOutlineContent = $event"
      @open-revision-detail="openRevisionDetail"
      @edit-unit="editUnitSummary"
      @save-unit="saveUnitSummary"
      @cancel-edit-unit="cancelEditUnitSummary"
      @update:editingUnitContent="editingUnitContent = $event"
      @start-revision="startRevision"
      @start-unit-summaries-revision="handleStartUnitSummariesRevision"
      @submit-revision="submitRevision"
      @finalize-content="finalizeContent"
      @exit-revision="exitRevision"
      @update:revisionInput="revisionInput = $event"
      @global-outline-qc="handleGlobalOutlineQC"
      @analyze-global-outline-qc="handleGlobalOutlineQC"
      @revise-global-outline="handleGlobalOutlineRevise"
      @update-quality-report="handleUpdateQualityReport"
      @update-unit-content="handleUpdateUnitContent"
      @quality-control="handleImportedUnitSummariesQC"
      @quality-control-unit-summaries="handleUnitSummariesQC"
      @unit-summaries-feedback="handleUnitSummariesFeedback"
      @apply-unit-summaries-revision="handleApplyUnitSummariesRevision"
      @remove-unit-summaries-duplicates="handleRemoveUnitSummariesQCDuplicates"
      @resume-unit-summaries-from-backend="handleResumeUnitSummariesFromBackend"
      @create-writing-project="handleCreateWritingProject"
      @open-unit-diff="handleOpenUnitSummariesDiff"
    />
    
    <!-- v2.4新增：全局大纲修正对比对话框 -->
    <GlobalOutlineReviseDialog
      v-model="showGlobalOutlineReviseDialog"
      :original-content="globalOutlineReviseData.originalContent"
      :revised-content="globalOutlineReviseData.revisedContent"
      :changes="globalOutlineReviseData.changes"
      :original-length="globalOutlineReviseData.originalLength"
      :revised-length="globalOutlineReviseData.revisedLength"
      @confirm="handleConfirmGlobalOutlineRevise"
      @cancel="handleCancelGlobalOutlineRevise"
    />
    
    <!-- 单元概述修正对比对话框（手动质控） -->
    <UnitSummariesReviseDialog
      v-model="showUnitSummariesReviseDialog"
      :original-content="unitSummariesReviseData.originalContent"
      :revised-content="unitSummariesReviseData.revisedContent"
      :revised-parsed="unitSummariesReviseData.revisedParsed"
      :changes="unitSummariesReviseData.changes || []"
      :original-length="unitSummariesReviseData.originalContent?.length || 0"
      :revised-length="unitSummariesReviseData.revisedContent?.length || 0"
      :total-issues="unitSummariesReviseData.qualityReport?.issues?.length || 0"
      :critical-issues-count="unitSummariesReviseData.changes?.length || 0"
      :quality-score="unitSummariesReviseData.qualityReport?.overall_score || 0"
      @confirm="handleConfirmUnitSummariesRevise"
      @cancel="handleCancelUnitSummariesRevise"
      @remove-duplicates="handleRemoveUnitSummariesDuplicates"
    />
  </div>

  <!-- 导入已有大纲对话框 -->
  <ImportOutlineDialog
    v-model="showImportDialog"
    v-model:import-type="importType"
    :upload-url="outlineImportUploadUrl"
    :upload-headers="uploadHeaders"
    :importing="importingOutline"
    :progress="importOutlineProgress"
    @before-upload="beforeOutlineImportUpload"
    @upload-success="handleOutlineImportUploadSuccess"
    @upload-error="handleOutlineImportUploadError"
    @upload-progress="handleOutlineImportProgress"
  />

  <!-- 导入单元概述对话框 -->
  <ImportUnitSummariesDialog
    v-model="showImportUnitSummariesDialog"
    :upload-url="unitSummariesImportUploadUrl"
    :importing="importingUnitSummaries"
    :progress="importUnitSummariesProgress"
    @before-upload="beforeUnitSummariesImportUpload"
    @upload-success="handleUnitSummariesImportUploadSuccess"
    @upload-error="handleUnitSummariesImportUploadError"
    @upload-progress="handleUnitSummariesImportProgress"
  />

  <!-- 从指定单元开始对话框 -->
  <StartUnitDialog
    v-model="showStartUnitDialog"
    v-model:start-from-unit="startFromUnit"
    :max-unit="startUnitMax"
    :loading="unitSummariesGenerating"
    @generate="handleGenerateFromUnit"
  />

  <!-- 逻辑问题详情对话框 -->
  <LogicIssuesDialog
    v-model="showLogicIssuesDialog"
    :issues="logicCheckResult?.issues || []"
  />

  <!-- 修正详情对话框 -->
  <RevisionDetailDialog
    v-model="showRevisionDetailDialog"
    :unit-data="currentRevisionUnitData"
    :unit-number="currentRevisionUnitNumber"
    :unit-label="currentRevisionUnitLabel"
    v-model:view-mode="revisionViewMode"
    :diff-html="currentRevisionDiffHtml"
  />
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CREATIVE_MODULES } from '@/config'
import { generateApi, revisionApi, historyApi, globalOutlineQCApi, unitSummariesQCApi, novelWriterApi } from '@/api'
import { useApiKeyStore } from '@/stores'
import { API_BASE_URL } from '@/config'
import { useUserStore } from '@/stores/user'
import { getToken, getAuthHeaders, getSseAuthParams } from '@/utils/authStorage'
import { computeDiffHtml } from '@/utils/diffUtils'
import { parseChapterCountFromOutline, parseUnitSummariesFromContent } from './utils/outlineParser'
import { buildOutlineInputParams as buildOutlineParams } from './utils/buildRequestParams'
import { useConfigPersistence } from '@/composables/useConfigPersistence'
import { announceGenerationStatus } from '@/utils/ariaLive'
import { MagicStick, List, Download, Edit, Refresh, Upload, Document } from '@element-plus/icons-vue'

// 导入子组件
import FormFieldsSection from './components/FormFieldsSection.vue'
import KnowledgeBaseSection from './components/KnowledgeBaseSection.vue'
import WorkflowProgress from './components/WorkflowProgress.vue'
import ResultViewer from './components/ResultViewer.vue'
import GlobalOutlineReviseDialog from './components/GlobalOutlineReviseDialog.vue'
import UnitSummariesReviseDialog from './components/UnitSummariesReviseDialog.vue'
import ImportOutlineDialog from './components/ImportOutlineDialog.vue'
import ImportUnitSummariesDialog from './components/ImportUnitSummariesDialog.vue'
import StartUnitDialog from './components/StartUnitDialog.vue'
import LogicIssuesDialog from './components/LogicIssuesDialog.vue'
import RevisionDetailDialog from './components/RevisionDetailDialog.vue'
import CreationStepBar from '@/components/CreationStepBar.vue'
import { GENERAL_PHASES } from '@/domain/taskPresentation'

// 导入composables
import { useGenerationForm } from './composables/useGenerationForm'
import { useWorkflow } from './composables/useWorkflow'
import { useGenerationRestore } from '@/composables/useGenerationRestore'
import { useUnitSummariesGeneration } from './composables/useUnitSummariesGeneration'
import { useRevisionMode } from './composables/useRevisionMode'
import { useQualityControl } from './composables/useQualityControl'
import { useImportLogic } from './composables/useImportLogic'
import { useReviseHandlers } from './composables/useReviseHandlers'

const router = useRouter()
const route = useRoute()
const apiKeyStore = useApiKeyStore()
const userStore = useUserStore()

// 文风选择器相关的
const formFieldsSectionRef = ref(null)
const styleData = ref({
  styleIds: [], 
  styleNames: [], 
  intensity: 0.7, 
  styleGuide: null 
})

// 标题风格选择器相关的
const titleStyleData = ref({
  styleId: '',
  styleName: ''
})

// 导入大纲上传URL
const outlineImportUploadUrl = computed(() => 
  `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/generate/upload-outline-import`
)

/**
 * 处理子组件字段整体更新（如短视频风格类型、生成模式联动字段）
 * 子组件通过 update:form 事件传回新表单对象，需合并回响应式 form
 */
function handleFormFieldsUpdate(updatedForm) {
  Object.assign(form.value, updatedForm)
}

/**
 * 处理文风数据更新
 */
function handleStyleDataUpdate(data) {
  styleData.value = data
  console.log('[GenerateForm] 文风数据更新:', styleData.value)
}

/**
 * 处理标题风格数据更新
 */
function handleTitleStyleDataUpdate(data) {
  titleStyleData.value = data
  console.log('[GenerateForm] 标题风格数据更新:', titleStyleData.value)
}

const type = computed(() => route.params.type)
// 前端路由参数（连字符格式）→ 后端 content_type（下划线格式）
const backendContentType = computed(() => {
  const map = {
    'movie-outline': 'movie_outline',
    'series-outline': 'series_outline',
    'short-video': 'short_video',
    'print-ad': 'print_ad',
    'original-ip': 'original_ip'
  }
  return map[type.value] || type.value
})
const currentModule = computed(() => 
  CREATIVE_MODULES.find(m => m.key === type.value)
)

// 使用composables
const {
  formRef,
  form,
  rules,
  imageFileList,
  imageUrlInput,
  uploadUrl,
  uploadHeaders,
  uploading_outline,
  outline_upload_progress,
  uploading_reference_materials,
  reference_materials_upload_progress,
  uploading_reference_doc,
  reference_doc_upload_progress,
  optimizing,
  optimizeTarget,
  useTwoStageMode,
  combinedStyleTypes,
  seriesDurationHint,
  movieDurationHint,
  seriesEpisodeDurationHint,
  beforeUpload,
  beforeOutlineUpload,
  handleOutlineProgress,
  handleOutlineUploadSuccess,
  handleOutlineUploadError,
  removeOutlineFile,
  beforeReferenceMaterialsUpload,
  handleReferenceMaterialsUploadSuccess,
  handleReferenceMaterialsUploadError,
  removeReferenceMaterialsFile,
  handleUploadSuccess,
  handleUploadError,
  parseImageUrls,
  beforeReferenceDocUpload,
  handleReferenceDocProgress,
  handleReferenceDocUploadSuccess,
  handleReferenceDocUploadError,
  removeReferenceDocFile,
  handleVideoModeChange,
  handleSeriesTypeChange,
  handleMovieTypeChange,
  handleSeriesOutlineTypeChange,
  handleOptimizePrompt,
  saveFormData,
  restoreFormData,
  resetForm,
  importInputRef,
  exportConfig,
  triggerImport,
  importConfig
} = useGenerationForm(type, router)

// 流式处理相关状态（必须在 useWorkflow 之前定义）
const generating = ref(false)

// 屏幕阅读器播报：生成状态变更时通知辅助技术
watch(generating, (isGen) => {
  const moduleName = currentModule?.value?.title || ''
  if (isGen) {
    announceGenerationStatus('generating', { moduleName })
  } else {
    // generating 变为 false 可能是完成或出错，由调用处再次播报具体状态
  }
})

const showResult = ref(false)
const generatedContent = ref('')
const currentGenerationId = ref(null)
const currentEventSource = ref(null)
const currentSessionId = ref(null)

const {
  workflowSteps,
  currentStep,
  workflowComplete,
  generationDuration,
  qualityReport,
  truncationInfo,  // 新增:截断检测信息
  isContinuing,    // 新增:是否正在接续
  handleWorkflowEvent,
  formatDuration,
  copyResult,
  downloadResult,
  trackAction
} = useWorkflow(type, form, generatedContent, currentGenerationId)

// 两阶段大纲生成状态
const outlineStage = ref(0)
const globalOutlineContent = ref('')
const globalOutlineGenerating = ref(false)
const unitSummaries = ref({})
const unitSummariesGenerating = ref(false)

// 续生成相关计算属性
const expectedUnitCount = computed(() => {
  const formChapterCount = type.value === 'novel'
    ? parseInt(form.value.chapter_count) || null
    : parseInt(form.value.episode_count) || null
  const outlineChapterCount = formChapterCount ? null : parseChapterCountFromOutline(globalOutlineContent.value)
  return formChapterCount || outlineChapterCount || (type.value === 'novel' ? 50 : 24)
})

// 逻辑检测状态
const logicChecking = ref(false)
const logicCheckResult = ref(null)
const showLogicIssuesDialog = ref(false)

// 知识库修正状态
const knowledgeRevising = ref(false)

// 修正详情对话框状态
const showRevisionDetailDialog = ref(false)
const currentRevisionUnit = ref(null)
const revisionViewMode = ref('diff')

// 修正详情对话框 - 计算属性
const currentRevisionUnitData = computed(() => {
  return currentRevisionUnit.value && unitSummaries.value 
    ? unitSummaries.value[currentRevisionUnit.value] 
    : null
})
const currentRevisionUnitNumber = computed(() => {
  return currentRevisionUnitData.value?.unit_number || ''
})
const currentRevisionUnitLabel = computed(() => {
  return type.value === 'novel' ? '章' : '集'
})
const currentRevisionDiffHtml = computed(() => {
  if (!currentRevisionUnitData.value) return ''
  return getRevisionDiffHtml(currentRevisionUnitData.value)
})

// StartUnitDialog - 最大单元数
const startUnitMax = computed(() => {
  return type.value === 'novel' 
    ? (parseInt(form.value?.chapter_count) || 50) 
    : (parseInt(form.value?.episode_count) || 24)
})

// 修订模式状态
const isRevisionMode = ref(false)
const currentRevisionRound = ref(0)
const revisionInput = ref('')
const revising = ref(false)
const revisionContent = ref('')
const revisionMessages = ref([])
const revisionHistory = ref([])
const generationId = ref(null)

// 编辑状态
const editingUnitNumber = ref(null)
const editingUnitContent = ref('')
const editingGlobalOutline = ref(false)
const editingGlobalOutlineContent = ref('')

// 全局大纲质控状态 (v1.0新增)
const globalOutlineQCReport = ref(null)
const globalOutlineQCLoading = ref(false)
const revisingIssueId = ref(null)

// v1.1新增：SSE实时进度状态
const qcProgress = ref(null)          // SSE进度数据
const qcSSEConnection = ref(null)    // SSE连接实例

// v2.3新增：自动质控状态
const qcApplied = ref(false)          // 是否已应用质控修正
const qcReportData = ref(null)        // 质控报告数据（用于历史记录）
const issuesFixed = ref(0)            // 修正的问题数量
const importedOutline = ref(false)    // 是否为导入的大纲
const autoQCLoading = ref(false)      // 自动质控加载状态
const unitSummariesQCLoading = ref(false)  // 单元概述质控加载状态（手动触发）

// 全局大纲修正对比对话框 (v2.2新增)
const showGlobalOutlineReviseDialog = ref(false)
const globalOutlineReviseData = ref({
  originalContent: '',
  revisedContent: '',
  changes: [],
  issueId: null,
  issueDescription: '',
  originalLength: 0,
  revisedLength: 0
})

// 单元概述修正对比对话框（手动质控）
const showUnitSummariesReviseDialog = ref(false)
const unitSummariesReviseData = ref({
  originalContent: '',
  revisedContent: '',
  revisedParsed: null,
  qualityReport: null
})
// v3.1新增：原始版本快照（用于后续对比查看）
const unitSummariesOriginalSnapshot = ref({
  content: '',
  parsed: null
})

// 灵活介入流程状态
const showImportDialog = ref(false)
const importType = ref('global')
const importContent = ref('')
const startFromUnit = ref(1)
const showStartUnitDialog = ref(false)

// 导入文件上传状态
const importingOutline = ref(false)
const importOutlineProgress = ref(0)

// 导入单元概述相关状态
const showImportUnitSummariesDialog = ref(false)
const importingUnitSummaries = ref(false)
const importUnitSummariesProgress = ref(0)
const importedUnitSummaries = ref(false)  // 是否为导入的单元概述
const unitSummariesImportUploadUrl = computed(() => 
  `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/generate/upload-unit-summaries-import`
)

// 后端断点信息（用于页面刷新后恢复续生成状态）
const backendResumeInfo = ref(null)  // { can_resume, remaining_count, start_from_unit, existing_count, expected_count, global_outline, existing_parsed, existing_content }

// P0改造新增：创建写作项目状态
const creatingWritingProject = ref(false)

// ==================== 创作步骤条状态（阶段01新增） ====================

/** 创作阶段（复用 domain 定义） */
const creationPhases = computed(() => {
  // 两阶段模式（小说/剧本/电影大纲）使用不同的阶段定义
  if (useTwoStageMode.value) {
    return [
      { key: 'setup', label: '设定', icon: 'Setting' },
      { key: 'global_outline', label: '全局大纲', icon: 'Memo' },
      { key: 'unit_summaries', label: '单元概述', icon: 'List' },
      { key: 'review', label: '审阅', icon: 'View' },
      { key: 'deliver', label: '交付', icon: 'Trophy' },
    ]
  }
  return GENERAL_PHASES
})

/** 当前阶段索引（0-based） */
const currentPhaseIndex = computed(() => {
  // 两阶段模式
  if (useTwoStageMode.value) {
    if (outlineStage.value === 0 && !generating.value) return 0         // 设定
    if (globalOutlineGenerating.value) return 1                          // 全局大纲中
    if (outlineStage.value === 1 && !globalOutlineGenerating.value && !unitSummariesGenerating.value) return 1 // 大纲完成
    if (unitSummariesGenerating.value) return 2                          // 单元概述中
    if (outlineStage.value >= 2 && !generating.value) return 3           // 审阅
    if (isRevisionMode.value || creatingWritingProject.value) return 4   // 交付
    return 3
  }
  // 通用模式
  if (!generating.value && !showResult.value) return 0                   // 设定
  if (generating.value) return 2                                         // 生成
  if (showResult.value && !isRevisionMode.value) return 3                // 审阅
  if (isRevisionMode.value) return 4                                     // 交付
  return 0
})

/** 主操作按钮 */
const phasePrimaryAction = computed(() => {
  const phaseIdx = currentPhaseIndex.value

  // 设定阶段 → 开始生成
  if (phaseIdx === 0) {
    return {
      label: '开始生成',
      icon: MagicStick,
      type: 'primary',
      loading: generating.value || globalOutlineGenerating.value,
      disabled: generating.value,
      onClick: handleGenerate,
    }
  }

  // 两阶段：全局大纲完成后 → 生成单元概述
  if (useTwoStageMode.value && phaseIdx === 1 && outlineStage.value >= 1) {
    return {
      label: unitSummariesGenerating.value ? '生成中...' : '审核并生成单元概述',
      icon: List,
      type: 'primary',
      loading: unitSummariesGenerating.value,
      disabled: unitSummariesGenerating.value || globalOutlineGenerating.value,
      onClick: () => handleGenerateUnitSummaries(),
    }
  }

  // 两阶段：单元概述完成后 → 创建写作项目
  if (useTwoStageMode.value && phaseIdx === 3) {
    return {
      label: creatingWritingProject.value ? '创建中...' : '创建写作项目',
      icon: Edit,
      type: 'success',
      loading: creatingWritingProject.value,
      onClick: handleCreateWritingProject,
    }
  }

  // 交付阶段 → 导出
  if (phaseIdx === 4) {
    return {
      label: '导出结果',
      icon: Download,
      type: 'primary',
      onClick: downloadResult,
    }
  }

  return null
})

/** 次级操作按钮 */
const phaseSecondaryActions = computed(() => {
  const phaseIdx = currentPhaseIndex.value
  const actions = []

  // 设定阶段
  if (phaseIdx === 0) {
    actions.push({
      label: '重置',
      icon: Refresh,
      onClick: resetForm,
    })
    actions.push({
      label: '导入配置',
      icon: Upload,
      onClick: triggerImport,
    })
  }

  // 大纲完成后
  if (useTwoStageMode.value && phaseIdx === 1 && outlineStage.value >= 1) {
    actions.push({
      label: '编辑大纲',
      icon: Edit,
      onClick: startEditGlobalOutline,
    })
    actions.push({
      label: '导出大纲',
      icon: Download,
      onClick: downloadOutline,
    })
  }

  // 交付阶段
  if (phaseIdx === 4) {
    actions.push({
      label: '复制内容',
      icon: Document,
      onClick: copyResult,
    })
  }

  return actions
})

/** 当前步骤提示 */
const phaseHint = computed(() => {
  const phaseIdx = currentPhaseIndex.value
  if (phaseIdx === 0) return '填写创作参数后点击"开始生成"'
  if (phaseIdx === 1 && useTwoStageMode.value) return '请审阅全局大纲，确认后可生成单元概述'
  if (phaseIdx === 2 && generating.value) return 'AI 正在创作中，请耐心等待...'
  if (phaseIdx === 3) return '请审阅生成结果，可进行修订或直接导出'
  if (phaseIdx === 4) return '内容已定稿，可导出或分享'
  return ''
})

// 知识库组件引用
const knowledgeBaseSectionRef = ref(null)

// ==================== 用户配置持久化（风格选择器） ====================
const { saveConfig, restoreConfig } = useConfigPersistence()

function persistGenerateStyleConfig() {
  saveConfig(`user_config_generate_${type.value}_style`, styleData.value)
}
function persistGenerateTitleStyleConfig() {
  saveConfig(`user_config_generate_${type.value}_title_style`, titleStyleData.value)
}
function restoreGenerateStyleConfig() {
  const saved = restoreConfig(`user_config_generate_${type.value}_style`)
  if (saved) {
    styleData.value = saved
    console.log('[GenerateForm] 已恢复文风配置:', saved)
  }
}
function restoreGenerateTitleStyleConfig() {
  const saved = restoreConfig(`user_config_generate_${type.value}_title_style`)
  if (saved) {
    titleStyleData.value = saved
    console.log('[GenerateForm] 已恢复标题风格配置:', saved)
  }
}

watch(styleData, () => persistGenerateStyleConfig(), { deep: true })
watch(titleStyleData, () => persistGenerateTitleStyleConfig(), { deep: true })

// ==================== 初始化 Composables ====================

// 单元概述生成
const {
  handleGenerateUnitSummaries,
  performLogicCheck,
  cancelUnitSummariesGeneration,
  handleResumeUnitSummaries,
  handleContinueGeneration,
  handleResumeUnitSummariesFromBackend,
  openStartUnitDialog,
  handleGenerateFromUnit
} = useUnitSummariesGeneration({
  type,
  form,
  globalOutlineContent,
  generatedContent,
  unitSummaries,
  outlineStage,
  currentSessionId,
  currentEventSource,
  unitSummariesGenerating,
  globalOutlineGenerating,
  showResult,
  titleStyleData,
  startFromUnit,
  showStartUnitDialog,
  expectedUnitCount,
  backendResumeInfo,
  logicChecking,
  logicCheckResult,
  generationId,
  handleWorkflowEvent,
})


// 修订模式
const {
  startRevision,
  submitRevision,
  finalizeContent,
  exitRevision
} = useRevisionMode({
  type,
  form,
  useTwoStageMode,
  isRevisionMode,
  currentRevisionRound,
  revisionInput,
  revising,
  revisionContent,
  revisionMessages,
  revisionHistory,
  generationId,
  currentGenerationId,
  globalOutlineContent,
  generatedContent,
  knowledgeRevising,
  buildOutlineInputParams: buildOutlineParams,
  unitSummaries
})

// 质量控制
const {
  startQCSSESubscription,
  stopQCSSEConnection,
  handleImportedUnitSummariesQC,
  handleUnitSummariesQC,
  handleGlobalOutlineQC,
  handleAutoGlobalOutlineRevise
} = useQualityControl({
  type,
  form,
  useTwoStageMode,
  globalOutlineContent,
  generatedContent,
  unitSummaries,
  editingGlobalOutline,
  editingGlobalOutlineContent,
  generationId,
  importedOutline,
  globalOutlineQCLoading,
  globalOutlineQCReport,
  qcProgress,
  qcSSEConnection,
  revisingIssueId,
  qcApplied,
  qcReportData,
  issuesFixed,
  autoQCLoading,
  unitSummariesQCLoading,
  showGlobalOutlineReviseDialog,
  globalOutlineReviseData,
  showUnitSummariesReviseDialog,
  unitSummariesReviseData
})

// 导入逻辑
const {
  openImportDialog,
  confirmImport,
  beforeOutlineImportUpload,
  handleOutlineImportUploadSuccess,
  handleOutlineImportUploadError,
  handleOutlineImportProgress,
  openImportUnitSummariesDialog,
  beforeUnitSummariesImportUpload,
  handleUnitSummariesImportUploadSuccess,
  handleUnitSummariesImportUploadError,
  handleUnitSummariesImportProgress
} = useImportLogic({
  type,
  globalOutlineContent,
  generatedContent,
  unitSummaries,
  outlineStage,
  showResult,
  showImportDialog,
  importType,
  importContent,
  importingOutline,
  importOutlineProgress,
  showImportUnitSummariesDialog,
  importingUnitSummaries,
  importUnitSummariesProgress,
  importedUnitSummaries,
  importedOutline,
  qcApplied,
  qcReportData,
  issuesFixed
})

// 修正处理
const {
  getRevisionDiffHtml,
  handleUnitSummariesFeedback,
  handleApplyUnitSummariesRevision,
  handleGlobalOutlineRevise,
  handleConfirmGlobalOutlineRevise,
  handleCancelGlobalOutlineRevise,
  handleConfirmUnitSummariesRevise,
  handleCancelUnitSummariesRevise,
  handleOpenUnitSummariesDiff,
  handleRemoveUnitSummariesQCDuplicates,
  handleRemoveUnitSummariesDuplicates,
  handleUpdateUnitContent,
  updateGeneratedContentUnit,
  parseUnitSummaries
} = useReviseHandlers({
  type,
  useTwoStageMode,
  globalOutlineContent,
  generatedContent,
  unitSummaries,
  editingGlobalOutline,
  editingGlobalOutlineContent,
  generationId,
  qcApplied,
  qcReportData,
  issuesFixed,
  qcProgress,
  showGlobalOutlineReviseDialog,
  globalOutlineReviseData,
  showUnitSummariesReviseDialog,
  unitSummariesReviseData,
  unitSummariesOriginalSnapshot,
  revisingIssueId,
  globalOutlineQCReport,
  stopQCSSEConnection
})

onMounted(async () => {
  await apiKeyStore.fetchApiKeys()
  restoreFormData()
  
  // 恢复用户持久化配置：风格选择器
  restoreGenerateStyleConfig()
  restoreGenerateTitleStyleConfig()
  
  // 尝试恢复上次的生成状态
  try {
    const restoreState = {
      currentGenerationId,
      generationId,
      globalOutlineContent,
      generatedContent,
      outlineStage,
      revisionMessages,
      revisionHistory,
      currentRevisionRound,
      showResult
    }
    
    const { tryRestore } = useGenerationRestore(type, restoreState)
    await tryRestore()
  } catch (error) {
    console.log('[GenerateForm] 无历史记录可恢复:', error.message)
  }
  
  // 获取后端断点信息（用于页面刷新后恢复续生成状态）
  try {
    // 如果有generationId，从后端获取断点信息
    if (generationId.value) {
      const resumeInfoResult = await generateApi.getUnitSummariesResumeInfo(generationId.value)
      if (resumeInfoResult?.success && resumeInfoResult?.data) {
        backendResumeInfo.value = resumeInfoResult.data
        console.log('[GenerateForm] 获取后端断点信息:', backendResumeInfo.value)
        
        // 如果后端显示可以续生成，且前端状态不是正在生成，则更新状态
        if (backendResumeInfo.value.can_resume && !unitSummariesGenerating.value) {
          // 如果有已生成的内容但前端没有，从后端恢复
          if (backendResumeInfo.value.existing_content && !generatedContent.value) {
            generatedContent.value = backendResumeInfo.value.existing_content
          }
          if (backendResumeInfo.value.existing_parsed && Object.keys(unitSummaries.value).length === 0) {
            unitSummaries.value = backendResumeInfo.value.existing_parsed
          }
          // 如果有全局大纲但前端没有，从后端恢复
          if (backendResumeInfo.value.global_outline && !globalOutlineContent.value) {
            globalOutlineContent.value = backendResumeInfo.value.global_outline
          }
          // 确保阶段正确
          if (outlineStage.value < 4) {
            outlineStage.value = 4  // 设置为已完成阶段，显示续生成按钮
          }
          showResult.value = true  // 显示结果区域
        }
      }
    }
  } catch (error) {
    console.log('[GenerateForm] 获取后端断点信息失败:', error.message)
  }

  // 从历史记录"继续调整"进入时，恢复该次生成的内容与参数
  await restoreFromHistory()
})

/**
 * 从历史记录恢复生成状态（通过 ?generation_id=xxx 进入）
 * 回填表单参数、正文内容与 generation_id，并显示结果区。
 */
async function restoreFromHistory() {
  const historyId = route.query?.generation_id
  if (!historyId) return

  try {
    const detail = await historyApi.get(historyId)
    if (!detail?.id) {
      ElMessage.warning('未找到该历史记录')
      return
    }

    // 回填表单参数（含模块差异字段映射）
    const params = detail.input_params || {}
    Object.entries(params).forEach(([key, value]) => {
      if (key in form.value && value !== null && value !== undefined && value !== '') {
        form.value[key] = value
      }
    })
    // 模块特有字段映射（前端表单键 -> 后端参数键）
    if (params.mode) {
      if (type.value === 'tvc' && 'tvc_mode' in form.value) form.value.tvc_mode = params.mode
      if (type.value === 'short-video' && 'video_mode' in form.value) form.value.video_mode = params.mode
    }
    if (params.generate_ai_prompt !== undefined) {
      if (type.value === 'tvc' && 'generate_ai_prompt_tvc' in form.value) {
        form.value.generate_ai_prompt_tvc = params.generate_ai_prompt === '是'
      }
      if (type.value === 'short-video' && 'generate_ai_prompt' in form.value) {
        form.value.generate_ai_prompt = params.generate_ai_prompt === '是'
      }
    }
    if (params.ai_platforms && typeof params.ai_platforms === 'string') {
      if (type.value === 'tvc' && 'ai_platforms_tvc' in form.value) form.value.ai_platforms_tvc = params.ai_platforms
      if (type.value === 'short-video' && 'ai_platforms' in form.value) {
        form.value.ai_platforms = params.ai_platforms.split(/[,，]/).map(s => s.trim()).filter(Boolean)
      }
    }
    if (params.aspect_ratio && type.value === 'tvc' && 'aspect_ratio_tvc' in form.value) {
      form.value.aspect_ratio_tvc = params.aspect_ratio
    }

    // 恢复正文与生成记录ID
    generatedContent.value = detail.output_content || ''
    currentGenerationId.value = detail.id
    generationId.value = detail.id

    // 两阶段模块：将内容恢复到全局大纲编辑区（阶段2），便于继续调整
    if (useTwoStageMode.value) {
      globalOutlineContent.value = detail.output_content || ''
      outlineStage.value = 2
    }

    showResult.value = true
    ElMessage.success('已从历史记录恢复内容，可继续调整')
    console.log('[GenerateForm] 已从历史记录恢复:', historyId, '模块:', type.value)
  } catch (error) {
    console.error('[GenerateForm] 从历史记录恢复失败:', error)
    ElMessage.error('从历史记录恢复失败: ' + (error.message || '未知错误'))
  }
}

onBeforeUnmount(() => {
  // 离开路由时释放全部实时连接：生成主流 + 质控进度 SSE
  if (currentEventSource.value && currentEventSource.value.abort) {
    currentEventSource.value.abort()
    currentEventSource.value = null
  }
  // 修复：此前遗漏关闭质控 SSE，导致离开页面后连接泄漏
  stopQCSSEConnection()
  generating.value = false
  globalOutlineGenerating.value = false
  unitSummariesGenerating.value = false
  logicChecking.value = false
})

// 监听表单变化自动保存
watch(form, () => {
  saveFormData()
}, { deep: true })

// 监听模块类型变化时恢复对应模块的表单数据和风格配置
watch(type, () => {
  restoreFormData()
  restoreGenerateStyleConfig()
  restoreGenerateTitleStyleConfig()
})

// 处理生成
async function handleGenerate() {
  // 防重复提交：如果正在生成中，直接返回（急性子用户测试发现的问题）
  if (generating.value) {
    console.warn('[GenerateForm] 生成请求进行中，忽略重复提交')
    ElMessage.warning('正在生成中，请勿重复点击')
    return
  }
  
  // 如果是小说/剧本/电影大纲/剧集大纲，使用两阶段生成
  if (useTwoStageMode.value) {
    // 获取知识库参数
    const kbParams = knowledgeBaseSectionRef.value?.getKbParams() || {}
    console.log('[GenerateForm] 两阶段生成 - kbParams:', kbParams)
    await handleTwoStageGenerate(null, null, kbParams)
    return
  }
  
  // 其他模块使用原有生成逻辑
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  if (!apiKeyStore.defaultKey) {
    const hasKeys = apiKeyStore.apiKeys.length > 0
    if (hasKeys) {
      ElMessage.warning('请在API Key管理页面设置一个默认Key')
    } else {
      ElMessage.warning('请先添加API Key')
    }
    router.push('/api-keys')
    return
  }
  
  generating.value = true
  showResult.value = true
  generatedContent.value = ''
  currentGenerationId.value = null
  
  // 生成唯一会话ID
  const sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
  currentSessionId.value = sessionId
  
  // 重置工作流程状态
  workflowSteps.value = []
  currentStep.value = ''
  workflowComplete.value = false
  
  try {
    const apiMethod = {
      'short-video': generateApi.shortVideo,
      'movie-outline': generateApi.movieOutline,
      'series-outline': generateApi.seriesOutline,
      'novel': generateApi.novel,
      'print-ad': generateApi.printAd,
      'tvc': generateApi.tvc,
      'original-ip': generateApi.originalIp,
      'practical-writing': generateApi.practicalWriting
    }[type.value]
    
    // 获取知识库参数
    const kbParams = knowledgeBaseSectionRef.value?.getKbParams() || {}
    console.log('[GenerateForm] kbParams from KnowledgeBaseSection:', kbParams)
    
    // 根据模块类型映射字段名
    let submitData = {}
    
    if (type.value === 'short-video') {
      submitData = {
        topic: form.value.title,
        audience: form.value.target_audience,
        description: form.value.description,
        platform: form.value.platform || '抖音',
        style: combinedStyleTypes.value || '轻松有趣',
        duration: parseInt(form.value.duration) || 60,
        aspect_ratio: form.value.aspect_ratio || '9:16',
        mode: form.value.video_mode || 'virtual',
        generate_ai_prompt: form.value.video_mode === 'virtual' && form.value.generate_ai_prompt ? '是' : '否',
        generate_storyboard_images: form.value.video_mode === 'virtual' && form.value.generate_storyboard_images ? '是' : '否',
        ai_platforms: form.value.video_mode === 'virtual' ? (form.value.ai_platforms?.join(', ') || '无') : '无',
        reference_video: form.value.reference_video || null,
        reference_materials: form.value.reference_materials || null,
        account_tone: form.value.account_tone || null,
        target_fans: form.value.target_fans || null,
        content_position: form.value.content_position || null,
        enable_knowledge: kbParams.enableKnowledge,
        enable_creative_search: kbParams.enableCreativeSearch,
        enable_trending: kbParams.enableTrending,
        ...kbParams
      }
    } else if (type.value === 'movie-outline') {
      // NOTE: 当前 movie-outline 始终走两阶段模式（useTwoStageMode=true），
      // 此分支为死代码。保留用于未来可能支持单阶段生成时参考参数映射。
      submitData = {
        title: form.value.title,
        movie_type: form.value.movie_type || '院线电影',
        theme: Array.isArray(form.value.genre) ? form.value.genre.join('、') : (form.value.genre || '剧情'),
        audience: form.value.target_audience,
        platform: form.value.platform || '院线发行',
        reference_works: form.value.reference_works || '无',
        synopsis: form.value.description,
        scene_count: form.value.scene_count || null,
        custom_outline: form.value.custom_outline || null,
        duration_range: `${form.value.duration_range[0]}-${form.value.duration_range[1]}分钟`,
        scene_count_range: form.value.scene_count_range || 'AI自动设计',
        format_standard: form.value.format_standard || '标准格式',
        dialogue_narration_ratio: form.value.dialogue_narration_ratio || '均衡',
        target_broadcast: form.value.target_broadcast || '未指定',
        script_mode: form.value.script_mode || 'real',
        enable_knowledge: kbParams.enableKnowledge,
        enable_creative_search: kbParams.enableCreativeSearch,
        enable_trending: kbParams.enableTrending,
        ...kbParams
      }
    } else if (type.value === 'series-outline') {
      // NOTE: 当前 series-outline 始终走两阶段模式（useTwoStageMode=true），
      // 此分支为死代码。保留用于未来可能支持单阶段生成时参考参数映射。
      submitData = {
        title: form.value.title,
        series_type: form.value.series_type || '电视剧',
        theme: Array.isArray(form.value.genre) ? form.value.genre.join('、') : (form.value.genre || '都市'),
        audience: form.value.target_audience,
        platform: form.value.platform || '爱奇艺',
        reference_works: form.value.reference_works || '无',
        synopsis: form.value.description,
        episode_count: form.value.episode_count || null,
        custom_outline: form.value.custom_outline || null,
        episode_duration_range: `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟`,
        scenes_per_episode_range: form.value.scenes_per_episode_range || 'AI自动设计',
        format_standard: form.value.format_standard || '标准格式',
        dialogue_narration_ratio: form.value.dialogue_narration_ratio || '均衡',
        target_broadcast: form.value.target_broadcast || '未指定',
        script_mode: form.value.script_mode || 'real',
        enable_knowledge: kbParams.enableKnowledge,
        enable_creative_search: kbParams.enableCreativeSearch,
        enable_trending: kbParams.enableTrending,
        ...kbParams
      }
    } else if (type.value === 'novel') {
      const lengthMap = { 'short': '短篇', 'medium': '中篇', 'long': '长篇' }
      submitData = {
        title: form.value.title,
        length: lengthMap[form.value.length] || '中篇',
        genre: Array.isArray(form.value.genre) ? form.value.genre.join('、') : (form.value.genre || '言情'),
        target_platform: form.value.target_platform || '起点',
        tone: form.value.tone || '正剧',
        theme: form.value.theme || '',
        unique_selling_point: form.value.unique_selling_point || '',
        synopsis: form.value.description,
        chapter_count: form.value.chapter_count || null,
        custom_outline: form.value.custom_outline || null,
        enable_knowledge: kbParams.enableKnowledge,
        enable_creative_search: kbParams.enableCreativeSearch,
        enable_trending: kbParams.enableTrending,
        ...kbParams
      }
    } else if (type.value === 'print-ad') {
      submitData = {
        title: form.value.title,
        design_category: form.value.design_category || '商业广告',
        brand_product: form.value.brand_product,
        ad_purpose: form.value.ad_purpose,
        core_message: form.value.core_message,
        audience_profile: form.value.audience_profile,
        contact_scene: form.value.contact_scene,
        style_tone: form.value.style_tone || '视觉冲击',
        copy_content: form.value.copy_content || null,
        size_spec: form.value.size_spec || null,
        publish_media: form.value.publish_media || null,
        ai_platforms: form.value.ai_platforms_ad || '豆包',
        description: form.value.description || null,
        images: form.value.images.length > 0 ? form.value.images : null,
        enable_knowledge: kbParams.enableKnowledge,
        enable_creative_search: kbParams.enableCreativeSearch,
        enable_trending: kbParams.enableTrending,
        ...kbParams
      }
    } else if (type.value === 'tvc') {
      submitData = {
        title: form.value.title,
        brand_product: form.value.brand_product,
        ad_purpose: form.value.ad_purpose,
        core_message: form.value.core_message,
        audience_profile: form.value.audience_profile,
        broadcast_platform: form.value.broadcast_platform || '视频平台',
        style_tone: form.value.style_tone || '温情走心',
        duration: parseInt(form.value.duration) || 30,
        aspect_ratio: form.value.aspect_ratio_tvc || '16:9',
        mode: form.value.tvc_mode || 'real',
        generate_ai_prompt: form.value.generate_ai_prompt_tvc ? '是' : '否',
        ai_platforms: form.value.ai_platforms_tvc || 'Seedance 2.0',
        reference_video: form.value.reference_video || null,
        description: form.value.description || null,
        enable_knowledge: kbParams.enableKnowledge,
        enable_creative_search: kbParams.enableCreativeSearch,
        enable_trending: kbParams.enableTrending,
        ...kbParams
      }
    } else if (type.value === 'original-ip') {
      submitData = {
        ip_description: form.value.ip_description,
        target_platform: form.value.target_platform || '综合',
        reference_ip: form.value.reference_ip || null,
        commercial_goal: form.value.commercial_goal || null,
        custom_requirements: form.value.custom_requirements || null,
        enable_knowledge: kbParams.enableKnowledge,
        enable_creative_search: kbParams.enableCreativeSearch,
        enable_trending: kbParams.enableTrending,
        ...kbParams
      }
    } else if (type.value === 'practical-writing') {
      if (!form.value.doc_type) {
        ElMessage.warning('请选择文案类型')
        generating.value = false
        return
      }
      if (!form.value.industry) {
        ElMessage.warning('请选择所属行业')
        generating.value = false
        return
      }
      submitData = {
        title: form.value.title,
        doc_type: form.value.doc_type || '演讲稿',
        industry: form.value.industry || '信息技术/互联网',
        description: form.value.description,
        doc_length: form.value.doc_length_custom || '中篇（1000-3000字）',
        formality: form.value.formality || '半正式',
        target_audience: form.value.target_audience || '上级领导/管理层',
        language_style: form.value.language_style || '专业严谨',
        additional_requirements: form.value.additional_requirements || '',
        reference_document: form.value.reference_document || null,
        reference_document_name: form.value.reference_document_name || null,
        enable_knowledge: kbParams.enableKnowledge,
        enable_creative_search: kbParams.enableCreativeSearch,
        enable_trending: kbParams.enableTrending,
        ...kbParams
      }
    }
    
    // 调试日志：输出提交数据
    console.log('[GenerateForm] submitData:', submitData)
    
    const result = await apiMethod(submitData, (fullContent, newContent) => {
      generatedContent.value = fullContent
    }, (workflowEvent) => {
      handleWorkflowEvent(workflowEvent)
    }, (eventSource) => {
      currentEventSource.value = eventSource
    }, sessionId)
    
    if (result) {
      if (result.generation_id) {
        currentGenerationId.value = result.generation_id
      }
      if (result.duration_ms) {
        generationDuration.value = result.duration_ms
      }
    }
    
    workflowComplete.value = true
    ElMessage.success('生成完成')
  } catch (error) {
    console.error('生成失败:', error)
    ElMessage.error('生成失败，请重试')
  } finally {
    generating.value = false
  }
}

// 中断生成
async function handleStop() {
  if (currentEventSource.value && currentEventSource.value.abort) {
    currentEventSource.value.abort()
    currentEventSource.value = null
  }
  // 中断生成时一并释放质控进度 SSE，避免残留连接
  stopQCSSEConnection()
  
  if (currentSessionId.value) {
    try {
      await fetch(`${API_BASE_URL}/api/v1/generate/cancel/${currentSessionId.value}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${userStore.token}`,
          'Content-Type': 'application/json'
        }
      })
    } catch (error) {
      console.warn('发送取消请求失败:', error)
    }
  }
  
  generating.value = false
  globalOutlineGenerating.value = false
  unitSummariesGenerating.value = false
  workflowComplete.value = true
  
  workflowSteps.value.push({
    step: 'stopped',
    status: 'error',
    message: '生成已被用户中断',
    icon: 'CircleClose'
  })
  
  ElMessage.warning('已中断生成')
}

// ==================== 两阶段大纲生成（第一阶段） ====================

// 开始两阶段生成（第一阶段：全局大纲）
async function handleTwoStageGenerate(apiKeyStoreRef, routerRef, kbParams = {}) {
  // API Key 检查
  if (!apiKeyStore.defaultKey) {
    const hasKeys = apiKeyStore.apiKeys.length > 0
    if (hasKeys) {
      ElMessage.warning('请在API Key管理页面设置一个默认Key')
    } else {
      ElMessage.warning('请先添加API Key')
    }
    router.push('/api-keys')
    return
  }
  
  // 重置工作流程状态
  workflowSteps.value = []
  currentStep.value = ''
  workflowComplete.value = false
  
  // 开始第一阶段
  outlineStage.value = 1
  globalOutlineGenerating.value = true
  globalOutlineContent.value = ''
  showResult.value = true
  generatedContent.value = ''
  
  try {
    const inputParams = buildOutlineInputParams()
    
    setTimeout(() => {
      if (globalOutlineGenerating.value) {
        workflowSteps.value.push({ step: 'model', status: 'done', message: '已加载模型', icon: 'Cpu' })
        workflowSteps.value.push({ step: 'prompt', status: 'running', message: '正在准备提示词...', icon: 'Document' })
      }
    }, 500)
    
    setTimeout(() => {
      if (globalOutlineGenerating.value) {
        const promptIndex = workflowSteps.value.findIndex(s => s.step === 'prompt')
        if (promptIndex >= 0) {
          workflowSteps.value[promptIndex] = { step: 'prompt', status: 'done', message: '提示词准备完成', icon: 'Document' }
        }
      }
    }, 1000)
    
    const enableKnowledge = kbParams.enableKnowledge || false
    const enableAutoQC = kbParams.enableAutoQC || false
    
    const result = await generateApi.generateGlobalOutlineStream(
      {
        content_type: backendContentType.value,
        input_params: inputParams,
        provider: null,
        model: null,
        temperature: 0.7,
        enable_knowledge: enableKnowledge,
        enable_auto_qc: enableAutoQC
      },
      (chunk, fullContent) => {
        globalOutlineContent.value = fullContent
        generatedContent.value = fullContent
      },
      (abortController) => {
        currentEventSource.value = abortController
      },
      (event) => {
        handleWorkflowEvent(event)
      },
      (newContent, message) => {
        globalOutlineContent.value = newContent
        generatedContent.value = newContent
        ElMessage.success(message || '内容已优化')
      }
    )
    
    if (result && !result.cancelled) {
      // [2026-05-05] 修复：从SSE响应中提取generation_id，用于后续单元概述生成时传递project_id
      if (result.generation_id) {
        currentGenerationId.value = result.generation_id
        generationId.value = result.generation_id
        console.log('[handleTwoStageGenerate] 捕获generation_id:', result.generation_id)
      } else {
        console.warn('[handleTwoStageGenerate] ⚠️ generation_id未获取到，续生成功能将不可用')
      }
      outlineStage.value = 2
      ElMessage.success('全局大纲生成完成，请审核后继续生成单元概述')
    }
  } catch (error) {
    console.error('全局大纲生成失败:', error)
    const runningStep = workflowSteps.value.find(s => s.status === 'running')
    if (runningStep) {
      runningStep.status = 'error'
      runningStep.message = '生成失败: ' + (error.message || '未知错误')
    }
    ElMessage.error('全局大纲生成失败：' + (error.message || '未知错误'))
    outlineStage.value = 0
  } finally {
    globalOutlineGenerating.value = false
  }
}

// ==================== 保留在主组件中的简单处理函数 ====================

// 开始编辑全局大纲
function startEditGlobalOutline() {
  editingGlobalOutlineContent.value = globalOutlineContent.value
  editingGlobalOutline.value = true
}

// 保存全局大纲编辑
function saveGlobalOutlineEdit() {
  globalOutlineContent.value = editingGlobalOutlineContent.value
  editingGlobalOutline.value = false
  ElMessage.success('全局大纲已修改')
}

// 取消编辑全局大纲
function cancelEditGlobalOutline() {
  editingGlobalOutline.value = false
  editingGlobalOutlineContent.value = ''
}

// 编辑单元概述
function editUnitSummary(unitNum) {
  editingUnitNumber.value = unitNum.toString()
  editingUnitContent.value = unitSummaries.value[unitNum.toString()]?.summary || ''
}

// 保存单元概述修改
function saveUnitSummary() {
  if (editingUnitNumber.value && unitSummaries.value[editingUnitNumber.value]) {
    unitSummaries.value[editingUnitNumber.value].summary = editingUnitContent.value
    editingUnitNumber.value = null
    editingUnitContent.value = ''
    ElMessage.success('单元概述已更新')
  }
}

// 取消编辑单元概述
function cancelEditUnitSummary() {
  editingUnitNumber.value = null
  editingUnitContent.value = ''
}

// 下载大纲
function downloadOutline() {
  const content = outlineStage.value === 2 ? globalOutlineContent.value : generatedContent.value
  const blob = new Blob([content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${form.value.title || '大纲'}_${outlineStage.value === 2 ? '全局大纲' : '完整大纲'}.md`
  a.click()
  URL.revokeObjectURL(url)
  trackAction('download')
}

// 重置两阶段生成状态
function resetTwoStageOutline() {
  outlineStage.value = 0
  globalOutlineContent.value = ''
  unitSummaries.value = {}
  globalOutlineGenerating.value = false
  unitSummariesGenerating.value = false
  showResult.value = false
  generatedContent.value = ''
  startFromUnit.value = 1
}

// 打开修正详情对话框
function openRevisionDetail(unitNum) {
  currentRevisionUnit.value = unitNum.toString()
  revisionViewMode.value = 'diff'
  showRevisionDetailDialog.value = true
}

// 重新生成
function regenerate() {
  trackAction('regenerate')
  handleGenerate()
}

/**
 * 处理质量报告更新
 */
function handleUpdateQualityReport(newReport) {
  qualityReport.value = newReport
}

// 构建大纲输入参数（薄包装，委托给工具函数）
function buildOutlineInputParams() {
  return buildOutlineParams(type.value, form.value, styleData.value, titleStyleData.value)
}

// ==================== P0改造：一键创建写作项目 ====================

/**
 * 一键创建写作项目
 * 流程：创建项目 → 填入大纲和单元概述 → 跳转工作台
 */
async function handleCreateWritingProject() {
  if (!globalOutlineContent.value) {
    ElMessage.warning('请先生成或导入全局大纲')
    return
  }
  
  creatingWritingProject.value = true
  
  try {
    // 步骤1：创建新项目
    const projectName = form.value.title || `小说项目_${new Date().toLocaleDateString()}`
    const createResponse = await novelWriterApi.createProject({
      name: projectName,
      description: form.value.description || '从创意生成页面一键创建',
      project_type: 'novel'
    })
    
    if (!createResponse.data?.id) {
      throw new Error('创建项目失败：未返回项目ID')
    }
    
    const projectId = createResponse.data.id
    console.log('[handleCreateWritingProject] 项目创建成功:', projectId)
    
    // 步骤2：更新项目内容（填入全局大纲和单元概述）
    const updateData = {
      outline_content: globalOutlineContent.value
    }
    
    // 如果有单元概述，也一并填入
    if (Object.keys(unitSummaries.value).length > 0) {
      updateData.unit_summaries = unitSummaries.value
    }
    
    await novelWriterApi.updateProject(projectId, updateData)
    console.log('[handleCreateWritingProject] 大纲和单元概述已填入')
    
    ElMessage.success(`项目"${projectName}"创建成功，正在跳转工作台...`)
    
    // 步骤3：跳转到写作工作台
    router.push({ name: 'NovelWriterDetail', params: { id: projectId } })
    
  } catch (error) {
    console.error('[handleCreateWritingProject] 创建写作项目失败:', error)
    ElMessage.error('创建写作项目失败：' + (error.message || '未知错误'))
  } finally {
    creatingWritingProject.value = false
  }
}

// ==================== 以下函数已提取到 composables，仅保留声明 ====================

// handleGenerateUnitSummaries → useUnitSummariesGeneration
// performLogicCheck → useUnitSummariesGeneration
// cancelUnitSummariesGeneration → useUnitSummariesGeneration
// handleResumeUnitSummaries → useUnitSummariesGeneration
// handleContinueGeneration → useUnitSummariesGeneration
// handleResumeUnitSummariesFromBackend → useUnitSummariesGeneration
// openStartUnitDialog → useUnitSummariesGeneration
// handleGenerateFromUnit → useUnitSummariesGeneration
// startRevision, submitRevision, finalizeContent, exitRevision → useRevisionMode

/**
 * 处理单元概述对话修订
 */
function handleStartUnitSummariesRevision() {
  startRevision('units')
}
// startQCSSESubscription, stopQCSSEConnection → useQualityControl
// handleImportedUnitSummariesQC, handleUnitSummariesQC → useQualityControl
// handleGlobalOutlineQC, handleAutoGlobalOutlineRevise → useQualityControl
// openImportDialog, confirmImport, etc. → useImportLogic
// handleUnitSummariesIssueRevise, handleGlobalOutlineRevise, etc. → useReviseHandlers
</script>

<style lang="scss" scoped>
.generate-form-page {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 20px;
}

.page-header {
  margin-bottom: 24px;
  background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
  border-radius: 16px;
  padding: 20px 24px;
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: 
      radial-gradient(ellipse at 20% 50%, rgba(64, 158, 255, 0.1) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 50%, rgba(0, 212, 170, 0.08) 0%, transparent 50%);
    pointer-events: none;
  }
  
  .header-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    z-index: 1;
  }
  
  .header-actions {
    display: flex;
    gap: 8px;
    
    .el-button {
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(64, 158, 255, 0.2);
      color: rgba(255, 255, 255, 0.8);
      border-radius: 8px;
      
      &:hover {
        background: rgba(64, 158, 255, 0.2);
        border-color: rgba(64, 158, 255, 0.4);
        color: #fff;
      }
    }
  }
  
  .header-info {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 20px 0 10px;
    position: relative;
    z-index: 1;
    
    .el-icon {
      color: #409EFF;
    }
    
    h1 {
      font-size: 24px;
      background: linear-gradient(90deg, #fff, #409EFF, #00D4AA);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      font-weight: 600;
    }
  }
  
  p {
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
    position: relative;
    z-index: 1;
  }
}

.main-container {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
  align-items: flex-start;
}

.left-panel {
  flex: 1;
  min-width: 0;
  
  .form-container {
    background: #fff;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    border: 1px solid rgba(64, 158, 255, 0.08);
    max-height: calc(100vh - 200px);
    overflow-y: auto;
    
    &::-webkit-scrollbar {
      width: 6px;
    }
    
    &::-webkit-scrollbar-track {
      background: #f5f7fa;
      border-radius: 3px;
    }
    
    &::-webkit-scrollbar-thumb {
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 3px;
      
      &:hover {
        background: #409EFF;
      }
    }
  }
}

.right-panel {
  width: 420px;
  flex-shrink: 0;
}

// 质量管控配置区域样式
.quality-control-section {
  margin-top: 24px;
  padding: 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ebf0 100%);
  border-radius: 8px;
  border: 1px solid #dcdfe6;
  
  :deep(.el-divider__text) {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    color: #303133;
  }
  
  .mode-description {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 8px;
    
    .desc-text {
      font-size: 13px;
      color: #606266;
    }
  }
  
  :deep(.el-checkbox-group) {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    
    .el-checkbox {
      margin-right: 0;
      
      .el-checkbox__label {
        display: flex;
        align-items: center;
        gap: 6px;
      }
    }
  }
  
  :deep(.el-radio-button) {
    .el-radio-button__inner {
      display: flex;
      align-items: center;
      gap: 6px;
    }
  }
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 24px;
  margin-top: 24px;
  border-top: 1px solid rgba(64, 158, 255, 0.1);
  
  .el-button {
    min-width: 100px;
    font-weight: 500;
    border-radius: 10px;
  }
  
  .el-button--primary {
    background: linear-gradient(135deg, #409EFF 0%, #00D4AA 100%);
    border: none;
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
    
    &:hover {
      box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4);
      transform: translateY(-1px);
    }
  }
}

// 导入对话框样式
.import-dialog-content {
  .import-type-selector {
    display: flex;
    gap: 24px;
    margin-bottom: 20px;
    
    .el-radio {
      height: auto;
      padding: 16px;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      margin-right: 0;
      
      &.is-checked {
        border-color: var(--el-color-primary);
        background: var(--el-color-primary-light-9);
      }
    }
    
    .import-type-option {
      display: flex;
      flex-direction: column;
      gap: 4px;
      
      .title {
        font-weight: 500;
        font-size: 14px;
      }
      
      .desc {
        font-size: 12px;
        color: #909399;
      }
    }
  }
  
  .import-tips {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: #f4f4f5;
    border-radius: 6px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #606266;
    
    .el-icon {
      color: #909399;
    }
  }
  
  .file-upload-area {
    .outline-uploader {
      width: 100%;
      
      :deep(.el-upload) {
        width: 100%;
      }
      
      :deep(.el-upload-dragger) {
        padding: 40px 20px;
        border: 2px dashed #dcdfe6;
        border-radius: 8px;
        background: #fafafa;
        transition: all 0.3s;
        
        &:hover {
          border-color: var(--el-color-primary);
          background: #f5f7fa;
        }
      }
      
      :deep(.el-icon--upload) {
        font-size: 48px;
        color: #c0c4cc;
        margin-bottom: 16px;
      }
      
      :deep(.el-upload__text) {
        color: #606266;
        font-size: 14px;
        
        em {
          color: var(--el-color-primary);
          font-style: normal;
          font-weight: 500;
        }
      }
      
      :deep(.el-upload__tip) {
        font-size: 12px;
        color: #909399;
        margin-top: 8px;
      }
    }
    
    .upload-progress {
      margin-top: 16px;
    }
  }
  
  .import-textarea {
    .el-textarea__inner {
      font-family: monospace;
      font-size: 13px;
      line-height: 1.5;
    }
  }
}

// 全局大纲修正对比对话框样式 (v2.2新增)
.revise-compare-dialog {
  .content-comparison {
    margin-top: 12px;
  }
  
  .comparison-panel {
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    overflow: hidden;
    
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      background: #f5f7fa;
      border-bottom: 1px solid #e4e7ed;
      
      .word-count {
        font-size: 12px;
        color: #909399;
      }
    }
    
    .comparison-textarea {
      :deep(.el-textarea__inner) {
        font-family: monospace;
        font-size: 12px;
        line-height: 1.5;
        background: #fafafa;
        border: none;
        border-radius: 0;
      }
      
      &.revised {
        :deep(.el-textarea__inner) {
          background: #f0f9eb;
        }
      }
    }
  }
}

// 从指定单元开始对话框样式
.start-unit-dialog-content {
  .start-unit-tip {
    color: #606266;
    line-height: 1.6;
    margin-bottom: 20px;
  }
  
  .start-unit-warning {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: #fdf6ec;
    border-radius: 6px;
    margin-top: 16px;
    font-size: 13px;
    color: #e6a23c;
    
    .el-icon {
      font-size: 16px;
    }
  }
}

// 逻辑问题详情对话框样式
.logic-issues-dialog {
  .issue-item {
    padding: 12px;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    margin-bottom: 12px;
    
    &:last-child {
      margin-bottom: 0;
    }
    
    .issue-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
      
      .issue-unit {
        font-size: 13px;
        color: #909399;
      }
    }
    
    .issue-description {
      margin: 0;
      font-size: 14px;
      color: #606266;
      line-height: 1.6;
    }
  }
}

// 修正详情对话框样式
.revision-detail-container {
  .revision-info-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 8px;
    margin-bottom: 16px;
    
    .revision-stats {
      font-size: 14px;
      color: #606266;
      
      strong {
        color: #303133;
      }
    }
  }
  
  .view-switch {
    margin-bottom: 16px;
  }
  
  .diff-view {
    .diff-legend {
      display: flex;
      gap: 16px;
      margin-bottom: 12px;
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 6px;
      
      .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #606266;
        
        .legend-color {
          width: 16px;
          height: 16px;
          border-radius: 3px;
        }
        
        &.added .legend-color {
          background: #d4edda;
          border: 1px solid #c3e6cb;
        }
        
        &.removed .legend-color {
          background: #f8d7da;
          border: 1px solid #f5c6cb;
        }
        
        &.unchanged .legend-color {
          background: transparent;
          border: 1px solid #dcdfe6;
        }
      }
    }
    
    .diff-content {
      padding: 16px;
      font-family: 'Microsoft YaHei', sans-serif;
      line-height: 1.8;
      font-size: 14px;
      max-height: 400px;
      overflow-y: auto;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      
      :deep(.diff-paragraph) {
        padding: 8px 12px;
        margin-bottom: 8px;
        border-radius: 4px;
        white-space: pre-wrap;
        word-break: break-word;
        
        &.unchanged {
          background: transparent;
          color: #303133;
        }
        
        &.added {
          background: #d4edda;
          border-left: 4px solid #28a745;
          color: #155724;
        }
        
        &.removed {
          background: #f8d7da;
          border-left: 4px solid #dc3545;
          color: #721c24;
          text-decoration: line-through;
          opacity: 0.8;
        }
      }
    }
  }
  
  .compare-view {
    display: flex;
    gap: 16px;
    
    .compare-panel {
      flex: 1;
      display: flex;
      flex-direction: column;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      overflow: hidden;
      
      .panel-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        background: #f5f7fa;
        border-bottom: 1px solid #e4e7ed;
        
        .panel-word-count {
          font-size: 13px;
          color: #909399;
        }
      }
      
      .panel-content {
        flex: 1;
        overflow: hidden;
        
        .el-textarea {
          height: 100%;
          
          :deep(.el-textarea__inner) {
            height: 300px !important;
            min-height: 300px !important;
            border: none;
            border-radius: 0;
            font-family: 'Microsoft YaHei', sans-serif;
            line-height: 1.8;
          }
        }
      }
    }
  }
}
</style>
