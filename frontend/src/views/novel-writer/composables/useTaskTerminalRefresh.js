/**
 * useTaskTerminalRefresh - 任务终态内容校准（阶段03 §3.5）
 *
 * 职责：监听写作任务从 running 进入终态（completed/failed/interrupted）时，
 * 刷新一次单元内容（fetchUnits），保证工作台正文与后端最终落库内容一致。
 *
 * 约束：
 * - 仅“运行中 → 终态”迁移触发；每个运行代次最多校准一次
 * - 连接关闭由Store消息处理层统一负责，本组件watcher不持有连接所有权
 * - 初次加载即为终态的任务不重复刷新
 *   （fetchCurrentTask 已在加载时拉取过单元列表）
 */
import { watch } from 'vue'

const TERMINAL_TASK_STATUSES = ['completed', 'failed', 'interrupted']

export function useTaskTerminalRefresh(writingStore) {
  watch(
    () => writingStore.currentTask?.status,
    async (status, prevStatus) => {
      if (prevStatus !== 'running' || !TERMINAL_TASK_STATUSES.includes(status)) return
      const taskId = writingStore.currentTask?.id
      if (!taskId) return
      try {
        await writingStore.fetchUnits(taskId)
        console.log('[WritingWorkbench] 任务终态内容校准完成: taskId=%s, status=%s', taskId, status)
      } catch (error) {
        console.error('[WritingWorkbench] 任务终态内容校准失败: taskId=' + taskId, error)
      }
    }
  )
}
