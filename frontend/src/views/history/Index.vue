<template>
  <div class="history-page">
    <div class="page-header">
      <h1 class="page-title">历史记录</h1>
      <el-button @click="refreshList">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filterType" placeholder="类型筛选" clearable style="width: 150px" @change="handleFilter">
        <el-option label="全部" value="" />
        <el-option v-for="cfg in moduleConfigs" :key="cfg.id" :label="cfg.name" :value="cfg.backendModuleId" />
      </el-select>

      <el-select v-model="filterStatus" placeholder="状态筛选" clearable style="width: 140px" @change="handleFilter">
        <el-option label="全部" value="" />
        <el-option label="已完成" value="completed" />
        <el-option label="进行中" value="processing" />
        <el-option label="失败" value="failed" />
        <el-option label="已取消" value="cancelled" />
      </el-select>

      <el-input
        v-model="filterKeyword"
        placeholder="搜索标题关键词"
        clearable
        style="width: 200px"
        @keyup.enter="handleFilter"
        @clear="handleFilter"
      >
        <template #append>
          <el-button @click="handleFilter"><el-icon><Search /></el-icon></el-button>
        </template>
      </el-input>

      <el-date-picker
        v-model="filterDate"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        style="width: 260px"
        @change="handleFilter"
      />
    </div>

    <!-- 历史列表 -->
    <div class="history-list">
      <el-table :data="historyList" v-loading="loading" style="width: 100%">
        <el-table-column prop="module" label="类型" width="130">
          <template #default="{ row }">
            <el-tag :type="getTagType(row.module)">{{ getTypeName(row.module) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ getTitle(row) }}
          </template>
        </el-table-column>
        <el-table-column label="模型" width="130">
          <template #default="{ row }">
            {{ row.provider || '-' }} / {{ row.model_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="修订" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.revision_count" type="info" size="small">{{ row.revision_count }} 次</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link size="small" @click="viewDetail(row)">
                <el-icon><View /></el-icon>查看
              </el-button>
              <el-button
                v-if="getModuleConfigByBackendId(row.module)"
                type="warning"
                link
                size="small"
                @click="continueAdjust(row)"
              >
                <el-icon><ChatDotRound /></el-icon>继续调整
              </el-button>
              <el-button type="danger" link size="small" @click="confirmDelete(row.id)">
                <el-icon><Delete /></el-icon>删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchHistory"
        />
      </div>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="showDetail"
      :title="getTitle(currentItem)"
      size="50%"
    >
      <div class="detail-content" v-if="currentItem">
        <div class="detail-header">
          <div class="detail-info">
            <span class="info-item">
              <strong>类型：</strong>
              <el-tag :type="getTagType(currentItem.module)">{{ getTypeName(currentItem.module) }}</el-tag>
            </span>
            <span class="info-item">
              <strong>模型：</strong>{{ currentItem.provider || '-' }} / {{ currentItem.model_name || '-' }}
            </span>
            <span class="info-item">
              <strong>时间：</strong>{{ formatDate(currentItem.created_at) }}
            </span>
            <span class="info-item" v-if="currentItem.updated_at">
              <strong>更新时间：</strong>{{ formatDate(currentItem.updated_at) }}
            </span>
            <span class="info-item">
              <strong>状态：</strong>
              <el-tag :type="getStatusTagType(currentItem.status)" size="small">
                {{ getStatusName(currentItem.status) }}
              </el-tag>
            </span>
            <span class="info-item">
              <strong>修订：</strong>
              <el-tag type="info" size="small">{{ currentItem.revision_count || 0 }} 次</el-tag>
              <el-tag v-if="currentItem.is_finalized" type="success" size="small" style="margin-left: 4px;">已确认</el-tag>
            </span>
          </div>
          <div class="detail-actions">
            <el-button text @click="copyContent">
              <el-icon><CopyDocument /></el-icon>
              复制内容
            </el-button>
            <el-button type="warning" text @click="continueAdjust(currentItem)">
              <el-icon><ChatDotRound /></el-icon>继续调整
            </el-button>
          </div>
        </div>

        <!-- 修订历史 -->
        <div class="revision-section" v-if="revisionHistoryList.length > 0">
          <el-divider content-position="left">修订历史（{{ revisionHistoryList.length }} 轮）</el-divider>
          <el-timeline>
            <el-timeline-item
              v-for="rev in revisionHistoryList"
              :key="rev.id"
              :timestamp="formatDate(rev.created_at)"
              placement="top"
            >
              <div class="revision-item">
                <div class="revision-round">第 {{ rev.round_number }} 轮修订</div>
                <div class="revision-feedback">
                  <strong>修改意见：</strong>{{ rev.user_feedback }}
                </div>
                <div class="revision-length" v-if="rev.content_before || rev.content_after">
                  <strong>内容长度：</strong>{{ (rev.content_before || '').length }} → {{ (rev.content_after || '').length }} 字
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>

        <div class="detail-body markdown-content" v-html="renderedContent"></div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, Delete, Search, ChatDotRound } from '@element-plus/icons-vue'
import { historyApi, revisionApi } from '@/api'
import { MODULE_CONFIGS, getModuleConfigByBackendId } from '@/config/modules'

const loading = ref(false)
const historyList = ref([])
const showDetail = ref(false)
const currentItem = ref(null)
const revisionHistoryList = ref([])

const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const filterType = ref('')
const filterDate = ref(null)
const filterStatus = ref('')
const filterKeyword = ref('')

const router = useRouter()

// 模块配置（用于筛选下拉与类型显示，与生成页共用同一份配置）
const moduleConfigs = Object.values(MODULE_CONFIGS)

const renderedContent = computed(() => {
  if (!currentItem.value?.output_content) return ''
  // 使用DOMPurify净化HTML，防止XSS攻击
  return DOMPurify.sanitize(marked(currentItem.value.output_content))
})

onMounted(() => {
  fetchHistory()
})

// 详情抽屉打开时加载修订历史
function loadRevisionHistory(generationId) {
  revisionHistoryList.value = []
  if (!generationId) return
  revisionApi.getHistory(generationId)
    .then((res) => {
      revisionHistoryList.value = Array.isArray(res?.data) ? res.data : []
    })
    .catch((error) => {
      console.error('获取修订历史失败:', error)
    })
}

async function fetchHistory() {
  loading.value = true
  try {
    // 后端API使用limit和offset参数
    const params = {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value
    }
    if (filterType.value) {
      params.module = filterType.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    if (filterKeyword.value.trim()) {
      params.keyword = filterKeyword.value.trim()
    }
    if (Array.isArray(filterDate.value) && filterDate.value.length === 2) {
      params.start_date = formatDateParam(filterDate.value[0])
      params.end_date = formatDateParam(filterDate.value[1])
    }

    const res = await historyApi.list(params)
    // 后端返回 {code, message, data: {items: [...], total: number}}
    const data = res.data || { items: [], total: 0 }
    historyList.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    console.error('获取历史记录失败:', error)
  } finally {
    loading.value = false
  }
}

function handleFilter() {
  currentPage.value = 1
  fetchHistory()
}

function refreshList() {
  fetchHistory()
}

async function viewDetail(row) {
  try {
    const res = await historyApi.get(row.id)
    currentItem.value = res
    loadRevisionHistory(row.id)
    showDetail.value = true
  } catch (error) {
    console.error('获取详情失败:', error)
  }
}

async function confirmDelete(id) {
  await ElMessageBox.confirm('确定删除此记录？', '提示', { type: 'warning' })
  await deleteRecord(id)
}

async function deleteRecord(id) {
  try {
    await historyApi.delete(id)
    ElMessage.success('删除成功')
    await fetchHistory()
  } catch (error) {
    console.error('删除失败:', error)
  }
}

async function copyContent() {
  try {
    await navigator.clipboard.writeText(currentItem.value?.output_content || '')
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

// 从历史记录继续调整：跳转到生成页并携带 generation_id
function continueAdjust(row) {
  const cfg = getModuleConfigByBackendId(row?.module)
  if (!cfg) {
    ElMessage.warning('该模块暂不支持从历史继续调整')
    return
  }
  router.push({ path: `/generate/${cfg.id}`, query: { generation_id: row.id } })
}

function getTypeName(type) {
  return getModuleConfigByBackendId(type)?.name || type
}

function getTagType(type) {
  const typeMap = {
    'short_video': 'danger',
    'novel': 'primary',
    'print_ad': 'warning',
    'tvc': 'info',
    'movie_outline': 'success',
    'series_outline': '',
    'original_ip': 'success',
    'practical_writing': 'info'
  }
  return typeMap[type] || ''
}

function getStatusName(status) {
  const map = {
    'completed': '已完成',
    'processing': '进行中',
    'failed': '失败',
    'cancelled': '已取消'
  }
  return map[status] || status || '未知'
}

function getStatusTagType(status) {
  const map = {
    'completed': 'success',
    'processing': 'warning',
    'failed': 'danger',
    'cancelled': 'info'
  }
  return map[status] || 'info'
}

function getTitle(row) {
  // 优先使用后端提取的 title 字段
  if (row?.title) {
    return row.title
  }

  // 兜底：从 input_params 中提取标题
  const params = row?.input_params || {}
  return params.topic || params.theme || params.synopsis || params.title || '创意内容'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatDateParam(date) {
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
</script>

<style lang="scss" scoped>
.history-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .page-title {
    font-size: 22px;
    color: #303133;
  }
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 20px;
}

.history-list {
  background: #fff;
  border-radius: 12px;
  padding: 24px;

  .pagination {
    margin-top: 20px;
    display: flex;
    justify-content: center;
  }
}

.detail-content {
  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    padding-bottom: 20px;
    border-bottom: 1px solid #eee;
    margin-bottom: 20px;

    .detail-info {
      display: flex;
      flex-wrap: wrap;
      gap: 20px;

      .info-item {
        font-size: 14px;
        color: #606266;
      }
    }

    .detail-actions {
      display: flex;
      gap: 8px;
      flex-shrink: 0;
    }
  }

  .revision-section {
    margin-bottom: 12px;

    .revision-item {
      .revision-round {
        font-weight: 600;
        color: #409eff;
        margin-bottom: 4px;
      }

      .revision-feedback,
      .revision-length {
        font-size: 13px;
        color: #606266;
        margin-top: 2px;
        word-break: break-all;
      }
    }
  }

  .detail-body {
    max-height: calc(100vh - 260px);
    overflow-y: auto;
  }
}

// 操作按钮样式
.action-buttons {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 4px;
  white-space: nowrap;

  .el-button {
    padding: 2px 4px;
    font-size: 13px;

    .el-icon {
      margin-right: 2px;
      font-size: 14px;
    }
  }
}
</style>
