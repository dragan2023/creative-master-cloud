<!--
  ContentQCFixDialog.vue - 修正预览与选择对话框
  
  功能：
  1. 显示修正前原文与修正后内容对比
  2. 选择性应用修正（勾选要应用的修正）
  3. 撤销已应用的修正
  4. 清晰的diff可视化
  
  设计原则：
  - 全面：展示所有修正建议
  - 客观：保留用户选择权
  - 高效：直观对比，快速操作
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="修正预览与选择"
    width="90%"
    :fullscreen="false"
    destroy-on-close
    top="5vh"
    class="fix-dialog"
  >
    <div v-if="loading" class="fix-loading">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else class="fix-content">
      <!-- 问题信息 -->
      <div class="issue-info" v-if="currentIssue">
        <el-tag :type="getSeverityType(currentIssue.severity)" size="small">
          {{ currentIssue.severity }}
        </el-tag>
        <span class="issue-category">{{ currentIssue.dimension }} · {{ currentIssue.category }}</span>
        <p class="issue-desc">{{ currentIssue.description }}</p>
      </div>

      <el-divider />

      <!-- 内容对比区域 -->
      <div class="content-compare">
        <div class="compare-header">
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="diff">差异对比</el-radio-button>
            <el-radio-button value="full">全文对比</el-radio-button>
          </el-radio-group>
          <span class="compare-info">
            原文 {{ originalLength }} 字 → 修正后 {{ fixedLength }} 字
            <el-tag 
              v-if="changeRatio > 0.1" 
              type="warning" 
              size="small"
            >
              修改幅度 {{ Math.round(changeRatio * 100) }}%
            </el-tag>
          </span>
        </div>

        <div class="compare-body">
          <!-- 差异对比模式 -->
          <div v-if="viewMode === 'diff'" class="diff-view">
            <div class="diff-column original">
              <h5>原文（红色为被删除部分）</h5>
              <div class="diff-text" v-html="diffHtml.original"></div>
            </div>
            <div class="diff-column fixed">
              <h5>修正后（绿色为新增部分）</h5>
              <div class="diff-text" v-html="diffHtml.fixed"></div>
            </div>
          </div>

          <!-- 全文对比模式 -->
          <div v-else class="full-view">
            <el-tabs v-model="fullViewTab">
              <el-tab-pane label="原文" name="original">
                <div class="full-text original-text">{{ originalContent }}</div>
              </el-tab-pane>
              <el-tab-pane label="修正后" name="fixed">
                <div class="full-text fixed-text">{{ fixedContent }}</div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </div>
      </div>

      <el-divider />

      <!-- 修正选择区域（多选） -->
      <div class="fix-selection" v-if="availableFixes.length > 0">
        <h4>选择要应用的修正</h4>
        <el-checkbox-group v-model="selectedFixIds">
          <div v-for="fix in availableFixes" :key="fix.issue_id" class="fix-item">
            <el-checkbox :value="fix.issue_id">
              <span class="fix-category">{{ fix.category }}</span>
              <span class="fix-desc">{{ fix.description || fix.auto_fix?.description }}</span>
              <el-tag size="small" type="info">
                置信度 {{ Math.round((fix.auto_fix?.confidence || 0) * 100) }}%
              </el-tag>
            </el-checkbox>
          </div>
        </el-checkbox-group>
      </div>

      <!-- 修正说明 -->
      <div class="fix-note">
        <el-alert
          type="info"
          :closable="false"
          show-icon
        >
          <template #title>
            <span>修正说明</span>
          </template>
          <p>应用修正后，原文将被替换为修正后的内容。如不满意，可在质控面板中撤销修正。</p>
          <p v-if="changeRatio > 0.3" style="color: #e6a23c;">
            注意：本次修改幅度较大（>30%），请仔细检查修正内容是否偏离原意。
          </p>
        </el-alert>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button 
          v-if="hasAppliedFixes"
          type="warning"
          @click="handleRevert"
        >
          <el-icon><RefreshLeft /></el-icon>
          撤销修正
        </el-button>
        <el-button
          type="primary"
          :disabled="selectedFixIds.length === 0"
          :loading="applying"
          @click="handleApply"
        >
          <el-icon><Check /></el-icon>
          应用选中的修正 ({{ selectedFixIds.length }})
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { RefreshLeft, Check } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { diffChars } from 'diff'
import { getSeverityType } from '../composables/useContentQualityControl'

const props = defineProps({
  visible: { type: Boolean, default: false },
  unitIndex: { type: Number, default: null },
  issue: { type: Object, default: null },
  fixes: { type: Array, default: () => [] },
  originalContent: { type: String, default: '' },
  fixedContent: { type: String, default: '' },
  hasAppliedFixes: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'apply-fixes', 'revert-fix', 'preview-fix'])

// 对话框可见性
const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

// 状态
const loading = ref(false)
const applying = ref(false)
const viewMode = ref('diff')
const fullViewTab = ref('original')
const selectedFixIds = ref([])

// 当前问题
const currentIssue = computed(() => props.issue)

// 可用修正列表
const availableFixes = computed(() => {
  // 如果传入的是单个issue，从它的auto_fix构建
  if (props.issue?.auto_fix) {
    return [{
      issue_id: props.issue.id,
      category: props.issue.category,
      description: props.issue.auto_fix.description,
      auto_fix: props.issue.auto_fix
    }]
  }
  // 否则使用传入的fixes数组
  return props.fixes || []
})

// 内容长度
const originalLength = computed(() => props.originalContent?.length || 0)
const fixedLength = computed(() => props.fixedContent?.length || 0)

// 修改幅度
const changeRatio = computed(() => {
  if (originalLength.value === 0) return 0
  return Math.abs(fixedLength.value - originalLength.value) / originalLength.value
})

// 原文与修正后内容
const originalContent = computed(() => props.originalContent || '')
const fixedContent = computed(() => props.fixedContent || '')

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
 * 生成差异高亮HTML
 */
const diffHtml = computed(() => {
  const original = originalContent.value
  const fixed = fixedContent.value
  
  if (!original && !fixed) {
    return { original: '', fixed: '' }
  }
  
  const diff = diffChars(original || '', fixed || '')
  
  // 原文视图：显示删除部分（红色）
  let originalHtml = ''
  diff.forEach(part => {
    const escaped = escapeHtml(part.value)
    if (part.removed) {
      originalHtml += `<span class="diff-removed">${escaped}</span>`
    } else if (!part.added) {
      originalHtml += escaped
    }
  })
  
  // 修正视图：显示新增部分（绿色）
  let fixedHtml = ''
  diff.forEach(part => {
    const escaped = escapeHtml(part.value)
    if (part.added) {
      fixedHtml += `<span class="diff-added">${escaped}</span>`
    } else if (!part.removed) {
      fixedHtml += escaped
    }
  })
  
  return { original: originalHtml, fixed: fixedHtml }
})

/**
 * 应用选中的修正
 */
async function handleApply() {
  if (selectedFixIds.value.length === 0) {
    ElMessage.warning('请选择要应用的修正')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认应用 ${selectedFixIds.value.length} 个修正？原文将被替换。`,
      '确认应用修正',
      {
        confirmButtonText: '确认应用',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    applying.value = true
    emit('apply-fixes', {
      unitIndex: props.unitIndex,
      fixIds: selectedFixIds.value
    })
    
    // 等待父组件处理完成后关闭对话框
    dialogVisible.value = false
  } catch (e) {
    if (e !== 'cancel') {
      console.error('[修正对话框] 应用修正失败:', e)
    }
  } finally {
    applying.value = false
  }
}

/**
 * 撤销修正
 */
async function handleRevert() {
  try {
    await ElMessageBox.confirm(
      '确认撤销修正？内容将恢复为原文。',
      '撤销修正',
      {
        confirmButtonText: '确认撤销',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    emit('revert-fix', { unitIndex: props.unitIndex })
    dialogVisible.value = false
  } catch (e) {
    if (e !== 'cancel') {
      console.error('[修正对话框] 撤销修正失败:', e)
    }
  }
}

// 重置选中状态
watch(dialogVisible, (val) => {
  if (!val) {
    selectedFixIds.value = []
    viewMode.value = 'diff'
  } else {
    // 打开时默认选中高置信度修正
    availableFixes.value.forEach(fix => {
      if (fix.auto_fix?.confidence >= 0.8) {
        selectedFixIds.value.push(fix.issue_id)
      }
    })
  }
})
</script>

<style lang="scss">
/* 非scoped：dialog内容teleport到body */
.fix-dialog {
  .fix-content {
    .issue-info {
      padding: 12px;
      background: #f5f7fa;
      border-radius: 6px;
      margin-bottom: 12px;

      .issue-category {
        margin-left: 8px;
        color: #909399;
        font-size: 13px;
      }

      .issue-desc {
        margin-top: 8px;
        font-size: 14px;
        line-height: 1.6;
      }
    }

    .content-compare {
      .compare-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;

        .compare-info {
          font-size: 13px;
          color: #909399;
          display: flex;
          align-items: center;
          gap: 8px;
        }
      }

      .compare-body {
        min-height: 200px;
        max-height: 400px;
        overflow-y: auto;
        overflow-x: hidden; // 防止横向溢出

        .diff-view {
          display: flex;
          gap: 16px;

          .diff-column {
            flex: 1;
            min-width: 0; // 允许收缩
            border: 1px solid #e4e7ed;
            border-radius: 6px;
            padding: 12px;
            overflow: hidden; // 防止内容溢出边框

            h5 {
              margin: 0 0 8px;
              font-size: 13px;
              color: #909399;
            }

            .diff-text {
              font-size: 13px;
              line-height: 1.8;
              white-space: pre-wrap;
              word-break: break-word; // 允许长单词换行
              overflow-wrap: break-word; // 兼容性更好

              .diff-removed {
                background: #fde2e2;
                color: #f56c6c;
                text-decoration: line-through;
                padding: 2px 0;
                border-radius: 2px;
              }

              .diff-added {
                background: #d4edda;
                color: #155724;
                padding: 2px 0;
                border-radius: 2px;
              }
            }
          }
        }

        .full-view {
          .full-text {
            font-size: 13px;
            line-height: 1.8;
            white-space: pre-wrap;
            word-break: break-word; // 允许长单词换行
            overflow-wrap: break-word; // 兼容性更好
            padding: 12px;
            background: #f5f7fa;
            border-radius: 6px;
            min-height: 200px;
            overflow: auto; // 允许滚动
          }
        }
      }
    }

    .fix-selection {
      margin-top: 12px;

      h4 { margin-bottom: 12px; font-size: 14px; }

      .fix-item {
        margin-bottom: 8px;
        padding: 10px 12px;
        background: #f5f7fa;
        border-radius: 6px;
        transition: background 0.2s;
        overflow: hidden; // 防止内容溢出

        &:hover { background: #ebeef5; }

        .el-checkbox {
          display: flex;
          align-items: flex-start; // 改为顶部对齐，适配多行文本
          gap: 8px;
          width: 100%; // 占满宽度
          line-height: 1.6; // 统一行高
        }

        .fix-category {
          font-weight: 500;
          min-width: 80px;
          flex-shrink: 0; // 防止被压缩
        }

        .fix-desc {
          color: #606266;
          flex: 1;
          min-width: 0; // 允许收缩
          word-break: break-word; // 允许长单词换行
          overflow-wrap: break-word; // 兼容性更好
          line-height: 1.6; // 增加行高提升可读性
        }

        .el-tag {
          flex-shrink: 0; // 防止标签被压缩
          margin-left: 8px;
        }
      }
    }

    .fix-note {
      margin-top: 12px;

      p { margin-bottom: 4px; font-size: 12px; }
    }
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
}
</style>