<template>
  <div class="profile-page">
    <h1 class="page-title">系统设置</h1>
    
    <div class="profile-container">
      <!-- 网络代理设置 -->
      <div class="profile-section">
        <h3>
          网络代理设置
          <el-tag v-if="proxyConfig.is_enabled" type="success" size="small" style="margin-left: 10px">已启用</el-tag>
          <el-tag v-else type="info" size="small" style="margin-left: 10px">已禁用</el-tag>
        </h3>
        <p class="section-tip">配置代理用于访问外网资源（如下载AI模型）。如果您使用科学上网工具，请填写您的代理端口。</p>
        
        <el-form :model="proxyConfig" label-width="100px" v-loading="proxyLoading">
          <el-form-item label="启用代理">
            <el-switch v-model="proxyConfig.is_enabled" />
            <span class="form-tip">启用后将使用代理访问外网资源</span>
          </el-form-item>
          
          <el-form-item label="HTTP代理">
            <el-input 
              v-model="proxyConfig.http_proxy" 
              placeholder="http://127.0.0.1:您的端口"
              :disabled="!proxyConfig.is_enabled"
            >
              <template #prepend>http://127.0.0.1:</template>
            </el-input>
            <span class="form-tip">请填写您的代理端口，如 7897</span>
          </el-form-item>
          
          <el-form-item label="HTTPS代理">
            <el-input 
              v-model="proxyConfig.https_proxy" 
              placeholder="https://127.0.0.1:您的端口"
              :disabled="!proxyConfig.is_enabled"
            >
              <template #prepend>https://127.0.0.1:</template>
            </el-input>
            <span class="form-tip">大多数HTTPS资源需要使用此代理</span>
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" @click="saveProxyConfig" :loading="proxySaving">保存代理设置</el-button>
            <el-button @click="testProxy" :loading="proxyTesting">测试连接</el-button>
          </el-form-item>
        </el-form>
        
        <el-alert
          v-if="proxyTestResult"
          :title="proxyTestResult.message"
          :type="proxyTestResult.success ? 'success' : 'error'"
          show-icon
          closable
          @close="proxyTestResult = null"
          style="margin-top: 16px"
        />
      </div>
      
      <!-- 文档预处理设置 -->
      <div class="profile-section">
        <h3>
          文档预处理设置
          <el-tag v-if="preprocessorConfig.doc_preprocessor_enabled" type="success" size="small" style="margin-left: 10px">已启用</el-tag>
          <el-tag v-else type="info" size="small" style="margin-left: 10px">已禁用</el-tag>
        </h3>
        <p class="section-tip">配置知识库文档的预处理方式，优化GraphRAG检索效果。</p>
        
        <el-form :model="preprocessorConfig" label-width="120px" v-loading="preprocessorLoading">
          <el-form-item label="启用预处理">
            <el-switch v-model="preprocessorConfig.doc_preprocessor_enabled" />
            <span class="form-tip">启用后将使用三层流水线处理文档（Cleaner-Filter-Refiner）</span>
          </el-form-item>
          
          <el-divider content-position="left">Cleaner 层 - 文档转换</el-divider>
          
          <el-form-item label="Marker转换">
            <el-switch 
              v-model="preprocessorConfig.marker_enabled" 
              :disabled="!preprocessorConfig.doc_preprocessor_enabled"
            />
            <span class="form-tip">使用Marker将PDF/DOCX转换为高质量Markdown</span>
          </el-form-item>
          
          <el-divider content-position="left">Refiner 层 - 语义切片</el-divider>
          
          <el-form-item label="语义切片">
            <el-switch 
              v-model="preprocessorConfig.semantic_chunk_enabled" 
              :disabled="!preprocessorConfig.doc_preprocessor_enabled"
            />
            <span class="form-tip">基于语义相似度智能划分文本边界</span>
          </el-form-item>
          
          <el-form-item label="切片大小" v-if="preprocessorConfig.semantic_chunk_enabled">
            <el-slider 
              v-model="preprocessorConfig.semantic_chunk_size" 
              :min="256" 
              :max="4096" 
              :step="128"
              :disabled="!preprocessorConfig.doc_preprocessor_enabled"
              show-input
              style="max-width: 400px"
            />
            <span class="form-tip">每个切片的最大Token数</span>
          </el-form-item>
          
          <el-form-item label="语义阈值" v-if="preprocessorConfig.semantic_chunk_enabled">
            <el-slider 
              v-model="preprocessorConfig.semantic_threshold" 
              :min="0.1" 
              :max="1.0" 
              :step="0.1"
              :disabled="!preprocessorConfig.doc_preprocessor_enabled"
              show-input
              style="max-width: 400px"
            />
            <span class="form-tip">相似度阈值，越低分块越大</span>
          </el-form-item>
          
          <el-divider content-position="left">可选 - 摘要压缩</el-divider>
          
          <el-form-item label="摘要压缩">
            <el-switch 
              v-model="preprocessorConfig.summarization_enabled" 
              :disabled="!preprocessorConfig.doc_preprocessor_enabled"
            />
            <span class="form-tip">将长文本压缩为"事实清单"，降低50%+Token消耗（需要LLM）</span>
          </el-form-item>
          
          <el-divider content-position="left">知识图谱</el-divider>
          
          <el-form-item label="GraphRAG">
            <el-switch 
              v-model="preprocessorConfig.graphrag_enabled"
            />
            <span class="form-tip">启用后将使用LLM提取文档实体和关系，构建知识图谱（消耗Token但检索更精准）</span>
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" @click="savePreprocessorConfig" :loading="preprocessorSaving">保存预处理设置</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { userConfigApi } from '@/api'

// 代理配置
const proxyLoading = ref(false)
const proxySaving = ref(false)
const proxyTesting = ref(false)
const proxyTestResult = ref(null)
const proxyConfig = ref({
  http_proxy: '',
  https_proxy: '',
  is_enabled: false,
  model_cache_dir: ''
})

// 预处理配置
const preprocessorLoading = ref(false)
const preprocessorSaving = ref(false)
const preprocessorConfig = ref({
  doc_preprocessor_enabled: true,
  marker_enabled: true,
  semantic_chunk_enabled: true,
  semantic_chunk_size: 1024,
  semantic_threshold: 0.7,
  summarization_enabled: false,
  graphrag_enabled: true,
  marker_model_dir: ''
})

onMounted(() => {
  loadProxyConfig()
  loadPreprocessorConfig()
})

// 加载代理配置
async function loadProxyConfig() {
  proxyLoading.value = true
  try {
    const res = await userConfigApi.getProxyConfig()
    if (res.data) {
      proxyConfig.value = {
        http_proxy: res.data.http_proxy || '',
        https_proxy: res.data.https_proxy || '',
        is_enabled: res.data.is_enabled ?? false,
        model_cache_dir: res.data.model_cache_dir || ''
      }
    }
  } catch (error) {
    console.error('加载代理配置失败:', error)
  } finally {
    proxyLoading.value = false
  }
}

// 保存代理配置
async function saveProxyConfig() {
  proxySaving.value = true
  try {
    await userConfigApi.setProxyConfig({
      http_proxy: proxyConfig.value.http_proxy || null,
      https_proxy: proxyConfig.value.https_proxy || null,
      is_enabled: proxyConfig.value.is_enabled
    })
    ElMessage.success('代理配置已保存')
  } catch (error) {
    console.error('保存代理配置失败:', error)
    ElMessage.error('保存失败')
  } finally {
    proxySaving.value = false
  }
}

// 测试代理
async function testProxy() {
  proxyTesting.value = true
  proxyTestResult.value = null
  try {
    const res = await userConfigApi.testProxy()
    proxyTestResult.value = res.data
  } catch (error) {
    console.error('测试代理失败:', error)
    proxyTestResult.value = { success: false, message: '测试请求失败' }
  } finally {
    proxyTesting.value = false
  }
}

// 加载预处理配置
async function loadPreprocessorConfig() {
  preprocessorLoading.value = true
  try {
    const res = await userConfigApi.getPreprocessorConfig()
    if (res.data) {
      preprocessorConfig.value = {
        doc_preprocessor_enabled: res.data.doc_preprocessor_enabled ?? true,
        marker_enabled: res.data.marker_enabled ?? true,
        semantic_chunk_enabled: res.data.semantic_chunk_enabled ?? true,
        semantic_chunk_size: res.data.semantic_chunk_size ?? 1024,
        semantic_threshold: res.data.semantic_threshold ?? 0.7,
        summarization_enabled: res.data.summarization_enabled ?? false,
        graphrag_enabled: res.data.graphrag_enabled ?? true,
        marker_model_dir: res.data.marker_model_dir || ''
      }
    }
  } catch (error) {
    console.error('加载预处理配置失败:', error)
  } finally {
    preprocessorLoading.value = false
  }
}

// 保存预处理配置
async function savePreprocessorConfig() {
  preprocessorSaving.value = true
  try {
    await userConfigApi.setPreprocessorConfig({
      doc_preprocessor_enabled: preprocessorConfig.value.doc_preprocessor_enabled,
      marker_enabled: preprocessorConfig.value.marker_enabled,
      semantic_chunk_enabled: preprocessorConfig.value.semantic_chunk_enabled,
      semantic_chunk_size: preprocessorConfig.value.semantic_chunk_size,
      semantic_threshold: preprocessorConfig.value.semantic_threshold,
      summarization_enabled: preprocessorConfig.value.summarization_enabled,
      graphrag_enabled: preprocessorConfig.value.graphrag_enabled
    })
    ElMessage.success('预处理配置已保存')
  } catch (error) {
    console.error('保存预处理配置失败:', error)
    ElMessage.error('保存失败')
  } finally {
    preprocessorSaving.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}
</script>

<style lang="scss" scoped>
.profile-page {
  max-width: 800px;
  margin: 0 auto;
}

.profile-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.profile-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  
  h3 {
    font-size: 16px;
    color: #303133;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 1px solid #eee;
    display: flex;
    align-items: center;
  }
  
  .section-tip {
    color: #909399;
    font-size: 13px;
    margin-top: -10px;
    margin-bottom: 16px;
  }
  
  .form-tip {
    margin-left: 12px;
    color: #909399;
    font-size: 12px;
  }
  
  &.danger-zone {
    border: 1px solid #fde2e2;
    background: #fef0f0;
    
    h3 {
      color: #F56C6C;
      border-bottom-color: #fde2e2;
    }
    
    .warning-text {
      color: #909399;
      font-size: 13px;
      margin-bottom: 15px;
    }
  }
}

.account-info {
  .info-row {
    display: flex;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid #f5f5f5;
    
    &:last-child {
      border-bottom: none;
    }
    
    .label {
      width: 100px;
      color: #909399;
    }
    
    .value {
      color: #303133;
    }
  }
}

:deep(.el-divider__text) {
  font-size: 13px;
  color: #909399;
}
</style>
