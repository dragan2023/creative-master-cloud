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

    <!-- 体验质量指标看板（阶段04新增） -->
    <el-row v-if="expMetrics" class="content-row">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>📊 体验质量指标（最近 {{ expMetrics.observation_days }} 天）</span>
              <el-tag :type="expMetrics.sample_sufficient ? 'success' : 'warning'" size="small">
                {{ expMetrics.sample_note }}
              </el-tag>
            </div>
          </template>
          <div v-if="Object.keys(expMetrics.by_module).length === 0" class="empty-hint">
            <el-empty description="暂无体验事件数据" :image-size="80" />
          </div>
          <el-table v-else :data="moduleMetricsTable" border stripe size="small">
            <el-table-column prop="module" label="模块" width="140" />
            <el-table-column prop="started" label="启动次数" width="100" sortable />
            <el-table-column prop="completed" label="完成次数" width="100" sortable />
            <el-table-column prop="completion_rate" label="完成率" width="90" sortable>
              <template #default="{ row }">{{ (row.completion_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column prop="cancellation_rate" label="中断率" width="90" sortable>
              <template #default="{ row }">{{ (row.cancellation_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column prop="recovery_rate" label="恢复成功率" width="110" sortable>
              <template #default="{ row }">{{ (row.recovery_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column prop="avg_revision_rounds" label="平均修订轮次" width="110" sortable />
          </el-table>

          <!-- 错误类别分布 -->
          <div v-if="errorDistData.length" style="margin-top: 16px;">
            <h4 style="margin-bottom: 8px; font-size: 14px; color: #606266;">错误类别分布</h4>
            <div class="error-dist-chips">
              <el-tag
                v-for="item in errorDistData"
                :key="item.category"
                :type="errorTagType(item.category)"
                size="small"
                class="error-chip"
              >
                {{ errorCategoryLabel(item.category) }}：{{ item.count }} 次
              </el-tag>
            </div>
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

// 体验质量指标（阶段04新增）
const expMetrics = ref(null)

const storagePercent = computed(() => {
  if (health.value.storage_total_mb === 0) return 0
  return Math.round((health.value.storage_used_mb / health.value.storage_total_mb) * 100)
})

/** 模块指标表格数据 */
const moduleMetricsTable = computed(() => {
  if (!expMetrics.value?.by_module) return []
  return Object.entries(expMetrics.value.by_module).map(([module, m]) => ({
    module: moduleLabel(module),
    ...m
  }))
})

/** 错误类别分布（转换为数组便于渲染） */
const errorDistData = computed(() => {
  if (!expMetrics.value?.error_distribution) return []
  return Object.entries(expMetrics.value.error_distribution)
    .filter(([, count]) => count > 0)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)
})

/** 模块名中文标签 */
function moduleLabel(key) {
  const map = {
    short_video: '短视频脚本',
    novel: '小说大纲',
    print_ad: '平面广告',
    tvc: 'TVC广告',
    practical_writing: '应用文',
    script: '剧本',
    series: '剧集',
    movie_outline: '电影大纲',
    series_outline: '剧集大纲',
    original_ip: '原创IP',
  }
  return map[key] || key
}

/** 错误类别中文标签 */
function errorCategoryLabel(cat) {
  const map = {
    network: '网络错误',
    unauthorized: '认证过期',
    'rate-limited': '请求限流',
    'model-unavailable': '模型不可用',
    'task-interrupted': '任务中断',
  }
  return map[cat] || cat
}

/** 错误类别对应的 Tag 样式 */
function errorTagType(cat) {
  const map = {
    network: 'danger',
    unauthorized: 'warning',
    'rate-limited': 'warning',
    'model-unavailable': 'info',
    'task-interrupted': '',
  }
  return map[cat] || 'info'
}

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

/** 获取体验质量指标 */
const fetchExperienceMetrics = async () => {
  try {
    const res = await adminApi.getExperienceMetrics({ days: 14 })
    if (res.data) {
      expMetrics.value = res.data
    }
  } catch (error) {
    console.warn('[Dashboard] 获取体验指标失败:', error?.message || error)
    // 体验指标获取失败不影响看板主体展示
  }
}

onMounted(() => {
  fetchDashboard()
  refreshHealth()
  fetchExperienceMetrics()
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
