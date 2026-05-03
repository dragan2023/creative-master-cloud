<!--
  组件: UnitSummariesUploadDialog
  上传单元概述弹窗
  P0改造：支持Markdown自动解析
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="上传单元概述"
    width="650px"
  >
    <div class="unit-summaries-upload-dialog">
      <el-tabs :model-value="uploadMode" @update:model-value="$emit('update:uploadMode', $event)" class="upload-tabs">
        <el-tab-pane label="文件上传" name="file">
          <el-upload
            drag
            :show-file-list="false"
            :http-request="handleFileUpload"
            accept=".txt,.md,.doc,.docx"
            :disabled="uploading"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽单元概述文件到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 .txt, .md, .doc, .docx 格式，与全局大纲格式相同
              </div>
            </template>
          </el-upload>
          <el-alert type="info" :closable="false" style="margin-top: 12px;">
            <template #title>文件格式说明</template>
            <div style="font-size: 13px; margin-top: 4px;">
              <p>文件应包含各单元的标题和梗概内容，格式示例：</p>
              <pre style="background: #f5f7fa; padding: 8px; border-radius: 4px; font-size: 12px; overflow-x: auto; margin-top: 8px;">### 第1章：开篇

**本章梗概**：故事的开端，介绍主人公...

---

### 第2章：相遇

**本章梗概**：主人公与关键人物相遇...</pre>
            </div>
          </el-alert>
        </el-tab-pane>
        
        <!-- P0改造：将JSON粘贴改为内容粘贴，支持JSON和Markdown两种格式 -->
        <el-tab-pane label="内容粘贴" name="content">
          <el-alert type="success" :closable="false" style="margin-bottom: 12px;">
            <template #title>智能格式识别</template>
            <div style="font-size: 13px; margin-top: 4px;">
              <p>系统会自动识别粘贴的内容格式：</p>
              <ul style="margin: 4px 0; padding-left: 16px;">
                <li><strong>JSON格式</strong>：可从创意生成板块的导出功能获取</li>
                <li><strong>Markdown格式</strong>：直接粘贴生成的单元概述内容即可</li>
              </ul>
            </div>
          </el-alert>
          
          <!-- 格式检测提示 -->
          <el-tag v-if="detectedFormat" :type="detectedFormat === 'json' ? 'success' : 'primary'" style="margin-bottom: 12px;">
            已识别格式: {{ detectedFormat === 'json' ? 'JSON' : 'Markdown' }}
            <span v-if="parsedUnitCount > 0"> ({{ parsedUnitCount }}个单元)</span>
          </el-tag>
          <el-tag v-else-if="unitSummariesInput.trim() && !detectedFormat" type="warning" style="margin-bottom: 12px;">
            未识别到有效格式，请检查内容
          </el-tag>
          
          <el-form-item label="单元概述内容">
            <el-input
              :model-value="unitSummariesInput"
              @update:model-value="handleContentInput"
              type="textarea"
              :rows="8"
              placeholder="请粘贴单元概述内容（支持JSON或Markdown格式）..."
            />
          </el-form-item>
          
          <el-form-item label="全局大纲（可选）">
            <el-input
              :model-value="globalOutlineInput"
              @update:model-value="$emit('update:globalOutlineInput', $event)"
              type="textarea"
              :rows="4"
              placeholder="可选：粘贴全局大纲内容..."
            />
          </el-form-item>
        </el-tab-pane>
      </el-tabs>
    </div>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button 
        v-if="uploadMode === 'content'"
        type="primary" 
        @click="handleUploadContent"
        :loading="uploading"
        :disabled="!unitSummariesInput.trim() || !detectedFormat"
      >
        确认上传
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { parseUnitSummariesFromContent } from '@/views/generate/utils/outlineParser'

const props = defineProps({
  visible: { type: Boolean, default: false },
  uploadMode: { type: String, default: 'file' },
  unitSummariesInput: { type: String, default: '' },
  globalOutlineInput: { type: String, default: '' },
  uploading: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'update:uploadMode', 'update:unitSummariesInput', 'update:globalOutlineInput', 'upload-file', 'upload-content', 'cancel'])

// P0改造新增：格式检测状态
const detectedFormat = ref(null)
const parsedUnitCount = ref(0)

/**
 * 处理内容输入并自动检测格式
 */
function handleContentInput(value) {
  emit('update:unitSummariesInput', value)
  
  if (!value.trim()) {
    detectedFormat.value = null
    parsedUnitCount.value = 0
    return
  }
  
  // 尝试JSON解析
  try {
    const parsed = JSON.parse(value)
    if (parsed && typeof parsed === 'object') {
      detectedFormat.value = 'json'
      parsedUnitCount.value = Object.keys(parsed).length
      return
    }
  } catch (e) {
    // JSON解析失败，继续尝试Markdown
  }
  
  // 尝试Markdown解析
  const parsedMarkdown = parseUnitSummariesFromContent(value)
  if (Object.keys(parsedMarkdown).length > 0) {
    detectedFormat.value = 'markdown'
    parsedUnitCount.value = Object.keys(parsedMarkdown).length
  } else {
    detectedFormat.value = null
    parsedUnitCount.value = 0
  }
}

/**
 * 处理上传内容（支持JSON和Markdown）
 */
function handleUploadContent() {
  if (!props.unitSummariesInput.trim() || !detectedFormat.value) {
    return
  }
  
  let parsedData = null
  let rawContent = props.unitSummariesInput
  
  if (detectedFormat.value === 'json') {
    // JSON格式直接使用
    try {
      parsedData = JSON.parse(rawContent)
    } catch (e) {
      // JSON解析失败（理论上不会发生，因为检测时已验证）
      return
    }
  } else if (detectedFormat.value === 'markdown') {
    // Markdown格式需要解析
    parsedData = parseUnitSummariesFromContent(rawContent)
  }
  
  // 发送解析后的数据
  emit('upload-content', {
    format: detectedFormat.value,
    parsedData: parsedData,
    rawContent: rawContent
  })
}

const handleClose = () => {
  detectedFormat.value = null
  parsedUnitCount.value = 0
  emit('update:visible', false)
}

function handleFileUpload(options) {
  emit('upload-file', options)
}
</script>
