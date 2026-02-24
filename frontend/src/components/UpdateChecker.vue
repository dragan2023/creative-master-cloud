<template>
  <div class="update-checker">
    <!-- 更新提示对话框 -->
    <el-dialog
      v-model="showDialog"
      :title="updateInfo?.is_critical ? '发现重要更新' : '发现新版本'"
      width="600px"
      :close-on-click-modal="!updateInfo?.force_update"
      :close-on-press-escape="!updateInfo?.force_update"
      :show-close="!updateInfo?.force_update"
    >
      <div class="update-content">
        <!-- 版本信息 -->
        <div class="version-info">
          <div class="version-row">
            <span class="label">当前版本：</span>
            <span class="value current">{{ currentVersion }}</span>
          </div>
          <div class="version-row">
            <span class="label">最新版本：</span>
            <span class="value latest">{{ updateInfo?.latest_version }}</span>
            <el-tag v-if="updateInfo?.is_critical" type="danger" size="small" style="margin-left: 8px">
              重要更新
            </el-tag>
          </div>
          <div class="version-row">
            <span class="label">发布日期：</span>
            <span class="value">{{ updateInfo?.release_date }}</span>
          </div>
          <div class="version-row">
            <span class="label">文件大小：</span>
            <span class="value">{{ updateInfo?.file_size_mb }} MB</span>
          </div>
        </div>

        <!-- 更新说明 -->
        <div class="update-notes">
          <div class="notes-header">更新说明</div>
          <div class="notes-content" v-html="formattedUpdateNotes"></div>
        </div>

        <!-- 下载进度 -->
        <div v-if="isDownloading" class="download-progress">
          <el-progress
            :percentage="downloadProgress"
            :status="downloadProgress === 100 ? 'success' : ''"
            :stroke-width="10"
          />
          <div class="progress-info">
            <span>{{ downloadedMB }} MB / {{ totalMB }} MB</span>
            <span v-if="downloadSpeed"> - {{ downloadSpeed }} MB/s</span>
            <span v-if="eta"> - 剩余 {{ eta }}</span>
          </div>
        </div>

        <!-- 错误提示 -->
        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="false"
          style="margin-top: 16px"
        />
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button
            v-if="!updateInfo?.force_update && !isDownloading"
            @click="skipUpdate"
          >
            跳过此版本
          </el-button>
          <el-button
            v-if="!isDownloading"
            @click="showDialog = false"
          >
            稍后提醒
          </el-button>
          <el-button
            type="primary"
            :loading="isDownloading"
            @click="startDownload"
          >
            {{ isDownloading ? '下载中...' : '立即更新' }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 手动检查按钮（可选） -->
    <slot name="trigger" :check="checkUpdate" :loading="checking">
      <el-button
        v-if="showManualCheck"
        :loading="checking"
        @click="checkUpdate"
        circle
        :icon="Refresh"
        title="检查更新"
      />
    </slot>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { updateApi } from '@/api'

const props = defineProps({
  // 是否显示手动检查按钮
  showManualCheck: {
    type: Boolean,
    default: false
  },
  // 是否自动检查（应用启动时）
  autoCheck: {
    type: Boolean,
    default: true
  },
  // 自动检查延迟（秒）
  autoCheckDelay: {
    type: Number,
    default: 3
  },
  // 当前版本号（从环境变量或配置获取）
  currentVersion: {
    type: String,
    default: '1.0.0'
  }
})

const emit = defineEmits(['update-available', 'no-update', 'download-complete'])

// 状态
const showDialog = ref(false)
const checking = ref(false)
const isDownloading = ref(false)
const downloadProgress = ref(0)
const downloadedMB = ref(0)
const totalMB = ref(0)
const downloadSpeed = ref(null)
const eta = ref(null)
const errorMessage = ref('')
const updateInfo = ref(null)
const skippedVersions = ref(new Set())

// 计算属性
const formattedUpdateNotes = computed(() => {
  if (!updateInfo.value?.update_notes) return ''
  // 将 Markdown 风格的换行转换为 HTML
  return updateInfo.value.update_notes
    .replace(/\n/g, '<br>')
    .replace(/## /g, '<strong>')
    .replace(/### /g, '<strong>')
})

// 检查更新
async function checkUpdate() {
  if (checking.value) return
  
  checking.value = true
  errorMessage.value = ''
  
  try {
    const response = await updateApi.check(props.currentVersion)
    const data = response.data
    
    if (data.has_update) {
      // 检查是否跳过此版本
      if (skippedVersions.value.has(data.latest_version) && !data.force_update) {
        return
      }
      
      updateInfo.value = data
      showDialog.value = true
      emit('update-available', data)
    } else {
      emit('no-update')
      ElMessage.success('当前已是最新版本')
    }
  } catch (error) {
    console.error('检查更新失败:', error)
    // 静默失败，不打扰用户
  } finally {
    checking.value = false
  }
}

// 跳过此版本
function skipUpdate() {
  if (updateInfo.value?.latest_version) {
    skippedVersions.value.add(updateInfo.value.latest_version)
    // 保存到 localStorage
    localStorage.setItem('skippedVersions', JSON.stringify([...skippedVersions.value]))
  }
  showDialog.value = false
}

// 开始下载
async function startDownload() {
  if (!updateInfo.value?.download_url) {
    errorMessage.value = '下载地址不可用'
    return
  }
  
  isDownloading.value = true
  downloadProgress.value = 0
  errorMessage.value = ''
  
  try {
    // 模拟下载进度（实际下载需要在后端进行，因为浏览器有安全限制）
    // 这里我们打开下载链接让用户下载
    const downloadUrl = updateInfo.value.download_url
    
    // 使用浏览器下载
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `creative-master-v${updateInfo.value.latest_version}.zip`
    link.target = '_blank'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    // 显示下载提示
    ElNotification({
      title: '下载已开始',
      message: '请在浏览器下载管理器中查看下载进度。下载完成后请解压并运行 start.bat',
      type: 'success',
      duration: 0
    })
    
    emit('download-complete')
    showDialog.value = false
    
  } catch (error) {
    console.error('下载失败:', error)
    errorMessage.value = '下载失败，请稍后重试或手动下载'
  } finally {
    isDownloading.value = false
  }
}

// 从 localStorage 加载跳过的版本
function loadSkippedVersions() {
  try {
    const saved = localStorage.getItem('skippedVersions')
    if (saved) {
      skippedVersions.value = new Set(JSON.parse(saved))
    }
  } catch (error) {
    console.error('加载跳过版本失败:', error)
  }
}

// 组件挂载
onMounted(() => {
  loadSkippedVersions()
  
  if (props.autoCheck) {
    setTimeout(() => {
      checkUpdate()
    }, props.autoCheckDelay * 1000)
  }
})

// 暴露方法给父组件
defineExpose({
  checkUpdate
})
</script>

<style scoped>
.update-content {
  max-height: 60vh;
  overflow-y: auto;
}

.version-info {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.version-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.version-row:last-child {
  margin-bottom: 0;
}

.version-row .label {
  color: #909399;
  width: 80px;
  flex-shrink: 0;
}

.version-row .value {
  color: #303133;
}

.version-row .value.current {
  color: #909399;
}

.version-row .value.latest {
  color: #409eff;
  font-weight: bold;
}

.update-notes {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.notes-header {
  background: #f5f7fa;
  padding: 12px 16px;
  font-weight: bold;
  border-bottom: 1px solid #e4e7ed;
}

.notes-content {
  padding: 16px;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}

.download-progress {
  margin-top: 16px;
}

.progress-info {
  text-align: center;
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
