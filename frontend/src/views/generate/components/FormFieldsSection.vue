<template>
  <div class="form-section">
    <h3>基本信息</h3>
    
    <el-form-item label="标题/主题" prop="title">
      <el-input
        v-model="form.title"
        placeholder="请输入创意标题或主题"
      />
    </el-form-item>
    
    <el-form-item v-if="type !== 'print-ad' && type !== 'tvc' && type !== 'practical-writing'" label="目标受众" prop="target_audience">
      <el-input
        v-model="form.target_audience"
        placeholder="如：18-25岁年轻人"
      />
    </el-form-item>
  </div>
  
  <div class="form-section">
    <h3>内容要求</h3>
    
    <!-- 原创IP计划模块不显示此字段，使用独立的ip_description字段 -->
    <el-form-item v-if="type !== 'original-ip'" :label="type === 'novel' || type === 'movie-outline' || type === 'series-outline' ? '故事梗概' : '详细描述'" prop="description">
      <div class="description-input-wrapper">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="4"
          :placeholder="type === 'movie-outline' ? '请描述电影的故事梗概，包括世界观、主线剧情、人物关系等' : type === 'series-outline' ? '请描述剧集的故事梗概，包括世界观、主线剧情、人物关系等' : type === 'novel' ? '请描述小说的故事梗概，包括世界观、主线剧情、人物关系等' : '请详细描述您的创意需求，包括背景、目标、关键元素等'"
        />
        <!-- 优化按钮 -->
        <div class="optimize-actions">
          <el-button 
            type="primary" 
            text
            :loading="optimizing && optimizeTarget === 'description'"
            :disabled="!form.description || form.description.length < 5"
            @click="$emit('optimize', 'description')"
          >
            <el-icon><MagicStick /></el-icon>
            {{ optimizing && optimizeTarget === 'description' ? '优化中...' : '优化输入' }}
          </el-button>
          <span class="optimize-tip" v-if="form.description && form.description.length < 5">
            请至少输入5个字符
          </span>
        </div>
      </div>
    </el-form-item>
    
    <!-- ========== 短视频模块特殊字段 ========== -->
    <template v-if="type === 'short-video'">
      <ShortVideoFields
        :form="form"
        :optimizing="optimizing"
        :optimize-target="optimizeTarget"
        :upload-url="uploadUrl"
        :upload-headers="uploadHeaders"
        :uploading-reference-materials="uploadingReferenceMaterials"
        :reference-materials-upload-progress="referenceMaterialsUploadProgress"
        @update:form="$emit('update:form', $event)"
        @optimize="$emit('optimize', $event)"
        @upload-success="$emit('reference-upload-success', $event)"
        @upload-error="$emit('reference-upload-error', $event)"
        @remove-file="$emit('remove-reference-file')"
      />
    </template>
    
    <!-- ========== 电影大纲模块 ========== -->
    <template v-if="type === 'movie-outline'">
      <MovieOutlineFields
        :form="form"
        :movie-duration-hint="movieDurationHint"
        :upload-url="uploadUrl"
        :upload-headers="uploadHeaders"
        :uploading-outline="uploadingOutline"
        :outline-upload-progress="outlineUploadProgress"
        @update:form="$emit('update:form', $event)"
        @movie-type-change="$emit('movie-type-change', $event)"
        @outline-upload-success="$emit('outline-upload-success', $event)"
        @outline-upload-error="$emit('outline-upload-error', $event)"
        @outline-progress="$emit('outline-progress', $event)"
        @remove-outline="$emit('remove-outline')"
        @update:style-data="$emit('update:style-data', $event)"
        @update:title-style-data="$emit('update:title-style-data', $event)"
      />
    </template>
    
    <!-- ========== 剧集大纲模块 ========== -->
    <template v-if="type === 'series-outline'">
      <SeriesOutlineFields
        :form="form"
        :series-episode-duration-hint="seriesEpisodeDurationHint"
        :upload-url="uploadUrl"
        :upload-headers="uploadHeaders"
        :uploading-outline="uploadingOutline"
        :outline-upload-progress="outlineUploadProgress"
        @update:form="$emit('update:form', $event)"
        @series-outline-type-change="$emit('series-outline-type-change', $event)"
        @outline-upload-success="$emit('outline-upload-success', $event)"
        @outline-upload-error="$emit('outline-upload-error', $event)"
        @outline-progress="$emit('outline-progress', $event)"
        @remove-outline="$emit('remove-outline')"
        @update:style-data="$emit('update:style-data', $event)"
        @update:title-style-data="$emit('update:title-style-data', $event)"
      />
    </template>
    
    <!-- ========== 小说模块 ========== -->
    <template v-if="type === 'novel'">
      <NovelFields
        ref="novelFieldsRef"
        :form="form"
        :upload-url="uploadUrl"
        :upload-headers="uploadHeaders"
        :uploading-outline="uploadingOutline"
        :outline-upload-progress="outlineUploadProgress"
        @update:form="$emit('update:form', $event)"
        @outline-upload-success="$emit('outline-upload-success', $event)"
        @outline-upload-error="$emit('outline-upload-error', $event)"
        @outline-progress="$emit('outline-progress', $event)"
        @remove-outline="$emit('remove-outline')"
        @update:style-data="handleStyleDataUpdate"
        @update:title-style-data="$emit('update:title-style-data', $event)"
      />
    </template>
    
    <!-- ========== 平面设计模块 ========== -->
    <template v-if="type === 'print-ad'">
      <PrintAdFields
        :form="form"
        :optimizing="optimizing"
        :optimize-target="optimizeTarget"
        :upload-url="uploadUrl"
        :upload-headers="uploadHeaders"
        :image-file-list="imageFileList"
        :image-url-input="imageUrlInput"
        @update:form="$emit('update:form', $event)"
        @update:imageUrlInput="$emit('update:imageUrlInput', $event)"
        @optimize="$emit('optimize', $event)"
        @upload-success="$emit('image-upload-success', $event)"
        @upload-error="$emit('image-upload-error', $event)"
        @parse-image-urls="$emit('parse-image-urls')"
      />
    </template>
    
    <!-- ========== TVC广告模块 ========== -->
    <template v-if="type === 'tvc'">
      <TvcFields
        :form="form"
        :optimizing="optimizing"
        :optimize-target="optimizeTarget"
        @update:form="$emit('update:form', $event)"
        @optimize="$emit('optimize', $event)"
      />
    </template>
    
    <!-- ========== 原创IP计划模块 ========== -->
    <template v-if="type === 'original-ip'">
      <OriginalIpFields
        :form="form"
        :optimizing="optimizing"
        :optimize-target="optimizeTarget"
        @update:form="$emit('update:form', $event)"
        @optimize="$emit('optimize', $event)"
      />
    </template>
    
    <!-- ========== 应用文写作模块 ========== -->
    <template v-if="type === 'practical-writing'">
      <PracticalWritingFields
        :form="form"
        :optimizing="optimizing"
        :optimize-target="optimizeTarget"
        :upload-url="uploadUrl"
        :upload-headers="uploadHeaders"
        :uploading-ref-doc="uploadingRefDoc"
        :ref-doc-upload-progress="refDocUploadProgress"
        @update:form="$emit('update:form', $event)"
        @optimize="$emit('optimize', $event)"
        @ref-doc-upload-success="$emit('ref-doc-upload-success', $event)"
        @ref-doc-upload-error="$emit('ref-doc-upload-error', $event)"
        @ref-doc-progress="$emit('ref-doc-progress', $event)"
        @remove-ref-doc="$emit('remove-ref-doc')"
      />
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { MagicStick } from '@element-plus/icons-vue'
import ShortVideoFields from './ShortVideoFields.vue'
import ScriptFields from './ScriptFields.vue'
import MovieOutlineFields from './MovieOutlineFields.vue'
import SeriesOutlineFields from './SeriesOutlineFields.vue'
import NovelFields from './NovelFields.vue'
import PrintAdFields from './PrintAdFields.vue'
import TvcFields from './TvcFields.vue'
import OriginalIpFields from './OriginalIpFields.vue'
import PracticalWritingFields from './PracticalWritingFields.vue'

// NovelFields组件引用
const novelFieldsRef = ref(null)

const emit = defineEmits([
  'update:form',
  'update:imageUrlInput',
  'update:style-data',  // 文风数据
  'update:title-style-data',  // 标题风格数据
  'optimize',
  'series-type-change',
  'movie-type-change',  // 电影类型变化
  'series-outline-type-change',  // 剧集大纲类型变化
  'outline-upload-success',
  'outline-upload-error',
  'outline-progress',
  'remove-outline',
  'reference-upload-success',
  'reference-upload-error',
  'remove-reference-file',
  'ref-doc-upload-success',
  'ref-doc-upload-error',
  'ref-doc-progress',
  'remove-ref-doc',
  'image-upload-success',
  'image-upload-error',
  'parse-image-urls'
])

// 文风数据更新处理
function handleStyleDataUpdate(styleData) {
  console.log('[FormFieldsSection] 文风数据更新:', styleData)
  // 向上传递到GenerateForm
  emit('update:styleData', styleData)
}

const props = defineProps({
  form: {
    type: Object,
    required: true
  },
  type: {
    type: String,
    required: true
  },
  optimizing: {
    type: Boolean,
    default: false
  },
  optimizeTarget: {
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
  },
  uploadingReferenceMaterials: {
    type: Boolean,
    default: false
  },
  referenceMaterialsUploadProgress: {
    type: Number,
    default: 0
  },
  uploadingRefDoc: {
    type: Boolean,
    default: false
  },
  refDocUploadProgress: {
    type: Number,
    default: 0
  },
  seriesDurationHint: {
    type: String,
    default: ''
  },
  movieDurationHint: {
    type: String,
    default: ''
  },
  seriesEpisodeDurationHint: {
    type: String,
    default: ''
  },
  imageFileList: {
    type: Array,
    default: () => []
  },
  imageUrlInput: {
    type: String,
    default: ''
  }
})
</script>

<style lang="scss" scoped>
.form-section {
  margin-bottom: 28px;
  
  &:last-child {
    margin-bottom: 0;
  }
  
  h3 {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 2px solid rgba(64, 158, 255, 0.1);
    display: flex;
    align-items: center;
    gap: 10px;
    
    &::before {
      content: '';
      width: 4px;
      height: 18px;
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 2px;
    }
  }
}

.description-input-wrapper {
  width: 100%;
  
  .optimize-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 8px;
    padding-top: 8px;
    
    .el-button {
      padding: 4px 8px;
      font-size: 13px;
      
      .el-icon {
        margin-right: 4px;
      }
    }
    
    .optimize-tip {
      font-size: 12px;
      color: #e6a23c;
    }
  }
}
</style>
