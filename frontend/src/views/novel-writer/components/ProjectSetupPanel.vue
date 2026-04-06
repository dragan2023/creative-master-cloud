<!--
  项目准备面板组件
  
  功能：
  1. 准备步骤状态指示
  2. 大纲上传入口
  3. 单元概述上传入口
  4. 项目状态统计
  5. 快捷操作按钮

  依赖：
  - 父组件需提供 project 数据
  - 通过 emit 与父组件通信

  创建时间: 2026-03-30
  版本: 1.0.0
-->
<template>
  <div class="project-setup-panel">
    <!-- 准备步骤指示器 -->
    <div class="setup-steps">
      <div class="steps-header">
        <el-icon><Setting /></el-icon>
        <span>项目准备</span>
      </div>
      <el-steps :active="activeStep" direction="vertical" :space="32" simple>
        <el-step title="上传大纲" :status="outlineStatus">
          <template #icon>
            <el-icon :class="{ 'step-done': hasOutline }">
              <Check v-if="hasOutline" />
              <Document v-else />
            </el-icon>
          </template>
        </el-step>
        <el-step title="生成目录" :status="directoryStatus">
          <template #icon>
            <el-icon :class="{ 'step-done': hasDirectory }">
              <Check v-if="hasDirectory" />
              <List v-else />
            </el-icon>
          </template>
        </el-step>
        <el-step title="单元概述" :status="unitSummariesStatus">
          <template #icon>
            <el-icon :class="{ 'step-done': hasUnitSummaries }">
              <Check v-if="hasUnitSummaries" />
              <Reading v-else />
            </el-icon>
          </template>
        </el-step>
        <el-step title="开始生成" :status="readyStatus">
          <template #icon>
            <el-icon :class="{ 'step-done': canStartGenerate }">
              <Check v-if="canStartGenerate" />
              <VideoPlay v-else />
            </el-icon>
          </template>
        </el-step>
      </el-steps>
    </div>

    <!-- 操作按钮组 -->
    <div class="setup-actions">
      <el-button 
        :type="hasOutline ? 'default' : 'primary'" 
        size="small"
        class="action-btn"
        @click="$emit('upload-outline')"
      >
        <el-icon><Upload /></el-icon>
        {{ hasOutline ? '更换大纲' : '上传大纲' }}
      </el-button>
      
      <el-button 
        :type="hasUnitSummaries ? 'default' : 'primary'" 
        size="small"
        plain
        class="action-btn"
        @click="$emit('upload-unit-summaries')"
        :disabled="!hasOutline"
      >
        <el-icon><Upload /></el-icon>
        {{ hasUnitSummaries ? '更换单元概述' : '上传单元概述' }}
      </el-button>
      
      <el-button 
        v-if="hasOutline && !hasDirectory"
        type="warning"
        size="small"
        class="action-btn"
        @click="$emit('generate-directory')"
        :loading="generatingDirectory"
      >
        <el-icon><List /></el-icon>
        生成目录
      </el-button>
    </div>

    <!-- 项目状态统计 -->
    <div class="project-stats" v-if="hasOutline">
      <el-divider content-position="left">
        <el-icon><DataAnalysis /></el-icon>
        项目统计
      </el-divider>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-value">{{ outlineWordCount }}</span>
          <span class="stat-label">大纲字数</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ totalUnits }}</span>
          <span class="stat-label">{{ unitLabel }}数量</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ unitSummariesCount }}</span>
          <span class="stat-label">单元概述</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ completedUnits }}</span>
          <span class="stat-label">已生成</span>
        </div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="quick-actions" v-if="hasOutline">
      <el-divider content-position="left">
        <el-icon><Operation /></el-icon>
        快捷操作
      </el-divider>
      <div class="action-links">
        <el-button 
          type="primary" 
          plain 
          size="small"
          @click="$emit('show-knowledge-graph')"
        >
          <el-icon><Connection /></el-icon>
          查看知识图谱
        </el-button>
        <el-button 
          type="success" 
          plain 
          size="small"
          @click="$emit('show-consistency-report')"
        >
          <el-icon><DataAnalysis /></el-icon>
          一致性检查报告
        </el-button>
        <el-button text @click="$emit('build-knowledge-base')">
          <el-icon><DataAnalysis /></el-icon>
          构建知识库
        </el-button>
        <el-button text @click="$emit('show-settings')">
          <el-icon><Setting /></el-icon>
          项目设置
        </el-button>
      </div>
    </div>

    <!-- 架构优化：已移除章节大纲生成功能 -->
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { 
  Setting, Check, Document, List, Reading, VideoPlay, Upload,
  DataAnalysis, Operation, Connection
  // 架构优化：移除 View 图标
} from '@element-plus/icons-vue'

// ==================== Props ====================
const props = defineProps({
  // 项目数据
  project: {
    type: Object,
    default: () => ({})
  },
  // 章节列表
  chapters: {
    type: Array,
    default: () => []
  },
  // 单位标签
  unitLabel: {
    type: String,
    default: '章'
  },
  // 是否正在生成目录
  generatingDirectory: {
    type: Boolean,
    default: false
  }
  // 架构优化：移除 chapterOutlines prop
})

// ==================== Emits ====================
defineEmits([
  'upload-outline',
  'upload-unit-summaries',
  'generate-directory',
  'show-knowledge-graph',
  'show-consistency-report',
  'build-knowledge-base',
  'show-settings'
  // 架构优化：移除 'generate-chapter-outlines', 'view-chapter-outlines'
])

// ==================== Computed ====================

// 是否有大纲
const hasOutline = computed(() => !!props.project?.outline_content)

// 是否有目录
const hasDirectory = computed(() => props.chapters?.length > 0)

// 是否有单元概述
const hasUnitSummaries = computed(() => {
  const summaries = props.project?.unit_summaries
  return summaries && Object.keys(summaries).length > 0
})

// 是否有知识库
const hasKnowledgeBase = computed(() => {
  return props.project?.knowledge_base_config?.graphrag_enabled !== false
})

// 是否可以开始生成
const canStartGenerate = computed(() => hasOutline.value && hasDirectory.value)

// 是否为小说类型
const isNovel = computed(() => {
  const contentType = props.project?.content_type
  return contentType === 'novel' || !contentType
})

// 当前步骤
const activeStep = computed(() => {
  if (!hasOutline.value) return 0
  if (!hasDirectory.value) return 1
  if (!hasUnitSummaries.value) return 2
  return 3
})

// 大纲状态
const outlineStatus = computed(() => {
  if (hasOutline.value) return 'success'
  return 'wait'
})

// 目录状态
const directoryStatus = computed(() => {
  if (hasDirectory.value) return 'success'
  if (hasOutline.value) return 'process'
  return 'wait'
})

// 单元概述状态
const unitSummariesStatus = computed(() => {
  if (hasUnitSummaries.value) return 'success'
  if (hasDirectory.value) return 'process'
  return 'wait'
})

// 就绪状态
const readyStatus = computed(() => {
  if (canStartGenerate.value) return 'success'
  return 'wait'
})

// 大纲字数（优先使用后端计算的精确值，回退到前端计算）
const outlineWordCount = computed(() => {
  if (props.project?.outline_word_count !== undefined && props.project?.outline_word_count !== null) {
    return props.project.outline_word_count
  }
  const content = props.project?.outline_content || ''
  return content.replace(/\s/g, '').length
})

// 总单元数
const totalUnits = computed(() => props.project?.total_chapters || 0)

// 单元概述数量
const unitSummariesCount = computed(() => {
  const summaries = props.project?.unit_summaries
  return summaries ? Object.keys(summaries).length : 0
})

// 已完成单元数
const completedUnits = computed(() => props.project?.completed_chapters || 0)

// 架构优化：移除 chapterOutlinesCount 和 chapterOutlinesPercentage 计算属性
</script>

<style lang="scss" scoped>
.project-setup-panel {
  padding: 16px;
  background: white;
  border-radius: 8px;
}

.setup-steps {
  margin-bottom: 20px;
  padding: 12px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: 8px;
  
  .steps-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 14px;
    font-weight: 600;
    color: #303133;
  }
  
  :deep(.el-steps) {
    .el-step__icon {
      width: 32px;
      height: 32px;
      background: white;
      border-radius: 50%;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      transition: all 0.3s ease;
      
      .el-icon {
        font-size: 16px;
        
        &.step-done {
          color: #67c23a;
        }
      }
    }
    
    .el-step.is-success .el-step__icon {
      background: #f0f9eb;
      border-color: #67c23a;
    }
    
    .el-step.is-process .el-step__icon {
      background: #ecf5ff;
      border-color: #409eff;
    }
    
    .el-step__title {
      font-size: 13px;
      font-weight: 500;
    }
    
    .el-step__line {
      background: #e4e7ed;
    }
    
    .el-step.is-success .el-step__line {
      background: #67c23a;
    }
  }
}

.setup-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
  
  .action-btn {
    justify-content: flex-start;
    width: 100%;
    height: 36px;
    padding: 0 16px;
    font-size: 13px;
    
    .el-icon {
      margin-right: 8px;
    }
  }
}

.project-stats {
  margin-top: 16px;
  
  :deep(.el-divider__text) {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: #909399;
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    margin-top: 12px;
  }
  
  .stat-item {
    text-align: center;
    padding: 8px;
    background: #f5f7fa;
    border-radius: 6px;
    
    .stat-value {
      display: block;
      font-size: 18px;
      font-weight: 600;
      color: #409eff;
    }
    
    .stat-label {
      display: block;
      font-size: 11px;
      color: #909399;
      margin-top: 2px;
    }
  }
}

.quick-actions {
  margin-top: 16px;
  
  :deep(.el-divider__text) {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: #909399;
  }
  
  .action-links {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 8px;
    
    .el-button {
      justify-content: flex-start;
      padding: 8px 12px;
      font-size: 13px;
      
      .el-icon {
        margin-right: 6px;
      }
    }
  }
}

/* 架构优化：移除 .chapter-outlines-status 样式 */
</style>
