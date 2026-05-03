<!--
  组件: RevisionDialog
  AI对话修订弹窗
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="AI对话修订"
    width="1100px"
  >
    <div class="revision-container">
      <div class="revision-chat">
        <div class="chat-header">
          <h4>
            <el-icon><ChatDotRound /></el-icon>
            与AI对话修订
            <el-tag v-if="currentRevisionRound > 0" type="success" size="small" style="margin-left: 8px;">
              第 {{ currentRevisionRound }} 轮修订
            </el-tag>
          </h4>
        </div>
        <div class="chat-messages">
          <div v-if="revisionMessages.length === 0" class="empty-message">
            <el-empty description="请输入您的修改意见" />
          </div>
          <div v-for="(msg, idx) in revisionMessages" :key="idx" class="message-item">
            <div v-if="msg.role === 'user'" class="message user-message">
              <div class="message-avatar">用户</div>
              <div class="message-content">{{ msg.content }}</div>
            </div>
            <div v-else class="message ai-message">
              <div class="message-avatar">AI</div>
              <div class="message-content">
                <div v-if="msg.loading" class="loading-indicator">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <span>AI正在生成修订内容...</span>
                </div>
                <div v-else v-html="sanitizeHtml(msg.content)"></div>
              </div>
            </div>
          </div>
        </div>
        <div class="chat-input">
          <div v-if="uploadedFiles.length > 0" class="uploaded-files-list">
            <div v-for="(file, idx) in uploadedFiles" :key="idx" class="file-tag">
              <el-icon><Document /></el-icon>
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">({{ formatFileSize(file.size) }})</span>
              <el-icon class="remove-file" @click="removeUploadedFile(idx)"><Close /></el-icon>
            </div>
          </div>
          <el-input
            v-model="localRevisionInput"
            type="textarea"
            :rows="3"
            placeholder="请输入修改意见"
            :disabled="revising"
            @keyup.ctrl.enter="handleSubmitRevision"
          />
          <div class="input-actions">
            <div class="left-actions">
              <el-button text size="small" @click="fileInputRef?.click()">
                <el-icon><Paperclip /></el-icon>
                上传参考文件
              </el-button>
              <input
                ref="fileInputRef"
                type="file"
                multiple
                accept=".txt,.md,.doc,.docx"
                style="display: none"
                @change="handleFileSelect"
              />
              <el-text v-if="uploadedFiles.length > 0" type="success" size="small">
                已上传 {{ uploadedFiles.length }} 个文件
              </el-text>
            </div>
            <div class="right-actions">
              <el-button @click="handleExitRevision">
                <el-icon><Close /></el-icon>
                退出修订
              </el-button>
              <el-button
                type="primary"
                @click="handleSubmitRevision"
                :loading="revising"
                :disabled="!localRevisionInput.trim() && uploadedFiles.length === 0"
              >
                <el-icon><Promotion /></el-icon>
                提交修订意见
              </el-button>
            </div>
          </div>
        </div>
      </div>
      <div class="revision-preview">
        <div class="preview-header">
          <h4>
            <el-icon><Document /></el-icon>
            当前内容预览
          </h4>
        </div>
        <div class="preview-content">
          <div v-if="revisionContent" class="markdown-content" v-html="renderedRevisionContent"></div>
          <el-empty v-else description="暂无内容" />
        </div>
      </div>
    </div>
    <template #footer>
      <div class="revision-footer">
        <el-button @click="handleExitRevision">
          <el-icon><Close /></el-icon>
          退出修订
        </el-button>
        <el-button type="success" @click="handleFinalizeContent">
          <el-icon><Check /></el-icon>
          确认使用当前内容
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ChatDotRound, Loading, Document, Close, Paperclip, Promotion, Check } from '@element-plus/icons-vue'
import { ref } from 'vue'
import DOMPurify from 'dompurify'

const props = defineProps({
  visible: { type: Boolean, default: false },
  revisionContent: { type: String, default: '' },
  revisionMessages: { type: Array, default: () => [] },
  currentRevisionRound: { type: Number, default: 0 },
  revising: { type: Boolean, default: false },
  renderedRevisionContent: { type: String, default: '' },
  useTwoStageMode: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'submit-revision', 'exit-revision', 'finalize-content', 'file-select'])

/** 安全渲染HTML内容，防止XSS攻击 */
const sanitizeHtml = (html) => {
  if (!html) return ''
  return DOMPurify.sanitize(html)
}

const localRevisionInput = ref('')
const fileInputRef = ref(null)
const uploadedFiles = ref([])

function formatFileSize(bytes) {
  return (bytes / 1024).toFixed(1) + 'KB'
}

function handleSubmitRevision() {
  console.log('[RevisionDialog] 提交修订, localRevisionInput:', localRevisionInput.value)
  console.log('[RevisionDialog] 提交数据类型:', { input: localRevisionInput.value, files: uploadedFiles.value })
  
  emit('submit-revision', { input: localRevisionInput.value, files: uploadedFiles.value })
  localRevisionInput.value = ''
}

function handleExitRevision() {
  emit('exit-revision')
}

function handleFinalizeContent() {
  emit('finalize-content')
}

function handleFileSelect(event) {
  const files = Array.from(event.target.files || [])
  uploadedFiles.value = [...uploadedFiles.value, ...files]
  emit('file-select', files)
}

function removeUploadedFile(idx) {
  uploadedFiles.value.splice(idx, 1)
}
</script>
