<template>
  <div class="form-section">
    <h3>知识库增强</h3>
    <el-form-item>
      <div class="knowledge-switch-wrapper">
        <el-switch
          v-model="enableKnowledge"
          active-text="启用知识库增强"
          inactive-text="不使用知识库"
          :loading="loadingKnowledge"
          @change="handleKnowledgeChange"
        />
        <div class="knowledge-tip" v-if="enableKnowledge">
          <el-icon><InfoFilled /></el-icon>
          <span><strong>通用知识库</strong>将默认加载，提供基础理论支持</span>
        </div>
      </div>
    </el-form-item>

    <!-- 知识库类别选择（启用知识库后显示） -->
    <div v-if="enableKnowledge" class="kb-category-selector">
      <!-- 垂直领域知识库 -->
      <div class="kb-category-item">
        <div class="kb-category-header">
          <el-checkbox
            v-model="kbCategories.vertical.enabled"
            @change="onKbCategoryChange('vertical')"
          >
            <span class="category-title">垂直领域知识库</span>
            <el-tag size="small" type="info">可选</el-tag>
          </el-checkbox>
          <span class="category-desc">行业专业知识、实际案例、成品脚本、策划案等实践性资料</span>
        </div>
        <div v-if="kbCategories.vertical.enabled" class="kb-list-selector">
          <el-select
            v-model="kbCategories.vertical.ids"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择垂直领域知识库"
            :loading="loadingKbByCategory.vertical"
            style="width: 100%"
          >
            <el-option
              v-for="kb in kbCategories.vertical.list"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            />
          </el-select>
          <div v-if="kbCategories.vertical.list.length === 0 && !loadingKbByCategory.vertical" class="kb-empty-tip">
            暂无垂直领域知识库
          </div>
        </div>
      </div>

      <!-- 用户专属知识库 -->
      <div class="kb-category-item">
        <div class="kb-category-header">
          <el-checkbox
            v-model="kbCategories.userSpecific.enabled"
            @change="onKbCategoryChange('userSpecific')"
          >
            <span class="category-title">用户专属知识库</span>
            <el-tag size="small" type="success">GraphRAG</el-tag>
          </el-checkbox>
          <span class="category-desc">存储用户个性化知识，针对小众人物、专有名词、专业知识、个人经验等优化</span>
        </div>
        <div v-if="kbCategories.userSpecific.enabled" class="kb-list-selector">
          <el-select
            v-model="kbCategories.userSpecific.ids"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择用户专属知识库"
            :loading="loadingKbByCategory.userSpecific"
            style="width: 100%"
          >
            <el-option
              v-for="kb in kbCategories.userSpecific.list"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            />
          </el-select>
          <div v-if="kbCategories.userSpecific.list.length === 0 && !loadingKbByCategory.userSpecific" class="kb-empty-tip">
            暂无用户专属知识库
          </div>
        </div>
      </div>

      <!-- 官方手册知识库 -->
      <div class="kb-category-item">
        <div class="kb-category-header">
          <el-checkbox
            v-model="kbCategories.manual.enabled"
            @change="onKbCategoryChange('manual')"
          >
            <span class="category-title">官方手册知识库</span>
            <el-tag size="small" type="warning">可选</el-tag>
          </el-checkbox>
          <span class="category-desc">官方规范、标准手册、产品文档、技术文档等参考资料</span>
        </div>
        <div v-if="kbCategories.manual.enabled" class="kb-list-selector">
          <el-select
            v-model="kbCategories.manual.ids"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择官方手册知识库"
            :loading="loadingKbByCategory.manual"
            style="width: 100%"
          >
            <el-option
              v-for="kb in kbCategories.manual.list"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            />
          </el-select>
          <div v-if="kbCategories.manual.list.length === 0 && !loadingKbByCategory.manual" class="kb-empty-tip">
            暂无官方手册知识库
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 创作辅助搜索开关 -->
  <div class="form-section">
    <h3>创作辅助搜索</h3>
    <el-form-item>
      <div class="knowledge-switch-wrapper">
        <el-switch
          v-model="enableCreativeSearch"
          active-text="启用联网搜索"
          inactive-text="不使用联网搜索"
        />
        <div class="knowledge-tip" v-if="enableCreativeSearch">
          <el-icon><InfoFilled /></el-icon>
          <span>智能搜索创作素材和背景信息，如地理、历史、文化等资料，提升创作准确性</span>
        </div>
      </div>
    </el-form-item>
    <!-- 自定义搜索关键词 -->
    <el-form-item v-if="enableCreativeSearch" label="搜索关键词">
      <el-input
        v-model="searchKeywords"
        placeholder="输入自定义搜索关键词（可选，多个关键词用逗号分隔）"
        clearable
      >
        <template #prepend>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <div class="input-tip">
        <el-icon><InfoFilled /></el-icon>
        <span>留空则系统自动分析并提取关键词；填写后将使用您指定的关键词进行精准搜索</span>
      </div>
    </el-form-item>
  </div>

  <!-- 实时热点开关 -->
  <div class="form-section">
    <h3>实时热点</h3>
    <el-form-item>
      <div class="knowledge-switch-wrapper">
        <el-switch
          v-model="enableTrending"
          active-text="启用实时热点"
          inactive-text="不使用热点数据"
        />
        <div class="knowledge-tip" v-if="enableTrending">
          <el-icon><InfoFilled /></el-icon>
          <span>获取<strong>微博、知乎、抖音、B站</strong>等平台实时热点数据，为创意提供灵感参考</span>
        </div>
      </div>
    </el-form-item>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { knowledgeApi } from '@/api'
import { useConfigPersistence } from '@/composables/useConfigPersistence'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  },
  /** 持久化存储键名，传入后自动启用 localStorage 持久化 */
  storageKey: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['update:modelValue'])

// 知识库状态
const knowledgeBases = ref([])
const loadingKnowledge = ref(false)
const enableKnowledge = ref(false)
const enableCreativeSearch = ref(false)
const searchKeywords = ref('')
const enableTrending = ref(false)

// 知识库类别选择
const kbCategories = ref({
  vertical: { enabled: false, ids: [], list: [] },
  userSpecific: { enabled: false, ids: [], list: [] },
  manual: { enabled: false, ids: [], list: [] }
})

const loadingKbByCategory = ref({
  vertical: false,
  userSpecific: false,
  manual: false
})

// 加载知识库列表
async function loadKnowledgeBases() {
  loadingKnowledge.value = true
  try {
    const res = await knowledgeApi.list({ status: 'ready' })
    knowledgeBases.value = res.data || []
    categorizeKnowledgeBases(res.data || [])
  } catch (error) {
    console.error('加载知识库列表失败:', error)
  } finally {
    loadingKnowledge.value = false
  }
}

// 按类别分组知识库
function categorizeKnowledgeBases(kbs) {
  const verticalCategories = ['short-video', 'novel', 'print-ad', 'tvc', 'movie-outline', 'series-outline']
  kbCategories.value.vertical.list = kbs.filter(kb => verticalCategories.includes(kb.category))
  kbCategories.value.userSpecific.list = kbs.filter(kb => kb.category === 'user-specific')
  kbCategories.value.manual.list = kbs.filter(kb => kb.category === 'manual')
}

// 加载指定类别的知识库
async function loadKbByCategory(category) {
  loadingKbByCategory.value[category] = true
  try {
    if (category === 'vertical') {
      const verticalCategories = ['short-video', 'novel', 'print-ad', 'tvc', 'movie-outline', 'series-outline']
      const allResults = []
      for (const cat of verticalCategories) {
        const res = await knowledgeApi.list({ status: 'ready', category: cat })
        if (res.data) {
          allResults.push(...res.data)
        }
      }
      kbCategories.value.vertical.list = allResults
    } else {
      const res = await knowledgeApi.list({ status: 'ready', category: category })
      if (category === 'userSpecific' || category === 'user-specific') {
        kbCategories.value.userSpecific.list = res.data || []
      } else if (category === 'manual') {
        kbCategories.value.manual.list = res.data || []
      }
    }
  } catch (error) {
    console.error(`加载${category}知识库失败:`, error)
  } finally {
    loadingKbByCategory.value[category] = false
  }
}

// 知识库开关变化
function handleKnowledgeChange(val) {
  updateModelValue()
}

// 知识库类别勾选变化处理
function onKbCategoryChange(category) {
  if (kbCategories.value[category].enabled && kbCategories.value[category].list.length === 0) {
    loadKbByCategory(category)
  }
  if (!kbCategories.value[category].enabled) {
    kbCategories.value[category].ids = []
  }
  updateModelValue()
}

// 更新父组件的值
function updateModelValue() {
  emit('update:modelValue', {
    enableKnowledge: enableKnowledge.value,
    enableCreativeSearch: enableCreativeSearch.value,
    searchKeywords: searchKeywords.value,
    enableTrending: enableTrending.value,
    kbCategories: {
      vertical: { ...kbCategories.value.vertical },
      userSpecific: { ...kbCategories.value.userSpecific },
      manual: { ...kbCategories.value.manual }
    }
  })
}

onMounted(() => {
  loadKnowledgeBases()
  restoreKbConfig()
})

// ==================== 配置持久化（localStorage） ====================
const { saveConfig, restoreConfig } = useConfigPersistence()

function persistKbConfig() {
  if (!props.storageKey) return
  saveConfig(props.storageKey, {
    enableKnowledge: enableKnowledge.value,
    enableCreativeSearch: enableCreativeSearch.value,
    enableTrending: enableTrending.value,
    searchKeywords: searchKeywords.value,
    kbCategories: {
      vertical: { enabled: kbCategories.value.vertical.enabled, ids: kbCategories.value.vertical.ids },
      userSpecific: { enabled: kbCategories.value.userSpecific.enabled, ids: kbCategories.value.userSpecific.ids },
      manual: { enabled: kbCategories.value.manual.enabled, ids: kbCategories.value.manual.ids }
    }
  })
}

function restoreKbConfig() {
  if (!props.storageKey) return
  const saved = restoreConfig(props.storageKey)
  if (!saved) return
  enableKnowledge.value = saved.enableKnowledge ?? false
  enableCreativeSearch.value = saved.enableCreativeSearch ?? false
  enableTrending.value = saved.enableTrending ?? false
  searchKeywords.value = saved.searchKeywords ?? ''
  if (saved.kbCategories) {
    for (const cat of ['vertical', 'userSpecific', 'manual']) {
      if (saved.kbCategories[cat] && kbCategories.value[cat]) {
        kbCategories.value[cat].enabled = saved.kbCategories[cat].enabled ?? false
        kbCategories.value[cat].ids = saved.kbCategories[cat].ids ?? []
      }
    }
  }
  console.log('[KnowledgeBaseSection] 已恢复知识库配置')
}

// 自动持久化
watch([enableKnowledge, enableCreativeSearch, enableTrending, searchKeywords, kbCategories],
  () => persistKbConfig(),
  { deep: true }
)

// 暴露方法给父组件
defineExpose({
  loadKnowledgeBases,
  getKbParams: () => ({
    // 核心开关 - 必须传递给后端
    enableKnowledge: enableKnowledge.value,
    enableCreativeSearch: enableCreativeSearch.value,
    enableTrending: enableTrending.value,
    // 知识库类别开关
    kb_vertical: kbCategories.value.vertical.enabled,
    kb_user_specific: kbCategories.value.userSpecific.enabled,
    kb_manual: kbCategories.value.manual.enabled,
    // 知识库ID列表
    kb_vertical_ids: kbCategories.value.vertical.ids.length > 0 ? kbCategories.value.vertical.ids.join(',') : null,
    kb_user_specific_ids: kbCategories.value.userSpecific.ids.length > 0 ? kbCategories.value.userSpecific.ids.join(',') : null,
    kb_manual_ids: kbCategories.value.manual.ids.length > 0 ? kbCategories.value.manual.ids.join(',') : null,
    // 搜索关键词
    search_keywords: searchKeywords.value ? searchKeywords.value.split(/[,，]/).map(k => k.trim()).filter(k => k) : null
  })
})
</script>

<style lang="scss" scoped>
.form-section {
  margin-bottom: 28px;
  
  &:last-child {
    margin-bottom: 0;
  }
  
  h3 {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 2px solid rgba(64, 158, 255, 0.1);
    display: flex;
    align-items: center;
    gap: 10px;
    
    &::before {
      content: '';
      width: 4px;
      height: 18px;
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 2px;
    }
  }
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}

.knowledge-switch-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
  
  .knowledge-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px;
    background: #f0f9ff;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    font-size: 13px;
    color: #1e40af;
    
    strong {
      font-weight: 600;
      color: #1e3a8a;
    }
  }
}

.input-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  
  .el-icon {
    font-size: 14px;
    color: #409eff;
  }
}

.kb-category-selector {
  margin-top: 16px;
  padding: 16px;
  background: #fafbfc;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  
  .kb-category-item {
    padding: 12px;
    margin-bottom: 12px;
    background: #fff;
    border-radius: 6px;
    border: 1px solid #ebeef5;
    transition: all 0.3s;
    
    &:last-child {
      margin-bottom: 0;
    }
    
    &:hover {
      border-color: #c0c4cc;
    }
    
    .kb-category-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      
      .category-title {
        font-weight: 500;
        margin-right: 8px;
      }
      
      .category-desc {
        font-size: 12px;
        color: #909399;
      }
    }
    
    .kb-list-selector {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px dashed #e4e7ed;
    }
    
    .kb-empty-tip {
      margin-top: 8px;
      font-size: 12px;
      color: #909399;
      text-align: center;
      padding: 8px;
      background: #f5f7fa;
      border-radius: 4px;
    }
  }
}
</style>
