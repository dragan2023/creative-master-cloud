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
      <!-- 小说文风知识库选择 -->
      <div v-if="!isScriptType" class="style-library-section">
        <div class="section-header">
          <span class="section-title">文风知识库</span>
          <el-tag v-if="selectedStyleIds.length > 0" type="success" size="small">
            已选 {{ selectedStyleIds.length }} 种
          </el-tag>
        </div>

        <div class="style-library-content">
          <div v-if="selectedStyleIds.length > 0" class="selected-styles">
            <el-tag
              v-for="(style, idx) in selectedStyleNames"
              :key="idx"
              closable
              :type="idx === 0 ? '' : 'success'"
              @close="$emit('remove-style', idx)"
              style="margin-right: 8px; margin-bottom: 8px;"
            >
              {{ idx === 0 ? '主' : '辅' }} · {{ style }}
            </el-tag>
            <div class="style-intensity-info">
              <el-text type="info" size="small">
                风格强度: {{ Math.round(styleIntensity * 100) }}%
              </el-text>
            </div>
          </div>

          <div v-else class="empty-style-selection">
            <el-text type="info">
              从61种经典文风中选择1-3种进行融合创作
            </el-text>
          </div>

          <el-button type="primary" plain @click="$emit('show-style-selector')" style="margin-top: 12px;">
            <el-icon><Edit /></el-icon>
            {{ selectedStyleIds.length > 0 ? '修改文风选择' : '选择写作风格' }}
          </el-button>
        </div>
      </div>

      <!-- 剧本多维风格选择（电影/剧集） -->
      <div v-else class="script-style-section">
        <div class="section-header">
          <span class="section-title">{{ contentTypeLabel }}风格</span>
          <el-tag v-if="scriptStyleNames.length > 0" type="success" size="small">
            已选 {{ scriptStyleNames.length }} 维度
          </el-tag>
        </div>

        <div class="script-style-content">
          <div v-if="scriptStyleNames.length > 0" class="selected-dimensions">
            <el-tag
              v-for="(item, idx) in scriptStyleTagItems"
              :key="idx"
              type="primary"
              size="small"
              closable
              @close="$emit('remove-script-style', item.dimName)"
              style="margin-right: 6px; margin-bottom: 6px;"
            >
              {{ item.dimName }}: {{ item.styleName }}
            </el-tag>
            <div class="style-intensity-info">
              <el-text type="info" size="small">
                风格强度: {{ Math.round(scriptStyleIntensity * 100) }}%
              </el-text>
            </div>
          </div>

          <div v-else class="empty-style-selection">
            <el-text type="info">
              从多个维度选择{{ contentTypeLabel }}风格，为创作提供艺术指导
            </el-text>
          </div>

          <el-button type="primary" plain @click="$emit('show-script-style-selector')" style="margin-top: 12px;">
            <el-icon><Edit /></el-icon>
            {{ scriptStyleNames.length > 0 ? '修改风格' : '选择' + contentTypeLabel + '风格' }}
          </el-button>
        </div>
      </div>

      <!-- AI文风消除设置 -->
      <div class="ai-elimination-section">
        <div class="section-header">
          <span class="section-title">AI文风消除</span>
          <el-switch
            :model-value="aiEliminationEnabled"
            @update:model-value="$emit('update:aiEliminationEnabled', $event)"
            @change="$emit('elimination-change', $event)"
          />
        </div>
        <div class="elimination-config" v-if="aiEliminationEnabled">
          <div class="threshold-setting">
            <span class="threshold-label">强度</span>
            <el-slider
              :model-value="aiEliminationThreshold"
              @update:model-value="$emit('update:aiEliminationThreshold', $event)"
              @change="$emit('threshold-change', $event)"
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

    <!-- DeepSeek 思考模式 -->
    <el-divider content-position="left">
      <el-icon><Cpu /></el-icon>
      <span style="margin-left: 6px">DeepSeek 思考模式</span>
    </el-divider>

    <div class="thinking-mode-section">
      <div class="section-header">
        <span class="section-title">启用思考模式</span>
        <el-switch
          :model-value="thinkingModeEnabled"
          @update:model-value="$emit('update:thinkingModeEnabled', $event)"
          @change="$emit('thinking-mode-change', $event)"
        />
      </div>
      <p class="section-desc">
        启用后 DeepSeek V4 Pro/Flash 模型在回答前会进行深度推理，提升复杂任务准确性。
        启用后自动禁用 temperature 参数。
      </p>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-top: 8px"
      >
        <template #title>
          <span style="font-size: 12px; font-weight: normal">
            ⚠️ 仅 <b>DeepSeek V4 Pro</b>、<b>DeepSeek V4 Flash</b> 及 <b>DeepSeek Reasoner</b> 模型支持思考模式。
            若写作 Agent 使用的是其他模型，开启此开关不会生效。
          </span>
        </template>
      </el-alert>

      <div class="thinking-config" v-if="thinkingModeEnabled">
        <div class="effort-setting">
          <span class="effort-label">思考强度</span>
          <el-radio-group
            :model-value="thinkingReasoningEffort"
            @update:model-value="$emit('update:thinkingReasoningEffort', $event)"
            size="small"
          >
            <el-radio value="high">high（推荐）</el-radio>
            <el-radio value="max">max（最强）</el-radio>
          </el-radio-group>
        </div>

        <div class="save-dir-setting">
          <span class="dir-label">保存目录</span>
          <el-input
            :model-value="thinkingSaveDir"
            @update:model-value="$emit('update:thinkingSaveDir', $event)"
            placeholder="./data/thinking_logs"
            size="small"
            style="max-width: 300px"
          />
          <el-text type="info" size="small">思考过程日志保存路径</el-text>
        </div>

        <el-alert
          title="提示"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 12px"
        >
          <template #default>
            <span style="font-size: 12px">
              思考过程不会在前端显示，仅保存到文件。响应时间增加30%-100%，Token消耗增加。
            </span>
          </template>
        </el-alert>
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
import { Edit, Document, Upload, Setting, Cpu } from '@element-plus/icons-vue'
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
  },
  // 小说文风
  selectedStyleIds: {
    type: Array,
    default: () => []
  },
  selectedStyleNames: {
    type: Array,
    default: () => []
  },
  styleIntensity: {
    type: Number,
    default: 0.8
  },
  // 剧本风格（电影/剧集）
  isScriptType: {
    type: Boolean,
    default: false
  },
  scriptStyleNames: {
    type: Array,
    default: () => []
  },
  scriptStyleDimensions: {
    type: Object,
    default: () => ({})
  },
  scriptStyleIntensity: {
    type: Number,
    default: 0.7
  },
  // DeepSeek 思考模式
  thinkingModeEnabled: {
    type: Boolean,
    default: false
  },
  thinkingReasoningEffort: {
    type: String,
    default: 'high'
  },
  thinkingSaveDir: {
    type: String,
    default: './data/thinking_logs'
  }
})

const emit = defineEmits([
  'update:visible',
  'update:aiEliminationEnabled',
  'update:aiEliminationThreshold',
  'show-style-detail',
  'delete-style-document',
  'show-model-config',
  'show-style-selector',
  'show-script-style-selector',  // 剧本风格选择器
  'remove-style',
  'remove-script-style',         // 移除剧本风格维度
  'elimination-change',
  'threshold-change',
  'upload-success',
  'upload-error',
  // DeepSeek 思考模式
  'update:thinkingModeEnabled',
  'update:thinkingReasoningEffort',
  'update:thinkingSaveDir',
  'thinking-mode-change'
])

const contentTypeLabel = computed(() => {
  const labels = {
    novel: '小说',
    series_script: '连续剧剧本',
    movie_script: '电影剧本'
  }
  return labels[props.projectData?.content_type] || '小说'
})

// 剧本风格标签项（从 dimensions 扁平化）
const scriptStyleTagItems = computed(() => {
  const items = []
  const dims = props.scriptStyleDimensions || {}
  for (const [dimName, styles] of Object.entries(dims)) {
    if (styles && styles.length > 0) {
      items.push({
        dimName,
        styleName: styles[0]?.name || String(styles[0] || '未知')
      })
    }
  }
  return items
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
  flex-wrap: wrap;
  gap: 24px;
  padding: 0 4px;

  .style-library-section,
  .script-style-section,
  .style-document-section {
    flex: 1;
  }

  .ai-elimination-section {
    flex: 1 1 100%;

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

  .style-library-content {
    .selected-styles {
      margin-bottom: 8px;
    }

    .style-intensity-info {
      margin-top: 8px;
    }

    .empty-style-selection {
      padding: 8px 0;
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

.thinking-mode-section {
  padding: 0 4px;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;

    .section-title {
      font-size: 14px;
      font-weight: 500;
      color: #303133;
    }
  }

  .section-desc {
    font-size: 12px;
    color: #909399;
    margin: 0 0 16px 0;
    line-height: 1.5;
  }

  .thinking-config {
    padding: 16px;
    background: #f5f7fa;
    border-radius: 8px;

    .effort-setting {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;

      .effort-label {
        font-size: 13px;
        color: #606266;
        min-width: 70px;
      }
    }

    .save-dir-setting {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;

      .dir-label {
        font-size: 13px;
        color: #606266;
        min-width: 70px;
      }
    }
  }
}
</style>
