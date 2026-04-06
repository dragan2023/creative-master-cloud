<!--
  差异对比视图组件
  
  功能：
  1. 显示原始内容与修正内容的差异对比
  2. 高亮显示修改的部分
  3. 提供修改原因说明
  4. 用户可以选择接受全部/部分/拒绝修正
  
  依赖：
  - 父组件需提供 originalContent, correctedContent, corrections
  
  创建时间: 2026-04-02
  版本: 1.0.0
-->
<template>
  <div class="diff-viewer">
    <!-- 标题栏 -->
    <div class="diff-header">
      <div class="header-tabs">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="split">对比视图</el-radio-button>
          <el-radio-button value="unified">合并视图</el-radio-button>
        </el-radio-group>
      </div>
      <div class="header-stats">
        <el-tag type="info" size="small">
          {{ corrections.length }} 处修改
        </el-tag>
      </div>
    </div>

    <!-- 修正列表 -->
    <div class="corrections-list" v-if="corrections.length > 0">
      <div class="corrections-header">
        <span>修改建议列表</span>
        <div class="bulk-actions">
          <el-button size="small" type="success" plain @click="acceptAll">
            接受全部
          </el-button>
          <el-button size="small" type="danger" plain @click="rejectAll">
            拒绝全部
          </el-button>
        </div>
      </div>
      
      <el-collapse v-model="expandedCorrections">
        <el-collapse-item
          v-for="(correction, index) in corrections"
          :key="index"
          :name="index"
        >
          <template #title>
            <div class="correction-title">
              <el-tag
                :type="getCorrectionTypeTag(correction.type)"
                size="small"
                effect="plain"
              >
                {{ correction.type }}
              </el-tag>
              <span class="correction-summary">{{ correction.description }}</span>
              <el-tag
                v-if="correctionDecisions[index] === 'accepted'"
                type="success"
                size="small"
              >
                已接受
              </el-tag>
              <el-tag
                v-else-if="correctionDecisions[index] === 'rejected'"
                type="danger"
                size="small"
              >
                已拒绝
              </el-tag>
            </div>
          </template>
          
          <div class="correction-content">
            <!-- 修改位置 -->
            <div class="correction-location" v-if="correction.location">
              <el-icon><Location /></el-icon>
              <span>位置: {{ correction.location }}</span>
            </div>
            
            <!-- 原始文本 -->
            <div class="text-block original">
              <div class="block-label">
                <el-icon><Document /></el-icon>
                原始文本
              </div>
              <div class="block-content">
                <pre>{{ correction.original_text || getOriginalSnippet(correction) }}</pre>
              </div>
            </div>
            
            <!-- 修正文本 -->
            <div class="text-block corrected">
              <div class="block-label">
                <el-icon><Edit /></el-icon>
                修正文本
              </div>
              <div class="block-content">
                <pre>{{ correction.corrected_text || correction.suggestion }}</pre>
              </div>
            </div>
            
            <!-- 修改原因 -->
            <div class="correction-reason" v-if="correction.reason || correction.conflict_with">
              <el-icon><InfoFilled /></el-icon>
              <span>
                <template v-if="correction.conflict_with">
                  与 {{ correction.conflict_with }} 冲突: 
                </template>
                {{ correction.reason || correction.description }}
              </span>
            </div>
            
            <!-- 操作按钮 -->
            <div class="correction-actions">
              <el-button
                size="small"
                type="success"
                plain
                :disabled="correctionDecisions[index] === 'accepted'"
                @click="acceptCorrection(index)"
              >
                <el-icon><Check /></el-icon>
                接受
              </el-button>
              <el-button
                size="small"
                type="danger"
                plain
                :disabled="correctionDecisions[index] === 'rejected'"
                @click="rejectCorrection(index)"
              >
                <el-icon><Close /></el-icon>
                拒绝
              </el-button>
              <el-button
                size="small"
                plain
                @click="toggleDiffView(index)"
              >
                <el-icon><View /></el-icon>
                查看上下文
              </el-button>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
    
    <el-empty v-else description="没有检测到需要修正的内容" :image-size="80" />

    <!-- 对比视图 -->
    <div class="diff-content" v-if="viewMode === 'split' && (originalContent || correctedContent)">
      <div class="diff-columns">
        <!-- 原始内容 -->
        <div class="diff-column original">
          <div class="column-header">
            <el-icon><Document /></el-icon>
            原始内容
          </div>
          <div class="column-content" v-html="highlightedOriginal"></div>
        </div>
        
        <!-- 修正内容 -->
        <div class="diff-column corrected">
          <div class="column-header">
            <el-icon><Edit /></el-icon>
            修正内容
          </div>
          <div class="column-content" v-html="highlightedCorrected"></div>
        </div>
      </div>
    </div>

    <!-- 合并视图 -->
    <div class="diff-unified" v-if="viewMode === 'unified' && unifiedDiff.length > 0">
      <div class="unified-header">
        <el-icon><Merge /></el-icon>
        合并差异视图
      </div>
      <div class="unified-content">
        <div
          v-for="(line, index) in unifiedDiff"
          :key="index"
          :class="['diff-line', line.type]"
        >
          <span class="line-marker">{{ line.marker }}</span>
          <span class="line-text">{{ line.text }}</span>
        </div>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="diff-footer">
      <div class="footer-summary">
        <span>
          已选择: 
          <el-tag type="success" size="small">{{ acceptedCount }} 接受</el-tag>
          <el-tag type="danger" size="small" style="margin-left: 8px;">{{ rejectedCount }} 拒绝</el-tag>
          <el-tag type="info" size="small" style="margin-left: 8px;">{{ pendingCount }} 待定</el-tag>
        </span>
      </div>
      <div class="footer-actions">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" @click="handleApply" :disabled="acceptedCount === 0">
          应用选中的修改
        </el-button>
      </div>
    </div>

    <!-- 上下文查看弹窗 -->
    <el-dialog
      v-model="contextDialogVisible"
      title="查看上下文"
      width="60%"
      top="10vh"
    >
      <div class="context-view">
        <div class="context-text" v-html="contextContent"></div>
      </div>
      <template #footer>
        <el-button @click="contextDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  Document, Edit, Check, Close, View, InfoFilled,
  Location, Merge
} from '@element-plus/icons-vue'

// ==================== Props ====================
const props = defineProps({
  originalContent: {
    type: String,
    default: ''
  },
  correctedContent: {
    type: String,
    default: ''
  },
  corrections: {
    type: Array,
    default: () => []
  },
  // 是否自动展开所有修正
  autoExpand: {
    type: Boolean,
    default: true
  }
})

// ==================== Emits ====================
const emit = defineEmits(['apply', 'cancel', 'decision'])

// ==================== 状态 ====================
const viewMode = ref('split')
const expandedCorrections = ref([])
const correctionDecisions = ref({}) // { index: 'accepted' | 'rejected' }
const contextDialogVisible = ref(false)
const contextContent = ref('')
const selectedContextIndex = ref(null)

// ==================== 初始化 ====================
onMounted(() => {
  if (props.autoExpand && props.corrections.length > 0) {
    expandedCorrections.value = props.corrections.map((_, i) => i)
  }
})

// 监听corrections变化
watch(() => props.corrections, (newVal) => {
  if (props.autoExpand && newVal.length > 0) {
    expandedCorrections.value = newVal.map((_, i) => i)
  }
  // 重置决策
  correctionDecisions.value = {}
}, { immediate: true })

// ==================== 计算属性 ====================

// 接受的数量
const acceptedCount = computed(() => {
  return Object.values(correctionDecisions.value).filter(v => v === 'accepted').length
})

// 拒绝的数量
const rejectedCount = computed(() => {
  return Object.values(correctionDecisions.value).filter(v => v === 'rejected').length
})

// 待定的数量
const pendingCount = computed(() => {
  return props.corrections.length - acceptedCount.value - rejectedCount.value
})

// 高亮的原始内容
const highlightedOriginal = computed(() => {
  if (!props.originalContent) return ''
  
  let content = escapeHtml(props.originalContent)
  
  // 标记被删除的内容
  props.corrections.forEach((correction, index) => {
    const originalText = correction.original_text || correction.location
    if (originalText && correctionDecisions.value[index] !== 'rejected') {
      const regex = new RegExp(escapeRegExp(originalText), 'g')
      content = content.replace(regex, `<span class="diff-delete">${escapeHtml(originalText)}</span>`)
    }
  })
  
  return content.replace(/\n/g, '<br>')
})

// 高亮的修正内容
const highlightedCorrected = computed(() => {
  if (!props.correctedContent) return ''
  
  let content = escapeHtml(props.correctedContent)
  
  // 标记新增的内容
  props.corrections.forEach((correction, index) => {
    const correctedText = correction.corrected_text || correction.suggestion
    if (correctedText && correctionDecisions.value[index] === 'accepted') {
      const regex = new RegExp(escapeRegExp(correctedText), 'g')
      content = content.replace(regex, `<span class="diff-add">${escapeHtml(correctedText)}</span>`)
    }
  })
  
  return content.replace(/\n/g, '<br>')
})

// 合并差异视图
const unifiedDiff = computed(() => {
  if (!props.originalContent || !props.correctedContent) return []
  
  const originalLines = props.originalContent.split('\n')
  const correctedLines = props.correctedContent.split('\n')
  const diff = []
  
  const maxLen = Math.max(originalLines.length, correctedLines.length)
  
  for (let i = 0; i < maxLen; i++) {
    const origLine = originalLines[i]
    const corrLine = correctedLines[i]
    
    if (origLine === corrLine) {
      diff.push({ type: 'unchanged', marker: ' ', text: origLine || '' })
    } else {
      if (origLine !== undefined) {
        diff.push({ type: 'removed', marker: '-', text: origLine })
      }
      if (corrLine !== undefined) {
        diff.push({ type: 'added', marker: '+', text: corrLine })
      }
    }
  }
  
  return diff
})

// ==================== 方法 ====================

// 获取修正类型标签
function getCorrectionTypeTag(type) {
  const typeMap = {
    '设定冲突': 'danger',
    '剧情衔接跳脱': 'warning',
    '人物成长过快': 'warning',
    '时间线矛盾': 'danger',
    '核心线索断裂': 'danger',
    '角色一致性': 'warning',
    '设定一致性': 'info',
    '情节一致性': 'info'
  }
  return typeMap[type] || 'info'
}

// 获取原始文本片段
function getOriginalSnippet(correction) {
  if (!props.originalContent || !correction.location) return ''
  
  const location = correction.location
  const index = props.originalContent.indexOf(location)
  if (index === -1) return location
  
  const start = Math.max(0, index - 50)
  const end = Math.min(props.originalContent.length, index + location.length + 50)
  
  return props.originalContent.substring(start, end)
}

// 接受单个修正
function acceptCorrection(index) {
  correctionDecisions.value[index] = 'accepted'
  emit('decision', { index, decision: 'accepted', correction: props.corrections[index] })
}

// 拒绝单个修正
function rejectCorrection(index) {
  correctionDecisions.value[index] = 'rejected'
  emit('decision', { index, decision: 'rejected', correction: props.corrections[index] })
}

// 接受全部
function acceptAll() {
  props.corrections.forEach((_, index) => {
    if (correctionDecisions.value[index] !== 'accepted') {
      correctionDecisions.value[index] = 'accepted'
      emit('decision', { index, decision: 'accepted', correction: props.corrections[index] })
    }
  })
}

// 拒绝全部
function rejectAll() {
  props.corrections.forEach((_, index) => {
    if (correctionDecisions.value[index] !== 'rejected') {
      correctionDecisions.value[index] = 'rejected'
      emit('decision', { index, decision: 'rejected', correction: props.corrections[index] })
    }
  })
}

// 切换差异视图
function toggleDiffView(index) {
  selectedContextIndex.value = index
  const correction = props.corrections[index]
  
  // 构建上下文内容
  let context = ''
  if (props.originalContent) {
    const location = correction.location || correction.original_text
    if (location) {
      const index2 = props.originalContent.indexOf(location)
      if (index2 !== -1) {
        const start = Math.max(0, index2 - 100)
        const end = Math.min(props.originalContent.length, index2 + location.length + 100)
        context = props.originalContent.substring(start, end)
      }
    }
  }
  
  contextContent.value = context ? `<pre>${escapeHtml(context)}</pre>` : '<p>无法定位上下文</p>'
  contextDialogVisible.value = true
}

// 应用修改
function handleApply() {
  const acceptedCorrections = props.corrections.filter((_, index) => 
    correctionDecisions.value[index] === 'accepted'
  )
  const rejectedCorrections = props.corrections.filter((_, index) => 
    correctionDecisions.value[index] === 'rejected'
  )
  
  emit('apply', {
    accepted: acceptedCorrections,
    rejected: rejectedCorrections,
    decisions: { ...correctionDecisions.value }
  })
}

// 取消
function handleCancel() {
  emit('cancel')
}

// 辅助函数：转义HTML
function escapeHtml(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

// 辅助函数：转义正则表达式特殊字符
function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
</script>

<style lang="scss" scoped>
.diff-viewer {
  .diff-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 8px 8px 0 0;
    border-bottom: 1px solid #e4e7ed;
  }

  .corrections-list {
    padding: 16px;

    .corrections-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      font-weight: 500;
      color: #303133;
    }

    .correction-title {
      display: flex;
      align-items: center;
      gap: 8px;
      
      .correction-summary {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .correction-content {
      .correction-location {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 12px;
        color: #909399;
        font-size: 13px;
      }

      .text-block {
        margin-bottom: 12px;

        .block-label {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-bottom: 6px;
          font-size: 12px;
          font-weight: 500;
          color: #606266;
        }

        .block-content {
          padding: 12px;
          border-radius: 6px;
          font-size: 13px;
          line-height: 1.6;

          pre {
            margin: 0;
            white-space: pre-wrap;
            word-wrap: break-word;
          }
        }

        &.original .block-content {
          background: #fef0f0;
          border: 1px solid #fbc4c4;
        }

        &.corrected .block-content {
          background: #f0f9eb;
          border: 1px solid #c2e7b0;
        }
      }

      .correction-reason {
        display: flex;
        align-items: flex-start;
        gap: 6px;
        padding: 10px;
        margin-bottom: 12px;
        background: #fdf6ec;
        border-radius: 6px;
        font-size: 13px;
        color: #e6a23c;

        .el-icon {
          margin-top: 2px;
        }
      }

      .correction-actions {
        display: flex;
        gap: 8px;
      }
    }
  }

  .diff-content {
    .diff-columns {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      padding: 16px;

      .diff-column {
        .column-header {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 12px;
          background: #f5f7fa;
          border-radius: 6px 6px 0 0;
          font-weight: 500;
          color: #606266;
        }

        .column-content {
          padding: 16px;
          border: 1px solid #e4e7ed;
          border-top: none;
          border-radius: 0 0 6px 6px;
          min-height: 200px;
          max-height: 400px;
          overflow-y: auto;
          font-size: 13px;
          line-height: 1.8;

          :deep(.diff-delete) {
            background: #fef0f0;
            text-decoration: line-through;
            color: #f56c6c;
          }

          :deep(.diff-add) {
            background: #f0f9eb;
            color: #67c23a;
          }
        }

        &.original .column-content {
          background: #fafafa;
        }

        &.corrected .column-content {
          background: #f9fff9;
        }
      }
    }
  }

  .diff-unified {
    padding: 16px;

    .unified-header {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 12px;
      font-weight: 500;
      color: #606266;
    }

    .unified-content {
      border: 1px solid #e4e7ed;
      border-radius: 6px;
      max-height: 400px;
      overflow-y: auto;

      .diff-line {
        display: flex;
        padding: 4px 12px;
        font-family: monospace;
        font-size: 13px;
        line-height: 1.5;

        .line-marker {
          width: 20px;
          color: #909399;
          text-align: center;
        }

        .line-text {
          flex: 1;
          white-space: pre-wrap;
          word-wrap: break-word;
        }

        &.unchanged {
          background: white;
        }

        &.removed {
          background: #fef0f0;
          color: #f56c6c;

          .line-marker {
            color: #f56c6c;
          }
        }

        &.added {
          background: #f0f9eb;
          color: #67c23a;

          .line-marker {
            color: #67c23a;
          }
        }
      }
    }
  }

  .diff-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    background: #f5f7fa;
    border-radius: 0 0 8px 8px;
    border-top: 1px solid #e4e7ed;

    .footer-summary {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #606266;
    }

    .footer-actions {
      display: flex;
      gap: 12px;
    }
  }

  .context-view {
    .context-text {
      padding: 16px;
      background: #f5f7fa;
      border-radius: 6px;
      max-height: 400px;
      overflow-y: auto;
      font-family: monospace;
      font-size: 13px;
      line-height: 1.6;

      pre {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
      }
    }
  }
}
</style>
