<template>
  <!-- 生成模式选择 -->
  <el-form-item label="剧本模式">
    <el-radio-group v-model="form.script_mode">
      <el-radio value="real">
        <span>现实模式</span>
        <el-tag size="small" type="info" style="margin-left: 4px;">真人拍摄</el-tag>
      </el-radio>
      <el-radio value="virtual">
        <span>虚拟模式</span>
        <el-tag size="small" type="success" style="margin-left: 4px;">AI视频生成</el-tag>
      </el-radio>
    </el-radio-group>
    <div class="form-tip">
      <el-text type="info" size="small">虚拟模式将简化分镜复杂度，更适合AI视频生成</el-text>
    </div>
  </el-form-item>
  
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="剧集类型" prop="series_type">
        <el-select v-model="form.series_type" placeholder="选择剧集类型" style="width: 100%" @change="$emit('series-type-change', $event)">
          <el-option v-for="st in seriesTypes" :key="st" :label="st" :value="st" />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="题材类型" prop="genre">
        <el-select v-model="form.genre" placeholder="选择题材" style="width: 100%">
          <el-option v-for="g in genres" :key="g" :label="g" :value="g" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="投放平台" prop="platform">
        <el-select v-model="form.platform" placeholder="选择投放平台" style="width: 100%">
          <el-option v-for="p in platforms" :key="p" :label="p" :value="p" />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="集数" prop="episode_count">
        <el-input v-model="form.episode_count" placeholder="如：24集、40集，自定义填写" />
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 剧本专业配置 -->
  <el-divider content-position="left">剧本专业配置</el-divider>
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="每集时长" prop="episode_duration_range">
        <div style="display: flex; align-items: center; gap: 8px;">
          <el-input-number v-model="form.episode_duration_range[0]" :min="1" :max="120" :step="5" style="width: 120px;" />
          <span style="margin: 0 8px; font-weight: 500;">-</span>
          <el-input-number v-model="form.episode_duration_range[1]" :min="1" :max="120" :step="5" style="width: 120px;" />
          <span style="color: #909399; font-size: 12px; margin-left: 8px;">分钟</span>
        </div>
        <div v-if="seriesDurationHint" class="form-tip">{{ seriesDurationHint }}</div>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="场景数/集" prop="scenes_per_episode_range">
        <el-input v-model="form.scenes_per_episode_range" placeholder="如：10-20场，留空AI自动设计" />
      </el-form-item>
    </el-col>
  </el-row>
  
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="剧本格式" prop="format_standard">
        <el-select v-model="form.format_standard" placeholder="选择格式标准" style="width: 100%">
          <el-option label="标准格式" value="标准格式" />
          <el-option label="简格式" value="简格式" />
          <el-option label="网络平台格式" value="网络平台格式" />
          <el-option label="短剧格式" value="短剧格式" />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="对白比例" prop="dialogue_narration_ratio">
        <el-select v-model="form.dialogue_narration_ratio" placeholder="选择对白比例" style="width: 100%">
          <el-option label="对话为主" value="对话为主" />
          <el-option label="均衡" value="均衡" />
          <el-option label="叙述为主" value="叙述为主" />
          <el-option label="动作导向" value="动作导向" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="对标作品" prop="reference_works">
        <el-input v-model="form.reference_works" placeholder="填写对标作品名称，如《狂飙》《隐秘的角落》" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="自写大纲" prop="custom_outline_file">
        <div class="outline-upload-wrapper">
          <el-upload
            :action="uploadUrl"
            :headers="uploadHeaders"
            :on-success="(res, file) => $emit('outline-upload-success', { response: res, file })"
            :on-error="(err, file) => $emit('outline-upload-error', { error: err, file })"
            :on-progress="(event) => $emit('outline-progress', event)"
            :before-upload="beforeOutlineUpload"
            :show-file-list="false"
            accept=".txt,.md,.doc,.docx,.pdf"
            :disabled="uploadingOutline"
          >
            <el-button type="primary" text :loading="uploadingOutline">
              <el-icon v-if="!uploadingOutline"><Upload /></el-icon>
              {{ uploadingOutline ? '上传中...' : (form.custom_outline ? '重新上传' : '上传大纲文件（可选）') }}
            </el-button>
          </el-upload>
          <!-- 上传进度 -->
          <div v-if="uploadingOutline" class="upload-progress">
            <el-progress :percentage="outlineUploadProgress" :stroke-width="6" />
          </div>
          <!-- 已上传文件显示 -->
          <div v-if="form.custom_outline && !uploadingOutline" class="uploaded-file-info">
            <el-tag type="success" closable @close="$emit('remove-outline')">
              <el-icon><Document /></el-icon>
              {{ form.custom_outline_name || '已上传文件' }}
            </el-tag>
          </div>
          <!-- Token 消耗提示 -->
          <div class="token-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>文件字符数量越多，消耗的token越多</span>
          </div>
        </div>
      </el-form-item>
    </el-col>
  </el-row>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { Upload, Document, InfoFilled } from '@element-plus/icons-vue'
import { seriesTypes, genres, platforms } from '../composables/useGenerationForm'

defineProps({
  form: {
    type: Object,
    required: true
  },
  seriesDurationHint: {
    type: String,
    default: ''
  },
  uploadUrl: {
    type: String,
    required: true
  },
  uploadHeaders: {
    type: Object,
    required: true
  },
  uploadingOutline: {
    type: Boolean,
    default: false
  },
  outlineUploadProgress: {
    type: Number,
    default: 0
  }
})

defineEmits([
  'update:form',
  'series-type-change',
  'outline-upload-success',
  'outline-upload-error',
  'outline-progress',
  'remove-outline'
])

// 上传前验证（大纲文件）
const beforeOutlineUpload = (file) => {
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
  return true
}
</script>

<style lang="scss" scoped>
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}

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
