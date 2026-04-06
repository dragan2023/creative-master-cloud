<!--
  多Agent协作文学作品生成系统 - 写作工作台
  
  模块: writing-engine
  文件: WritingWorkbench.vue
  功能: 多Agent写作任务的核心工作台，整合项目准备、任务创建、进度监控、知识图谱等功能
  
  依赖关系:
      - API: /api/v1/writing-tasks/*, /api/v1/novel-writer/*
      - Store: writingTask
      - 组件: ProjectSetupPanel, KnowledgeGraphDialog
  
  创建时间: 2026-03-28
  最后修改: 2026-03-30
  版本: 2.0.0
  
  [2026-03-28] 多Agent重构: Agent角色名与后端AgentRole对齐，添加中文显示名映射
  [2026-03-30] 功能整合: 合并项目详情页功能，添加大纲上传、知识图谱、左侧边栏布局
-->
<template>
  <div class="writing-workbench">
    <!-- 顶部状态栏 -->
    <div class="workbench-header">
      <!-- 项目标题区域 -->
      <div class="project-title-section">
        <el-tag
          :type="getContentTypeTagType(actualContentType)"
          size="large"
          effect="plain"
        >
          {{ getContentTypeLabel(actualContentType) }}
        </el-tag>
        <span class="project-title">{{
          props.projectTitle || "写作工作台"
        }}</span>
      </div>

      <!-- 任务状态信息（有任务时显示） -->
      <div v-if="writingStore.currentTask" class="task-status-section">
        <el-tag
          :type="getStatusType(writingStore.currentTask?.status)"
          size="large"
          effect="dark"
        >
          {{ getStatusLabel(writingStore.currentTask?.status) }}
        </el-tag>
        <div class="progress-wrapper">
          <el-progress
            :percentage="writingStore.progress"
            :stroke-width="10"
            :status="writingStore.isCompleted ? 'success' : ''"
          />
          <span class="progress-text">
            {{ writingStore.currentTask?.completed_units || 0 }} /
            {{ writingStore.currentTask?.total_units || 0 }} 单元
          </span>
        </div>
        <div class="quick-stats">
          <el-tooltip content="总耗时">
            <span class="stat-item">
              <el-icon><Timer /></el-icon>
              {{ formattedDuration }}
            </span>
          </el-tooltip>
          <el-tooltip content="Token消耗">
            <span class="stat-item">
              <el-icon><Coin /></el-icon>
              {{ formatNumber(writingStore.currentTask?.total_tokens || 0) }}
            </span>
          </el-tooltip>
          <el-tooltip content="预估费用">
            <span class="stat-item">
              <el-icon><Money /></el-icon>
              ${{ (writingStore.currentTask?.total_cost || 0).toFixed(4) }}
            </span>
          </el-tooltip>
        </div>
      </div>
      <!-- 单元概览（无任务时显示） -->
      <div v-else class="unit-overview-section">
        <el-tag type="info" size="large" effect="plain">
          <el-icon><List /></el-icon>
          共 {{ displayUnits.length }} {{ unitLabel }}
        </el-tag>
        <span class="overview-hint">选择起始单元和生成数量，开始创作</span>
      </div>
      <div class="task-actions">
        <!-- 任务控制按钮（有任务时显示） -->
        <template v-if="writingStore.currentTask">
          <el-button
            v-if="writingStore.isRunning"
            type="warning"
            @click="handleInterrupt"
            :loading="interrupting"
          >
            <el-icon><VideoPause /></el-icon>
            中断
          </el-button>
          <el-button
            v-if="writingStore.canResume"
            type="success"
            @click="handleResume"
            :loading="writingStore.loading"
          >
            <el-icon><VideoPlay /></el-icon>
            续传
          </el-button>
          <el-button
            v-if="writingStore.isCompleted"
            type="primary"
            @click="showContinueDialog = true"
            :disabled="!canContinueGenerate"
          >
            <el-icon><Plus /></el-icon>
            继续生成
          </el-button>
          <el-button
            v-if="!writingStore.isRunning"
            type="danger"
            plain
            @click="handleDelete"
          >
            <el-icon><Delete /></el-icon>
            删除
          </el-button>
        </template>
        <!-- 下载全文按钮（始终显示） -->
        <el-button
          type="success"
          @click="handleExport"
          :disabled="!hasGeneratedContent"
        >
          <el-icon><Download /></el-icon>
          下载全文
        </el-button>
      </div>
    </div>

    <!-- 主内容区（无任务时显示）-->
    <div v-if="!writingStore.currentTask" class="task-creation">
      <div class="workbench-layout">
        <!-- 左侧边栏：项目准备面板 -->
        <div class="left-sidebar">
          <ProjectSetupPanel
            :project="projectData"
            :chapters="displayUnits"
            :unit-label="unitLabel"
            :generating-directory="generatingDirectory"
            @upload-outline="showOutlineUploadDialog = true"
            @upload-unit-summaries="showUnitSummariesUploadDialog = true"
            @generate-directory="handleGenerateDirectory"
            @show-knowledge-graph="knowledgeGraphVisible = true"
            @show-consistency-report="consistencyReportVisible = true"
            @build-knowledge-base="handleBuildKnowledgeBase"
            @show-settings="showSettingsDialog = true"
          />
          <!-- 架构优化：移除 :chapter-outlines, @generate-chapter-outlines, @view-chapter-outlines -->
        </div>

        <!-- 右侧主区域 -->
        <div class="right-main-area">
          <!-- 单元概述缺失提示（仅小说类型显示） -->
          <el-alert
            v-if="
              !hasUnitSummaries &&
              (actualContentType === 'novel')
            "
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
                单元概述可从“创意生成”板块导出后上传，或直接在下方输入。
              </p>
              <el-button
                type="primary"
                size="small"
                style="margin-top: 8px"
                @click="showUnitSummariesUploadDialog = true"
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
                    @click="handleCreateTask"
                    :loading="writingStore.loading"
                  >
                    <el-icon><VideoPlay /></el-icon>
                    开始生成正文
                  </el-button>
                  <el-button
                    size="small"
                    type="primary"
                    plain
                    @click="showAgentConfigDialog = true"
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

            <!-- AI文风消除配置 -->
            <div class="ai-elimination-config">
              <div class="config-header">
                <span class="header-title">
                  <el-icon><MagicStick /></el-icon>
                  AI文风消除
                </span>
                <el-switch 
                  v-model="taskForm.ai_elimination_enabled"
                  @change="handleTaskAiEliminationChange"
                />
              </div>
              <div class="config-content" v-if="taskForm.ai_elimination_enabled">
                <div class="threshold-row">
                  <span class="threshold-label">消除强度</span>
                  <el-slider 
                    v-model="taskForm.ai_elimination_threshold" 
                    :min="0" 
                    :max="100" 
                    :step="10"
                    :format-tooltip="(val) => `${val}%`"
                    style="flex: 1; margin: 0 16px;"
                  />
                  <span class="threshold-value">{{ taskForm.ai_elimination_threshold }}%</span>
                </div>
                <el-text type="info" size="small">
                  消除AI生成文本的机械感，使内容更接近自然人类写作风格
                </el-text>
              </div>
            </div>

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
          </el-card>

          <!-- 架构优化：已移除单元大纲生成面板 -->

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
                :class="{
                  'is-selected': unit.unit_index === taskForm.start_from,
                }"
                @click="taskForm.start_from = unit.unit_index"
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
      </div>
    </div>

    <!-- 主内容区（有任务时）-->
    <div v-else class="workbench-main">
      <el-row :gutter="20">
        <!-- 左侧：实时进度面板 -->
        <el-col :span="14">
          <el-card class="progress-panel" shadow="hover">
            <template #header>
              <div class="panel-header">
                <span>
                  <el-icon><DataLine /></el-icon>
                  实时进度
                </span>
                <el-tag
                  v-if="writingStore.wsConnected"
                  type="success"
                  size="small"
                  effect="plain"
                >
                  <el-icon><Connection /></el-icon>
                  实时连接
                </el-tag>
                <el-tag v-else type="info" size="small" effect="plain">
                  <el-icon><Loading /></el-icon>
                  连接中...
                </el-tag>
              </div>
            </template>

            <!-- Agent状态流水线 -->
            <div class="agent-pipeline">
              <div
                v-for="(agent, idx) in agentPipeline"
                :key="agent.role"
                class="pipeline-item"
                :class="agent.status"
              >
                <div class="pipeline-icon">
                  <el-icon :size="24">
                    <component :is="agent.icon" />
                  </el-icon>
                  <div
                    v-if="idx < agentPipeline.length - 1"
                    class="pipeline-arrow"
                  >
                    <el-icon><ArrowRight /></el-icon>
                  </div>
                </div>
                <div class="pipeline-info">
                  <span class="pipeline-name">{{ agent.label }}</span>
                  <el-tag :type="agent.statusType" size="small">
                    {{ agent.statusLabel }}
                  </el-tag>
                </div>
              </div>
            </div>

            <!-- 工作流步骤显示 -->
            <div v-if="workflowSteps.length > 0" class="workflow-steps-section">
              <el-divider content-position="left">执行步骤</el-divider>
              <div class="workflow-steps">
                <div
                  v-for="(step, index) in workflowSteps"
                  :key="`${step.step}-${index}`"
                  class="workflow-step"
                  :class="{
                    'is-running': step.status === 'running',
                    'is-done': step.status === 'done',
                    'is-error': step.status === 'error',
                  }"
                >
                  <div class="step-icon">
                    <el-icon
                      v-if="step.status === 'running'"
                      class="is-spinning"
                      ><Loading
                    /></el-icon>
                    <el-icon v-else-if="step.status === 'done'" color="#67C23A"
                      ><CircleCheck
                    /></el-icon>
                    <el-icon v-else-if="step.status === 'error'" color="#F56C6C"
                      ><CircleClose
                    /></el-icon>
                    <el-icon v-else><component :is="step.icon" /></el-icon>
                  </div>
                  <div class="step-content">
                    <div class="step-message">{{ step.message }}</div>
                  </div>
                  <div class="step-status">
                    <el-tag
                      v-if="step.status === 'done'"
                      type="success"
                      size="small"
                      >完成</el-tag
                    >
                    <el-tag
                      v-else-if="step.status === 'running'"
                      type="warning"
                      size="small"
                      >执行中</el-tag
                    >
                    <el-tag
                      v-else-if="step.status === 'error'"
                      type="danger"
                      size="small"
                      >失败</el-tag
                    >
                  </div>
                </div>
              </div>
            </div>

            <!-- 当前处理信息 -->
            <div v-if="currentProcessingInfo" class="current-processing">
              <el-divider content-position="left">当前处理</el-divider>
              <div class="processing-info">
                <el-icon><Loading class="is-loading" /></el-icon>
                <span>{{ currentProcessingInfo }}</span>
              </div>
            </div>

            <!-- 进度消息列表 -->
            <div class="progress-messages">
              <el-divider content-position="left">执行日志</el-divider>
              <div class="messages-list" ref="messagesListRef">
                <div
                  v-for="(msg, idx) in writingStore.progressMessages"
                  :key="idx"
                  class="progress-item"
                  :class="msg.type"
                >
                  <el-tag
                    size="small"
                    :type="getMessageTagType(msg)"
                    class="msg-agent"
                  >
                    {{
                      msg.data?.agent_name ||
                      getAgentLabel(msg.data?.agent_role) ||
                      "系统"
                    }}
                  </el-tag>
                  <span class="msg-content">{{
                    msg.data?.message || msg.type
                  }}</span>
                  <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
                </div>
                <el-empty
                  v-if="writingStore.progressMessages.length === 0"
                  description="暂无进度消息"
                  :image-size="60"
                />
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：单元/场景浏览面板 -->
        <el-col :span="10">
          <el-card class="units-panel" shadow="hover">
            <template #header>
              <div class="panel-header">
                <span>
                  <el-icon><List /></el-icon>
                  单元列表
                </span>
                <div class="panel-header-actions">
                  <!-- 知识图谱快捷入口 -->
                  <el-tooltip content="查看实时知识图谱：人物关系、地点、事件等" placement="top">
                    <el-button
                      type="primary"
                      size="small"
                      plain
                      @click="knowledgeGraphVisible = true"
                    >
                      <el-icon><Connection /></el-icon>
                      知识图谱
                    </el-button>
                  </el-tooltip>
                  <!-- 一致性检查报告快捷入口 -->
                  <el-tooltip content="查看一致性检查报告：人物状态、设施状态、待回收伏笔等" placement="top">
                    <el-button
                      type="success"
                      size="small"
                      plain
                      @click="consistencyReportVisible = true"
                    >
                      <el-icon><DataAnalysis /></el-icon>
                      一致性报告
                    </el-button>
                  </el-tooltip>
                  <el-tag type="info" size="small">
                    {{ displayUnits.length }} 单元
                  </el-tag>
                </div>
              </div>
            </template>

            <el-collapse v-model="activeUnits" class="units-collapse">
              <el-collapse-item
                v-for="unit in displayUnits"
                :key="unit.unit_index"
                :name="unit.unit_index"
                @click="handleUnitExpand(unit)"
              >
                <template #title>
                  <div class="unit-title">
                    <span class="unit-index">#{{ unit.unit_index }}</span>
                    <span class="unit-name" :title="unit.unit_title">
                      {{ unit.unit_title || `单元 ${unit.unit_index}` }}
                    </span>
                    <el-tag :type="getUnitStatusType(unit.status)" size="small">
                      {{ getUnitStatusLabel(unit.status) }}
                    </el-tag>
                    <span v-if="unit.word_count > 0" class="unit-word-count">
                      {{ unit.word_count }} 字
                    </span>
                    <el-button
                      v-if="unit.status === 'completed'"
                      type="primary"
                      size="small"
                      link
                      @click.stop="handleExportUnit(unit.unit_index)"
                    >
                      <el-icon><Download /></el-icon>
                    </el-button>
                  </div>
                </template>

                <!-- 场景列表 -->
                <div
                  class="scenes-list"
                  v-loading="loadingScenes[unit.unit_index]"
                >
                  <div
                    v-for="scene in getScenes(unit.unit_index)"
                    :key="scene.scene_index"
                    class="scene-item"
                    @click.stop="handleSceneClick(scene, unit)"
                  >
                    <div class="scene-info">
                      <span class="scene-index"
                        >场景 {{ scene.scene_index }}</span
                      >
                      <span class="scene-title">{{
                        scene.scene_title || "未命名场景"
                      }}</span>
                    </div>
                    <div class="scene-meta">
                      <el-tag
                        :type="getSceneStatusType(scene.status)"
                        size="small"
                      >
                        {{ getSceneStatusLabel(scene.status) }}
                      </el-tag>
                      <span
                        v-if="scene.word_count > 0"
                        class="scene-word-count"
                      >
                        {{ scene.word_count }} 字
                      </span>
                    </div>
                  </div>
                  <el-empty
                    v-if="
                      getScenes(unit.unit_index).length === 0 &&
                      !loadingScenes[unit.unit_index]
                    "
                    description="暂无场景"
                    :image-size="40"
                  />
                </div>
              </el-collapse-item>
            </el-collapse>

            <el-empty
              v-if="displayUnits.length === 0"
              description="暂无单元数据"
              :image-size="60"
            />
          </el-card>
        </el-col>
      </el-row>

      <!-- 底部：统计仪表板 -->
      <el-card v-if="writingStore.stats" class="stats-dashboard" shadow="hover">
        <template #header>
          <div class="panel-header">
            <span>
              <el-icon><TrendCharts /></el-icon>
              Agent统计
            </span>
          </div>
        </template>

        <el-row :gutter="20">
          <!-- 总体统计 -->
          <el-col :span="6">
            <div class="stat-card total">
              <div class="stat-icon">
                <el-icon><Coin /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">
                  {{
                    formatNumber(
                      writingStore.stats?._summary?.total_tokens ||
                        writingStore.stats?.total_tokens ||
                        0,
                    )
                  }}
                </div>
                <div class="stat-label">总Token数</div>
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card cost">
              <div class="stat-icon">
                <el-icon><Money /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">
                  ${{
                    (
                      writingStore.stats?._summary?.total_cost ||
                      writingStore.stats?.total_cost ||
                      0
                    ).toFixed(4)
                  }}
                </div>
                <div class="stat-label">总费用</div>
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card time">
              <div class="stat-icon">
                <el-icon><Timer /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">
                  {{ writingStore.formattedDuration }}
                </div>
                <div class="stat-label">总耗时</div>
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card efficiency">
              <div class="stat-icon">
                <el-icon><Odometer /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ calculateEfficiency() }}</div>
                <div class="stat-label">Token/秒</div>
              </div>
            </div>
          </el-col>
        </el-row>

        <!-- Agent详细统计 -->
        <el-divider content-position="left">Agent详细统计</el-divider>
        <el-table
          :data="writingStore.stats.by_agent || []"
          stripe
          style="width: 100%"
        >
          <el-table-column prop="agent_name" label="Agent" width="120">
            <template #default="{ row }">
              <el-tag :type="getAgentTagType(row.agent_name)" effect="plain">
                {{ row.agent_name }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="model_id"
            label="模型"
            min-width="150"
            show-overflow-tooltip
          />
          <el-table-column
            prop="call_count"
            label="调用次数"
            width="100"
            align="center"
          />
          <el-table-column
            prop="total_tokens"
            label="Token数"
            width="120"
            align="right"
          >
            <template #default="{ row }">
              {{ formatNumber(row.total_tokens) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="total_cost"
            label="费用"
            width="100"
            align="right"
          >
            <template #default="{ row }">
              ${{ row.total_cost?.toFixed(4) || "0.0000" }}
            </template>
          </el-table-column>
          <el-table-column
            prop="total_duration_sec"
            label="耗时"
            width="100"
            align="right"
          >
            <template #default="{ row }">
              {{ row.total_duration_sec?.toFixed(1) || "0.0" }}s
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 场景内容查看对话框 -->
    <el-dialog
      v-model="sceneDialogVisible"
      :title="selectedSceneTitle"
      width="800px"
      destroy-on-close
      class="scene-dialog"
    >
      <div v-if="selectedScene" class="scene-content">
        <div class="scene-meta-info">
          <el-tag :type="getSceneStatusType(selectedScene.status)">
            {{ getSceneStatusLabel(selectedScene.status) }}
          </el-tag>
          <span v-if="selectedScene.word_count > 0">
            <el-icon><Document /></el-icon>
            {{ selectedScene.word_count }} 字
          </span>
          <span v-if="selectedScene.token_count > 0">
            <el-icon><Coin /></el-icon>
            {{ formatNumber(selectedScene.token_count) }} tokens
          </span>
        </div>
        <el-divider />
        <div class="content-body">
          <pre v-if="selectedScene.final_content">{{
            selectedScene.final_content
          }}</pre>
          <el-empty v-else description="暂无内容" />
        </div>
      </div>
    </el-dialog>

    <!-- 继续生成对话框 -->
    <el-dialog
      v-model="showContinueDialog"
      title="继续生成"
      width="400px"
      destroy-on-close
    >
      <div class="continue-dialog-content">
        <p class="continue-hint">
          当前已完成
          <strong>{{ writingStore.currentTask?.completed_units || 0 }}</strong>
          个单元。
        </p>
        <el-form label-width="100px">
          <el-form-item label="生成数量">
            <el-input-number
              v-model="continueUnitCount"
              :min="1"
              :max="10"
              :step="1"
              style="width: 150px"
            />
            <span class="input-hint">个单元</span>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showContinueDialog = false">取消</el-button>
        <el-button type="primary" @click="handleContinue"> 开始生成 </el-button>
      </template>
    </el-dialog>

    <!-- Agent配置对话框 -->
    <el-dialog
      v-model="showAgentConfigDialog"
      title="Agent配置"
      width="950px"
      destroy-on-close
      class="agent-config-dialog"
    >
      <div class="agent-dialog-content">
        <!-- 并发配置 -->
        <div class="concurrency-section">
          <div class="section-header">
            <el-icon><Setting /></el-icon>
            <span>并发配置</span>
          </div>
          <div class="concurrency-config">
            <div class="config-item">
              <span class="config-label">并发写手数量：</span>
              <el-slider
                v-model="taskForm.concurrency"
                :min="1"
                :max="10"
                show-stops
                show-input
                style="width: 300px"
              />
            </div>
            <div class="config-hint">
              同时运行的写手Agent数量，建议根据API速率限制调整
            </div>
          </div>
        </div>

        <el-divider />

        <!-- 一键应用区域 -->
        <div class="quick-apply-section">
          <span class="section-label">快速配置：</span>
          <el-select
            v-model="quickApplyConfigId"
            placeholder="选择模型配置，一键应用到所有Agent"
            style="width: 300px"
            clearable
          >
            <el-option
              v-for="config in modelConfigs.filter((c) => c.is_active)"
              :key="config.id"
              :label="`${config.name} (${config.provider_display || config.provider} / ${config.model_id})`"
              :value="config.id"
            />
          </el-select>
          <el-button
            type="primary"
            :disabled="!quickApplyConfigId"
            @click="handleQuickApply"
          >
            应用到全部
          </el-button>
        </div>

        <el-divider />

        <!-- Agent配置列表 -->
        <div class="agent-list">
          <div
            v-for="agent in configurableAgents"
            :key="agent.role"
            class="agent-item"
          >
            <div class="agent-header">
              <el-icon :size="20"
                ><component :is="getAgentIcon(agent.role)"
              /></el-icon>
              <span class="agent-name">{{ agent.label }}</span>
              <el-tooltip :content="agent.description" placement="top">
                <el-icon class="info-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
            <div class="agent-config-row">
              <el-select
                v-model="taskForm.agent_config_ids[agent.role]"
                placeholder="选择预配置模型"
                style="width: 250px"
                clearable
                @change="onModelConfigChange(agent.role, $event)"
              >
                <el-option
                  v-for="config in modelConfigs.filter((c) => c.is_active)"
                  :key="config.id"
                  :label="`${config.name} (${config.provider_display || config.provider})`"
                  :value="config.id"
                />
                <el-option label="自定义配置..." :value="'custom'" />
              </el-select>
              <div class="temp-slider">
                <span class="temp-label">温度:</span>
                <el-slider
                  v-model="taskForm.agent_temps[agent.role]"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  style="width: 120px"
                />
                <span class="temp-value">{{
                  taskForm.agent_temps[agent.role]
                }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showAgentConfigDialog = false">取消</el-button>
        <el-button type="primary" @click="showAgentConfigDialog = false"
          >确定</el-button
        >
      </template>
    </el-dialog>

    <!-- 单元概述上传对话框 -->
    <el-dialog
      v-model="showUnitSummariesUploadDialog"
      title="上传单元概述"
      width="650px"
      destroy-on-close
    >
      <div class="unit-summaries-upload-dialog">
        <el-alert type="info" :closable="false" style="margin-bottom: 16px">
          <template #title>支持的格式</template>
          <div style="font-size: 13px">
            <p>
              <strong>文件格式：</strong
              >TXT（纯文本）、Markdown（.md）、Word文档（.docx, .doc）
            </p>
            <p style="margin-top: 6px"><strong>内容要求：</strong></p>
            <ul style="margin: 4px 0; padding-left: 20px">
              <li>小说：包含章节标题（如 ### 第1章：xxx）和梗概内容</li>
              <li>剧集剧本：包含分集标题（如 ### 第1集：xxx）和梗概内容</li>
              <li>电影剧本：包含场景标题（如 **第1场：xxx）和梗概内容</li>
            </ul>
            <p style="margin-top: 6px; color: #909399">
              系统将自动识别章节结构并解析单元概述
            </p>
          </div>
        </el-alert>

        <el-upload
          ref="unitSummariesUploadRef"
          :auto-upload="false"
          :limit="1"
          :on-change="handleUnitSummariesFileChange"
          :on-exceed="handleUploadExceed"
          :file-list="unitSummariesFileList"
          accept=".txt,.md,.docx,.doc"
          drag
        >
          <el-icon class="el-icon--upload"><Upload /></el-icon>
          <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">
              支持 .txt, .md, .docx, .doc 格式文件
            </div>
          </template>
        </el-upload>
      </div>
      <template #footer>
        <el-button @click="handleCancelUnitSummariesUpload">取消</el-button>
        <el-button
          type="primary"
          @click="handleUploadUnitSummariesFile"
          :loading="uploadingUnitSummaries"
          :disabled="unitSummariesFileList.length === 0"
        >
          确认上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 大纲上传弹窗 -->
    <el-dialog
      v-model="showOutlineUploadDialog"
      title="上传大纲"
      width="600px"
      destroy-on-close
    >
      <div class="outline-upload-content">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        >
          <template #title>支持的格式</template>
          <p style="margin: 4px 0">
            TXT（纯文本）、Markdown（.md）、JSON（结构化大纲）
          </p>
        </el-alert>

        <el-upload
          ref="outlineUploadRef"
          :auto-upload="false"
          :limit="1"
          :on-change="handleOutlineFileChange"
          accept=".txt,.md,.json"
          drag
        >
          <el-icon class="el-icon--upload"><Upload /></el-icon>
          <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
        </el-upload>

        <el-divider>或直接输入内容</el-divider>

        <el-form label-width="80px">
          <el-form-item label="大纲内容">
            <el-input
              v-model="outlineInput"
              type="textarea"
              :rows="10"
              placeholder="请粘贴大纲内容..."
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showOutlineUploadDialog = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleUploadOutline"
          :loading="uploadingOutline"
          :disabled="!outlineInput.trim()"
        >
          确认上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 知识图谱弹窗 -->
    <KnowledgeGraphDialog
      v-model:visible="knowledgeGraphVisible"
      :project-id="projectId"
      :total-units="projectTotalUnits"
      :unit-label="unitLabel"
      @build-knowledge-base="handleBuildKnowledgeBase"
    />

    <!-- 一致性检查报告弹窗 -->
    <ConsistencyReportDialog
      v-model:visible="consistencyReportVisible"
      :project-id="projectId"
      :total-units="projectTotalUnits"
      :unit-label="unitLabel"
    />

    <!-- 项目设置弹窗 -->
    <el-dialog
      v-model="showSettingsDialog"
      title="项目设置"
      width="600px"
      destroy-on-close
    >
      <el-form label-width="100px">
        <el-form-item label="项目名称">
          <el-input v-model="projectData.name" disabled />
        </el-form-item>
        <el-form-item label="内容类型">
          <el-tag>{{ getContentTypeLabel(projectData.content_type) }}</el-tag>
        </el-form-item>
        <el-form-item label="创建时间">
          <span>{{ projectData.created_at }}</span>
        </el-form-item>
      </el-form>

      <!-- 风格设置区域 -->
      <el-divider content-position="left">
        <el-icon><Edit /></el-icon>
        <span style="margin-left: 6px;">风格设置</span>
      </el-divider>
      
      <div class="style-settings-section">
        <!-- 风格文档上传 -->
        <div class="style-document-section">
          <div class="section-header">
            <span class="section-title">风格文档</span>
            <el-tag v-if="styleDocumentInfo?.style_document_uploaded" type="success" size="small">
              已上传
            </el-tag>
          </div>
          
          <div class="style-document-content">
            <div v-if="styleDocumentInfo?.style_document_uploaded" class="uploaded-document">
              <div class="document-info">
                <el-icon><Document /></el-icon>
                <span class="document-name">{{ styleDocumentInfo.style_document_name }}</span>
              </div>
              <div class="document-actions">
                <el-button type="primary" plain size="small" @click="showStyleDocumentDetail = true">
                  查看详情
                </el-button>
                <el-button type="danger" plain size="small" @click="handleDeleteStyleDocument">
                  删除
                </el-button>
              </div>
            </div>
            
            <div v-else class="upload-section">
              <el-upload
                class="style-upload"
                :action="styleUploadAction"
                :headers="uploadHeaders"
                :show-file-list="false"
                :on-success="handleStyleUploadSuccess"
                :on-error="handleStyleUploadError"
                :before-upload="beforeStyleUpload"
                accept=".txt,.docx,.pdf"
              >
                <el-button type="primary" plain>
                  <el-icon><Upload /></el-icon>
                  上传风格文档
                </el-button>
              </el-upload>
              <el-text type="info" size="small">
                支持 .txt, .docx, .pdf 格式，AI将分析并模仿该文档的写作风格
              </el-text>
            </div>
          </div>
        </div>

        <!-- AI文风消除设置 -->
        <div class="ai-elimination-section">
          <div class="section-header">
            <span class="section-title">AI文风消除</span>
            <el-switch 
              v-model="aiEliminationEnabled" 
              @change="handleAiEliminationChange"
            />
          </div>
          <div class="elimination-config" v-if="aiEliminationEnabled">
            <div class="threshold-setting">
              <span class="threshold-label">消除强度</span>
              <el-slider 
                v-model="aiEliminationThreshold" 
                :min="0" 
                :max="100" 
                :step="10"
                show-input
                @change="handleThresholdChange"
              />
            </div>
            <el-text type="info" size="small">
              强度越高，AI生成特征消除越明显，但可能影响原文风格
            </el-text>
          </div>
        </div>
      </div>

      <!-- 模型配置入口 -->
      <el-divider />
      <div class="settings-model-config">
        <div class="config-info">
          <el-icon><Setting /></el-icon>
          <span>LLM模型配置</span>
        </div>
        <el-button type="primary" @click="showModelConfigDialog = true">
          管理模型配置
        </el-button>
      </div>
      <template #footer>
        <el-button @click="showSettingsDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 风格文档详情弹窗 -->
    <el-dialog
      v-model="showStyleDocumentDetail"
      title="风格文档详情"
      width="700px"
      destroy-on-close
    >
      <!-- 空状态处理 -->
      <div v-if="!styleDocumentInfo" class="empty-state">
        <el-empty description="暂无风格文档数据">
          <el-button type="primary" @click="handleRefreshStyleDocument">重新加载</el-button>
        </el-empty>
      </div>
      
      <div v-else class="style-detail-content">
        <div class="detail-section" v-if="styleDocumentInfo.style_profile">
          <h4>风格特征</h4>
          <div class="profile-grid">
            <div class="profile-item" v-if="styleDocumentInfo.style_profile.vocabulary">
              <span class="item-label">词汇特征</span>
              <span class="item-value">{{ styleDocumentInfo.style_profile.vocabulary?.word_preference || '-' }}</span>
            </div>
            <div class="profile-item" v-if="styleDocumentInfo.style_profile.sentence_structure">
              <span class="item-label">句式特征</span>
              <span class="item-value">{{ styleDocumentInfo.style_profile.sentence_structure?.rhythm || styleDocumentInfo.style_profile.sentence_structure?.average_length || '-' }}</span>
            </div>
            <div class="profile-item" v-if="styleDocumentInfo.style_profile.narrative_style">
              <span class="item-label">叙事特征</span>
              <span class="item-value">{{ styleDocumentInfo.style_profile.narrative_style?.perspective || '-' }}</span>
            </div>
          </div>
        </div>
        
        <div class="detail-section" v-if="styleDocumentInfo.key_imitation_points?.length">
          <h4>模仿要点</h4>
          <ul class="imitation-points">
            <li v-for="(point, index) in styleDocumentInfo.key_imitation_points" :key="index">
              {{ point }}
            </li>
          </ul>
        </div>
        
        <div class="detail-section" v-if="styleDocumentInfo.avoid_patterns?.length">
          <h4>应避免的模式</h4>
          <ul class="avoid-patterns">
            <li v-for="(pattern, index) in styleDocumentInfo.avoid_patterns" :key="index">
              {{ pattern }}
            </li>
          </ul>
        </div>
        
        <div class="detail-section" v-if="styleDocumentInfo.style_guide_for_writing">
          <h4>风格指南</h4>
          <p class="style-guide">{{ styleDocumentInfo.style_guide_for_writing }}</p>
        </div>
        
        <!-- 无数据提示 -->
        <div v-if="!hasStyleDocumentData" class="no-data-tip">
          <el-text type="info">风格文档分析结果尚未生成或不完整，请重新上传分析。</el-text>
        </div>
      </div>
      <template #footer>
        <el-button @click="showStyleDocumentDetail = false">关闭</el-button>
        <el-button type="primary" v-if="styleDocumentInfo" @click="handleRefreshStyleDocument">刷新数据</el-button>
      </template>
    </el-dialog>

    <!-- 模型配置弹窗 -->
    <el-dialog
      v-model="showModelConfigDialog"
      title="LLM模型配置管理"
      width="90%"
      top="5vh"
      destroy-on-close
    >
      <ModelConfigPanel />
      <template #footer>
        <el-button type="primary" @click="showModelConfigDialog = false"
          >关闭</el-button
        >
      </template>
    </el-dialog>

    <!-- 架构优化：已移除章节大纲预览对话框和已生成大纲列表对话框 -->
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from "vue";
import { useRoute } from "vue-router";
import { useWritingTaskStore } from "@/stores/writingTask";
import { novelWriterApi } from "@/api/novel-writer";
import { writingTaskApi } from "@/api/writing-task";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  VideoPause,
  VideoPlay,
  Delete,
  EditPen,
  Timer,
  Coin,
  Money,
  DataLine,
  Connection,
  Loading,
  ArrowRight,
  List,
  TrendCharts,
  Document,
  OfficeBuilding,
  View,
  SetUp,
  Odometer,
  MagicStick,
  Warning,
  Reading,
  Download,
  CircleCheck,
  CircleClose,
  Setting,
  InfoFilled,
  Upload,
  Plus,
  Refresh,
  Edit,
  Close,
  DataAnalysis,
} from "@element-plus/icons-vue";

// 导入子组件
import ProjectSetupPanel from "./components/ProjectSetupPanel.vue";
import KnowledgeGraphDialog from "./components/KnowledgeGraphDialog.vue";
import ConsistencyReportDialog from "./components/ConsistencyReportDialog.vue";
import ModelConfigPanel from "./ModelConfigPanel.vue";
// 架构优化：移除 GenerationModeSelector 组件导入

// ==================== Props ====================
const props = defineProps({
  projectId: {
    type: [Number, String],
    // 支持从路由参数获取
    default: null,
  },
  projectTotalUnits: {
    type: Number,
    default: 0,
  },
  unitSummaries: {
    type: Object,
    default: () => ({}),
  },
  contentType: {
    type: String,
    default: "novel",
  },
  projectType: {
    type: String,
    default: "novel",
  },
  chapters: {
    type: Array,
    default: () => [],
  },
  // 新增 props
  projectTitle: {
    type: String,
    default: "",
  },
  projectData: {
    type: Object,
    default: () => ({}),
  },
  chapterOutlines: {
    type: Object,
    default: () => ({}),
  },
});

// ==================== Emits ====================
const emit = defineEmits(["refresh", "update-project"]);

// 获取实际的内容类型（优先使用本地加载的项目数据）
const actualContentType = computed(() => {
  // 优先使用本地加载的项目数据
  if (localProjectData.value?.content_type) {
    return localProjectData.value.content_type;
  }
  // 回退到 props
  return props.contentType || props.projectType || "novel";
});

// 根据项目类型获取单元标签
const unitLabel = computed(() => {
  switch (actualContentType.value) {
    case "series_script":
      return "集";
    case "movie_script":
      return "场";
    default:
      return "章";
  }
});

// 是否为小说类型（用于字数控制组件的条件渲染）
const isNovelType = computed(() => {
  return actualContentType.value === "novel";
});

// 剧本类型的时长标签
const durationLabel = computed(() => {
  switch (actualContentType.value) {
    case "series_script":
      return "单集时长";
    case "movie_script":
      return "单场时长";
    default:
      return "时长控制";
  }
});

// 剧本类型的时长提示
const durationHint = computed(() => {
  switch (actualContentType.value) {
    case "series_script":
      return "剧本按场景时长自动控制，无需手动设置字数";
    case "movie_script":
      return "电影剧本按时长分配场景，字数自动计算";
    default:
      return "剧本按时长控制生成";
  }
});

// 获取当前起始单元的名称
const currentUnitName = computed(() => {
  const unitIndex = taskForm.value.start_from;
  if (unitSummaries.value && unitSummaries.value[unitIndex]) {
    return (
      unitSummaries.value[unitIndex].title || unitSummaries.value[unitIndex]
    );
  }
  return `第${unitIndex}${unitLabel.value}`;
});

// ==================== Store ====================
const writingStore = useWritingTaskStore();

// ==================== Route ====================
const route = useRoute();

// 计算项目ID（优先使用props，其次从路由获取）
const projectId = computed(() => {
  if (props.projectId) return Number(props.projectId);
  if (route.params.id) return Number(route.params.id);
  return null;
});

// 本地项目数据（从API加载）
const localProjectData = ref({});
const loadingProject = ref(false);

// 加载项目数据
async function loadProjectData() {
  if (!projectId.value) return;

  loadingProject.value = true;
  try {
    const res = await novelWriterApi.getProject(projectId.value);
    if (res.success) {
      localProjectData.value = res.data;
    }
  } catch (error) {
    ElMessage.error("加载项目数据失败");
  } finally {
    loadingProject.value = false;
  }
}

// 合并后的项目数据（优先使用props传入的，其次使用本地加载的）
const projectData = computed(() => {
  return props.projectData && Object.keys(props.projectData).length > 0
    ? props.projectData
    : localProjectData.value;
});

// 项目总单元数（计算属性）
const projectTotalUnits = computed(() => {
  if (props.projectTotalUnits && props.projectTotalUnits > 0) {
    return props.projectTotalUnits;
  }
  return projectData.value?.total_chapters || 0;
});

// 单元概述数据
const unitSummaries = computed(() => {
  if (props.unitSummaries && Object.keys(props.unitSummaries).length > 0) {
    return props.unitSummaries;
  }
  return projectData.value?.unit_summaries || {};
});

// 是否有单元概述
const hasUnitSummaries = computed(() => {
  return unitSummaries.value && Object.keys(unitSummaries.value).length > 0;
});

// 架构优化：移除 chapterOutlines 计算属性

// ==================== Refs ====================
const activeCollapse = ref(["agents"]);
const activeUnits = ref([]);
const interrupting = ref(false);
const loadingScenes = ref({});
const messagesListRef = ref(null);
const sceneDialogVisible = ref(false);
const selectedScene = ref(null);
const selectedUnit = ref(null);
const testingAgent = ref({}); // 记录正在测试的agent
const showAgentConfigDialog = ref(false); // Agent配置对话框显示状态
const quickApplyConfigId = ref(null); // 快速应用模型配置ID

// 大纲上传相关
const showOutlineUploadDialog = ref(false);
const outlineInput = ref("");
const uploadingOutline = ref(false);
const outlineUploadRef = ref(null);

// 知识图谱相关
const knowledgeGraphVisible = ref(false);

// 一致性检查报告相关
const consistencyReportVisible = ref(false);

// 章节大纲预览相关
// 架构优化：移除 outlineForm, showOutlineListDialog, showChapterOutlineDialog, currentChapterOutline, currentChapterNum

// 项目设置弹窗
const showSettingsDialog = ref(false);

// 模型配置弹窗
const showModelConfigDialog = ref(false);

// 风格文档相关
const styleDocumentInfo = ref(null);
const showStyleDocumentDetail = ref(false);
const aiEliminationEnabled = ref(true);
const aiEliminationThreshold = ref(50);

// 计算属性：检查风格文档数据是否有效
const hasStyleDocumentData = computed(() => {
  if (!styleDocumentInfo.value) return false;
  const info = styleDocumentInfo.value;
  return !!(
    info.style_profile ||
    info.key_imitation_points?.length > 0 ||
    info.avoid_patterns?.length > 0 ||
    info.style_guide_for_writing
  );
});

// 风格文档上传地址
const styleUploadAction = computed(() => {
  return `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/novel-writer/projects/${projectId.value}/style-document`;
});

// 上传请求头
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
});

// 目录生成相关
const generatingDirectory = ref(false);

// 继续生成对话框
const showContinueDialog = ref(false);
const continueUnitCount = ref(1);

// 架构优化：移除 generatingOutlines, chapterOutlineProgress, chapterOutlineEventSource

// 单元概述上传相关
const showUnitSummariesUploadDialog = ref(false);
const unitSummariesUploadRef = ref(null);
const unitSummariesFileList = ref([]);
const uploadingUnitSummaries = ref(false);

// Provider相关
const availableProviders = ref([]);
const loadingProviders = ref(false);

// 预配置模型列表
const modelConfigs = ref([]);
const loadingConfigs = ref(false);

// ==================== Agent角色映射 ====================

/**
 * Agent角色中文显示名映射（与后端 AgentRole 枚举对应）
 */
const AGENT_ROLE_LABELS = {
  orchestrator: "总线Agent",
  structural: "结构师Agent",
  writer: "写手Agent",
  logic_editor: "逻辑编辑Agent",
  style_editor: "风格润色Agent",
  compliance: "合规审查Agent",
  knowledge: "知识顾问Agent",
  assembler: "合成Agent",
};

/**
 * Agent配置列表（角色名与后端 AgentRole 枚举一致）
 * 注意: assembler 不需要 LLM 配置，只做内容整合
 */
const agentConfigs = [
  {
    role: "orchestrator",
    label: "总线Agent",
    icon: "Connection",
    configurable: true,
    description:
      "任务调度和流程编排的核心Agent，负责控制其他Agent的协作顺序、管理并发写手数量、处理中断续传等。",
    configTips: {
      modelType: "推荐选择推理能力强的模型，需要稳定的决策输出",
      temperature: "建议 0.2-0.4，决策类任务需要低温度保持稳定性",
      extra: "此Agent是整个系统的调度中心，模型稳定性优先于创意性",
    },
  },
  {
    role: "structural",
    label: "结构师Agent",
    icon: "OfficeBuilding",
    configurable: true,
    description:
      "负责将写作大纲拆解为具体的场景列表，规划每个场景的叙事结构、人物出场、情节走向和目标字数。",
    configTips: {
      modelType: "推荐选择长文本理解和结构化输出能力强的模型",
      temperature: "建议 0.5-0.7，需要平衡结构严谨性和创意空间",
      extra: "结构师的输出质量直接影响后续所有写手的创作质量",
    },
  },
  {
    role: "writer",
    label: "写手Agent",
    icon: "EditPen",
    configurable: true,
    description:
      "核心内容创作Agent，根据场景大纲生成高质量的文学文本，是系统中调用频率最高的Agent。",
    configTips: {
      modelType: "推荐选择中文创作能力最强的模型，这是最核心的创作环节",
      temperature: "建议 0.7-0.9，高温度能增强文学创意性和表达多样性",
      extra: "建议使用最强的创作模型，写手Agent的质量决定了最终作品的质量",
    },
  },
  {
    role: "logic_editor",
    label: "逻辑编辑Agent",
    icon: "View",
    configurable: true,
    description:
      "负责审查内容的逻辑连贯性，包括情节逻辑、角色行为与人设一致性、时间线合理性、场景描述矛盾等。",
    configTips: {
      modelType: "推荐选择推理能力强的模型，如 thinking/reasoning 系列",
      temperature: "建议 0.1-0.3，逻辑分析需要极低温度保证严谨性",
      extra: "推理类模型（如带thinking标签的模型）在逻辑检查任务上表现更优",
    },
  },
  {
    role: "style_editor",
    label: "风格润色Agent",
    icon: "MagicStick",
    configurable: true,
    description:
      "负责优化文学风格、修辞手法、叙述节奏和语言质量，提升文本的文学性和可读性。",
    configTips: {
      modelType: "推荐选择中文理解和文学表达能力强的模型",
      temperature: "建议 0.5-0.7，需要平衡文风润色效果和保持原意",
      extra: "风格润色需要对中文文学有良好理解，建议选择中文优化过的模型",
    },
  },
  {
    role: "compliance",
    label: "合规审查Agent",
    icon: "Warning",
    configurable: true,
    description:
      "采用Trie树本地检测+LLM辅助判断的双层架构，检测敏感内容，确保生成内容符合发布规范。",
    configTips: {
      modelType: "推荐选择安全审查能力强、判断准确的模型",
      temperature: "建议 0.0-0.2，合规判断需要最高一致性，不容许随机性",
      extra: "合规审查的准确性直接关系到内容安全，建议选择经过安全训练的模型",
    },
  },
  {
    role: "knowledge",
    label: "知识顾问Agent",
    icon: "Reading",
    configurable: true,
    description:
      "负责检索项目知识库和上下文信息，为其他Agent提供背景参考资料，确保创作内容与项目设定一致。",
    configTips: {
      modelType: "推荐选择检索增强和准确回答能力强的模型",
      temperature: "建议 0.2-0.4，知识检索需要准确性优先",
      extra: "知识顾问的准确性影响其他Agent的创作一致性",
    },
  },
  {
    role: "assembler",
    label: "合成Agent",
    icon: "SetUp",
    configurable: false,
    description:
      "负责将同一单元下所有场景的最终内容合并为完整文本，纯规则合并，无需配置LLM模型。",
    configTips: null,
  },
];

// ==================== Form ====================
const taskForm = ref({
  start_from: 1,
  unit_count: null,
  words_per_chapter: 3000,
  concurrency: 3,
  generation_mode: "direct",  // 架构优化：固定使用direct模式
  agent_models: {
    orchestrator: "",
    structural: "",
    writer: "",
    logic_editor: "",
    style_editor: "",
    compliance: "",
    knowledge: "",
  },
  agent_temps: {
    orchestrator: 0.3,
    structural: 0.6,
    writer: 0.8,
    logic_editor: 0.2,
    style_editor: 0.6,
    compliance: 0.1,
    knowledge: 0.3,
  },
  agent_providers: {
    orchestrator: "",
    structural: "",
    writer: "",
    logic_editor: "",
    style_editor: "",
    compliance: "",
    knowledge: "",
  },

  agent_api_bases: {
    orchestrator: "",
    structural: "",
    writer: "",
    logic_editor: "",
    style_editor: "",
    compliance: "",
    knowledge: "",
  },
  agent_api_keys: {
    orchestrator: "",
    structural: "",
    writer: "",
    logic_editor: "",
    style_editor: "",
    compliance: "",
    knowledge: "",
  },
  agent_config_ids: {
    orchestrator: null,
    structural: null,
    writer: null,
    logic_editor: null,
    style_editor: null,
    compliance: null,
    knowledge: null,
  },
  // AI文风消除配置
  ai_elimination_enabled: true,
  ai_elimination_threshold: 50,
});

// ==================== Computed ====================

// 格式化耗时
const formattedDuration = computed(() => {
  const task = writingStore.currentTask;
  if (!task) return "00:00:00";

  const start = task.start_time ? new Date(task.start_time) : null;
  const end = task.end_time ? new Date(task.end_time) : null;

  let ms = 0;
  if (start && end) {
    ms = end - start;
  } else if (start && writingStore.isRunning) {
    ms = Date.now() - start;
  }

  if (ms === 0) return "00:00:00";

  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  return `${hours.toString().padStart(2, "0")}:${(minutes % 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
});

// Agent流水线状态
const agentPipeline = computed(() => {
  const messages = writingStore.progressMessages;
  const pipeline = agentConfigs.map((agent) => {
    // 查找该Agent的最新消息
    const agentMsgs = messages.filter(
      (m) =>
        m.data?.agent_role === agent.role ||
        m.data?.agent_name?.includes(agent.label),
    );
    const latestMsg = agentMsgs[0];

    let status = "waiting";
    let statusLabel = "等待中";
    let statusType = "info";

    if (latestMsg) {
      if (
        latestMsg.type === "agent_complete" ||
        latestMsg.type === "unit_complete"
      ) {
        status = "completed";
        statusLabel = "已完成";
        statusType = "success";
      } else if (latestMsg.type === "agent_error") {
        status = "error";
        statusLabel = "失败";
        statusType = "danger";
      } else if (
        latestMsg.type === "agent_start" ||
        latestMsg.data?.message?.includes("开始")
      ) {
        status = "running";
        statusLabel = "运行中";
        statusType = "primary";
      }
    }

    // 如果任务已完成，所有Agent都标记为完成
    if (writingStore.isCompleted) {
      status = "completed";
      statusLabel = "已完成";
      statusType = "success";
    }

    return {
      ...agent,
      status,
      statusLabel,
      statusType,
    };
  });

  return pipeline;
});

// 当前处理信息
const currentProcessingInfo = computed(() => {
  const current = writingStore.currentUnit;
  if (!current || !writingStore.isRunning) return null;

  const msg = writingStore.progressMessages.find(
    (m) => m.data?.unit_index === current.unit_index,
  );
  if (msg) {
    return `正在处理: ${current.unit_title || `单元 ${current.unit_index}`} - ${msg.data?.message || ""}`;
  }
  return `正在处理: ${current.unit_title || `单元 ${current.unit_index}`}`;
});

// 工作流步骤（从WebSocket消息中提取）
const workflowSteps = computed(() => {
  const steps = [];
  const messages = writingStore.progressMessages;

  // 定义图标映射
  const iconMap = {
    MagicStick: "MagicStick",
    Collection: "Reading",
    DataLine: "DataLine",
    EditPen: "EditPen",
    View: "View",
    Warning: "Warning",
    SetUp: "SetUp",
  };

  // 遍历消息，提取工作流步骤
  for (const msg of messages) {
    // 处理 unit_progress 类型的消息（包含 workflow 信息）
    if (msg.type === "unit_progress" && msg.data?.status) {
      const status = msg.data.status;
      const progress = msg.data.progress || 0;

      // 将单元进度转换为工作流步骤
      let stepMessage = "";
      let stepIcon = "MagicStick";

      switch (status) {
        case "structuring":
          stepMessage = `单元 ${msg.data.unit_index || ""}: 结构拆解中...`;
          stepIcon = "OfficeBuilding";
          break;
        case "writing":
          stepMessage = `单元 ${msg.data.unit_index || ""}: 内容生成中...`;
          stepIcon = "EditPen";
          break;
        case "reviewing":
          stepMessage = `单元 ${msg.data.unit_index || ""}: 审阅润色中...`;
          stepIcon = "View";
          break;
        case "assembling":
          stepMessage = `单元 ${msg.data.unit_index || ""}: 内容组装中...`;
          stepIcon = "SetUp";
          break;
        case "completed":
          stepMessage = `单元 ${msg.data.unit_index || ""}: 处理完成`;
          stepIcon = "CircleCheck";
          break;
        default:
          stepMessage =
            msg.data.message || `单元 ${msg.data.unit_index || ""}: ${status}`;
      }

      // 检查是否已存在相同单元的相同步骤
      const existingStep = steps.find(
        (s) => s.step === `unit_${msg.data.unit_index}_${status}`,
      );
      if (!existingStep) {
        steps.push({
          step: `unit_${msg.data.unit_index}_${status}`,
          status:
            status === "completed"
              ? "done"
              : status === "failed"
                ? "error"
                : "running",
          message: stepMessage,
          icon: stepIcon,
          progress,
        });
      }
    }

    // 处理 scene_progress 类型的消息
    if (msg.type === "scene_progress" && msg.data?.status) {
      const status = msg.data.status;
      const unitIdx = msg.data.unit_index || "";
      const sceneIdx = msg.data.scene_index || "";

      if (status === "writing") {
        steps.push({
          step: `scene_${unitIdx}_${sceneIdx}_writing`,
          status: "running",
          message: `单元 ${unitIdx} 场景 ${sceneIdx}: 内容生成中...`,
          icon: "EditPen",
        });
      } else if (status === "completed" || status === "done") {
        steps.push({
          step: `scene_${unitIdx}_${sceneIdx}_done`,
          status: "done",
          message: `单元 ${unitIdx} 场景 ${sceneIdx}: 生成完成`,
          icon: "CircleCheck",
        });
      } else if (status === "failed") {
        steps.push({
          step: `scene_${unitIdx}_${sceneIdx}_error`,
          status: "error",
          message: `单元 ${unitIdx} 场景 ${sceneIdx}: 生成失败`,
          icon: "CircleClose",
        });
      }
    }

    // 处理 task_progress 类型的消息
    if (msg.type === "task_progress" && msg.data) {
      const completed = msg.data.completed_units || 0;
      const total = msg.data.total_units || 0;
      if (completed > 0) {
        steps.push({
          step: `task_progress_${completed}`,
          status: "done",
          message: `已完成 ${completed}/${total} 单元`,
          icon: "DataLine",
        });
      }
    }
  }

  // 只保留最近的5个步骤
  return steps.slice(-5);
});

// 选中的场景标题
const selectedSceneTitle = computed(() => {
  if (!selectedScene.value) return "";
  const unitIdx = selectedUnit.value?.unit_index || "";
  const sceneIdx = selectedScene.value.scene_index;
  const sceneTitle = selectedScene.value.scene_title || `场景 ${sceneIdx}`;
  return `单元 ${unitIdx} - ${sceneTitle}`;
});

// 显示的单元列表 - 合并 store.units 和 unitSummaries
const displayUnits = computed(() => {
  // 如果有任务，优先使用 store 中的单元列表
  if (writingStore.currentTask && writingStore.units.length > 0) {
    return writingStore.units;
  }

  // 如果没有任务但有 unitSummaries，从 unitSummaries 构建初始列表
  if (unitSummaries.value && Object.keys(unitSummaries.value).length > 0) {
    return Object.entries(unitSummaries.value)
      .map(([index, summary]) => ({
        unit_index: parseInt(index),
        unit_title:
          typeof summary === "string"
            ? summary
            : summary?.title || `第${index}${unitLabel.value}`,
        unit_summary:
          typeof summary === "string" ? null : summary?.summary || null,
        status: "pending",
        word_count: 0,
      }))
      .sort((a, b) => a.unit_index - b.unit_index);
  }

  // 如果没有 unitSummaries 但有 chapters，从 chapters 构建列表
  if (props.chapters && props.chapters.length > 0) {
    return props.chapters
      .map((chapter) => ({
        unit_index: chapter.chapter_number,
        unit_title: chapter.chapter_title,
        unit_summary: null,
        status: "pending",
        word_count: chapter.word_count || 0,
      }))
      .sort((a, b) => a.unit_index - b.unit_index);
  }

  // 如果有 projectTotalUnits，生成占位列表
  if (projectTotalUnits.value > 0) {
    return Array.from({ length: projectTotalUnits.value }, (_, i) => ({
      unit_index: i + 1,
      unit_title: `第${i + 1}${unitLabel.value}`,
      unit_summary: null,
      status: "pending",
      word_count: 0,
    }));
  }

  return [];
});

// 是否有已生成的内容
const hasGeneratedContent = computed(() => {
  // 检查 store 中是否有已完成的单元
  if (writingStore.units && writingStore.units.length > 0) {
    return writingStore.units.some(
      (u) => u.status === "completed" && u.word_count > 0,
    );
  }
  return false;
});

// 是否可以继续生成（任务完成且有更多单元可生成）
const canContinueGenerate = computed(() => {
  if (!writingStore.currentTask || !writingStore.isCompleted) return false;

  // 检查是否还有未生成的单元
  const completedUnits = writingStore.currentTask.completed_units || 0;
  const totalUnits =
    projectTotalUnits.value ||
    Object.keys(unitSummaries.value || {}).length ||
    props.chapters?.length ||
    0;

  return totalUnits > completedUnits;
});

// 架构优化：移除 canGenerateChapterOutlines, chapterOutlineStats, recommendedStartUnit, pendingChaptersList, generatedOutlineList 计算属性

// ==================== Methods ====================

// 测试Agent连接
async function handleTestConnection(agentRole) {
  const modelId = taskForm.value.agent_models[agentRole];
  const provider = taskForm.value.agent_providers[agentRole];

  if (!modelId || !provider) {
    ElMessage.warning("请先填写模型ID和供应商");
    return;
  }

  testingAgent.value[agentRole] = true;
  try {
    const config = {
      model_id: modelId,
      provider: provider,
      api_base: taskForm.value.agent_api_bases[agentRole] || undefined,
      api_key: taskForm.value.agent_api_keys[agentRole] || undefined,
    };
    const res = await writingStore.testConnection(config);
    if (res?.success) {
      ElMessage.success("连接成功！");
    } else {
      ElMessage.error(res?.message || "连接失败");
    }
  } catch (error) {
    ElMessage.error("测试连接失败: " + (error.message || "未知错误"));
  } finally {
    testingAgent.value[agentRole] = false;
  }
}

// 架构优化：移除 handleModeChange 函数，generation_mode 固定为 "direct"

// 创建任务
async function handleCreateTask() {
  // 校验配置完整性
  const configurableAgentsList = agentConfigs.filter((a) => a.configurable);
  const unconfigured = configurableAgentsList.filter((a) => {
    const configId = taskForm.value.agent_config_ids[a.role];
    if (configId && configId !== "custom") return false; // 使用预配置，算已配置
    if (configId === "custom") {
      return (
        !taskForm.value.agent_models[a.role] ||
        !taskForm.value.agent_providers[a.role]
      );
    }
    return true; // 未选择任何配置
  });
  if (unconfigured.length > 0) {
    ElMessage.warning(
      `请先配置以下Agent的模型: ${unconfigured.map((a) => a.label).join("、")}`,
    );
    return;
  }

  // ===== 新增：验证并获取正确的项目总单元数 =====
  // 使用计算属性 projectTotalUnits（会从API加载的数据中获取 total_chapters）
  let actualTotalUnits = projectTotalUnits.value;

  // 如果计算属性为0或无效，从 unitSummaries 或 chapters 计算
  if (!actualTotalUnits || actualTotalUnits <= 0) {
    if (unitSummaries.value && Object.keys(unitSummaries.value).length > 0) {
      actualTotalUnits = Object.keys(unitSummaries.value).length;
    } else if (props.chapters && props.chapters.length > 0) {
      actualTotalUnits = props.chapters.length;
    }
  }

  // 验证起始单元
  const startFrom = taskForm.value.start_from || 1;
  if (startFrom > actualTotalUnits) {
    ElMessage.warning(
      `起始单元 ${startFrom} 超出范围（总单元数: ${actualTotalUnits}）`,
    );
    return;
  }

  // 计算有效的 unit_count
  let effectiveUnitCount = taskForm.value.unit_count;
  const availableUnits = actualTotalUnits - startFrom + 1;

  if (!effectiveUnitCount || effectiveUnitCount > availableUnits) {
    effectiveUnitCount = availableUnits;
  }

  console.log(
    `[创建任务] 实际总单元数: ${actualTotalUnits}, 起始: ${startFrom}, 生成数量: ${effectiveUnitCount}`,
  );
  // ===== 单元数校验结束 =====

  // 构建Agent配置（仅包含可配置且有值的Agent）
  const agentsConfig = {};

  // 遍历所有可配置的Agent
  for (const agent of configurableAgentsList) {
    const configId = taskForm.value.agent_config_ids[agent.role];

    if (configId && configId !== "custom") {
      // 使用预配置模型
      agentsConfig[agent.role] = {
        config_id: configId, // 传预配置ID给后端
        temperature: taskForm.value.agent_temps[agent.role] ?? 0.7,
      };
    } else {
      // 自定义配置（保持原有逻辑）
      agentsConfig[agent.role] = {
        model: taskForm.value.agent_models[agent.role] || "",
        provider: taskForm.value.agent_providers[agent.role] || "",
        temperature: taskForm.value.agent_temps[agent.role] ?? 0.7,
        api_base: taskForm.value.agent_api_bases[agent.role] || undefined,
        api_key: taskForm.value.agent_api_keys[agent.role] || undefined,
      };
    }
  }

  const task = await writingStore.createTask(projectId.value, {
    start_from: startFrom,
    unit_count: effectiveUnitCount || null,
    config: {
      words_per_chapter: taskForm.value.words_per_chapter,
      concurrency: taskForm.value.concurrency,
      generation_mode: "direct",  // 架构优化：固定使用direct模式
      agents: agentsConfig,
      agent_api_bases: taskForm.value.agent_api_bases,
      agent_api_keys: taskForm.value.agent_api_keys,
    },
  });
  if (task) {
    // 清空表单
    taskForm.value.start_from = 1;
    taskForm.value.unit_count = null;
  }
}

// 中断任务
async function handleInterrupt() {
  try {
    interrupting.value = true;
    await writingStore.interruptTask(writingStore.currentTask.id);
  } finally {
    interrupting.value = false;
  }
}

// 续传任务
async function handleResume() {
  await writingStore.resumeTask(writingStore.currentTask.id);
}

// 继续生成任务
async function handleContinue() {
  if (!continueUnitCount.value || continueUnitCount.value < 1) {
    ElMessage.warning("请输入有效的生成数量");
    return;
  }

  try {
    showContinueDialog.value = false;
    await writingStore.continueTask(
      writingStore.currentTask.id,
      continueUnitCount.value,
    );
    ElMessage.success(`已开始继续生成 ${continueUnitCount.value} 个单元`);
  } catch (error) {
    console.error("继续生成失败:", error);
    ElMessage.error("继续生成失败: " + (error.message || "未知错误"));
  }
}

// 架构优化：移除 handleGenerateChapterOutlines, connectChapterOutlineEvents, handleInterruptChapterOutlines, handleContinueFromBreakpoint 函数

// 大纲文件选择处理
function handleOutlineFileChange(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    outlineInput.value = e.target.result;
  };
  reader.readAsText(file.raw);
}

// 上传大纲
async function handleUploadOutline() {
  if (!outlineInput.value.trim()) {
    ElMessage.warning("请输入大纲内容");
    return;
  }

  uploadingOutline.value = true;
  try {
    const res = await novelWriterApi.updateProject(projectId.value, {
      outline_content: outlineInput.value,
    });

    if (res.success) {
      ElMessage.success("大纲上传成功");
      showOutlineUploadDialog.value = false;
      outlineInput.value = "";
      emit("refresh");
    } else {
      ElMessage.error(res.message || "上传失败");
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "上传失败");
  } finally {
    uploadingOutline.value = false;
  }
}

// 生成目录
async function handleGenerateDirectory() {
  generatingDirectory.value = true;
  try {
    // 调用API生成目录
    const res = await novelWriterApi.generateDirectory(projectId.value, {
      total_chapters: projectTotalUnits.value || 10,
      chapter_naming_style: "数字编号",
      generate_names: true,
    });
    if (res.success) {
      ElMessage.success("目录生成成功");
      emit("refresh");
    } else {
      ElMessage.error(res.message || "目录生成失败");
    }
  } catch (error) {
    ElMessage.error("目录生成失败");
  } finally {
    generatingDirectory.value = false;
  }
}

// 构建知识库
async function handleBuildKnowledgeBase() {
  try {
    const res = await novelWriterApi.buildKnowledgeBase(projectId.value);
    if (res.success) {
      ElMessage.success("知识库构建任务已启动");
    } else {
      ElMessage.error(res.message || "构建失败");
    }
  } catch (error) {
    ElMessage.error("知识库构建失败");
  }
}

// 获取内容类型标签
function getContentTypeLabel(type) {
  const labels = {
    novel: "小说",
    series_script: "连续剧剧本",
    movie_script: "电影剧本",
  };
  return labels[type] || "小说";
}

// 获取内容类型标签样式
function getContentTypeTagType(type) {
  const types = {
    novel: "primary",
    series_script: "success",
    movie_script: "warning",
  };
  return types[type] || "primary";
}

// ==================== 风格文档相关方法 ====================

// 加载风格文档信息
async function loadStyleDocumentInfo() {
  if (!projectId.value) return;
  
  try {
    const res = await novelWriterApi.getStyleDocument(projectId.value);
    if (res.success) {
      styleDocumentInfo.value = res.data;
      aiEliminationEnabled.value = res.data.ai_elimination_enabled ?? true;
      aiEliminationThreshold.value = res.data.ai_elimination_threshold ?? 50;
    }
  } catch (error) {
    console.error('加载风格文档信息失败:', error);
  }
}

// 刷新风格文档信息
async function handleRefreshStyleDocument() {
  await loadStyleDocumentInfo();
  ElMessage.success('风格文档数据已刷新');
}

// 风格文档上传前校验
function beforeStyleUpload(file) {
  const allowedTypes = ['.txt', '.docx', '.pdf'];
  const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  
  if (!allowedTypes.includes(fileExt)) {
    ElMessage.warning('仅支持 .txt, .docx, .pdf 格式的文件');
    return false;
  }
  
  const maxSize = 10 * 1024 * 1024; // 10MB
  if (file.size > maxSize) {
    ElMessage.warning('文件大小不能超过10MB');
    return false;
  }
  
  return true;
}

// 风格文档上传成功
function handleStyleUploadSuccess(response) {
  if (response.success) {
    ElMessage.success('风格文档上传成功，正在分析中...');
    loadStyleDocumentInfo();
  } else {
    ElMessage.error(response.message || '上传失败');
  }
}

// 风格文档上传失败
function handleStyleUploadError(error) {
  console.error('风格文档上传失败:', error);
  ElMessage.error('风格文档上传失败');
}

// 删除风格文档
async function handleDeleteStyleDocument() {
  try {
    await ElMessageBox.confirm('确定要删除风格文档吗？删除后AI将无法模仿该文档的写作风格。', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    
    const res = await novelWriterApi.deleteStyleDocument(projectId.value);
    if (res.success) {
      ElMessage.success('风格文档已删除');
      styleDocumentInfo.value = null;
    } else {
      ElMessage.error(res.message || '删除失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败');
    }
  }
}

// AI文风消除开关变更
async function handleAiEliminationChange(value) {
  try {
    await novelWriterApi.updateStyleDocumentSettings(projectId.value, {
      ai_elimination_enabled: value
    });
    ElMessage.success(value ? '已启用AI文风消除' : '已关闭AI文风消除');
  } catch (error) {
    ElMessage.error('设置保存失败');
    aiEliminationEnabled.value = !value;
  }
}

// 消除强度变更
async function handleThresholdChange(value) {
  try {
    await novelWriterApi.updateStyleDocumentSettings(projectId.value, {
      ai_elimination_threshold: value
    });
  } catch (error) {
    console.error('保存消除强度失败:', error);
  }
}

// 生成任务AI文风消除开关变更
function handleTaskAiEliminationChange(value) {
  // 同步到项目设置
  if (styleDocumentInfo.value) {
    handleAiEliminationChange(value);
  }
}

// 处理单元概述文件选择
function handleUnitSummariesFileChange(file) {
  unitSummariesFileList.value = [file.raw];
}

// 超出文件数量限制处理
function handleUploadExceed(files) {
  ElMessage.warning("只能上传一个文件，请先移除当前文件");
}

// 取消上传
function handleCancelUnitSummariesUpload() {
  showUnitSummariesUploadDialog.value = false;
  unitSummariesFileList.value = [];
}

// 上传单元概述文件
async function handleUploadUnitSummariesFile() {
  if (unitSummariesFileList.value.length === 0) {
    ElMessage.warning("请选择要上传的文件");
    return;
  }

  uploadingUnitSummaries.value = true;
  try {
    const formData = new FormData();
    formData.append("file", unitSummariesFileList.value[0]);

    const res = await novelWriterApi.uploadUnitSummariesFile(
      projectId.value,
      formData,
    );
    if (res.success) {
      ElMessage.success(res.data?.message || "单元概述上传成功");
      showUnitSummariesUploadDialog.value = false;
      unitSummariesFileList.value = [];
      // 刷新本地项目数据
      await loadProjectData();
      console.log("[单元概述上传] 刷新后项目数据:", {
        unit_summaries: localProjectData.value?.unit_summaries,
        hasUnitSummaries: hasUnitSummaries.value,
      });
      // 通知父组件刷新数据
      emit("refresh");
    } else {
      ElMessage.error(res.data?.message || "上传失败");
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "上传失败");
  } finally {
    uploadingUnitSummaries.value = false;
  }
}

// 删除任务
async function handleDelete() {
  try {
    await ElMessageBox.confirm(
      "确定要删除此任务吗？删除后将清除所有进度数据。",
      "确认删除",
      { type: "warning" },
    );
    await writingStore.deleteTask(writingStore.currentTask.id);
  } catch (error) {
    if (error !== "cancel") {
      console.error("删除任务失败:", error);
    }
  }
}

// 导出任务内容
async function handleExport() {
  try {
    const taskId = writingStore.currentTask?.id;
    if (!taskId) return;

    const response = await writingTaskApi.exportTask(taskId, "txt");
    const blob = new Blob([response.data || response], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `writing_task_${taskId}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    ElMessage.success("下载成功");
  } catch (error) {
    console.error("导出失败:", error);
    ElMessage.error("导出失败: " + (error.message || "未知错误"));
  }
}

// 处理单元展开
async function handleUnitExpand(unit) {
  // 如果已经加载过，不再重复加载
  if (writingStore.scenes[unit.unit_index]) return;

  loadingScenes.value[unit.unit_index] = true;
  await writingStore.fetchScenes(writingStore.currentTask.id, unit.unit_index);
  loadingScenes.value[unit.unit_index] = false;
}

// 获取场景列表
function getScenes(unitIndex) {
  return writingStore.scenes[unitIndex] || [];
}

// 导出单个单元内容
async function handleExportUnit(unitIndex) {
  try {
    const taskId = writingStore.currentTask?.id;
    if (!taskId) {
      ElMessage.warning("没有正在进行的任务");
      return;
    }

    const response = await writingTaskApi.exportUnit(taskId, unitIndex, "txt");
    const blob = new Blob([response.data || response], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;

    // 从单元列表获取单元标题
    const unit = displayUnits.value.find((u) => u.unit_index === unitIndex);
    const unitTitle = unit?.unit_title || `第${unitIndex}${unitLabel.value}`;
    a.download = `${unitTitle}.txt`;

    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    ElMessage.success("下载成功");
  } catch (error) {
    console.error("导出单元失败:", error);
    ElMessage.error("导出失败: " + (error.message || "未知错误"));
  }
}

// 处理场景点击
function handleSceneClick(scene, unit) {
  selectedScene.value = scene;
  selectedUnit.value = unit;
  sceneDialogVisible.value = true;
}

// 获取消息标签类型
function getMessageTagType(msg) {
  const agentRole = msg.data?.agent_role;
  if (!agentRole) return "info";

  const typeMap = {
    structural: "primary",
    writer: "success",
    logic_editor: "warning",
    style_editor: "",
    compliance: "danger",
    assembler: "info",
  };
  return typeMap[agentRole] || "info";
}

// 获取Agent标签
function getAgentLabel(role) {
  // 优先使用 AGENT_ROLE_LABELS 映射
  if (AGENT_ROLE_LABELS[role]) {
    return AGENT_ROLE_LABELS[role].replace("Agent", "");
  }
  // 其次在 agentConfigs 中查找
  const agent = agentConfigs.find((a) => a.role === role);
  return agent?.label || role;
}

// 获取Agent标签类型
function getAgentTagType(agentName) {
  const typeMap = {
    结构师: "primary",
    写手: "success",
    逻辑编辑: "warning",
    风格润色: "",
    合规审查: "danger",
    合成: "info",
  };
  return typeMap[agentName] || "info";
}

// 可配置的Agent列表（过滤掉assembler等不需要配置的）
const configurableAgents = computed(() => {
  return agentConfigs.filter((agent) => agent.configurable !== false);
});

// 加载可用Provider列表
const loadProviders = async () => {
  loadingProviders.value = true;
  try {
    const res = await writingTaskApi.getAvailableProviders();
    // 后端返回格式: { data: { providers: [...] }, message: "..." }
    availableProviders.value =
      res.data?.data?.providers || res.data?.providers || [];
  } catch (error) {
    console.error("加载Provider列表失败:", error);
    // 使用默认列表作为降级
    availableProviders.value = [
      {
        name: "qianwen",
        display_name: "通义千问 (阿里云百炼)",
        api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
        is_preset: true,
        models: [],
      },
      {
        name: "doubao",
        display_name: "豆包 (字节跳动/火山引擎)",
        api_base: "https://ark.cn-beijing.volces.com/api/v3",
        is_preset: true,
        models: [],
      },
      {
        name: "siliconflow",
        display_name: "硅基流动 (SiliconFlow)",
        api_base: "https://api.siliconflow.cn/v1",
        is_preset: true,
        models: [],
      },
      {
        name: "openrouter",
        display_name: "OpenRouter",
        api_base: "https://openrouter.ai/api/v1",
        is_preset: true,
        models: [],
      },
      {
        name: "t8star",
        display_name: "贞贞AI工坊",
        api_base: "https://ai.t8star.cn/v1",
        is_preset: true,
        models: [],
      },
      {
        name: "custom",
        display_name: "自定义服务商",
        api_base: "",
        is_preset: false,
        models: [],
      },
    ];
  } finally {
    loadingProviders.value = false;
  }
};

// 加载预配置模型列表
const loadModelConfigs = async () => {
  loadingConfigs.value = true;
  try {
    const res = await writingTaskApi.getModelConfigs();
    // 后端返回格式: { data: [...配置列表], message: "..." }
    modelConfigs.value = res.data?.data || res.data || [];
  } catch (error) {
    console.error("加载模型配置失败:", error);
    modelConfigs.value = [];
  } finally {
    loadingConfigs.value = false;
  }
};

// 模型配置选择变更
const onModelConfigChange = (role, configId) => {
  if (configId === "custom") {
    // 清空预配置关联，让用户手动输入
    return;
  }
  const config = modelConfigs.value.find((c) => c.id === configId);
  if (config) {
    // 自动填充provider/model/api_base（api_key由后端通过config_id获取）
    taskForm.value.agent_providers[role] = config.provider;
    taskForm.value.agent_models[role] = config.model_id;
    taskForm.value.agent_api_bases[role] = config.api_base || "";
    taskForm.value.agent_api_keys[role] = ""; // 使用预配置的key，不需要前端传
  }
};

// 一键应用同一模型到所有Agent
const applyToAllAgents = (configId) => {
  const configurableRoles = agentConfigs
    .filter((a) => a.configurable)
    .map((a) => a.role);
  for (const role of configurableRoles) {
    taskForm.value.agent_config_ids[role] = configId;
    onModelConfigChange(role, configId);
  }
  ElMessage.success("已应用到所有Agent");
};

// 快速应用模型配置（对话框中使用）
const handleQuickApply = () => {
  if (!quickApplyConfigId.value) return;
  applyToAllAgents(quickApplyConfigId.value);
};

// 架构优化：移除章节大纲相关方法 isChapterOutlineGenerated, handleViewChapterOutline, handleEditChapterOutline

// 点击单元项
function handleUnitItemClick(unit) {
  // 设置为起始单元
  taskForm.value.start_from = unit.unit_index;
}

// 获取Agent图标
const getAgentIcon = (role) => {
  const iconMap = {
    orchestrator: "Connection",
    structural: "OfficeBuilding",
    writer: "EditPen",
    logic_editor: "View",
    style_editor: "MagicStick",
    compliance: "Warning",
    knowledge: "Reading",
    assembler: "SetUp",
  };
  return iconMap[role] || "Setting";
};

// Provider变更时，自动填充api_base
const onProviderChange = (role, providerName) => {
  const provider = availableProviders.value.find(
    (p) => p.name === providerName,
  );
  if (provider && provider.api_base) {
    taskForm.value.agent_api_bases[role] = provider.api_base;
  } else {
    taskForm.value.agent_api_bases[role] = "";
  }
  // 清空model选择
  taskForm.value.agent_models[role] = "";
};

// 获取指定provider的模型列表（用于下拉建议）
const getProviderModels = (role) => {
  const providerName = taskForm.value.agent_providers[role];
  const provider = availableProviders.value.find(
    (p) => p.name === providerName,
  );
  return provider?.models || [];
};

// 获取单元状态类型
function getUnitStatusType(status) {
  const typeMap = {
    pending: "info",
    processing: "primary",
    completed: "success",
    failed: "danger",
  };
  return typeMap[status] || "info";
}

// 获取单元状态标签
function getUnitStatusLabel(status) {
  const labelMap = {
    pending: "等待中",
    processing: "处理中",
    completed: "已完成",
    failed: "失败",
  };
  return labelMap[status] || status;
}

// 获取场景状态类型
function getSceneStatusType(status) {
  const typeMap = {
    pending: "info",
    writing: "primary",
    reviewing: "warning",
    completed: "success",
    failed: "danger",
  };
  return typeMap[status] || "info";
}

// 获取场景状态标签
function getSceneStatusLabel(status) {
  const labelMap = {
    pending: "等待中",
    writing: "写作中",
    reviewing: "审阅中",
    completed: "已完成",
    failed: "失败",
  };
  return labelMap[status] || status;
}

// 格式化数字
function formatNumber(num) {
  if (!num) return "0";
  return num.toLocaleString();
}

// 格式化时间
function formatTime(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// 计算效率
function calculateEfficiency() {
  const tokens =
    writingStore.stats?._summary?.total_tokens ||
    writingStore.stats?.total_tokens ||
    0;
  const task = writingStore.currentTask;
  if (!task) return "0";

  const start = task.start_time ? new Date(task.start_time) : null;
  const end = task.end_time ? new Date(task.end_time) : null;

  let ms = 0;
  if (start && end) {
    ms = end - start;
  } else if (start && writingStore.isRunning) {
    ms = Date.now() - start;
  }

  const durationSec = ms / 1000;
  if (durationSec === 0) return "0";
  return (tokens / durationSec).toFixed(1);
}

// 获取状态类型（用于el-tag）
function getStatusType(status) {
  const typeMap = {
    pending: "info",
    running: "primary",
    interrupted: "warning",
    completed: "success",
    failed: "danger",
  };
  return typeMap[status] || "info";
}

// 获取状态标签
function getStatusLabel(status) {
  const labelMap = {
    pending: "等待中",
    running: "运行中",
    interrupted: "已中断",
    completed: "已完成",
    failed: "失败",
  };
  return labelMap[status] || status;
}

// ==================== Lifecycle ====================

onMounted(async () => {
  // 加载项目数据（如果是路由组件）
  if (!props.projectId && route.params.id) {
    await loadProjectData();
  }
  // 加载预配置模型列表
  await loadModelConfigs();
  // 加载可用Provider列表
  await loadProviders();
  // 加载当前任务
  await writingStore.fetchCurrentTask(projectId.value);
  // 加载风格文档信息
  await loadStyleDocumentInfo();
});

onUnmounted(() => {
  // 断开WebSocket连接
  writingStore.disconnectWebSocket();
});

// 监听项目ID变化（路由切换时）
watch(
  () => route.params.id,
  async (newId) => {
    if (newId && !props.projectId) {
      await loadProjectData();
      await writingStore.fetchCurrentTask(projectId.value);
      // 切换项目时重新加载风格文档信息
      await loadStyleDocumentInfo();
    }
  },
);

// 监听进度消息，自动滚动
watch(
  () => writingStore.progressMessages.length,
  () => {
    nextTick(() => {
      if (messagesListRef.value) {
        messagesListRef.value.scrollTop = 0;
      }
    });
  },
);
</script>

<style lang="scss" scoped>
.writing-workbench {
  padding: 20px;
  min-height: 600px;
}

// 顶部状态栏
.workbench-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);

  // 项目标题区域
  .project-title-section {
    display: flex;
    align-items: center;
    gap: 12px;

    .project-title {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
  }

  .task-status-section {
    display: flex;
    align-items: center;
    gap: 20px;
    flex: 1;

    .progress-wrapper {
      flex: 1;
      max-width: 300px;

      .progress-text {
        display: block;
        margin-top: 4px;
        font-size: 12px;
        color: #606266;
        text-align: center;
      }
    }

    .quick-stats {
      display: flex;
      gap: 16px;

      .stat-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: #606266;

        .el-icon {
          font-size: 14px;
          color: #409eff;
        }
      }
    }
  }

  .task-actions {
    display: flex;
    gap: 10px;
  }

  // 单元概览区（无任务时显示）
  .unit-overview-section {
    display: flex;
    align-items: center;
    gap: 16px;
    flex: 1;

    .overview-hint {
      font-size: 13px;
      color: #909399;
    }
  }
}

// 任务创建面板
.task-creation {
  // 工作台布局
  .workbench-layout {
    display: flex;
    gap: 20px;
    min-height: 600px;
  }

  // 左侧边栏
  .left-sidebar {
    width: 350px;
    flex-shrink: 0;
    min-width: 300px;
    position: sticky;
    top: 20px;
    max-height: calc(100vh - 40px);
    overflow-y: auto;
  }

  // 右侧主区域
  .right-main-area {
    flex: 1;
    min-width: 0;
  }

  // 参数配置卡片样式
  .params-card {
    margin-bottom: 16px;

    .params-row {
      display: flex;
      align-items: center;
      gap: 24px;
      flex-wrap: wrap;

      .param-item {
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

      .param-actions {
        margin-left: auto;
        display: flex;
        gap: 8px;
      }
    }
  }

  // 单元输入包装器
  .unit-input-wrapper {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;

    .unit-name-display {
      flex-shrink: 0;
      padding: 4px 10px;
      background: #f0f9eb;
      border-radius: 4px;
      font-size: 13px;
      color: #67c23a;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 200px;
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

    .agent-config-list {
      .agent-config-item {
        padding: 16px;
        background: #f5f7fa;
        border-radius: 8px;
        margin-bottom: 12px;

        .agent-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;

          .agent-name {
            font-weight: 600;
            font-size: 14px;
          }
        }
      }
    }

    .slider-hint {
      font-size: 12px;
      color: #909399;
      margin-top: 4px;
    }

    .form-hint {
      font-size: 12px;
      color: #909399;
      margin-left: 8px;
    }

    .form-actions {
      margin-top: 30px;
      text-align: center;

      .start-btn {
        min-width: 160px;
        height: 44px;
        font-size: 16px;
      }
    }
  }
}

// 单元参数配置区样式（新增）
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

// 单元操作按钮区样式（保留兼容）
.unit-actions-bar {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 12px;
}

// 单元预览列表样式
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

// 主内容区
.workbench-main {
  .progress-panel {
    height: 100%;
    min-height: 500px;

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .el-icon {
        margin-right: 4px;
      }
    }

    .agent-pipeline {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 20px 0;
      gap: 16px;
      flex-wrap: wrap;

      .pipeline-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        padding: 12px 20px;
        border-radius: 8px;
        background: #f5f7fa;
        transition: all 0.3s;

        &.running {
          background: #ecf5ff;
          box-shadow: 0 0 0 2px #409eff;
        }

        &.completed {
          background: #f0f9eb;
        }

        &.error {
          background: #fef0f0;
        }

        .pipeline-icon {
          position: relative;
          display: flex;
          align-items: center;

          .el-icon {
            font-size: 24px;
            color: #606266;
          }

          .pipeline-arrow {
            position: absolute;
            right: -28px;
            top: 50%;
            transform: translateY(-50%);
            color: #c0c4cc;
          }
        }

        .pipeline-info {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;

          .pipeline-name {
            font-size: 13px;
            font-weight: 500;
          }
        }
      }
    }

    .current-processing {
      margin: 16px 0;
      padding: 12px 16px;
      background: #ecf5ff;
      border-radius: 8px;
      border-left: 4px solid #409eff;

      .processing-info {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #409eff;
        font-size: 14px;

        .el-icon {
          font-size: 16px;
        }
      }
    }

    .progress-messages {
      .messages-list {
        max-height: 300px;
        overflow-y: auto;
        padding-right: 8px;

        .progress-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 12px;
          border-bottom: 1px solid #ebeef5;
          font-size: 13px;

          &:hover {
            background: #f5f7fa;
          }

          .msg-agent {
            flex-shrink: 0;
            min-width: 60px;
            text-align: center;
          }

          .msg-content {
            flex: 1;
            color: #303133;
            word-break: break-all;
          }

          .msg-time {
            flex-shrink: 0;
            color: #909399;
            font-size: 12px;
          }
        }
      }
    }
  }

  .units-panel {
    height: 100%;
    min-height: 500px;

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .el-icon {
        margin-right: 4px;
      }

      .panel-header-actions {
        display: flex;
        align-items: center;
        gap: 10px;
      }
    }

    .units-collapse {
      .unit-title {
        display: flex;
        align-items: center;
        gap: 10px;
        flex: 1;
        padding-right: 16px;

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
        }

        .unit-word-count {
          font-size: 12px;
          color: #909399;
        }
      }

      .scenes-list {
        padding: 8px 0;

        .scene-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 12px;
          margin-bottom: 8px;
          background: #f5f7fa;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;

          &:hover {
            background: #ecf5ff;
          }

          .scene-info {
            display: flex;
            flex-direction: column;
            gap: 2px;

            .scene-index {
              font-size: 12px;
              color: #909399;
            }

            .scene-title {
              font-size: 13px;
              color: #303133;
            }
          }

          .scene-meta {
            display: flex;
            align-items: center;
            gap: 8px;

            .scene-word-count {
              font-size: 12px;
              color: #909399;
            }
          }
        }
      }
    }
  }

  .stats-dashboard {
    margin-top: 20px;

    .panel-header {
      display: flex;
      align-items: center;

      .el-icon {
        margin-right: 4px;
      }
    }

    .stat-card {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      border-radius: 8px;
      background: #f5f7fa;

      &.total {
        background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
        .stat-icon {
          color: #409eff;
        }
      }

      &.cost {
        background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
        .stat-icon {
          color: #67c23a;
        }
      }

      &.time {
        background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
        .stat-icon {
          color: #e6a23c;
        }
      }

      &.efficiency {
        background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
        .stat-icon {
          color: #f56c6c;
        }
      }

      .stat-icon {
        font-size: 32px;
      }

      .stat-info {
        .stat-value {
          font-size: 20px;
          font-weight: 600;
          color: #303133;
        }

        .stat-label {
          font-size: 12px;
          color: #909399;
          margin-top: 2px;
        }
      }
    }
  }
}

// 场景对话框
.scene-dialog {
  .scene-content {
    .scene-meta-info {
      display: flex;
      gap: 16px;
      align-items: center;
      margin-bottom: 12px;

      span {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: #606266;

        .el-icon {
          color: #409eff;
        }
      }
    }

    .content-body {
      max-height: 500px;
      overflow-y: auto;
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;

      pre {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
        font-family: inherit;
        font-size: 14px;
        line-height: 1.8;
        color: #303133;
      }
    }
  }
}

// Agent配置对话框
.agent-config-dialog {
  .agent-dialog-content {
    .concurrency-section {
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;
      margin-bottom: 16px;

      .section-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 15px;
        font-weight: 600;
        color: #303133;
        margin-bottom: 12px;
      }

      .concurrency-config {
        .config-item {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .config-label {
          font-size: 14px;
          color: #606266;
          white-space: nowrap;
        }

        .config-hint {
          margin-top: 8px;
          font-size: 12px;
          color: #909399;
        }
      }
    }

    .quick-apply-section {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      background: #f5f7fa;
      border-radius: 8px;
      margin-bottom: 16px;

      .section-label {
        font-size: 14px;
        color: #606266;
        white-space: nowrap;
      }
    }

    .agent-list {
      max-height: 500px;
      overflow-y: auto;

      .agent-item {
        padding: 12px 16px;
        background: #fafafa;
        border-radius: 8px;
        margin-bottom: 12px;
        transition: all 0.2s;

        &:hover {
          background: #f0f9eb;
        }

        .agent-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 10px;

          .agent-name {
            font-size: 14px;
            font-weight: 600;
            color: #303133;
          }

          .info-icon {
            color: #909399;
            cursor: help;
          }
        }

        .agent-config-row {
          display: flex;
          align-items: center;
          gap: 16px;

          .temp-slider {
            display: flex;
            align-items: center;
            gap: 8px;

            .temp-label {
              font-size: 12px;
              color: #909399;
            }

            .temp-value {
              font-size: 12px;
              color: #409eff;
              min-width: 24px;
            }
          }
        }
      }
    }
  }
}

// 响应式
@media (max-width: 1200px) {
  .workbench-main {
    .el-col {
      width: 100%;
      margin-bottom: 20px;
    }
  }
}

@media (max-width: 768px) {
  .workbench-header {
    flex-direction: column;
    gap: 12px;

    .task-status-section {
      flex-direction: column;
      width: 100%;

      .progress-wrapper {
        max-width: 100%;
        width: 100%;
      }
    }
  }

  .agent-pipeline {
    .pipeline-item {
      .pipeline-arrow {
        display: none;
      }
    }
  }
}

// 单元概述缺失提示样式
.unit-summaries-alert {
  margin-bottom: 16px;

  .alert-content {
    p {
      margin: 0;
      line-height: 1.6;
    }
  }
}

// 单元概述上传对话框样式
.unit-summaries-upload-dialog {
  .el-alert {
    p {
      margin: 4px 0;
      line-height: 1.5;
    }

    code {
      font-family: "Courier New", monospace;
      font-size: 12px;
    }
  }

  .el-textarea {
    font-family: "Courier New", Consolas, monospace;
  }
}

// 项目设置弹窗中的模型配置入口样式
.settings-model-config {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;

  .config-info {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #606266;

    .el-icon {
      font-size: 18px;
      color: #409eff;
    }
  }
}

// 单元大纲生成面板样式
.chapter-outline-card {
  margin-bottom: 16px;

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

// 已生成大纲列表对话框样式
.outline-list-dialog {
  .outline-list-content {
    .list-stats {
      display: flex;
      gap: 40px;
      justify-content: center;
      margin-bottom: 20px;
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;
    }
  }
}

// 章节大纲预览对话框样式
.chapter-outline-dialog {
  .chapter-outline-content {
    max-height: 60vh;
    overflow-y: auto;
  }

  .outline-header {
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid #ebeef5;

    .chapter-title {
      margin: 0 0 8px 0;
      font-size: 18px;
      color: #303133;
    }

    .chapter-meta {
      display: flex;
      align-items: center;
      gap: 12px;

      .update-time {
        font-size: 12px;
        color: #909399;
      }
    }
  }

  .outline-section {
    margin-bottom: 16px;

    .section-label {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 8px;
      padding-left: 8px;
      border-left: 3px solid #409eff;
    }

    .section-content {
      font-size: 14px;
      color: #606266;
      line-height: 1.8;
      margin: 0;
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 4px;
    }

    .detailed-outline {
      white-space: pre-wrap;
    }

    .key-events-list {
      margin: 0;
      padding: 0 0 0 20px;

      li {
        font-size: 14px;
        color: #606266;
        line-height: 2;
        position: relative;

        &::marker {
          color: #409eff;
        }
      }
    }
  }
}

// 风格设置区域样式
.style-settings-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 0 4px;
  
  .style-document-section,
  .ai-elimination-section {
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      
      .section-title {
        font-size: 14px;
        font-weight: 500;
        color: #303133;
      }
    }
  }
  
  .style-document-content {
    .uploaded-document {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      background: rgba(103, 194, 58, 0.08);
      border-radius: 8px;
      border: 1px solid rgba(103, 194, 58, 0.2);
      
      .document-info {
        display: flex;
        align-items: center;
        gap: 8px;
        
        .el-icon {
          font-size: 20px;
          color: #67c23a;
        }
        
        .document-name {
          font-size: 14px;
          color: #606266;
        }
      }
      
      .document-actions {
        display: flex;
        gap: 8px;
      }
    }
    
    .upload-section {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
  }
  
  .elimination-config {
    margin-top: 12px;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 8px;
    
    .threshold-setting {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 8px;
      
      .threshold-label {
        font-size: 13px;
        color: #606266;
        min-width: 70px;
      }
      
      .el-slider {
        flex: 1;
      }
    }
  }
}

// 风格文档详情弹窗样式
.style-detail-content {
  .detail-section {
    margin-bottom: 20px;
    
    h4 {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 12px;
      padding-left: 8px;
      border-left: 3px solid #409eff;
    }
    
    .profile-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      
      .profile-item {
        padding: 10px 12px;
        background: #f5f7fa;
        border-radius: 6px;
        
        .item-label {
          display: block;
          font-size: 12px;
          color: #909399;
          margin-bottom: 4px;
        }
        
        .item-value {
          font-size: 13px;
          color: #606266;
        }
      }
    }
    
    .imitation-points,
    .avoid-patterns {
      margin: 0;
      padding: 0 0 0 20px;
      
      li {
        font-size: 13px;
        color: #606266;
        line-height: 1.8;
        margin-bottom: 6px;
      }
    }
    
    .avoid-patterns li {
      color: #f56c6c;
    }
    
    .style-guide {
      font-size: 13px;
      color: #606266;
      line-height: 1.8;
      padding: 12px 16px;
      background: #f5f7fa;
      border-radius: 8px;
      margin: 0;
    }
    
    .no-data-tip {
      padding: 20px;
      text-align: center;
      background: #fafafa;
      border-radius: 8px;
    }
  }
}

// 空状态样式
.empty-state {
  padding: 40px 0;
  text-align: center;
}

// AI文风消除配置样式
.ai-elimination-config {
  margin-top: 16px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #f0f9eb 0%, #fff 100%);
  border-radius: 8px;
  border: 1px solid rgba(103, 194, 58, 0.2);
  
  .config-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    
    .header-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 14px;
      font-weight: 500;
      color: #303133;
      
      .el-icon {
        color: #67c23a;
      }
    }
  }
  
  .config-content {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px dashed #e4e7ed;
    
    .threshold-row {
      display: flex;
      align-items: center;
      margin-bottom: 8px;
      
      .threshold-label {
        font-size: 13px;
        color: #606266;
        min-width: 70px;
      }
      
      .threshold-value {
        font-size: 13px;
        font-weight: 500;
        color: #67c23a;
        min-width: 40px;
        text-align: right;
      }
    }
  }
}
</style>
