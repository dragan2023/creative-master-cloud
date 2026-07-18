<template>
  <!-- 第一行：设计类别 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="设计类别" prop="design_category">
        <el-select v-model="form.design_category" placeholder="选择设计类别" style="width: 100%">
          <el-option label="Logo设计" value="logo设计" />
          <el-option label="商业广告" value="商业广告" />
          <el-option label="宣传单页" value="宣传单页" />
          <el-option label="公益广告" value="公益广告" />
          <el-option label="政府宣传" value="政府宣传" />
          <el-option label="海报设计" value="海报设计" />
          <el-option label="展架设计" value="展架设计" />
          <el-option label="包装设计" value="包装设计" />
          <el-option label="其他设计" value="其他设计" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第二行：品牌/产品 + 广告目的 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="品牌/产品名称" prop="brand_product">
        <el-input v-model="form.brand_product" placeholder="具体品牌+产品（新品牌需说明调性）" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="广告目的" prop="ad_purpose">
        <el-input v-model="form.ad_purpose" placeholder="如：新品上市、品牌升级、促销活动等" />
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第二行：核心信息 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="核心信息" prop="core_message">
        <div class="description-input-wrapper">
          <el-input
            v-model="form.core_message"
            type="textarea"
            :rows="2"
            placeholder="如果受众看完只记住一件事，你希望是什么？必须用一句话说清楚"
          />
          <!-- 优化按钮 -->
          <div class="optimize-actions">
            <el-button 
              type="primary" 
              text
              :loading="optimizing && optimizeTarget === 'core_message'"
              :disabled="!form.core_message || form.core_message.length < 5"
              @click="$emit('optimize', 'core_message')"
            >
              <el-icon><MagicStick /></el-icon>
              {{ optimizing && optimizeTarget === 'core_message' ? '优化中...' : '优化输入' }}
            </el-button>
            <span class="optimize-tip" v-if="form.core_message && form.core_message.length < 5">
              请至少输入5个字符
            </span>
          </div>
        </div>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第三行：受众特征 + 接触场景 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="受众特征" prop="audience_profile">
        <el-input
          v-model="form.audience_profile"
          type="textarea"
          :rows="3"
          placeholder="年龄+性别+学历+职业+收入+地域&#10;如：25-35岁+女性+本科+白领+月收入8K-15K+一二线城市"
        />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="接触场景" prop="contact_scene">
        <el-input
          v-model="form.contact_scene"
          type="textarea"
          :rows="3"
          placeholder="他们通常在哪里看到这则广告？&#10;如：地铁站台、微信朋友圈、电梯间、商场中庭"
        />
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第四行：风格调性 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="风格调性" prop="style_tone">
        <el-select v-model="form.style_tone" placeholder="选择风格" style="width: 100%">
          <el-option label="视觉冲击" value="视觉冲击" />
          <el-option label="极简留白" value="极简留白" />
          <el-option label="幽默搞怪" value="幽默搞怪" />
          <el-option label="温情走心" value="温情走心" />
          <el-option label="功能直给" value="功能直给" />
          <el-option label="复古怀旧" value="复古怀旧" />
          <el-option label="科技感" value="科技感" />
          <el-option label="高级感" value="高级感" />
          <el-option label="国潮风" value="国潮风" />
          <el-option label="赛博朋克" value="赛博朋克" />
          <el-option label="手绘插画" value="手绘插画" />
          <el-option label="摄影写实" value="摄影写实" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第五行：文案内容 + 具体尺寸 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="文案内容" prop="copy_content">
        <el-input v-model="form.copy_content" placeholder="已有文案可直接填写（可选）" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="具体尺寸" prop="size_spec">
        <el-input v-model="form.size_spec" placeholder="如：1080x1920px、A4、3x4m等（可选）" />
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第七行：发布媒介 + AI平台 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="发布媒介" prop="publish_media">
        <el-input v-model="form.publish_media" placeholder="如：微信朋友圈、地铁灯箱、户外大屏等（可选）" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="AI提示词平台" prop="ai_platforms_ad">
        <el-select v-model="form.ai_platforms_ad" placeholder="选择AI平台" style="width: 100%">
          <el-option label="豆包" value="豆包" />
          <el-option label="即梦" value="即梦" />
          <el-option label="千问" value="千问" />
          <el-option label="Gemini" value="Gemini" />
          <el-option label="GPT" value="GPT" />
          <el-option label="Grok" value="Grok" />
          <el-option label="可灵" value="可灵" />
          <el-option label="Midjourney" value="Midjourney" />
          <el-option label="Stable Diffusion" value="Stable Diffusion" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第八行：参考图片（多模态） -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item>
        <template #label>
          <span>参考图片</span>
          <el-tag type="warning" size="small" style="margin-left: 8px;">仅支持多模态模型</el-tag>
        </template>
        <div class="image-upload-section">
          <el-upload
            :action="uploadUrl"
            :headers="uploadHeaders"
            :on-success="(res, file) => $emit('upload-success', { response: res, file })"
            :on-error="(err, file) => $emit('upload-error', { error: err, file })"
            :before-upload="beforeUpload"
            :file-list="imageFileList"
            list-type="picture-card"
            :limit="5"
            accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
            multiple
          >
            <el-icon><Plus /></el-icon>
            <template #tip>
              <div class="upload-tip">支持 png/jpg/gif/webp，最大10MB，最多5张</div>
            </template>
          </el-upload>
          <div class="url-input-section">
            <el-input
              :model-value="imageUrlInput"
              @update:model-value="$emit('update:imageUrlInput', $event)"
              placeholder="或输入图片URL，多个用逗号分隔"
              @blur="$emit('parse-image-urls')"
            />
            <div class="form-tip">URL需要资料直链，推荐使用图床网站获取直链</div>
          </div>
        </div>
      </el-form-item>
    </el-col>
  </el-row>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { MagicStick, Plus } from '@element-plus/icons-vue'

defineProps({
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
  imageFileList: {
    type: Array,
    default: () => []
  },
  imageUrlInput: {
    type: String,
    default: ''
  }
})

defineEmits([
  'update:form',
  'update:imageUrlInput',
  'optimize',
  'upload-success',
  'upload-error',
  'parse-image-urls'
])

// 上传前验证（图片）
const beforeUpload = (file) => {
  const isImage = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'].includes(file.type)
  const isLt50M = file.size / 1024 / 1024 < 50
  
  if (!isImage) {
    ElMessage.error('只能上传图片文件！')
    return false
  }
  if (!isLt50M) {
    ElMessage.error('图片大小不能超过50MB！')
    return false
  }
  return true
}
</script>

<style lang="scss" scoped>
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

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

.image-upload-section {
  width: 100%;
  
  .upload-tip {
    font-size: 12px;
    color: #909399;
    margin-top: 8px;
  }
  
  .url-input-section {
    margin-top: 12px;
  }
}
</style>
