<!--
  组件: UnitRevisionDialog
  单元对话修正弹窗 - 上方内容编辑区 + 下方输入框的简洁修订界面
  
  界面布局：
  - 上方：内容编辑区（textarea），SSE流式重写时内容在此区域实时更新
  - 下方：修订指令输入框 + 提交按钮
  - 底部：退出修订 / 确认使用当前内容
  
  @date: 2026-06-03
  @version: v2.0.0（重构为上下布局）
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="`继续调整内容 - ${unitTitle || '单元 ' + unitIndex}`"
    width="900px"
    top="3vh"
    :close-on-click-modal="false"
    destroy-on-close
    class="unit-revision-dialog"
  >
    <!-- 上方：内容编辑区 -->
    <div class="revision-content-area">
      <div class="content-header">
        <span class="content-label">
          <el-icon><Document /></el-icon>
          修订内容
        </span>
        <div class="content-meta">
          <el-tag v-if="currentRevisionRound > 0" type="success" size="small" effect="plain">
            第 {{ currentRevisionRound }} 轮修订
          </el-tag>
          <span class="word-count" v-if="revisionContent">{{ revisionContent.length }} 字</span>
          <el-tag v-if="revising" type="warning" size="small" effect="dark">
            <el-icon class="is-loading"><Loading /></el-icon>
            AI正在重写...
          </el-tag>
        </div>
      </div>
      <el-input
        v-model="revisionContent"
        type="textarea"
        :rows="18"
        placeholder="修订内容将在此处实时显示..."
        :disabled="revising"
        class="content-textarea"
      />
      <!-- SSE 进度提示 -->
      <div v-if="revising" class="streaming-hint">
        <el-progress
          :percentage="streamProgress"
          :show-text="false"
          :stroke-width="4"
          :indeterminate="streamProgress === 0"
        />
        <span class="hint-text">AI 正在根据您的指令重写内容，请稍候...</span>
      </div>
    </div>

    <!-- 下方：修订指令输入区 -->
    <div class="revision-input-area">
      <div class="input-header">
        <span class="input-label">
          <el-icon><EditPen /></el-icon>
          修订指令
        </span>
      </div>
      <el-input
        v-model="revisionInput"
        type="textarea"
        :rows="3"
        placeholder="请输入修改意见，例如：把主角的性格描写得更果断一些、加强这段对话的张力..."
        :disabled="revising"
        @keyup.ctrl.enter="handleSubmitRevision"
        class="instruction-textarea"
      />
      <div class="input-actions">
        <el-text v-if="currentRevisionRound > 0" type="info" size="small">
          已进行 {{ currentRevisionRound }} 轮修订
        </el-text>
        <div class="action-buttons">
          <el-button
            type="primary"
            @click="handleSubmitRevision"
            :loading="revising"
            :disabled="!revisionInput.trim()"
          >
            <el-icon><Promotion /></el-icon>
            提交修订指令
          </el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="revision-footer">
        <el-button @click="handleExitRevision">
          <el-icon><Close /></el-icon>
          退出修订
        </el-button>
        <el-button type="success" @click="handleConfirmContent" :disabled="!revisionContent">
          <el-icon><Check /></el-icon>
          确认使用当前内容
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'
import {
  Loading, Document, Close, Promotion, Check,
  EditPen
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

const props = defineProps({
  visible: { type: Boolean, default: false },
  unitIndex: { type: Number, required: true },
  projectId: { type: Number, required: true },
  unitTitle: { type: String, default: '' },
  currentContent: { type: String, default: '' }
})

const emit = defineEmits([
  'update:visible',
  'content-updated'
])

// ==================== 状态 ====================
const revisionInput = ref('')
const revising = ref(false)
const revisionContent = ref('')
const revisionHistory = ref([])
const currentRevisionRound = ref(0)
const streamProgress = ref(0)  // SSE流进度指示

const abortRevisionRef = ref(null)  // SSE 流中断控制器

// ==================== 监听 ====================
watch(() => props.visible, (val) => {
  if (val) {
    // 初始化：设置当前内容
    revisionContent.value = props.currentContent
    revisionHistory.value = []
    currentRevisionRound.value = 0
    revisionInput.value = ''
    streamProgress.value = 0
  } else {
    // 对话框关闭时中断进行中的 SSE 流
    abortRevision()
  }
})

// 组件销毁时清理
onUnmounted(() => {
  abortRevision()
})

/** 中断当前 SSE 修订流 */
function abortRevision() {
  if (abortRevisionRef.value) {
    abortRevisionRef.value.abort()
    abortRevisionRef.value = null
  }
}

// ==================== 核心逻辑 ====================

/** 提交修订指令 */
async function handleSubmitRevision() {
  const feedback = revisionInput.value.trim()
  if (!feedback) return

  // 先中断上一轮未完成的流（如有）
  abortRevision()

  revisionInput.value = ''
  revising.value = true
  streamProgress.value = 0

  let contentBuffer = ''
  let doneReceived = false

  // 调用 SSE API：返回 { promise, abort } ，onMessage 接收已解析的 eventData
  const { promise, abort } = novelWriterApi.reviseUnitContent(
    props.unitIndex,
    {
      project_id: props.projectId,
      user_feedback: feedback,
      current_content: revisionContent.value,
      revision_history: revisionHistory.value
    },
    // onMessage - eventData 已经是解析后的 JSON 对象，如 {text: "..."}
    (eventData) => {
      if (eventData.text) {
        contentBuffer += eventData.text
        // 实时更新 textarea 内容：用 buffer 替换原内容
        revisionContent.value = contentBuffer
        // 模拟进度（基于内容增长）
        const estimatedTotal = Math.max(revisionContent.value.length * 1.2, 100)
        streamProgress.value = Math.min(Math.round((contentBuffer.length / estimatedTotal) * 90), 90)
      }
    },
    // onDone - eventData 是 {content: "..."}
    (eventData) => {
      doneReceived = true
      streamProgress.value = 100
      const finalContent = eventData.content || contentBuffer
      revisionContent.value = finalContent
      // 更新修订历史
      currentRevisionRound.value++
      revisionHistory.value.push({
        round_number: currentRevisionRound.value,
        user_feedback: feedback
      })

      ElMessage.success(`第 ${currentRevisionRound.value} 轮修订完成`)
    },
    // onError - error 是 Error 对象
    (error) => {
      console.error('[UnitRevisionDialog] 修订失败:', error)
      const errMsg = error.message || '未知错误'
      ElMessage.error('修订失败: ' + errMsg)
    }
  )

  abortRevisionRef.value = { abort }

  try {
    await promise

    // 兜底：如果 done 事件未被触发，用 buffer 作为最终内容
    if (!doneReceived && contentBuffer) {
      revisionContent.value = contentBuffer
      currentRevisionRound.value++
      revisionHistory.value.push({
        round_number: currentRevisionRound.value,
        user_feedback: feedback
      })
      ElMessage.success(`第 ${currentRevisionRound.value} 轮修订完成`)
    }
  } catch (error) {
    console.error('[UnitRevisionDialog] 修订异常:', error)
    if (!doneReceived) {
      ElMessage.error('修订异常: ' + (error.message || '未知错误'))
    }
  } finally {
    revising.value = false
    abortRevisionRef.value = null
  }
}

/** 退出修订 */
function handleExitRevision() {
  emit('update:visible', false)
}

/** 确认使用当前修订内容 */
async function handleConfirmContent() {
  if (!revisionContent.value) {
    ElMessage.warning('没有可用的修订内容')
    return
  }

  try {
    await novelWriterApi.updateUnitContent({
      unit_index: props.unitIndex,
      content: revisionContent.value,
      project_id: props.projectId,
      save_as: 'self_revise'
    })

    ElMessage.success('内容已保存，最终修正完成')
    emit('content-updated', {
      unit_index: props.unitIndex,
      content: revisionContent.value,
      version: 'self_revise',
    })
    emit('update:visible', false)
  } catch (error) {
    console.error('[UnitRevisionDialog] 保存失败:', error)
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  }
}
</script>

<style lang="scss" scoped>
.unit-revision-dialog {
  .revision-content-area {
    margin-bottom: 20px;

    .content-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;

      .content-label {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 14px;
        font-weight: 600;
        color: #303133;
      }

      .content-meta {
        display: flex;
        align-items: center;
        gap: 10px;

        .word-count {
          font-size: 12px;
          color: #909399;
        }
      }
    }

    .content-textarea {
      :deep(.el-textarea__inner) {
        font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
        font-size: 14px;
        line-height: 1.8;
        min-height: 380px;
      }
    }

    .streaming-hint {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 12px;
      margin-top: 8px;
      background: #fdf6ec;
      border-radius: 6px;
      border: 1px solid #faecd8;

      .el-progress {
        flex: 1;
        max-width: 200px;
      }

      .hint-text {
        font-size: 13px;
        color: #e6a23c;
      }
    }
  }

  .revision-input-area {
    padding: 16px;
    background: #fafafa;
    border-radius: 8px;
    border: 1px solid #ebeef5;

    .input-header {
      margin-bottom: 10px;

      .input-label {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        font-weight: 600;
        color: #606266;
      }
    }

    .instruction-textarea {
      :deep(.el-textarea__inner) {
        font-size: 13px;
        line-height: 1.6;
      }
    }

    .input-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 12px;

      .action-buttons {
        display: flex;
        gap: 8px;
        margin-left: auto;
      }
    }
  }

  .revision-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
}
</style>
