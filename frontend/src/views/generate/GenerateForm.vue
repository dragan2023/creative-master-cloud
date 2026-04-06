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
            />
            
            <!-- 知识库增强区域 -->
            <KnowledgeBaseSection ref="knowledgeBaseSectionRef" />
            
            <!-- 提交按钮 -->
            <div class="form-actions">
              <el-button @click="resetForm">重置</el-button>
              <!-- 两阶段大纲生成模式：显示导入按钮 -->
              <el-button v-if="useTwoStageMode" @click="openImportDialog">
                <el-icon><Upload /></el-icon>
                导入已有大纲
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
      @stop="handleStop"
      @generate-unit-summaries="handleGenerateUnitSummaries"
      @cancel-unit-summaries="cancelUnitSummariesGeneration"
      @download-outline="downloadOutline"
      @open-start-unit-dialog="openStartUnitDialog"
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
          请粘贴全局大纲内容，系统将跳过第一阶段，直接进入审核修改阶段
        </span>
        <span v-else>
          请粘贴完整大纲内容（包含全局大纲和单元概述），系统将尝试解析并跳转到完成阶段
        </span>
      </div>
      
      <el-input
        v-model="importContent"
        type="textarea"
        :rows="15"
        placeholder="请在此粘贴大纲内容..."
        class="import-textarea"
      />
    </div>
    <template #footer>
      <el-button @click="showImportDialog = false">取消</el-button>
      <el-button type="primary" @click="confirmImport">确认导入</el-button>
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
import { ElMessage } from 'element-plus'
import { CREATIVE_MODULES } from '@/config'
import { generateApi } from '@/api'
import { useApiKeyStore } from '@/stores'
import { API_BASE_URL } from '@/config'
import { useUserStore } from '@/stores/user'

// 导入子组件
import FormFieldsSection from './components/FormFieldsSection.vue'
import KnowledgeBaseSection from './components/KnowledgeBaseSection.vue'
import WorkflowProgress from './components/WorkflowProgress.vue'
import ResultViewer from './components/ResultViewer.vue'

// 导入composables
import { useGenerationForm } from './composables/useGenerationForm'
import { useStreamHandler } from './composables/useStreamHandler'
import { useWorkflow } from './composables/useWorkflow'

const router = useRouter()
const route = useRoute()
const apiKeyStore = useApiKeyStore()
const userStore = useUserStore()

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

// 逻辑检测状态
const logicChecking = ref(false)
const logicCheckResult = ref(null)
const showLogicIssuesDialog = ref(false)

// 修正详情对话框状态
const showRevisionDetailDialog = ref(false)
const currentRevisionUnit = ref(null)
const revisionViewMode = ref('diff')

// 编辑状态
const editingUnitNumber = ref(null)
const editingUnitContent = ref('')
const editingGlobalOutline = ref(false)
const editingGlobalOutlineContent = ref('')

// 灵活介入流程状态
const showImportDialog = ref(false)
const importType = ref('global')
const importContent = ref('')
const startFromUnit = ref(1)
const showStartUnitDialog = ref(false)

// 知识库组件引用
const knowledgeBaseSectionRef = ref(null)

onMounted(async () => {
  await apiKeyStore.fetchApiKeys()
  restoreFormData()
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
    await handleTwoStageGenerate()
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
        temperature: 0.7
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
      genre: Array.isArray(form.value.genre) ? form.value.genre.join('、') : (form.value.genre || '言情'),
      target_platform: form.value.target_platform || '起点',
      tone: form.value.tone || '正剧',
      synopsis: form.value.description,
      theme: form.value.theme || '',
      unique_selling_point: form.value.unique_selling_point || '',
      chapter_count: form.value.chapter_count || '50',
      custom_outline: form.value.custom_outline || ''
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
  
  const unitCount = type.value === 'novel' 
    ? parseInt(form.value.chapter_count) || 50
    : parseInt(form.value.episode_count) || 24
  
  currentSessionId.value = `unit_summaries_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  
  outlineStage.value = 3
  unitSummariesGenerating.value = true
  unitSummaries.value = {}
  
  try {
    const result = await generateApi.generateUnitSummariesStream(
      {
        content_type: type.value,
        global_outline: globalOutlineContent.value,
        unit_count: unitCount,
        series_type: type.value === 'script' ? form.value.series_type : null,
        episode_duration_range: type.value === 'script' 
          ? `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟` 
          : null,
        provider: null,
        model: null,
        temperature: 0.7
      },
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
        generatedContent.value = newContent
        ElMessage.success(message || '内容已更新')
      }
    )
    
    if (result && !result.cancelled) {
      unitSummaries.value = parseUnitSummariesFromContent(result.content)
      await performLogicCheck()
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
    
    const summaryPattern = isMovie
      ? new RegExp(`\\*\\*本场梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
      : new RegExp(`\\*\\*本(?:章|集)梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
    
    const summaryMatch = content.slice(match.index, match.index + 500).match(summaryPattern)
    const summary = summaryMatch ? summaryMatch[1].trim() : ''
    
    result[unitNum.toString()] = {
      unit_number: unitNum,
      title: title,
      summary: summary,
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
          ElMessage.warning(`逻辑检测发现 ${response.data.issues?.length || 0} 个潜在问题`)
        }
      }
    }
  } catch (error) {
    console.error('逻辑检测失败:', error)
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
  showImportDialog.value = true
}

// 确认导入内容
function confirmImport() {
  if (!importContent.value.trim()) {
    ElMessage.warning('请粘贴要导入的大纲内容')
    return
  }
  
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

// 打开从指定单元开始的对话框
function openStartUnitDialog() {
  const unitCount = type.value === 'novel'
    ? parseInt(form.value.chapter_count) || 50
    : parseInt(form.value.episode_count) || 24
  startFromUnit.value = Math.min(startFromUnit.value, unitCount)
  showStartUnitDialog.value = true
}

// 从指定单元开始生成
async function handleGenerateFromUnit() {
  if (!globalOutlineContent.value) {
    ElMessage.warning('请先导入或生成全局大纲')
    return
  }
  
  const unitCount = type.value === 'novel'
    ? parseInt(form.value.chapter_count) || 50
    : parseInt(form.value.episode_count) || 24
  
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
        unit_count: unitCount - startFromUnit.value + 1,
        series_type: type.value === 'script' ? form.value.series_type : null,
        episode_duration_range: type.value === 'script'
          ? `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟`
          : null,
        script_mode: type.value === 'script' ? (form.value.script_mode || 'real') : null,
        provider: null,
        model: null,
        temperature: 0.7
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
  
  .import-textarea {
    .el-textarea__inner {
      font-family: monospace;
      font-size: 13px;
      line-height: 1.5;
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
