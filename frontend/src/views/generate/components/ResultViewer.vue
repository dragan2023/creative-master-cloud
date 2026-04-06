<template>
  <div class="result-container" v-if="showResult">
    <!-- 两阶段大纲生成：阶段指示器 -->
    <div v-if="useTwoStageMode" class="outline-stages">
      <el-steps :active="outlineStage" align-center finish-status="success">
        <el-step title="全局大纲" description="世界观、人物、结构" />
        <el-step title="审核修改" description="确认全局大纲" />
        <el-step title="单元概述" description="章节/分集概要" />
        <el-step title="完成" description="可下载或导入" />
      </el-steps>
      <div class="stage-actions">
        <!-- 阶段1：全局大纲生成中，显示中断按钮 -->
        <el-button
          v-if="outlineStage === 1 && globalOutlineGenerating"
          type="danger"
          @click="$emit('stop')"
        >
          <el-icon><CircleClose /></el-icon>
          中断生成
        </el-button>
        <!-- 阶段2：全局大纲完成，显示继续按钮 -->
        <el-button
          v-if="outlineStage === 2"
          type="primary"
          @click="$emit('generate-unit-summaries')"
          :loading="unitSummariesGenerating"
        >
          确认全局大纲，继续生成单元概述
        </el-button>
        <!-- 阶段3：单元概述生成中，显示中断按钮 -->
        <el-button
          v-if="outlineStage === 3 && unitSummariesGenerating"
          type="danger"
          @click="$emit('cancel-unit-summaries')"
        >
          <el-icon><VideoPause /></el-icon>
          中断生成
        </el-button>
        <!-- 阶段4：全部完成，显示下载按钮 -->
        <el-button
          v-if="outlineStage === 4"
          type="success"
          @click="$emit('download-outline')"
        >
          <el-icon><Download /></el-icon>
          下载完整大纲
        </el-button>
        <el-button
          v-if="outlineStage === 4"
          @click="$emit('open-start-unit-dialog')"
        >
          <el-icon><Edit /></el-icon>
          从指定单元重新生成
        </el-button>
        <el-button
          v-if="outlineStage === 4"
          @click="$emit('reset-two-stage')"
        >
          重新开始
        </el-button>
      </div>
      
      <!-- 逻辑检测状态 -->
      <div v-if="logicChecking || logicCheckResult" class="logic-check-status">
        <div v-if="logicChecking" class="logic-checking">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在进行逻辑检测...</span>
        </div>
        <div v-else-if="logicCheckResult" class="logic-check-result">
          <div v-if="logicCheckResult.has_issues" class="has-issues">
            <el-icon><WarningFilled /></el-icon>
            <span>检测到 {{ logicCheckResult.issues?.length || 0 }} 个逻辑问题</span>
            <el-button size="small" text @click="showLogicIssuesDialog = true">
              查看详情
            </el-button>
          </div>
          <div v-else class="no-issues">
            <el-icon><CircleCheckFilled /></el-icon>
            <span>逻辑检测通过，未发现问题</span>
          </div>
        </div>
      </div>
    </div>

    <div class="result-header">
      <h3>{{ useTwoStageMode ? (outlineStage <= 2 ? '全局大纲' : '完整大纲') : '生成结果' }}</h3>
      <div class="result-meta">
        <el-tag v-if="generationDuration" type="info" size="small" class="duration-tag">
          <el-icon><Timer /></el-icon>
          耗时: {{ formatDuration(generationDuration) }}
        </el-tag>
        <div class="result-actions">
          <el-button text @click="$emit('copy')">
            <el-icon><CopyDocument /></el-icon>
            复制
          </el-button>
          <el-button text @click="$emit('download')">
            <el-icon><Download /></el-icon>
            下载
          </el-button>
          <el-button v-if="!useTwoStageMode" text @click="$emit('regenerate')">
            <el-icon><Refresh /></el-icon>
            重新生成
          </el-button>
          <el-button v-if="useTwoStageMode && outlineStage > 0" text @click="$emit('reset-two-stage')">
            <el-icon><Refresh /></el-icon>
            重新开始
          </el-button>
        </div>
      </div>
    </div>
    
    <!-- 两阶段大纲生成：全局大纲编辑区（阶段2显示） -->
    <div v-if="useTwoStageMode && outlineStage === 2" class="global-outline-edit">
      <div class="edit-header">
        <span class="edit-tip"><el-icon><Edit /></el-icon> 您可以直接编辑全局大纲内容，修改后将用于生成单元概述</span>
        <div class="edit-actions">
          <el-button v-if="!editingGlobalOutline" type="primary" size="small" @click="$emit('start-edit-global')">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <template v-else>
            <el-button type="success" size="small" @click="$emit('save-global-edit')">
              <el-icon><Check /></el-icon> 保存修改
            </el-button>
            <el-button size="small" @click="$emit('cancel-global-edit')">
              <el-icon><Close /></el-icon> 取消
            </el-button>
          </template>
        </div>
      </div>
      <div class="edit-content">
        <el-input
          v-if="editingGlobalOutline"
          :model-value="editingGlobalOutlineContent"
          @update:model-value="$emit('update:editingGlobalOutlineContent', $event)"
          type="textarea"
          :rows="20"
          placeholder="请输入全局大纲内容..."
        />
        <div v-else class="preview-content markdown-content" v-html="renderedGlobalOutline"></div>
      </div>
    </div>
    
    <!-- 两阶段大纲生成：单元概述列表（阶段4显示） -->
    <div v-if="useTwoStageMode && outlineStage === 4 && Object.keys(unitSummaries).length > 0" class="unit-summaries-list">
      <el-collapse>
        <el-collapse-item
          v-for="(unit, num) in unitSummaries"
          :key="num"
          :name="num"
        >
          <template #title>
            <div class="unit-title-wrapper">
              <span>第{{ unit.unit_number }}{{ contentType === 'novel' ? '章' : '集' }}：{{ unit.title }}</span>
              <el-tag v-if="unit.logic_fixed" type="success" size="small" class="fixed-tag">
                <el-icon><Check /></el-icon> 已修正
              </el-tag>
            </div>
          </template>
          <div class="unit-summary-content">
            <p v-if="editingUnitNumber !== num" :class="{ 'logic-fixed-content': unit.logic_fixed }">
              {{ unit.summary }}
            </p>
            <el-input
              v-else
              :model-value="editingUnitContent"
              @update:model-value="$emit('update:editingUnitContent', $event)"
              type="textarea"
              :rows="4"
            />
            <div class="unit-actions">
              <el-button
                v-if="unit.logic_fixed && editingUnitNumber !== num"
                size="small"
                type="primary"
                text
                @click.stop="$emit('open-revision-detail', parseInt(num))"
              >
                <el-icon><View /></el-icon> 查看修正
              </el-button>
              <el-button
                v-if="editingUnitNumber !== num"
                size="small"
                text
                @click="$emit('edit-unit', parseInt(num))"
              >
                编辑
              </el-button>
              <template v-else>
                <el-button size="small" type="primary" @click="$emit('save-unit')">保存</el-button>
                <el-button size="small" @click="$emit('cancel-edit-unit')">取消</el-button>
              </template>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
    
    <!-- 默认渲染内容（阶段2时不显示，因为已有编辑区） -->
    <div v-if="!(useTwoStageMode && outlineStage === 2)" class="result-content markdown-content" v-html="renderedContent"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  showResult: Boolean,
  useTwoStageMode: Boolean,
  outlineStage: { type: Number, default: 0 },
  globalOutlineGenerating: Boolean,
  unitSummariesGenerating: Boolean,
  logicChecking: Boolean,
  logicCheckResult: Object,
  generationDuration: Number,
  editingGlobalOutline: Boolean,
  editingGlobalOutlineContent: String,
  editingUnitNumber: [Number, String],
  editingUnitContent: String,
  unitSummaries: { type: Object, default: () => ({}) },
  globalOutlineContent: String,
  generatedContent: String,
  contentType: String
})

defineEmits([
  'stop',
  'generate-unit-summaries',
  'cancel-unit-summaries',
  'download-outline',
  'open-start-unit-dialog',
  'reset-two-stage',
  'copy',
  'download',
  'regenerate',
  'start-edit-global',
  'save-global-edit',
  'cancel-global-edit',
  'update:editingGlobalOutlineContent',
  'open-revision-detail',
  'edit-unit',
  'save-unit',
  'cancel-edit-unit',
  'update:editingUnitContent'
])

const formatDuration = (ms) => {
  if (!ms || ms < 0) return ''
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes > 0) {
    return `${minutes}分${remainingSeconds}秒`
  } else {
    return `${remainingSeconds}秒`
  }
}

const renderedGlobalOutline = computed(() => {
  if (!props.globalOutlineContent) return ''
  return DOMPurify.sanitize(marked(props.globalOutlineContent))
})

const renderedContent = computed(() => {
  if (!props.generatedContent) return ''
  return DOMPurify.sanitize(marked(props.generatedContent))
})
</script>

<style lang="scss" scoped>
.result-container {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(64, 158, 255, 0.08);
  margin-bottom: 24px;
  
  .result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 2px solid #f0f2f5;
    
    h3 {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 8px;
      
      &::before {
        content: '✨';
        font-size: 20px;
      }
    }
    
    .result-meta {
      display: flex;
      align-items: center;
      gap: 16px;
      
      .duration-tag {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      
      .result-actions {
        display: flex;
        gap: 8px;
        
        .el-button {
          font-weight: 500;
        }
      }
    }
  }
  
  .result-content {
    background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
    border-radius: 8px;
    padding: 24px;
    border: 1px solid #e4e7ed;
    min-height: 200px;
  }
}

.outline-stages {
  margin-bottom: 24px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  
  .el-steps {
    margin-bottom: 20px;
  }
  
  .stage-actions {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-top: 16px;
  }
}

.global-outline-edit {
  margin-bottom: 24px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  
  .edit-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: #f5f7fa;
    border-bottom: 1px solid #e4e7ed;
    
    .edit-tip {
      font-size: 14px;
      color: #606266;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    
    .edit-actions {
      display: flex;
      gap: 8px;
    }
  }
  
  .edit-content {
    padding: 16px;
    
    .el-textarea {
      font-family: monospace;
    }
    
    .preview-content {
      max-height: 500px;
      overflow-y: auto;
      padding: 8px;
    }
  }
}

.unit-summaries-list {
  margin-bottom: 24px;
  
  .el-collapse {
    border: 1px solid #e4e7ed;
    border-radius: 8px;
  }
  
  .unit-title-wrapper {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .fixed-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
  }
  
  .unit-summary-content {
    padding: 12px;
    
    p {
      margin: 0 0 12px;
      line-height: 1.6;
      color: #606266;
      
      &.logic-fixed-content {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        padding: 8px 12px;
        border-radius: 6px;
        border-left: 3px solid #28a745;
      }
    }
    
    .unit-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }
  }
}

.logic-check-status {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  
  .logic-checking {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #409eff;
    font-size: 14px;
    
    .el-icon {
      font-size: 16px;
    }
  }
  
  .logic-check-result {
    .has-issues {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #e6a23c;
      font-size: 14px;
      
      .el-icon {
        font-size: 16px;
      }
    }
    
    .no-issues {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #67c23a;
      font-size: 14px;
      
      .el-icon {
        font-size: 16px;
      }
    }
  }
}
</style>
