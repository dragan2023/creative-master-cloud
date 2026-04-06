<template>
  <!-- 第一行：篇幅与类型 -->
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
      <el-form-item label="类型标签" prop="genre">
        <el-select v-model="form.genre" placeholder="选择类型（可多选）" style="width: 100%" multiple>
          <el-option label="言情" value="言情" />
          <el-option label="悬疑推理" value="悬疑推理" />
          <el-option label="科幻" value="科幻" />
          <el-option label="奇幻玄幻" value="奇幻玄幻" />
          <el-option label="历史" value="历史" />
          <el-option label="现实题材" value="现实题材" />
          <el-option label="轻小说" value="轻小说" />
          <el-option label="恐怖惊悚" value="恐怖惊悚" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第二行：目标读者/平台 -->
  <el-row :gutter="20">
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
    <el-col :span="12">
      <el-form-item label="基调氛围" prop="tone">
        <el-select v-model="form.tone" placeholder="选择基调" style="width: 100%">
          <el-option label="正剧（严肃厚重）" value="正剧" />
          <el-option label="喜剧（轻松解压）" value="喜剧" />
          <el-option label="虐恋催泪" value="虐恋催泪" />
          <el-option label="爽文（逆袭打脸）" value="爽文" />
          <el-option label="治愈温暖" value="治愈温暖" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第三行：故事主题 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="故事主题" prop="theme">
        <el-input
          v-model="form.theme"
          type="textarea"
          :rows="2"
          placeholder="你想通过这个故事表达什么？——关于爱、牺牲、正义、自由、欲望、人性的探讨？"
        />
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第四行：独特卖点 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="独特卖点" prop="unique_selling_point">
        <el-input
          v-model="form.unique_selling_point"
          type="textarea"
          :rows="2"
          placeholder="这个故事最吸引人的钩子是什么？——高概念设定、极致人设、社会热点映射、还是烧脑谜题？"
        />
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
</template>

<script setup>
import { ElMessage } from 'element-plus'

defineProps({
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

defineEmits([
  'update:form',
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
  if (file.size / 1024 / 1024 > 50) {
    ElMessage.error('文件大小不能超过50MB！')
    return false
  }
  return true
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
