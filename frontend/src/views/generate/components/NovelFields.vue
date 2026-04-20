<template>
  <!-- 第一行：篇幅与目标平台 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="篇幅体量" prop="length">
        <el-select v-model="form.length" placeholder="选择篇幅" style="width: 100%">
          <el-option label="长篇（50万字+）" value="long" />
          <el-option label="中篇（10-50万字）" value="medium" />
          <el-option label="短篇（10万字内）" value="short" />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="目标读者/平台" prop="target_platform">
        <el-select v-model="form.target_platform" placeholder="选择目标平台" style="width: 100%">
          <el-option label="网文平台-起点" value="起点" />
          <el-option label="网文平台-晋江" value="晋江" />
          <el-option label="网文平台-番茄" value="番茄" />
          <el-option label="实体出版" value="实体出版" />
          <el-option label="纯个人创作" value="纯个人创作" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第三行：标题风格选择器 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="标题风格（可选）">
        <div class="title-style-selector-wrapper">
          <div class="selector-header">
            <div class="style-info">
              <el-tag v-if="titleStyleName" type="warning" size="small" style="margin-right: 8px;">
                已选: {{ titleStyleName }}
              </el-tag>
              <el-text type="info" size="small" v-else>
                选择章节标题的命名风格（可选）
              </el-text>
            </div>
            <el-button type="primary" text size="small" @click="showTitleStyleSelector = true">
              <el-icon><Edit /></el-icon>
              {{ titleStyleName ? '修改' : '选择' }}
            </el-button>
          </div>
        </div>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第四行：写作风格选择器 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="写作风格（可选）">
        <div class="style-selector-wrapper">
          <div class="style-selector-header">
            <div class="style-info">
              <el-tag v-if="styleData.styleNames.length > 0" type="success" size="small" style="margin-right: 8px;">
                已选 {{ styleData.styleNames.length }} 种
              </el-tag>
              <el-text type="info" size="small" v-else>
                从61种经典文风中选择1-3种进行融合（可选）
              </el-text>
            </div>
            <el-button type="primary" text size="small" @click="showStyleSelector = true">
              <el-icon><Edit /></el-icon>
              {{ styleData.styleNames.length > 0 ? '修改文风' : '选择文风' }}
            </el-button>
          </div>
          
          <!-- 已选文风展示 -->
          <div v-if="styleData.styleNames.length > 0" class="selected-styles-display">
            <el-tag
              v-for="(name, idx) in styleData.styleNames"
              :key="idx"
              :type="idx === 0 ? 'primary' : 'success'"
              size="small"
              style="margin-right: 8px; margin-bottom: 4px;"
            >
              {{ idx === 0 ? '主' : '辅' }} · {{ name }}
            </el-tag>
            <el-text type="info" size="small" style="margin-left: 8px;">
              强度: {{ Math.round(styleData.intensity * 100) }}%
            </el-text>
          </div>
        </div>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第五行：章节数 + 自写大纲 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="章节数" prop="chapter_count">
        <el-input v-model="form.chapter_count" placeholder="如：100章、200章，自定义填写" />
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
  
  <!-- 文风选择器对话框 -->
  <StyleSelectorDialog
    v-model:visible="showStyleSelector"
    :initial-style-ids="styleData.styleIds"
    :initial-intensity="styleData.intensity"
    @confirm="handleStyleSelectionConfirm"
  />
  
  <!-- 标题风格选择器对话框 -->
  <TitleStyleSelectorDialog
    v-model:visible="showTitleStyleSelector"
    :initial-style-id="titleStyle"
    @confirm="handleTitleStyleConfirm"
  />
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Upload, Document, InfoFilled } from '@element-plus/icons-vue'
import StyleSelectorDialog from '@/views/novel-writer/components/StyleSelectorDialog.vue'
import TitleStyleSelectorDialog from './TitleStyleSelectorDialog.vue'

const props = defineProps({
  form: {
    type: Object,
    required: true
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
  'outline-upload-success',
  'outline-upload-error',
  'outline-progress',
  'remove-outline',
  'update:styleData',  // 传递文风数据
  'update:titleStyleData'  // 传递标题风格数据
])

// 文风选择器相关
const showStyleSelector = ref(false)
const styleData = reactive({
  styleIds: [],
  styleNames: [],
  intensity: 0.7,
  styleGuide: null  // 融合后的风格指南
})

// 标题风格选择器相关
const showTitleStyleSelector = ref(false)
const titleStyle = ref('')
const titleStyleName = ref('')

/**
 * 处理文风选择确认
 */
function handleStyleSelectionConfirm(data) {
  styleData.styleIds = data.styleIds || []
  styleData.styleNames = data.styleNames || []
  styleData.intensity = data.intensity || 0.7
  styleData.styleGuide = data.styleGuide
  
  emit('update:styleData', styleData)
  
  ElMessage.success(`已选择 ${styleData.styleNames.length} 种文风: ${styleData.styleNames.join(' + ')}`)
  
  console.log('[NovelFields] 文风配置:', {
    styleIds: styleData.styleIds,
    styleNames: styleData.styleNames,
    intensity: styleData.intensity,
    styleGuide: styleData.styleGuide
  })
}

/**
 * 处理标题风格选择确认
 */
function handleTitleStyleConfirm(data) {
  titleStyle.value = data.styleId || ''
  titleStyleName.value = data.styleName || ''
  
  emit('update:titleStyleData', { 
    styleId: titleStyle.value, 
    styleName: titleStyleName.value 
  })
  
  console.log('[NovelFields] 标题风格配置:', {
    styleId: titleStyle.value,
    styleName: titleStyleName.value
  })
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

// 暴露styleData和titleStyle给父组件
defineExpose({
  styleData,
  titleStyle,
  titleStyleName
})
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

.style-selector-wrapper {
  width: 100%;
  
  .selector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    
    .style-info {
      flex: 1;
    }
  }
  
  .selected-styles-display {
    padding: 8px 12px;
    background: rgba(64, 158, 255, 0.05);
    border-radius: 6px;
    border: 1px solid rgba(64, 158, 255, 0.15);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
  }
}

.title-style-selector-wrapper {
  width: 100%;
  
  .selector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    
    .style-info {
      flex: 1;
    }
  }
}
</style>
