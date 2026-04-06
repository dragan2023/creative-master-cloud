<!--
  项目设置对话框组件
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="项目设置"
    width="600px"
    destroy-on-close
  >
    <el-form label-width="100px">
      <el-form-item label="项目名称">
        <el-input :model-value="projectData?.name" disabled />
      </el-form-item>
      <el-form-item label="内容类型">
        <el-tag>{{ contentTypeLabel }}</el-tag>
      </el-form-item>
      <el-form-item label="创建时间">
        <span>{{ projectData?.created_at }}</span>
      </el-form-item>
    </el-form>

    <!-- 风格设置区域 -->
    <el-divider content-position="left">
      <el-icon><Edit /></el-icon>
      <span style="margin-left: 6px">风格设置</span>
    </el-divider>

    <div class="style-settings-section">
      <!-- AI文风消除设置 -->
      <div class="ai-elimination-section">
        <div class="section-header">
          <span class="section-title">AI文风消除</span>
          <el-switch
            :model-value="aiEliminationEnabled"
            @update:model-value="$emit('update:aiEliminationEnabled', $event)"
          />
        </div>
        <div class="elimination-config" v-if="aiEliminationEnabled">
          <div class="threshold-setting">
            <span class="threshold-label">强度</span>
            <el-slider
              :model-value="aiEliminationThreshold"
              @update:model-value="$emit('update:aiEliminationThreshold', $event)"
              :min="0"
              :max="100"
              :step="10"
              :show-input="false"
            />
            <span class="threshold-value">{{ aiEliminationThreshold }}%</span>
          </div>
        </div>
      </div>

      <!-- 风格文档上传 -->
      <div class="style-document-section">
        <div class="section-header">
          <span class="section-title">文风模仿</span>
          <el-tag v-if="styleDocumentInfo?.style_document_uploaded" type="success" size="small">
            已上传
          </el-tag>
        </div>

        <div class="style-document-content">
          <div v-if="styleDocumentInfo?.style_document_uploaded" class="uploaded-document">
            <div class="document-info">
              <el-icon><Document /></el-icon>
              <span class="document-name">{{ styleDocumentInfo.style_document_name }}</span>
            </div>
            <div class="document-actions">
              <el-button type="primary" plain size="small" @click="$emit('show-style-detail')">
                查看详情
              </el-button>
              <el-button type="danger" plain size="small" @click="$emit('delete-style-document')">
                删除
              </el-button>
            </div>
          </div>

          <div v-else class="upload-section">
            <el-upload
              class="style-upload"
              :action="uploadAction"
              :headers="uploadHeaders"
              :show-file-list="false"
              :on-success="handleUploadSuccess"
              :on-error="handleUploadError"
              :before-upload="beforeUpload"
              accept=".txt,.docx,.pdf,.md"
            >
              <el-button type="primary" plain size="small">
                <el-icon><Upload /></el-icon>
                上传风格文档
              </el-button>
            </el-upload>
            <el-text type="info" size="small">上传参考文档，AI将模仿其写作风格</el-text>
          </div>
        </div>
      </div>
    </div>

    <!-- 模型配置入口 -->
    <el-divider />
    <div class="settings-model-config">
      <div class="config-info">
        <el-icon><Setting /></el-icon>
        <span>LLM模型配置</span>
      </div>
      <el-button type="primary" @click="$emit('show-model-config')">
        管理模型配置
      </el-button>
    </div>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { Edit, Document, Upload, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  projectData: {
    type: Object,
    default: () => ({})
  },
  styleDocumentInfo: {
    type: Object,
    default: null
  },
  aiEliminationEnabled: {
    type: Boolean,
    default: true
  },
  aiEliminationThreshold: {
    type: Number,
    default: 50
  },
  uploadAction: {
    type: String,
    default: ''
  },
  uploadHeaders: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits([
  'update:visible',
  'update:aiEliminationEnabled',
  'update:aiEliminationThreshold',
  'show-style-detail',
  'delete-style-document',
  'show-model-config',
  'upload-success',
  'upload-error'
])

const contentTypeLabel = computed(() => {
  const labels = {
    novel: '小说',
    series_script: '连续剧剧本',
    movie_script: '电影剧本'
  }
  return labels[props.projectData?.content_type] || '小说'
})

function beforeUpload(file) {
  const allowedTypes = ['.txt', '.docx', '.pdf', '.md']
  const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

  if (!allowedTypes.includes(fileExt)) {
    ElMessage.warning('仅支持 .txt, .docx, .pdf, .md 格式的文件')
    return false
  }

  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.warning('文件大小不能超过10MB')
    return false
  }

  return true
}

function handleUploadSuccess(response) {
  emit('upload-success', response)
}

function handleUploadError(error) {
  emit('upload-error', error)
}
</script>

<style lang="scss" scoped>
.style-settings-section {
  display: flex;
  flex-direction: row;
  gap: 24px;
  padding: 0 4px;

  .style-document-section,
  .ai-elimination-section {
    flex: 1;

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      .section-title {
        font-size: 14px;
        font-weight: 500;
        color: #303133;
      }
    }
  }

  .style-document-content {
    .uploaded-document {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 12px 16px;
      background: rgba(103, 194, 58, 0.08);
      border-radius: 8px;
      border: 1px solid rgba(103, 194, 58, 0.2);

      .document-info {
        display: flex;
        align-items: center;
        gap: 8px;

        .el-icon {
          font-size: 20px;
          color: #67c23a;
        }

        .document-name {
          font-size: 14px;
          color: #606266;
        }
      }

      .document-actions {
        display: flex;
        gap: 8px;
      }
    }

    .upload-section {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
  }

  .elimination-config {
    margin-top: 12px;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 8px;

    .threshold-setting {
      display: flex;
      align-items: center;
      gap: 12px;

      .threshold-label {
        font-size: 13px;
        color: #606266;
        min-width: 50px;
      }

      .el-slider {
        flex: 1;
      }

      .threshold-value {
        font-size: 13px;
        color: #409eff;
        min-width: 40px;
        text-align: right;
      }
    }
  }
}

.settings-model-config {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;

  .config-info {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #606266;

    .el-icon {
      font-size: 18px;
      color: #409eff;
    }
  }
}
</style>
