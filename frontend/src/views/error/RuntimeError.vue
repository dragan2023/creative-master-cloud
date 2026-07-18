<template>
  <div class="runtime-error">
    <el-result icon="error" title="当前页面加载异常">
      <template #sub-title>
        <p class="error-hint">页面遇到意外错误，您可以重试当前页面或返回首页。</p>
        <div class="error-id-row">
          <span class="error-id-label">错误标识：</span>
          <code class="error-id">{{ errorId }}</code>
          <el-button text type="primary" size="small" @click="copyErrorId">
            {{ copied ? '已复制' : '复制' }}
          </el-button>
        </div>
      </template>
      <template #extra>
        <el-button type="primary" @click="emit('retry')">重试当前页面</el-button>
        <el-button @click="emit('back-home')">返回首页</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup>
/**
 * 可恢复运行时错误界面
 *
 * 子页面抛出未捕获异常时由 MainLayout 渲染。
 * 只接收错误标识和回调，不显示原始堆栈或敏感请求内容。
 */
import { ref } from 'vue'

const props = defineProps({
  /** 可复制的错误标识，用于用户反馈时定位控制台日志 */
  errorId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['retry', 'back-home'])

const copied = ref(false)

/** 复制错误标识，剪贴板不可用时降级为输入框选中复制 */
async function copyErrorId() {
  try {
    await navigator.clipboard.writeText(props.errorId)
    copied.value = true
  } catch (clipboardError) {
    console.warn('[RuntimeError] 剪贴板不可用，使用降级复制', clipboardError)
    copied.value = fallbackCopy(props.errorId)
  }
  if (copied.value) {
    setTimeout(() => { copied.value = false }, 2000)
  }
}

/** execCommand 降级复制（旧浏览器/非安全上下文） */
function fallbackCopy(text) {
  const input = document.createElement('textarea')
  input.value = text
  document.body.appendChild(input)
  input.select()
  let succeeded = false
  try {
    succeeded = document.execCommand('copy')
  } catch (execError) {
    console.warn('[RuntimeError] 降级复制失败', execError)
  }
  document.body.removeChild(input)
  return succeeded
}
</script>

<style lang="scss" scoped>
.runtime-error {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;

  .error-hint {
    margin: 0 0 12px;
    color: #606266;
    font-size: 14px;
  }

  .error-id-row {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: #f5f7fa;
    border-radius: 8px;

    .error-id-label {
      font-size: 13px;
      color: #909399;
    }

    .error-id {
      font-family: monospace;
      font-size: 13px;
      color: #303133;
      user-select: all;
    }
  }
}
</style>
