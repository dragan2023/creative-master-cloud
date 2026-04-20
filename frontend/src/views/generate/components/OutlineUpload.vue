<template>
  <div class="outline-upload-wrapper">
    <el-upload
      :action="uploadUrl"
      :headers="uploadHeaders"
      :on-success="handleSuccess"
      :on-error="handleError"
      :on-progress="handleProgress"
      :before-upload="handleBeforeUpload"
      :show-file-list="false"
      accept=".txt,.md,.doc,.docx,.pdf"
      :disabled="uploading"
    >
      <el-button type="primary" text :loading="uploading">
        <el-icon v-if="!uploading"><Upload /></el-icon>
        {{ uploading ? '上传中...' : (modelValue.url ? '重新上传' : '上传大纲文件（可选）') }}
      </el-button>
    </el-upload>
    <!-- 上传进度 -->
    <div v-if="uploading" class="upload-progress">
      <el-progress :percentage="progress" :stroke-width="6" />
    </div>
    <!-- 已上传文件显示 -->
    <div v-if="modelValue.url && !uploading" class="uploaded-file-info">
      <el-tag type="success" closable @close="handleRemove">
        <el-icon><Document /></el-icon>
        {{ modelValue.name || '已上传文件' }}
      </el-tag>
    </div>
    <!-- Token 消耗提示 -->
    <div class="token-tip">
      <el-icon><InfoFilled /></el-icon>
      <span>支持 .txt, .md, .doc, .docx, .pdf 格式，文件大小不超过100MB</span>
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({ url: '', name: '' })
  },
  uploadUrl: {
    type: String,
    required: true
  },
  uploadHeaders: {
    type: Object,
    default: () => ({})
  },
  uploading: {
    type: Boolean,
    default: false
  },
  progress: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['update:modelValue', 'before-upload', 'progress', 'error', 'remove'])

const handleBeforeUpload = (file) => {
  const allowedExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf']
  const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedExtensions.includes(fileExtension)) {
    ElMessage.error('只支持上传 .txt, .md, .doc, .docx, .pdf 格式的文件！')
    return false
  }
  if (file.size / 1024 / 1024 > 100) {
    ElMessage.error('文件大小不能超过100MB！')
    return false
  }
  
  emit('before-upload', file)
  return true
}

const handleProgress = (event) => {
  emit('progress', event)
}

const handleSuccess = (response, file) => {
  if ((response.code === 0 || response.code === 200) && response.data?.url) {
    emit('update:modelValue', {
      url: response.data.url,
      name: file.name
    })
    ElMessage.success('大纲文件上传成功')
  } else {
    ElMessage.error(response.message || '上传失败')
    emit('error', new Error(response.message || '上传失败'))
  }
}

const handleError = (error) => {
  ElMessage.error('大纲文件上传失败：' + (error.message || '未知错误'))
  emit('error', error)
}

const handleRemove = () => {
  emit('update:modelValue', { url: '', name: '' })
  emit('remove')
}
</script>

<style lang="scss" scoped>
.outline-upload-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
  
  .upload-progress {
    width: 100%;
    max-width: 300px;
  }
  
  .uploaded-file-info {
    display: flex;
    align-items: center;
    
    .el-tag {
      display: flex;
      align-items: center;
      gap: 4px;
      
      .el-icon {
        margin-right: 4px;
      }
    }
  }
  
  .token-tip {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 4px;
    font-size: 12px;
    color: #909399;
    
    .el-icon {
      font-size: 14px;
    }
  }
}
</style>
