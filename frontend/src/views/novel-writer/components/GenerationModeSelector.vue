<!--
  多Agent协作文学作品生成系统 - 生成模式选择器
  
  模块: writing-engine
  文件: GenerationModeSelector.vue
  功能: 提供生成模式选择界面，支持智能模式、整章模式和场景拆解模式
  
  创建时间: 2026-04-01
  版本: 1.0.0
-->
<template>
  <div class="generation-mode-selector">
    <div class="selector-header">
      <span class="header-title">
        <el-icon><Operation /></el-icon>
        生成模式
      </span>
      <el-tooltip content="选择内容生成的工作方式" placement="top">
        <el-icon class="help-icon"><QuestionFilled /></el-icon>
      </el-tooltip>
    </div>
    
    <div class="mode-cards">
      <div
        v-for="mode in modes"
        :key="mode.value"
        class="mode-card"
        :class="{ 
          'is-selected': selectedMode === mode.value,
          'is-recommended': mode.recommended
        }"
        @click="selectMode(mode.value)"
      >
        <div class="card-badge" v-if="mode.recommended">
          <el-tag type="success" size="small" effect="dark">推荐</el-tag>
        </div>
        
        <div class="card-icon">
          <el-icon :size="32">
            <component :is="mode.icon" />
          </el-icon>
        </div>
        
        <div class="card-content">
          <h4 class="card-title">{{ mode.label }}</h4>
          <p class="card-description">{{ mode.description }}</p>
        </div>
        
        <div class="card-features">
          <div 
            v-for="(feature, idx) in mode.features" 
            :key="idx"
            class="feature-item"
          >
            <el-icon class="feature-icon"><Check /></el-icon>
            <span>{{ feature }}</span>
          </div>
        </div>
        
        <div class="card-footer">
          <el-tag 
            :type="mode.tagType" 
            size="small"
            effect="plain"
          >
            {{ mode.tagText }}
          </el-tag>
        </div>
        
        <div class="card-check" v-if="selectedMode === mode.value">
          <el-icon><CircleCheckFilled /></el-icon>
        </div>
      </div>
    </div>
    
    <div class="mode-detail" v-if="currentModeDetail">
      <el-collapse>
        <el-collapse-item>
          <template #title>
            <span class="detail-title">
              <el-icon><InfoFilled /></el-icon>
              {{ currentModeDetail.label }}详细说明
            </span>
          </template>
          <div class="detail-content">
            <div class="detail-section">
              <h5>适用场景</h5>
              <p>{{ currentModeDetail.scenarios }}</p>
            </div>
            <div class="detail-section">
              <h5>工作流程</h5>
              <ol class="workflow-list">
                <li v-for="(step, idx) in currentModeDetail.workflow" :key="idx">
                  {{ step }}
                </li>
              </ol>
            </div>
            <div class="detail-section" v-if="currentModeDetail.tips">
              <h5>使用提示</h5>
              <el-alert
                type="info"
                :closable="false"
                show-icon
              >
                {{ currentModeDetail.tips }}
              </el-alert>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  Operation,
  QuestionFilled,
  Check,
  CircleCheckFilled,
  InfoFilled,
  Cpu,
  Document,
  Grid
} from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: 'auto'
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const STORAGE_KEY = 'writing_generation_mode'

const modes = [
  {
    value: 'auto',
    label: '智能模式',
    icon: 'Cpu',
    description: '自动检测详细大纲，智能选择最优生成策略',
    features: [
      '自动检测单元详细大纲',
      '无大纲时自动降级',
      '最优生成策略选择'
    ],
    tagType: 'success',
    tagText: '智能适配',
    recommended: true,
    scenarios: '适合大多数创作场景，系统会根据项目数据自动选择最佳生成方式。如果您不确定选择哪种模式，推荐使用智能模式。',
    workflow: [
      '检测当前单元是否存在详细大纲',
      '存在详细大纲：使用整章生成模式，充分利用大纲信息',
      '不存在详细大纲：自动降级为场景拆解模式，使用全局大纲+单元概述',
      '实时显示模式决策日志，便于了解系统行为'
    ],
    tips: '智能模式会在生成开始时自动检测并选择模式，无需手动干预。'
  },
  {
    value: 'direct',
    label: '整章生成',
    icon: 'Document',
    description: '直接生成完整章节内容，适合有详细大纲的项目',
    features: [
      '一次性生成完整章节',
      '充分利用详细大纲',
      '生成效率高'
    ],
    tagType: 'primary',
    tagText: '高效生成',
    recommended: false,
    scenarios: '适合已经准备好详细章节大纲的项目。整章生成可以更好地保持内容的连贯性和一致性，生成效率较高。',
    workflow: [
      '读取章节详细大纲（场景划分、人物状态变化等）',
      '调用Writer Agent直接生成完整章节内容',
      'Logic Editor进行逻辑检查和修正',
      'Style Editor进行风格润色',
      '输出最终章节内容'
    ],
    tips: '使用整章生成模式前，请确保已生成或上传了单元详细大纲。'
  },
  {
    value: 'scene_split',
    label: '场景拆解',
    icon: 'Grid',
    description: '将章节拆分为多个场景分别生成，适合复杂情节',
    features: [
      '精细化场景控制',
      '灵活处理复杂情节',
      '便于分段修改'
    ],
    tagType: 'warning',
    tagText: '精细控制',
    recommended: false,
    scenarios: '适合情节复杂、场景较多的章节，或者没有详细大纲的项目。场景拆解模式会先分析章节结构，然后逐场景生成内容。',
    workflow: [
      'Structural Agent分析章节结构',
      '将章节拆分为多个场景',
      'Writer Agent逐场景生成内容',
      'Logic Editor检查场景间逻辑一致性',
      'Style Editor统一润色风格',
      'Assembler Agent合并场景内容'
    ],
    tips: '场景拆解模式会使用全局大纲和单元概述作为参考，无需详细大纲即可工作。'
  }
]

const selectedMode = ref(props.modelValue)

const currentModeDetail = computed(() => {
  return modes.find(m => m.value === selectedMode.value)
})

function selectMode(mode) {
  selectedMode.value = mode
  emit('update:modelValue', mode)
  emit('change', mode)
  saveToStorage(mode)
}

function saveToStorage(mode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch (e) {
    console.warn('保存生成模式到本地存储失败:', e)
  }
}

function loadFromStorage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && modes.find(m => m.value === saved)) {
      return saved
    }
  } catch (e) {
    console.warn('从本地存储加载生成模式失败:', e)
  }
  return 'auto'
}

watch(() => props.modelValue, (newVal) => {
  if (newVal !== selectedMode.value) {
    selectedMode.value = newVal
  }
})

onMounted(() => {
  const savedMode = loadFromStorage()
  if (savedMode !== selectedMode.value) {
    selectedMode.value = savedMode
    emit('update:modelValue', savedMode)
  }
})
</script>

<style lang="scss" scoped>
.generation-mode-selector {
  margin-bottom: 16px;
  
  .selector-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    
    .header-title {
      font-size: 14px;
      font-weight: 500;
      color: #303133;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    
    .help-icon {
      color: #909399;
      cursor: help;
      font-size: 14px;
    }
  }
  
  .mode-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    
    @media (max-width: 1200px) {
      grid-template-columns: repeat(2, 1fr);
    }
    
    @media (max-width: 768px) {
      grid-template-columns: 1fr;
    }
    
    .mode-card {
      position: relative;
      border: 2px solid #e4e7ed;
      border-radius: 8px;
      padding: 16px;
      cursor: pointer;
      transition: all 0.3s ease;
      background: #fff;
      
      &:hover {
        border-color: #409eff;
        box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
        transform: translateY(-2px);
      }
      
      &.is-selected {
        border-color: #409eff;
        background: linear-gradient(135deg, #f0f7ff 0%, #fff 100%);
        box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
        
        .card-icon {
          color: #409eff;
        }
      }
      
      &.is-recommended {
        border-color: #67c23a;
        
        &:hover {
          border-color: #67c23a;
          box-shadow: 0 2px 12px rgba(103, 194, 58, 0.15);
        }
        
        &.is-selected {
          border-color: #67c23a;
          background: linear-gradient(135deg, #f0f9eb 0%, #fff 100%);
          box-shadow: 0 4px 16px rgba(103, 194, 58, 0.2);
          
          .card-icon {
            color: #67c23a;
          }
        }
      }
      
      .card-badge {
        position: absolute;
        top: -8px;
        right: 8px;
      }
      
      .card-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 56px;
        height: 56px;
        border-radius: 12px;
        background: #f5f7fa;
        margin-bottom: 12px;
        color: #606266;
        transition: all 0.3s ease;
      }
      
      .card-content {
        margin-bottom: 12px;
        
        .card-title {
          font-size: 15px;
          font-weight: 600;
          color: #303133;
          margin: 0 0 6px 0;
        }
        
        .card-description {
          font-size: 12px;
          color: #909399;
          margin: 0;
          line-height: 1.5;
        }
      }
      
      .card-features {
        margin-bottom: 12px;
        
        .feature-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #606266;
          margin-bottom: 4px;
          
          .feature-icon {
            color: #67c23a;
            font-size: 12px;
          }
        }
      }
      
      .card-footer {
        display: flex;
        justify-content: flex-start;
      }
      
      .card-check {
        position: absolute;
        top: 12px;
        right: 12px;
        color: #409eff;
        font-size: 20px;
        
        .is-recommended & {
          color: #67c23a;
        }
      }
    }
  }
  
  .mode-detail {
    margin-top: 12px;
    
    .detail-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: #606266;
    }
    
    .detail-content {
      .detail-section {
        margin-bottom: 16px;
        
        &:last-child {
          margin-bottom: 0;
        }
        
        h5 {
          font-size: 13px;
          font-weight: 500;
          color: #303133;
          margin: 0 0 8px 0;
        }
        
        p {
          font-size: 12px;
          color: #606266;
          margin: 0;
          line-height: 1.6;
        }
        
        .workflow-list {
          margin: 0;
          padding-left: 20px;
          
          li {
            font-size: 12px;
            color: #606266;
            line-height: 1.8;
          }
        }
      }
    }
  }
}
</style>
