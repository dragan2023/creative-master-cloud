<template>
  <div class="admin-dashboard">
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon users">
            <el-icon><User /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_users }}</div>
            <div class="stat-label">总用户数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon tenants">
            <el-icon><OfficeBuilding /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_tenants }}</div>
            <div class="stat-label">租户数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon projects">
            <el-icon><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_projects }}</div>
            <div class="stat-label">项目数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon active">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.active_users_today }}</div>
            <div class="stat-label">今日活跃</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="content-row">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>系统健康状态</span>
              <el-button type="primary" link @click="refreshHealth">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          <div class="health-status">
            <div class="health-item">
              <span class="health-label">数据库</span>
              <el-tag :type="health.database === 'healthy' ? 'success' : 'danger'">
                {{ health.database === 'healthy' ? '正常' : '异常' }}
              </el-tag>
            </div>
            <div class="health-item">
              <span class="health-label">Redis缓存</span>
              <el-tag :type="health.redis === 'healthy' ? 'success' : 'warning'">
                {{ health.redis === 'healthy' ? '正常' : health.redis === 'not_configured' ? '未配置' : '异常' }}
              </el-tag>
            </div>
            <div class="health-item">
              <span class="health-label">存储使用</span>
              <el-progress 
                :percentage="storagePercent" 
                :status="storagePercent > 80 ? 'exception' : ''"
                :format="() => `${health.storage_used_mb}MB / ${health.storage_total_mb}MB`"
              />
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span>快速操作</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/admin/users')">
              <el-icon><User /></el-icon>
              用户管理
            </el-button>
            <el-button type="success" @click="$router.push('/admin/tenants')">
              <el-icon><OfficeBuilding /></el-icon>
              租户管理
            </el-button>
            <el-button type="warning" @click="$router.push('/admin/logs')">
              <el-icon><Document /></el-icon>
              操作日志
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { User, OfficeBuilding, Document, TrendCharts, Refresh } from '@element-plus/icons-vue'
import { adminApi } from '@/api/admin'
import { ElMessage } from 'element-plus'

const stats = ref({
  total_users: 0,
  total_tenants: 0,
  active_users_today: 0,
  total_projects: 0,
  total_generations: 0,
  new_users_this_week: 0
})

const health = ref({
  database: 'healthy',
  redis: 'healthy',
  storage_used_mb: 0,
  storage_total_mb: 10240
})

const storagePercent = computed(() => {
  if (health.value.storage_total_mb === 0) return 0
  return Math.round((health.value.storage_used_mb / health.value.storage_total_mb) * 100)
})

const fetchDashboard = async () => {
  try {
    const res = await adminApi.getDashboard()
    if (res.data) {
      stats.value = res.data
    }
  } catch (error) {
    ElMessage.error('获取仪表盘数据失败')
  }
}

const refreshHealth = async () => {
  try {
    const res = await adminApi.getHealth()
    if (res.data) {
      health.value = res.data
      ElMessage.success('刷新成功')
    }
  } catch (error) {
    ElMessage.error('获取健康状态失败')
  }
}

onMounted(() => {
  fetchDashboard()
  refreshHealth()
})
</script>

<style scoped>
.admin-dashboard {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 10px;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 15px;
}

.stat-icon .el-icon {
  font-size: 30px;
  color: white;
}

.stat-icon.users {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.stat-icon.tenants {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.stat-icon.projects {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.stat-icon.active {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.content-row {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.health-status {
  padding: 10px 0;
}

.health-item {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
}

.health-item:last-child {
  margin-bottom: 0;
}

.health-label {
  width: 100px;
  color: #606266;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quick-actions .el-button {
  justify-content: flex-start;
}
</style>
