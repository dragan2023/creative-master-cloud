<!--
  大纲上传对话框组件
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="上传大纲"
    width="600px"
    destroy-on-close
  >
    <div class="outline-upload-content">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
        <template #title>支持的格式</template>
        <p style="margin: 4px 0">TXT（纯文本）、Markdown（.md）、JSON（结构化大纲）</p>
      </el-alert>

      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        :on-change="handleFileChange"
        accept=".txt,.md,.json"
        drag
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
      </el-upload>

      <el-divider>或直接输入内容</el-divider>

      <el-form label-width="80px">
        <el-form-item label="大纲内容">
          <el-input
            v-model="outlineContent"
            type="textarea"
            :rows="10"
            placeholder="请粘贴大纲内容..."
          />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button
        type="primary"
        @click="handleConfirm"
        :loading="uploading"
        :disabled="!outlineContent.trim()"
      >
        确认上传
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Upload } from '@element-plus/icons-vue'

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

const emit = defineEmits(['update:visible', 'upload'])

const outlineContent = ref('')
const uploadRef = ref(null)

watch(() => props.visible, (val) => {
  if (!val) {
    outlineContent.value = ''
  }
})

function handleFileChange(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    outlineContent.value = e.target.result
  }
  reader.readAsText(file.raw)
}

function handleConfirm() {
  emit('upload', outlineContent.value)
}
</script>

<style lang="scss" scoped>
.outline-upload-content {
  .el-alert p {
    margin: 4px 0;
  }
}
</style>
