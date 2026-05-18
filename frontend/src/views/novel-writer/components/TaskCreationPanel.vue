<!--
  TaskCreationPanel - 任务创建面板（展示型组件）

  从 WritingWorkbench.vue 提取，负责任务创建区域的 UI 展示。
  所有业务逻辑由父组件通过 props 注入，用户操作通过 emits 上抛。

  @component TaskCreationPanel
-->
<template>
  <div class="task-creation">
      <!-- 右侧主区域 -->
      <div class="right-main-area">
        <!-- 单元概述缺失提示（所有类型通用） -->
        <el-alert
          v-if="!hasUnitSummaries"
          type="warning"
          :closable="false"
          show-icon
          class="unit-summaries-alert"
        >
          <template #title>
            <span>缺少{{ unitLabel }}概述数据</span>
          </template>
          <div class="alert-content">
            <p>请先上传全局大纲，再上传{{ unitLabel }}概述（支持 .txt/.md/.docx 文件或直接粘贴内容）。</p>
            <el-button
              type="primary"
              size="small"
              style="margin-top: 8px"
              @click="$emit('upload-unit-summaries')"
            >
              <el-icon><Upload /></el-icon>
              上传{{ unitLabel }}概述
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
                  :loading="isLoading"
                >
                  <el-icon><VideoPlay /></el-icon>
                  开始生成正文
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  plain
                  @click="$emit('open-agent-config')"
                >
                  <el-icon><Setting /></el-icon>
                  Agent配置
                </el-button>
              </div>
            </div>
          </template>

          <!-- 知识库推荐提示 -->
          <el-alert
            v-if="!kbStatus || kbStatus.status !== 'ready'"
            type="info"
            :closable="true"
            show-icon
            style="margin-bottom: 12px"
          >
            <template #title>
              推荐构建知识库以提升生成质量
            </template>
            <template #default>
              知识库基于已上传的大纲自动构建，包含人物设定、世界观等，可增强正文生成的一致性和质量。
              请在左侧"知识库"面板中点击"构建知识库"按钮。
            </template>
          </el-alert>

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

          <!-- 基本参数 -->
          <el-form :model="taskForm" label-width="80px" class="task-form">
            <el-row :gutter="20">
              <!-- 字数限制：仅小说类型显示 -->
              <el-col :span="12" v-if="isNovelType">
                <el-form-item label="每章字数">
                  <el-input-number
                    v-model="taskForm.words_per_chapter"
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
                <el-form-item :label="durationLabel">
                  <el-text type="info" size="small">
                    {{ durationHint }}
                  </el-text>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="并发数">
                  <el-input-number
                    v-model="taskForm.concurrency"
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

          <!-- 剧集专属参数 -->
          <el-form
            v-if="actualContentType === 'series_script'"
            :model="taskForm"
            label-width="80px"
            class="task-form"
            style="margin-top: 12px"
          >
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="剧集类型">
                  <el-select v-model="taskForm.series_type" style="width: 150px">
                    <el-option label="电视剧" value="电视剧" />
                    <el-option label="网络剧" value="网络剧" />
                    <el-option label="短剧" value="短剧" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="每集时长(分钟)">
                  <el-input-number
                    v-model="taskForm.episode_duration_min"
                    :min="1"
                    :max="120"
                    size="small"
                    style="width: 80px"
                    controls-position="right"
                  />
                  -
                  <el-input-number
                    v-model="taskForm.episode_duration_max"
                    :min="1"
                    :max="120"
                    size="small"
                    style="width: 80px"
                    controls-position="right"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="生成模式">
                  <el-radio-group v-model="taskForm.script_mode">
                    <el-radio-button value="real">现实模式</el-radio-button>
                    <el-radio-button value="virtual">虚拟模式（AI生成）</el-radio-button>
                  </el-radio-group>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>

          <!-- 电影专属参数 -->
          <el-form
            v-if="actualContentType === 'movie_script'"
            :model="taskForm"
            label-width="80px"
            class="task-form"
            style="margin-top: 12px"
          >
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="电影类型">
                  <el-select v-model="taskForm.movie_type" style="width: 150px">
                    <el-option label="电影" value="电影" />
                    <el-option label="网络电影" value="网络电影" />
                    <el-option label="微电影" value="微电影" />
                    <el-option label="动画电影" value="动画电影" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="每场时长(分钟)">
                  <el-input-number
                    v-model="taskForm.scene_duration_min"
                    :min="1"
                    :max="60"
                    size="small"
                    style="width: 80px"
                    controls-position="right"
                  />
                  -
                  <el-input-number
                    v-model="taskForm.scene_duration_max"
                    :min="1"
                    :max="60"
                    size="small"
                    style="width: 80px"
                    controls-position="right"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="生成模式">
                  <el-radio-group v-model="taskForm.script_mode">
                    <el-radio-button value="real">现实模式</el-radio-button>
                    <el-radio-button value="virtual">虚拟模式（AI生成）</el-radio-button>
                  </el-radio-group>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
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

          <!-- 参数配置区 -->
          <div class="unit-params-bar">
            <div class="param-item-inline">
              <span class="param-label">起始单元</span>
              <div class="param-input-wrapper">
                <el-input-number
                  v-model="taskForm.start_from"
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
                v-model="taskForm.unit_count"
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
              :class="{ 'is-selected': unit.unit_index === taskForm.start_from }"
              @click="taskForm.start_from = unit.unit_index"
            >
              <span class="unit-index">#{{ unit.unit_index }}</span>
              <span class="unit-name" :title="unit.unit_title">
                {{ unit.unit_title || `${unit.unit_index}${unitLabel}` }}
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
  </div>
</template>

<script setup>
import { EditPen, List, Setting, Upload, VideoPlay } from '@element-plus/icons-vue'

defineProps({
  projectData: { type: Object, default: () => ({}) },
  displayUnits: { type: Array, default: () => [] },
  unitLabel: { type: String, default: '章' },
  actualContentType: { type: String, default: 'novel' },
  isNovelType: { type: Boolean, default: true },
  durationLabel: { type: String, default: '时长' },
  durationHint: { type: String, default: '' },
  taskForm: { type: Object, required: true },
  projectTotalUnits: { type: Number, default: 0 },
  currentUnitName: { type: String, default: '' },
  kbStatus: { type: Object, default: () => ({ status: 'pending' }) },
  buildingKb: { type: Boolean, default: false },
  hasOutline: { type: Boolean, default: false },
  hasUnitSummaries: { type: Boolean, default: false },
  generatingDirectory: { type: Boolean, default: false },
  isLoading: { type: Boolean, default: false },
})

defineEmits([
  'upload-outline',
  'upload-unit-summaries',
  'generate-directory',
  'show-knowledge-graph',
  'show-consistency-report',
  'show-settings',
  'build-kb',
  'rebuild-global-kb',
  'delete-kb',
  'refresh-kb',
  'create-task',
  'open-agent-config',
])
</script>

<style lang="scss" scoped>
.task-creation {
  .workbench-layout {
    display: flex;
    gap: 20px;
    min-height: 600px;
  }

  .left-sidebar {
    width: 350px;
    flex-shrink: 0;
    min-width: 300px;
    position: sticky;
    top: 20px;
    max-height: calc(100vh - 40px);
    overflow-y: auto;
  }

  .right-main-area {
    flex: 1;
    min-width: 0;
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

.unit-summaries-alert {
  margin-bottom: 16px;

  .alert-content p {
    margin: 0;
    line-height: 1.6;
  }
}
</style>
