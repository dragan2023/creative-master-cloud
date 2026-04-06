<!--
  单元概述上传对话框组件
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="上传单元概述"
    width="650px"
    destroy-on-close
  >
    <div class="unit-summaries-upload-dialog">
      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        <template #title>支持的格式</template>
        <div style="font-size: 13px">
          <p><strong>文件格式：</strong>TXT（纯文本）、Markdown（.md）、Word文档（.docx, .doc）</p>
          <p style="margin-top: 6px"><strong>内容要求：</strong></p>
          <ul style="margin: 4px 0; padding-left: 20px">
            <li>小说：包含章节标题（如 ### 第1章：xxx）和梗概内容</li>
            <li>剧集剧本：包含分集标题（如 ### 第1集：xxx）和梗概内容</li>
            <li>电影剧本：包含场景标题（如 **第1场：xxx）和梗概内容</li>
          </ul>
          <p style="margin-top: 6px; color: #909399">系统将自动识别章节结构并解析单元概述</p>
        </div>
      </el-alert>

      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        :on-change="handleFileChange"
        :on-exceed="handleExceed"
        :file-list="fileList"
        accept=".txt,.md,.docx,.doc"
        drag
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 .txt, .md, .docx, .doc 格式文件</div>
        </template>
      </el-upload>
    </div>
    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button
        type="primary"
        @click="handleConfirm"
        :loading="uploading"
        :disabled="fileList.length === 0"
      >
        确认上传
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  uploading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'upload', 'cancel'])

const fileList = ref([])
const uploadRef = ref(null)

watch(() => props.visible, (val) => {
  if (!val) {
    fileList.value = []
  }
})

function handleFileChange(file) {
  fileList.value = [file.raw]
}

function handleExceed() {
  ElMessage.warning('只能上传一个文件，请先移除当前文件')
}

function handleCancel() {
  fileList.value = []
  emit('update:visible', false)
  emit('cancel')
}

function handleConfirm() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  emit('upload', fileList.value[0])
}
</script>

<style lang="scss" scoped>
.unit-summaries-upload-dialog {
  .el-alert {
    p {
      margin: 4px 0;
      line-height: 1.5;
    }
  }

  .el-textarea {
    font-family: 'Courier New', Consolas, monospace;
  }
}
</style>
