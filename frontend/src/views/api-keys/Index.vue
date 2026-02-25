<template>
  <div class="api-keys-page">
    <div class="page-header">
      <h1 class="page-title">API Key 管理</h1>
      <el-button type="primary" @click="openAddDialog">
        <el-icon><Plus /></el-icon>
        添加 API Key
      </el-button>
    </div>
    
    <!-- 说明卡片 -->
    <div class="info-card">
      <el-icon :size="20"><InfoFilled /></el-icon>
      <div class="info-content">
        <p>API Key 用于访问 AI 模型服务。您可以配置多个不同提供商的 API Key，系统将使用默认的 Key 进行创意生成。</p>
        <p>添加后请点击"测试连接"按钮验证配置是否正确。</p>
      </div>
    </div>
    
    <!-- 模型类型筛选 -->
    <div class="type-filter">
      <span class="filter-label">模型类型：</span>
      <el-radio-group v-model="selectedType" size="small">
        <el-radio-button label="all">全部</el-radio-button>
        <el-radio-button label="text">
          <el-icon><EditPen /></el-icon> 文本模型
        </el-radio-button>
        <el-radio-button label="image">
          <el-icon><Picture /></el-icon> 图像模型
        </el-radio-button>
      </el-radio-group>
    </div>
    
     <!-- 未设置默认Key警告 -->
    <el-alert
      v-if="apiKeyStore.apiKeys.length > 0 && !apiKeyStore.defaultKey"
      type="warning"
      title="未设置默认API Key"
      description="请点击任意Key的[设为默认]按钮，否则无法进行创意生成。"
      show-icon
      :closable="false"
      style="margin-bottom: 16px;"
    />
    
    <!-- API Key 列表 -->
    <div class="keys-list">
      <el-empty v-if="!filteredApiKeys.length && !apiKeyStore.loading" description="暂无 API Key">
        <el-button type="primary" @click="openAddDialog">立即添加</el-button>
      </el-empty>
      
      <div v-else class="key-cards">
        <div
          v-for="key in filteredApiKeys"
          :key="key.id"
          class="key-card"
          :class="{ 'is-default': key.is_default }"
        >
          <div class="key-header">
            <div class="provider-badges">
              <div class="provider-badge" :style="{ background: getProviderColor(key.provider) }">
                {{ getProviderLabel(key.provider) }}
              </div>
              <el-tag v-if="getProviderType(key.provider) === 'image'" type="warning" size="small">
                <el-icon><Picture /></el-icon> 图像
              </el-tag>
              <el-tag v-else type="primary" size="small">
                <el-icon><EditPen /></el-icon> 文本
              </el-tag>
            </div>
            <div class="header-tags">
              <el-tag v-if="key.is_default" type="success" size="small">默认</el-tag>
              <el-tag v-if="key.test_status === 'success'" type="success" size="small">
                <el-icon><CircleCheck /></el-icon> 已验证
              </el-tag>
              <el-tag v-else-if="key.test_status === 'failed'" type="danger" size="small">
                <el-icon><CircleClose /></el-icon> 验证失败
              </el-tag>
            </div>
          </div>
          
          <div class="key-info">
            <div class="info-row">
              <span class="label">模型</span>
              <span class="value">{{ key.model_name }}</span>
            </div>
            <div class="info-row" v-if="key.api_base">
              <span class="label">API地址</span>
              <span class="value api-base">{{ key.api_base }}</span>
            </div>
            <div class="info-row">
              <span class="label">Key</span>
              <span class="value masked">{{ key.api_key_masked }}</span>
            </div>
            <div class="info-row">
              <span class="label">添加时间</span>
              <span class="value">{{ formatDate(key.created_at) }}</span>
            </div>
          </div>
          
          <div class="key-actions">
            <el-button
              type="primary"
              text
              :loading="testingId === key.id"
              @click="testConnection(key)"
            >
              测试连接
            </el-button>
            <el-button
              v-if="!key.is_default"
              type="success"
              text
              @click="setDefault(key.id)"
            >
              设为默认
            </el-button>
            <el-popconfirm
              title="确定删除此 API Key？"
              @confirm="removeKey(key.id)"
            >
              <template #reference>
                <el-button type="danger" text>删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 添加 API Key 对话框 -->
    <el-dialog
      v-model="showAddDialog"
      title="添加 API Key"
      width="550px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <!-- 模型类型选择 -->
        <el-form-item label="模型类型" prop="model_type">
          <el-radio-group v-model="form.model_type" @change="onModelTypeChange">
            <el-radio-button label="text">
              <el-icon><EditPen /></el-icon> 文本模型
            </el-radio-button>
            <el-radio-button label="image">
              <el-icon><Picture /></el-icon> 图像模型
            </el-radio-button>
          </el-radio-group>
          <div class="form-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>文本模型用于创意生成，图像模型用于图片生成/编辑</span>
          </div>
        </el-form-item>
        
        <el-form-item label="提供商" prop="provider">
          <el-select v-model="form.provider" placeholder="选择提供商" style="width: 100%" @change="onProviderChange">
            <el-option
              v-for="p in filteredProviders"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
          <div class="form-tip" v-if="currentProviderDoc">
            <el-icon><Link /></el-icon>
            <a :href="currentProviderDoc" target="_blank">获取 API Key</a>
          </div>
          <!-- 服务商特殊说明 -->
          <div class="provider-notice" v-if="currentProviderNotice">
            <el-icon><WarningFilled /></el-icon>
            <span>{{ currentProviderNotice }}</span>
          </div>
        </el-form-item>
        
        <!-- API Base - 用户自行填写 -->
        <el-form-item label="API地址" prop="api_base" v-if="form.provider && form.provider !== 'google'">
          <el-input
            v-model="form.api_base"
            placeholder="如：https://api.deepseek.com/v1"
            clearable
          />
          <div class="form-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>OpenAI兼容API地址，通常以 /v1 结尾</span>
          </div>
        </el-form-item>
        
        <!-- 模型名称 - 用户自行填写 -->
        <el-form-item label="模型名称" prop="model_name">
          <el-select 
            v-model="form.model_name" 
            placeholder="选择或直接输入模型名称" 
            style="width: 100%" 
            filterable
            allow-create
            clearable
          >
            <el-option
              v-for="m in availableModels"
              :key="m.id"
              :label="m.name"
              :value="m.id"
            >
              <div class="model-option">
                <div class="model-name">
                  <span>{{ m.name }}</span>
                  <el-tag v-if="m.vision" type="success" size="small" class="vision-tag">
                    <el-icon><Picture /></el-icon> 多模态
                  </el-tag>
                  <span class="context-badge">{{ m.context }}</span>
                </div>
                <div class="model-desc" v-if="m.description">{{ m.description }}</div>
              </div>
            </el-option>
          </el-select>
          <div class="form-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>可直接输入自定义模型名称（如豆包的Endpoint ID）</span>
          </div>
        </el-form-item>
        
        <el-form-item label="API Key" prop="api_key">
          <el-input
            v-model="form.api_key"
            placeholder="请输入 API Key"
            show-password
          />
        </el-form-item>
        
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="testBeforeAdd" :loading="testingNew">
          <el-icon><Connection /></el-icon>
          测试连接
        </el-button>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAdd">
          添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useApiKeyStore } from '@/stores'
import { LLM_PROVIDERS } from '@/config'
import { apiKeyApi } from '@/api'

const apiKeyStore = useApiKeyStore()

const showAddDialog = ref(false)
const submitting = ref(false)
const testingNew = ref(false)
const testingId = ref(null)
const formRef = ref()
const selectedType = ref('all')

const form = ref({
  model_type: 'text',
  provider: '',
  api_base: '',
  model_name: '',
  api_key: '',
  is_default: true
})

const rules = {
  model_type: [{ required: true, message: '请选择模型类型', trigger: 'change' }],
  provider: [{ required: true, message: '请选择提供商', trigger: 'change' }],
  model_name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }]
}

// 根据类型筛选提供商
const filteredProviders = computed(() => {
  if (form.value.model_type === 'all') return LLM_PROVIDERS
  return LLM_PROVIDERS.filter(p => p.type === form.value.model_type)
})

// 根据类型筛选已添加的API Key
const filteredApiKeys = computed(() => {
  if (selectedType.value === 'all') return apiKeyStore.apiKeys
  return apiKeyStore.apiKeys.filter(key => {
    const provider = LLM_PROVIDERS.find(p => p.value === key.provider)
    return provider?.type === selectedType.value
  })
})

const currentProviderDoc = computed(() => {
  const provider = LLM_PROVIDERS.find(p => p.value === form.value.provider)
  return provider?.doc_url
})

const currentProviderNotice = computed(() => {
  const provider = LLM_PROVIDERS.find(p => p.value === form.value.provider)
  return provider?.notice
})

const availableModels = computed(() => {
  const provider = LLM_PROVIDERS.find(p => p.value === form.value.provider)
  return provider?.models || []
})

onMounted(async () => {
  await apiKeyStore.fetchApiKeys()
})

function openAddDialog() {
  resetForm()
  showAddDialog.value = true
}

function onModelTypeChange() {
  form.value.provider = ''
  form.value.model_name = ''
  form.value.api_base = ''
}

function onProviderChange() {
  form.value.model_name = ''
  // 自动填充默认API地址
  const provider = LLM_PROVIDERS.find(p => p.value === form.value.provider)
  form.value.api_base = provider?.api_base || ''
}

async function testConnection(key) {
  testingId.value = key.id
  try {
    const res = await apiKeyApi.testSaved(key.id)
    
    if (res.data?.success) {
      ElMessage.success('连接测试成功！API Key 配置正确')
      key.test_status = 'success'
      key.is_valid = true
    } else {
      ElMessage.error(res.data?.message || '连接测试失败')
      key.test_status = 'failed'
      key.is_valid = false
    }
  } catch (error) {
    console.error('测试失败:', error)
    ElMessage.error(error.response?.data?.detail || '连接测试失败')
    key.test_status = 'failed'
  } finally {
    testingId.value = null
  }
}

async function testBeforeAdd() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  testingNew.value = true
  try {
    const res = await apiKeyApi.test({
      provider: form.value.provider,
      model_name: form.value.model_name,
      api_key: form.value.api_key,
      api_base: form.value.api_base || null
    })
    
    if (res.data?.success) {
      ElMessage.success('连接测试成功！可以添加此 API Key')
    } else {
      ElMessage.error(res.data?.message || '连接测试失败，请检查配置')
    }
  } catch (error) {
    console.error('测试失败:', error)
    ElMessage.error(error.response?.data?.detail || '连接测试失败')
  } finally {
    testingNew.value = false
  }
}

async function handleAdd() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  submitting.value = true
  try {
    await apiKeyStore.addApiKey({ 
      provider: form.value.provider,
      model_name: form.value.model_name,
      api_key: form.value.api_key,
      api_base: form.value.api_base || null,
      is_default: form.value.is_default
    })
    ElMessage.success('添加成功')
    showAddDialog.value = false
    resetForm()
  } catch (error) {
    console.error('添加失败:', error)
  } finally {
    submitting.value = false
  }
}

async function setDefault(id) {
  try {
    await apiKeyStore.setDefaultKey(id)
    ElMessage.success('已设为默认')
  } catch (error) {
    console.error('设置失败:', error)
  }
}

async function removeKey(id) {
  try {
    await apiKeyStore.removeApiKey(id)
    ElMessage.success('删除成功')
  } catch (error) {
    console.error('删除失败:', error)
  }
}

function resetForm() {
  form.value = {
    model_type: 'text',
    provider: '',
    api_base: '',
    model_name: '',
    api_key: '',
    is_default: false
  }
}

function getProviderLabel(provider) {
  const p = LLM_PROVIDERS.find(p => p.value === provider)
  return p?.label || provider
}

function getProviderType(provider) {
  const p = LLM_PROVIDERS.find(p => p.value === provider)
  return p?.type || 'text'
}

function getProviderColor(provider) {
  const colors = {
    qianwen: '#722ed1',
    'qianwen-image': '#9c27b0',
    doubao: '#ff4d4f',
    'doubao-image': '#ff7875',
    siliconflow: '#2f54eb',
    openrouter: '#10a37f'
  }
  return colors[provider] || '#909399'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}
</script>

<style lang="scss" scoped>
.api-keys-page {
  max-width: 900px;
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

.info-card {
  display: flex;
  gap: 12px;
  background: #f0f9ff;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 20px;
  color: #409EFF;
  
  .info-content {
    p {
      color: #606266;
      font-size: 14px;
      line-height: 1.6;
      margin: 0;
      
      & + p {
        margin-top: 6px;
      }
    }
  }
}

.type-filter {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  
  .filter-label {
    font-size: 14px;
    color: #606266;
  }
}

.key-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.key-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  border: 2px solid #eee;
  transition: all 0.3s;
  
  &:hover {
    border-color: #409EFF;
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
  }
  
  &.is-default {
    border-color: #67C23A;
  }
  
  .key-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    
    .provider-badges {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .provider-badge {
      padding: 4px 12px;
      border-radius: 4px;
      color: #fff;
      font-size: 12px;
      font-weight: 500;
    }
    
    .header-tags {
      display: flex;
      gap: 6px;
    }
  }
  
  .key-info {
    margin-bottom: 16px;
    
    .info-row {
      display: flex;
      margin-bottom: 8px;
      
      .label {
        width: 70px;
        color: #909399;
        font-size: 13px;
        flex-shrink: 0;
      }
      
      .value {
        flex: 1;
        color: #303133;
        font-size: 13px;
        word-break: break-all;
        
        &.masked {
          font-family: monospace;
          background: #f5f5f5;
          padding: 2px 6px;
          border-radius: 4px;
        }
        
        &.api-base {
          font-size: 12px;
          color: #909399;
        }
      }
    }
  }
  
  .key-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding-top: 12px;
    border-top: 1px solid #eee;
  }
}

.form-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
  
  a {
    color: #409EFF;
    text-decoration: none;
    
    &:hover {
      text-decoration: underline;
    }
  }
}

// 服务商特殊说明
.provider-notice {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fdf6ec;
  border-radius: 4px;
  font-size: 12px;
  color: #e6a23c;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  
  .el-icon {
    margin-top: 2px;
    flex-shrink: 0;
  }
  
  span {
    line-height: 1.5;
  }
}

// 模型选择器样式
.model-option {
  padding: 4px 0;
  
  .model-name {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
    
    .vision-tag {
      .el-icon {
        margin-right: 2px;
      }
    }
    
    .context-badge {
      font-size: 12px;
      color: #909399;
      font-weight: normal;
    }
  }
  
  .model-desc {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
    line-height: 1.4;
  }
}
</style>
