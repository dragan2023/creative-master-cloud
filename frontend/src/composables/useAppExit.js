/**
 * 退出程序组合式函数
 *
 * 承载"退出程序"入口的展示判断与退出流程（自首页迁移，逻辑保持不变）：
 * - 仅当后端明确返回本地桌面运行环境（local_desktop）时才展示退出入口
 * - 退出流程：确认弹窗 -> 调用后端退出接口 -> 尝试关闭窗口 -> 手动关闭提示
 */
import { ref } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { systemApi, RUNTIME_ENV_LOCAL_DESKTOP } from '@/api/system'

export function useAppExit() {
  const exiting = ref(false)
  // 默认不显示退出入口，后端明确返回 local_desktop 后才显示
  const isLocalDesktopEnv = ref(false)

  /** 查询后端运行环境，失败时保持不显示退出入口 */
  async function detectRuntimeEnvironment() {
    try {
      const envInfo = await systemApi.getRuntimeEnvironment()
      isLocalDesktopEnv.value = envInfo?.runtime_env === RUNTIME_ENV_LOCAL_DESKTOP
    } catch (error) {
      console.error('查询运行环境失败，隐藏退出程序入口:', error)
      isLocalDesktopEnv.value = false
    }
  }

  /** 确认并退出程序 */
  async function confirmAndExit() {
    try {
      await ElMessageBox.confirm(
        '确定要退出程序吗？\n\n退出后将关闭所有服务，请确保已保存所有工作。',
        '退出确认',
        {
          confirmButtonText: '确定退出',
          cancelButtonText: '取消',
          type: 'warning',
          distinguishCancelAndClose: true
        }
      )

      exiting.value = true
      ElMessage.info('正在关闭程序，请稍候...')

      try {
        // 调用后端退出接口
        const response = await systemApi.exit()

        if (response.success) {
          // 后端已开始退出流程
          ElMessage.success('服务已关闭')

          // 尝试关闭窗口
          setTimeout(() => {
            if (window.close) {
              try {
                window.close()
              } catch (e) {
                // 无法通过脚本关闭窗口（浏览器安全限制）
                showManualCloseTip()
              }
            } else {
              showManualCloseTip()
            }
          }, 500)
        }
      } catch (apiError) {
        // API调用失败，可能是后端已经退出导致连接中断
        console.log('后端已关闭:', apiError)
        ElMessage.success('服务已关闭')
        showManualCloseTip()
      }
    } catch (error) {
      // 用户取消或关闭对话框
      exiting.value = false
    }
  }

  /** 显示手动关闭提示 */
  function showManualCloseTip() {
    ElMessageBox.alert(
      '服务已成功关闭。\n\n由于浏览器安全限制，无法自动关闭窗口。\n请手动关闭此浏览器窗口或标签页。',
      '退出完成',
      {
        confirmButtonText: '我知道了',
        type: 'success',
        showClose: false,
        closeOnClickModal: false,
        closeOnPressEscape: false
      }
    ).finally(() => {
      exiting.value = false
    })
  }

  return {
    exiting,
    isLocalDesktopEnv,
    detectRuntimeEnvironment,
    confirmAndExit
  }
}
