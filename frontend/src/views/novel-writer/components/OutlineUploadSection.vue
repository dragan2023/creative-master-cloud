<template>
  <div class="outline-upload-section" v-if="!project?.outline_content">
    <el-upload
      ref="uploadRef"
      :auto-upload="false"
      :limit="1"
      accept=".txt,.md,.docx"
      :on-change="handleFileChange"
      :on-exceed="() => ElMessage.warning('只能上传一个文件')"
    >
      <el-button type="primary" :icon="UploadFilled">上传大纲文件</el-button>
      <template #tip>
        <div class="upload-tip">支持 .txt, .md, .docx 格式</div>
      </template>
    </el-upload>

    <el-divider>或</el-divider>

    <div class="directory-gen">
      <span>生成目录结构</span>
      <el-input-number v-model="unitCount" :min="1" :max="200" size="small" style="width: 120px;" />
      <el-button type="primary" size="small" :loading="loading" @click="handleGenerateDirectory">
        生成
      </el-button>
    </div>
  </div>

  <div class="outline-uploaded" v-else>
    <el-tag type="success" :icon="CircleCheckFilled">大纲已上传</el-tag>
    <el-button size="small" @click="handleReupload">更换大纲</el-button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, CircleCheckFilled } from '@element-plus/icons-vue'

const props = defineProps({
  project: { type: Object, default: null },
  chapters: { type: Array, default: () => [] },
  unitLabel: { type: String, default: '章节' },
  loading: { type: Boolean, default: false },
  unitCount: { type: Number, default: 10 },
  onUpload: { type: Function, default: null },
  onGenerateDirectory: { type: Function, default: null }
})

const emit = defineEmits(['update:unitCount'])
const uploadRef = ref(null)
const unitCount = ref(props.unitCount)

watch(() => props.unitCount, (val) => { unitCount.value = val })
watch(unitCount, (val) => { emit('update:unitCount', val) })

const selectedFile = ref(null)

const handleFileChange = (file) => {
  selectedFile.value = file
  if (props.onUpload) props.onUpload(file)
}

const handleGenerateDirectory = () => {
  if (props.onGenerateDirectory) props.onGenerateDirectory(unitCount.value)
}

const handleReupload = () => {
  if (props.onUpload) props.onUpload(null)
}
</script>

<style lang="scss" scoped>
.outline-upload-section {
  padding: 16px 0;

  .upload-tip {
    font-size: 12px;
    color: #999;
  }

  .directory-gen {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.outline-uploaded {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}
</style>
