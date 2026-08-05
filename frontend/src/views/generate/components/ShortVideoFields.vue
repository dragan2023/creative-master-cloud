<template>
  <!-- 生成模式选择（置顶） -->
  <el-form-item label="生成模式">
    <el-radio-group v-model="form.video_mode" @change="handleVideoModeChange">
      <el-radio value="real">
        <span>现实模式</span>
        <el-tag size="small" type="info" style="margin-left: 4px;">真人拍摄</el-tag>
      </el-radio>
      <el-radio value="virtual">
        <span>虚拟模式</span>
        <el-tag size="small" type="success" style="margin-left: 4px;">AI生成</el-tag>
      </el-radio>
    </el-radio-group>
    <div class="form-tip">
      <span v-if="form.video_mode === 'real'">现实模式：生成详细分镜拍摄脚本，适合真人演绎拍摄</span>
      <span v-else>虚拟模式：生成简洁分镜剧情描述，适合AI视频生成流程</span>
    </div>
  </el-form-item>
  
  <el-row :gutter="20">
    <el-col :span="8">
      <el-form-item label="视频时长" prop="duration">
        <el-input
          v-model="form.duration"
          placeholder="如：15秒、30秒、60秒、3分钟"
        />
      </el-form-item>
    </el-col>
    <el-col :span="8">
      <el-form-item label="目标平台" prop="platform">
        <el-select v-model="form.platform" placeholder="选择平台" style="width: 100%">
          <el-option label="抖音" value="douyin" />
          <el-option label="快手" value="kuaishou" />
          <el-option label="视频号" value="weixin" />
          <el-option label="B站" value="bilibili" />
          <el-option label="小红书" value="xiaohongshu" />
          <el-option label="YouTube Shorts" value="youtube" />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="8">
      <el-form-item label="画幅尺寸" prop="aspect_ratio">
        <el-select v-model="form.aspect_ratio" placeholder="选择画幅比例" style="width: 100%" allow-create filterable>
          <el-option label="9:16 竖屏（抖音/快手/视频号）" value="9:16" />
          <el-option label="16:9 横屏" value="16:9" />
          <el-option label="1:1 方形" value="1:1" />
          <el-option label="3:4 竖屏" value="3:4" />
          <el-option label="4:3 横屏" value="4:3" />
          <el-option label="21:9 超宽屏" value="21:9" />
        </el-select>
        <div class="form-tip">如：9:16竖屏、16:9横屏，可自定义输入</div>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 风格类型（多选两级）- 直观一览式选择 -->
  <StyleSelector v-model="styleTypesValue" />
  
  <!-- AI视频生成提示（仅虚拟模式显示） -->
  <el-form-item v-if="form.video_mode === 'virtual'" label="生成AI视频提示">
    <el-radio-group v-model="form.generate_ai_prompt">
      <el-radio :value="true">是</el-radio>
      <el-radio :value="false">否</el-radio>
    </el-radio-group>
    <span class="form-tip">选择"是"将额外生成适用于AI视频生成平台的提示词</span>
  </el-form-item>
  
  <el-form-item v-if="form.video_mode === 'virtual' && form.generate_ai_prompt" label="AI视频生成平台">
    <el-checkbox-group v-model="form.ai_platforms">
      <el-checkbox label="Seedance 2.0">Seedance 2.0</el-checkbox>
      <el-checkbox label="MiniMax H3">MiniMax H3</el-checkbox>
    </el-checkbox-group>
    <div class="form-tip" style="display: block; margin-left: 0; margin-top: 4px;">两款模型均支持多模态参考：上传人物/场景/物品参考图与音频素材，可提升生成一致性</div>
  </el-form-item>
  
  <!-- 分镜图提示词（仅虚拟模式显示） -->
  <el-form-item v-if="form.video_mode === 'virtual'" label="生成分镜图提示词">
    <el-radio-group v-model="form.generate_storyboard_images">
      <el-radio :value="true">是</el-radio>
      <el-radio :value="false">否</el-radio>
    </el-radio-group>
    <span class="form-tip">为每个分镜生成AI绘图提示词，用于制作参考图</span>
  </el-form-item>
  
  <!-- 参考视频URL -->
  <el-form-item prop="reference_video">
    <template #label>
      <span>参考视频</span>
      <el-tag type="warning" size="small" style="margin-left: 8px;">仅支持多模态模型</el-tag>
    </template>
    <el-input
      v-model="form.reference_video"
      placeholder="输入参考视频URL（可选）"
    />
    <div class="form-tip">URL需要资料直链，推荐使用图床网站获取直链</div>
  </el-form-item>
  
  <!-- 参考资料上传 -->
  <el-form-item prop="reference_materials_file">
    <template #label>
      <span>参考资料</span>
      <el-tooltip content="上传包含创作参考素材的文本文件，AI将参考这些内容生成脚本" placement="top">
        <el-icon style="margin-left: 4px; cursor: help;"><QuestionFilled /></el-icon>
      </el-tooltip>
    </template>
    <div class="outline-upload-wrapper">
      <el-upload
        :action="uploadUrl"
        :headers="uploadHeaders"
        :on-success="(res, file) => $emit('upload-success', { response: res, file })"
        :on-error="(err, file) => $emit('upload-error', { error: err, file })"
        :before-upload="beforeReferenceMaterialsUpload"
        :show-file-list="false"
        accept=".txt,.md,.doc,.docx,.pdf"
        :disabled="uploadingReferenceMaterials"
      >
        <el-button type="primary" text :loading="uploadingReferenceMaterials">
          <el-icon v-if="!uploadingReferenceMaterials"><Upload /></el-icon>
          {{ uploadingReferenceMaterials ? '上传中...' : (form.reference_materials ? '重新上传' : '上传参考资料（可选）') }}
        </el-button>
      </el-upload>
      <!-- 上传进度 -->
      <div v-if="uploadingReferenceMaterials" class="upload-progress">
        <el-progress :percentage="referenceMaterialsUploadProgress" :stroke-width="6" />
      </div>
      <!-- 已上传文件显示 -->
      <div v-if="form.reference_materials && !uploadingReferenceMaterials" class="uploaded-file-info">
        <el-tag type="success" closable @close="$emit('remove-file')">
          <el-icon><Document /></el-icon>
          {{ form.reference_materials_name || '已上传文件' }}
        </el-tag>
      </div>
      <!-- Token 消耗提示 -->
      <div class="token-tip">
        <el-icon><InfoFilled /></el-icon>
        <span>支持 .txt, .md, .doc, .docx, .pdf 格式，文件内容将作为AI创作的参考素材</span>
      </div>
    </div>
  </el-form-item>
  
  <!-- 运营相关变量 -->
  <el-divider content-position="left">运营设置（自定义变量）</el-divider>
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="账号调性" prop="account_tone">
        <el-input
          v-model="form.account_tone"
          placeholder="如：专业干货型、搞笑娱乐型、情感治愈型"
        />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="目标粉丝群体" prop="target_fans">
        <el-input
          v-model="form.target_fans"
          placeholder="如：18-25岁女性、职场白领、宝妈群体"
        />
      </el-form-item>
    </el-col>
  </el-row>
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="内容定位" prop="content_position">
        <el-input
          v-model="form.content_position"
          placeholder="如：知识科普、生活记录、好物推荐、情感分享、技能教学等"
        />
      </el-form-item>
    </el-col>
  </el-row>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import StyleSelector from './StyleSelector.vue'

const props = defineProps({
  form: {
    type: Object,
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
  uploadingReferenceMaterials: {
    type: Boolean,
    default: false
  },
  referenceMaterialsUploadProgress: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits([
  'update:form',
  'optimize',
  'upload-success',
  'upload-error',
  'remove-file'
])

// 风格类型值映射
const styleTypesValue = computed({
  get: () => ({
    level1: props.form.style_types_level1 || [],
    level2: props.form.style_types || []
  }),
  set: (val) => {
    emit('update:form', {
      ...props.form,
      style_types_level1: val.level1,
      style_types: val.level2
    })
  }
})

// 视频模式切换
const handleVideoModeChange = (mode) => {
  if (mode === 'real') {
    emit('update:form', {
      ...props.form,
      generate_ai_prompt: false,
      generate_storyboard_images: false,
      ai_platforms: []
    })
  } else {
    emit('update:form', {
      ...props.form,
      generate_storyboard_images: true
    })
  }
}

// 参考资料上传前处理
const beforeReferenceMaterialsUpload = (file) => {
  const allowedTypes = ['text/plain', 'text/markdown', 'application/pdf', 
    'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
  const allowedExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf']
  const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
    ElMessage.error('只支持 .txt, .md, .doc, .docx, .pdf 格式的文件')
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
