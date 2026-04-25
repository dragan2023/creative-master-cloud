<!--
  全局大纲修正对比对话框 (v2.4)
  功能：
  1. 并排显示修正前后的大纲内容
  2. 字符级差异高亮（使用diff库的diffChars算法）
  3. 差异统计（新增/删除/修改字数）
  4. 用户确认或取消修正

  依赖：npm包 diff (diffChars)
  创建时间: 2026-04-17
  版本: 2.4 (含差异高亮)
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="全局大纲修正对比"
    width="90%"
    destroy-on-close
    :close-on-click-modal="false"
    top="4vh"
  >
    <!-- 统计信息栏 -->
    <div class="stats-bar" v-if="dialogVisible">
      <div class="stat-item">
        <span class="stat-label">原始长度</span>
        <span class="stat-value">{{ originalLength || (originalContent?.length || 0) }} 字</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">修正长度</span>
        <span class="stat-value">{{ revisedLength || (revisedContent?.length || 0) }} 字</span>
      </div>
      <el-divider direction="vertical" />
      <div class="stat-item">
        <span class="stat-label">变化量</span>
        <span class="stat-value changed">{{ diffStats.totalChanged }} 字</span>
      </div>
      <div class="stat-item added">
        <span class="stat-label">新增</span>
        <span class="stat-value">+{{ diffStats.added }} 字</span>
      </div>
      <div class="stat-item removed">
        <span class="stat-label">删除</span>
        <span class="stat-value">-{{ diffStats.removed }} 字</span>
      </div>
      <div class="stat-item" v-if="changes.length > 0">
        <el-tag type="warning" size="small">{{ changes.length }} 处修改</el-tag>
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

    <!-- 修改列表 -->
    <div class="changes-list" v-if="changes.length > 0">
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
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <template #footer>
      <el-button @click="handleCancel">保留原始内容</el-button>
      <el-button type="primary" @click="handleConfirm">应用修正</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, watch, nextTick } from 'vue'
import { diffChars } from 'diff'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  originalContent: { type: String, default: '' },
  revisedContent: { type: String, default: '' },
  changes: { type: Array, default: () => [] },
  originalLength: { type: Number, default: 0 },
  revisedLength: { type: Number, default: 0 }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// HTML转义（防止XSS）
function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// 差异高亮计算
function computeDiffHtml() {
  const original = props.originalContent || ''
  const revised = props.revisedContent || ''

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
    if (part.added) {
      added += part.value.length
    } else if (part.removed) {
      removed += part.value.length
    }
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
  // 延迟关闭对话框，确保confirm事件先处理完
  nextTick(() => { dialogVisible.value = false })
}

function handleCancel() {
  emit('cancel')
  nextTick(() => { dialogVisible.value = false })
}

// 调试日志
watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    console.log('========== [GlobalOutlineReviseDialog] 对话框状态变化 ==========')
    console.log('newVal (visible):', newVal)
    console.log('originalContent长度:', props.originalContent?.length || 0)
    console.log('revisedContent长度:', props.revisedContent?.length || 0)
    console.log('changes数量:', props.changes?.length || 0)
    console.log('originalLength:', props.originalLength)
    console.log('revisedLength:', props.revisedLength)
    console.log('===============================================================')
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

    &.added .stat-value { color: #67c23a; }
    &.removed .stat-value { color: #f56c6c; }
    &.changed .stat-value { color: #409eff; }
  }
}

.compare-view {
  display: flex;
  gap: 12px;
  min-height: 400px;
  max-height: 60vh;

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

      :deep(.diff-added) {
        background-color: #d4edda;
        color: #155724;
        padding: 2px 0;
        border-radius: 2px;
        font-weight: 500;
      }

      :deep(.diff-removed) {
        background-color: #f8d7da;
        color: #721c24;
        padding: 2px 0;
        border-radius: 2px;
        text-decoration: line-through;
        opacity: 0.8;
      }
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

    .change-reason {
      color: #909399;
      font-style: italic;
    }
  }
}
</style>
