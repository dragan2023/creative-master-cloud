<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="导入已有大纲"
    width="700px"
    :close-on-click-modal="false"
  >
    <div class="import-dialog-content">
      <el-radio-group 
        :model-value="importType" 
        @update:model-value="$emit('update:importType', $event)"
        class="import-type-selector"
      >
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
          :action="uploadUrl"
          :headers="uploadHeaders"
          :before-upload="handleBeforeUpload"
          :on-success="handleSuccess"
          :on-error="handleError"
          :on-progress="handleProgress"
          :show-file-list="true"
          :limit="1"
          accept=".md,.txt,.docx,.doc"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
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
          v-if="importing"
          :percentage="progress"
          :stroke-width="4"
          class="upload-progress"
        />
      </div>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { InfoFilled, UploadFilled } from '@element-plus/icons-vue'

defineProps({
  modelValue: { type: Boolean, default: false },
  importType: { type: String, default: 'global' },
  uploadUrl: { type: String, default: '' },
  uploadHeaders: { type: Object, default: () => ({}) },
  importing: { type: Boolean, default: false },
  progress: { type: Number, default: 0 }
})

const emit = defineEmits(['update:modelValue', 'update:importType', 'before-upload', 'upload-success', 'upload-error', 'upload-progress'])

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
