<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h1 class="page-title">知识库管理</h1>
      <el-button type="primary" class="upload-btn" @click="showUploadDialog = true">
        <el-icon><Upload /></el-icon>
        上传文件
      </el-button>
    </div>
    
    <!-- 说明卡片 -->
    <div class="info-card">
      <div class="info-icon">
        <el-icon :size="20"><InfoFilled /></el-icon>
      </div>
      <div class="info-content">
        <p>上传您的知识文档，AI将结合知识库内容生成更精准的创意内容。支持 PDF、Word、TXT、Markdown 等格式。</p>
        <p class="recommend-text">
          <el-icon><CircleCheck /></el-icon>
          建议上传 md、docx、txt 等格式的知识库文档，pdf 的效果不佳。
        </p>
        <p class="warning-text">
          <el-icon><Warning /></el-icon>
          文档字数越多，消耗的大模型token越多，请尽量上传精炼的文档。单个文件限制100MB。
        </p>
      </div>
    </div>
    
    <!-- 知识库类型引导 -->
    <el-card class="guide-card">
      <template #header>
        <div class="guide-header">
          <el-icon><Guide /></el-icon>
          <span>知识库分类指南</span>
        </div>
      </template>
      <div class="guide-content">
        <div class="guide-item">
          <div class="guide-icon general">
            <el-icon><Reading /></el-icon>
          </div>
          <div class="guide-text">
            <h4>通用知识库</h4>
            <p>存放创意理论、方法论、通用技巧等<strong>理论性资料</strong></p>
            <span class="guide-example">例如：三幕式结构、峰终定律、色彩心理学、叙事理论等</span>
          </div>
        </div>
        <div class="guide-divider">
          <el-icon><ArrowDown /></el-icon>
        </div>
        <div class="guide-item">
          <div class="guide-icon user-specific">
            <el-icon><User /></el-icon>
          </div>
          <div class="guide-text">
            <h4>用户专属知识库 <el-tag size="small" type="success">GraphRAG</el-tag></h4>
            <p>存储用户上传的<strong>个性化知识内容</strong>，针对小众人物、专有名词、专业知识、个人经验等优化</p>
            <span class="guide-example">例如：个人作品集、专业知识笔记、特定人物介绍等</span>
          </div>
        </div>
        <div class="guide-divider">
          <el-icon><ArrowDown /></el-icon>
        </div>
        <div class="guide-item">
          <div class="guide-icon manual">
            <el-icon><Document /></el-icon>
          </div>
          <div class="guide-text">
            <h4>官方手册知识库</h4>
            <p>存放官方规范、标准手册、产品文档等<strong>参考资料</strong></p>
            <span class="guide-example">例如：API文档、使用手册、配置说明等</span>
          </div>
        </div>
        <div class="guide-divider">
          <el-icon><ArrowDown /></el-icon>
        </div>
        <div class="guide-item">
          <div class="guide-icon vertical">
            <el-icon><Collection /></el-icon>
          </div>
          <div class="guide-text">
            <h4>垂直领域知识库</h4>
            <p>按业务模块划分的<strong>实践性资料</strong>，包括短视频、剧本、小说、平面广告、TVC广告等</p>
            <span class="guide-example">例如：爆款短视频脚本、成功广告案例、优秀剧本大纲等</span>
          </div>
        </div>
        <div class="guide-tip">
          <el-icon><InfoFilled /></el-icon>
          <span>通用知识库默认加载，用户专属和官方手册可选择性启用，垂直领域知识库按业务模块智能匹配</span>
        </div>
      </div>
    </el-card>
    
    <!-- 业务模块筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="filterCategory" @change="fetchKnowledge">
        <el-radio-button label="all">全部</el-radio-button>
        <el-radio-button label="general">通用</el-radio-button>
        <el-radio-button label="user-specific">用户专属</el-radio-button>
        <el-radio-button label="manual">官方手册</el-radio-button>
        <el-radio-button label="short-video">短视频</el-radio-button>
        <el-radio-button label="script">剧本</el-radio-button>
        <el-radio-button label="novel">小说</el-radio-button>
        <el-radio-button label="print-ad">平面广告</el-radio-button>
        <el-radio-button label="tvc">TVC广告</el-radio-button>
      </el-radio-group>
    </div>
    
    <!-- 处理进度卡片 -->
    <el-card v-if="processingProgress.is_processing" class="progress-card">
      <template #header>
        <div class="card-header">
          <span>知识库处理中</span>
          <div class="header-actions">
            <el-tag type="warning" size="small" style="margin-right: 10px;">
              {{ processingProgress.current_step }}
            </el-tag>
            <el-button 
              type="danger" 
              size="small" 
              :loading="stopping"
              @click="stopProcessing"
            >
              <el-icon><CircleClose /></el-icon>
              终止处理
            </el-button>
          </div>
        </div>
      </template>
      <el-progress :percentage="processingProgress.progress" :stroke-width="10" />
      <div class="progress-steps">
        <div v-for="step in 4" :key="step" 
             :class="['step-item', { active: step === processingProgress.current_step_index, done: step < processingProgress.current_step_index }]">
          <div class="step-icon">
            <el-icon v-if="step < processingProgress.current_step_index"><Check /></el-icon>
            <span v-else>{{ step }}</span>
          </div>
          <span class="step-label">{{ getStepLabel(step) }}</span>
        </div>
      </div>
    </el-card>
    
    <!-- 文件列表 -->
    <div class="file-list-container">
      <el-table :data="knowledgeList" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="知识库名称" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="file-name">
              <el-icon :size="18"><Document /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="业务模块" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getCategoryType(row.category)">
              {{ getCategoryName(row.category) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.file_type?.toUpperCase() || 'N/A' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="document_count" label="文档片段" width="90">
          <template #default="{ row }">
            {{ row.document_count || 0 }} 条
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" width="90">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预处理" width="100">
          <template #default="{ row }">
            <el-tooltip v-if="row.status === 'ready' && row.preprocessor_metadata" placement="top">
              <template #content>
                <div class="preprocessor-tooltip">
                  <p><strong>预处理流水线：</strong></p>
                  <p>• 文档转换: {{ row.preprocessor_metadata.marker_used ? 'Marker' : '基本解析' }}</p>
                  <p>• 语义切片: {{ row.preprocessor_metadata.semantic_chunk_used ? 'Chonkie' : '固定大小' }}</p>
                  <p>• 摘要压缩: {{ row.preprocessor_metadata.summarization_used ? '已启用' : '未启用' }}</p>
                  <p v-if="row.preprocessor_metadata.original_size">
                    <strong>压缩效果:</strong> {{ formatSize(row.preprocessor_metadata.original_size) }} → {{ formatSize(row.preprocessor_metadata.filtered_size) }}
                  </p>
                </div>
              </template>
              <el-tag type="success" size="small">
                <el-icon><Check /></el-icon>
              </el-tag>
            </el-tooltip>
            <el-tooltip v-else-if="row.status === 'ready'" content="基本处理" placement="top">
              <el-tag type="info" size="small">基本</el-tag>
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button v-if="row.status === 'ready'" type="success" link size="small" @click="showGraphDialog(row)">
                <el-icon><Share /></el-icon>图谱
              </el-button>
              <el-button type="primary" link size="small" @click="openEditDialog(row)">
                <el-icon><Edit /></el-icon>编辑
              </el-button>
              <el-popconfirm
                title="确定删除此知识库？"
                @confirm="removeFile(row.id)"
              >
                <template #reference>
                  <el-button type="danger" link size="small">
                    <el-icon><Delete /></el-icon>删除
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="fetchKnowledge"
        />
      </div>
    </div>
    
    <!-- 上传对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传知识文件"
      width="550px"
      :close-on-click-modal="false"
    >
      <el-form :model="uploadForm" label-width="100px">
        <!-- 知识库类型选择引导 -->
        <el-form-item label="知识库类型" required>
          <el-radio-group v-model="uploadForm.category" class="category-radio-group">
            <el-radio-button label="general">
              <div class="radio-content">
                <el-icon><Reading /></el-icon>
                <span>通用知识库</span>
                <small>理论、方法论</small>
              </div>
            </el-radio-button>
            <el-radio-button label="user-specific">
              <div class="radio-content">
                <el-icon><User /></el-icon>
                <span>用户专属</span>
                <small>个性化知识</small>
              </div>
            </el-radio-button>
            <el-radio-button label="manual">
              <div class="radio-content">
                <el-icon><Document /></el-icon>
                <span>官方手册</span>
                <small>API、文档</small>
              </div>
            </el-radio-button>
            <el-radio-button label="short-video">
              <div class="radio-content">
                <el-icon><VideoPlay /></el-icon>
                <span>短视频</span>
                <small>脚本、案例</small>
              </div>
            </el-radio-button>
            <el-radio-button label="script">
              <div class="radio-content">
                <el-icon><Film /></el-icon>
                <span>剧本</span>
                <small>大纲、剧本</small>
              </div>
            </el-radio-button>
            <el-radio-button label="novel">
              <div class="radio-content">
                <el-icon><Notebook /></el-icon>
                <span>小说</span>
                <small>大纲、作品</small>
              </div>
            </el-radio-button>
            <el-radio-button label="print-ad">
              <div class="radio-content">
                <el-icon><Picture /></el-icon>
                <span>平面广告</span>
                <small>案例、策划</small>
              </div>
            </el-radio-button>
            <el-radio-button label="tvc">
              <div class="radio-content">
                <el-icon><Monitor /></el-icon>
                <span>TVC广告</span>
                <small>脚本、案例</small>
              </div>
            </el-radio-button>
          </el-radio-group>
          <div class="category-hint" :class="uploadForm.category">
            <el-icon><InfoFilled /></el-icon>
            <span v-if="uploadForm.category === 'general'">
              适合存放：创意理论、方法论、通用技巧等<strong>理论性资料</strong>
            </span>
            <span v-else-if="uploadForm.category === 'user-specific'">
              适合存放：用户上传的个性化知识内容，支持GraphRAG，针对<strong>小众人物、专有名词、专业知识、个人经验</strong>等优化
            </span>
            <span v-else-if="uploadForm.category === 'manual'">
              适合存放：官方规范、标准手册、API文档、配置说明等<strong>技术文档</strong>（快速检索）
            </span>
            <span v-else>
              适合存放：{{ getCategoryName(uploadForm.category) }}相关的<strong>实际案例、成品脚本、策划案</strong>等实践性资料
            </span>
          </div>
        </el-form-item>
        
        <el-form-item label="知识库名称">
          <el-input 
            v-model="uploadForm.name" 
            placeholder="自动获取文件名，可修改" 
            clearable
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="uploadForm.description" type="textarea" :rows="2" placeholder="描述知识库内容，帮助您日后识别" />
        </el-form-item>
        <el-form-item label="文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="10"
            :on-change="handleFileChange"
            :on-exceed="handleExceed"
            :file-list="fileList"
            drag
            multiple
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 PDF、Word、TXT、Markdown 格式，单个文件不超过 100MB，最多10个文件
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          上传
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 编辑对话框 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑知识库"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="知识库名称" required>
          <el-input v-model="editForm.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="2" placeholder="可选，描述知识库内容" />
        </el-form-item>
        <el-form-item label="业务模块">
          <el-select v-model="editForm.category" placeholder="选择业务模块" style="width: 100%">
            <el-option label="通用" value="general" />
            <el-option label="用户专属" value="user-specific" />
            <el-option label="官方手册" value="manual" />
            <el-option label="短视频" value="short-video" />
            <el-option label="剧本" value="script" />
            <el-option label="小说" value="novel" />
            <el-option label="平面广告" value="print-ad" />
            <el-option label="TVC广告" value="tvc" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleEdit">
          保存
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 知识图谱对话框 -->
    <el-dialog
      v-model="showGraphDialogVisible"
      :title="`知识图谱 - ${currentKbName}`"
      width="900px"
      top="5vh"
      @close="closeGraphDialog"
    >
      <div v-if="graphLoading" class="graph-loading">
        <el-icon class="is-loading" :size="40"><Loading /></el-icon>
        <p>正在加载知识图谱...</p>
      </div>
      <div v-else-if="graphData.nodes.length === 0" class="graph-empty">
        <el-empty description="暂无知识图谱数据" />
      </div>
      <div v-else>
        <div class="graph-stats">
          <el-tag>节点: {{ graphData.stats.node_count }}</el-tag>
          <el-tag type="success">关系: {{ graphData.stats.edge_count }}</el-tag>
        </div>
        <div ref="graphContainer" class="graph-container"></div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { knowledgeApi } from '@/api'
import { Graph } from '@antv/g6'
import { Share, Edit, Delete } from '@element-plus/icons-vue'

const loading = ref(false)
const uploading = ref(false)
const saving = ref(false)
const stopping = ref(false)
const showUploadDialog = ref(false)
const showEditDialog = ref(false)
const showGraphDialogVisible = ref(false)
const knowledgeList = ref([])
const fileList = ref([])
const uploadRef = ref()
const filterCategory = ref('all')
const graphContainer = ref(null)
const graphLoading = ref(false)
const currentKbId = ref(null)
const currentKbName = ref('')
// 进度轮询定时器（使用Map管理多个定时器，避免内存泄漏）
const progressTimers = new Map()
let graphInstance = null // G6 实例

const uploadForm = ref({
  name: '',
  description: '',
  category: 'general'
})

const editForm = ref({
  id: null,
  name: '',
  description: '',
  category: ''
})

const processingProgress = ref({
  is_processing: false,
  current_step: '',
  progress: 0,
  current_step_index: 0,
  total_steps: 4
})

const graphData = ref({
  nodes: [],
  edges: [],
  stats: { node_count: 0, edge_count: 0 }
})

const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

onMounted(() => {
  fetchKnowledge()
})

onUnmounted(() => {
  // 清理所有进度轮询定时器
  progressTimers.forEach(timer => clearInterval(timer))
  progressTimers.clear()

  // 销毁G6图表实例
  if (graphInstance) {
    try {
      graphInstance.destroy()
    } catch (e) {
      console.warn('销毁图表实例失败:', e)
    }
    graphInstance = null
  }
})

async function fetchKnowledge() {
  loading.value = true
  try {
    const params = {}
    if (filterCategory.value && filterCategory.value !== 'all') {
      params.category = filterCategory.value
    }
    const res = await knowledgeApi.list(params)
    knowledgeList.value = res.data || []
    // 优先使用后端返回的total，支持分页
    total.value = res.total || res.pagination?.total || (res.data || []).length

    // 检查是否有正在处理的知识库
    const processing = knowledgeList.value.find(kb => kb.status === 'processing')
    if (processing) {
      startProgressPolling(processing.id)
    }
  } catch (error) {
    console.error('获取知识库失败:', error)
  } finally {
    loading.value = false
  }
}

function startProgressPolling(kbId) {
  processingProgress.value.is_processing = true
  processingProgress.value.kb_id = kbId

  // 先清理已有的同ID定时器
  if (progressTimers.has(kbId)) {
    clearInterval(progressTimers.get(kbId))
  }

  const timer = setInterval(async () => {
    try {
      const res = await knowledgeApi.getProgress(kbId)
      processingProgress.value = { ...res.data, kb_id: kbId }

      if (!res.data.is_processing) {
        // 处理完成，清理定时器
        clearInterval(timer)
        progressTimers.delete(kbId)
        await fetchKnowledge()
      }
    } catch (error) {
      console.error('获取进度失败:', error)
    }
  }, 2000)

  progressTimers.set(kbId, timer)
}

function getStepLabel(step) {
  const labels = ['解析文件', '向量存储', '知识图谱', '完成']
  return labels[step - 1] || ''
}

async function stopProcessing() {
  if (!processingProgress.value.kb_id) {
    ElMessage.warning('没有正在处理的知识库')
    return
  }

  stopping.value = true
  try {
    await knowledgeApi.stopProcessing(processingProgress.value.kb_id)
    ElMessage.success('处理已终止')

    // 清除定时器
    const kbId = processingProgress.value.kb_id
    if (progressTimers.has(kbId)) {
      clearInterval(progressTimers.get(kbId))
      progressTimers.delete(kbId)
    }

    // 重置进度
    processingProgress.value = {
      is_processing: false,
      current_step: '',
      progress: 0,
      current_step_index: 0,
      total_steps: 4
    }

    // 刷新列表
    await fetchKnowledge()
  } catch (error) {
    console.error('终止处理失败:', error)
    ElMessage.error(error.response?.data?.detail || '终止处理失败')
  } finally {
    stopping.value = false
  }
}

function handleFileChange(file, files) {
  // 验证文件大小（100MB限制）
  const maxSize = 100 * 1024 * 1024 // 100MB
  const invalidFiles = files.filter(f => f.size > maxSize)
  
  if (invalidFiles.length > 0) {
    ElMessage.error(`以下文件超过100MB限制：${invalidFiles.map(f => f.name).join(', ')}`)
    // 移除超大文件
    fileList.value = files.filter(f => f.size <= maxSize)
  } else {
    fileList.value = files
  }
  
  // 自动填充知识库名称（使用第一个文件名，去除扩展名）
  if (files.length > 0 && !uploadForm.value.name) {
    const firstFileName = files[0].name
    // 去除文件扩展名
    const nameWithoutExt = firstFileName.replace(/\.[^/.]+$/, '')
    uploadForm.value.name = nameWithoutExt
  }
}

function handleExceed(files) {
  ElMessage.warning('最多只能上传10个文件')
}

async function handleUpload() {
  if (!uploadForm.value.name) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  if (!fileList.value.length) {
    ElMessage.warning('请选择文件')
    return
  }
  
  uploading.value = true
  const uploadedIds = []
  
  try {
    // 遍历上传多个文件，每个文件创建一个知识库
    for (let i = 0; i < fileList.value.length; i++) {
      const file = fileList.value[i]
      const formData = new FormData()
      
      // 如果有多个文件，在名称后添加序号
      const kbName = fileList.value.length > 1 
        ? `${uploadForm.value.name} (${i + 1}/${fileList.value.length})`
        : uploadForm.value.name
      
      formData.append('name', kbName)
      formData.append('file', file.raw)
      formData.append('category', uploadForm.value.category)
      if (uploadForm.value.description) {
        formData.append('description', uploadForm.value.description)
      }
      
      const res = await knowledgeApi.upload(formData)
      uploadedIds.push(res.data.id)
    }
    
    ElMessage.success(`已上传 ${fileList.value.length} 个文件，正在处理中...`)
    showUploadDialog.value = false
    fileList.value = []
    uploadForm.value = { name: '', description: '', category: 'general' }
    
    // 为所有上传的知识库开始进度轮询
    uploadedIds.forEach(id => startProgressPolling(id))
    await fetchKnowledge()
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

function openEditDialog(row) {
  editForm.value = {
    id: row.id,
    name: row.name,
    description: row.description || '',
    category: row.category || 'general'
  }
  showEditDialog.value = true
}

async function handleEdit() {
  if (!editForm.value.name) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  
  saving.value = true
  try {
    await knowledgeApi.update(editForm.value.id, {
      name: editForm.value.name,
      description: editForm.value.description,
      category: editForm.value.category
    })
    
    ElMessage.success('保存成功')
    showEditDialog.value = false
    await fetchKnowledge()
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeFile(id) {
  try {
    await knowledgeApi.delete(id)
    ElMessage.success('删除成功')
    await fetchKnowledge()
  } catch (error) {
    console.error('删除失败:', error)
  }
}

async function showGraphDialog(row) {
  currentKbId.value = row.id
  currentKbName.value = row.name
  showGraphDialogVisible.value = true
  graphLoading.value = true
  graphData.value = { nodes: [], edges: [], stats: { node_count: 0, edge_count: 0 } }
  
  console.log('=== 开始获取知识图谱 ===')
  console.log('知识库ID:', row.id)
  
  try {
    const res = await knowledgeApi.getGraph(row.id, 200)
    console.log('API响应:', res)
    
    // 修复：API响应结构是 {code, message, data: {...}}，添加防御性处理
    const rawData = res.data?.data || res.data || {}
    const data = {
      nodes: Array.isArray(rawData.nodes) ? rawData.nodes : [],
      edges: Array.isArray(rawData.edges) ? rawData.edges : [],
      stats: rawData.stats || {}
    }
    console.log('图谱数据:', data)
    console.log('节点数:', data.nodes.length)
    console.log('边数:', data.edges.length)
    console.log('统计:', data.stats)

    graphData.value = data
    
    console.log('设置后 graphData.value.nodes.length:', graphData.value?.nodes?.length)
    
    // 等待 DOM 更新
    await nextTick()
    
    // 额外等待确保容器渲染
    setTimeout(() => {
      console.log('setTimeout后 graphContainer.value:', graphContainer.value)
      
      if (graphContainer.value && data?.nodes?.length > 0) {
        console.log('调用 renderGraph')
        renderGraph(data)
      } else {
        console.log('未调用 renderGraph, 原因:', 
          !graphContainer.value ? '容器不存在' : '节点数为0')
      }
    }, 100)
  } catch (error) {
    console.error('获取图谱失败:', error)
    ElMessage.error('获取知识图谱失败')
  } finally {
    graphLoading.value = false
  }
}

function renderGraph(data) {
  const container = graphContainer.value
  if (!container) {
    console.error('图谱容器不存在')
    return
  }
  
  console.log('开始渲染图谱，节点数:', data.nodes.length, '边数:', data.edges.length)

  // 销毁旧实例（添加try-catch保护）
  if (graphInstance) {
    try {
      graphInstance.destroy()
    } catch (e) {
      console.warn('销毁旧图表实例失败:', e)
    }
    graphInstance = null
  }
  
  // 颜色映射
  const typeColors = {
    '人物': '#409EFF',
    '作品': '#67C23A',
    '风格': '#E6A23C',
    '平台': '#F56C6C',
    '品牌': '#909399',
    '场景': '#00D4AA',
    '技术': '#9B59B6',
    '情感': '#FF69B4',
    '概念': '#3498DB',
    '参数': '#1ABC9C',
    '数据': '#E74C3C',
    '未知': '#95A5A6'
  }
  
  // 转换数据格式 - G6 v5 格式
  const nodes = data.nodes.map(node => ({
    id: node.id,
    data: {
      label: node.label || node.text || node.id,
      type: node.type
    }
  }))
  
  const edges = data.edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: edge.source,
    target: edge.target,
    data: {
      label: edge.relation || ''
    }
  }))
  
  console.log('转换后节点:', nodes.slice(0, 3))
  console.log('转换后边:', edges.slice(0, 3))
  
  try {
    // 创建 G6 v5 实例
    graphInstance = new Graph({
      container: container,
      width: container.clientWidth || 800,
      height: 500,
      data: { nodes, edges },
      autoFit: 'view',
      padding: 20,
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
      layout: {
        type: 'force',
        preventOverlap: true,
        nodeSize: 30,
        linkDistance: 100
      },
      node: {
        type: 'circle',
        style: {
          size: 20,
          labelText: (d) => d.data?.label || d.id,
          labelFill: '#333',
          labelFontSize: 10,
          labelPlacement: 'bottom',
          fill: (d) => typeColors[d.data?.type] || typeColors['未知'],
          stroke: '#fff',
          lineWidth: 2
        }
      },
      edge: {
        style: {
          stroke: '#aaa',
          lineWidth: 1,
          endArrow: true,
          labelText: (d) => d.data?.label || '',
          labelFill: '#666',
          labelFontSize: 8
        }
      }
    })
    
    // 渲染图谱
    graphInstance.render()
    console.log('图谱渲染完成')
  } catch (error) {
    console.error('图谱渲染错误:', error)
  }
}

function closeGraphDialog() {
  // 销毁 G6 实例（添加try-catch保护）
  if (graphInstance) {
    try {
      graphInstance.destroy()
    } catch (e) {
      console.warn('销毁图表实例失败:', e)
    }
    graphInstance = null
  }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(1)} ${units[i]}`
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

function getStatusName(status) {
  const statusMap = {
    'ready': '已就绪',
    'processing': '处理中',
    'pending': '待处理',
    'failed': '失败'
  }
  return statusMap[status] || status
}

function getStatusType(status) {
  const typeMap = {
    'ready': 'success',
    'processing': 'warning',
    'pending': 'info',
    'failed': 'danger'
  }
  return typeMap[status] || ''
}

function getCategoryName(category) {
  const categoryMap = {
    'general': '通用',
    'user-specific': '用户专属',
    'manual': '官方手册',
    'short-video': '短视频',
    'script': '剧本',
    'novel': '小说',
    'print-ad': '平面广告',
    'tvc': 'TVC广告'
  }
  return categoryMap[category] || category || '通用'
}

function getCategoryType(category) {
  const typeMap = {
    'general': 'primary',
    'user-specific': 'success',
    'manual': 'warning',
    'short-video': 'primary',
    'script': 'success',
    'novel': 'warning',
    'print-ad': 'info',
    'tvc': 'danger'
  }
  return typeMap[category] || 'info'
}
</script>

<style lang="scss" scoped>
.knowledge-page {
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
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 10px;
    
    &::before {
      content: '';
      width: 4px;
      height: 22px;
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 2px;
    }
  }
  
  .upload-btn {
    background: linear-gradient(135deg, #409EFF 0%, #00D4AA 100%);
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
    transition: all 0.3s;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4);
    }
  }
}

.info-card {
  display: flex;
  gap: 14px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e8f4f8 100%);
  border-radius: 12px;
  padding: 18px 22px;
  margin-bottom: 20px;
  border: 1px solid rgba(64, 158, 255, 0.15);
  
  .info-icon {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(64, 158, 255, 0.1);
    border-radius: 10px;
    color: #409EFF;
    flex-shrink: 0;
  }
  
  .info-content {
    flex: 1;
    
    p {
      color: #606266;
      font-size: 14px;
      line-height: 1.6;
      margin: 0;
      
      & + p {
        margin-top: 10px;
      }
    }
    
    .recommend-text {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #67C23A;
      font-weight: 500;
      background: rgba(103, 194, 58, 0.08);
      padding: 8px 12px;
      border-radius: 6px;
    }
    
    .warning-text {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #E6A23C;
      font-weight: 500;
      background: rgba(230, 162, 60, 0.08);
      padding: 8px 12px;
      border-radius: 6px;
    }
  }
}

.filter-bar {
  margin-bottom: 20px;
  
  :deep(.el-radio-group) {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  
  :deep(.el-radio-button__inner) {
    border-radius: 8px !important;
    border: 1px solid #dcdfe6;
    padding: 8px 16px;
    font-size: 13px;
    transition: all 0.3s;
  }
  
  :deep(.el-radio-button.is-active .el-radio-button__inner) {
    background: linear-gradient(135deg, #409EFF, #00D4AA);
    border-color: #409EFF;
    box-shadow: 0 2px 8px rgba(64, 158, 255, 0.3);
  }
}

.guide-card {
  margin-bottom: 20px;
  border-radius: 14px;
  border: 1px solid rgba(64, 158, 255, 0.1);
  
  :deep(.el-card__header) {
    padding: 16px 20px;
    border-bottom: 1px solid rgba(64, 158, 255, 0.1);
  }
  
  :deep(.el-card__body) {
    padding: 20px;
  }
  
  .guide-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 600;
    color: #303133;
    
    .el-icon {
      color: #409EFF;
    }
  }
  
  .guide-content {
    .guide-item {
      display: flex;
      align-items: flex-start;
      gap: 14px;
      padding: 14px 0;
      
      &:not(:last-child) {
        border-bottom: 1px dashed rgba(64, 158, 255, 0.15);
      }
      
      .guide-icon {
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        flex-shrink: 0;
        
        &.general {
          background: rgba(64, 158, 255, 0.1);
          color: #409EFF;
        }
        
        &.user-specific {
          background: rgba(103, 194, 58, 0.1);
          color: #67C23A;
        }
        
        &.manual {
          background: rgba(230, 162, 60, 0.1);
          color: #E6A23C;
        }
        
        &.vertical {
          background: rgba(0, 212, 170, 0.1);
          color: #00D4AA;
        }
      }
      
      .guide-text {
        flex: 1;
        
        h4 {
          font-size: 14px;
          color: #303133;
          margin: 0 0 4px;
          font-weight: 600;
        }
        
        p {
          font-size: 13px;
          color: #606266;
          margin: 0 0 4px;
        }
        
        .guide-example {
          font-size: 12px;
          color: #909399;
        }
      }
    }
    
    .guide-divider {
      display: flex;
      justify-content: center;
      padding: 8px 0;
      color: #c0c4cc;
    }
    
    .guide-tip {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: rgba(64, 158, 255, 0.05);
      border-radius: 8px;
      font-size: 12px;
      color: #606266;
      margin-top: 16px;
      
      .el-icon {
        color: #409EFF;
      }
    }
  }
}

.progress-card {
  margin-bottom: 20px;
  border-radius: 14px;
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .progress-steps {
    display: flex;
    justify-content: space-between;
    margin-top: 20px;
    
    .step-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      
      .step-icon {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: #e4e7ed;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        color: #909399;
        transition: all 0.3s;
      }
      
      .step-label {
        font-size: 12px;
        color: #909399;
      }
      
      &.active .step-icon {
        background: linear-gradient(135deg, #409EFF, #00D4AA);
        color: #fff;
        box-shadow: 0 2px 8px rgba(64, 158, 255, 0.4);
      }
      
      &.active .step-label {
        color: #409EFF;
        font-weight: 500;
      }
      
      &.done .step-icon {
        background: #67C23A;
        color: #fff;
      }
      
      &.done .step-label {
        color: #67C23A;
      }
    }
  }
}

.file-list-container {
  background: #fff;
  border-radius: 14px;
  padding: 24px;
  border: 1px solid rgba(64, 158, 255, 0.08);
  
  :deep(.el-table) {
    border-radius: 10px;
    overflow: hidden;
    
    th.el-table__cell {
      background: #f5f7fa;
      font-weight: 600;
      color: #303133;
    }
    
    tr:hover > td {
      background: rgba(64, 158, 255, 0.04) !important;
    }
  }
  
  .file-name {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .el-icon {
      color: #409EFF;
    }
  }
  
  .pagination {
    margin-top: 20px;
    display: flex;
    justify-content: center;
  }
}

.graph-loading, .graph-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: #909399;
}

.graph-stats {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
}

.graph-container {
  width: 100%;
  height: 500px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  overflow: hidden;
}

.preprocessor-tooltip {
  p {
    margin: 4px 0;
    font-size: 13px;
    line-height: 1.5;
  }
}

// 操作按钮样式
.action-buttons {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0;
  white-space: nowrap;
  
  .el-button {
    padding: 2px 6px;
    font-size: 13px;
    margin: 0;
    
    .el-icon {
      margin-right: 2px;
      font-size: 14px;
    }
  }
}

// 上传对话框样式
:deep(.el-dialog) {
  border-radius: 16px;
  
  .el-dialog__header {
    padding: 20px 24px;
    border-bottom: 1px solid rgba(64, 158, 255, 0.1);
    
    .el-dialog__title {
      font-weight: 600;
      color: #303133;
    }
  }
  
  .el-dialog__body {
    padding: 24px;
  }
  
  .el-dialog__footer {
    padding: 16px 24px;
    border-top: 1px solid rgba(64, 158, 255, 0.1);
  }
}

.category-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  
  :deep(.el-radio-button) {
    .el-radio-button__inner {
      border-radius: 8px !important;
      border: 1px solid #dcdfe6;
      padding: 10px 16px;
    }
    
    &.is-active .el-radio-button__inner {
      background: linear-gradient(135deg, #409EFF, #00D4AA);
      border-color: #409EFF;
    }
  }
  
  .radio-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    
    .el-icon {
      font-size: 18px;
    }
    
    span {
      font-size: 13px;
    }
    
    small {
      font-size: 11px;
      opacity: 0.7;
    }
  }
}

.category-hint {
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(64, 158, 255, 0.05);
  border-radius: 8px;
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 8px;
  
  .el-icon {
    color: #409EFF;
  }
  
  &.user-specific {
    background: rgba(103, 194, 58, 0.05);
    .el-icon { color: #67C23A; }
  }
  
  &.manual {
    background: rgba(230, 162, 60, 0.05);
    .el-icon { color: #E6A23C; }
  }
}
</style>
