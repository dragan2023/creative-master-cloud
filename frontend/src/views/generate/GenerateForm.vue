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
              :series-duration-hint="seriesDurationHint"
              :image-file-list="imageFileList"
              :image-url-input="imageUrlInput"
              @optimize="handleOptimizePrompt"
              @series-type-change="handleSeriesTypeChange"
              @outline-upload-success="handleOutlineUploadSuccess"
              @outline-upload-error="handleOutlineUploadError"
              @outline-progress="handleOutlineProgress"
              @remove-outline="removeOutlineFile"
              @reference-upload-success="handleReferenceMaterialsUploadSuccess"
              @reference-upload-error="handleReferenceMaterialsUploadError"
              @remove-reference-file="removeReferenceMaterialsFile"
              @image-upload-success="handleUploadSuccess"
              @image-upload-error="handleUploadError"
              @parse-image-urls="parseImageUrls"
              @update:style-data="handleStyleDataUpdate"
              @update:title-style-data="handleTitleStyleDataUpdate"
            />
            
            <!-- 知识库增强区域 -->
            <KnowledgeBaseSection ref="knowledgeBaseSectionRef" />
            
            <!-- 质量管控配置区域 -->
            <div class="quality-control-section">
              <el-divider content-position="left">
                <el-icon><Setting /></el-icon>
                质量管控配置
              </el-divider>
                          
              <el-form-item label="自动质控修正">
                <el-switch 
                  v-model="enableAutoQC" 
                  active-text="启用" 
                  inactive-text="禁用"
                  @change="handleAutoQCChange"
                />
                <span class="form-tip">启用后，生成完成后将自动检测并修正质量问题</span>
              </el-form-item>
                          
              <el-form-item label="质控模式">
                <el-radio-group v-model="qualityControlMode" @change="handleQualityModeChange">
                  <el-radio-button 
                    v-for="mode in qualityControlModes"
                    :key="mode.key" 
                    :value="mode.key"
                    :title="mode.description"
                  >
                    <el-icon><component :is="mode.icon" /></el-icon>
                    {{ mode.label }}
                  </el-radio-button>
                </el-radio-group>
                <div class="mode-description">
                  <el-tag :type="currentQualityMode.type" size="small">
                    {{ currentQualityMode.timeEstimate }}
                  </el-tag>
                  <span class="desc-text">{{ currentQualityMode.description }}</span>
                </div>
              </el-form-item>
              
              <el-form-item v-if="qualityControlMode !== 'quick'" label="质控维度">
                <el-checkbox-group v-model="qualityDimensions">
                  <el-checkbox 
                    v-for="dim in unitQualityDimensions" 
                    :key="dim.key" 
                    :label="dim.key"
                  >
                    <el-icon><component :is="dim.icon" /></el-icon>
                    {{ dim.label }}
                  </el-checkbox>
                </el-checkbox-group>
              </el-form-item>
            </div>
            
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
      :enable-auto-revise="enableAutoRevise"
      @update:enable-auto-revise="enableAutoRevise = $event"
      :truncation-info="truncationInfo"
      :is-continuing="isContinuing"
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
      @submit-revision="submitRevision"
      @finalize-content="finalizeContent"
      @exit-revision="exitRevision"
      @update:revisionInput="revisionInput = $event"
      @analyze-global-outline-qc="handleGlobalOutlineQC"
      @revise-global-outline="handleGlobalOutlineRevise"
      @update-quality-report="handleUpdateQualityReport"
      @update-unit-content="handleUpdateUnitContent"
      @quality-control="handleImportedUnitSummariesQC"
      @quality-control-unit-summaries="handleUnitSummariesQC"
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
    />
  </div>

  <!-- 导入已有大纲对话框 -->
  <el-dialog
    v-model="showImportDialog"
    title="导入已有大纲"
    width="700px"
    :close-on-click-modal="false"
  >
    <div class="import-dialog-content">
      <el-radio-group v-model="importType" class="import-type-selector">
        <el-radio value="global">
          <div class="import-type-option">
            <span class="title">仅全局大纲</span>
            <span class="desc">导入全局大纲后，继续生成单元概述</span>
          </div>
        </el-radio>
        <el-radio value="full">
          <div class="import-type-option">
            <span class="title">完整大纲</span>
            <span class="desc">包含全局大纲和单元概述的完整内容</span>
          </div>
        </el-radio>
      </el-radio-group>
      
      <div class="import-tips">
        <el-icon><InfoFilled /></el-icon>
        <span v-if="importType === 'global'">
          请上传全局大纲文件（支持 .md、.txt、.docx 格式），系统将跳过第一阶段，直接进入审核修改阶段
        </span>
        <span v-else>
          请上传完整大纲文件（包含全局大纲和单元概述），系统将尝试解析并跳转到完成阶段
        </span>
      </div>
      
      <!-- 文件上传区域 -->
      <div class="file-upload-area">
        <el-upload
          class="outline-uploader"
          drag
          :action="outlineImportUploadUrl"
          :headers="uploadHeaders"
          :before-upload="beforeOutlineImportUpload"
          :on-success="handleOutlineImportUploadSuccess"
          :on-error="handleOutlineImportUploadError"
          :on-progress="handleOutlineImportProgress"
          :show-file-list="true"
          :limit="1"
          accept=".md,.txt,.docx,.doc"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 .md、.txt、.docx、.doc 格式，文件大小不超过 10MB
            </div>
          </template>
        </el-upload>
        
        <!-- 上传进度条 -->
        <el-progress
          v-if="importingOutline"
          :percentage="importOutlineProgress"
          :stroke-width="4"
          class="upload-progress"
        />
      </div>
    </div>
    <template #footer>
      <el-button @click="showImportDialog = false">取消</el-button>
    </template>
  </el-dialog>

  <!-- 导入单元概述对话框 -->
  <el-dialog
    v-model="showImportUnitSummariesDialog"
    title="导入已有单元概述"
    width="700px"
    :close-on-click-modal="false"
  >
    <div class="import-dialog-content">
      <div class="import-tips">
        <el-icon><InfoFilled /></el-icon>
        <span>
          请上传单元概述文件（支持 .md、.txt、.docx 格式）。
          导入后将自动解析章节内容，您可以手动触发质控检测。
        </span>
      </div>
      
      <el-upload
        class="import-uploader"
        drag
        :action="unitSummariesImportUploadUrl"
        :before-upload="beforeUnitSummariesImportUpload"
        :on-success="handleUnitSummariesImportUploadSuccess"
        :on-error="handleUnitSummariesImportUploadError"
        :on-progress="handleUnitSummariesImportProgress"
        :show-file-list="false"
        accept=".md,.txt,.docx,.doc"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .md、.txt、.docx 格式，文件大小不超过 100MB
          </div>
        </template>
      </el-upload>
      
      <div v-if="importingUnitSummaries" class="import-progress">
        <el-progress :percentage="importUnitSummariesProgress" />
        <span>正在上传并解析...</span>
      </div>
    </div>
    <template #footer>
      <el-button @click="showImportUnitSummariesDialog = false">取消</el-button>
    </template>
  </el-dialog>

  <!-- 从指定单元开始对话框 -->
  <el-dialog
    v-model="showStartUnitDialog"
    title="从指定单元重新生成"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="start-unit-dialog-content">
      <p class="start-unit-tip">
        选择从哪个单元开始重新生成。该单元及之后的所有单元概述将被重新生成，之前的单元概述将保留。
      </p>
      <el-form-item label="起始单元编号">
        <el-input-number
          v-model="startFromUnit"
          :min="1"
          :max="type === 'novel' ? (parseInt(form.chapter_count) || 50) : (parseInt(form.episode_count) || 24)"
          :step="1"
        />
      </el-form-item>
      <p class="start-unit-warning">
        <el-icon><WarningFilled /></el-icon>
        注意：从第 {{ startFromUnit }} 单元开始的所有内容将被覆盖
      </p>
    </div>
    <template #footer>
      <el-button @click="showStartUnitDialog = false">取消</el-button>
      <el-button type="primary" @click="handleGenerateFromUnit" :loading="unitSummariesGenerating">
        开始生成
      </el-button>
    </template>
  </el-dialog>

  <!-- 逻辑问题详情对话框 -->
  <el-dialog
    v-model="showLogicIssuesDialog"
    title="逻辑问题详情"
    width="600px"
  >
    <div class="logic-issues-dialog">
      <div v-for="(issue, index) in logicCheckResult?.issues" :key="index" class="issue-item">
        <div class="issue-header">
          <el-tag :type="issue.severity === 'high' ? 'danger' : issue.severity === 'medium' ? 'warning' : 'info'">
            {{ issue.type }}
          </el-tag>
          <span class="issue-unit">单元 {{ issue.unit_number }}</span>
        </div>
        <p class="issue-description">{{ issue.description }}</p>
      </div>
    </div>
    <template #footer>
      <el-button type="primary" @click="showLogicIssuesDialog = false">确定</el-button>
    </template>
  </el-dialog>

  <!-- 修正详情对话框 -->
  <el-dialog
    v-model="showRevisionDetailDialog"
    :title="`修正详情 - 第${currentRevisionUnit ? unitSummaries[currentRevisionUnit]?.unit_number : ''}${type === 'novel' ? '章' : '集'}`"
    width="800px"
    top="5vh"
  >
    <div v-if="currentRevisionUnit && unitSummaries[currentRevisionUnit]" class="revision-detail-container">
      <!-- 修正信息 -->
      <div class="revision-info-header">
        <el-tag type="success">逻辑修正</el-tag>
        <span class="revision-stats">
          原文 <strong>{{ unitSummaries[currentRevisionUnit]?.original_summary?.length || 0 }}</strong> 字 
          → 修正后 <strong>{{ unitSummaries[currentRevisionUnit]?.revised_summary?.length || 0 }}</strong> 字
        </span>
      </div>

      <!-- 视图切换 -->
      <div class="view-switch">
        <el-radio-group v-model="revisionViewMode" size="small">
          <el-radio-button value="diff">差异对比</el-radio-button>
          <el-radio-button value="side">左右对照</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 差异对比视图 -->
      <div v-if="revisionViewMode === 'diff'" class="diff-view">
        <div class="diff-legend">
          <span class="legend-item added"><span class="legend-color"></span>新增内容</span>
          <span class="legend-item removed"><span class="legend-color"></span>删除内容</span>
          <span class="legend-item unchanged"><span class="legend-color"></span>未修改</span>
        </div>
        <div class="diff-content" v-html="getRevisionDiffHtml(unitSummaries[currentRevisionUnit])"></div>
      </div>

      <!-- 左右对照视图 -->
      <div v-else class="compare-view">
        <div class="compare-panel">
          <div class="panel-header">
            <el-tag type="warning">原始内容</el-tag>
            <span class="panel-word-count">{{ unitSummaries[currentRevisionUnit]?.original_summary?.length || 0 }} 字</span>
          </div>
          <div class="panel-content">
            <el-input
              :model-value="unitSummaries[currentRevisionUnit]?.original_summary"
              type="textarea"
              :rows="15"
              readonly
            />
          </div>
        </div>
        
        <div class="compare-panel">
          <div class="panel-header">
            <el-tag type="success">修正后内容</el-tag>
            <span class="panel-word-count">{{ unitSummaries[currentRevisionUnit]?.revised_summary?.length || 0 }} 字</span>
          </div>
          <div class="panel-content">
            <el-input
              :model-value="unitSummaries[currentRevisionUnit]?.revised_summary"
              type="textarea"
              :rows="15"
              readonly
            />
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="showRevisionDetailDialog = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Setting, Lightning, CircleCheck, Rank } from '@element-plus/icons-vue'
import { CREATIVE_MODULES } from '@/config'
import { generateApi, revisionApi, globalOutlineQCApi, unitSummariesQCApi } from '@/api'
import { useApiKeyStore } from '@/stores'
import { API_BASE_URL } from '@/config'
import { useUserStore } from '@/stores/user'
import { applyDiffInstructions, validateDiffInstructions } from '@/utils/diffApplier'

// 导入子组件
import FormFieldsSection from './components/FormFieldsSection.vue'
import KnowledgeBaseSection from './components/KnowledgeBaseSection.vue'
import WorkflowProgress from './components/WorkflowProgress.vue'
import ResultViewer from './components/ResultViewer.vue'
import GlobalOutlineReviseDialog from './components/GlobalOutlineReviseDialog.vue'
import UnitSummariesReviseDialog from './components/UnitSummariesReviseDialog.vue'

// 导入composables
import { useGenerationForm } from './composables/useGenerationForm'
import { useStreamHandler } from './composables/useStreamHandler'
import { useWorkflow } from './composables/useWorkflow'
import { useGenerationRestore } from '@/composables/useGenerationRestore'

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
  optimizing,
  optimizeTarget,
  useTwoStageMode,
  combinedStyleTypes,
  seriesDurationHint,
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
  handleVideoModeChange,
  handleSeriesTypeChange,
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

// 质量管控配置
const enableAutoQC = ref(false)  // v2.3新增：是否启用自动质控修正（默认禁用，由用户主动控制）
const qualityControlMode = ref('standard')  // quick, standard, deep
const qualityDimensions = ref(['unit_structure', 'unit_character', 'unit_consistency', 'unit_timeline_space', 'unit_ooc'])

// 质控模式配置
const qualityControlModes = [
  {
    key: 'quick',
    label: '快速',
    icon: 'Lightning',
    description: '仅规则引擎检测，零Token消耗，秒级返回',
    timeEstimate: '< 1秒',
    type: 'success'
  },
  {
    key: 'standard',
    label: '标准',
    icon: 'CircleCheck',
    description: '规则引擎 + LLM深度分析，推荐日常使用',
    timeEstimate: '5-10秒',
    type: 'primary'
  },
  {
    key: 'deep',
    label: '深度',
    icon: 'Rank',
    description: '全量LLM分析，最高精度，适合重要章节',
    timeEstimate: '10-30秒',
    type: 'warning'
  }
]

// 单元概述质控维度配置
const unitQualityDimensions = [
  {
    key: 'unit_structure',
    label: '单元结构',
    icon: 'Grid',
    description: 'LLM深度检测单元长度、衔接流畅度、情节节奏'
  },
  {
    key: 'unit_character',
    label: '人物发展',
    icon: 'User',
    description: 'LLM深度检测人物状态变化、成长逻辑、关系一致性'
  },
  {
    key: 'unit_consistency',
    label: '大纲一致性',
    icon: 'Connection',
    description: 'LLM深度检测与全局大纲的偏离度、核心要素完整性'
  },
  {
    key: 'unit_timeline_space',
    label: '时间线空间',
    icon: 'Location',
    description: '检测人物位置逻辑、出场时间线、事件因果关系、状态连续性'
  },
  {
    key: 'unit_ooc',
    label: '人物OOC',
    icon: 'Warning',
    description: '检测人物是否违背人设（性格违背、动机矛盾、能力超纲）'
  }
]

// 当前选中的质控模式信息
const currentQualityMode = computed(() => {
  return qualityControlModes.find(m => m.key === qualityControlMode.value) || qualityControlModes[1]
})

/**
 * 质控模式切换处理
 */
function handleQualityModeChange(mode) {
  console.log('[GenerateForm] 质控模式切换:', mode)
  // quick模式不显示维度选择
  if (mode === 'quick') {
    qualityDimensions.value = []
  } else {
    qualityDimensions.value = ['unit_structure', 'unit_character', 'unit_consistency', 'unit_timeline_space', 'unit_ooc']
  }
}

/**
 * 自动质控开关变化处理
 */
function handleAutoQCChange(enabled) {
  console.log('[GenerateForm] 自动质控修正:', enabled ? '启用' : '禁用')
  if (!enabled) {
    ElMessage.info('已禁用自动质控修正，生成完成后可手动触发质控检测')
  }
}

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
const enableAutoRevise = ref(true)    // 是否启用自动修正（用户可选择）

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

// 知识库组件引用
const knowledgeBaseSectionRef = ref(null)

onMounted(async () => {
  await apiKeyStore.fetchApiKeys()
  restoreFormData()
  
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
})

onBeforeUnmount(() => {
  if (currentEventSource.value && currentEventSource.value.abort) {
    currentEventSource.value.abort()
    currentEventSource.value = null
  }
  generating.value = false
  globalOutlineGenerating.value = false
  unitSummariesGenerating.value = false
  logicChecking.value = false
})

// 监听表单变化自动保存
watch(form, () => {
  saveFormData()
}, { deep: true })

// 监听模块类型变化时恢复对应模块的表单数据
watch(type, () => {
  restoreFormData()
})

// 处理生成
async function handleGenerate() {
  // 如果是小说或剧本大纲，使用两阶段生成
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
      'script': generateApi.script,
      'novel': generateApi.novel,
      'print-ad': generateApi.printAd,
      'tvc': generateApi.tvc,
      'original-ip': generateApi.originalIp
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
    } else if (type.value === 'script') {
      submitData = {
        title: form.value.title,
        series_type: form.value.series_type || '网剧',
        theme: form.value.genre || '都市',
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
        mode: form.value.tvc_mode || 'real',
        generate_ai_prompt: form.value.generate_ai_prompt_tvc ? '是' : '否',
        ai_platforms: form.value.ai_platforms_tvc || '可灵',
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

// ==================== 两阶段大纲生成方法 ====================

// 开始两阶段生成（第一阶段：全局大纲）
async function handleTwoStageGenerate() {
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
  
  workflowSteps.value = [
    { step: 'model', status: 'running', message: '正在加载AI模型...', icon: 'Cpu' }
  ]
  workflowComplete.value = false
  
  outlineStage.value = 1
  globalOutlineGenerating.value = true
  globalOutlineContent.value = ''
  showResult.value = true
  generatedContent.value = ''
  
  try {
    const inputParams = buildOutlineInputParams()
    
    setTimeout(() => {
      if (globalOutlineGenerating.value) {
        const modelIndex = workflowSteps.value.findIndex(s => s.step === 'model')
        if (modelIndex >= 0) {
          workflowSteps.value[modelIndex] = { step: 'model', status: 'done', message: '已加载模型', icon: 'Cpu' }
        }
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
    
    const result = await generateApi.generateGlobalOutlineStream(
      {
        content_type: type.value,
        input_params: inputParams,
        provider: null,
        model: null,
        temperature: 0.7,
        enable_auto_qc: enableAutoQC.value  // v2.3新增：传递自动质控开关
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
      (newContent, message, eventData) => {
        // 处理replace_content事件（知识库修正后或质控修正后）
        globalOutlineContent.value = newContent
        generatedContent.value = newContent
        
        // v2.3新增：处理质控修正相关字段
        if (eventData && eventData.qc_applied) {
          qcApplied.value = true
          issuesFixed.value = eventData.issues_fixed || 0
          if (eventData.qc_report) {
            qcReportData.value = eventData.qc_report
          }
          
          // v2.4修复：自动质控修正后显示对比对话框
          if (eventData.original_content && eventData.revised_content) {
            console.log('[自动质控修正] 准备显示对比对话框...')
            
            globalOutlineReviseData.value = {
              originalContent: eventData.original_content,
              revisedContent: eventData.revised_content,
              changes: eventData.qc_report?.issues || [],
              issueId: 'auto_qc_generation',
              issueDescription: `生成时自动质控修正 ${eventData.issues_fixed || 0} 个问题`,
              originalLength: eventData.original_length || eventData.original_content.length,
              revisedLength: eventData.revised_length || eventData.revised_content.length
            }
            
            showGlobalOutlineReviseDialog.value = true
            console.log('[自动质控修正] 对比对话框已显示')
          }
          
          ElMessage.success(`已完成质量检测与修正，修正了${issuesFixed.value}个问题`)
        } else if (message) {
          ElMessage.success(message)
        }
      },
      // v2.3新增：处理qc_report事件（无修正时）
      (eventData) => {
        if (eventData && eventData.qc_report) {
          qcReportData.value = eventData.qc_report
          qcApplied.value = eventData.qc_applied || false
          issuesFixed.value = eventData.issues_fixed || 0
        }
      }
    )
    
    if (result && !result.cancelled) {
      const generateIndex = workflowSteps.value.findIndex(s => s.step === 'generate')
      if (generateIndex >= 0) {
        workflowSteps.value[generateIndex] = { step: 'generate', status: 'done', message: '全局大纲生成完成', icon: 'MagicStick' }
      }
      workflowComplete.value = true
      
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

// 构建大纲输入参数
function buildOutlineInputParams() {
  if (type.value === 'novel') {
    const lengthMap = { 'short': '短篇', 'medium': '中篇', 'long': '长篇' }
    return {
      title: form.value.title || '',
      length: lengthMap[form.value.length] || '中篇',
      target_platform: form.value.target_platform || '起点',
      synopsis: form.value.description,
      chapter_count: form.value.chapter_count || '50',
      custom_outline: form.value.custom_outline || '',
      // 文风参数
      style_ids: styleData.value.styleIds || [],
      style_names: styleData.value.styleNames || [],
      style_intensity: styleData.value.intensity || 0.7,
      style_guide: styleData.value.styleGuide || null,
      // 标题风格参数
      title_style: titleStyleData.value.styleId || '',
      title_style_name: titleStyleData.value.styleName || ''
    }
  } else if (type.value === 'script') {
    return {
      title: form.value.title || '',
      series_type: form.value.series_type || '网剧',
      theme: form.value.genre || '都市',
      audience: form.value.target_audience || '年轻观众',
      platform: form.value.platform || '爱奇艺',
      reference_works: form.value.reference_works || '无',
      synopsis: form.value.description,
      episode_count: form.value.episode_count || '24',
      custom_outline: form.value.custom_outline || '',
      episode_duration_range: `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟`,
      format_standard: form.value.format_standard || '标准格式',
      dialogue_narration_ratio: form.value.dialogue_narration_ratio || '均衡',
      script_mode: form.value.script_mode || 'real'
    }
  }
  return {}
}

// 开始第二阶段：生成单元概述
async function handleGenerateUnitSummaries() {
  if (!globalOutlineContent.value) {
    ElMessage.warning('请先生成全局大纲')
    return
  }
  
  // 智能获取章节数：优先使用表单值，其次从全局大纲中解析
  const formChapterCount = type.value === 'novel' 
    ? parseInt(form.value.chapter_count) || null
    : parseInt(form.value.episode_count) || null
  
  const outlineChapterCount = formChapterCount ? null : parseChapterCountFromOutline(globalOutlineContent.value)
  
  // 默认值：表单未填写且大纲未解析到时使用默认值
  const unitCount = formChapterCount || outlineChapterCount || (type.value === 'novel' ? 50 : 24)
  
  console.log(`[GenerateForm] 章节数计算:`)
  console.log(`  - 表单设置: ${formChapterCount || '未填写'}`)
  console.log(`  - 从大纲解析: ${outlineChapterCount || '未找到'}`)
  console.log(`  - 最终使用: ${unitCount}`)
  
  currentSessionId.value = `unit_summaries_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  
  // 检测是否为续生成模式（从已有内容中检测）
  const existingContent = generatedContent.value || ''
  const existingParsed = parseUnitSummariesFromContent(existingContent)
  const existingUnitCount = Object.keys(existingParsed).length
  const isResumeMode = existingUnitCount > 0 && existingUnitCount < unitCount

  outlineStage.value = 3
  unitSummariesGenerating.value = true
  // 续生成模式下不清空已有数据，保留前文
  if (!isResumeMode) {
    unitSummaries.value = {}
  }
  
  try {
    // 构建请求参数
    const requestData = {
      content_type: type.value,
      global_outline: globalOutlineContent.value,
      unit_count: unitCount,
      series_type: type.value === 'script' ? form.value.series_type : null,
      episode_duration_range: type.value === 'script' 
        ? `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟` 
        : null,
      provider: null,
      model: null,
      temperature: 0.7,
      enable_quality_control: qualityControlMode.value !== 'quick',  // quick模式不启用
      quality_control_mode: qualityControlMode.value,  // 传递质控模式
      quality_dimensions: qualityDimensions.value,  // 传递质控维度
      // 标题风格参数（新增）
      title_style: titleStyleData.value.styleId || null,
      title_style_name: titleStyleData.value.styleName || null
    }
    
    // 续生成检测（复用上面的变量）
    console.log(`[GenerateForm] 续生成检测:`)
    console.log(`  - existingContent长度: ${existingContent.length}`)
    console.log(`  - existingParsed章节数: ${existingUnitCount}`)
    console.log(`  - existingParsed keys: ${Object.keys(existingParsed).slice(0, 10).join(', ')}...`)
    console.log(`  - unitCount: ${unitCount}`)
    
    if (isResumeMode) {
      // 续生成模式
      console.log(`[GenerateForm] ✅ 检测到续生成模式: 已有${existingUnitCount}章，目标${unitCount}章`)
      requestData.existing_content = existingContent
      requestData.existing_parsed = existingParsed
      requestData.start_from_unit = existingUnitCount + 1
      
      console.log(`[GenerateForm] 续生成参数:`)
      console.log(`  - start_from_unit: ${requestData.start_from_unit}`)
      console.log(`  - unit_count: ${requestData.unit_count}`)
      console.log(`  - 将生成: 第${requestData.start_from_unit}-${requestData.unit_count}章`)
      
      ElMessage.info(`从第${requestData.start_from_unit}章继续生成至第${unitCount}章`)
    } else {
      console.log(`[GenerateForm] ❌ 未检测到续生成模式 (existingUnitCount=${existingUnitCount}, unitCount=${unitCount})`)
    }
    
    const result = await generateApi.generateUnitSummariesStream(
      requestData,
      (chunk, fullContent) => {
        generatedContent.value = fullContent
      },
      (abortController) => {
        currentEventSource.value = abortController
      },
      currentSessionId.value,
      (event) => {
        handleWorkflowEvent(event)
      },
      (newContent, message) => {
        // 处理replace_content事件（质量修正后的内容替换）
        generatedContent.value = newContent
        if (message) {
          ElMessage.success(message)
        }
      }
    )
    
    if (result && !result.cancelled) {
      unitSummaries.value = parseUnitSummariesFromContent(result.content)
      // 质量管控已在流式生成过程中自动执行，无需再次调用
      outlineStage.value = 4
      ElMessage.success('单元概述生成完成')
    } else if (result && result.cancelled) {
      ElMessage.info('生成已取消')
      if (result.content) {
        unitSummaries.value = parseUnitSummariesFromContent(result.content)
        outlineStage.value = 4
      } else {
        outlineStage.value = 2
      }
    }
  } catch (error) {
    console.error('单元概述生成失败:', error)
    ElMessage.error('单元概述生成失败：' + (error.message || '未知错误'))
    outlineStage.value = 2
  } finally {
    unitSummariesGenerating.value = false
    currentSessionId.value = null
  }
}

// 从全局大纲中解析章节数
function parseChapterCountFromOutline(outlineContent) {
  if (!outlineContent) return null
  
  // 尝试多种模式匹配章节数
  const patterns = [
    /共(\d+)章/,           // "共100章"
    /总计(\d+)章/,         // "总计100章"
    /(\d+)章.*全书/,       // "100章全书"
    /全书.*?(\d+)章/,      // "全书共100章"
    /第1章.*?第(\d+)章/,   // "第1章...第100章"（最后的章节号）
    /章节总数[：:]\s*(\d+)/, // "章节总数：100"
    /总章节数[：:]\s*(\d+)/, // "总章节数：100"
  ]
  
  for (const pattern of patterns) {
    const match = outlineContent.match(pattern)
    if (match) {
      const count = parseInt(match[1])
      if (count > 0 && count <= 1000) {  // 合理范围检查
        console.log(`[ParseOutline] 从大纲中解析到章节数: ${count} (模式: ${pattern.source})`)
        return count
      }
    }
  }
  
  // 如果没有找到明确标识，尝试找最大的章节号
  const chapterPattern = /第(\d+)章/g
  let maxChapter = 0
  let match
  while ((match = chapterPattern.exec(outlineContent)) !== null) {
    const chapterNum = parseInt(match[1])
    if (chapterNum > maxChapter) {
      maxChapter = chapterNum
    }
  }
  
  if (maxChapter > 0) {
    console.log(`[ParseOutline] 从大纲中找到最大章节号: ${maxChapter}`)
    return maxChapter
  }
  
  console.log(`[ParseOutline] 未能从大纲中解析到章节数`)
  return null
}

// 从内容中解析单元概述
function parseUnitSummariesFromContent(content) {
  const result = {}
  const isMovie = content.includes('场') && !content.includes('集')
  
  const pattern = isMovie 
    ? /\*\*第(\d+)场[：:]\s*(.+?)(?:\n|$)/g
    : /###\s*第(\d+)(?:章|集)[：:]\s*(.+?)(?:\n|$)/g
  
  let match
  while ((match = pattern.exec(content)) !== null) {
    const unitNum = parseInt(match[1])
    const title = match[2].trim()
    
    // 提取梳概
    const summaryPattern = isMovie
      ? new RegExp(`\\*\\*本场梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
      : new RegExp(`\\*\\*本(?:章|集)梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
    
    const summaryMatch = content.slice(match.index, match.index + 500).match(summaryPattern)
    const summary = summaryMatch ? summaryMatch[1].trim() : ''
    
    // v2.1: 提取完整单元内容（从当前单元到下一单元之间）
    const nextUnitPattern = isMovie
      ? new RegExp(`\\*\\*第${unitNum + 1}场`)
      : new RegExp(`###\\s*第${unitNum + 1}(?:章|集)`)
    const nextMatch = content.slice(match.index).search(nextUnitPattern)
    const fullContent = nextMatch > 0 
      ? content.slice(match.index, match.index + nextMatch).trim()
      : content.slice(match.index).trim()
    
    result[unitNum.toString()] = {
      unit_id: `unit-${unitNum}-${Date.now().toString(36)}`,
      unit_number: unitNum,
      title: title,
      summary: summary,
      full_content: fullContent,
      status: 'completed'
    }
  }
  
  return result
}

// 执行逻辑检测
async function performLogicCheck() {
  if (!globalOutlineContent.value || Object.keys(unitSummaries.value).length === 0) {
    return
  }
  
  logicChecking.value = true
  logicCheckResult.value = null
  
  try {
    const response = await generateApi.checkOutlineLogic({
      content_type: type.value,
      global_outline: globalOutlineContent.value,
      unit_summaries: unitSummaries.value,
      provider: null,
      temperature: 0.7
    })
    
    if (response.success && response.data) {
      logicCheckResult.value = response.data
      
      if (response.data.has_issues) {
        if (response.data.revised_units && Object.keys(response.data.revised_units).length > 0) {
          const originalUnits = response.data.original_units || {}
          const revisedUnits = response.data.revised_units
          
          for (const [unitNum, revisedContent] of Object.entries(revisedUnits)) {
            if (unitSummaries.value[unitNum]) {
              unitSummaries.value[unitNum].original_summary = originalUnits[unitNum]?.summary || unitSummaries.value[unitNum].summary
              unitSummaries.value[unitNum].summary = revisedContent
              unitSummaries.value[unitNum].logic_fixed = true
              unitSummaries.value[unitNum].revised_summary = revisedContent
            }
          }
          ElMessage.success(`逻辑检测完成，已修正 ${Object.keys(revisedUnits).length} 个单元的问题`)
        } else {
          ElMessage.warning(`逻辑检测发现 ${response.data.issues?.length || 0} 个潜在问题，但未自动修正`)
        }
      } else {
        ElMessage.success('逻辑检测通过，未发现严重问题')
      }
    }
  } catch (error) {
    console.error('逻辑检测失败:', error)
    
    // 区分超时和其他错误
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      ElMessage.warning('逻辑检测超时，跳过此步骤。您可以稍后手动执行逻辑检测。')
    } else {
      ElMessage.warning('逻辑检测失败，跳过此步骤。您可以稍后手动执行逻辑检测。')
    }
    
    // 不阻断流程，继续后续步骤
    logicCheckResult.value = {
      has_issues: false,
      issues: [],
      error: error.message
    }
  } finally {
    logicChecking.value = false
  }
}

// 取消单元概述生成
async function cancelUnitSummariesGeneration() {
  if (!currentSessionId.value) {
    if (currentEventSource.value && currentEventSource.value.abort) {
      currentEventSource.value.abort()
    }
    return
  }
  
  try {
    await generateApi.cancelGeneration(currentSessionId.value)
    if (currentEventSource.value && currentEventSource.value.abort) {
      currentEventSource.value.abort()
    }
    ElMessage.info('正在取消生成...')
  } catch (error) {
    console.error('取消生成失败:', error)
    if (currentEventSource.value && currentEventSource.value.abort) {
      currentEventSource.value.abort()
    }
  }
}

// 断点续生成（核心方法）
async function handleResumeUnitSummaries() {
  if (!unitSummaries.value || Object.keys(unitSummaries.value).length === 0) {
    ElMessage.warning('没有已生成的单元概述，无法续生成')
    return
  }

  if (!globalOutlineContent.value) {
    ElMessage.warning('缺少全局大纲，无法续生成')
    return
  }

  const existingCount = Object.keys(unitSummaries.value).length
  const unitCount = expectedUnitCount.value
  const startFrom = existingCount + 1
  const remainingCount = unitCount - existingCount

  if (existingCount >= unitCount) {
    ElMessage.info('所有章节已生成完成，无需续生成')
    return
  }

  if (unitSummariesGenerating.value) {
    ElMessage.warning('正在生成中，请稍候...')
    return
  }

  // 确认对话框
  try {
    await ElMessageBox.confirm(
      `当前已生成 ${existingCount} 章，目标 ${unitCount} 章。\n将从第 ${startFrom} 章继续生成剩余 ${remainingCount} 章。\n\n已有内容不会被清除，续生成内容将与前文自然衔接。`,
      '断点续生成',
      {
        confirmButtonText: '开始续生成',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
  } catch {
    return  // 用户取消
  }

  unitSummariesGenerating.value = true
  currentSessionId.value = `unit_summaries_resume_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  outlineStage.value = 3
  // 注意：不清空 unitSummaries，保留已有数据

  try {
    // 构建续生成请求参数
    const requestData = {
      content_type: type.value,
      global_outline: globalOutlineContent.value,
      unit_count: unitCount,  // 传递总章节数
      series_type: type.value === 'script' ? form.value.series_type : null,
      episode_duration_range: type.value === 'script'
        ? `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟`
        : null,
      provider: null,
      model: null,
      temperature: 0.7,
      enable_quality_control: qualityControlMode.value !== 'quick',
      // 续生成关键参数
      existing_content: generatedContent.value || '',
      existing_parsed: unitSummaries.value,
      start_from_unit: startFrom,
      // 标题风格参数
      title_style: titleStyleData.value.styleId || null,
      title_style_name: titleStyleData.value.styleName || null
    }

    console.log(`[handleResumeUnitSummaries] 续生成参数:`)
    console.log(`  - 已有: ${existingCount}章`)
    console.log(`  - 目标: ${unitCount}章`)
    console.log(`  - 起始: 第${startFrom}章`)
    console.log(`  - 剩余: ${remainingCount}章`)

    const result = await generateApi.generateUnitSummariesStream(
      requestData,
      (chunk, fullContent) => {
        // 续生成时，内容追加上显示
        generatedContent.value = fullContent
      },
      (abortController) => {
        currentEventSource.value = abortController
      },
      currentSessionId.value,
      (event) => {
        handleWorkflowEvent(event)
      },
      (newContent, message) => {
        // replace_content事件（质量修正后替换内容）
        generatedContent.value = newContent
        if (message) {
          ElMessage.success(message)
        }
      }
    )

    if (result && !result.cancelled) {
      // 续生成完成后，重新解析全部内容并合并
      const allParsed = parseUnitSummariesFromContent(result.content)
      // 合并：已有数据保留，新数据覆盖（以解析结果为准）
      const mergedSummaries = { ...unitSummaries.value }
      for (const [num, unit] of Object.entries(allParsed)) {
        if (!mergedSummaries[num]) {
          // 新生成的章节
          mergedSummaries[num] = unit
        } else if (allParsed[num].full_content && allParsed[num].full_content.length > (mergedSummaries[num].full_content?.length || 0)) {
          // 新解析内容更丰富，用新数据覆盖
          mergedSummaries[num] = unit
        }
      }
      unitSummaries.value = mergedSummaries
      // 重建完整内容文本，确保下载功能能获取全部章节
      const allChapterTexts = Object.keys(mergedSummaries)
        .sort((a, b) => parseInt(a) - parseInt(b))
        .map(num => mergedSummaries[num].full_content || mergedSummaries[num].summary)
        .filter(Boolean)
      generatedContent.value = allChapterTexts.join('\n\n')
      outlineStage.value = 4

      const newCount = Object.keys(mergedSummaries).length
      if (newCount >= unitCount) {
        ElMessage.success(`续生成完成！全部 ${unitCount} 章已生成`)
      } else {
        ElMessage.warning(`续生成完成，当前共 ${newCount}/${unitCount} 章。如需继续，请再次点击续生成。`)
      }
    } else if (result && result.cancelled) {
      ElMessage.info('续生成已取消')
      if (result.content) {
        // 取消时也保留已解析的内容
        const partialParsed = parseUnitSummariesFromContent(result.content)
        const mergedSummaries = { ...unitSummaries.value }
        for (const [num, unit] of Object.entries(partialParsed)) {
          if (!mergedSummaries[num]) {
            mergedSummaries[num] = unit
          }
        }
        unitSummaries.value = mergedSummaries
        // 重建完整内容文本
        const allChapterTexts = Object.keys(mergedSummaries)
          .sort((a, b) => parseInt(a) - parseInt(b))
          .map(num => mergedSummaries[num].full_content || mergedSummaries[num].summary)
          .filter(Boolean)
        generatedContent.value = allChapterTexts.join('\n\n')
        outlineStage.value = 4
      }
    }
  } catch (error) {
    console.error('续生成失败:', error)
    ElMessage.error('续生成失败：' + (error.message || '未知错误'))
    // 续生成失败时保留已有的单元概述，不回退阶段
    if (Object.keys(unitSummaries.value).length > 0) {
      outlineStage.value = 4
    } else {
      outlineStage.value = 2
    }
  } finally {
    unitSummariesGenerating.value = false
    currentSessionId.value = null
  }
}

// 接续生成(兼容旧版入口，转发到 handleResumeUnitSummaries)
async function handleContinueGeneration() {
  // 旧版依赖 truncationInfo，新版改为直接基于 unitSummaries 数量判断
  await handleResumeUnitSummaries()
}

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

// 打开导入对话框
function openImportDialog() {
  importType.value = 'global'
  importContent.value = ''
  importingOutline.value = false
  importOutlineProgress.value = 0
  showImportDialog.value = true
}

// 确认导入内容
function confirmImport() {
  if (!importContent.value.trim()) {
    ElMessage.warning('请上传要导入的大纲文件')
    return
  }
  
  // v2.3新增：标记为导入大纲
  importedOutline.value = true
  qcApplied.value = false  // 重置质控状态
  qcReportData.value = null
  issuesFixed.value = 0
  
  if (importType.value === 'global') {
    globalOutlineContent.value = importContent.value.trim()
    generatedContent.value = importContent.value.trim()
    outlineStage.value = 2
    showResult.value = true
    ElMessage.success('全局大纲已导入，您可以编辑后继续生成单元概述')
  } else {
    try {
      const parsed = parseUnitSummariesFromContent(importContent.value)
      if (Object.keys(parsed).length > 0) {
        unitSummaries.value = parsed
        const globalOutlineMatch = importContent.value.match(/^([\s\S]*?)(?=###\s*第\d+章|###\s*第\d+集|\*\*第\d+集)/)
        if (globalOutlineMatch) {
          globalOutlineContent.value = globalOutlineMatch[1].trim()
        } else {
          globalOutlineContent.value = importContent.value.split('###')[0].trim()
        }
        generatedContent.value = importContent.value
        outlineStage.value = 4
        showResult.value = true
        ElMessage.success('完整大纲已导入，您可以编辑后下载')
      } else {
        globalOutlineContent.value = importContent.value.trim()
        generatedContent.value = importContent.value.trim()
        outlineStage.value = 2
        showResult.value = true
        ElMessage.warning('无法解析单元概述，已作为全局大纲导入')
      }
    } catch (error) {
      console.error('解析导入内容失败:', error)
      globalOutlineContent.value = importContent.value.trim()
      generatedContent.value = importContent.value.trim()
      outlineStage.value = 2
      showResult.value = true
      ElMessage.warning('导入内容已作为全局大纲处理')
    }
  }
  
  showImportDialog.value = false
}

// 导入文件上传前验证
function beforeOutlineImportUpload(file) {
  const isLt100M = file.size / 1024 / 1024 < 100
  if (!isLt100M) {
    ElMessage.error('文件大小不能超过 100MB!')
    return false
  }
  
  const allowedTypes = ['.md', '.txt', '.docx', '.doc']
  const fileName = file.name.toLowerCase()
  const isValidType = allowedTypes.some(ext => fileName.endsWith(ext))
  
  if (!isValidType) {
    ElMessage.error('只支持 .md、.txt、.docx、.doc 格式的文件!')
    return false
  }
  
  importingOutline.value = true
  importOutlineProgress.value = 0
  return true
}

// 导入文件上传成功
function handleOutlineImportUploadSuccess(response, file) {
  importingOutline.value = false
  importOutlineProgress.value = 100
  
  try {
    if (response.code === 200 && response.data) {
      const content = response.data.content || response.data.outline_content || ''
      
      if (!content.trim()) {
        ElMessage.warning('上传的文件内容为空')
        return
      }
      
      importContent.value = content
      
      // 自动确认导入
      confirmImport()
      
      ElMessage.success('文件上传成功')
    } else {
      ElMessage.error(response.message || '文件上传失败')
    }
  } catch (error) {
    console.error('处理上传响应失败:', error)
    ElMessage.error('文件上传失败')
  }
}

// 导入文件上传失败
function handleOutlineImportUploadError(error, file) {
  importingOutline.value = false
  importOutlineProgress.value = 0
  console.error('文件上传失败:', error)
  ElMessage.error('文件上传失败，请重试')
}

// 导入文件上传进度
function handleOutlineImportProgress(event, file) {
  importOutlineProgress.value = Math.round(event.percent)
}

// ==================== 导入单元概述相关函数 ====================

// 打开导入单元概述对话框
function openImportUnitSummariesDialog() {
  importingUnitSummaries.value = false
  importUnitSummariesProgress.value = 0
  showImportUnitSummariesDialog.value = true
}

// 上传前验证
function beforeUnitSummariesImportUpload(file) {
  const isLt100M = file.size / 1024 / 1024 < 100
  if (!isLt100M) {
    ElMessage.error('文件大小不能超过 100MB!')
    return false
  }
  
  const allowedTypes = ['.md', '.txt', '.docx', '.doc']
  const fileName = file.name.toLowerCase()
  const isValidType = allowedTypes.some(ext => fileName.endsWith(ext))
  
  if (!isValidType) {
    ElMessage.error('只支持 .md、.txt、.docx、.doc 格式的文件!')
    return false
  }
  
  importingUnitSummaries.value = true
  importUnitSummariesProgress.value = 0
  return true
}

// 上传成功处理
function handleUnitSummariesImportUploadSuccess(response, file) {
  importingUnitSummaries.value = false
  importUnitSummariesProgress.value = 100
  
  try {
    if (response.code === 200 && response.data) {
      const content = response.data.content || ''
      
      if (!content.trim()) {
        ElMessage.warning('上传的文件内容为空')
        return
      }
      
      // 解析单元概述内容
      const parsed = parseUnitSummariesFromContent(content)
      
      if (Object.keys(parsed).length > 0) {
        // 成功解析
        unitSummaries.value = parsed
        
        // 修复：从导入内容中提取全局大纲
        // 尝试匹配单元概述之前的内容作为全局大纲
        const globalOutlineMatch = content.match(/^([\s\S]*?)(?=###\s*第\d+章[:：]|###\s*第\d+集[:：]|\*\*第\d+集\*\*[:：])/)
        if (globalOutlineMatch && globalOutlineMatch[1].trim()) {
          globalOutlineContent.value = globalOutlineMatch[1].trim()
          console.log('[单元概述导入] 已提取全局大纲，长度:', globalOutlineContent.value.length)
        } else {
          // 如果无法提取，尝试从文件内容的前部分作为全局大纲
          const firstPart = content.split(/###\s*第\d+章[:：]|###\s*第\d+集[:：]|\*\*第\d+集\*\*[:：]/)[0]
          if (firstPart && firstPart.trim().length > 50) {
            globalOutlineContent.value = firstPart.trim()
            console.log('[单元概述导入] 从文件前部分提取全局大纲，长度:', globalOutlineContent.value.length)
          } else {
            globalOutlineContent.value = ''
            console.warn('[单元概述导入] 未找到全局大纲内容，质控检测可能不准确')
          }
        }
        
        generatedContent.value = content
        outlineStage.value = 4  // 跳转到单元概述阶段
        showResult.value = true
        importedUnitSummaries.value = true  // 标记为导入的单元概述
        
        // 重置质控状态
        qcApplied.value = false
        qcReportData.value = null
        issuesFixed.value = 0
        
        const outlineInfo = globalOutlineContent.value 
          ? `（已提取全局大纲 ${globalOutlineContent.value.length} 字）` 
          : '（⚠️ 未检测到全局大纲，建议先导入全局大纲以保证质控准确性）'
        
        ElMessage.success(`单元概述导入成功，共解析 ${Object.keys(parsed).length} 章 ${outlineInfo}`)
        
        // 关闭对话框
        showImportUnitSummariesDialog.value = false
      } else {
        ElMessage.error('无法解析单元概述内容，请检查文件格式')
      }
    } else {
      ElMessage.error(response.message || '文件上传失败')
    }
  } catch (error) {
    console.error('处理上传响应失败:', error)
    ElMessage.error('文件上传失败')
  }
}

// 上传失败处理
function handleUnitSummariesImportUploadError(error, file) {
  importingUnitSummaries.value = false
  importUnitSummariesProgress.value = 0
  console.error('文件上传失败:', error)
  ElMessage.error('文件上传失败，请重试')
}

// 上传进度
function handleUnitSummariesImportProgress(event, file) {
  importUnitSummariesProgress.value = Math.round(event.percent)
}

// 打开从指定单元开始的对话框
function openStartUnitDialog() {
  // 智能获取章节数：优先使用表单值，其次从全局大纲中解析
  const formChapterCount = type.value === 'novel'
    ? parseInt(form.value.chapter_count) || null
    : parseInt(form.value.episode_count) || null
  
  const outlineChapterCount = formChapterCount ? null : parseChapterCountFromOutline(globalOutlineContent.value)
  
  // 默认值：表单未填写且大纲未解析到时使用默认值
  const unitCount = formChapterCount || outlineChapterCount || (type.value === 'novel' ? 50 : 24)
  
  startFromUnit.value = Math.min(startFromUnit.value, unitCount)
  showStartUnitDialog.value = true
}

// 从指定单元开始生成
async function handleGenerateFromUnit() {
  if (!globalOutlineContent.value) {
    ElMessage.warning('请先导入或生成全局大纲')
    return
  }
  
  // 智能获取章节数：优先使用表单值，其次从全局大纲中解析
  const formChapterCount = type.value === 'novel'
    ? parseInt(form.value.chapter_count) || null
    : parseInt(form.value.episode_count) || null
  
  const outlineChapterCount = formChapterCount ? null : parseChapterCountFromOutline(globalOutlineContent.value)
  
  // 默认值：表单未填写且大纲未解析到时使用默认值
  const unitCount = formChapterCount || outlineChapterCount || (type.value === 'novel' ? 50 : 24)
  
  console.log(`[GenerateForm.handleGenerateFromUnit] 章节数: 表单=${formChapterCount || '未填写'}, 大纲=${outlineChapterCount || '未找到'}, 最终=${unitCount}`)
  
  if (startFromUnit.value < 1 || startFromUnit.value > unitCount) {
    ElMessage.warning(`请输入有效的单元编号（1-${unitCount}）`)
    return
  }
  
  showStartUnitDialog.value = false
  outlineStage.value = 3
  unitSummariesGenerating.value = true
  
  try {
    let existingContext = ''
    if (Object.keys(unitSummaries.value).length > 0) {
      existingContext = '\n\n【已生成的单元概述】\n'
      for (const [num, unit] of Object.entries(unitSummaries.value)) {
        if (parseInt(num) < startFromUnit.value) {
          existingContext += `单元${num}: ${unit.title}\n${unit.summary}\n\n`
        }
      }
    }
    
    const modifiedOutline = globalOutlineContent.value + existingContext +
      `\n\n【生成要求】从第${startFromUnit.value}单元开始生成后续单元概述。`
    
    const result = await generateApi.generateUnitSummariesStream(
      {
        content_type: type.value,
        global_outline: modifiedOutline,
        unit_count: unitCount,  // 传递总章节数，后端会计算需要生成的数量
        series_type: type.value === 'script' ? form.value.series_type : null,
        episode_duration_range: type.value === 'script'
          ? `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟`
          : null,
        script_mode: type.value === 'script' ? (form.value.script_mode || 'real') : null,
        provider: null,
        model: null,
        temperature: 0.7,
        enable_quality_control: qualityControlMode.value !== 'quick',  // quick模式不启用
        quality_control_mode: qualityControlMode.value,  // 传递质控模式
        quality_dimensions: qualityDimensions.value,  // 传递质控维度
        // 续生成参数
        existing_content: generatedContent.value || '',
        existing_parsed: unitSummaries.value,
        start_from_unit: startFromUnit.value
      },
      (chunk, fullContent) => {
        generatedContent.value = fullContent
      },
      (abortController) => {
        currentEventSource.value = abortController
      },
      null,
      (event) => {
        handleWorkflowEvent(event)
      },
      (newContent, message) => {
        generatedContent.value = newContent
        ElMessage.success(message || '内容已更新')
      }
    )
    
    if (result && !result.cancelled) {
      const newUnits = parseUnitSummariesFromContent(result.content)
      for (const [num, unit] of Object.entries(newUnits)) {
        const actualNum = parseInt(num) + startFromUnit.value - 1
        unitSummaries.value[actualNum.toString()] = {
          ...unit,
          unit_number: actualNum
        }
      }
      outlineStage.value = 4
      ElMessage.success(`从第${startFromUnit.value}单元开始的生成已完成`)
    }
  } catch (error) {
    console.error('单元概述生成失败:', error)
    ElMessage.error('单元概述生成失败：' + (error.message || '未知错误'))
    outlineStage.value = 2
  } finally {
    unitSummariesGenerating.value = false
  }
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

// ==================== 差异对比函数 ====================

function escapeHtml(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/ /g, '&nbsp;')
}

function findLCS(arr1, arr2) {
  const m = arr1.length, n = arr2.length
  const dp = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0))
  
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (arr1[i - 1] === arr2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }
  
  const lcs = []
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (arr1[i - 1] === arr2[j - 1]) {
      lcs.unshift(arr1[i - 1])
      i--
      j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }
  
  return lcs
}

function computeDiffWithLCS(oldParagraphs, newParagraphs) {
  const lcs = findLCS(oldParagraphs, newParagraphs)
  
  let html = ''
  let oldIdx = 0, newIdx = 0, lcsIdx = 0
  
  while (oldIdx < oldParagraphs.length || newIdx < newParagraphs.length) {
    if (lcsIdx < lcs.length && oldIdx < oldParagraphs.length && 
        oldParagraphs[oldIdx] === lcs[lcsIdx] &&
        newIdx < newParagraphs.length && newParagraphs[newIdx] === lcs[lcsIdx]) {
      html += `<div class="diff-paragraph unchanged">${escapeHtml(oldParagraphs[oldIdx])}</div>`
      oldIdx++
      newIdx++
      lcsIdx++
    } else if (newIdx < newParagraphs.length &&
               (lcsIdx >= lcs.length || newParagraphs[newIdx] !== lcs[lcsIdx])) {
      if (oldIdx < oldParagraphs.length &&
          (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
        html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
        html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
        oldIdx++
        newIdx++
      } else {
        html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
        newIdx++
      }
    } else if (oldIdx < oldParagraphs.length &&
               (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
      html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
      oldIdx++
    }
  }
  
  return html
}

function computeDiffHtml(oldText, newText) {
  if (!oldText && !newText) return ''
  if (!oldText) return `<div class="diff-paragraph added">${escapeHtml(newText)}</div>`
  if (!newText) return `<div class="diff-paragraph removed">${escapeHtml(oldText)}</div>`
  
  const oldParagraphs = oldText.split(/\n+/).filter(p => p.trim())
  const newParagraphs = newText.split(/\n+/).filter(p => p.trim())
  
  if (oldParagraphs.length <= 50 && newParagraphs.length <= 50) {
    return computeDiffWithLCS(oldParagraphs, newParagraphs)
  } else {
    const newSet = new Set(newParagraphs)
    let html = ''
    for (const para of oldParagraphs) {
      if (newSet.has(para)) {
        html += `<div class="diff-paragraph unchanged">${escapeHtml(para)}</div>`
      } else {
        html += `<div class="diff-paragraph removed">${escapeHtml(para)}</div>`
      }
    }
    const oldSet = new Set(oldParagraphs)
    for (const para of newParagraphs) {
      if (!oldSet.has(para)) {
        html += `<div class="diff-paragraph added">${escapeHtml(para)}</div>`
      }
    }
    return html
  }
}

function getRevisionDiffHtml(unit) {
  if (!unit?.original_summary || !unit?.revised_summary) return ''
  return computeDiffHtml(unit.original_summary, unit.revised_summary)
}

// ==================== 修订模式相关函数 ====================

/**
 * 进入修订模式
 */
function startRevision() {
  // 检查知识库修正是否正在进行中
  if (knowledgeRevising.value) {
    ElMessage.warning('知识库修正进行中，请稍候...')
    return
  }
  
  isRevisionMode.value = true
  currentRevisionRound.value = 0
  revisionMessages.value = []
  revisionHistory.value = []
  
  // 两阶段大纲生成：修订全局大纲
  if (useTwoStageMode.value) {
    // 使用全局大纲内容
    revisionContent.value = globalOutlineContent.value || ''
    generationId.value = null  // 两阶段模式没有generation_id
    console.log('[Revision] Starting revision for global outline, content length:', globalOutlineContent.value?.length || 0)
  } else {
    // 普通模式：使用生成的内容
    revisionContent.value = generatedContent.value
    generationId.value = currentGenerationId.value
    console.log('[Revision] Starting revision for generated content, generationId:', generationId.value)
  }
  
  const modeText = useTwoStageMode.value ? '全局大纲修订模式' : '修订模式'
  ElMessage.info(`已进入${modeText},请输入修改意见`)
}

/**
 * 提交修订
 */
async function submitRevision(userFeedback) {
  // 接收子组件传递的修订意见
  const feedback = userFeedback || revisionInput.value
  
  if (!feedback.trim()) {
    ElMessage.warning('请输入修改意见')
    return
  }
  
  // 两阶段大纲生成：使用本地简单修订（不调用后端API）
  if (useTwoStageMode.value) {
    submitLocalRevision(feedback)
    return
  }
  
  // 普通模式：调用后端修订API
  await submitRemoteRevision()
}

/**
 * 本地修订（两阶段大纲生成使用）
 */
async function submitLocalRevision(userFeedback) {
  revising.value = true
  
  // 使用传递的修订意见
  const currentFeedback = userFeedback || revisionInput.value
  
  // 添加用户消息
  revisionMessages.value.push({
    role: 'user',
    content: currentFeedback,
    timestamp: new Date()
  })
  
  try {
    // 调用后端API流式生成修订内容
    await generateApi.reviseGlobalOutlineStream(
      {
        content_type: type.value,
        current_content: revisionContent.value,
        user_feedback: currentFeedback,
        revision_history: revisionHistory.value.map(h => ({
          round: h.round_number,
          feedback: h.user_feedback,
          summary: h.diff_summary
        })),
        input_params: buildOutlineInputParams(),
        provider: null,
        temperature: 0.7
      },
      // onMessage - 处理SSE消息（streamGenerate传入的是完整内容和当前chunk）
      (fullContent, chunk) => {
        console.log('[Revision] onMessage called, fullContent length:', fullContent?.length, 'chunk:', chunk?.substring(0, 50))
        
        // 直接使用fullContent更新修订内容
        if (fullContent) {
          revisionContent.value = fullContent
          
          // 两阶段模式：同步更新全局大纲显示
          if (useTwoStageMode.value) {
            globalOutlineContent.value = fullContent
          }
          
          console.log('[Revision] Content updated, length:', revisionContent.value.length)
        }
      },
      // onWorkflow - 处理工作流事件（包括diff_complete和error）
      (event) => {
        console.log('[Revision] Workflow event:', event)
        if (event.type === 'diff_complete') {
          try {
            const diffInstructions = event.data
              
            // 记录修订历史
            revisionHistory.value.push({
              round_number: currentRevisionRound.value,
              user_feedback: currentFeedback,
              diff_summary: diffInstructions.summary || '已修改'
            })
              
            currentRevisionRound.value++
            revisionInput.value = ''
              
            // 添加AI回复
            revisionMessages.value.push({
              role: 'assistant',
              content: diffInstructions.summary || '修改完成'
            })
              
            ElMessage.success(`第${currentRevisionRound.value}轮修订完成`)
          } catch (e) {
            console.error('[Revision] Parse diff_complete failed:', e)
            ElMessage.error('解析修订结果失败')
          }
        } else if (event.type === 'error') {
          console.error('[Revision] Revision error:', event.data)
          ElMessage.error('修订失败: ' + (event.data?.data || event.data?.message || '未知错误'))
        }
      },
      // onStreamStart - 流开始回调
      () => {
        console.log('[Revision] Stream started')
      },
      // sessionId - 修订不需要session_id
      null
    )
  } catch (error) {
    console.error('[Revision] submitLocalRevision error:', error)
    ElMessage.error('修订失败: ' + (error.message || '未知错误'))
  } finally {
    revising.value = false
  }
}

/**
 * 远程修订（普通模式使用后端API）
 */
async function submitRemoteRevision() {
  
  if (!generationId.value) {
    ElMessage.error('未找到生成记录ID')
    return
  }
  
  console.log('[Revision] Starting remote revision, generationId:', generationId.value)
  console.log('[Revision] Revision round:', currentRevisionRound.value + 1)
  console.log('[Revision] User feedback:', revisionInput.value)
  
  revising.value = true
  currentRevisionRound.value++
  
  // 添加用户消息
  revisionMessages.value.push({
    role: 'user',
    content: revisionInput.value
  })
  
  // 添加超时机制
  let timeoutId = null
  const timeoutPromise = new Promise((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error('修订请求超时（60秒），请检查网络连接或后端服务'))
    }, 60000) // 60秒超时
  })
  
  try {
    const currentFeedback = revisionInput.value
    
    // 显示“正在生成”提示
    revisionMessages.value.push({
      role: 'assistant',
      content: '正在生成修改指令...'
    })
    
    console.log('[Revision] Calling revisionApi.revise()')
    
    // 使用Promise.race实现超时控制
    await Promise.race([
      revisionApi.revise(
        generationId.value,
        {
          generation_id: generationId.value,
          user_feedback: currentFeedback,
          current_content: revisionContent.value,
          original_params: form.value,
          module: type.value,
          round_number: currentRevisionRound.value
        },
        // onMessage: 流式接收diff指令
        (chunk) => {
          console.log('[Revision] Received SSE chunk:', chunk.substring(0, 100))
          // 解析SSE事件
          if (chunk.startsWith('event: diff_chunk\ndata: ')) {
            try {
              const jsonStr = chunk.split('data: ', 2)[1].trim()
              if (jsonStr) {
                const data = JSON.parse(jsonStr)
                console.log('[Revision] Received diff_chunk')
              }
            } catch (e) {
              console.error('Parse diff_chunk failed:', e)
            }
          } else if (chunk.startsWith('event: diff_complete\ndata: ')) {
            try {
              const jsonStr = chunk.split('data: ', 2)[1].trim()
              if (jsonStr) {
                const diffInstructions = JSON.parse(jsonStr)
                console.log('[Revision] Received diff_complete:', diffInstructions.summary)
                  
                // 验证格式
                if (!validateDiffInstructions(diffInstructions)) {
                  throw new Error('差异指令格式无效')
                }
                  
                // 应用diff到当前内容
                const newContent = applyDiffInstructions(
                  revisionContent.value,
                  diffInstructions
                )
                  
                revisionContent.value = newContent
                  
                // 移除"正在生成"消息,添加完成消息
                const lastMsgIndex = revisionMessages.value.length - 1
                if (lastMsgIndex >= 0 && 
                    revisionMessages.value[lastMsgIndex].content === '正在生成修改指令...') {
                  revisionMessages.value.pop()
                }
                  
                revisionMessages.value.push({
                  role: 'assistant',
                  content: diffInstructions.summary || '修改完成'
                })
                  
                // 记录修订历史
                revisionHistory.value.push({
                  round_number: currentRevisionRound.value,
                  user_feedback: currentFeedback,
                  diff_summary: diffInstructions.summary
                })
                  
                // 清空输入
                revisionInput.value = ''
                  
                ElMessage.success(`第${currentRevisionRound.value}轮修订完成`)
              }
            } catch (e) {
              console.error('Parse diff_complete failed:', e)
              ElMessage.error('解析差异指令失败')
            }
          } else if (chunk.startsWith('event: error\ndata: ')) {
            try {
              const jsonStr = chunk.split('data: ', 2)[1].trim()
              if (jsonStr) {
                const data = JSON.parse(jsonStr)
                throw new Error(data.data || data.message || '未知错误')
              }
            } catch (e) {
              console.error('Revision error:', e)
              ElMessage.error('修订失败: ' + e.message)
            }
          }
        },
        // onDone
        () => {
          console.log('[Revision] Stream completed')
          if (timeoutId) clearTimeout(timeoutId)
          revising.value = false
        },
        // onError
        (error) => {
          console.error('[Revision] Stream error:', error)
          if (timeoutId) clearTimeout(timeoutId)
          revising.value = false
          ElMessage.error('修订失败: ' + (error.message || '未知错误'))
        }
      ),
      timeoutPromise
    ])
      
    console.log('[Revision] Revision completed successfully')
  } catch (error) {
    console.error('[Revision] Revision failed:', error)
    if (timeoutId) clearTimeout(timeoutId)
    revising.value = false
    ElMessage.error('修订失败: ' + error.message)
  }
}

/**
 * 最终确认内容
 */
async function finalizeContent() {
  try {
    // 两阶段大纲生成：直接保存，不执行知识库修正
    if (useTwoStageMode.value) {
      finalizeLocalContent()
      return
    }
    
    // 普通模式：调用后端API执行知识库修正和自反思
    await finalizeRemoteContent()
  } catch (error) {
    console.error('最终确认失败:', error)
    ElMessage.error('最终确认失败: ' + error.message)
  }
}

/**
 * 本地最终确认（两阶段大纲生成使用）
 */
function finalizeLocalContent() {
  // 更新全局大纲内容
  if (useTwoStageMode.value) {
    globalOutlineContent.value = revisionContent.value
    console.log('[Revision] Local finalize: global outline updated, length:', revisionContent.value.length)
  } else {
    // 普通模式：更新生成内容
    generatedContent.value = revisionContent.value
  }
  
  // 退出修订模式
  isRevisionMode.value = false
  
  ElMessage.success('大纲已保存')
}

/**
 * 远程最终确认（普通模式使用后端API）
 */
async function finalizeRemoteContent() {
  try {
    const result = await revisionApi.finalize(generationId.value, {
      generation_id: generationId.value,
      final_content: revisionContent.value,
      enable_knowledge_check: true,
      enable_self_reflection: true
    })
    
    if (result.code === 200) {
      ElMessage.success('最终优化完成!')
      
      // 更新最终内容
      revisionContent.value = result.data.final_content
      generatedContent.value = result.data.final_content
      
      // 退出修订模式
      isRevisionMode.value = false
      
      // 显示优化建议(如果有)
      if (result.data.knowledge_issues && result.data.knowledge_issues.length > 0) {
        console.log('知识库问题:', result.data.knowledge_issues)
      }
      if (result.data.reflection_suggestions && result.data.reflection_suggestions.length > 0) {
        console.log('自反思建议:', result.data.reflection_suggestions)
      }
    } else {
      throw new Error(result.message || '最终确认失败')
    }
  } catch (error) {
    ElMessage.error('最终确认失败: ' + error.message)
  }
}

/**
 * 退出修订模式
 */
function exitRevision() {
  if (revisionMessages.value.length > 0) {
    // 如果有修订历史,提示用户是否保存
    ElMessageBox.confirm(
      '退出后将保留当前修改后的内容,是否继续?',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      // 更新生成的内容
      generatedContent.value = revisionContent.value
      isRevisionMode.value = false
    }).catch(() => {
      // 用户取消
    })
  } else {
    // 没有修订历史,直接退出
    isRevisionMode.value = false
  }
}

/**
 * 处理质量报告更新
 */
function handleUpdateQualityReport(newReport) {
  qualityReport.value = newReport
}

/**
 * 启动质控SSE订阅 (v1.1新增)
 * 实时接收全局大纲质控进度
 * v1.1修复: 添加token参数支持认证
 * v1.1修复: 添加重连机制
 */
function startQCSSESubscription(taskId) {
  // 关闭现有连接
  stopQCSSEConnection()
  
  // 获取token用于SSE认证（EventSource不支持自定义Header）
  const token = localStorage.getItem('token')
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  const sseURL = `${baseURL}/api/v1/novel-writer/quality-control/global-outline/${taskId}/events${token ? `?token=${encodeURIComponent(token)}` : ''}`
  
  console.log('[质控SSE] 连接到:', sseURL.replace(/token=[^&]+/, 'token=***'))
  
  // v1.1修复: 重连机制
  let reconnectAttempts = 0
  const MAX_RECONNECT_ATTEMPTS = 3
  const RECONNECT_DELAY = 2000 // 2秒
  
  const eventSource = new EventSource(sseURL)
  qcSSEConnection.value = eventSource
  
  eventSource.onopen = () => {
    console.log('[质控SSE] 连接已建立')
    reconnectAttempts = 0 // 重置重连计数器
  }
  
  eventSource.addEventListener('connected', (event) => {
    console.log('[质控SSE] 服务器确认连接:', event.data)
    reconnectAttempts = 0 // 重置重连计数器
  })
  
  eventSource.addEventListener('progress', (event) => {
    try {
      const data = JSON.parse(event.data)
      console.log('[质控SSE] 进度更新:', data)
      qcProgress.value = data
    } catch (e) {
      console.error('[质控SSE] 解析进度数据失败:', e)
    }
  })
  
  eventSource.addEventListener('completed', (event) => {
    try {
      const data = JSON.parse(event.data)
      console.log('[质控SSE] 分析完成:', data)
      qcProgress.value = { ...data, status: 'completed' }
      // 关闭SSE连接
      stopQCSSEConnection()
    } catch (e) {
      console.error('[质控SSE] 解析完成数据失败:', e)
    }
  })
  
  eventSource.addEventListener('error', (event) => {
    console.error('[质控SSE] 事件错误:', event)
    if (event.data) {
      try {
        const data = JSON.parse(event.data)
        qcProgress.value = { ...data, status: 'error' }
      } catch (e) {
        // 忽略解析错误
      }
    }
    stopQCSSEConnection()
  })
  
  eventSource.onerror = (error) => {
    console.warn('[质控SSE] 连接错误:', error)
    reconnectAttempts++
    
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error('[质控SSE] 重连次数已达上限')
      qcProgress.value = { 
        status: 'error', 
        message: '连接失败，请刷新页面重试',
        reconnect_failed: true
      }
      stopQCSSEConnection()
      ElMessage.warning('质控进度连接中断，但质控仍在后台运行，请稍后查看结果')
    } else {
      console.log(`[质控SSE] 浏览器自动重连中 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
      qcProgress.value = {
        status: 'reconnecting',
        message: `连接中断，正在重连 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`,
        reconnect_attempt: reconnectAttempts
      }
    }
  }
}

/**
 * 停止质控SSE连接 (v1.1新增)
 */
function stopQCSSEConnection() {
  if (qcSSEConnection.value) {
    qcSSEConnection.value.close()
    qcSSEConnection.value = null
    console.log('[质控SSE] 连接已关闭')
  }
}

/**
 * 对导入的单元概述执行质控检测
 */
async function handleImportedUnitSummariesQC() {
  if (!unitSummaries.value || Object.keys(unitSummaries.value).length === 0) {
    ElMessage.warning('没有可检测的单元概述')
    return
  }
  
  autoQCLoading.value = true
  
  try {
    // 调用导入大纲自动质控API（复用）
    const token = localStorage.getItem('access_token')
    const response = await fetch(
      `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/novel-writer/quality-control/imported-outline/auto-revise`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          outline_content: generatedContent.value,
          content_type: type.value === 'novel' ? 'novel' : 'script',
          enable_auto_revise: false  // 仅检测，不自动修正
        })
      }
    )
    
    const result = await response.json()
    
    if (result.success) {
      qcReportData.value = result.data.qc_report
      qcApplied.value = true
      issuesFixed.value = result.data.issues_fixed || 0
      
      ElMessage.success(`质控检测完成，发现 ${qcReportData.value?.issues?.length || 0} 个问题`)
    } else {
      ElMessage.error(result.message || '质控检测失败')
    }
  } catch (error) {
    console.error('质控检测失败:', error)
    ElMessage.error('质控检测失败: ' + (error.message || '未知错误'))
  } finally {
    autoQCLoading.value = false
  }
}

/**
 * 处理单元概述质量检测（手动触发）
 * 等待所有单元概述生成完成后，用户点击按钮触发质控检测
 */
async function handleUnitSummariesQC() {
  if (!unitSummaries.value || Object.keys(unitSummaries.value).length === 0) {
    ElMessage.warning('没有可检测的单元概述')
    return
  }
  
  // 检查全局大纲是否为空
  if (!globalOutlineContent.value || globalOutlineContent.value.trim().length === 0) {
    ElMessage.warning({
      message: '未检测到全局大纲！质控检测需要全局大纲作为参考标准。',
      duration: 5000,
      group: 'qc-warning'
    })
    
    // 询问用户是否继续
    try {
      await ElMessageBox.confirm(
        '当前没有全局大纲，质控检测可能不准确。您可以：\n\n1. 点击"取消"，先导入全局大纲\n2. 点击"继续"，使用当前内容检测（效果可能不佳）',
        '缺少全局大纲',
        {
          confirmButtonText: '继续检测',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
    } catch {
      // 用户取消
      return
    }
  }
  
  unitSummariesQCLoading.value = true
  
  try {
    // 使用unitSummariesQCApi调用（自动处理认证）
    const result = await unitSummariesQCApi.analyzeAndRevise({
      content_type: type.value === 'novel' ? 'novel' : 'script',
      global_outline: globalOutlineContent.value || '',
      unit_summaries: unitSummaries.value,
      enable_auto_revise: enableAutoRevise.value,
      temperature: 0.7
    })
    
    if (result.success) {
      const { quality_report, revised_content, revised_parsed, has_issues, issues_count, changes, auto_revised } = result.data
      
      // 显示质控报告
      qcReportData.value = quality_report
      qcApplied.value = true
      issuesFixed.value = issues_count || 0
      
      // 如果有修正结果，弹出对比对话框
      if (auto_revised && revised_content) {
        ElMessage.success(`质控检测完成，发现 ${quality_report?.issues?.length || 0} 个问题，已修正 ${changes?.length || 0} 个问题`)
        
        // 存储修正数据供后续使用
        unitSummariesReviseData.value = {
          originalContent: generatedContent.value,
          revisedContent: revised_content,
          revisedParsed: revised_parsed,
          qualityReport: quality_report,
          changes: changes || []  // 变更列表（用于显示修正详情）
        }
        
        // 显示修正对比对话框
        showUnitSummariesReviseDialog.value = true
      } else {
        const issueCount = quality_report?.issues?.length || 0
        if (issueCount > 0) {
          ElMessage.warning(`质控检测完成，发现 ${issueCount} 个问题，但未启用自动修正`)
        } else {
          ElMessage.success('质控检测完成，未发现任何问题')
        }
      }
    } else {
      ElMessage.error(result.message || '质控检测失败')
    }
  } catch (error) {
    console.error('单元概述质控检测失败:', error)
    
    // 区分超时错误和其他错误
    if (error.message && error.message.includes('timeout')) {
      ElMessage.error('质控检测超时（10分钟），请稍后重试或减少单元数量')
    } else {
      const errorMessage = error.message || error.response?.data?.message || '未知错误'
      ElMessage.error('质控检测失败: ' + errorMessage)
    }
  } finally {
    unitSummariesQCLoading.value = false
  }
}

/**
 * 处理全局大纲质量检测 (v1.0新增, v2.3优化, v1.1 SSE增强)
 * - 导入大纲场景：自动执行质控修正
 * - 新生成场景：显示质控报告
 * - v1.1新增: SSE实时进度推送
 */
async function handleGlobalOutlineQC() {
  try {
    // v2.3新增：导入大纲场景使用自动质控API
    if (importedOutline.value) {
      await handleAutoQCForImported()
      return
    }
    
    globalOutlineQCLoading.value = true
    qcProgress.value = null  // v1.1新增: 重置进度
    
    // 检查是否有全局大纲内容
    const outlineContent = editingGlobalOutline.value 
      ? editingGlobalOutlineContent.value
      : globalOutlineContent.value
    
    if (!outlineContent || outlineContent.trim().length === 0) {
      ElMessage.warning('全局大纲内容为空，请先生成全局大纲')
      return
    }
    
    // 两阶段大纲模式: 使用0作为projectId(表示大纲阶段)
    // 普通模式: 使用generationId
    const projectId = useTwoStageMode.value ? 0 : (generationId.value || 0)
    
    console.log('========== [全局大纲质控] 调试信息 ==========')
    console.log('useTwoStageMode:', useTwoStageMode.value)
    console.log('generationId:', generationId.value)
    console.log('projectId:', projectId)
    console.log('outlineContent length:', outlineContent.length)
    console.log('=============================================')
    
    // 调用API进行质量检测
    const requestData = {
      dimensions: null,  // 使用默认四维度
      depth: 'standard'
    }
    
    // 两阶段模式: 传递全局大纲内容
    if (useTwoStageMode.value) {
      requestData.existing_outline = outlineContent
      console.log('[全局大纲质控] 两阶段模式,传递大纲内容')
    }
    
    const response = await globalOutlineQCApi.analyze(projectId, requestData)
    
    // v1.1新增: 如果返回task_id，启动SSE订阅
    if (response?.task_id) {
      console.log('[全局大纲质控] 启动SSE订阅, task_id:', response.task_id)
      startQCSSESubscription(response.task_id)
    }
    
    if (response?.success) {
      console.log('========== [全局大纲质控] 响应数据 ==========')
      console.log('response:', response)
      console.log('response.success:', response.success)
      console.log('response.data:', response.data)
      console.log('response.data.overall_score:', response.data?.overall_score)
      console.log('response.data.issues:', response.data?.issues)
      console.log('response.data.dimension_scores:', response.data?.dimension_scores)
      console.log('=============================================')
      
      globalOutlineQCReport.value = response.data
      
      console.log('[全局大纲质控] globalOutlineQCReport.value:', globalOutlineQCReport.value)
      console.log('[全局大纲质控] globalOutlineQCReport.value !== null:', globalOutlineQCReport.value !== null)
      
      // 强制触发Vue更新
      await new Promise(resolve => setTimeout(resolve, 100))
      
      const issuesCount = response.data.issues?.length || 0
      ElMessage.success(
        `质量检测完成！综合得分: ${response.data.overall_score?.toFixed(1) || 0}分, ` +
        `发现 ${issuesCount} 个问题`
      )
      console.log('[全局大纲质控] 检测完成,消息已显示')
      
      // v2.3新增：如果发现问题，自动调用全局辩证性整体修正
      if (issuesCount > 0) {
        console.log('[全局大纲质控] 发现问题，开始自动修正...')
        ElMessage.info(`检测到 ${issuesCount} 个问题，正在自动进行全局辩证修正...`)
        
        // 调用自动修正函数
        await handleAutoGlobalOutlineRevise(response.data, outlineContent)
      }
    } else {
      ElMessage.error(response?.message || '质量检测失败')
      console.error('[全局大纲质控] API返回失败:', response)
    }
  } catch (error) {
    console.error('========== [全局大纲质控] 错误详情 ==========')
    console.error('错误类型:', error.constructor.name)
    console.error('错误消息:', error.message)
    console.error('错误堆栈:', error.stack)
    
    if (error.response) {
      console.error('HTTP状态码:', error.response.status)
      console.error('HTTP状态文本:', error.response.statusText)
      console.error('响应数据:', error.response.data)
      console.error('响应头:', error.response.headers)
    }
    
    if (error.request) {
      console.error('请求配置:', error.config)
      console.error('请求URL:', error.config?.url)
      console.error('请求方法:', error.config?.method)
      console.error('请求头:', error.config?.headers)
    }
    
    console.error('=============================================')
    
    // 检测超时错误
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.error('质量检测超时（20分钟），LLM分析耗时较长，请稍后重试。')
    } else if (error.response?.status === 405) {
      ElMessage.error('API端点不可用，请检查后端服务是否已重启')
    } else if (error.response?.status === 404) {
      ElMessage.error('API端点未找到，请检查后端路由配置')
    } else {
      ElMessage.error('质量检测失败: ' + (error.response?.data?.detail || error.message || ''))
    }
  } finally {
    globalOutlineQCLoading.value = false
  }
}

/**
 * 导入大纲自动质控修正 (v2.3新增)
 * 对导入的大纲自动执行质量检测并修正所有问题
 */
async function handleAutoQCForImported() {
  try {
    autoQCLoading.value = true
    
    const outlineContent = editingGlobalOutline.value 
      ? editingGlobalOutlineContent.value
      : globalOutlineContent.value
    
    if (!outlineContent || outlineContent.trim().length === 0) {
      ElMessage.warning('大纲内容为空')
      return
    }
    
    console.log('[导入大纲自动质控] 开始自动质控修正...')
    
    // 调用自动质控修正API
    const response = await globalOutlineQCApi.autoReviseImported({
      outline_content: outlineContent,
      depth: 'standard'  // 使用standard模式确保LLM深度分析
    })
    
    if (response?.success) {
      const data = response.data
      
      console.log('[导入大纲自动质控] 检查修正结果:')
      console.log('  - response.success:', response.success)
      console.log('  - revised_content存在:', !!data.revised_content)
      console.log('  - revised_content长度:', data.revised_content?.length || 0)
      console.log('  - issues_fixed:', data.issues_fixed)
      console.log('  - original_length:', data.original_length)
      console.log('  - revised_length:', data.revised_length)
      
      // 更新状态
      qcApplied.value = true
      issuesFixed.value = data.issues_fixed || 0
      qcReportData.value = data.qc_report
      
      // v2.4优化：如果有修正内容，显示对比对话框让用户确认
      if (data.revised_content) {
        console.log('[导入大纲自动质控] 修正完成，准备显示对比对话框...')
        
        // 填充对比对话框数据
        globalOutlineReviseData.value = {
          originalContent: outlineContent,
          revisedContent: data.revised_content,
          changes: data.qc_report?.issues || [],
          issueId: 'auto_revise_imported',
          issueDescription: `导入大纲自动质控修正 ${data.issues_fixed || 0} 个问题`,
          originalLength: data.original_length || outlineContent.length,
          revisedLength: data.revised_length || data.revised_content.length
        }
        
        console.log('[导入大纲自动质控] 对话框数据已填充:')
        console.log('  - originalContent长度:', globalOutlineReviseData.value.originalContent.length)
        console.log('  - revisedContent长度:', globalOutlineReviseData.value.revisedContent.length)
        console.log('  - changes数量:', globalOutlineReviseData.value.changes.length)
        console.log('  - originalLength:', globalOutlineReviseData.value.originalLength)
        console.log('  - revisedLength:', globalOutlineReviseData.value.revisedLength)
        
        // 显示对比对话框
        showGlobalOutlineReviseDialog.value = true
        
        console.log('[导入大纲自动质控] 对话框状态:', showGlobalOutlineReviseDialog.value)
        console.log('[导入大纲自动质控] 对比对话框已显示，等待用户确认')
        
        ElMessage.info(`质量检测完成，发现 ${issuesFixed.value} 个问题，已自动修正。请确认修正结果。`)
      } else {
        // 没有修正内容，直接更新报告
        console.log('[导入大纲自动质控] 无修正内容，直接完成')
        
        // 清除旧的质控报告显示
        globalOutlineQCReport.value = null
        
        if (issuesFixed.value > 0) {
          ElMessage.success(`质量检测完成，已自动修正 ${issuesFixed.value} 个问题`)
        } else {
          ElMessage.success('质量检测完成，未发现需要修正的问题')
        }
      }
      
      console.log('[导入大纲自动质控] 完成，修正问题数:', issuesFixed.value)
    } else {
      ElMessage.error(response?.message || '自动质控修正失败')
    }
  } catch (error) {
    console.error('[导入大纲自动质控] 错误:', error)
    
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.error('质量检测超时（20分钟），LLM分析耗时较长，请稍后重试。')
    } else {
      ElMessage.error('质量检测失败: ' + (error.message || ''))
    }
  } finally {
    autoQCLoading.value = false
  }
}

/**
 * 自动全局大纲辩证性整体修正 (v2.3新增)
 * 质控检测发现问题后，自动调用LLM进行全局辩证修正
 * @param {Object} qualityReport - 质控报告
 * @param {String} originalContent - 原始大纲内容
 */
async function handleAutoGlobalOutlineRevise(qualityReport, originalContent) {
  try {
    // v2.3修复：设置修正状态，防止并发操作
    revisingIssueId.value = 'auto_revise_all'
    
    console.log('[自动全局修正] 开始全局辩证性整体修正...')
    
    // 两阶段大纲模式: 使用0作为projectId(表示大纲阶段)
    // 普通模式: 使用generationId
    const projectId = useTwoStageMode.value ? 0 : (generationId.value || 0)
    
    // 提取所有问题ID
    const issuesToFix = qualityReport.issues?.map(issue => issue.id) || []
    
    if (issuesToFix.length === 0) {
      console.log('[自动全局修正] 没有需要修正的问题')
      return
    }
    
    console.log(`[自动全局修正] 准备修正 ${issuesToFix.length} 个问题`)
    
    // v2.3修复：确保qualityReport包含original_outline字段（两阶段模式必需）
    const qualityReportWithOutline = {
      ...qualityReport,
      original_outline: qualityReport.original_outline || originalContent
    }
    
    // 调用修正API（传递所有问题，执行全局辩证性整体修正）
    const response = await globalOutlineQCApi.revise(projectId, {
      quality_report: qualityReportWithOutline,
      issues_to_fix: issuesToFix  // 传递所有问题ID，触发全局辩证修正
    })
    
    if (response?.success) {
      const revisedContent = response.data.revised_content
      console.log('[自动全局修正] 检查修正结果:')
      console.log('  - response.success:', response.success)
      console.log('  - revisedContent存在:', !!revisedContent)
      console.log('  - revisedContent长度:', revisedContent?.length || 0)
      console.log('  - response.data:', response.data)
      
      if (revisedContent) {
        console.log('[自动全局修正] 修正完成，准备显示对比对话框...')
        
        // v2.4新增：显示修正对比对话框
        globalOutlineReviseData.value = {
          originalContent: originalContent,
          revisedContent: revisedContent,
          changes: response.data.changes || qualityReport.issues || [],
          issueId: 'auto_revise_all',
          issueDescription: `自动修正 ${issuesToFix.length} 个问题`,
          originalLength: response.data.original_length || originalContent.length,
          revisedLength: response.data.revised_length || revisedContent.length
        }
        
        console.log('[自动全局修正] 对话框数据已填充:')
        console.log('  - originalContent长度:', globalOutlineReviseData.value.originalContent.length)
        console.log('  - revisedContent长度:', globalOutlineReviseData.value.revisedContent.length)
        console.log('  - changes数量:', globalOutlineReviseData.value.changes.length)
        console.log('  - originalLength:', globalOutlineReviseData.value.originalLength)
        console.log('  - revisedLength:', globalOutlineReviseData.value.revisedLength)
        
        showGlobalOutlineReviseDialog.value = true
        
        console.log('[自动全局修正] 对话框状态:', showGlobalOutlineReviseDialog.value)
        console.log('[自动全局修正] 对比对话框已显示，等待用户确认')
        
        // 更新质控报告状态
        globalOutlineQCReport.value = {
          ...qualityReport,
          revised: true,
          revised_at: new Date().toISOString(),
          revised_issues: issuesToFix
        }
      } else {
        console.error('[自动全局修正] 警告: revisedContent为空!')
        console.error('[自动全局修正] response.data:', response.data)
        ElMessage.warning('修正完成但未返回修正内容，请检查后端日志')
      }
    } else {
      console.error('[自动全局修正] API返回失败:', response)
      ElMessage.warning(`自动修正失败: ${response?.message || '未知错误'}`)
    }
  } catch (error) {
    console.error('[自动全局修正] 修正失败:', error)
    
    // 检测超时错误
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.warning('全局修正超时（20分钟），LLM处理耗时较长，可稍后手动触发修正。')
    } else {
      ElMessage.warning('全局修正失败: ' + (error.message || ''))
    }
  } finally {
    // v2.3修复：确保状态被重置
    revisingIssueId.value = null
  }
}

/**
 * 确认应用全局大纲修正
 */
function handleConfirmGlobalOutlineRevise() {
  const issueId = globalOutlineReviseData.value.issueId
  
  // 应用修正后的内容
  globalOutlineContent.value = globalOutlineReviseData.value.revisedContent
  generatedContent.value = globalOutlineReviseData.value.revisedContent
  if (editingGlobalOutline.value) {
    editingGlobalOutlineContent.value = globalOutlineReviseData.value.revisedContent
  }
  
  // 标记已应用质控修正
  qcApplied.value = true
  issuesFixed.value = globalOutlineReviseData.value.changes?.length || 0
  
  // 根据修正来源设置质控报告
  if (issueId === 'auto_revise_imported') {
    // 导入大纲场景：使用已有的qcReportData
    console.log('[全局大纲修正] 导入大纲场景，使用已有质控报告')
  } else {
    // 其他场景：使用globalOutlineQCReport
    qcReportData.value = globalOutlineQCReport.value
  }
  
  // v2.3修复：清除SSE进度状态
  qcProgress.value = null
  stopQCSSEConnection()
  
  // 关闭对话框
  showGlobalOutlineReviseDialog.value = false
  
  // 根据修正来源显示不同的成功消息
  if (issueId === 'auto_revise_imported') {
    ElMessage.success(
      `已应用导入大纲修正！共修正 ${issuesFixed.value} 个问题 ` +
      `(${globalOutlineReviseData.value.originalLength}字 → ${globalOutlineReviseData.value.revisedLength}字)`
    )
  } else {
    ElMessage.success(
      `已应用全局辩证修正！共修正 ${issuesFixed.value} 个问题 ` +
      `(${globalOutlineReviseData.value.originalLength}字 → ${globalOutlineReviseData.value.revisedLength}字)`
    )
  }
  
  console.log('[全局大纲修正] 修正已应用, issueId:', issueId)
}

/**
 * 取消应用全局大纲修正
 */
function handleCancelGlobalOutlineRevise() {
  // 不应用修正，保持原始内容
  ElMessage.info('已取消修正，保留原始内容')
  console.log('[全局大纲修正] 修正已取消')
}

/**
 * 处理单元概述修正确认
 */
function handleConfirmUnitSummariesRevise() {
  // 应用修正后的内容
  generatedContent.value = unitSummariesReviseData.value.revisedContent
  
  // 更新单元概述数据
  if (unitSummariesReviseData.value.revisedParsed) {
    unitSummaries.value = unitSummariesReviseData.value.revisedParsed
  }
  
  // 标记已应用质控修正
  qcApplied.value = true
  issuesFixed.value = unitSummariesReviseData.value.qualityReport?.issues?.filter(i => i.severity === 'critical').length || 0
  qcReportData.value = unitSummariesReviseData.value.qualityReport
  
  // 关闭对话框
  showUnitSummariesReviseDialog.value = false
  
  ElMessage.success('已应用单元概述修正')
  console.log('[单元概述修正] 修正已应用')
}

/**
 * 处理单元概述修正取消
 */
function handleCancelUnitSummariesRevise() {
  // 清理修正数据
  unitSummariesReviseData.value = {
    originalContent: '',
    revisedContent: '',
    revisedParsed: null,
    qualityReport: null
  }
  
  ElMessage.info('已取消修正，保留原始内容')
  console.log('[单元概述修正] 修正已取消，数据已清理')
}

/**
 * 处理全局大纲修正 (v2.2优化: 显示对比对话框)
 */
async function handleGlobalOutlineRevise({ issue, qualityReport: report }) {
  try {
    if (!issue || !report) {
      ElMessage.error('修正参数不完整')
      return
    }
    
    revisingIssueId.value = issue.id
    
    // 两阶段大纲模式: 使用0作为projectId(表示大纲阶段)
    // 普通模式: 使用generationId
    const projectId = useTwoStageMode.value ? 0 : (generationId.value || 0)
    
    console.log('[全局大纲修正] 开始修正问题:', issue.id, 'projectId:', projectId)
    
    // 保存原始内容用于对比
    const originalContent = editingGlobalOutline.value 
      ? editingGlobalOutlineContent.value 
      : globalOutlineContent.value
    
    // 调用API进行修正
    const response = await globalOutlineQCApi.revise(projectId, {
      quality_report: report,
      issues_to_fix: [issue.id]
    })
    
    if (response?.success) {
      const revisedContent = response.data.revised_content
      if (revisedContent) {
        // v2.2优化: 显示对比对话框，让用户确认是否应用修改
        globalOutlineReviseData.value = {
          originalContent: originalContent,
          revisedContent: revisedContent,
          changes: response.data.changes || [],
          issueId: issue.id,
          issueDescription: issue.description,
          originalLength: response.data.original_length,
          revisedLength: response.data.revised_length
        }
        showGlobalOutlineReviseDialog.value = true
        ElMessage.success('修正完成！请确认是否应用修改')
      }
    } else {
      ElMessage.error(response?.message || '修正失败')
    }
  } catch (error) {
    console.error('[全局大纲修正] 修正失败:', error)
    
    // 检测超时错误
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.error('修正超时（20分钟），LLM处理耗时较长，请稍后重试。')
    } else {
      ElMessage.error('修正失败: ' + (error.message || ''))
    }
  } finally {
    revisingIssueId.value = null
  }
}

// v2.1新增: 处理单元内容更新（质控修正应用）
function handleUpdateUnitContent({ chapter_number, unit_id, content }) {
  console.log('=== 更新单元内容 ===')
  console.log('chapter_number:', chapter_number)
  console.log('unit_id:', unit_id)
  console.log('新内容长度:', content?.length, '字')
  
  if (!chapter_number || !content) {
    console.error('缺少chapter_number或content')
    return
  }
  
  const key = String(chapter_number)
  
  // 优先使用unit_id精确定位（v2.1新增）
  if (unit_id && unitSummaries.value[key]) {
    console.log('使用unit_id精确定位')
    unitSummaries.value[key].summary = content
    unitSummaries.value[key].full_content = content
    
    // 同时更新generatedContent中对应的内容
    updateGeneratedContentUnit(chapter_number, content)
    
    ElMessage.success(`第${chapter_number}单元已更新`)
    return
  }
  
  // 降级方案：仅使用chapter_number定位
  if (unitSummaries.value[key]) {
    console.log('使用chapter_number定位')
    unitSummaries.value[key].summary = content
    unitSummaries.value[key].full_content = content
    
    // 同时更新generatedContent中对应的内容
    updateGeneratedContentUnit(chapter_number, content)
    
    ElMessage.success(`第${chapter_number}单元已更新`)
    return
  }
  
  console.error(`未找到第${chapter_number}单元`)
  ElMessage.error(`未找到第${chapter_number}单元`)
}

// 辅助函数: 更新generatedContent中的指定单元
function updateGeneratedContentUnit(chapterNumber, newContent) {
  if (!generatedContent.value) return
  
  const isMovie = generatedContent.value.includes('场') && !generatedContent.value.includes('集')
  
  // 构建匹配模式
  const patterns = isMovie
    ? [
        new RegExp(`(\\*\\*第${chapterNumber}场[\\s\\S]*?\\*\\*)(?:[\\s\\S]*?)(?=\\*\\*第${chapterNumber + 1}场|$)`),
      ]
    : [
        new RegExp(`(###\\s*第${chapterNumber}(?:章|集)[\\s\\S]*?)(?=###\\s*第${chapterNumber + 1}(?:章|集)|$)`),
      ]
  
  for (const pattern of patterns) {
    const match = generatedContent.value.match(pattern)
    if (match) {
      // 保留标题部分，只替换内容
      const titlePart = match[1]
      const oldContent = match[0]
      const newFullContent = titlePart + '\n' + newContent
      
      generatedContent.value = generatedContent.value.replace(oldContent, newFullContent)
      console.log('已更新generatedContent中的单元内容')
      return
    }
  }
  
  console.warn('未能在generatedContent中找到对应单元')
}
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
