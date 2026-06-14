<!--
  ContentPreviewDialog.vue - 单元内容统一预览弹窗
  
  功能：
  1. 统一展示初稿/修正稿/自主修订稿的格式化内容
  2. 版本切换 tabs（哪个版本有内容就显示哪个 tab）
  3. 弹窗内集成"编辑内容"和"继续调整内容"操作按钮
  4. 内容以渲染后的HTML展示（markdown → 格式化HTML）
  
  @date: 2026-06-03
  @version: v1.0.0
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="dialogTitle"
    width="900px"
    top="3vh"
    :close-on-click-modal="false"
    destroy-on-close
    class="content-preview-dialog"
  >
    <div class="preview-container">
      <!-- 版本切换 tabs -->
      <div class="version-tabs" v-if="availableVersions.length > 1">
        <el-radio-group v-model="currentVersion" size="small">
          <el-radio-button
            v-for="ver in availableVersions"
            :key="ver.key"
            :value="ver.key"
          >
            {{ ver.label }}
          </el-radio-button>
        </el-radio-group>
        <span class="version-word-count" v-if="currentContent">
          {{ currentContent.length }} 字
        </span>
      </div>

      <!-- 内容显示区域 -->
      <div class="content-area">
        <!-- 编辑模式 -->
        <template v-if="isEditing">
          <el-input
            v-model="editContent"
            type="textarea"
            :rows="20"
            placeholder="请输入内容..."
          />
          <div class="edit-actions">
            <el-button type="success" size="small" @click="handleSaveEdit" :loading="savingEdit">
              <el-icon><Check /></el-icon> 保存修改
            </el-button>
            <el-button size="small" @click="cancelEdit">
              <el-icon><Close /></el-icon> 取消
            </el-button>
          </div>
        </template>

        <!-- 预览模式 -->
        <template v-else>
          <div
            v-if="currentContent"
            class="markdown-content"
            v-html="sanitizeHtml(renderMarkdown(currentContent))"
          ></div>
          <el-empty v-else :description="emptyDescription" :image-size="60" />
        </template>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="$emit('update:visible', false)">关闭</el-button>
        <el-button
          v-if="!isEditing && currentContent"
          type="primary"
          plain
          @click="startEdit"
        >
          <el-icon><Edit /></el-icon> {{ currentVersion === 'ai_resource' ? '编辑AI资源' : '编辑内容' }}
        </el-button>
        <el-button
          v-if="!isEditing && currentContent && currentVersion !== 'ai_resource'"
          type="warning"
          plain
          @click="openRevision"
        >
          <el-icon><ChatDotRound /></el-icon> 继续调整内容
        </el-button>
      </div>
    </template>
  </el-dialog>

  <!-- 对话修正弹窗（嵌套） -->
  <UnitRevisionDialog
    v-model:visible="showRevisionDialog"
    :unit-index="unit?.unit_index || 0"
    :project-id="projectId"
    :unit-title="unit?.unit_title || ''"
    :current-content="currentContent"
    @content-updated="handleRevisionContentUpdated"
  />
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  Edit, Check, Close, ChatDotRound,
} from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'
import { useWritingTaskStore } from '@/stores/writingTask'
import UnitRevisionDialog from './UnitRevisionDialog.vue'

const writingStore = useWritingTaskStore()

const props = defineProps({
  visible: { type: Boolean, default: false },
  unit: { type: Object, default: null },
  projectId: { type: Number, required: true },
  /** v4.0: 从外部指定打开弹窗时的目标版本（不传则自动选择最佳版本） */
  targetVersion: { type: String, default: null },
  /** v4.0优化: 内容类型，用于控制版本选择 */
  contentType: { type: String, default: 'novel' },
})

const emit = defineEmits([
  'update:visible',
  'content-updated',
])

// ==================== 版本定义 ====================
const BASE_VERSION_DEFS = [
  { key: 'self_revise', label: '自主修订稿', field: 'content_after_self_revise' },
  { key: 'qc_fix', label: '修正稿', field: 'content_after_qc_fix' },
  { key: 'draft', label: '初稿', field: 'content_after_generation' },
  { key: 'ai_resource', label: 'AI资源', field: 'ai_resource_content' },
]

// v4.0优化: 剧本类型不显示qc_fix版本
const VERSION_DEFS = computed(() => {
  if (props.contentType !== 'novel') {
    return BASE_VERSION_DEFS.filter(def => def.key !== 'qc_fix')
  }
  return BASE_VERSION_DEFS
})

// ==================== 状态 ====================
// v4.0优化: 剧本类型默认版本为draft，小说类型默认qc_fix
const currentVersion = ref(props.contentType === 'novel' ? 'qc_fix' : 'draft')
const isEditing = ref(false)
const editContent = ref('')
const savingEdit = ref(false)
const showRevisionDialog = ref(false)

// ==================== 计算属性 ====================

/**
 * 获取指定版本的内容
 * 
 * 三个内容版本的语义（不可混用）：
 * - 'draft':      LLM首次输出的完整稿件 → content_after_generation（永不回退到final_content）
 * - 'qc_fix':     自动质控修正后的完整稿件 → content_after_qc_fix
 * - 'self_revise': 用户对话修正后的完整稿件 → content_after_self_revise
 */
function getVersionContent(versionKey) {
  if (!props.unit) return ''
  const qc = props.unit.quality_control || {}
  switch (versionKey) {
    case 'self_revise':
      // qc对象优先，top-level字段作为回退
      return qc.content_after_self_revise || props.unit.content_after_self_revise || ''
    case 'qc_fix':
      // qc对象优先，top-level字段作为回退；fixed_content是旧字段，作为最后回退
      return qc.content_after_qc_fix || props.unit.content_after_qc_fix || qc.fixed_content || ''
    case 'draft':
      // 初稿永不回退到final_content（QC修正后final_content已是修正稿）
      return qc.content_after_generation || props.unit.content_after_generation || ''
    case 'ai_resource':
      // AI视觉资源独立存储（v4.1）
      return props.unit.ai_resource_content || ''
    default:
      return ''
  }
}

/** 可用的版本列表（AI资源模式下隐藏版本切换） */
const availableVersions = computed(() => {
  // AI资源模式下不显示版本切换tabs
  if (currentVersion.value === 'ai_resource') return []
  return VERSION_DEFS.value.filter(def => def.key !== 'ai_resource' && !!getVersionContent(def.key))
})

/** 当前选中版本的内容 */
const currentContent = computed(() => getVersionContent(currentVersion.value))

/** 弹窗标题 */
const dialogTitle = computed(() => {
  const unitLabel = props.unit?.unit_title || `单元 ${props.unit?.unit_index || ''}`
  if (currentVersion.value === 'ai_resource') {
    return `AI视觉资源 - ${unitLabel}`
  }
  const verDef = VERSION_DEFS.value.find(d => d.key === currentVersion.value)
  const verLabel = verDef ? verDef.label : ''
  return `${verLabel} - ${unitLabel}`
})

/** 空内容提示 */
const emptyDescription = computed(() => {
  const verDef = VERSION_DEFS.value.find(d => d.key === currentVersion.value)
  return verDef ? `暂无${verDef.label}内容` : '暂无内容'
})

// ==================== 监听 ====================

// 打开弹窗时，自动选择最佳版本
watch(() => props.visible, (val) => {
  if (val && props.unit) {
    isEditing.value = false
    // v4.0: 外部指定版本优先，否则按优先级自动选择
    if (props.targetVersion && getVersionContent(props.targetVersion)) {
      currentVersion.value = props.targetVersion
    } else if (getVersionContent('self_revise')) {
      currentVersion.value = 'self_revise'
    } else if (props.contentType === 'novel' && getVersionContent('qc_fix')) {
      // v4.0优化: 仅小说类型才考虑qc_fix版本
      currentVersion.value = 'qc_fix'
    } else {
      currentVersion.value = 'draft'
    }
  }
})

// ==================== 辅助函数 ====================

/** 安全渲染HTML */
function sanitizeHtml(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html)
}

/** Markdown渲染 */
function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch {
    return text
  }
}

// ==================== 编辑功能 ====================

function startEdit() {
  editContent.value = currentContent.value
  isEditing.value = true
}

function cancelEdit() {
  isEditing.value = false
  editContent.value = ''
}

async function handleSaveEdit() {
  const newContent = editContent.value
  if (!newContent || newContent.trim() === '') {
    ElMessage.warning('内容不能为空')
    return
  }

  savingEdit.value = true
  try {
    if (currentVersion.value === 'ai_resource') {
      // AI资源保存使用专门API
      await novelWriterApi.saveAIResource(props.projectId, props.unit.unit_index, newContent)
    } else {
      await novelWriterApi.updateUnitContent({
        unit_index: props.unit.unit_index,
        content: newContent,
        project_id: props.projectId,
        save_as: currentVersion.value === 'self_revise' ? 'self_revise' : 
                currentVersion.value === 'draft' ? 'draft' : 'qc_fix',
      })
    }

    // v4.0: 通过 store 更新单元数据（替代直接修改 props）
    const unitIdx = writingStore.units.findIndex(
      u => u.unit_index === props.unit.unit_index
    )
    if (unitIdx !== -1) {
      const storeUnit = writingStore.units[unitIdx]
      const qc = storeUnit.quality_control || {}
      if (currentVersion.value === 'ai_resource') {
        storeUnit.ai_resource_content = newContent
      } else if (currentVersion.value === 'self_revise') {
        storeUnit.quality_control = { ...qc, content_after_self_revise: newContent }
      } else if (currentVersion.value === 'draft') {
        storeUnit.quality_control = { ...qc, content_after_generation: newContent }
      } else {
        storeUnit.quality_control = {
          ...qc,
          content_after_qc_fix: newContent,
          fixed_content: newContent,
        }
      }
      storeUnit.final_content = newContent
      storeUnit.word_count = newContent.length
    }

    ElMessage.success('内容已保存')
    isEditing.value = false
    editContent.value = ''

    emit('content-updated', {
      unit_index: props.unit.unit_index,
      content: newContent,
      version: currentVersion.value,
    })
  } catch (error) {
    console.error('[ContentPreviewDialog] 保存失败:', error)
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    savingEdit.value = false
  }
}

// ==================== 修订功能 ====================

function openRevision() {
  showRevisionDialog.value = true
}

function handleRevisionContentUpdated(data) {
  if (props.unit && data) {
    // v4.0: 通过 store 更新单元数据
    const unitIdx = writingStore.units.findIndex(
      u => u.unit_index === props.unit.unit_index
    )
    if (unitIdx !== -1) {
      const storeUnit = writingStore.units[unitIdx]
      const qc = storeUnit.quality_control || {}
      // 保存到自主修订稿
      storeUnit.quality_control = { ...qc, content_after_self_revise: data.content }
      storeUnit.final_content = data.content
      storeUnit.word_count = data.content ? data.content.length : 0
    }

    // 切换到自主修订稿 tab
    currentVersion.value = 'self_revise'

    emit('content-updated', {
      unit_index: props.unit.unit_index,
      content: data.content,
      version: 'self_revise',
    })
  }
}
</script>

<style lang="scss" scoped>
.content-preview-dialog {
  .preview-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-height: 400px;
  }

  .version-tabs {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: #f5f7fa;
    border-radius: 8px;

    .version-word-count {
      font-size: 12px;
      color: #909399;
      flex-shrink: 0;
    }
  }

  .content-area {
    flex: 1;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    overflow: hidden;

    .markdown-content {
      padding: 20px 24px;
      max-height: 500px;
      overflow-y: auto;
      font-size: 15px;
      line-height: 2;
      color: #303133;
      white-space: pre-wrap;
      word-break: break-word;

      :deep(p) {
        margin-bottom: 12px;
        text-indent: 2em;
      }

      :deep(h1), :deep(h2), :deep(h3),
      :deep(h4), :deep(h5), :deep(h6) {
        margin-top: 20px;
        margin-bottom: 12px;
        font-weight: 600;
        line-height: 1.4;
      }

      :deep(h1) { font-size: 24px; }
      :deep(h2) { font-size: 20px; }
      :deep(h3) { font-size: 18px; }

      :deep(strong) {
        font-weight: 700;
      }

      :deep(em) {
        font-style: italic;
      }

      :deep(ul), :deep(ol) {
        padding-left: 24px;
        margin-bottom: 12px;
      }

      :deep(li) {
        margin-bottom: 4px;
      }

      :deep(blockquote) {
        margin: 12px 0;
        padding: 8px 16px;
        border-left: 4px solid #409eff;
        background: #ecf5ff;
        color: #606266;
      }

      :deep(hr) {
        margin: 16px 0;
        border: none;
        border-top: 1px solid #ebeef5;
      }
    }

    .edit-actions {
      display: flex;
      gap: 8px;
      padding: 12px 24px;
      border-top: 1px solid #ebeef5;
      background: #fafafa;
    }
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
}
</style>
