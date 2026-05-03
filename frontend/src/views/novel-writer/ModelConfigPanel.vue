<!--
  多Agent协作文学作品生成系统 - 模型配置管理面板
  
  模块: writing-engine
  文件: ModelConfigPanel.vue
  功能: 预配置AI模型，在写作工作台中快速选择使用
  
  依赖关系:
      - API: /api/v1/writing-model-configs/*
      - Element Plus组件
  
  创建时间: 2026-03-28
  最后修改: 2026-03-28
  版本: 1.0.0
-->
<template>
  <div class="model-config-panel">
    <!-- 顶部操作栏 -->
    <div class="panel-header">
      <div class="header-left">
        <h3>模型配置管理</h3>
        <span class="subtitle">预配置AI模型，在写作工作台中快速选择使用</span>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon> 添加配置
        </el-button>
        <el-button @click="handleExport">
          <el-icon><Download /></el-icon> 导出
        </el-button>
        <el-upload :show-file-list="false" accept=".json" :before-upload="handleImport">
          <el-button>
            <el-icon><Upload /></el-icon> 导入
          </el-button>
        </el-upload>
      </div>
    </div>

    <!-- 提示信息 -->
    <el-alert 
      v-if="configs.length === 0" 
      title="暂无模型配置" 
      description="请点击'添加配置'按钮预配置AI模型，配置后可在写作工作台中直接选择使用。" 
      type="info" 
      :closable="false" 
      show-icon 
      style="margin-bottom: 20px" 
    />

    <!-- 配置卡片网格 -->
    <el-row :gutter="16" v-loading="loading">
      <el-col 
        :xs="24" 
        :sm="12" 
        :md="8" 
        :lg="6" 
        v-for="config in configs" 
        :key="config.id" 
        style="margin-bottom: 16px"
      >
        <el-card 
          shadow="hover" 
          class="config-card" 
          :class="{ 'is-invalid': !config.is_valid, 'is-inactive': !config.is_active }"
        >
          <!-- 卡片头部 -->
          <div class="card-header">
            <el-tag 
              :color="getProviderColor(config.provider)" 
              effect="dark" 
              size="small" 
              style="color: #fff"
            >
              {{ config.provider_display || config.provider }}
            </el-tag>
            <div class="card-status">
              <el-tag v-if="config.is_valid" type="success" size="small" effect="plain">已验证</el-tag>
              <el-tag v-else type="warning" size="small" effect="plain">未验证</el-tag>
            </div>
          </div>
          
          <!-- 卡片内容 -->
          <div class="card-body">
            <div class="config-name">{{ config.name }}</div>
            <div class="config-detail">
              <span class="label">模型:</span>
              <span class="value">{{ config.model_id }}</span>
            </div>
            <div class="config-detail" v-if="config.api_base">
              <span class="label">API:</span>
              <span class="value" :title="config.api_base">{{ config.api_base }}</span>
            </div>
            <div class="config-detail">
              <span class="label">Key:</span>
              <span class="value">{{ config.api_key_masked }}</span>
            </div>
          </div>
          
          <!-- 卡片操作 -->
          <div class="card-actions">
            <el-button 
              size="small" 
              type="primary" 
              plain 
              :loading="testingId === config.id" 
              @click="handleTest(config.id)"
            >
              测试连接
            </el-button>
            <el-button size="small" plain @click="showEditDialog(config)">编辑</el-button>
            <el-button 
              size="small" 
              type="danger" 
              plain 
              @click="handleDelete(config.id, config.name)"
            >
              删除
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加/编辑弹窗 -->
    <el-dialog 
      v-model="dialogVisible" 
      :title="isEditing ? '编辑模型配置' : '添加模型配置'" 
      width="550px" 
      destroy-on-close
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="配置名称" prop="name">
          <el-input 
            v-model="formData.name" 
            placeholder="如：我的GPT-4配置" 
            maxlength="100" 
            show-word-limit 
          />
        </el-form-item>
        
        <el-form-item label="服务商" prop="provider">
          <el-select 
            v-model="formData.provider" 
            filterable 
            allow-create 
            placeholder="选择或输入服务商" 
            style="width: 100%" 
            @change="onProviderSelect"
          >
            <el-option 
              v-for="p in providerOptions" 
              :key="p.name" 
              :label="p.display_name" 
              :value="p.name" 
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="API地址" prop="api_base">
          <el-input 
            v-model="formData.api_base" 
            placeholder="API端点地址，如 https://api.example.com/v1" 
          />
        </el-form-item>
        
        <el-form-item label="模型ID" prop="model_id">
          <el-select 
            v-model="formData.model_id" 
            filterable 
            allow-create 
            default-first-option 
            placeholder="输入或选择模型ID" 
            style="width: 100%"
          >
            <el-option 
              v-for="m in currentProviderModels" 
              :key="m.id" 
              :label="m.name || m.id" 
              :value="m.id" 
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="API密钥" prop="api_key">
          <el-input 
            v-model="formData.api_key" 
            type="password" 
            show-password 
            :placeholder="isEditing ? '不修改请留空' : '请输入API密钥'" 
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button :loading="testingNew" @click="handleTestNew">
            测试连接
          </el-button>
          <div>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">
              {{ isEditing ? '保存' : '添加' }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { writingTaskApi } from '@/api/writing-task'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Upload } from '@element-plus/icons-vue'

// 数据
const configs = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const saving = ref(false)
const testingId = ref(null)
const testingNew = ref(false)
const formRef = ref(null)

// 预设Provider选项（降级列表，优先从API获取）
const providerOptions = ref([
  { 
    name: 'qianwen', 
    display_name: '通义千问 (阿里云百炼)', 
    api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', 
    models: [
      { id: 'qwen3.5-plus', name: 'Qwen3.5-Plus' },
      { id: 'qwen3.5-turbo', name: 'Qwen3.5-Turbo' },
      { id: 'qwen-max', name: 'Qwen-Max' }
    ]
  },
  { 
    name: 'doubao', 
    display_name: '豆包 (字节跳动/火山引擎)', 
    api_base: 'https://ark.cn-beijing.volces.com/api/v3', 
    models: [
      { id: 'doubao-seed-2-0-pro-260215', name: 'Doubao Seed 2.0 Pro' },
      { id: 'doubao-pro-32k', name: 'Doubao Pro 32K' }
    ]
  },
  { 
    name: 'siliconflow', 
    display_name: '硅基流动 (SiliconFlow)', 
    api_base: 'https://api.siliconflow.cn/v1', 
    models: [
      { id: 'deepseek-ai/DeepSeek-V3.2', name: 'DeepSeek V3.2' },
      { id: 'Qwen/Qwen3.5-72B-Instruct', name: 'Qwen3.5 72B' }
    ]
  },
  { 
    name: 'openrouter', 
    display_name: 'OpenRouter', 
    api_base: 'https://openrouter.ai/api/v1', 
    models: [
      { id: 'google/gemini-3.1-pro-preview', name: 'Gemini 3.1 Pro' },
      { id: 'openai/gpt-5.2-pro', name: 'GPT-5.2 Pro' },
      { id: 'anthropic/claude-opus-4.5', name: 'Claude Opus 4.5' }
    ]
  },
  { 
    name: 't8star', 
    display_name: '贞贞AI工坊', 
    api_base: 'https://ai.t8star.cn/v1', 
    models: [
      { id: 'gpt-5.2-pro', name: 'GPT-5.2 Pro' },
      { id: 'claude-opus-4-5-20251101', name: 'Claude Opus 4.5' },
      { id: 'gemini-3.1-pro', name: 'Gemini 3.1 Pro' }
    ]
  },
  { 
    name: 'deepseek', 
    display_name: 'DeepSeek', 
    api_base: 'https://api.deepseek.com', 
    models: [
      { id: 'deepseek-v4-pro', name: 'DeepSeek V4 Pro' },
      { id: 'deepseek-v4-flash', name: 'DeepSeek V4 Flash' },
      { id: 'deepseek-chat', name: 'DeepSeek Chat (旧版，即将弃用)' },
      { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner (旧版，即将弃用)' }
    ]
  },
  { 
    name: 'custom', 
    display_name: '自定义服务商', 
    api_base: '', 
    models: [] 
  }
])

const formData = ref({
  name: '',
  provider: '',
  provider_display: '',
  model_id: '',
  api_key: '',
  api_base: ''
})

const formRules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  provider: [{ required: true, message: '请选择服务商', trigger: 'change' }],
  model_id: [{ required: true, message: '请输入模型ID', trigger: 'blur' }],
  api_key: [] // 编辑时非必填，添加时在handleSave中手动验证
}

// 计算属性：当前选中provider的模型列表
const currentProviderModels = computed(() => {
  if (!formData.value.provider) return []
  const provider = providerOptions.value.find(p => p.name === formData.value.provider)
  return provider?.models || []
})

// 加载配置列表
async function loadConfigs() {
  loading.value = true
  try {
    const response = await writingTaskApi.getModelConfigs()
    // 后端返回格式: { data: [...配置列表], message: "..." }
    const configData = response.data?.data || response.data || []
    configs.value = Array.isArray(configData) ? configData : []
  } catch (error) {
    console.error('加载模型配置失败:', error)
    ElMessage.error(error.response?.data?.detail || '加载模型配置失败')
  } finally {
    loading.value = false
  }
}

// 显示添加弹窗
function showAddDialog() {
  resetForm()
  isEditing.value = false
  editingId.value = null
  dialogVisible.value = true
}

// 显示编辑弹窗
function showEditDialog(config) {
  isEditing.value = true
  editingId.value = config.id
  formData.value = {
    name: config.name,
    provider: config.provider,
    provider_display: config.provider_display || '',
    model_id: config.model_id,
    api_key: '', // 编辑时密钥留空
    api_base: config.api_base || ''
  }
  dialogVisible.value = true
}

// 重置表单
function resetForm() {
  formData.value = {
    name: '',
    provider: '',
    provider_display: '',
    model_id: '',
    api_key: '',
    api_base: ''
  }
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

// 选择provider后自动填充
function onProviderSelect(providerName) {
  const provider = providerOptions.value.find(p => p.name === providerName)
  if (provider) {
    formData.value.api_base = provider.api_base || ''
    formData.value.provider_display = provider.display_name
    formData.value.model_id = '' // 清空模型选择
  }
}

// 保存配置
async function handleSave() {
  // 验证表单
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  
  // 添加时验证api_key必填
  if (!isEditing.value && !formData.value.api_key) {
    ElMessage.warning('请输入API密钥')
    return
  }
  
  saving.value = true
  try {
    const submitData = {
      name: formData.value.name,
      provider: formData.value.provider,
      provider_display: formData.value.provider_display,
      model_id: formData.value.model_id,
      api_base: formData.value.api_base
    }
    
    // 只有填写了api_key才传递
    if (formData.value.api_key) {
      submitData.api_key = formData.value.api_key
    }
    
    if (isEditing.value) {
      await writingTaskApi.updateModelConfig(editingId.value, submitData)
      ElMessage.success('配置更新成功')
    } else {
      await writingTaskApi.createModelConfig(submitData)
      ElMessage.success('配置添加成功')
    }
    
    dialogVisible.value = false
    await loadConfigs()
  } catch (error) {
    console.error('保存配置失败:', error)
    ElMessage.error(error.response?.data?.detail || '保存配置失败')
  } finally {
    saving.value = false
  }
}

// 测试已保存配置
async function handleTest(id) {
  testingId.value = id
  try {
    const response = await writingTaskApi.testModelConfig(id)
    // 后端返回格式: { data: { success: boolean, message: string }, message: "..." }
    const result = response.data?.data || response.data || response
    
    if (result.success) {
      ElMessage.success('连接测试成功！模型配置正确')
      // 更新本地状态
      const config = configs.value.find(c => c.id === id)
      if (config) {
        config.is_valid = true
      }
    } else {
      ElMessage.error(result.message || '连接测试失败')
    }
  } catch (error) {
    console.error('测试失败:', error)
    ElMessage.error(error.response?.data?.detail || '连接测试失败')
  } finally {
    testingId.value = null
  }
}

// 测试未保存配置
async function handleTestNew() {
  // 基本验证
  if (!formData.value.provider) {
    ElMessage.warning('请选择服务商')
    return
  }
  if (!formData.value.model_id) {
    ElMessage.warning('请输入模型ID')
    return
  }
  if (!formData.value.api_key) {
    ElMessage.warning('请输入API密钥')
    return
  }
  
  testingNew.value = true
  try {
    const response = await writingTaskApi.testNewModelConfig({
      provider: formData.value.provider,
      model_id: formData.value.model_id,
      api_key: formData.value.api_key,
      api_base: formData.value.api_base
    })
    
    // 后端返回格式: { data: { success: boolean, message: string }, message: "..." }
    const result = response.data?.data || response.data || response
    if (result.success) {
      ElMessage.success('连接测试成功！可以保存此配置')
    } else {
      ElMessage.error(result.message || '连接测试失败')
    }
  } catch (error) {
    console.error('测试失败:', error)
    ElMessage.error(error.response?.data?.detail || '连接测试失败')
  } finally {
    testingNew.value = false
  }
}

// 删除配置
async function handleDelete(id, name) {
  try {
    await ElMessageBox.confirm(
      `确定删除配置「${name}」吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await writingTaskApi.deleteModelConfig(id)
    ElMessage.success('删除成功')
    await loadConfigs()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

// 导出配置
async function handleExport() {
  try {
    const response = await writingTaskApi.exportModelConfigs()
    // 后端返回格式: { data: { configs: [...], export_time: "..." }, message: "..." }
    const exportData = response.data?.data || response.data || response
    
    // 创建下载
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `model-configs-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error(error.response?.data?.detail || '导出失败')
  }
}

// 导入配置
async function handleImport(file) {
  try {
    const text = await file.text()
    const importData = JSON.parse(text)
    
    // 验证格式
    if (!importData.configs || !Array.isArray(importData.configs)) {
      ElMessage.error('无效的配置文件格式')
      return false
    }
    
    // 调用导入API
    const response = await writingTaskApi.importModelConfigs(importData)
    // 后端返回格式: { data: { success_count: number, failed_count: number }, message: "..." }
    const result = response.data?.data || response.data || response
    
    ElMessage.success(`成功导入 ${result.success_count || importData.configs.length} 个配置`)
    await loadConfigs()
  } catch (error) {
    console.error('导入失败:', error)
    if (error instanceof SyntaxError) {
      ElMessage.error('无效的JSON文件')
    } else {
      ElMessage.error(error.response?.data?.detail || '导入失败')
    }
  }
  return false // 阻止el-upload默认上传行为
}

// 获取provider颜色
function getProviderColor(provider) {
  const colors = {
    qianwen: '#722ed1',
    doubao: '#ff4d4f',
    siliconflow: '#2f54eb',
    openrouter: '#10a37f',
    t8star: '#ff6b35',
    deepseek: '#0066cc',
    custom: '#909399'
  }
  return colors[provider] || '#909399'
}

// 初始化
onMounted(() => {
  loadConfigs()
  // 可选：从API获取provider列表
  loadProviders()
})

// 加载provider列表（可选增强）
async function loadProviders() {
  try {
    const response = await writingTaskApi.getAvailableProviders()
    // 后端返回格式: { data: { providers: [...] }, message: "..." }
    const providers = response.data?.data?.providers || response.data?.providers || []
    if (providers.length > 0) {
      // 合并API返回的provider列表
      const existingNames = providerOptions.value.map(p => p.name)
      providers.forEach(p => {
        if (!existingNames.includes(p.name)) {
          providerOptions.value.push(p)
        }
      })
    }
  } catch (error) {
    // 静默失败，使用预设列表
    console.debug('使用预设Provider列表')
  }
}
</script>

<style lang="scss" scoped>
.model-config-panel {
  padding: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  
  .header-left {
    h3 {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
      margin: 0 0 4px 0;
    }
    
    .subtitle {
      font-size: 13px;
      color: #909399;
    }
  }
  
  .header-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
}

.config-card {
  border-radius: 8px;
  border: 2px solid #eee;
  transition: all 0.3s;
  
  &:hover {
    border-color: #409EFF;
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
  }
  
  &.is-invalid {
    border-color: #E6A23C;
  }
  
  &.is-inactive {
    opacity: 0.6;
  }
  
  :deep(.el-card__body) {
    padding: 16px;
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  
  .card-body {
    margin-bottom: 12px;
    
    .config-name {
      font-size: 15px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 10px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    .config-detail {
      display: flex;
      margin-bottom: 6px;
      font-size: 13px;
      
      .label {
        color: #909399;
        width: 40px;
        flex-shrink: 0;
      }
      
      .value {
        color: #606266;
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }
  }
  
  .card-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding-top: 12px;
    border-top: 1px solid #eee;
  }
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  
  > div {
    display: flex;
    gap: 8px;
  }
}
</style>
