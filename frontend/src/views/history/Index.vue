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
        <el-option label="短视频脚本" value="short-video" />
        <el-option label="剧本大纲" value="script" />
        <el-option label="小说大纲" value="novel" />
        <el-option label="平面广告" value="print-ad" />
        <el-option label="TVC广告" value="tvc" />
      </el-select>
      
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
        <el-table-column prop="module" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTagType(row.module)">{{ getTypeName(row.module) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ getTitle(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="provider" label="模型" width="120">
          <template #default="{ row }">
            {{ row.provider }} / {{ row.model_name }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link size="small" @click="viewDetail(row)">
                <el-icon><View /></el-icon>查看
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
              <strong>模型：</strong>{{ currentItem.provider }} / {{ currentItem.model_name }}
            </span>
            <span class="info-item">
              <strong>时间：</strong>{{ formatDate(currentItem.created_at) }}
            </span>
          </div>
          <div class="detail-actions">
            <el-button text @click="copyContent">
              <el-icon><CopyDocument /></el-icon>
              复制内容
            </el-button>
          </div>
        </div>
        
        <div class="detail-body markdown-content" v-html="renderedContent"></div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, Delete } from '@element-plus/icons-vue'
import { historyApi } from '@/api'

const loading = ref(false)
const historyList = ref([])
const showDetail = ref(false)
const currentItem = ref(null)

const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const filterType = ref('')
const filterDate = ref(null)

const renderedContent = computed(() => {
  if (!currentItem.value?.output_content) return ''
  // 使用DOMPurify净化HTML，防止XSS攻击
  return DOMPurify.sanitize(marked(currentItem.value.output_content))
})

onMounted(() => {
  fetchHistory()
})

async function fetchHistory() {
  loading.value = true
  try {
    // 后端API使用limit和offset参数
    const params = {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value
    }
    if (filterType.value) {
      params.module = filterType.value  // 后端使用module参数
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

// 模块名称映射（后端返回下划线格式）
const moduleNameMap = {
  'short_video': '短视频脚本',
  'script': '剧本大纲',
  'novel': '小说大纲',
  'print_ad': '平面广告',
  'tvc': 'TVC广告脚本'
}

function getTypeName(type) {
  return moduleNameMap[type] || type
}

function getTagType(type) {
  const typeMap = {
    'short_video': 'danger',
    'script': 'success',
    'novel': 'primary',
    'print_ad': 'warning',
    'tvc': 'info'
  }
  return typeMap[type] || ''
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
  }
  
  .detail-body {
    max-height: calc(100vh - 200px);
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
