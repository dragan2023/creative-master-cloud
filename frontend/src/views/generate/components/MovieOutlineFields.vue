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
      <el-form-item label="电影类型" prop="movie_type">
        <el-select v-model="form.movie_type" placeholder="选择电影类型" style="width: 100%" @change="$emit('movie-type-change', $event)">
          <el-option v-for="mt in movieTypes" :key="mt" :label="mt" :value="mt" />
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
      <el-form-item label="场次数" prop="scene_count">
        <el-input v-model="form.scene_count" placeholder="如：80场，留空AI自动估算" />
      </el-form-item>
    </el-col>
  </el-row>

  <!-- 电影专业配置 -->
  <el-divider content-position="left">电影专业配置</el-divider>
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="整片时长" prop="duration_range">
        <div style="display: flex; align-items: center; gap: 8px;">
          <el-input-number v-model="form.duration_range[0]" :min="1" :max="300" :step="5" style="width: 120px;" />
          <span style="margin: 0 8px; font-weight: 500;">-</span>
          <el-input-number v-model="form.duration_range[1]" :min="1" :max="300" :step="5" style="width: 120px;" />
          <span style="color: #909399; font-size: 12px; margin-left: 8px;">分钟</span>
        </div>
        <div v-if="movieDurationHint" class="form-tip">{{ movieDurationHint }}</div>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="场景数范围" prop="scene_count_range">
        <el-input v-model="form.scene_count_range" placeholder="如：80-150场，留空AI自动设计" />
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
          <el-option label="纪录片格式" value="纪录片格式" />
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
        <el-input v-model="form.reference_works" placeholder="填写对标作品名称，如《流浪地球》《哪吒之魔童降世》" />
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

  <!-- 电影风格选择器 -->
  <el-divider content-position="left">电影风格</el-divider>
  <el-form-item label="电影风格">
    <div class="style-selector-entry">
      <!-- 已选风格标签 -->
      <div v-if="selectedStyleSummary.length > 0" class="selected-styles-display">
        <el-tag
          v-for="item in selectedStyleSummary"
          :key="item.dimName"
          type="primary"
          size="small"
          closable
          @close="removeStyleFromDimension(item.dimName)"
        >
          {{ item.dimName }}: {{ item.styleName }}
        </el-tag>
        <span class="style-count-text">
          已选 {{ selectedStyleCount }} / 6 个维度
        </span>
      </div>
      <div v-else class="no-style-hint">
        <el-text type="info" size="small">从六大维度选择电影风格，为创作提供艺术指导</el-text>
      </div>
      <el-button
        type="primary"
        text
        size="small"
        @click="showStyleDialog = true"
      >
        <el-icon><Edit /></el-icon>
        {{ selectedStyleCount > 0 ? '修改风格' : '选择电影风格' }}
      </el-button>
    </div>
  </el-form-item>

  <!-- 电影风格选择对话框 -->
  <MovieStyleSelectorDialog
    v-model:visible="showStyleDialog"
    :initial-selected="movieStyleData"
    :initial-intensity="movieStyleData.intensity || 0.7"
    @confirm="handleMovieStyleConfirm"
  />
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Upload, Document, InfoFilled } from '@element-plus/icons-vue'
import { movieTypes, genres, platforms } from '../composables/useGenerationForm'
import MovieStyleSelectorDialog from './MovieStyleSelectorDialog.vue'

defineProps({
  form: {
    type: Object,
    required: true
  },
  movieDurationHint: {
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

const emit = defineEmits([
  'update:form',
  'movie-type-change',
  'outline-upload-success',
  'outline-upload-error',
  'outline-progress',
  'remove-outline',
  'update:style-data',  // 电影风格数据
  'update:title-style-data'  // 标题风格数据
])

// 电影风格选择器状态
const showStyleDialog = ref(false)
const movieStyleData = reactive({
  styleType: 'movie',
  dimensions: {},
  selectedNames: [],
  intensity: 0.7
})

const selectedStyleSummary = computed(() => {
  const summary = []
  for (const [dimName, styles] of Object.entries(movieStyleData.dimensions)) {
    if (styles && styles.length > 0) {
      summary.push({
        dimName,
        styleName: styles[0]?.name || String(styles[0] || '未知')
      })
    }
  }
  return summary
})

const selectedStyleCount = computed(() => selectedStyleSummary.value.length)

function handleMovieStyleConfirm(data) {
  Object.assign(movieStyleData, {
    styleType: data.styleType,
    dimensions: data.dimensions,
    selectedNames: data.selectedNames,
    intensity: data.intensity
  })
  emit('update:style-data', { ...movieStyleData })
}

function removeStyleFromDimension(dimName) {
  delete movieStyleData.dimensions[dimName]
  // 重新计算 selectedNames
  movieStyleData.selectedNames = []
  for (const [, styles] of Object.entries(movieStyleData.dimensions)) {
    if (styles && styles.length > 0) {
      movieStyleData.selectedNames.push(styles[0]?.name || String(styles[0] || '未知'))
    }
  }
  emit('update:style-data', { ...movieStyleData })
}

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

.style-selector-entry {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;

  .selected-styles-display {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;

    .style-count-text {
      font-size: 12px;
      color: #909399;
      margin-left: 4px;
    }
  }

  .no-style-hint {
    flex: 1;
  }
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
