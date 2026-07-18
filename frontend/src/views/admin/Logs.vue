<template>
  <div class="logs-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统日志</span>
          <el-button @click="refreshLogs">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      
      <el-table :data="logs" v-loading="loading" stripe max-height="600">
        <el-table-column prop="timestamp" label="时间" width="180" />
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="getLevelType(row.level)">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="150" />
        <el-table-column prop="message" label="消息" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const logs = ref([])

const getLevelType = (level) => {
  const types = {
    'INFO': 'info',
    'WARNING': 'warning',
    'ERROR': 'danger',
    'DEBUG': ''
  }
  return types[level] || ''
}

const refreshLogs = async () => {
  loading.value = true
  try {
    // TODO: 调用API获取日志
    logs.value = []
    ElMessage.success('日志已刷新')
  } catch (error) {
    ElMessage.error('获取日志失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refreshLogs()
})
</script>

<style scoped>
.logs-view {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
