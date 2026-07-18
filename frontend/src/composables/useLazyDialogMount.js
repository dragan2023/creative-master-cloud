/**
 * useLazyDialogMount - 低频弹窗懒挂载标记
 *
 * 配合 defineAsyncComponent 使用：弹窗组件首次打开前不渲染（异步 chunk 不加载），
 * 首次打开后保持挂载，避免关闭时销毁导致的离场动画丢失与内部状态重置。
 *
 * 用法：
 *   const importDialogMounted = useLazyDialogMount(showImportDialog)
 *   <ImportDialog v-if="importDialogMounted" v-model="showImportDialog" ... />
 *
 * @param {import('vue').Ref<boolean>|(() => boolean)} visibleSource - 弹窗可见状态 ref 或 getter
 * @returns {import('vue').Ref<boolean>} 是否应挂载该弹窗
 */
import { ref, watch, unref } from 'vue'

export function useLazyDialogMount(visibleSource) {
  const initialVisible = typeof visibleSource === 'function'
    ? !!visibleSource()
    : !!unref(visibleSource)
  const everOpened = ref(initialVisible)

  if (!everOpened.value) {
    const stopWatch = watch(visibleSource, (isVisible) => {
      if (isVisible) {
        everOpened.value = true
        stopWatch()
      }
    })
  }

  return everOpened
}
