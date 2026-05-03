<!--
  单元概述修正对比对话框
  功能：
  1. 并排显示修正前后的单元概述内容
  2. 字符级差异高亮（使用diff库的diffChars算法）
  3. 质控评分和问题统计
  4. 用户确认或取消修正

  依赖：npm包 diff (diffChars)
  创建时间: 2026-04-18
  版本: 1.0
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="单元概述修正对比"
    width="90%"
    destroy-on-close
    :close-on-click-modal="false"
    top="4vh"
  >
    <!-- 统计信息栏 -->
    <div class="stats-bar" v-if="dialogVisible">
      <div class="stat-item">
        <span class="stat-label">原始长度</span>
        <span class="stat-value">{{ originalLength }} 字</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">修正长度</span>
        <span class="stat-value">{{ revisedLength }} 字</span>
      </div>
      <el-divider direction="vertical" />
      <div class="stat-item" v-if="qualityScore > 0">
        <span class="stat-label">质控评分</span>
        <el-rate
          v-model="scoreStars"
          disabled
          show-score
          text-color="#ff9900"
          score-template="{value}分"
        />
      </div>
      <div class="stat-item" v-if="totalIssues > 0">
        <el-tag type="danger" size="small">{{ totalIssues }} 个问题</el-tag>
      </div>
      <div class="stat-item" v-if="criticalIssuesCount > 0">
        <el-tag type="warning" size="small">{{ criticalIssuesCount }} 个关键问题</el-tag>
      </div>
      <div class="stat-item">
        <span class="stat-label">变化量</span>
        <span class="stat-value changed">{{ diffStats.totalChanged }} 字</span>
      </div>
    </div>

    <!-- 并排对比视图 -->
    <div class="compare-view" v-if="dialogVisible">
      <div class="compare-panel original-panel">
        <div class="panel-header">
          <el-tag type="info">修正前</el-tag>
          <span class="char-count">{{ originalContent?.length || 0 }} 字</span>
        </div>
        <pre class="content-text" v-html="highlightedOriginal"></pre>
      </div>

      <div class="compare-panel revised-panel">
        <div class="panel-header">
          <el-tag type="success">修正后</el-tag>
          <span class="char-count">{{ revisedContent?.length || 0 }} 字</span>
        </div>
        <pre class="content-text" v-html="highlightedRevised"></pre>
      </div>
    </div>

    <!-- 修改详情列表 -->
    <div class="changes-list" v-if="changes && changes.length > 0">
      <el-divider>修改详情 ({{ changes.length }}处)</el-divider>
      <el-collapse>
        <el-collapse-item
          v-for="(change, idx) in changes"
          :key="idx"
          :name="idx"
        >
          <template #title>
            <div class="change-title">
              <el-tag :type="getChangeType(change.type)" size="small">{{ change.type || '修改' }}</el-tag>
              <span class="change-location">{{ change.location || `修改 #${idx + 1}` }}</span>
              <span v-if="change.dimension" class="change-dimension">
                <el-tag size="small" type="info">{{ change.dimension }}</el-tag>
              </span>
            </div>
          </template>
          <div class="change-detail">
            <div v-if="change.original_text" class="change-original">
              <strong>原文：</strong>
              <div class="change-text removed-text">{{ change.original_text }}</div>
            </div>
            <div v-if="change.new_text" class="change-new">
              <strong>修改为：</strong>
              <div class="change-text added-text">{{ change.new_text }}</div>
            </div>
            <div v-if="change.reason" class="change-reason">
              <strong>原因：</strong>{{ change.reason }}
            </div>
            <div v-if="change.suggestion" class="change-suggestion">
              <strong>建议：</strong>{{ change.suggestion }}
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- 差异统计 -->
    <div class="diff-summary" v-if="dialogVisible && diffStats.totalChanged > 0">
      <el-descriptions :column="3" size="small" border>
        <el-descriptions-item label="新增字符">{{ diffStats.added }}</el-descriptions-item>
        <el-descriptions-item label="删除字符">{{ diffStats.removed }}</el-descriptions-item>
        <el-descriptions-item label="修改字符">{{ diffStats.modified }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 重复章节检测 -->
    <div class="duplicate-detection" v-if="dialogVisible && duplicates.length > 0">
      <el-divider>重复章节检测</el-divider>
      <el-alert
        :title="`发现 ${duplicates.length} 组重复章节`"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 12px;"
      >
        <template #default>
          <div class="duplicate-info">
            修正过程中产生了重复章节，建议清理后再应用修正。
          </div>
        </template>
      </el-alert>
      
      <el-table :data="duplicates" border size="small" style="margin-bottom: 12px;">
        <el-table-column prop="groupIndex" label="组别" width="60" align="center" />
        <el-table-column label="重复章节" min-width="200">
          <template #default="{ row }">
            <div v-for="(dup, idx) in row.duplicates" :key="idx" class="duplicate-item">
              <el-tag :type="idx === 0 ? 'success' : 'danger'" size="small" style="margin-right: 8px;">
                {{ idx === 0 ? '保留' : '删除' }}
              </el-tag>
              <strong>{{ dup.title }}</strong>
              <span class="duplicate-unit-num">（第{{ dup.unitNumber }}章）</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="内容长度" width="120" align="center">
          <template #default="{ row }">
            {{ row.duplicates[0]?.contentLength || 0 }} 字
          </template>
        </el-table-column>
      </el-table>
      
      <el-button
        type="warning"
        size="small"
        @click="handleRemoveDuplicates"
        :loading="removingDuplicates"
      >
        <el-icon><Delete /></el-icon>
        自动清理重复章节
      </el-button>
    </div>

    <template #footer>
      <el-button @click="handleDownloadOriginal" :disabled="!originalContent">
        <el-icon><Download /></el-icon>
        下载原始稿
      </el-button>
      <el-button @click="handleDownloadRevised" :disabled="!revisedContent">
        <el-icon><Download /></el-icon>
        下载修正稿
      </el-button>
      <el-button @click="handleCancel">保留原始内容</el-button>
      <el-button type="primary" @click="handleConfirm">应用修正</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, watch, nextTick, ref } from 'vue'
import { diffChars } from 'diff'
import { Delete, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  originalContent: { type: String, default: '' },
  revisedContent: { type: String, default: '' },
  revisedParsed: { type: [Object, Array], default: null },
  changes: { type: Array, default: () => [] },
  originalLength: { type: Number, default: 0 },
  revisedLength: { type: Number, default: 0 },
  totalIssues: { type: Number, default: 0 },
  criticalIssuesCount: { type: Number, default: 0 },
  qualityScore: { type: Number, default: 0 }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel', 'remove-duplicates'])

// 重复章节检测相关
const removingDuplicates = ref(false)
const duplicates = ref([])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 质控评分转星星数(100分制转5分制)
const scoreStars = computed(() => Math.round(props.qualityScore / 20 * 10) / 10)

// HTML转义
function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// 差异高亮计算
function computeDiffHtml() {
  const original = props.originalContent || ''
  const revised = props.revisedContent || ''

  if (!original && !revised) return { originalHtml: '', revisedHtml: '' }

  const diff = diffChars(original, revised)

  let originalHtml = ''
  let revisedHtml = ''

  diff.forEach((part) => {
    const escapedText = escapeHtml(part.value)

    if (part.added) {
      revisedHtml += `<span class="diff-added">${escapedText}</span>`
    } else if (part.removed) {
      originalHtml += `<span class="diff-removed">${escapedText}</span>`
    } else {
      originalHtml += escapedText
      revisedHtml += escapedText
    }
  })

  return { originalHtml, revisedHtml }
}

const highlightedOriginal = computed(() => computeDiffHtml().originalHtml)
const highlightedRevised = computed(() => computeDiffHtml().revisedHtml)

// 差异统计
const diffStats = computed(() => {
  const original = props.originalContent || ''
  const revised = props.revisedContent || ''

  const diff = diffChars(original, revised)

  let added = 0
  let removed = 0

  diff.forEach((part) => {
    if (part.added) added += part.value.length
    else if (part.removed) removed += part.value.length
  })

  return {
    added,
    removed,
    modified: Math.min(added, removed),
    totalChanged: added + removed
  }
})

function getChangeType(type) {
  if (type === 'replace' || type === '修改') return 'warning'
  if (type === 'insert' || type === '新增') return 'success'
  if (type === 'delete' || type === '删除') return 'danger'
  return 'info'
}

function handleConfirm() {
  emit('confirm')
  nextTick(() => { dialogVisible.value = false })
}

function handleCancel() {
  emit('cancel')
  nextTick(() => { dialogVisible.value = false })
}

/**
 * v3.1新增：下载原始稿
 */
function handleDownloadOriginal() {
  const content = props.originalContent
  if (!content) {
    ElMessage.warning('原始内容为空，无法下载')
    return
  }
  downloadMarkdownFile(content, 'unit_summaries_original.md')
  ElMessage.success('原始稿已下载')
}

/**
 * v3.1新增：下载修正稿
 */
function handleDownloadRevised() {
  const content = props.revisedContent
  if (!content) {
    ElMessage.warning('修正内容为空，无法下载')
    return
  }
  downloadMarkdownFile(content, 'unit_summaries_revised.md')
  ElMessage.success('修正稿已下载')
}

/**
 * v3.1新增：下载Markdown文件
 */
function downloadMarkdownFile(content, filename) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 检测重复章节
 * 以章节为单位,比较标题和内容的完全匹配
 */
function detectDuplicates(content) {
  if (!content) return []
  
  // 解析章节内容
  const chapterRegex = /###\s*第([\u4e00二三四五六七八九十百千万\d]+)[章集场][：:]\s*(.+?)\n([\s\S]*?)(?=###\s*第|$)/g
  const chapters = []
  let match
  
  while ((match = chapterRegex.exec(content)) !== null) {
    chapters.push({
      unitNumber: match[1],
      title: match[2].trim(),
      content: match[3].trim(),
      fullMatch: match[0]
    })
  }
  
  if (chapters.length === 0) return []
  
  // 查找重复章节
  const duplicateGroups = []
  const seen = new Map() // title+content -> first index
  
  chapters.forEach((chapter, index) => {
    const key = `${chapter.title}|||${chapter.content}`
    
    if (seen.has(key)) {
      // 找到重复章节
      const firstIndex = seen.get(key)
      let group = duplicateGroups.find(g => g.firstIndex === firstIndex)
      
      if (!group) {
        group = {
          groupIndex: duplicateGroups.length + 1,
          firstIndex: firstIndex,
          duplicates: [chapters[firstIndex]]
        }
        duplicateGroups.push(group)
      }
      
      group.duplicates.push({
        ...chapter,
        contentLength: chapter.content.length
      })
    } else {
      seen.set(key, index)
    }
  })
  
  return duplicateGroups
}

/**
 * 清理重复章节
 * 保留第一个出现的章节,删除后续完全相同的重复章节
 */
function handleRemoveDuplicates() {
  if (duplicates.value.length === 0) {
    ElMessage.info('没有检测到重复章节')
    return
  }
  
  ElMessageBox.confirm(
    `即将清理 ${duplicates.value.length} 组重复章节,保留第一个出现的章节,删除后续重复章节。是否继续?`,
    '确认清理重复章节',
    {
      confirmButtonText: '确认清理',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    removingDuplicates.value = true
    
    // 发射事件到父组件处理清理逻辑
    emit('remove-duplicates', {
      duplicates: duplicates.value,
      revisedContent: props.revisedContent
    })
    
    removingDuplicates.value = false
    ElMessage.success('重复章节已清理')
  }).catch(() => {
    // 用户取消
  })
}

// 监听对话框打开,自动检测重复章节
watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    console.log('[UnitSummariesReviseDialog] 对话框打开:', {
      originalLength: props.originalContent?.length || 0,
      revisedLength: props.revisedContent?.length || 0,
      changesCount: props.changes?.length || 0,
      qualityScore: props.qualityScore,
      totalIssues: props.totalIssues,
      criticalIssues: props.criticalIssuesCount
    })
    
    // 自动检测修正后内容的重复章节
    if (props.revisedContent) {
      duplicates.value = detectDuplicates(props.revisedContent)
      if (duplicates.value.length > 0) {
        console.log('[UnitSummariesReviseDialog] 检测到重复章节:', duplicates.value.length, '组')
      }
    }
  } else {
    // 关闭对话框时清空重复检测数据
    duplicates.value = []
  }
})
</script>

<style lang="scss">
/* 非scoped：el-dialog teleport内容到body时scoped样式失效 */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 13px;
  flex-wrap: wrap;

  .stat-item {
    display: flex;
    align-items: center;
    gap: 4px;

    .stat-label { color: #909399; }
    .stat-value { font-weight: 600; }

    &.changed .stat-value { color: #409eff; }
  }
}

.compare-view {
  display: flex;
  gap: 12px;
  min-height: 400px;
  max-height: 55vh;

  .compare-panel {
    flex: 1;
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    overflow: hidden;
    display: flex;
    flex-direction: column;

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      background: #fafafa;
      border-bottom: 1px solid #e4e7ed;

      .char-count { font-size: 12px; color: #909399; }
    }

    .content-text {
      flex: 1;
      overflow-y: auto;
      padding: 12px;
      margin: 0;
      font-size: 13px;
      line-height: 1.8;
      white-space: pre-wrap;
      word-break: break-all;
    }

    .content-text .diff-added {
      background-color: #d4edda;
      color: #155724;
      padding: 2px 0;
      border-radius: 2px;
      font-weight: 500;
    }

    .content-text .diff-removed {
      background-color: #f8d7da;
      color: #721c24;
      padding: 2px 0;
      border-radius: 2px;
      text-decoration: line-through;
      opacity: 0.8;
    }
  }
}

.changes-list {
  margin-top: 12px;

  .change-title {
    display: flex;
    align-items: center;
    gap: 8px;

    .change-location { font-size: 13px; font-weight: 500; }
  }

  .change-detail {
    font-size: 13px;
    line-height: 1.6;

    .change-text {
      padding: 6px 10px;
      border-radius: 4px;
      margin: 4px 0;
      white-space: pre-wrap;
    }

    .removed-text {
      background: #fef0f0;
      color: #f56c6c;
      text-decoration: line-through;
    }

    .added-text {
      background: #f0f9eb;
      color: #67c23a;
    }

    .change-reason, .change-suggestion {
      color: #909399;
      font-style: italic;
      margin-top: 4px;
    }
  }
}

.diff-summary {
  margin-top: 12px;
}

.duplicate-detection {
  margin-top: 12px;

  .duplicate-info {
    font-size: 13px;
    line-height: 1.6;
  }

  .duplicate-item {
    display: flex;
    align-items: center;
    padding: 4px 0;
    
    &:not(:last-child) {
      border-bottom: 1px dashed #e4e7ed;
      margin-bottom: 4px;
    }

    .duplicate-unit-num {
      margin-left: 8px;
      color: #909399;
      font-size: 12px;
    }
  }
}
</style>
