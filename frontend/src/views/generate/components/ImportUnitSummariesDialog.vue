<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
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
        :action="uploadUrl"
        :before-upload="handleBeforeUpload"
        :on-success="handleSuccess"
        :on-error="handleError"
        :on-progress="handleProgress"
        :show-file-list="false"
        accept=".md,.txt,.docx,.doc"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .md、.txt、.docx 格式，文件大小不超过 100MB
          </div>
        </template>
      </el-upload>
      
      <div v-if="importing" class="import-progress">
        <el-progress :percentage="progress" />
        <span>正在上传并解析...</span>
      </div>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { InfoFilled, UploadFilled } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  uploadUrl: { type: String, default: '' },
  importing: { type: Boolean, default: false },
  progress: { type: Number, default: 0 }
})

const emit = defineEmits(['update:modelValue', 'before-upload', 'upload-success', 'upload-error', 'upload-progress'])

function handleBeforeUpload(file) {
  emit('before-upload', file)
}

function handleSuccess(response, file) {
  emit('upload-success', response, file)
}

function handleError(error, file) {
  emit('upload-error', error, file)
}

function handleProgress(event, file) {
  emit('upload-progress', event, file)
}
</script>
