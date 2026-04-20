<!--
  ContentEditor.vue - 任务创建区域组件
  
  功能：
  - 任务配置面板（生成模式、AI文风消除、基本参数）
  - 单元大纲生成面板
  - 单元列表预览
-->
<template>
  <div class="content-editor">
    <!-- 单元概述缺失提示（仅小说类型显示） -->
    <el-alert
      v-if="showUnitSummariesAlert"
      type="warning"
      :closable="false"
      show-icon
      class="unit-summaries-alert"
    >
      <template #title>
        <span>缺少单元概述数据</span>
      </template>
      <div class="alert-content">
        <p>章节详细大纲功能需要先上传单元概述数据。</p>
        <p style="color: #909399; font-size: 12px; margin-top: 4px">
          单元概述可从"创意生成"板块导出后上传，或直接在下方输入。
        </p>
        <el-button
          type="primary"
          size="small"
          style="margin-top: 8px"
          @click="$emit('upload-unit-summaries')"
        >
          <el-icon><Upload /></el-icon>
          上传单元概述
        </el-button>
      </div>
    </el-alert>

    <!-- 任务配置面板 -->
    <el-card shadow="hover" class="creation-card">
      <template #header>
        <div class="card-header">
          <span class="header-title">
            <el-icon><EditPen /></el-icon>
            正文生成配置
          </span>
          <div class="header-actions">
            <el-button
              type="primary"
              @click="$emit('create-task')"
              :loading="loading"
            >
              <el-icon><VideoPlay /></el-icon>
              开始生成正文
            </el-button>
            <el-button
              size="small"
              type="primary"
              plain
              @click="$emit('show-agent-config')"
            >
              <el-icon><Setting /></el-icon>
              Agent配置
            </el-button>
          </div>
        </div>
      </template>

      <!-- 配置提示 -->
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      >
        <template #title>
          点击 "Agent配置" 按钮可配置模型参数和并发设置
        </template>
      </el-alert>

      <!-- 架构优化：移除生成模式选择器，固定使用direct模式 -->

      <!-- 基本参数 -->
      <el-form :model="taskForm" label-width="80px" class="task-form">
        <el-row :gutter="20">
          <!-- 字数限制：仅小说类型显示 -->
          <el-col :span="12" v-if="isNovelType">
            <el-form-item label="每章字数">
              <el-input-number
                :model-value="taskForm.words_per_chapter"
                @change="updateTaskForm('words_per_chapter', $event)"
                :min="500"
                :max="10000"
                :step="500"
                style="width: 150px"
                controls-position="right"
              />
            </el-form-item>
          </el-col>
          <!-- 时长提示：剧本类型显示 -->
          <el-col :span="12" v-else>
            <el-form-item label="时长控制">
              <el-text type="info" size="small">
                {{ durationHint }}
              </el-text>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="并发数">
              <el-input-number
                :model-value="taskForm.concurrency"
                @change="updateTaskForm('concurrency', $event)"
                :min="1"
                :max="10"
                style="width: 150px"
                controls-position="right"
              />
              <span class="form-hint">写手并发数</span>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 单元大纲生成面板（独立板块） -->
    <el-card
      v-if="canGenerateChapterOutlines"
      shadow="hover"
      class="chapter-outline-card"
    >
      <template #header>
        <div class="card-header">
          <span class="header-title">
            <el-icon><Document /></el-icon>
            单元大纲生成
          </span>
          <el-tag
            v-if="chapterOutlineStats.total > 0"
            :type="chapterOutlineStats.pending === 0 ? 'success' : 'warning'"
            size="small"
          >
            已生成 {{ chapterOutlineStats.generated }}/{{
              chapterOutlineStats.total
            }}
          </el-tag>
        </div>
      </template>

      <!-- 进度展示 -->
      <div
        v-if="chapterOutlineStats.total > 0"
        class="outline-progress-section"
      >
        <el-progress
          :percentage="chapterOutlineStats.progress"
          :stroke-width="10"
          :format="(p) => `${p}%`"
        />
        <div class="progress-detail">
          <span v-if="chapterOutlineStats.pending > 0" class="pending-hint">
            <el-icon><Warning /></el-icon>
            还有 {{ chapterOutlineStats.pending }} 个单元大纲待生成
          </span>
          <span v-else class="complete-hint">
            <el-icon><CircleCheck /></el-icon>
            全部单元大纲已生成完成
          </span>
        </div>
      </div>

      <!-- 生成范围控制 -->
      <el-form :model="outlineForm" label-width="80px" class="outline-form">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="起始单元">
              <el-input-number
                v-model="outlineForm.start_unit"
                :min="1"
                :max="projectTotalUnits || 999"
                style="width: 100%"
                controls-position="right"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="生成数量">
              <el-input-number
                v-model="outlineForm.unit_count"
                :min="1"
                :max="projectTotalUnits || 100"
                style="width: 100%"
                controls-position="right"
                placeholder="全部"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label-width="0">
              <el-checkbox v-model="outlineForm.skip_existing">
                跳过已生成（断点续传）
              </el-checkbox>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <div class="outline-actions">
            <!-- 进度显示 -->
            <div v-if="chapterOutlineProgress" class="outline-progress-info">
              <div class="progress-text">
                <span>{{ chapterOutlineProgress.message }}</span>
                <span v-if="chapterOutlineProgress.current_chapter">
                  (第 {{ chapterOutlineProgress.current_chapter }} 章)
                </span>
              </div>
              <el-progress
                v-if="chapterOutlineProgress.total > 0"
                :percentage="
                  Math.round(
                    ((chapterOutlineProgress.generated?.length || 0) /
                      chapterOutlineProgress.total) *
                      100
                  )
                "
                :stroke-width="8"
                style="margin-top: 8px"
              />
            </div>

            <!-- 操作按钮 -->
            <el-button
              v-if="
                !chapterOutlineProgress ||
                chapterOutlineProgress.status !== 'running'
              "
              type="primary"
              @click="$emit('generate-chapter-outlines')"
              :loading="generatingOutlines"
              :disabled="chapterOutlineStats.pending === 0 && outlineForm.skip_existing"
            >
              <el-icon><Document /></el-icon>
              生成单元大纲
            </el-button>
            <el-button v-else type="danger" @click="$emit('interrupt-chapter-outlines')">
              <el-icon><VideoPause /></el-icon>
              中断生成
            </el-button>
            <el-button
              v-if="
                chapterOutlineStats.pending > 0 &&
                (!chapterOutlineProgress ||
                  chapterOutlineProgress.status !== 'running')
              "
              type="success"
              plain
              @click="$emit('continue-from-breakpoint')"
            >
              <el-icon><Refresh /></el-icon>
              从第 {{ recommendedStartUnit }} 章继续
            </el-button>
            <el-button
              v-if="chapterOutlineStats.generated > 0"
              type="info"
              plain
              @click="$emit('view-outline-list')"
            >
              <el-icon><List /></el-icon>
              查看已生成列表
            </el-button>
          </div>
        </el-form-item>
      </el-form>

      <!-- 快捷提示 -->
      <el-alert
        v-if="!outlineForm.skip_existing && chapterOutlineStats.generated > 0"
        type="warning"
        :closable="false"
        show-icon
        style="margin-top: 12px"
      >
        <template #title>注意</template>
        未勾选"跳过已生成"时，将覆盖指定范围内的已存在大纲
      </el-alert>
    </el-card>

    <!-- 单元列表预览 -->
    <el-card class="units-panel" shadow="hover">
      <template #header>
        <div class="panel-header">
          <span>
            <el-icon><List /></el-icon>
            单元列表（正文生成）
          </span>
          <el-tag type="info" size="small">
            {{ displayUnits.length }} {{ unitLabel }}
          </el-tag>
        </div>
      </template>

      <!-- 参数配置区：起始单元和生成数量（正文生成用） -->
      <div class="unit-params-bar">
        <div class="param-item-inline">
          <span class="param-label">起始单元</span>
          <div class="param-input-wrapper">
            <el-input-number
              :model-value="taskForm.start_from"
              @change="updateTaskForm('start_from', $event)"
              :min="1"
              :max="projectTotalUnits || 999"
              style="width: 90px"
              controls-position="right"
              size="small"
            />
            <span class="unit-name-badge" v-if="currentUnitName">
              {{ currentUnitName }}
            </span>
          </div>
        </div>
        <div class="param-item-inline">
          <span class="param-label">生成数量</span>
          <el-input-number
            :model-value="taskForm.unit_count"
            @change="updateTaskForm('unit_count', $event)"
            :min="1"
            :max="projectTotalUnits || 100"
            placeholder="全部"
            style="width: 100px"
            size="small"
            controls-position="right"
          />
          <span class="param-hint">留空=全部</span>
        </div>
      </div>

      <div class="units-preview-list">
        <div
          v-for="unit in displayUnits"
          :key="unit.unit_index"
          class="unit-preview-item"
          :class="{
            'is-selected': unit.unit_index === taskForm.start_from
          }"
          @click="updateTaskForm('start_from', unit.unit_index)"
        >
          <span class="unit-index">#{{ unit.unit_index }}</span>
          <span class="unit-name" :title="unit.unit_title">
            {{ unit.unit_title || `第${unit.unit_index}${unitLabel}` }}
          </span>
        </div>
        <el-empty
          v-if="displayUnits.length === 0"
          description="暂无单元数据，请先在项目中创建大纲"
          :image-size="60"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  VideoPlay,
  EditPen,
  Document,
  List,
  Setting,
  MagicStick,
  Warning,
  CircleCheck,
  VideoPause,
  Refresh,
  Upload
} from '@element-plus/icons-vue'
// 架构优化：移除 GenerationModeSelector 导入

const props = defineProps({
  // 任务表单
  taskForm: {
    type: Object,
    required: true
  },
  // 单元大纲表单
  outlineForm: {
    type: Object,
    default: () => ({
      start_unit: 1,
      unit_count: null,
      skip_existing: true
    })
  },
  // 显示的单元列表
  displayUnits: {
    type: Array,
    default: () => []
  },
  // 项目总单元数
  projectTotalUnits: {
    type: Number,
    default: 0
  },
  // 单元标签
  unitLabel: {
    type: String,
    default: '章'
  },
  // 是否可以生成章节大纲
  canGenerateChapterOutlines: {
    type: Boolean,
    default: false
  },
  // 章节大纲统计
  chapterOutlineStats: {
    type: Object,
    default: () => ({
      total: 0,
      generated: 0,
      pending: 0,
      progress: 0
    })
  },
  // 章节大纲进度
  chapterOutlineProgress: {
    type: Object,
    default: null
  },
  // 推荐起始单元
  recommendedStartUnit: {
    type: Number,
    default: 1
  },
  // 是否正在生成大纲
  generatingOutlines: {
    type: Boolean,
    default: false
  },
  // 加载状态
  loading: {
    type: Boolean,
    default: false
  },
  // 内容类型
  contentType: {
    type: String,
    default: 'novel'
  },
  // 项目类型
  projectType: {
    type: String,
    default: 'novel'
  },
  // 是否有单元概述
  hasUnitSummaries: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'create-task',
  'show-agent-config',
  // 架构优化：移除 'mode-change'
  'update:taskForm'
  // 架构优化：移除 'generate-chapter-outlines', 'interrupt-chapter-outlines', 'continue-from-breakpoint', 'view-outline-list', 'upload-unit-summaries'
])

// 计算属性
const showUnitSummariesAlert = computed(() => {
  return (
    !props.hasUnitSummaries &&
    (props.contentType === 'novel' ||
      (!props.contentType && props.projectType === 'novel') ||
      (!props.contentType && !props.projectType))
  )
})

// 是否为小说类型（用于字数控制组件的条件渲染）
const isNovelType = computed(() => {
  const type = props.contentType || props.projectType || 'novel'
  return type === 'novel'
})

// 剧本类型的时长提示
const durationHint = computed(() => {
  const type = props.contentType || props.projectType || 'novel'
  if (type === 'series_script') {
    return '剧本按场景时长自动控制，无需手动设置字数'
  }
  if (type === 'movie_script') {
    return '电影剧本按时长分配场景，字数自动计算'
  }
  return ''
})

const currentUnitName = computed(() => {
  const unitIndex = props.taskForm.start_from
  const unit = props.displayUnits.find((u) => u.unit_index === unitIndex)
  return unit?.unit_title || null
})

// 方法
function updateTaskForm(field, value) {
  emit('update:taskForm', {
    ...props.taskForm,
    [field]: value
  })
}
</script>

<style lang="scss" scoped>
.content-editor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.unit-summaries-alert {
  margin-bottom: 16px;

  .alert-content {
    p {
      margin: 0;
      line-height: 1.6;
    }
  }
}

.creation-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;

      .el-icon {
        color: #409eff;
      }
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }
}

.task-form {
  padding: 10px 0;

  .form-hint {
    font-size: 12px;
    color: #909399;
    margin-left: 8px;
  }
}

.chapter-outline-card {
  margin-bottom: 16px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;

      .el-icon {
        color: #409eff;
      }
    }
  }

  .outline-progress-section {
    padding: 16px;
    background: linear-gradient(135deg, #ecf5ff 0%, #f5f7fa 100%);
    border-radius: 8px;
    margin-bottom: 16px;

    .progress-detail {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 12px;
      font-size: 13px;

      .pending-hint {
        display: flex;
        align-items: center;
        gap: 4px;
        color: #e6a23c;
        font-weight: 500;
      }

      .complete-hint {
        display: flex;
        align-items: center;
        gap: 4px;
        color: #67c23a;
        font-weight: 500;
      }
    }
  }

  .outline-form {
    .outline-actions {
      display: flex;
      flex-direction: column;
      gap: 12px;

      .outline-progress-info {
        padding: 12px;
        background: #f5f7fa;
        border-radius: 6px;

        .progress-text {
          font-size: 13px;
          color: #606266;
        }
      }
    }
  }
}

.unit-params-bar {
  display: flex;
  gap: 16px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;

  .param-item-inline {
    display: flex;
    align-items: center;
    gap: 8px;

    .param-label {
      font-size: 13px;
      color: #606266;
      white-space: nowrap;
    }

    .param-input-wrapper {
      display: flex;
      align-items: center;
      gap: 8px;

      .unit-name-badge {
        padding: 2px 8px;
        background: #f0f9eb;
        border-radius: 4px;
        font-size: 12px;
        color: #67c23a;
        white-space: nowrap;
        max-width: 120px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }

    .param-hint {
      font-size: 11px;
      color: #909399;
    }
  }
}

.units-panel {
  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    span {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      font-weight: 500;
    }
  }
}

.units-preview-list {
  max-height: 500px;
  overflow-y: auto;

  .unit-preview-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    margin-bottom: 8px;
    background: #f5f7fa;
    border-radius: 6px;
    transition: all 0.2s;
    cursor: pointer;

    &:hover {
      background: #ecf5ff;
    }

    &.is-selected {
      background: #f0f9eb;
      border-left: 3px solid #67c23a;
    }

    .unit-index {
      font-weight: 600;
      color: #409eff;
      min-width: 40px;
    }

    .unit-name {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 13px;
      color: #303133;
    }
  }
}
</style>
