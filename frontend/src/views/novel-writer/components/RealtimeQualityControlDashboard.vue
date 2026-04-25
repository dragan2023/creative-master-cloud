<!--
  实时质控可视化仪表盘 (v2.0)
  功能：
  1. 以对话框形式弹出，支持 v-model:visible 控制显示
  2. 实时显示各单元质控状态
  3. 点击单元查看详细问题和修正内容

  创建时间: 2026-04-17
  版本: 2.0 (对话框模式)
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="实时质控仪表盘"
    width="800px"
    destroy-on-close
    top="6vh"
  >
    <div class="realtime-qc-dashboard">
      <div v-if="unitQCList.length === 0" class="empty-state">
        <el-empty description="暂无质控数据，生成内容后将自动检测" :image-size="80" />
      </div>

      <div v-else>
        <!-- 概览统计 -->
        <div class="overview-stats" v-if="unitQCList.length > 0">
          <div class="stat-card completed">
            <span class="stat-value">{{ completedCount }}</span>
            <span class="stat-label">已完成</span>
          </div>
          <div class="stat-card running">
            <span class="stat-value">{{ runningCount }}</span>
            <span class="stat-label">检测中</span>
          </div>
          <div class="stat-card failed">
            <span class="stat-value">{{ failedCount }}</span>
            <span class="stat-label">失败</span>
          </div>
          <div class="stat-card avg-score">
            <span class="stat-value">{{ avgScore }}</span>
            <span class="stat-label">平均分</span>
          </div>
        </div>

        <!-- 单元列表 -->
        <div class="unit-list">
          <div
            v-for="item in unitQCList"
            :key="item.unitIndex"
            class="unit-qc-item"
            :class="{ active: activeUnit === item.unitIndex }"
            @click="activeUnit = item.unitIndex"
          >
            <div class="unit-info">
              <el-icon v-if="item.status === 'running'" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="item.status === 'completed'" color="#67c23a"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="item.status === 'failed'" color="#f56c6c"><CircleCloseFilled /></el-icon>
              <el-icon v-else color="#909399"><Clock /></el-icon>
              <span class="unit-label">第{{ item.unitIndex }}单元</span>
            </div>
            <div class="unit-score" v-if="item.score !== undefined">
              <el-progress
                type="circle"
                :percentage="Math.round(item.score)"
                :width="36"
                :color="getScoreColor(item.score)"
                :stroke-width="4"
              />
            </div>
            <div class="unit-meta">
              <span v-if="item.issuesCount !== undefined">{{ item.issuesCount }}个问题</span>
              <span v-if="item.fixedCount !== undefined">· {{ item.fixedCount }}个修正</span>
            </div>
          </div>
        </div>

        <!-- 问题详情 -->
        <div v-if="activeUnitData" class="detail-panel">
          <el-divider>第{{ activeUnitData.unitIndex }}单元 质控详情</el-divider>
          <div v-if="activeUnitData.issues && activeUnitData.issues.length" class="issue-list">
            <div v-for="(issue, idx) in activeUnitData.issues" :key="idx" class="issue-item">
              <el-tag :type="getSeverityType(issue.severity)" size="small">{{ issue.dimension || issue.severity }}</el-tag>
              <span class="issue-text">{{ issue.description }}</span>
            </div>
          </div>

          <!-- 修正对比 -->
          <div v-if="activeUnitData.fixesApplied && activeUnitData.fixesApplied.length" class="fix-panel">
            <div class="fix-header">
              <h5>修正内容对比</h5>
              <!-- 重复章节检测按钮 -->
              <el-button
                v-if="hasDuplicates"
                type="warning"
                size="small"
                @click="handleRemoveDuplicates"
                :loading="removingDuplicates"
              >
                <el-icon><Delete /></el-icon>
                清理重复章节 ({{ duplicates.length }}组)
              </el-button>
            </div>
            <div v-for="(fix, idx) in activeUnitData.fixesApplied" :key="idx" class="fix-item">
              <div class="fix-original">
                <strong>修正前:</strong>
                <div class="content-text" v-html="highlightDiff(fix.original_text, fix.fixed_text)"></div>
              </div>
              <div class="fix-revised">
                <strong>修正后:</strong>
                <div class="content-text" v-html="highlightDiff(fixedContentForRevised(fix.original_text, fix.fixed_text))"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Loading, CircleCheckFilled, CircleCloseFilled, Clock, Delete, WarningFilled } from '@element-plus/icons-vue'
import { diffChars } from 'diff'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: [String, Number], default: null },
  units: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:visible', 'close', 'remove-duplicates'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => {
    emit('update:visible', val)
    if (!val) emit('close')
  }
})

const unitQCList = reactive([])
const activeUnit = ref(null)
const activeUnitData = ref(null)

// 重复章节检测相关
const duplicates = ref([])
const removingDuplicates = ref(false)

// 统计计算
const completedCount = computed(() => unitQCList.filter(u => u.status === 'completed').length)
const runningCount = computed(() => unitQCList.filter(u => u.status === 'running').length)
const failedCount = computed(() => unitQCList.filter(u => u.status === 'failed').length)
const avgScore = computed(() => {
  const scored = unitQCList.filter(u => u.score !== undefined && u.score !== null)
  if (scored.length === 0) return '-'
  return (scored.reduce((sum, u) => sum + u.score, 0) / scored.length).toFixed(1)
})

const getScoreColor = (score) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

const getSeverityType = (severity) => {
  if (severity === 'high' || severity === '严重') return 'danger'
  if (severity === 'medium' || severity === '中等') return 'warning'
  return 'info'
}

/**
 * HTML转义
 */
function escapeHtml(text) {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

/**
 * 使用diffChars算法进行字符级差异高亮
 * @param {string} original - 修正前文本
 * @param {string} revised - 修正后文本
 * @returns {string} - 带HTML标签的高亮文本
 */
function highlightDiff(original, revised) {
  if (!original && !revised) return ''
  if (!original) return escapeHtml(revised || '')
  if (!revised) return escapeHtml(original || '')
  
  const diff = diffChars(original, revised)
  let html = ''
  
  diff.forEach((part) => {
    const escapedText = escapeHtml(part.value)
    
    if (part.added) {
      // 新增内容：绿色背景
      html += `<span class="diff-added">${escapedText}</span>`
    } else if (part.removed) {
      // 删除内容：红色背景 + 删除线
      html += `<span class="diff-removed">${escapedText}</span>`
    } else {
      // 未变化内容
      html += escapedText
    }
  })
  
  return html
}

// 从units prop初始化(兼容WritingWorkbench传入的单元数据)
watch(() => props.units, (newUnits) => {
  if (!newUnits || newUnits.length === 0) return
  for (const unit of newUnits) {
    if (unit.quality_control && unit.quality_control.status) {
      updateUnitQC(unit.unit_index || unit.chapter_number || unit.id, unit.quality_control)
    }
  }
}, { deep: true, immediate: true })

// 监听activeUnit变化,更新详情
watch(activeUnit, (unitIndex) => {
  activeUnitData.value = unitQCList.find(u => u.unitIndex === unitIndex) || null
  // 自动检测重复章节
  if (activeUnitData.value) {
    detectDuplicates(activeUnitData.value)
  }
})

// 计算是否有重复章节
const hasDuplicates = computed(() => duplicates.value.length > 0)

/**
 * 为修正后内容生成高亮HTML(显示新增部分)
 */
function fixedContentForRevised(original, revised) {
  if (!original && !revised) return ''
  if (!original) return escapeHtml(revised || '')
  
  const diff = diffChars(original, revised)
  let html = ''
  
  diff.forEach((part) => {
    const escapedText = escapeHtml(part.value)
    
    if (part.added) {
      html += `<span class="diff-added">${escapedText}</span>`
    } else if (!part.removed) {
      html += escapedText
    }
  })
  
  return html
}

/**
 * 检测重复章节
 * 以章节为单位,比较标题和内容的完全匹配
 */
function detectDuplicates(unitData) {
  if (!unitData || !unitData.fixesApplied) {
    duplicates.value = []
    return
  }
  
  const duplicateGroups = []
  const seen = new Map() // content -> first index
  
  unitData.fixesApplied.forEach((fix, index) => {
    const key = fix.fixed_text
    
    if (seen.has(key)) {
      // 找到重复章节
      const firstIndex = seen.get(key)
      let group = duplicateGroups.find(g => g.firstIndex === firstIndex)
      
      if (!group) {
        group = {
          groupIndex: duplicateGroups.length + 1,
          firstIndex: firstIndex,
          duplicates: [unitData.fixesApplied[firstIndex]]
        }
        duplicateGroups.push(group)
      }
      
      group.duplicates.push(fix)
    } else {
      seen.set(key, index)
    }
  })
  
  duplicates.value = duplicateGroups
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
  
  const totalDuplicates = duplicates.value.reduce((sum, g) => sum + g.duplicates.length - 1, 0)
  
  ElMessageBox.confirm(
    `即将清理 ${duplicates.value.length} 组重复章节(共${totalDuplicates}个),保留第一个出现的章节,删除后续重复章节。是否继续?`,
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
      unitIndex: activeUnit.value,
      duplicates: duplicates.value,
      unitData: activeUnitData.value
    })
    
    removingDuplicates.value = false
    ElMessage.success('重复章节已清理')
  }).catch(() => {
    // 用户取消
  })
}

// 暴露方法供父组件调用
const updateUnitQC = (unitIndex, qcData) => {
  console.log('[QC Dashboard] updateUnitQC 调用:', unitIndex, qcData)
  const existing = unitQCList.find(u => u.unitIndex === unitIndex)
  if (existing) {
    Object.assign(existing, {
      status: qcData.status || existing.status,
      score: qcData.score ?? existing.score,
      issuesCount: qcData.issues_count ?? qcData.issuesCount ?? existing.issuesCount,
      fixedCount: qcData.fixed_count ?? qcData.fixedCount ?? existing.fixedCount,
      issues: qcData.issues || existing.issues,
      fixesApplied: qcData.fixes_applied || qcData.fixesApplied || existing.fixesApplied
    })
  } else {
    unitQCList.push({
      unitIndex,
      status: qcData.status || 'pending',
      score: qcData.score,
      issuesCount: qcData.issues_count ?? qcData.issuesCount ?? 0,
      fixedCount: qcData.fixed_count ?? qcData.fixedCount ?? 0,
      issues: qcData.issues || [],
      fixesApplied: qcData.fixes_applied || qcData.fixesApplied || []
    })
  }

  // 更新活跃单元详情
  if (activeUnit.value === unitIndex) {
    activeUnitData.value = unitQCList.find(u => u.unitIndex === unitIndex)
  }
}

defineExpose({ updateUnitQC })
</script>

<style lang="scss">
/* 非scoped：el-dialog teleport内容到body时scoped样式失效 */
.realtime-qc-dashboard {
  .overview-stats {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;

    .stat-card {
      flex: 1;
      text-align: center;
      padding: 12px;
      border-radius: 8px;
      background: #f5f7fa;
      transition: transform 0.2s, box-shadow 0.2s;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      }

      .stat-value {
        display: block;
        font-size: 24px;
        font-weight: 700;
      }

      .stat-label {
        display: block;
        font-size: 12px;
        color: #909399;
        margin-top: 4px;
      }

      &.completed .stat-value { color: #67c23a; }
      &.running .stat-value { color: #409eff; }
      &.failed .stat-value { color: #f56c6c; }
      &.avg-score .stat-value { color: #e6a23c; }
    }
  }

  .unit-list {
    max-height: 300px;
    overflow-y: auto;
  }

  .unit-qc-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.25s ease;
    border: 1px solid transparent;

    &:hover {
      background: #f0f0f0;
      border-color: #e4e7ed;
    }

    &.active {
      background: #ecf5ff;
      border-color: #b3d8ff;
      box-shadow: 0 1px 4px rgba(64, 158, 255, 0.15);
    }

    .unit-info {
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 110px;

      .unit-label { font-weight: 500; }
    }

    .unit-score { flex-shrink: 0; }

    .unit-meta {
      font-size: 12px;
      color: #909399;
      margin-left: auto;
    }
  }

  .detail-panel {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #e4e7ed;

    h5 { margin: 0 0 8px; font-size: 14px; }

    .issue-item {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 6px;
      padding: 6px 8px;
      border-radius: 4px;
      transition: background 0.2s;

      &:hover { background: #fafafa; }
      .issue-text { font-size: 13px; flex: 1; }
    }

    .fix-panel {
      margin-top: 12px;

      .fix-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;

        h5 {
          margin: 0;
          font-size: 14px;
        }
      }

      .fix-item {
        margin-bottom: 12px;
        padding: 10px;
        background: #f5f7fa;
        border-radius: 6px;
        font-size: 13px;
        line-height: 1.6;
        transition: background 0.2s;

        &:hover { background: #ebeef5; }

        :deep(.diff-added) {
          background: #d4edda;
          color: #155724;
          padding: 2px 0;
          border-radius: 2px;
          font-weight: 500;
        }

        :deep(.diff-removed) {
          background: #f8d7da;
          color: #721c24;
          text-decoration: line-through;
          padding: 2px 0;
          border-radius: 2px;
          opacity: 0.8;
        }
      }
    }
  }
}
</style>
