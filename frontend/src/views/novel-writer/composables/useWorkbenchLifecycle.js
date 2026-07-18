/**
 * 注册 WritingWorkbench 的资源清理生命周期。
 *
 * 保持断连所有权集中且可通过轻量 Vue harness 验证。
 */
import { onUnmounted } from 'vue'

export function useWorkbenchLifecycle(writingStore) {
  onUnmounted(() => {
    writingStore.disconnectWebSocket()
  })
}
