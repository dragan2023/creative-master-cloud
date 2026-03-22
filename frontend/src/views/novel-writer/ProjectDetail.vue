<template>
  <div class="project-detail-page" v-loading="loading">
    <!-- 统一的任务状态提示条 - 始终固定在页面顶部 -->
    <div v-show="taskStore.hasTask" class="task-status-bar" :class="{ 'is-running': taskStore.isRunning }">
      <div class="task-info">
        <el-icon class="is-loading" v-if="taskStore.isRunning"><Refresh /></el-icon>
        <el-icon v-else><Finished /></el-icon>
        <span class="task-type">{{ taskStore.taskTypeLabel }}</span>
        <span class="task-progress">
          进度: {{ taskStore.progress?.completed || 0 }} / {{ taskStore.progress?.total || 0 }}
          <template v-if="taskStore.currentItemName">
            ({{ taskStore.currentItemName }})
          </template>
        </span>
        <!-- 当前步骤信息 -->
        <div v-if="taskStore.currentStep && taskStore.isRunning" class="current-step">
          <el-icon :class="{ 'is-loading': taskStore.currentStep.status === 'running' }">
            <component :is="getStepIcon(taskStore.currentStep.icon)" />
          </el-icon>
          <span class="step-message" :class="{ 'step-error': taskStore.currentStep.status === 'error', 'step-done': taskStore.currentStep.status === 'done' }">
            {{ taskStore.currentStep.message }}
          </span>
        </div>
      </div>
      <div class="task-actions">
        <!-- 步骤历史按钮 -->
        <el-popover
          v-if="taskStore.stepsHistory.length > 0"
          placement="bottom"
          :width="400"
          trigger="click"
        >
          <template #reference>
            <el-button size="small" text>
              <el-icon><List /></el-icon>
              步骤详情
            </el-button>
          </template>
          <div class="steps-history">
            <div class="steps-title">执行步骤历史</div>
            <div 
              v-for="(step, index) in getDisplaySteps" 
              :key="index" 
              class="step-item"
              :class="{ 'step-running': step.status === 'running', 'step-done': step.status === 'done', 'step-error': step.status === 'error' }"
            >
              <el-icon :size="16">
                <component :is="getStepIcon(step.icon)" />
              </el-icon>
              <span class="step-text">{{ step.message }}</span>
              <span v-if="step.duration_ms" class="step-duration">{{ formatDuration(step.duration_ms) }}</span>
              <el-tag v-if="step.status === 'running'" type="warning" size="small">进行中</el-tag>
              <el-tag v-else-if="step.status === 'done'" type="success" size="small">完成</el-tag>
              <el-tag v-else-if="step.status === 'error'" type="danger" size="small">失败</el-tag>
            </div>
          </div>
        </el-popover>
        <el-button type="danger" size="small" @click="handleCancelTask">
          <el-icon><VideoPause /></el-icon>
          终止生成
        </el-button>
      </div>
    </div>

    <div class="page-header">
      <div class="header-left">
        <el-button link @click="router.back()">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h1 class="project-title">{{ project?.title }}</h1>
        <el-tag :type="getTypeTagType(project?.content_type)" size="small">
          {{ getTypeLabel(project?.content_type) }}
        </el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="showSettingsDialog">
          <el-icon><Setting /></el-icon>
          设置
        </el-button>
        <el-button type="primary" @click="showExportDialog">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
        <!-- 一键清空下拉菜单 -->
        <el-dropdown trigger="click">
          <el-button type="warning" plain>
            <el-icon><DeleteFilled /></el-icon>
            清空
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleSyncContentStatus">
                <el-icon><Refresh /></el-icon>
                同步正文状态
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleClearAllOutlines">
                <el-icon><DocumentDelete /></el-icon>
                清空所有大纲
              </el-dropdown-item>
              <el-dropdown-item @click="handleClearAllContent">
                <el-icon><Delete /></el-icon>
                清空所有正文
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleClearAll">
                <el-icon><DeleteFilled /></el-icon>
                清空全部（大纲+正文）
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="danger" plain @click="handleDelete">
          <el-icon><Delete /></el-icon>
          删除项目
        </el-button>
      </div>
    </div>

    <!-- 项目信息卡片 -->
    <el-row :gutter="16" v-if="project">
      <el-col :span="14">
        <el-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>{{ unitLabel }}列表</span>
              <div class="header-actions">
                <el-button size="small" @click="showOutlineUpload" v-if="!project.outline_content">
                  上传大纲
                </el-button>
              </div>
            </div>
          </template>

          <!-- 大纲上传区域 -->
          <div v-if="!project.outline_content" class="outline-upload-area">
            <el-upload
              drag
              :show-file-list="false"
              :http-request="handleOutlineUpload"
              accept=".txt,.md,.doc,.docx"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                拖拽大纲文件到此处，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 .txt, .md, .doc, .docx 格式
                </div>
              </template>
            </el-upload>
          </div>

          <!-- 已有大纲时显示大纲信息和更换按钮 -->
          <div v-else-if="!chapters.length" class="outline-info">
            <div class="outline-status">
              <el-icon color="#67c23a"><CircleCheckFilled /></el-icon>
              <span>大纲已上传</span>
              <el-text type="info" size="small" style="margin-left: 12px;">
                {{ (project.outline_content || '').replace(/\s/g, '').length }} 字
              </el-text>
            </div>
            <el-upload
              :show-file-list="false"
              :http-request="handleOutlineUpload"
              accept=".txt,.md,.doc,.docx"
            >
              <el-button size="small" type="primary" plain>
                <el-icon><Upload /></el-icon>
                更换大纲
              </el-button>
            </el-upload>
          </div>

          <!-- 大纲已上传但无章节时，显示章节设置区域 -->
          <div v-if="project.outline_content && !chapters.length" class="chapter-setup-area">
            <el-divider content-position="left">{{ unitLabel }}设置</el-divider>
            <div class="setup-content">
              <div class="setup-info">
                <el-icon color="##E6A23C"><WarningFilled /></el-icon>
                <span v-if="project.total_chapters > 0">
                  已识别到 <strong>{{ project.total_chapters }}</strong> 个{{ unitLabel }}
                </span>
                <span v-else>
                  未能自动识别{{ unitLabel }}，请手动设置数量
                </span>
              </div>
              <div class="setup-actions">
                <el-input-number
                  v-model="manualUnitCount"
                  :min="1"
                  :max="200"
                  :step="1"
                  placeholder="数量"
                  style="width: 120px;"
                />
                <el-button
                  type="primary"
                  size="small"
                  @click="handleGenerateDirectory"
                  :loading="generatingDirectory"
                >
                  {{ chapters.length > 0 ? '重新生成目录' : `生成${unitLabel}目录` }}
                </el-button>
              </div>
            </div>
          </div>

          <!-- 单元概述上传区域（大纲已上传后显示） -->
          <div v-if="project.outline_content && !project.unit_summaries" class="unit-summaries-upload-area">
            <el-divider content-position="left">单元概述</el-divider>
            <div class="unit-summaries-info">
              <div class="info-text">
                <el-icon color="#E6A23C"><InfoFilled /></el-icon>
                <span>单元概述用于指导详细大纲生成，可从创意生成板块导出后上传</span>
              </div>
              <el-button size="small" type="primary" @click="showUnitSummariesUploadDialog = true">
                <el-icon><Upload /></el-icon>
                上传单元概述
              </el-button>
            </div>
          </div>

          <!-- 已有单元概述时显示信息 -->
          <div v-if="project.unit_summaries && Object.keys(project.unit_summaries).length > 0" class="unit-summaries-info-area">
            <el-divider content-position="left">单元概述</el-divider>
            <div class="unit-summaries-status">
              <div class="status-info">
                <el-icon color="#67c23a"><CircleCheckFilled /></el-icon>
                <span>已上传单元概述：<strong>{{ Object.keys(project.unit_summaries).length }}</strong> 个</span>
              </div>
              <el-button size="small" type="primary" plain @click="showUnitSummariesUploadDialog = true">
                <el-icon><Upload /></el-icon>
                更换单元概述
              </el-button>
            </div>
          </div>

          <!-- 分集详细大纲生成区域（仅剧集类型项目显示） -->
          <div 
            v-if="project.outline_content && project.content_type === 'series_script' && chapters.length > 0" 
            class="episode-outline-area"
          >
            <el-divider content-position="left">分集详细大纲</el-divider>
            <div class="episode-outline-info">
              <div class="outline-stats">
                <el-icon color="#409EFC"><Document /></el-icon>
                <span>已生成分集大纲：<strong>{{ generatedEpisodeCount }}</strong> / {{ totalEpisodeCount }} 集</span>
              </div>
              <div class='outline-actions'>
                <el-button
                  v-if='generatedEpisodeCount > 0'
                  size='small'
                  plain
                  @click='downloadAllEpisodeOutlines'
                >
                  <el-icon><Download /></el-icon>
                  下载全部大纲
                </el-button>
                <el-button
                  type='primary'
                  size='small'
                  @click='handleGenerateAllEpisodeOutlines()'
                  :loading='generatingEpisodeOutlines'
                  :disabled='totalEpisodeCount === 0 || taskStore.isRunning'
                >
                  <el-icon><MagicStick /></el-icon>
                  {{ generatingEpisodeOutlines ? '生成中...' : '一键生成全部分集大纲' }}
                </el-button>
                <el-button
                  size='small'
                  @click='openBatchCountDialog("outline", "episode")'
                  :disabled='totalEpisodeCount === 0 || taskStore.isRunning'
                >
                  生成指定数量
                </el-button>
              </div>
            </div>
            
            <!-- 分集大纲列表 -->
            <div class="episode-outline-list" v-if="episodeOutlines.length > 0">
              <div 
                v-for="outline in episodeOutlines" 
                :key="outline.episode_number"
                class="episode-outline-item"
                :class="{ 
                  'has-outline': outline.has_detailed, 
                  'has-content': outline.content_status === 'generated',
                  'is-generating': taskStore.isRunning && taskStore.currentTask?.task_type === 'episode_outline' && taskStore.progress?.current === outline.episode_number,
                  'is-completed': taskStore.currentTask?.task_type === 'episode_outline' && taskStore.progress?.completed >= outline.episode_number && !outline.has_detailed
                }"
              >
                <!-- 左侧：剧集信息 -->
                <div class="outline-left">
                  <span class='episode-num'>第{{ outline.episode_number }}集</span>
                  <span 
                    v-if='editingEpisodeTitle !== outline.episode_number'
                    class='episode-title editable'
                    @click.stop='startEditEpisodeTitle(outline)'
                    title='点击编辑集标题'
                  >
                    {{ outline.episode_title || '未命名' }}
                  </span>
                  <el-input
                    v-else
                    v-model='editEpisodeTitleValue'
                    size='small'
                    style='width: 150px;'
                    @click.stop
                    @keyup.enter='saveEpisodeTitle(outline)'
                    @keyup.escape='cancelEditEpisodeTitle'
                    @blur='saveEpisodeTitle(outline)'
                  />
                </div>
                
                <!-- 右侧：状态和操作 -->
                <div class="outline-right">
                  <!-- 状态标签行 -->
                  <div class="status-tags">
                    <!-- 生成中状态标签 -->
                    <el-tag 
                      v-if="taskStore.isRunning && taskStore.currentTask?.task_type === 'episode_outline' && taskStore.progress?.current === outline.episode_number" 
                      type="warning" 
                      size="small"
                      class="generating-tag"
                    >
                      <el-icon class="is-loading"><Refresh /></el-icon>
                      生成中...
                    </el-tag>
                    <!-- 大纲状态标签 -->
                    <el-tag v-else :type="outline.has_detailed ? 'success' : 'info'" size="small">
                      {{ outline.has_detailed ? '已生成详细大纲' : '仅基础概要' }}
                    </el-tag>
                    <!-- 正文生成状态标签 -->
                    <el-tag v-if="outline.content_status === 'generated'" type="warning" size="small">
                      正文已生成
                    </el-tag>
                  </div>
                  
                  <!-- 操作按钮行 -->
                  <div class="action-buttons">
                    <el-button
                      v-if='!outline.has_detailed'
                      size='small'
                      text
                      type='primary'
                      @click='handleGenerateSingleEpisodeOutline(outline.episode_number)'
                      :loading='generatingSingleEpisode === outline.episode_number'
                    >
                      生成大纲
                    </el-button>
                    <template v-else>
                      <el-button size='small' text type='primary' @click='showEpisodeOutlineDetail(outline)'>
                        查看
                      </el-button>
                      <el-button size='small' text type='success' @click='downloadEpisodeOutline(outline)'>
                        下载
                      </el-button>
                      <el-button 
                        size='small' 
                        :type="outline.content_status === 'generated' ? 'info' : 'warning'" 
                        text 
                        @click='generateEpisodeContent(outline)'
                        :loading='generating && selectedEpisode === outline.episode_number'
                      >
                        {{ outline.content_status === 'generated' ? '重生成正文' : '生成正文' }}
                      </el-button>
                      <el-button 
                        v-if='generating && selectedEpisode === outline.episode_number'
                        size='small' 
                        type='danger' 
                        text 
                        @click='handleStopGeneration'
                      >
                        终止
                      </el-button>
                      <!-- 删除按钮 -->
                      <el-popconfirm
                        v-if="outline.content_status === 'generated'"
                        title="确定要删除该集正文吗？（大纲将保留）"
                        @confirm='handleDeleteEpisodeContent(outline)'
                        confirm-button-text="删除"
                        cancel-button-text="取消"
                      >
                        <template #reference>
                          <el-button size='small' text type='danger'>
                            删除正文
                          </el-button>
                        </template>
                      </el-popconfirm>
                      <el-popconfirm
                        title="确定要删除该集详细大纲吗？"
                        @confirm='handleDeleteEpisodeOutline(outline)'
                        confirm-button-text="删除"
                        cancel-button-text="取消"
                      >
                        <template #reference>
                          <el-button size='small' text type='danger'>
                            删除大纲
                          </el-button>
                        </template>
                      </el-popconfirm>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 章节详细大纲生成区域（仅小说类型项目显示） -->
          <div 
            v-if="project.outline_content && project.content_type === 'novel' && chapters.length > 0" 
            class="chapter-outline-area"
          >
            <el-divider content-position="left">章节详细大纲</el-divider>
            <div class="chapter-outline-info">
              <div class="outline-stats">
                <el-icon color="#409EFC"><Document /></el-icon>
                <span>已生成章节大纲：<strong>{{ generatedChapterOutlineCount }}</strong> / {{ totalChapterOutlineCount }} 章</span>
              </div>
              <div class='outline-actions'>
                <el-button
                  v-if='generatedChapterOutlineCount > 0'
                  size='small'
                  plain
                  @click='downloadAllChapterOutlines'
                >
                  <el-icon><Download /></el-icon>
                  下载全部大纲
                </el-button>
                <el-button
                  type='primary'
                  size='small'
                  @click='handleGenerateAllChapterOutlines()'
                  :loading='generatingChapterOutlines'
                  :disabled='totalChapterOutlineCount === 0 || taskStore.isRunning'
                >
                  <el-icon><MagicStick /></el-icon>
                  {{ generatingChapterOutlines ? '生成中...' : '一键生成全部章节大纲' }}
                </el-button>
                <el-button
                  size='small'
                  @click='openBatchCountDialog("outline", "chapter")'
                  :disabled='totalChapterOutlineCount === 0 || taskStore.isRunning'
                >
                  生成指定数量
                </el-button>
              </div>
            </div>
            
            <!-- 章节大纲列表 -->
            <div class="chapter-outline-list" v-if="chapterOutlines.length > 0">
              <div 
                v-for="outline in chapterOutlines" 
                :key="outline.chapter_number"
                class="chapter-outline-item"
                :class="{ 
                  'has-outline': outline.has_detailed, 
                  'has-content': outline.content_status === 'generated',
                  'is-generating': taskStore.isRunning && taskStore.currentTask?.task_type === 'chapter_outline' && taskStore.progress?.current === outline.chapter_number,
                  'is-completed': taskStore.currentTask?.task_type === 'chapter_outline' && taskStore.progress?.completed >= outline.chapter_number && !outline.has_detailed
                }"
              >
                <!-- 左侧：章节信息 -->
                <div class="outline-left">
                  <span class='chapter-num'>第{{ outline.chapter_number }}章</span>
                  <span 
                    v-if='editingChapterOutlineTitle !== outline.chapter_number'
                    class='chapter-title-text editable'
                    @click.stop='startEditChapterOutlineTitle(outline)'
                    title='点击编辑章节标题'
                  >
                    {{ outline.chapter_title || '未命名' }}
                  </span>
                  <el-input
                    v-else
                    v-model='editChapterOutlineTitleValue'
                    size='small'
                    style='width: 150px;'
                    @click.stop
                    @keyup.enter='saveChapterOutlineTitle(outline)'
                    @keyup.escape='cancelEditChapterOutlineTitle'
                    @blur='saveChapterOutlineTitle(outline)'
                  />
                </div>
                
                <!-- 右侧：状态和操作 -->
                <div class="outline-right">
                  <!-- 状态标签行 -->
                  <div class="status-tags">
                    <!-- 生成中状态标签 -->
                    <el-tag 
                      v-if="taskStore.isRunning && taskStore.currentTask?.task_type === 'chapter_outline' && taskStore.progress?.current === outline.chapter_number" 
                      type="warning" 
                      size="small"
                      class="generating-tag"
                    >
                      <el-icon class="is-loading"><Refresh /></el-icon>
                      生成中...
                    </el-tag>
                    <!-- 大纲状态标签 -->
                    <el-tag v-else :type="outline.has_detailed ? 'success' : 'info'" size="small">
                      {{ outline.has_detailed ? '已生成详细大纲' : '仅基础概要' }}
                    </el-tag>
                    <!-- 正文生成状态标签 -->
                    <el-tag v-if="outline.content_status === 'generated'" type="warning" size="small">
                      正文已生成
                    </el-tag>
                  </div>
                  
                  <!-- 操作按钮行 -->
                  <div class="action-buttons">
                    <el-button
                      v-if='!outline.has_detailed'
                      size='small'
                      text
                      type='primary'
                      @click='handleGenerateSingleChapterOutline(outline.chapter_number)'
                      :loading='generatingSingleChapterOutline === outline.chapter_number'
                    >
                      生成大纲
                    </el-button>
                    <template v-else>
                      <el-button size='small' text type='primary' @click='showChapterOutlineDetail(outline)'>
                        查看
                      </el-button>
                      <el-button size='small' text type='success' @click='downloadChapterOutline(outline)'>
                        下载
                      </el-button>
                      <el-button 
                        size='small' 
                        text 
                        type='primary'
                        @click='handleGenerateSingleChapterOutline(outline.chapter_number, true)'
                        :loading='generatingSingleChapterOutline === outline.chapter_number'
                      >
                        重生成大纲
                      </el-button>
                      <el-button 
                        size='small' 
                        :type="outline.content_status === 'generated' ? 'info' : 'warning'" 
                        text 
                        @click='generateChapterContent(outline)'
                        :loading='generating && selectedChapter === outline.chapter_number'
                      >
                        {{ outline.content_status === 'generated' ? '重生成正文' : '生成正文' }}
                      </el-button>
                      <el-button 
                        v-if='generating && selectedChapter === outline.chapter_number'
                        size='small' 
                        type='danger' 
                        text 
                        @click='handleStopGeneration'
                      >
                        终止
                      </el-button>
                      <!-- 删除按钮 -->
                      <el-popconfirm
                        v-if="outline.content_status === 'generated'"
                        title="确定要删除该章节正文吗？（大纲将保留）"
                        @confirm='handleDeleteChapterContent(outline)'
                        confirm-button-text="删除"
                        cancel-button-text="取消"
                      >
                        <template #reference>
                          <el-button size='small' text type='danger'>
                            删除正文
                          </el-button>
                        </template>
                      </el-popconfirm>
                      <el-popconfirm
                        title="确定要删除该章节详细大纲吗？"
                        @confirm='handleDeleteChapterOutline(outline)'
                        confirm-button-text="删除"
                        cancel-button-text="取消"
                      >
                        <template #reference>
                          <el-button size='small' text type='danger'>
                            删除大纲
                          </el-button>
                        </template>
                      </el-popconfirm>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 场景详细大纲生成区域（仅电影剧本类型项目显示） -->
          <div 
            v-if="project.outline_content && project.content_type === 'movie_script' && chapters.length > 0" 
            class="scene-outline-area"
          >
            <el-divider content-position="left">场景详细大纲</el-divider>
            <div class="scene-outline-info">
              <div class="outline-stats">
                <el-icon color="#409EFC"><Document /></el-icon>
                <span>已生成场景大纲：<strong>{{ generatedSceneOutlineCount }}</strong> / {{ totalSceneOutlineCount }} 场</span>
              </div>
              <div class='outline-actions'>
                <el-button
                  v-if='generatedSceneOutlineCount > 0'
                  size='small'
                  plain
                  @click='downloadAllSceneOutlines'
                >
                  <el-icon><Download /></el-icon>
                  下载全部大纲
                </el-button>
                <el-button
                  type='primary'
                  size='small'
                  @click='handleGenerateAllSceneOutlines()'
                  :loading='generatingSceneOutlines'
                  :disabled='totalSceneOutlineCount === 0 || taskStore.isRunning'
                >
                  <el-icon><MagicStick /></el-icon>
                  {{ generatingSceneOutlines ? '生成中...' : '一键生成全部场景大纲' }}
                </el-button>
                <el-button
                  size='small'
                  @click='openBatchCountDialog("outline", "scene")'
                  :disabled='totalSceneOutlineCount === 0 || taskStore.isRunning'
                >
                  生成指定数量
                </el-button>
              </div>
            </div>
            
            <!-- 场景大纲列表 -->
            <div class="scene-outline-list" v-if="sceneOutlines.length > 0">
              <div 
                v-for="outline in sceneOutlines" 
                :key="outline.scene_number"
                class="scene-outline-item"
                :class="{ 
                  'has-outline': outline.has_detailed, 
                  'has-content': outline.content_status === 'generated',
                  'is-generating': taskStore.isRunning && taskStore.currentTask?.task_type === 'scene_outline' && taskStore.progress?.current === outline.scene_number,
                  'is-completed': taskStore.currentTask?.task_type === 'scene_outline' && taskStore.progress?.completed >= outline.scene_number && !outline.has_detailed
                }"
              >
                <!-- 左侧：场景信息 -->
                <div class="outline-left">
                  <span class='scene-num'>第{{ outline.scene_number }}场</span>
                  <span 
                    v-if='editingSceneOutlineTitle !== outline.scene_number'
                    class='scene-title-text editable'
                    @click.stop='startEditSceneOutlineTitle(outline)'
                    title='点击编辑场景标题'
                  >
                    {{ outline.scene_title || outline.location || '未命名' }}
                  </span>
                  <el-input
                    v-else
                    v-model='editSceneOutlineTitleValue'
                    size='small'
                    style='width: 150px;'
                    @click.stop
                    @keyup.enter='saveSceneOutlineTitle(outline)'
                    @keyup.escape='cancelEditSceneOutlineTitle'
                    @blur='saveSceneOutlineTitle(outline)'
                  />
                </div>
                
                <!-- 右侧：状态和操作 -->
                <div class="outline-right">
                  <!-- 状态标签行 -->
                  <div class="status-tags">
                    <!-- 生成中状态标签 -->
                    <el-tag 
                      v-if="taskStore.isRunning && taskStore.currentTask?.task_type === 'scene_outline' && taskStore.progress?.current === outline.scene_number" 
                      type="warning" 
                      size="small"
                      class="generating-tag"
                    >
                      <el-icon class="is-loading"><Refresh /></el-icon>
                      生成中...
                    </el-tag>
                    <!-- 大纲状态标签 -->
                    <el-tag v-else :type="outline.has_detailed ? 'success' : 'info'" size="small">
                      {{ outline.has_detailed ? '已生成详细大纲' : '仅基础概要' }}
                    </el-tag>
                    <!-- 正文生成状态标签 -->
                    <el-tag v-if="outline.content_status === 'generated'" type="warning" size="small">
                      正文已生成
                    </el-tag>
                  </div>
                  
                  <!-- 操作按钮行 -->
                  <div class="action-buttons">
                    <el-button
                      v-if='!outline.has_detailed'
                      size='small'
                      text
                      type='primary'
                      @click='handleGenerateSingleSceneOutline(outline.scene_number)'
                      :loading='generatingSingleSceneOutline === outline.scene_number'
                    >
                      生成大纲
                    </el-button>
                    <template v-else>
                      <el-button size='small' text type='primary' @click='showSceneOutlineDetail(outline)'>
                        查看
                      </el-button>
                      <el-button size='small' text type='success' @click='downloadSceneOutline(outline)'>
                        下载
                      </el-button>
                      <el-button 
                        size='small' 
                        :type="outline.content_status === 'generated' ? 'info' : 'warning'" 
                        text 
                        @click='generateSceneContent(outline)'
                        :loading='generating && selectedScene === outline.scene_number'
                      >
                        {{ outline.content_status === 'generated' ? '重生成正文' : '生成正文' }}
                      </el-button>
                      <el-button 
                        v-if='generating && selectedScene === outline.scene_number'
                        size='small' 
                        type='danger' 
                        text 
                        @click='handleStopGeneration'
                      >
                        终止
                      </el-button>
                      <!-- 删除按钮 -->
                      <el-popconfirm
                        v-if="outline.content_status === 'generated'"
                        title="确定要删除该场景正文吗？（大纲将保留）"
                        @confirm='handleDeleteSceneContent(outline)'
                        confirm-button-text="删除"
                        cancel-button-text="取消"
                      >
                        <template #reference>
                          <el-button size='small' text type='danger'>
                            删除正文
                          </el-button>
                        </template>
                      </el-popconfirm>
                      <el-popconfirm
                        title="确定要删除该场景详细大纲吗？"
                        @confirm='handleDeleteSceneOutline(outline)'
                        confirm-button-text="删除"
                        cancel-button-text="取消"
                      >
                        <template #reference>
                          <el-button size='small' text type='danger'>
                            删除大纲
                          </el-button>
                        </template>
                      </el-popconfirm>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 章节列表（有大纲且有章节时显示） -->
          <div v-if="chapters.length > 0" class="chapter-list">
            <!-- 章节名称操作区 -->
            <div class="chapter-actions-bar" v-if="chapters.length > 0">
              <div class="action-buttons">
                <el-button
                  size="small"
                  type="warning"
                  plain
                  @click="handleRegenerateDirectory"
                  :loading="generatingDirectory"
                >
                  <el-icon><Refresh /></el-icon>
                  重新生成目录
                </el-button>
                <el-button
                  size="small"
                  @click="handleRegenerateNames"
                  :loading="regeneratingNames"
                >
                  <el-icon><MagicStick /></el-icon>
                  重新生成名称
                </el-button>
                <!-- 正文操作按钮（根据内容类型显示） -->
                <el-button v-if='project.content_type === "series_script" && episodeOutlines.length > 0' type='success' size='small' @click='handleGenerateAllEpisodeContent()' :loading='generatingAllContent && batchContentType === "episode"'>
                  <el-icon><MagicStick /></el-icon>
                  一键生成全部分集正文
                </el-button>
                <el-button v-if='project.content_type === "series_script" && episodeOutlines.length > 0' size='small' @click='openBatchCountDialog("content", "episode")' :disabled='taskStore.isRunning'>
                  生成指定数量
                </el-button>
                <el-button v-if='project.content_type === "series_script" && episodeOutlines.length > 0' size='small' plain type='success' @click='downloadAllEpisodeContent'>
                  <el-icon><Download /></el-icon>
                  下载全部正文
                </el-button>
                <el-button v-if='project.content_type === "novel" && chapterOutlines.length > 0' type='success' size='small' @click='handleGenerateAllChapterContent()' :loading='generatingAllContent && batchContentType === "chapter"'>
                  <el-icon><MagicStick /></el-icon>
                  一键生成全部章节正文
                </el-button>
                <el-button v-if='project.content_type === "novel" && chapterOutlines.length > 0' size='small' @click='openBatchCountDialog("content", "chapter")' :disabled='taskStore.isRunning'>
                  生成指定数量
                </el-button>
                <el-button v-if='project.content_type === "novel" && chapterOutlines.length > 0' size='small' plain type='success' @click='downloadAllChapterContent'>
                  <el-icon><Download /></el-icon>
                  下载全部正文
                </el-button>
                <el-button v-if='project.content_type === "movie_script" && sceneOutlines.length > 0' type='success' size='small' @click='handleGenerateAllSceneContent()' :loading='generatingAllContent && batchContentType === "scene"'>
                  <el-icon><MagicStick /></el-icon>
                  一键生成全部场景正文
                </el-button>
                <el-button v-if='project.content_type === "movie_script" && sceneOutlines.length > 0' size='small' @click='openBatchCountDialog("content", "scene")' :disabled='taskStore.isRunning'>
                  生成指定数量
                </el-button>
                <el-button v-if='project.content_type === "movie_script" && sceneOutlines.length > 0' size='small' plain type='success' @click='downloadAllSceneContent'>
                  <el-icon><Download /></el-icon>
                  下载全部正文
                </el-button>
              </div>
              <el-text type="info" size="small">点击章节标题可编辑</el-text>
            </div>

            <div
              v-for="chapter in chapters"
              :key="chapter.id"
              class="chapter-item"
              :class="{ 
                active: selectedChapter?.chapter_number === chapter.chapter_number,
                'has-compliance-issue': chapter.chapter_metadata?.compliance_marking?.has_issues
              }"
              @click="selectChapter(chapter)"
            >
              <div class="chapter-info">
                <span class="chapter-number">第{{ chapter.chapter_number }}{{ unitLabel }}</span>
                <span
                  class="chapter-title editable"
                  @click.stop="startEditTitle(chapter)"
                  v-if="editingChapter !== chapter.chapter_number"
                  :title="'点击编辑'"
                >
                  {{ cleanChapterTitle(chapter.chapter_title) }}
                </span>
                <el-input
                  v-else
                  ref="editTitleInput"
                  v-model="editTitleValue"
                  size="small"
                  style="width: 150px;"
                  @click.stop
                  @keyup.enter.stop="handleEnterSaveTitle(chapter)"
                  @keyup.escape="cancelEditTitle"
                  @blur="handleBlurSaveTitle(chapter)"
                />
              </div>
              <div class="chapter-status">
                <el-tag :type="getChapterStatusType(chapter.status)" size="small">
                  {{ getChapterStatusText(chapter.status) }}
                </el-tag>
                <!-- 合规问题标记 - 更加明显 -->
                <el-tooltip 
                  v-if="chapter.chapter_metadata?.compliance_marking?.has_issues" 
                  :content="`发现${chapter.chapter_metadata.compliance_marking.issue_count}处潜在合规问题，点击查看详情`"
                  placement="top"
                >
                  <el-tag 
                    type="danger" 
                    size="small" 
                    class="compliance-tag has-issues"
                    effect="dark"
                    @click.stop="showComplianceDetail(chapter)"
                  >
                    <el-icon><WarningFilled /></el-icon>
                    合规问题 {{ chapter.chapter_metadata.compliance_marking.issue_count }}
                  </el-tag>
                </el-tooltip>
                <span class="word-count" v-if="chapter.word_count">
                  {{ chapter.word_count }}字
                </span>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 章节内容预览 -->
        <el-card class="content-card" v-if="selectedChapter">
          <template #header>
            <div class="card-header">
              <span>第{{ selectedChapter.chapter_number }}{{ unitLabel }} {{ selectedChapter.chapter_title }}</span>
              <div class="header-actions">
                <!-- 修正历史按钮 -->
                <el-button 
                  v-if="chapterRevisionInfo" 
                  size="small" 
                  plain
                  type="success"
                  @click="showRevisionCompareDialog"
                >
                  <el-icon><DataAnalysis /></el-icon>
                  修正对比
                </el-button>
                <el-dropdown v-if="chapterContent" @command="handleDownloadChapter" style="margin-right: 8px;">
                  <el-button size="small">
                    <el-icon><Download /></el-icon>
                    下载
                    <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="txt">下载为 TXT</el-dropdown-item>
                      <el-dropdown-item command="md">下载为 Markdown</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button size="small" @click="generateSingleChapter" :loading="generatingChapter">
                  {{ selectedChapter.status === 'completed' ? '重新生成' : '生成内容' }}
                </el-button>
              </div>
            </div>
          </template>

          <!-- 修正信息提示 -->
          <el-alert
            v-if="chapterRevisionInfo"
            type="success"
            :closable="false"
            show-icon
            style="margin-bottom: 12px;"
          >
            <template #title>
              <span>已应用知识库修正</span>
              <span style="margin-left: 12px; font-size: 12px; color: #909399;">
                原文 {{ chapterRevisionInfo.original_length }} 字 → 修正后 {{ chapterRevisionInfo.revised_length }} 字
              </span>
            </template>
          </el-alert>

          <!-- 合规审核提示 -->
          <el-alert
            v-if="chapterComplianceMarking?.has_issues"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 12px;"
          >
            <template #title>
              <span>合规审核：发现 {{ chapterComplianceMarking.issue_count }} 处潜在问题</span>
              <el-button 
                size="small" 
                text 
                type="primary" 
                style="margin-left: 12px;"
                @click="showComplianceDetail(selectedChapter)"
              >
                查看详情
              </el-button>
            </template>
          </el-alert>

          <div class="chapter-content" v-if="chapterContent">
            <el-input
              v-model="chapterContent"
              type="textarea"
              :rows="28"
              placeholder="内容"
              @blur="saveChapterContent"
            />
          </div>
          <el-empty v-else description="暂无内容，点击生成按钮开始生成" />
        </el-card>
      </el-col>

      <el-col :span="10">
        <!-- 项目状态卡片 -->
        <el-card class="status-card compact-card">
          <template #header>
            <span>项目状态</span>
          </template>

          <div class="status-grid">
            <div class="status-item-compact">
              <span class="label">状态</span>
              <el-tag :type="getStatusType(project.status)" size="small">
                {{ getStatusText(project.status) }}
              </el-tag>
            </div>
            <div class="status-item-compact">
              <span class="label">进度</span>
              <el-progress
                :percentage="project.progress_percentage"
                :status="project.status === 'completed' ? 'success' : null"
                :stroke-width="8"
              />
            </div>
            <div class="status-item-compact">
              <span class="label">{{ unitLabel }}数</span>
              <span class="value">{{ project.completed_chapters }}/{{ project.total_chapters }}</span>
            </div>
            <div class="status-item-compact">
              <span class="label">总字数</span>
              <span class="value">{{ totalWords }}</span>
            </div>
          </div>
        </el-card>

        <!-- 生成配置卡片 -->
        <el-card class="config-card compact-card">
          <template #header>
            <span>生成配置</span>
          </template>

          <!-- 小说配置显示 -->
          <template v-if="project?.content_type === 'novel'">
            <div class="config-item" v-if="project.novel_config?.target_platform">
              <span class="label">投放平台</span>
              <span class="value">{{ project.novel_config.target_platform }}</span>
            </div>
            <div class="config-item">
              <span class="label">每章字数</span>
              <span class="value">{{ project.novel_config?.words_per_chapter || project.generation_config?.words_per_chapter || 3000 }}字</span>
            </div>
            <div class="config-item" v-if="project.novel_config?.narrative_perspective">
              <span class="label">叙事视角</span>
              <span class="value">{{ project.novel_config.narrative_perspective }}</span>
            </div>
            <div class="config-item" v-if="project.novel_config?.tone">
              <span class="label">基调风格</span>
              <span class="value">{{ project.novel_config.tone }}</span>
            </div>
          </template>

          <!-- 剧集剧本配置显示 -->
          <template v-else-if="project?.content_type === 'series_script'">
            <div class="config-item">
              <span class="label">剧集类型</span>
              <span class="value">{{ project.series_script_config?.series_type || '电视剧' }}</span>
            </div>
            <div class="config-item">
              <span class="label">总集数</span>
              <span class="value">{{ project.series_script_config?.episode_count || '-' }}</span>
            </div>
            <div class="config-item">
              <span class="label">每集时长</span>
              <span class="value">{{ project.series_script_config?.episode_duration_range?.join('-') || '30-45' }}分钟</span>
            </div>
            <div class="config-item">
              <span class="label">剧本格式</span>
              <span class="value">{{ project.series_script_config?.format_standard || '标准格式' }}</span>
            </div>
            <div class="config-item">
              <span class="label">对白比例</span>
              <span class="value">{{ project.series_script_config?.dialogue_narration_ratio || '均衡' }}</span>
            </div>
            <div class="config-item" v-if="project.series_script_config?.target_broadcast">
              <span class="label">投放平台</span>
              <span class="value">{{ project.series_script_config.target_broadcast }}</span>
            </div>
          </template>

          <!-- 电影剧本配置显示 -->
          <template v-else-if="project?.content_type === 'movie_script'">
            <div class="config-item">
              <span class="label">电影类型</span>
              <span class="value">{{ project.movie_script_config?.movie_type || '院线电影' }}</span>
            </div>
            <div class="config-item">
              <span class="label">电影时长</span>
              <span class="value">{{ project.movie_script_config?.total_duration || 90 }}分钟</span>
            </div>
            <div class="config-item">
              <span class="label">剧本格式</span>
              <span class="value">{{ project.movie_script_config?.format_standard || '标准格式' }}</span>
            </div>
            <div class="config-item">
              <span class="label">对白比例</span>
              <span class="value">{{ project.movie_script_config?.dialogue_narration_ratio || '均衡' }}</span>
            </div>
            <div class="config-item" v-if="project.movie_script_config?.target_platform">
              <span class="label">投放平台</span>
              <span class="value">{{ project.movie_script_config.target_platform }}</span>
            </div>
          </template>

          <!-- 兼容旧版剧本配置显示 -->
          <template v-else-if="project?.project_type === 'script'">
            <div class="config-item">
              <span class="label">剧集类型</span>
              <span class="value">{{ project.script_config?.series_type || '电视剧' }}</span>
            </div>
            <div class="config-item">
              <span class="label">每集时长</span>
              <span class="value">{{ project.script_config?.episode_duration_range?.join('-') || '30-45' }}分钟</span>
            </div>
            <div class="config-item">
              <span class="label">剧本格式</span>
              <span class="value">{{ project.script_config?.format_standard || '标准格式' }}</span>
            </div>
            <div class="config-item">
              <span class="label">对白比例</span>
              <span class="value">{{ project.script_config?.dialogue_narration_ratio || '均衡' }}</span>
            </div>
          </template>

          <!-- 通用配置 -->
          <div class="config-item">
            <span class="label">题材</span>
            <span class="value">{{ project.genre || '未设置' }}</span>
          </div>
        </el-card>

        <!-- 统计信息 -->
        <el-card class="stats-card compact-card">
          <template #header>
            <span>统计信息</span>
          </template>

          <div class="stats-grid">
            <div class="stats-item-compact">
              <span class="label">Token消耗</span>
              <span class="value">{{ project.total_tokens?.toLocaleString() || 0 }}</span>
            </div>
            <div class="stats-item-compact">
              <span class="label">创建时间</span>
              <span class="value small">{{ formatDateTime(project.created_at) }}</span>
            </div>
            <div class="stats-item-compact">
              <span class="label">更新时间</span>
              <span class="value small">{{ formatDateTime(project.updated_at) }}</span>
            </div>
          </div>
        </el-card>

        <!-- 知识库状态卡片 -->
        <el-card class="knowledge-base-card compact-card">
          <template #header>
            <div class="card-header-flex">
              <span>知识库</span>
              <el-button 
                size="small" 
                text 
                type="primary" 
                @click="refreshKnowledgeBaseStatus"
                :loading="loadingKbStatus"
              >
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </template>

          <!-- 未构建状态 -->
          <div v-if="kbStatus.status === 'pending'" class="kb-status-pending">
            <el-empty :image-size="60" description="知识库未构建">
              <el-button 
                type="primary" 
                size="small" 
                @click="handleBuildKnowledgeBase"
                :loading="buildingKb"
                :disabled="!project.outline_content"
              >
                <el-icon><Cpu /></el-icon>
                构建知识库
              </el-button>
            </el-empty>
            <div v-if="!project.outline_content" class="kb-hint">
              <el-icon><WarningFilled /></el-icon>
              <span>请先上传大纲</span>
            </div>
          </div>

          <!-- 构建中状态 -->
          <div v-else-if="kbStatus.status === 'building'" class="kb-status-building">
            <!-- 幽灵状态警告 -->
            <el-alert
              v-if="kbStatus.is_stale"
              type="warning"
              title="检测到异常状态"
              description="知识库构建任务可能已中断，请点击下方按钮重置状态"
              :closable="false"
              show-icon
              style="margin-bottom: 12px;"
            />
            <div class="kb-progress">
              <el-progress 
                :percentage="kbStatus.progress?.progress || 0" 
                :status="kbStatus.is_stale ? 'exception' : 'warning'"
                :stroke-width="10"
              />
              <p class="kb-message">{{ kbStatus.progress?.message || '正在构建...' }}</p>
            </div>
            <!-- 正常构建中状态 -->
            <el-button 
              v-if="!kbStatus.is_stale"
              type="danger" 
              size="small" 
              plain
              disabled
            >
              构建中，请稍候...
            </el-button>
            <!-- 幽灵状态：显示重置按钮 -->
            <el-button 
              v-else
              type="warning" 
              size="small" 
              plain
              @click="handleResetKbStatus"
              :loading="resettingKbStatus"
            >
              <el-icon><RefreshRight /></el-icon>
              重置状态
            </el-button>
          </div>

          <!-- 构建完成状态 -->
          <div v-else-if="kbStatus.status === 'ready'" class="kb-status-ready">
            <div class="kb-stats-grid">
              <div class="kb-stat-item">
                <el-icon color="#67c23a"><CircleCheckFilled /></el-icon>
                <span class="kb-stat-label">状态</span>
                <el-tag type="success" size="small">已就绪</el-tag>
              </div>
              <div class="kb-stat-item" v-if="kbStatus.progress?.entity_count">
                <el-icon color="#409EFC"><DataAnalysis /></el-icon>
                <span class="kb-stat-label">实体数</span>
                <span class="kb-stat-value">{{ kbStatus.progress.entity_count }}</span>
              </div>
              <div class="kb-stat-item" v-if="kbStatus.progress?.relation_count">
                <el-icon color="#E6A23C"><Connection /></el-icon>
                <span class="kb-stat-label">关系数</span>
                <span class="kb-stat-value">{{ kbStatus.progress.relation_count }}</span>
              </div>
              <div class="kb-stat-item">
                <el-icon color="#909399"><Cpu /></el-icon>
                <span class="kb-stat-label">GraphRAG</span>
                <el-tag :type="kbStatus.graphrag_enabled ? 'success' : 'info'" size="small">
                  {{ kbStatus.graphrag_enabled ? '已启用' : '未启用' }}
                </el-tag>
              </div>
            </div>

            <div class="kb-actions">
              <el-button size="small" @click="showKnowledgeGraphDialog">
                <el-icon><DataAnalysis /></el-icon>
                查看图谱
              </el-button>
              <el-dropdown @command="handleUnitGraphCommand" style="margin-left: 8px;">
                <el-button size="small" type="primary" plain>
                  <el-icon><Collection /></el-icon>
                  重建单元图谱
                  <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="all">
                      <el-icon><List /></el-icon>
                      全部重建
                    </el-dropdown-item>
                    <el-dropdown-item command="select">
                      <el-icon><Select /></el-icon>
                      选择单元重建...
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-popconfirm
                title="确定要重建全局知识库吗？这将清除现有数据。"
                @confirm="handleBuildKnowledgeBase"
                confirm-button-text="确定"
                cancel-button-text="取消"
              >
                <template #reference>
                  <el-button size="small" type="warning" plain :loading="buildingKb">
                    <el-icon><Refresh /></el-icon>
                    重建全局
                  </el-button>
                </template>
              </el-popconfirm>
              <el-popconfirm
                title="确定要删除知识库吗？"
                @confirm="handleDeleteKnowledgeBase"
                confirm-button-text="删除"
                cancel-button-text="取消"
              >
                <template #reference>
                  <el-button size="small" type="danger" text>
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>

          <!-- 构建失败状态 -->
          <div v-else-if="kbStatus.status === 'failed'" class="kb-status-failed">
            <el-alert
              type="error"
              :title="'构建失败'"
              :description="kbStatus.progress?.error || '未知错误'"
              show-icon
              :closable="false"
            />
            <el-button 
              type="primary" 
              size="small" 
              @click="handleBuildKnowledgeBase"
              :loading="buildingKb"
              style="margin-top: 12px;"
            >
              重试构建
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 知识图谱可视化弹窗 -->
    <el-dialog 
      v-model="knowledgeGraphVisible" 
      title="知识图谱" 
      width="80%" 
      top="5vh"
      destroy-on-close
    >
      <div class="knowledge-graph-container">
        <!-- 图谱类型切换 -->
        <div class="graph-type-selector">
          <el-radio-group v-model="graphType" @change="loadKnowledgeGraph">
            <el-radio-button value="global">全局大纲图谱</el-radio-button>
            <el-radio-button value="unit">单元图谱</el-radio-button>
          </el-radio-group>
          <el-select 
            v-if="graphType === 'unit'" 
            v-model="selectedUnitNumber" 
            placeholder="选择单元"
            @change="loadKnowledgeGraph"
            style="margin-left: 12px; width: 120px;"
          >
            <el-option 
              v-for="i in project?.total_chapters || 0" 
              :key="i" 
              :label="`第${i}${unitLabel}`" 
              :value="i" 
            />
          </el-select>
        </div>

        <!-- 图谱统计信息 -->
        <div class="graph-stats" v-if="graphData.stats">
          <el-tag type="info" size="small">
            节点: {{ graphData.stats.node_count || 0 }}
          </el-tag>
          <el-tag type="info" size="small" style="margin-left: 8px;">
            边: {{ graphData.stats.edge_count || 0 }}
          </el-tag>
          <el-tag type="info" size="small" style="margin-left: 8px;" v-if="graphData.stats.entity_types">
            实体类型: {{ graphData.stats.entity_types?.join(', ') || '-' }}
          </el-tag>
        </div>

        <!-- 图谱可视化区域 -->
        <div class="graph-visualization" v-loading="loadingGraphData">
          <div v-if="graphData.nodes.length === 0 && !loadingGraphData" class="graph-empty">
            <el-empty :image-size="100" description="暂无图谱数据" />
          </div>
          <div v-else ref="graphContainer" class="graph-canvas">
            <!-- 节点列表视图 -->
            <div class="nodes-list-view">
              <el-collapse v-model="expandedNodeTypes">
                <el-collapse-item 
                  v-for="(nodes, type) in groupedNodes" 
                  :key="type"
                  :name="type"
                >
                  <template #title>
                    <div class="node-type-header">
                      <el-tag :type="getNodeTypeTag(type)" size="small">{{ type }}</el-tag>
                      <span class="node-count">({{ nodes.length }})</span>
                    </div>
                  </template>
                  <div class="node-list">
                    <div 
                      v-for="node in nodes" 
                      :key="node.id" 
                      class="node-item"
                      @click="selectNode(node)"
                      :class="{ 'selected': selectedNode?.id === node.id }"
                    >
                      <span class="node-name">{{ node.name }}</span>
                      <span class="node-desc" v-if="node.description">{{ node.description }}</span>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <!-- 关系列表视图 -->
            <div class="edges-list-view">
              <div class="edges-header">
                <span>关系列表</span>
                <el-tag size="small" type="info">{{ graphData.edges.length }}</el-tag>
              </div>
              <div class="edges-list">
                <div 
                  v-for="(edge, index) in graphData.edges" 
                  :key="index"
                  class="edge-item"
                >
                  <span class="edge-source">{{ getNodeName(edge.source) }}</span>
                  <span class="edge-relation">{{ edge.relation }}</span>
                  <span class="edge-target">{{ getNodeName(edge.target) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 选中节点详情 -->
        <div v-if="selectedNode" class="node-detail-panel">
          <el-card shadow="never">
            <template #header>
              <div class="detail-header">
                <el-tag :type="getNodeTypeTag(selectedNode.type)" size="small">
                  {{ selectedNode.type }}
                </el-tag>
                <span class="detail-name">{{ selectedNode.name }}</span>
              </div>
            </template>
            <div class="detail-content">
              <p v-if="selectedNode.description"><strong>描述:</strong> {{ selectedNode.description }}</p>
              <p v-if="selectedNode.attributes">
                <strong>属性:</strong>
                <el-tag 
                  v-for="(value, key) in selectedNode.attributes" 
                  :key="key"
                  size="small"
                  style="margin: 2px;"
                >
                  {{ key }}: {{ value }}
                </el-tag>
              </p>
              <!-- 相关关系 -->
              <div v-if="relatedEdges.length > 0" class="related-edges">
                <strong>相关关系:</strong>
                <div v-for="edge in relatedEdges" :key="edge.id" class="related-edge">
                  <span v-if="edge.source === selectedNode.id">
                    → {{ getNodeName(edge.target) }} ({{ edge.relation }})
                  </span>
                  <span v-else>
                    {{ getNodeName(edge.source) }} → ({{ edge.relation }})
                  </span>
                </div>
              </div>
            </div>
          </el-card>
        </div>
      </div>

      <template #footer>
        <el-button @click="knowledgeGraphVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 单元图谱重建弹窗 -->
    <el-dialog 
      v-model="unitGraphRebuildVisible" 
      title="重建单元知识图谱" 
      width="600px"
      destroy-on-close
    >
      <div class="unit-graph-rebuild-content">
        <!-- 状态概览 -->
        <div class="unit-status-overview" v-if="unitGraphsStatus.loaded">
          <el-statistic title="已构建" :value="unitGraphsStatus.built_count" suffix="个" />
          <el-statistic title="待构建" :value="unitGraphsStatus.unbuilt_count" suffix="个" />
          <el-statistic title="总计" :value="unitGraphsStatus.total_units" suffix="个" />
        </div>

        <el-divider />

        <!-- 构建选项 -->
        <div class="rebuild-options">
          <h4>选择构建范围</h4>
          <el-radio-group v-model="unitRebuildMode">
            <el-radio value="all">全部重建（覆盖已有图谱）</el-radio>
            <el-radio value="unbuilt">仅构建未构建的单元</el-radio>
            <el-radio value="select">选择指定单元</el-radio>
          </el-radio-group>

          <!-- 单元选择器 -->
          <div v-if="unitRebuildMode === 'select'" class="unit-selector">
            <el-transfer
              v-model="selectedUnitsForRebuild"
              :data="availableUnitsForRebuild"
              :titles="['可选单元', '已选单元']"
              :props="{
                key: 'value',
                label: 'label'
              }"
              filterable
              filter-placeholder="搜索单元"
            />
          </div>

          <!-- 待构建单元列表 -->
          <div v-if="unitRebuildMode === 'unbuilt' && unitGraphsStatus.unbuilt_units.length > 0" class="unbuilt-units-list">
            <el-tag 
              v-for="unit in unitGraphsStatus.unbuilt_units" 
              :key="unit.unit_number"
              type="info"
              style="margin: 2px;"
            >
              第{{ unit.unit_number }}{{ unitLabel }}
            </el-tag>
          </div>
        </div>

        <!-- 构建进度 -->
        <div v-if="buildingUnitGraphs" class="build-progress">
          <el-progress :percentage="unitBuildProgress" :status="unitBuildStatus" />
          <p class="progress-message">{{ unitBuildMessage }}</p>
        </div>
      </div>

      <template #footer>
        <el-button @click="unitGraphRebuildVisible = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="executeUnitGraphRebuild"
          :loading="buildingUnitGraphs"
          :disabled="isRebuildButtonDisabled"
        >
          开始构建
        </el-button>
      </template>
    </el-dialog>

    <!-- 修正对比弹窗 -->
    <el-dialog 
      v-model="revisionCompareVisible" 
      title="修正前后对比" 
      width="90%" 
      top="3vh"
      destroy-on-close
    >
      <div class="revision-compare-container">
        <!-- 修正信息 -->
        <div class="revision-info-header">
          <el-tag type="success">已应用知识库修正</el-tag>
          <span class="revision-stats">
            原文 <strong>{{ chapterRevisionInfo?.original_length || originalDraftContent?.length || 0 }}</strong> 字 
            → 修正后 <strong>{{ chapterRevisionInfo?.revised_length || revisedContent?.length || 0 }}</strong> 字
            <span v-if="revisionWordChange !== 0" :class="['word-change', revisionWordChange > 0 ? 'increase' : 'decrease']">
              ({{ revisionWordChange > 0 ? '+' : '' }}{{ revisionWordChange }}字)
            </span>
          </span>
          <span class="revision-time" v-if="chapterRevisionInfo?.revised_at">
            修正时间: {{ formatDateTime(chapterRevisionInfo.revised_at) }}
          </span>
        </div>

        <!-- 知识库引用信息 -->
        <div v-if="chapterRevisionInfo?.knowledge_used" class="knowledge-used-info">
          <el-collapse>
            <el-collapse-item title="知识库引用详情" name="knowledge">
              <div class="knowledge-detail">
                <p v-if="chapterRevisionInfo.knowledge_used.global_entities">
                  <strong>全局实体:</strong> {{ chapterRevisionInfo.knowledge_used.global_entities }} 个
                </p>
                <p v-if="chapterRevisionInfo.knowledge_used.unit_entities">
                  <strong>单元实体:</strong> {{ chapterRevisionInfo.knowledge_used.unit_entities }} 个
                </p>
                <p v-if="chapterRevisionInfo.knowledge_used.relations_found">
                  <strong>相关关系:</strong> {{ chapterRevisionInfo.knowledge_used.relations_found }} 个
                </p>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 视图切换标签 -->
        <div class="view-switch">
          <el-radio-group v-model="revisionViewMode" size="small">
            <el-radio-button value="diff">差异对比</el-radio-button>
            <el-radio-button value="side">左右对照</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 差异对比视图 -->
        <div v-if="revisionViewMode === 'diff'" class="diff-view">
          <div class="diff-legend">
            <span class="legend-item added"><span class="legend-color"></span>新增内容</span>
            <span class="legend-item removed"><span class="legend-color"></span>删除内容</span>
            <span class="legend-item modified"><span class="legend-color"></span>修改内容</span>
          </div>
          <div class="diff-content" v-html="revisionDiffHtml"></div>
        </div>

        <!-- 左右对照视图 -->
        <div v-else class="compare-view">
          <div class="compare-panel">
            <div class="panel-header">
              <el-tag type="warning">原始草稿</el-tag>
              <span class="panel-word-count">{{ originalDraftContent?.length || 0 }} 字</span>
            </div>
            <div class="panel-content">
              <el-input
                v-model="originalDraftContent"
                type="textarea"
                :rows="25"
                readonly
              />
            </div>
          </div>
          
          <div class="compare-panel">
            <div class="panel-header">
              <el-tag type="success">修正后内容</el-tag>
              <span class="panel-word-count">{{ revisedContent?.length || 0 }} 字</span>
            </div>
            <div class="panel-content">
              <el-input
                v-model="revisedContent"
                type="textarea"
                :rows="25"
                readonly
              />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="revisionCompareVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 合规审核详情弹窗 -->
    <el-dialog 
      v-model="complianceDetailVisible" 
      title="合规审核详情" 
      width="800px"
      top="5vh"
    >
      <div class="compliance-detail-container">
        <!-- 审核概况 -->
        <div class="compliance-summary">
          <el-alert
            :type="complianceDetailData?.has_issues ? 'warning' : 'success'"
            :closable="false"
            show-icon
          >
            <template #title>
              <span v-if="complianceDetailData?.has_issues">
                发现 {{ complianceDetailData?.issue_count }} 处潜在合规问题
              </span>
              <span v-else>内容合规，未发现问题</span>
            </template>
          </el-alert>
          <div class="compliance-meta" v-if="complianceDetailData">
            <span>审核时间: {{ formatDateTime(complianceDetailData.check_time) }}</span>
            <span style="margin-left: 16px;">审核级别: {{ complianceDetailData.level === 'strict' ? '严格' : complianceDetailData.level === 'loose' ? '宽松' : '标准' }}</span>
          </div>
        </div>

        <!-- 问题列表 -->
        <div v-if="complianceDetailData?.issues?.length" class="compliance-issues">
          <div class="issues-header">
            <span>问题分布：</span>
            <el-tag type="danger" size="small" v-if="complianceDetailData.issue_summary?.high">
              高危 {{ complianceDetailData.issue_summary.high }}
            </el-tag>
            <el-tag type="warning" size="small" v-if="complianceDetailData.issue_summary?.medium">
              中等 {{ complianceDetailData.issue_summary.medium }}
            </el-tag>
            <el-tag type="info" size="small" v-if="complianceDetailData.issue_summary?.low">
              低危 {{ complianceDetailData.issue_summary.low }}
            </el-tag>
          </div>

          <div class="issues-list">
            <div 
              v-for="issue in complianceDetailData.issues" 
              :key="issue.id" 
              class="issue-item"
              :class="['severity-' + issue.severity]"
            >
              <div class="issue-header">
                <el-tag 
                  :type="issue.severity === 'high' ? 'danger' : issue.severity === 'medium' ? 'warning' : 'info'"
                  size="small"
                >
                  {{ issue.severity === 'high' ? '高危' : issue.severity === 'medium' ? '中等' : '低危' }}
                </el-tag>
                <span class="issue-type">{{ getIssueTypeLabel(issue.type) }}</span>
                <span class="issue-location">第{{ issue.paragraph }}段</span>
              </div>
              <div class="issue-content">
                <div class="issue-text">
                  <span class="label">违规内容：</span>
                  <span class="text">"{{ issue.text }}"</span>
                </div>
                <div class="issue-context">
                  <span class="label">上下文：</span>
                  <span class="context" v-html="issue.context"></span>
                </div>
              </div>
              <div class="issue-footer">
                <div class="issue-reason">
                  <span class="label">违规原因：</span>
                  <span>{{ issue.reason }}</span>
                </div>
                <div class="issue-suggestion">
                  <span class="label">修改建议：</span>
                  <span>{{ issue.suggestion }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <el-empty v-else description="暂无合规问题" />
      </div>

      <template #footer>
        <el-button @click="complianceDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 设置对话框 -->
    <el-dialog v-model="settingsVisible" title="项目设置" width="600px">
      <el-form :model="settingsForm" label-width="120px">
        <el-form-item label="项目标题">
          <el-input v-model="settingsForm.title" />
        </el-form-item>
        <el-form-item label="题材">
          <el-input v-model="settingsForm.genre" />
        </el-form-item>
        
        <el-divider content-position="left">生成配置</el-divider>
        
        <!-- 小说设置 -->
        <template v-if="project?.content_type === 'novel'">
          <el-form-item label="投放平台">
            <el-input v-model="settingsForm.novel_config.target_platform" placeholder="如：起点中文网、豆瓣阅读" />
          </el-form-item>
          <el-form-item label="每章字数">
            <el-input-number v-model="settingsForm.novel_config.words_per_chapter" :min="1000" :max="10000" :step="500" />
          </el-form-item>
          <el-form-item label="叙事视角">
            <el-select v-model="settingsForm.novel_config.narrative_perspective">
              <el-option label="第一人称" value="第一人称" />
              <el-option label="第三人称" value="第三人称" />
            </el-select>
          </el-form-item>
          <el-form-item label="基调风格">
            <el-select v-model="settingsForm.novel_config.tone">
              <el-option label="正剧" value="正剧" />
              <el-option label="轻松" value="轻松" />
              <el-option label="幽默" value="幽默" />
              <el-option label="严肃" value="严肃" />
              <el-option label="温馨" value="温馨" />
              <el-option label="热血" value="热血" />
            </el-select>
          </el-form-item>
        </template>
        
        <!-- 剧集剧本设置 -->
        <template v-else-if="project?.content_type === 'series_script'">
          <el-form-item label="剧集类型">
            <el-select v-model="settingsForm.series_script_config.series_type">
              <el-option label="电视剧" value="电视剧" />
              <el-option label="网络剧" value="网络剧" />
              <el-option label="短剧" value="短剧" />
              <el-option label="微短剧" value="微短剧" />
            </el-select>
          </el-form-item>
          <el-form-item label="每集时长">
            <div style="display: flex; align-items: center; gap: 10px;">
              <el-input-number v-model="settingsForm.series_script_config.episode_duration_range[0]" :min="1" :max="120" :step="5" style="width: 100px;" />
              <span>-</span>
              <el-input-number v-model="settingsForm.series_script_config.episode_duration_range[1]" :min="1" :max="120" :step="5" style="width: 100px;" />
              <span style="color: #909399;">分钟</span>
            </div>
          </el-form-item>
          <el-form-item label="剧本格式">
            <el-select v-model="settingsForm.series_script_config.format_standard">
              <el-option label="标准格式" value="标准格式" />
              <el-option label="简格式" value="简格式" />
              <el-option label="网络平台格式" value="网络平台格式" />
              <el-option label="短剧格式" value="短剧格式" />
            </el-select>
          </el-form-item>
          <el-form-item label="对白比例">
            <el-select v-model="settingsForm.series_script_config.dialogue_narration_ratio">
              <el-option label="对话为主" value="对话为主" />
              <el-option label="均衡" value="均衡" />
              <el-option label="叙述为主" value="叙述为主" />
              <el-option label="动作导向" value="动作导向" />
            </el-select>
          </el-form-item>
          <el-form-item label="投放平台">
            <el-input v-model="settingsForm.series_script_config.target_broadcast" placeholder="如：爱奇艺、腾讯视频" />
          </el-form-item>
        </template>
        
        <!-- 电影剧本设置 -->
        <template v-else-if="project?.content_type === 'movie_script'">
          <el-form-item label="电影类型">
            <el-select v-model="settingsForm.movie_script_config.movie_type">
              <el-option label="院线电影" value="院线电影" />
              <el-option label="网络电影" value="网络电影" />
              <el-option label="微电影" value="微电影" />
              <el-option label="纪录片" value="纪录片" />
            </el-select>
          </el-form-item>
          <el-form-item label="电影时长">
            <el-input-number v-model="settingsForm.movie_script_config.total_duration" :min="5" :max="180" :step="5" />
            <span style="color: #909399; margin-left: 10px;">分钟</span>
          </el-form-item>
          <el-form-item label="剧本格式">
            <el-select v-model="settingsForm.movie_script_config.format_standard">
              <el-option label="标准格式" value="标准格式" />
              <el-option label="影院格式" value="影院格式" />
              <el-option label="电视电影格式" value="电视电影格式" />
            </el-select>
          </el-form-item>
          <el-form-item label="对白比例">
            <el-select v-model="settingsForm.movie_script_config.dialogue_narration_ratio">
              <el-option label="对话为主" value="对话为主" />
              <el-option label="均衡" value="均衡" />
              <el-option label="叙述为主" value="叙述为主" />
              <el-option label="动作导向" value="动作导向" />
            </el-select>
          </el-form-item>
        </template>
        
        <el-divider content-position="left">项目专属知识库</el-divider>
        
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        >
          <template #title>
            <span style="font-size: 13px;">项目专属知识库完全独立于公共知识库，仅存储本项目大纲的实体和关系。</span>
          </template>
        </el-alert>
        
        <!-- 项目知识库状态 -->
        <el-form-item label="知识库状态">
          <div class="kb-setting-status">
            <el-tag :type="kbStatus.status === 'ready' ? 'success' : kbStatus.status === 'building' ? 'warning' : kbStatus.status === 'failed' ? 'danger' : 'info'" size="small">
              {{ kbStatus.status === 'ready' ? '已就绪' : kbStatus.status === 'building' ? '构建中' : kbStatus.status === 'failed' ? '构建失败' : '未构建' }}
            </el-tag>
            <el-button 
              v-if="kbStatus.status !== 'building'"
              size="small" 
              text 
              type="primary" 
              @click="handleBuildKnowledgeBase"
              :loading="buildingKb"
              :disabled="!project.outline_content"
            >
              {{ kbStatus.status === 'ready' ? '重建知识库' : '构建知识库' }}
            </el-button>
            <span v-if="!project.outline_content" class="form-tip warn">（需先上传大纲）</span>
          </div>
        </el-form-item>
        
        <el-form-item label="GraphRAG增强">
          <el-switch v-model="settingsForm.graphrag_enabled" />
          <span class="form-tip">启用知识图谱增强检索（自动从大纲提取人物、事件等实体关系）</span>
        </el-form-item>
        
        <el-form-item v-if="kbStatus.status === 'ready' && kbStatus.progress" label="图谱统计">
          <div class="kb-stats-info">
            <span>实体: {{ kbStatus.progress.entity_count || 0 }}</span>
            <span style="margin-left: 16px;">关系: {{ kbStatus.progress.relation_count || 0 }}</span>
          </div>
        </el-form-item>
        
        <el-divider content-position="left">公共知识库（可选参考）</el-divider>
        
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        >
          <template #title>
            <span style="font-size: 13px;">公共知识库用于正文生成时参考创意理论、案例技巧等，与项目专属知识库完全独立。</span>
          </template>
        </el-alert>
        
        <el-form-item label="垂直领域知识库">
          <el-switch v-model="settingsForm.kb_vertical_enabled" />
          <span class="form-tip">小说/剧本案例、技巧等</span>
        </el-form-item>
        
        <el-form-item label="用户专属知识库">
          <el-switch v-model="settingsForm.kb_user_specific_enabled" />
          <span class="form-tip">您上传的个性化知识</span>
        </el-form-item>
        
        <el-form-item label="官方手册">
          <el-switch v-model="settingsForm.kb_manual_enabled" />
          <span class="form-tip">官方规范、标准手册</span>
        </el-form-item>
        
        <el-divider content-position="left">合规审核</el-divider>
        
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        >
          <template #title>
            <span style="font-size: 13px;">合规审核会标记正文中的敏感词、敏感地名、名人姓名等潜在问题，供您参考修改。</span>
          </template>
        </el-alert>
        
        <el-form-item label="启用合规审核">
          <el-switch v-model="settingsForm.compliance_enabled" />
          <span class="form-tip">生成后自动检测并标记潜在问题</span>
        </el-form-item>
        
        <el-form-item v-if="settingsForm.compliance_enabled" label="审核级别">
          <el-radio-group v-model="settingsForm.compliance_level">
            <el-radio value="strict">严格模式</el-radio>
            <el-radio value="normal">标准模式</el-radio>
            <el-radio value="loose">宽松模式</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item v-if="settingsForm.compliance_enabled" label="目标平台">
          <el-select v-model="settingsForm.compliance_platform" placeholder="选择目标发布平台" style="width: 200px;">
            <el-option label="通用" value="" />
            <el-option label="起点中文网" value="起点中文网" />
            <el-option label="晋江文学城" value="晋江文学城" />
            <el-option label="番茄小说" value="番茄小说" />
            <el-option label="飞卢小说" value="飞卢小说" />
            <el-option label="纵横中文网" value="纵横中文网" />
            <el-option label="17K小说网" value="17K小说网" />
            <el-option label="其他平台" value="其他" />
          </el-select>
          <span class="form-tip">不同平台有不同的内容规范</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="settingsVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSettings" :loading="savingSettings">保存</el-button>
      </template>
    </el-dialog>

    <!-- 导出对话框 -->
    <el-dialog v-model="exportVisible" title="导出项目" width="400px">
      <el-form :model="exportForm" label-width="100px">
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio value="txt">TXT</el-radio>
            <el-radio value="md">Markdown</el-radio>
            <el-radio value="docx">Word</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="包含元数据">
          <el-switch v-model="exportForm.include_metadata" />
        </el-form-item>
        <el-form-item label="范围">
          <el-input v-model="exportForm.chapter_range" :placeholder="`留空导出全部，如：1-10`" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportVisible = false">取消</el-button>
        <el-button type="primary" @click="handleExport" :loading="exporting">导出</el-button>
      </template>
    </el-dialog>

    <!-- 分集大纲详情弹窗 -->
    <el-dialog 
      v-model='outlineDetailVisible' 
      :title='`第 ${currentOutlineDetail.episode_number} 集《${currentOutlineDetail.episode_title}》详细大纲`'
      width='80%'
      top='5vh'
      destroy-on-close
      @closed='outlineEditMode = false'
    >
      <!-- 查看模式 -->
      <div v-if='!outlineEditMode' class='outline-detail-content markdown-content' v-html='renderedOutlineContent'></div>
      
      <!-- 编辑模式 -->
      <div v-else class='outline-edit-mode'>
        <el-form label-width='80px'>
          <el-form-item label='集标题'>
            <el-input v-model='outlineEditTitle' placeholder='请输入集标题' />
          </el-form-item>
          <el-form-item label='大纲内容'>
            <el-input
              v-model='outlineEditContent'
              type='textarea'
              :rows='20'
              placeholder='请输入分集详细大纲内容'
            />
          </el-form-item>
        </el-form>
      </div>
      
      <template #footer>
        <div style='display: flex; justify-content: space-between; width: 100%;'>
          <div>
            <el-button v-if='!outlineEditMode' type='primary' plain @click='startEditOutline'>
              <el-icon><Setting /></el-icon>
              编辑大纲
            </el-button>
          </div>
          <div>
            <template v-if='outlineEditMode'>
              <el-button @click='cancelEditOutline'>取消</el-button>
              <el-button type='primary' @click='saveOutlineEdit' :loading='savingOutlineEdit'>
                保存修改
              </el-button>
            </template>
            <template v-else>
              <el-button @click='outlineDetailVisible = false'>关闭</el-button>
              <el-button type='primary' @click='downloadSingleEpisodeOutline'>
                <el-icon><Download /></el-icon>
                下载
              </el-button>
            </template>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 章节大纲详情弹窗 -->
    <el-dialog 
      v-model='chapterOutlineDetailVisible'
      :title='`第 ${currentChapterOutlineDetail.chapter_number} 章《${currentChapterOutlineDetail.chapter_title}》详细大纲`'
      width='80%'
      top='5vh'
      destroy-on-close
      @closed='chapterOutlineEditMode = false'
    >
      <!-- 修正信息提示 -->
      <el-alert
        v-if='currentChapterOutlineDetail.revision_info?.applied'
        type='success'
        :closable='false'
        show-icon
        style='margin-bottom: 12px;'
      >
        <template #title>
          <span>已应用逻辑一致性修正</span>
          <span style='margin-left: 12px; font-size: 12px; color: #909399;'>
            原文 {{ currentChapterOutlineDetail.revision_info?.original_length }} 字 → 修正后 {{ currentChapterOutlineDetail.revision_info?.revised_length }} 字
          </span>
        </template>
      </el-alert>

      <!-- 查看模式 -->
      <div v-if='!chapterOutlineEditMode' class='outline-detail-content markdown-content' v-html='renderedChapterOutlineContent'></div>
      
      <!-- 编辑模式 -->
      <div v-else class='outline-edit-mode'>
        <el-input
          v-model='chapterOutlineEditTitle'
          placeholder='章节标题'
          style='margin-bottom: 12px;'
        />
        <el-input
          v-model='chapterOutlineEditContent'
          type='textarea'
          :rows='20'
          placeholder='章节大纲内容'
        />
      </div>
      
      <template #footer>
        <div class='dialog-footer-actions'>
          <div>
            <el-button v-if='!chapterOutlineEditMode && currentChapterOutlineDetail.revision_info?.applied' type='success' plain @click='showChapterOutlineRevisionCompare'>
              <el-icon><View /></el-icon>
              查看修正对比
            </el-button>
            <el-button v-if='!chapterOutlineEditMode' type='primary' @click='startEditChapterOutline'>
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
          </div>
          <div>
            <template v-if='chapterOutlineEditMode'>
              <el-button @click='cancelEditChapterOutline'>取消</el-button>
              <el-button type='primary' @click='saveChapterOutlineEdit' :loading='savingChapterOutlineEdit'>
                保存修改
              </el-button>
            </template>
            <template v-else>
              <el-button @click='chapterOutlineDetailVisible = false'>关闭</el-button>
              <el-button type='primary' @click='downloadSingleChapterOutline'>
                <el-icon><Download /></el-icon>
                下载
              </el-button>
            </template>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 章节大纲修正对比弹窗 -->
    <el-dialog 
      v-model='chapterOutlineRevisionCompareVisible' 
      title='章节大纲修正前后对比' 
      width='90%' 
      top='3vh'
      destroy-on-close
    >
      <div class='revision-compare-container'>
        <!-- 修正信息 -->
        <div class='revision-info-header'>
          <el-tag type='success'>已应用逻辑一致性修正</el-tag>
          <span class='revision-stats'>
            原文 <strong>{{ chapterOutlineRevisionInfo?.original_length || chapterOutlineOriginalContent?.length || 0 }}</strong> 字 
            → 修正后 <strong>{{ chapterOutlineRevisionInfo?.revised_length || chapterOutlineRevisedContent?.length || 0 }}</strong> 字
            <span v-if='chapterOutlineRevisionWordChange !== 0' :class='["word-change", chapterOutlineRevisionWordChange > 0 ? "increase" : "decrease"]'>
              ({{ chapterOutlineRevisionWordChange > 0 ? "+" : "" }}{{ chapterOutlineRevisionWordChange }}字)
            </span>
          </span>
          <span class='revision-time' v-if='chapterOutlineRevisionInfo?.revised_at'>
            修正时间: {{ formatDateTime(chapterOutlineRevisionInfo.revised_at) }}
          </span>
        </div>

        <!-- 视图切换标签 -->
        <div class='view-switch'>
          <el-radio-group v-model='chapterOutlineRevisionViewMode' size='small'>
            <el-radio-button value='diff'>差异对比</el-radio-button>
            <el-radio-button value='side'>左右对照</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 差异对比视图 -->
        <div v-if='chapterOutlineRevisionViewMode === "diff"' class='diff-view'>
          <div class='diff-legend'>
            <span class='legend-item added'><span class='legend-color'></span>新增内容</span>
            <span class='legend-item removed'><span class='legend-color'></span>删除内容</span>
            <span class='legend-item modified'><span class='legend-color'></span>修改内容</span>
          </div>
          <div class='diff-content' v-html='chapterOutlineRevisionDiffHtml'></div>
        </div>

        <!-- 左右对照视图 -->
        <div v-else class='compare-view'>
          <div class='compare-panel'>
            <div class='panel-header'>
              <el-tag type='warning'>原始大纲</el-tag>
              <span class='panel-word-count'>{{ chapterOutlineOriginalContent?.length || 0 }} 字</span>
            </div>
            <div class='panel-content'>
              <el-input
                v-model='chapterOutlineOriginalContent'
                type='textarea'
                :rows='25'
                readonly
              />
            </div>
          </div>
          
          <div class='compare-panel'>
            <div class='panel-header'>
              <el-tag type='success'>修正后大纲</el-tag>
              <span class='panel-word-count'>{{ chapterOutlineRevisedContent?.length || 0 }} 字</span>
            </div>
            <div class='panel-content'>
              <el-input
                v-model='chapterOutlineRevisedContent'
                type='textarea'
                :rows='25'
                readonly
              />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click='chapterOutlineRevisionCompareVisible = false'>关闭</el-button>
      </template>
    </el-dialog>

    <!-- 场景大纲详情弹窗 -->
    <el-dialog 
      v-model='sceneOutlineDetailVisible'
      :title='`第 ${currentSceneOutlineDetail.scene_number} 场《${currentSceneOutlineDetail.scene_title}》详细大纲`'
      width='80%'
      top='5vh'
      destroy-on-close
      @closed='sceneOutlineEditMode = false'
    >
      <!-- 查看模式 -->
      <div v-if='!sceneOutlineEditMode' class='outline-detail-content markdown-content' v-html='renderedSceneOutlineContent'></div>
      
      <!-- 编辑模式 -->
      <div v-else class='outline-edit-mode'>
        <el-input
          v-model='sceneOutlineEditTitle'
          placeholder='场景标题'
          style='margin-bottom: 12px;'
        />
        <el-input
          v-model='sceneOutlineEditContent'
          type='textarea'
          :rows='20'
          placeholder='场景大纲内容'
        />
      </div>
      
      <template #footer>
        <div class='dialog-footer-actions'>
          <div>
            <el-button v-if='!sceneOutlineEditMode' type='primary' @click='startEditSceneOutline'>
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
          </div>
          <div>
            <template v-if='sceneOutlineEditMode'>
              <el-button @click='cancelEditSceneOutline'>取消</el-button>
              <el-button type='primary' @click='saveSceneOutlineEdit' :loading='savingSceneOutlineEdit'>
                保存修改
              </el-button>
            </template>
            <template v-else>
              <el-button @click='sceneOutlineDetailVisible = false'>关闭</el-button>
              <el-button type='primary' @click='downloadSingleSceneOutline'>
                <el-icon><Download /></el-icon>
                下载
              </el-button>
            </template>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 用户干预对话框 -->
    <el-dialog
      v-model="interventionDialogVisible"
      title="生成确认"
      width="640px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      class="intervention-dialog"
    >
      <div class="intervention-content">
        <!-- 提示信息 -->
        <div class="intervention-banner">
          <div class="banner-icon">
            <el-icon><WarningFilled /></el-icon>
          </div>
          <div class="banner-info">
            <div class="banner-message">{{ interventionData.message }}</div>
          </div>
        </div>

        <!-- 推断的概要内容 -->
        <div v-if="interventionData.inferred_summary" class="inferred-summary">
          <div class="summary-header">
            <el-icon><Reading /></el-icon>
            <span>系统推断的章节概要</span>
          </div>
          <div class="summary-content">
            {{ interventionData.inferred_summary }}
          </div>
        </div>

        <!-- 用户选择 -->
        <div class="intervention-options">
          <div class="options-title">请选择处理方式</div>
          <div class="options-grid">
            <div
              v-for="option in interventionOptions"
              :key="option.value"
              class="option-card"
              :class="{ active: interventionUserChoice === option.value }"
              @click="interventionUserChoice = option.value"
            >
              <div class="option-icon">
                <el-icon><component :is="option.icon" /></el-icon>
              </div>
              <div class="option-info">
                <div class="option-label">{{ option.label }}</div>
                <div class="option-desc">{{ option.desc }}</div>
              </div>
              <div v-if="interventionUserChoice === option.value" class="option-check">
                <el-icon><CircleCheckFilled /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <!-- 用户输入概要内容 -->
        <div v-if="interventionUserChoice === 'provide'" class="user-guidance-input">
          <div class="input-label">
            <el-icon><Edit /></el-icon>
            <span>请输入章节概要内容</span>
          </div>
          <el-input
            v-model="interventionUserGuidance"
            type="textarea"
            :rows="4"
            placeholder="请输入本章概要内容，包括主要剧情、关键事件、人物发展等..."
          />
        </div>
      </div>

      <template #footer>
        <el-button @click="handleInterventionCancel">取消</el-button>
        <el-button 
          type="primary" 
          @click="handleInterventionConfirm"
          :loading="interventionLoading"
          :disabled="!interventionUserChoice || (interventionUserChoice === 'provide' && !interventionUserGuidance.trim())"
        >
          确认
        </el-button>
      </template>
    </el-dialog>

    <!-- 单元概述上传对话框 -->
    <el-dialog
      v-model="showUnitSummariesUploadDialog"
      title="上传单元概述"
      width="650px"
    >
      <div class="unit-summaries-upload-dialog">
        <!-- 上传方式切换 -->
        <el-tabs v-model="unitSummariesUploadMode" class="upload-tabs">
          <!-- 文件上传选项卡 -->
          <el-tab-pane label="文件上传" name="file">
            <el-upload
              drag
              :show-file-list="false"
              :http-request="handleUnitSummariesFileUpload"
              accept=".txt,.md,.doc,.docx"
              :disabled="uploadingUnitSummaries"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                拖拽单元概述文件到此处，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 .txt, .md, .doc, .docx 格式，与全局大纲格式相同
                </div>
              </template>
            </el-upload>
            <el-alert type="info" :closable="false" style="margin-top: 12px;">
              <template #title>文件格式说明</template>
              <div style="font-size: 13px; margin-top: 4px;">
                <p>文件应包含各单元的标题和梗概内容，格式示例：</p>
                <pre style="background: #f5f7fa; padding: 8px; border-radius: 4px; font-size: 12px; overflow-x: auto; margin-top: 8px;">### 第1章：开篇

**本章梗概**：故事的开端，介绍主人公...

---

### 第2章：相遇

**本章梗概**：主人公与关键人物相遇...</pre>
              </div>
            </el-alert>
          </el-tab-pane>
          
          <!-- JSON粘贴选项卡 -->
          <el-tab-pane label="JSON粘贴" name="json">
            <el-alert type="info" :closable="false" style="margin-bottom: 12px;">
              <template #title>JSON格式说明</template>
              <div style="font-size: 13px; margin-top: 4px;">
                <p>可从创意生成板块的“导出”功能获取JSON格式。</p>
              </div>
            </el-alert>
            
            <el-form-item label="单元概述内容">
              <el-input
                v-model="unitSummariesInput"
                type="textarea"
                :rows="8"
                placeholder="请粘贴单元概述JSON内容..."
              />
            </el-form-item>
            
            <el-form-item label="全局大纲（可选）">
              <el-input
                v-model="globalOutlineInput"
                type="textarea"
                :rows="4"
                placeholder="可选：粘贴全局大纲内容..."
              />
            </el-form-item>
          </el-tab-pane>
        </el-tabs>
      </div>
      <template #footer>
        <el-button @click="showUnitSummariesUploadDialog = false">取消</el-button>
        <el-button 
          v-if="unitSummariesUploadMode === 'json'"
          type="primary" 
          @click="handleUploadUnitSummaries"
          :loading="uploadingUnitSummaries"
          :disabled="!unitSummariesInput.trim()"
        >
          确认上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 指定数量生成对话框 -->
    <el-dialog 
      v-model="showBatchCountDialog" 
      title="生成指定数量单元" 
      width="450px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px">
        <el-form-item label="起始单元">
          <el-input-number 
            v-model="batchCountConfig.startUnit" 
            :min="1" 
            :max="batchCountConfig.maxUnit"
          />
        </el-form-item>
        <el-form-item label="生成数量">
          <el-input-number 
            v-model="batchCountConfig.count" 
            :min="1" 
            :max="50"
          />
        </el-form-item>
        <el-form-item label="预计生成">
          <el-text>
            第 {{ batchCountConfig.startUnit }} 至第 {{ Math.min(batchCountConfig.startUnit + batchCountConfig.count - 1, batchCountConfig.maxUnit) }} {{ batchCountConfig.unitLabel }}
          </el-text>
          <el-text v-if="batchCountConfig.startUnit + batchCountConfig.count - 1 > batchCountConfig.maxUnit" type="warning">
            (已超出最大单元数)
          </el-text>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchCountDialog = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="executeBatchCountGenerate" 
          :loading="batchCountLoading"
        >
          开始生成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Setting, Download, Delete, DeleteFilled, DocumentDelete, UploadFilled, Upload, CircleCheckFilled, WarningFilled, InfoFilled, Refresh, RefreshRight, Document, MagicStick, ArrowDown, Edit, VideoPause, Reading, Cpu, DataAnalysis, ChatDotRound, Folder, List, Loading, Finished, CircleCheck, CircleClose, Warning, Connection, Collection, Select } from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { novelWriterApi } from '@/api/novel-writer'
import { useTaskStore } from '@/stores/task'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()

const projectId = computed(() => parseInt(route.params.id))

// 内容类型标签映射
const CONTENT_TYPE_LABELS = {
  'novel': '小说',
  'series_script': '剧集剧本',
  'movie_script': '电影剧本'
}

// 内容类型对应的Tag类型
const CONTENT_TYPE_TAG_TYPES = {
  'novel': 'success',
  'series_script': 'warning',
  'movie_script': 'danger'
}

// 数据
const loading = ref(true)
const project = ref(null)
const chapters = ref([])
const selectedChapter = ref(null)
const chapterContent = ref('')

// 生成状态
const generating = ref(false)
const generatingChapter = ref(false)
const generatingDirectory = ref(false)
const regeneratingNames = ref(false)
const manualUnitCount = ref(10)  // 默认生成单位数量

// 单元概述上传状态
const showUnitSummariesUploadDialog = ref(false)
const unitSummariesUploadMode = ref('file')  // 'file' 或 'json'
const unitSummariesInput = ref('')
const globalOutlineInput = ref('')
const uploadingUnitSummaries = ref(false)

// AbortController 用于终止生成
const abortController = ref(null)

// 任务状态轮询相关
const taskPollingTimer = ref(null)
const TASK_POLLING_INTERVAL = 2000 // 轮询间隔 2秒

// SSE 实时推送相关（优先使用 SSE，降级到轮询）
const sseConnection = ref(null)
const sseReconnectTimer = ref(null)
const SSE_RECONNECT_DELAY = 3000 // SSE 断线重连延迟

// 分集大纲相关状态
const episodeOutlines = ref([])
const generatingEpisodeOutlines = ref(false)


// 批量正文生成状态
const generatingAllContent = ref(false)
const batchContentType = ref(null)
const batchProgress = ref({ completed: 0, total: 0, current: null })

// 指定数量生成对话框状态
const showBatchCountDialog = ref(false)
const batchCountLoading = ref(false)
const batchCountConfig = ref({
  startUnit: 1,      // 起始单元
  count: 5,          // 生成数量
  maxUnit: 100,      // 最大单元数
  unitLabel: '章',   // 单元标签
  type: 'outline',   // outline 或 content
  contentType: 'chapter'  // chapter, episode, scene
})

const generatingSingleEpisode = ref(null)
const selectedEpisode = ref(null)  // 当前正在生成正文的剧集

// 电影场景正文生成状态
const selectedScene = ref(null)  // 当前正在生成正文的场景

// 分集大纲详情弹窗
const outlineDetailVisible = ref(false)
const currentOutlineDetail = ref({
  episode_number: 0,
  episode_title: '',
  raw_content: ''
})

// 弹窗编辑模式
const outlineEditMode = ref(false)
const outlineEditContent = ref('')
const outlineEditTitle = ref('')
const savingOutlineEdit = ref(false)

// 分集大纲标题编辑状态
const editingEpisodeTitle = ref(null)
const editEpisodeTitleValue = ref('')

// 章节标题编辑状态
const editingChapter = ref(null)
const editTitleValue = ref('')

// 章节大纲相关状态（小说专用）
const chapterOutlines = ref([])
const generatingChapterOutlines = ref(false)
const generatingSingleChapterOutline = ref(null)

// 章节大纲详情弹窗
const chapterOutlineDetailVisible = ref(false)
const currentChapterOutlineDetail = ref({
  chapter_number: 0,
  chapter_title: '',
  raw_content: '',
  revision_info: null,
  original_content: null
})

// 章节大纲修正对比相关状态
const chapterOutlineRevisionCompareVisible = ref(false)
const chapterOutlineOriginalContent = ref('')
const chapterOutlineRevisedContent = ref('')
const chapterOutlineRevisionInfo = ref(null)
const chapterOutlineRevisionViewMode = ref('diff')  // 默认显示差异对比视图

// 章节大纲编辑模式
const chapterOutlineEditMode = ref(false)
const chapterOutlineEditContent = ref('')
const chapterOutlineEditTitle = ref('')
const savingChapterOutlineEdit = ref(false)

// 章节大纲标题编辑状态
const editingChapterOutlineTitle = ref(null)
const editChapterOutlineTitleValue = ref('')

// 场景大纲相关状态（电影剧本专用）
const sceneOutlines = ref([])
const generatingSceneOutlines = ref(false)
const generatingSingleSceneOutline = ref(null)

// 场景大纲详情弹窗
const sceneOutlineDetailVisible = ref(false)
const currentSceneOutlineDetail = ref({
  scene_number: 0,
  scene_title: '',
  raw_content: ''
})

// 场景大纲编辑模式
const sceneOutlineEditMode = ref(false)
const sceneOutlineEditContent = ref('')
const sceneOutlineEditTitle = ref('')
const savingSceneOutlineEdit = ref(false)

// 场景大纲标题编辑状态
const editingSceneOutlineTitle = ref(null)
const editSceneOutlineTitleValue = ref('')

// 用户干预对话框状态
const interventionDialogVisible = ref(false)
const interventionData = ref({
  unit_number: 0,
  content_type: 'novel',
  inferred_summary: '',
  reference_info: null,
  message: ''
})
const interventionLoading = ref(false)
const interventionUserChoice = ref('')  // accept/provide/reference/skip
const interventionUserGuidance = ref('')

// 干预选项配置
const interventionOptions = [
  { value: 'accept', label: '接受推断结果', desc: '使用系统推断的概要继续生成', icon: 'CircleCheck' },
  { value: 'provide', label: '提供概要内容', desc: '自行输入章节概要', icon: 'Edit' },
  { value: 'reference', label: '参考相邻章节', desc: '使用前后章节信息重新生成', icon: 'Reading' },
  { value: 'skip', label: '跳过此章节', desc: '暂时跳过，稍后处理', icon: 'VideoPause' }
]

// 对话框
const settingsVisible = ref(false)
const exportVisible = ref(false)
const savingSettings = ref(false)
const exporting = ref(false)

// 知识库状态
const kbStatus = ref({
  status: 'pending',
  progress: null,
  graphrag_enabled: true,
  stats: null
})
const loadingKbStatus = ref(false)
const buildingKb = ref(false)
const resettingKbStatus = ref(false)

// 知识图谱可视化
const knowledgeGraphVisible = ref(false)
const graphType = ref('global')
const selectedUnitNumber = ref(1)
const graphData = ref({
  nodes: [],
  edges: [],
  stats: null
})
const loadingGraphData = ref(false)
const selectedNode = ref(null)
const expandedNodeTypes = ref([])
const graphContainer = ref(null)

// 单元图谱重建相关状态
const unitGraphRebuildVisible = ref(false)
const unitRebuildMode = ref('unbuilt')  // 'all' | 'unbuilt' | 'select'
const unitGraphsStatus = ref({
  loaded: false,
  built_count: 0,
  unbuilt_count: 0,
  total_units: 0,
  built_units: [],
  unbuilt_units: []
})
const selectedUnitsForRebuild = ref([])
const buildingUnitGraphs = ref(false)
const unitBuildProgress = ref(0)
const unitBuildStatus = ref('')
const unitBuildMessage = ref('')

// 修正对比相关状态
const revisionCompareVisible = ref(false)
const originalDraftContent = ref('')
const revisedContent = ref('')
const chapterRevisionInfo = ref(null)
const revisionViewMode = ref('diff')  // 默认显示差异对比视图

// 合规审核相关状态
const complianceDetailVisible = ref(false)
const complianceDetailData = ref(null)

// 当前章节的合规标记（计算属性）
const chapterComplianceMarking = computed(() => {
  return selectedChapter.value?.chapter_metadata?.compliance_marking || null
})

// 问题类型中文映射
const ISSUE_TYPE_LABELS = {
  'sensitive_word': '敏感词',
  'sensitive_location': '敏感地名',
  'sensitive_person': '名人姓名',
  'sensitive_event': '历史事件'
}

// 获取问题类型标签
function getIssueTypeLabel(type) {
  return ISSUE_TYPE_LABELS[type] || type
}

// 显示合规详情
function showComplianceDetail(chapter) {
  if (chapter?.chapter_metadata?.compliance_marking) {
    complianceDetailData.value = chapter.chapter_metadata.compliance_marking
    complianceDetailVisible.value = true
  }
}

// 计算字数变化
const revisionWordChange = computed(() => {
  const originalLen = chapterRevisionInfo.value?.original_length || originalDraftContent.value?.length || 0
  const revisedLen = chapterRevisionInfo.value?.revised_length || revisedContent.value?.length || 0
  return revisedLen - originalLen
})

// 计算差异对比 HTML
const revisionDiffHtml = computed(() => {
  if (!originalDraftContent.value || !revisedContent.value) return ''
  return computeDiffHtml(originalDraftContent.value, revisedContent.value)
})

/**
 * 计算两段文本的差异，生成带高亮的 HTML
 * 使用优化的行级对比算法
 * @param {string} oldText - 原始文本
 * @param {string} newText - 新文本
 * @returns {string} 带差异标记的 HTML
 */
function computeDiffHtml(oldText, newText) {
  if (!oldText && !newText) return ''
  if (!oldText) return `<div class="diff-paragraph added">${escapeHtml(newText)}</div>`
  if (!newText) return `<div class="diff-paragraph removed">${escapeHtml(oldText)}</div>`
  
  // 按段落分割
  const oldParagraphs = oldText.split(/\n+/).filter(p => p.trim())
  const newParagraphs = newText.split(/\n+/).filter(p => p.trim())
  
  // 对于小文本使用LCS，大文本使用简单对比
  if (oldParagraphs.length <= 100 && newParagraphs.length <= 100) {
    return computeDiffWithLCS(oldParagraphs, newParagraphs)
  } else {
    return computeDiffSimple(oldParagraphs, newParagraphs)
  }
}

/**
 * 使用LCS算法计算差异（适用于小文本）
 */
function computeDiffWithLCS(oldParagraphs, newParagraphs) {
  const lcs = findLCS(oldParagraphs, newParagraphs)
  
  let html = ''
  let oldIdx = 0, newIdx = 0, lcsIdx = 0
  
  while (oldIdx < oldParagraphs.length || newIdx < newParagraphs.length) {
    if (lcsIdx < lcs.length && oldIdx < oldParagraphs.length && 
        oldParagraphs[oldIdx] === lcs[lcsIdx] && 
        newIdx < newParagraphs.length && newParagraphs[newIdx] === lcs[lcsIdx]) {
      // 相同段落
      html += `<div class="diff-paragraph unchanged">${escapeHtml(oldParagraphs[oldIdx])}</div>`
      oldIdx++
      newIdx++
      lcsIdx++
    } else if (newIdx < newParagraphs.length &&
               (lcsIdx >= lcs.length || newParagraphs[newIdx] !== lcs[lcsIdx])) {
      // 新增或修改的段落
      if (oldIdx < oldParagraphs.length &&
          (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
        // 修改：旧段落被删除，新段落是新增
        html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
        html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
        oldIdx++
        newIdx++
      } else {
        // 纯新增
        html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
        newIdx++
      }
    } else if (oldIdx < oldParagraphs.length &&
               (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
      // 纯删除
      html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
      oldIdx++
    }
  }
  
  return html
}

/**
 * 简单差异对比（适用于大文本）
 * 使用哈希集合快速匹配
 */
function computeDiffSimple(oldParagraphs, newParagraphs) {
  // 构建新段落集合
  const newSet = new Set(newParagraphs)
  const oldSet = new Set(oldParagraphs)
  
  let html = ''
  const processedOld = new Set()
  const processedNew = new Set()
  
  // 先处理旧段落
  for (const para of oldParagraphs) {
    if (newSet.has(para)) {
      // 相同段落
      html += `<div class="diff-paragraph unchanged">${escapeHtml(para)}</div>`
    } else {
      // 被删除的段落
      html += `<div class="diff-paragraph removed">${escapeHtml(para)}</div>`
    }
    processedOld.add(para)
  }
  
  // 找出新增的段落
  for (const para of newParagraphs) {
    if (!oldSet.has(para)) {
      html += `<div class="diff-paragraph added">${escapeHtml(para)}</div>`
    }
  }
  
  return html
}

/**
 * 找出两个数组的最长公共子序列
 */
function findLCS(arr1, arr2) {
  const m = arr1.length, n = arr2.length
  const dp = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0))
  
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (arr1[i - 1] === arr2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }
  
  // 回溯找出 LCS
  const lcs = []
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (arr1[i - 1] === arr2[j - 1]) {
      lcs.unshift(arr1[i - 1])
      i--
      j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }
  
  return lcs
}

/**
 * HTML 转义
 */
function escapeHtml(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/ /g, '&nbsp;')  // 保留空格
}

// 默认配置
const DEFAULT_NOVEL_CONFIG = {
  target_platform: '',
  words_per_chapter: 3000,
  narrative_perspective: '第三人称',
  tone: '正剧',
  temperature: 0.8
}

const DEFAULT_SERIES_SCRIPT_CONFIG = {
  series_type: '电视剧',
  episode_count: null,
  episode_duration_range: [30, 45],
  format_standard: '标准格式',
  dialogue_narration_ratio: '均衡',
  target_broadcast: ''
}

const DEFAULT_MOVIE_SCRIPT_CONFIG = {
  movie_type: '院线电影',
  total_duration: 90,
  format_standard: '标准格式',
  dialogue_narration_ratio: '均衡',
  target_platform: ''
}

// 表单
const settingsForm = ref({
  title: '',
  genre: '',
  // 小说配置
  novel_config: { ...DEFAULT_NOVEL_CONFIG },
  // 剧集剧本配置
  series_script_config: { ...DEFAULT_SERIES_SCRIPT_CONFIG },
  // 电影剧本配置
  movie_script_config: { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
  // 知识库配置
  kb_vertical_enabled: false,
  kb_user_specific_enabled: false,
  kb_manual_enabled: false,
  graphrag_enabled: true,
  // 合规审核配置
  compliance_enabled: true,
  compliance_level: 'normal',
  compliance_platform: ''
})

const exportForm = ref({
  format: 'txt',
  include_metadata: false,
  chapter_range: ''
})

// 计算属性
const canGenerate = computed(() => {
  return project.value?.outline_content && project.value?.total_chapters > 0
})

const totalWords = computed(() => {
  return chapters.value.reduce((sum, c) => sum + (c.word_count || 0), 0)
})

// 分集大纲相关计算属性
const totalEpisodeCount = computed(() => {
  return project.value?.series_script_config?.episode_count || project.value?.script_config?.episode_count || 0
})

const generatedEpisodeCount = computed(() => {
  return episodeOutlines.value.filter(e => e.has_detailed).length
})

// 渲染后的 Markdown 内容
const renderedOutlineContent = computed(() => {
  if (!currentOutlineDetail.value.raw_content) return ''
  return DOMPurify.sanitize(marked(currentOutlineDetail.value.raw_content))
})

// 章节大纲相关计算属性（小说专用）
const totalChapterOutlineCount = computed(() => {
  return project.value?.total_chapters || 0
})

const generatedChapterOutlineCount = computed(() => {
  return chapterOutlines.value.filter(c => c.has_detailed).length
})

// 渲染后的章节大纲 Markdown 内容
const renderedChapterOutlineContent = computed(() => {
  if (!currentChapterOutlineDetail.value.raw_content) return ''
  return DOMPurify.sanitize(marked(currentChapterOutlineDetail.value.raw_content))
})

// 章节大纲修正字数变化
const chapterOutlineRevisionWordChange = computed(() => {
  const originalLen = chapterOutlineRevisionInfo.value?.original_length || chapterOutlineOriginalContent.value?.length || 0
  const revisedLen = chapterOutlineRevisionInfo.value?.revised_length || chapterOutlineRevisedContent.value?.length || 0
  return revisedLen - originalLen
})

// 章节大纲修正差异对比 HTML
const chapterOutlineRevisionDiffHtml = computed(() => {
  if (!chapterOutlineOriginalContent.value || !chapterOutlineRevisedContent.value) return ''
  return computeDiffHtml(chapterOutlineOriginalContent.value, chapterOutlineRevisedContent.value)
})

// 场景大纲相关计算属性（电影剧本专用）
const totalSceneOutlineCount = computed(() => {
  return project.value?.total_chapters || 0
})

const generatedSceneOutlineCount = computed(() => {
  return sceneOutlines.value.filter(s => s.has_detailed).length
})

// 已生成正文的数量
const generatedEpisodeContentCount = computed(() => {
  return episodeOutlines.value.filter(e => e.content_status === 'generated').length
})

const generatedChapterContentCount = computed(() => {
  return chapterOutlines.value.filter(c => c.content_status === 'generated').length
})

const generatedSceneContentCount = computed(() => {
  return sceneOutlines.value.filter(s => s.content_status === 'generated').length
})

// 渲染后的场景大纲 Markdown 内容
const renderedSceneOutlineContent = computed(() => {
  if (!currentSceneOutlineDetail.value.raw_content) return ''
  return DOMPurify.sanitize(marked(currentSceneOutlineDetail.value.raw_content))
})

// 根据内容类型返回生成单位标签
const unitLabel = computed(() => {
  const contentType = project.value?.content_type
  if (contentType === 'novel') return '章'
  if (contentType === 'series_script') return '集'
  if (contentType === 'movie_script') return '场'
  // 兼容旧版
  if (project.value?.project_type === 'script') return '集'
  return '章'
})

// 可用于重建的单元列表（用于穿梭框）
const availableUnitsForRebuild = computed(() => {
  const total = project.value?.total_chapters || 0
  const units = []
  for (let i = 1; i <= total; i++) {
    units.push({
      value: i,
      label: `第${i}${unitLabel.value}`,
      disabled: false
    })
  }
  return units
})

// 重建按钮是否禁用
const isRebuildButtonDisabled = computed(() => {
  if (buildingUnitGraphs.value) return true
  if (unitRebuildMode.value === 'select' && selectedUnitsForRebuild.value.length === 0) return true
  if (unitRebuildMode.value === 'unbuilt' && unitGraphsStatus.value.unbuilt_count === 0) return true
  return false
})

// 内容类型标签
function getTypeLabel(contentType) {
  return CONTENT_TYPE_LABELS[contentType] || '小说'
}

function getTypeTagType(contentType) {
  return CONTENT_TYPE_TAG_TYPES[contentType] || 'info'
}

// 加载项目
async function loadProject() {
  loading.value = true
  try {
    const res = await novelWriterApi.getProject(projectId.value)
    if (res.success) {
      project.value = res.data
      const kbConfig = res.data.knowledge_base_config || {}
      const complianceConfig = res.data.compliance_config || {}
      
      // 设置默认生成单位数量
      manualUnitCount.value = res.data.total_chapters || 10
      
      // 基础表单数据
      settingsForm.value = {
        title: res.data.title,
        genre: res.data.genre || '',
        // 小说配置
        novel_config: res.data.novel_config || { ...DEFAULT_NOVEL_CONFIG },
        // 剧集剧本配置
        series_script_config: res.data.series_script_config || { ...DEFAULT_SERIES_SCRIPT_CONFIG },
        // 电影剧本配置
        movie_script_config: res.data.movie_script_config || { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
        // 知识库配置
        kb_vertical_enabled: kbConfig.kb_vertical_enabled || false,
        kb_user_specific_enabled: kbConfig.kb_user_specific_enabled || false,
        kb_manual_enabled: kbConfig.kb_manual_enabled || false,
        graphrag_enabled: kbConfig.graphrag_enabled !== false,
        // 合规审核配置
        compliance_enabled: complianceConfig.enabled !== false,
        compliance_level: complianceConfig.level || 'normal',
        compliance_platform: complianceConfig.platform || ''
      }
    }
  } catch (error) {
    ElMessage.error('加载项目失败')
    router.back()
  } finally {
    loading.value = false
  }
}

// 加载章节列表
async function loadChapters() {
  try {
    const res = await novelWriterApi.getChapters(projectId.value)
    if (res.success) {
      chapters.value = res.data.chapters
    }
  } catch (error) {
    console.error('加载章节列表失败', error)
  }
}

// 选择章节
async function selectChapter(chapter) {
  selectedChapter.value = chapter
  chapterContent.value = ''
  chapterRevisionInfo.value = null

  if (chapter.status === 'completed') {
    try {
      const res = await novelWriterApi.getChapter(projectId.value, chapter.chapter_number)
      if (res.success) {
        chapterContent.value = res.data.final_content || ''
        // 加载修正信息
        if (res.data.chapter_metadata?.revision_info) {
          chapterRevisionInfo.value = res.data.chapter_metadata.revision_info
          // 同时保存原始草稿内容
          originalDraftContent.value = res.data.draft_content || ''
          revisedContent.value = res.data.final_content || ''
        }
      }
    } catch (error) {
      console.error('加载章节内容失败', error)
    }
  }
}

// 显示修正对比对话框
function showRevisionCompareDialog() {
  revisionCompareVisible.value = true
}

// 上传大纲
async function handleOutlineUpload(options) {
  const file = options.file
  const formData = new FormData()
  formData.append('file', file)

  try {
    ElMessage.info('正在上传大纲...')
    const res = await novelWriterApi.uploadOutline(projectId.value, formData)
    if (res.success) {
      const extractedUnits = res.data.extracted_chapters || 0
      
      if (extractedUnits > 0) {
        ElMessage.success(`大纲上传成功，识别到${extractedUnits}个${unitLabel.value}`)
        manualUnitCount.value = extractedUnits
      } else {
        ElMessage.warning('大纲上传成功，但未能自动识别，请手动设置数量')
      }
      
      // 刷新项目信息（不自动生成目录，让用户确认）
      loadProject()
      loadChapters()
    }
  } catch (error) {
    ElMessage.error('上传失败')
  }
}

// 上传单元概述
async function handleUploadUnitSummaries() {
  if (!unitSummariesInput.value.trim()) {
    ElMessage.warning('请输入单元概述内容')
    return
  }

  // 尝试解析JSON
  let unitSummaries = null
  try {
    unitSummaries = JSON.parse(unitSummariesInput.value.trim())
  } catch (e) {
    ElMessage.error('单元概述格式错误，请输入有效的JSON格式')
    return
  }

  // 验证格式
  if (typeof unitSummaries !== 'object' || Array.isArray(unitSummaries)) {
    ElMessage.error('单元概述格式错误，应为对象格式')
    return
  }

  uploadingUnitSummaries.value = true
  try {
    const data = {
      unit_summaries: unitSummaries
    }
    
    // 如果有全局大纲，一并上传
    if (globalOutlineInput.value.trim()) {
      data.global_outline = globalOutlineInput.value.trim()
    }

    const res = await novelWriterApi.uploadUnitSummaries(projectId.value, data)
    if (res.success) {
      ElMessage.success(res.data.message || '单元概述上传成功')
      showUnitSummariesUploadDialog.value = false
      unitSummariesInput.value = ''
      globalOutlineInput.value = ''
      // 刷新项目信息
      loadProject()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploadingUnitSummaries.value = false
  }
}

// 上传单元概述文件
async function handleUnitSummariesFileUpload(options) {
  const file = options.file
  
  // 检查文件格式
  const validExtensions = ['.txt', '.md', '.doc', '.docx']
  const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!validExtensions.includes(fileExt)) {
    ElMessage.error(`不支持的文件格式: ${fileExt}，支持 .txt, .md, .doc, .docx`)
    return
  }

  uploadingUnitSummaries.value = true
  
  try {
    const formData = new FormData()
    formData.append('file', file)

    ElMessage.info('正在上传单元概述文件...')
    
    const res = await novelWriterApi.uploadUnitSummariesFile(projectId.value, formData)
    
    if (res.success) {
      ElMessage.success(res.data.message || '单元概述上传成功')
      showUnitSummariesUploadDialog.value = false
      // 刷新项目信息
      loadProject()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploadingUnitSummaries.value = false
  }
}

// 手动生成章节目录
async function handleGenerateDirectory() {
  if (!manualUnitCount.value || manualUnitCount.value < 1) {
    ElMessage.warning('请设置有效的数量')
    return
  }

  try {
    // 如果已有章节，提示用户确认
    if (chapters.value.length > 0) {
      await ElMessageBox.confirm(
        `当前已有 ${chapters.value.length} 个${unitLabel.value}，重新生成将会清空现有内容。确定要继续吗？`,
        '重新生成目录',
        { type: 'warning' }
      )
    }

    generatingDirectory.value = true
    const res = await novelWriterApi.generateDirectory(projectId.value, {
      total_chapters: manualUnitCount.value,
      generate_names: true  // 启用LLM预生成章节名称
    })
    
    if (res.success) {
      // 如果返回了章节列表，显示预览
      if (res.data && res.data.chapters) {
        ElMessage.success(`已创建${manualUnitCount.value}个${unitLabel.value}，名称已生成`)
      } else {
        ElMessage.success(`已创建${manualUnitCount.value}个${unitLabel.value}`)
      }
      loadProject()
      loadChapters()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('生成目录失败')
    }
  } finally {
    generatingDirectory.value = false
  }
}

// 重新生成章节名称
async function handleRegenerateNames() {
  try {
    regeneratingNames.value = true
    ElMessage.info('正在生成章节名称...')
    
    const res = await novelWriterApi.regenerateChapterNames(projectId.value)
    
    if (res.success) {
      ElMessage.success(`成功更新${res.data.updated_count}个${unitLabel.value}名称`)
      loadChapters()
    }
  } catch (error) {
    ElMessage.error('生成名称失败')
  } finally {
    regeneratingNames.value = false
  }
}

// 重新生成目录（清空现有章节并重新创建）
async function handleRegenerateDirectory() {
  try {
    // 确认操作
    await ElMessageBox.confirm(
      `重新生成目录将清空现有的 ${chapters.value.length} 个${unitLabel.value}及其内容，此操作不可撤销。确定要继续吗？`,
      '重新生成目录',
      { type: 'warning' }
    )

    // 获取配置
    const episodeCount = totalEpisodeCount.value || project.value?.total_chapters || chapters.value.length
    
    generatingDirectory.value = true
    const res = await novelWriterApi.generateDirectory(projectId.value, {
      total_chapters: episodeCount,
      generate_names: true
    })
    
    if (res.success) {
      ElMessage.success('目录已重新生成')
      loadProject()
      loadChapters()
      // 同时刷新分集大纲列表
      if (project.value?.content_type === 'series_script' || project.value?.project_type === 'script') {
        loadEpisodeOutlines()
      }
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重新生成目录失败')
    }
  } finally {
    generatingDirectory.value = false
  }
}

// 清理章节标题，去除重复的"第X集/第X章"前缀和"None场"等无效内容
function cleanChapterTitle(title) {
  if (!title) return '未命名'
  
  let cleaned = title
  
  // 去除开头的"第X集"、"第X章"、"第X场"等重复前缀
  cleaned = cleaned.replace(/^第\d+[集章场]\s*/g, '')
  
  // 去除"第None场"等无效内容
  cleaned = cleaned.replace(/第None[集章场]\s*/g, '')
  
  // 去除连续的重复"第X集/章/场"
  cleaned = cleaned.replace(/第\d+[集章场]\s*第\d+[集章场]\s*/g, '')
  
  // 去除前后空格
  cleaned = cleaned.trim()
  
  return cleaned || '未命名'
}

// 编辑章节标题
function startEditTitle(chapter) {
  editingChapter.value = chapter.chapter_number
  // 编辑时显示清理后的标题
  editTitleValue.value = cleanChapterTitle(chapter.chapter_title)
  if (editTitleValue.value === '未命名') {
    editTitleValue.value = ''
  }
}

// 保存章节标题的防抖标记
let isSavingTitle = false

// 处理回车键保存
function handleEnterSaveTitle(chapter) {
  if (isSavingTitle) return
  saveChapterTitle(chapter)
}

// 处理blur保存（带防抖）
function handleBlurSaveTitle(chapter) {
  if (isSavingTitle) return
  saveChapterTitle(chapter)
}

// 保存章节标题
async function saveChapterTitle(chapter) {
  // 防止重复保存
  if (isSavingTitle) return
  isSavingTitle = true
  
  try {
    const newTitle = editTitleValue.value.trim()
    
    // 如果标题为空，取消编辑
    if (!newTitle) {
      editingChapter.value = null
      return
    }

    // 如果没有变化，直接关闭编辑模式
    const currentCleaned = cleanChapterTitle(chapter.chapter_title)
    if (newTitle === currentCleaned) {
      editingChapter.value = null
      return
    }

    await novelWriterApi.updateChapterTitle(projectId.value, chapter.chapter_number, newTitle)
    chapter.chapter_title = newTitle
    editingChapter.value = null
    ElMessage.success('标题已更新')
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    // 延迟重置保存标记，防止blur和enter事件冲突
    setTimeout(() => {
      isSavingTitle = false
    }, 100)
  }
}

// 取消编辑标题
function cancelEditTitle() {
  editingChapter.value = null
  editTitleValue.value = ''
}

// 开始生成
async function startGenerate() {
  if (!canGenerate.value) return

  try {
    await ElMessageBox.confirm(
      '确定要开始生成所有章节吗？这可能需要较长时间。',
      '确认生成',
      { type: 'info' }
    )

    generating.value = true
    ElMessage.info('开始生成，请耐心等待...')

    const res = await novelWriterApi.generateAll(projectId.value, {
      start_chapter: 1,
      stop_on_error: true
    })

    if (res.success) {
      ElMessage.success(`生成完成！成功${res.data.completed_count}章，失败${res.data.failed_count}章`)
      loadProject()
      loadChapters()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('生成失败')
    }
  } finally {
    generating.value = false
  }
}

// 生成单个章节
async function generateSingleChapter() {
  if (!selectedChapter.value) return

  generatingChapter.value = true
  try {
    const res = await novelWriterApi.generateChapter(
      projectId.value,
      selectedChapter.value.chapter_number
    )

    if (res.success) {
      ElMessage.success('章节生成成功')
      loadChapters()
      selectChapter({ ...selectedChapter.value, status: 'completed' })
      loadProject()
    } else {
      ElMessage.error(res.data?.error_message || '生成失败')
    }
  } catch (error) {
    ElMessage.error('生成失败')
  } finally {
    generatingChapter.value = false
  }
}

// 保存章节内容
async function saveChapterContent() {
  if (!selectedChapter.value || !chapterContent.value) return

  try {
    await novelWriterApi.updateChapter(
      projectId.value,
      selectedChapter.value.chapter_number,
      { content: chapterContent.value }
    )
    ElMessage.success('已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

// 下载章节内容
function handleDownloadChapter(format) {
  if (!chapterContent.value || !selectedChapter.value) {
    ElMessage.warning('暂无内容可下载')
    return
  }
  
  const chapterNum = selectedChapter.value.chapter_number
  const chapterTitle = selectedChapter.value.chapter_title || `第${chapterNum}${unitLabel.value}`
  const projectTitle = project.value?.title || '未命名项目'
  
  let content = chapterContent.value
  let fileName = ''
  let mimeType = ''
  
  if (format === 'md') {
    // Markdown 格式：添加标题
    content = `# ${chapterTitle}\n\n> 来源：${projectTitle}\n\n---\n\n${chapterContent.value}`
    fileName = `${projectTitle}_${chapterTitle}.md`
    mimeType = 'text/markdown;charset=utf-8'
  } else {
    // TXT 格式
    content = `${chapterTitle}\n来源：${projectTitle}\n${'='.repeat(40)}\n\n${chapterContent.value}`
    fileName = `${projectTitle}_${chapterTitle}.txt`
    mimeType = 'text/plain;charset=utf-8'
  }
  
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.click()
  URL.revokeObjectURL(url)
  
  ElMessage.success('下载成功')
}

// 显示设置对话框
function showSettingsDialog() {
  settingsVisible.value = true
}

// 保存设置
async function saveSettings() {
  savingSettings.value = true
  try {
    const updateData = {
      title: settingsForm.value.title,
      genre: settingsForm.value.genre,
      knowledge_base_config: {
        kb_vertical_enabled: settingsForm.value.kb_vertical_enabled,
        kb_user_specific_enabled: settingsForm.value.kb_user_specific_enabled,
        kb_manual_enabled: settingsForm.value.kb_manual_enabled,
        graphrag_enabled: settingsForm.value.graphrag_enabled,
        kb_vertical_ids: [],
        kb_user_specific_ids: [],
        kb_manual_ids: []
      },
      compliance_config: {
        enabled: settingsForm.value.compliance_enabled,
        level: settingsForm.value.compliance_level,
        platform: settingsForm.value.compliance_platform
      }
    }
    
    // 根据内容类型保存对应配置
    const contentType = project.value?.content_type
    if (contentType === 'novel') {
      updateData.novel_config = settingsForm.value.novel_config
    } else if (contentType === 'series_script') {
      updateData.series_script_config = settingsForm.value.series_script_config
    } else if (contentType === 'movie_script') {
      updateData.movie_script_config = settingsForm.value.movie_script_config
    }
    
    await novelWriterApi.updateProject(projectId.value, updateData)
    ElMessage.success('设置已保存')
    settingsVisible.value = false
    loadProject()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    savingSettings.value = false
  }
}

// 显示导出对话框
function showExportDialog() {
  exportVisible.value = true
}

// 导出
async function handleExport() {
  exporting.value = true
  try {
    const res = await novelWriterApi.exportProject(projectId.value, exportForm.value)
    // 下载文件
    const url = window.URL.createObjectURL(new Blob([res]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${project.value.title}.${exportForm.value.format}`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    
    ElMessage.success('导出成功')
    exportVisible.value = false
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// 删除项目
async function handleDelete() {
  try {
    await ElMessageBox.confirm(
      '确定要删除此项目吗？删除后无法恢复。',
      '确认删除',
      { type: 'warning' }
    )

    await novelWriterApi.deleteProject(projectId.value)
    ElMessage.success('项目已删除')
    router.push('/novel-writer')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// ==================== 知识库相关方法 ====================

// 加载知识库状态
async function loadKnowledgeBaseStatus() {
  loadingKbStatus.value = true
  try {
    const res = await novelWriterApi.getKnowledgeBaseStatus(projectId.value)
    if (res.success) {
      kbStatus.value = res.data
    }
  } catch (error) {
    console.error('加载知识库状态失败', error)
  } finally {
    loadingKbStatus.value = false
  }
}

// 刷新知识库状态
async function refreshKnowledgeBaseStatus() {
  await loadKnowledgeBaseStatus()
  ElMessage.success('知识库状态已刷新')
}

// 构建知识库
async function handleBuildKnowledgeBase() {
  buildingKb.value = true
  try {
    const res = await novelWriterApi.buildKnowledgeBase(projectId.value)
    if (res.success) {
      ElMessage.success('知识库构建任务已启动')
      // 开始轮询状态
      startKbBuildPolling()
    }
  } catch (error) {
    ElMessage.error('启动知识库构建失败')
  } finally {
    buildingKb.value = false
  }
}

// 知识库构建状态轮询
let kbBuildPollingTimer = null
function startKbBuildPolling() {
  if (kbBuildPollingTimer) {
    clearInterval(kbBuildPollingTimer)
  }
  
  kbBuildPollingTimer = setInterval(async () => {
    try {
      const res = await novelWriterApi.getKnowledgeBaseStatus(projectId.value)
      if (res.success) {
        kbStatus.value = res.data
        if (res.data.status !== 'building') {
          // 构建完成或失败，停止轮询
          clearInterval(kbBuildPollingTimer)
          kbBuildPollingTimer = null
          
          if (res.data.status === 'ready') {
            ElMessage.success('知识库构建完成')
          } else if (res.data.status === 'failed') {
            ElMessage.error('知识库构建失败')
          }
        }
      }
    } catch (error) {
      console.error('轮询知识库状态失败', error)
    }
  }, 2000)
}

// 删除知识库
async function handleDeleteKnowledgeBase() {
  try {
    const res = await novelWriterApi.deleteKnowledgeBase(projectId.value)
    if (res.success) {
      ElMessage.success('知识库已删除')
      kbStatus.value = {
        status: 'pending',
        progress: null,
        graphrag_enabled: true,
        stats: null
      }
    }
  } catch (error) {
    ElMessage.error('删除知识库失败')
  }
}

// 重置知识库构建状态（用于清除幽灵状态）
async function handleResetKbStatus() {
  resettingKbStatus.value = true
  try {
    const res = await novelWriterApi.resetKnowledgeBaseStatus(projectId.value)
    if (res.success) {
      ElMessage.success(`知识库状态已重置: ${res.data.previous_status} → ${res.data.new_status}`)
      // 刷新知识库状态
      await loadKnowledgeBaseStatus()
    }
  } catch (error) {
    ElMessage.error('重置知识库状态失败')
  } finally {
    resettingKbStatus.value = false
  }
}

// 处理单元图谱重建命令
function handleUnitGraphCommand(command) {
  if (command === 'all') {
    unitRebuildMode.value = 'all'
    unitGraphRebuildVisible.value = true
    loadUnitGraphsStatus()
  } else if (command === 'select') {
    unitRebuildMode.value = 'select'
    selectedUnitsForRebuild.value = []
    unitGraphRebuildVisible.value = true
    loadUnitGraphsStatus()
  }
}

// 加载单元图谱状态
async function loadUnitGraphsStatus() {
  try {
    const res = await novelWriterApi.getUnitGraphsStatus(projectId.value)
    if (res.success) {
      unitGraphsStatus.value = {
        loaded: true,
        ...res.data
      }
    }
  } catch (error) {
    console.error('获取单元图谱状态失败', error)
  }
}

// 执行单元图谱重建
async function executeUnitGraphRebuild() {
  buildingUnitGraphs.value = true
  unitBuildProgress.value = 0
  unitBuildStatus.value = ''
  unitBuildMessage.value = '正在启动构建任务...'

  try {
    let unitNumbers = null

    if (unitRebuildMode.value === 'select') {
      unitNumbers = selectedUnitsForRebuild.value
    } else if (unitRebuildMode.value === 'unbuilt') {
      unitNumbers = unitGraphsStatus.value.unbuilt_units.map(u => u.unit_number)
    }
    // 'all' 模式传 null，后端会构建所有单元

    const res = await novelWriterApi.buildAllUnitKnowledgeGraphs(projectId.value, unitNumbers)

    if (res.success) {
      unitBuildProgress.value = 10
      unitBuildMessage.value = `已启动 ${res.data.total_count} 个单元的图谱构建...`

      // 开始轮询进度
      startUnitBuildPolling(res.data.total_count)
    } else {
      unitBuildStatus.value = 'exception'
      unitBuildMessage.value = res.message || '启动构建失败'
      buildingUnitGraphs.value = false
    }
  } catch (error) {
    unitBuildStatus.value = 'exception'
    unitBuildMessage.value = '启动构建失败: ' + (error.message || '未知错误')
    buildingUnitGraphs.value = false
  }
}

// 单元图谱构建进度轮询
let unitBuildPollingTimer = null
function startUnitBuildPolling(totalCount) {
  if (unitBuildPollingTimer) {
    clearInterval(unitBuildPollingTimer)
  }

  let checkCount = 0
  const maxChecks = 300  // 最多轮询5分钟（每秒一次）

  unitBuildPollingTimer = setInterval(async () => {
    checkCount++
    if (checkCount > maxChecks) {
      clearInterval(unitBuildPollingTimer)
      unitBuildPollingTimer = null
      unitBuildStatus.value = 'exception'
      unitBuildMessage.value = '构建超时，请刷新页面查看状态'
      buildingUnitGraphs.value = false
      return
    }

    try {
      const res = await novelWriterApi.getUnitGraphsStatus(projectId.value)
      if (res.success) {
        const newBuiltCount = res.data.built_count
        const progress = Math.min(95, 10 + (newBuiltCount / totalCount) * 85)
        unitBuildProgress.value = Math.round(progress)
        unitBuildMessage.value = `正在构建... 已完成 ${newBuiltCount}/${totalCount} 个单元`

        unitGraphsStatus.value = {
          loaded: true,
          ...res.data
        }

        // 检查是否完成
        if (res.data.unbuilt_count === 0 || newBuiltCount >= totalCount) {
          clearInterval(unitBuildPollingTimer)
          unitBuildPollingTimer = null
          unitBuildProgress.value = 100
          unitBuildStatus.value = 'success'
          unitBuildMessage.value = `构建完成！共构建 ${newBuiltCount} 个单元图谱`
          buildingUnitGraphs.value = false

          ElMessage.success('单元图谱构建完成')

          // 3秒后关闭弹窗
          setTimeout(() => {
            unitGraphRebuildVisible.value = false
          }, 2000)
        }
      }
    } catch (error) {
      console.error('轮询单元图谱状态失败', error)
    }
  }, 1000)
}

// 显示知识图谱弹窗
function showKnowledgeGraphDialog() {
  knowledgeGraphVisible.value = true
  loadKnowledgeGraph()
}

// 加载知识图谱数据
async function loadKnowledgeGraph() {
  loadingGraphData.value = true
  selectedNode.value = null
  
  try {
    const unitNumber = graphType.value === 'unit' ? selectedUnitNumber.value : null
    const res = await novelWriterApi.getKnowledgeGraph(projectId.value, unitNumber)
    
    if (res.success) {
      graphData.value = res.data
      // 默认展开所有节点类型
      expandedNodeTypes.value = Object.keys(groupedNodes.value)
    }
  } catch (error) {
    ElMessage.error('加载知识图谱失败')
  } finally {
    loadingGraphData.value = false
  }
}

// 计算属性：按类型分组的节点
const groupedNodes = computed(() => {
  const groups = {}
  for (const node of graphData.value.nodes) {
    const type = node.type || 'unknown'
    if (!groups[type]) {
      groups[type] = []
    }
    groups[type].push(node)
  }
  return groups
})

// 计算属性：选中节点的相关边
const relatedEdges = computed(() => {
  if (!selectedNode.value) return []
  return graphData.value.edges.filter(
    edge => edge.source === selectedNode.value.id || edge.target === selectedNode.value.id
  )
})

// 获取节点类型标签颜色
function getNodeTypeTag(type) {
  const typeColors = {
    '人物': 'primary',
    '地点': 'success',
    '事件': 'warning',
    '物品': 'info',
    '概念': 'danger',
    '组织': '',
    '时间': 'warning'
  }
  return typeColors[type] || 'info'
}

// 获取节点名称
function getNodeName(nodeId) {
  const node = graphData.value.nodes.find(n => n.id === nodeId)
  return node ? node.name : nodeId
}

// 选择节点
function selectNode(node) {
  selectedNode.value = node
}

// ==================== 删除内容相关方法 ====================

// 删除小说章节正文
async function handleDeleteChapterContent(outline) {
  try {
    await novelWriterApi.deleteChapterContent(projectId.value, outline.chapter_number)
    ElMessage.success(`第${outline.chapter_number}章正文已删除`)
    // 重新加载大纲列表
    await loadChapterOutlines()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 删除小说章节大纲
async function handleDeleteChapterOutline(outline) {
  try {
    await novelWriterApi.deleteChapterOutline(projectId.value, outline.chapter_number)
    ElMessage.success(`第${outline.chapter_number}章大纲已删除`)
    // 重新加载大纲列表
    await loadChapterOutlines()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 删除剧集正文
async function handleDeleteEpisodeContent(outline) {
  try {
    await novelWriterApi.deleteEpisodeContent(projectId.value, outline.episode_number)
    ElMessage.success(`第${outline.episode_number}集正文已删除`)
    // 重新加载大纲列表
    await loadEpisodeOutlines()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 删除剧集大纲
async function handleDeleteEpisodeOutline(outline) {
  try {
    await novelWriterApi.deleteEpisodeOutline(projectId.value, outline.episode_number)
    ElMessage.success(`第${outline.episode_number}集大纲已删除`)
    // 重新加载大纲列表
    await loadEpisodeOutlines()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 删除电影场景正文
async function handleDeleteSceneContent(outline) {
  try {
    await novelWriterApi.deleteSceneContent(projectId.value, outline.scene_number)
    ElMessage.success(`第${outline.scene_number}场正文已删除`)
    // 重新加载大纲列表
    await loadSceneOutlines()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 删除电影场景大纲
async function handleDeleteSceneOutline(outline) {
  try {
    await novelWriterApi.deleteSceneOutline(projectId.value, outline.scene_number)
    ElMessage.success(`第${outline.scene_number}场大纲已删除`)
    // 重新加载大纲列表
    await loadSceneOutlines()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// 同步正文状态（修复历史数据）
async function handleSyncContentStatus() {
  try {
    loading.value = true
    const res = await novelWriterApi.syncContentStatus(projectId.value)
    ElMessage.success(res.message || '正文状态同步成功')
    // 重新加载大纲列表
    if (project.value?.content_type === 'novel') {
      await loadChapterOutlines()
    } else if (project.value?.content_type === 'series_script') {
      await loadEpisodeOutlines()
    } else if (project.value?.content_type === 'movie_script') {
      await loadSceneOutlines()
    }
  } catch (error) {
    ElMessage.error('同步失败')
  } finally {
    loading.value = false
  }
}

// 一键清空所有大纲
async function handleClearAllOutlines() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有大纲吗？此操作不可恢复。',
      '确认清空',
      { type: 'warning' }
    )
    await novelWriterApi.deleteAllOutlines(projectId.value)
    ElMessage.success('所有大纲已清空')
    // 重新加载项目数据
    await loadProject()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

// 一键清空所有正文
async function handleClearAllContent() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有正文吗？大纲将保留。此操作不可恢复。',
      '确认清空',
      { type: 'warning' }
    )
    await novelWriterApi.deleteAllChapterContent(projectId.value)
    ElMessage.success('所有正文已清空')
    // 重新加载项目数据
    await loadProject()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

// 一键清空所有大纲和正文
async function handleClearAll() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有大纲和正文吗？此操作不可恢复！',
      '确认清空',
      { type: 'warning' }
    )
    await novelWriterApi.deleteAllContent(projectId.value)
    ElMessage.success('所有大纲和正文已清空')
    // 重新加载项目数据
    await loadProject()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

// ==================== 分集详细大纲相关方法 ====================

// 加载分集大纲列表
async function loadEpisodeOutlines() {
  if (project.value?.content_type !== 'series_script' && project.value?.project_type !== 'script') {
    return
  }
  
  try {
    const res = await novelWriterApi.getEpisodeOutlines(projectId.value)
    console.log('[分集大纲] API响应:', res)  // 调试日志
    
    if (res.success && res.data) {
      // 后端返回的是 episodes 字段，不是 episode_outlines
      const episodes = res.data.episodes || []
      const totalEp = res.data.total_episodes || totalEpisodeCount.value
      
      console.log('[分集大纲] 总集数:', totalEp, '已生成:', res.data.generated_count)
      
      // 创建完整的列表，包括未生成的大纲
      episodeOutlines.value = episodes.map(ep => ({
        episode_number: ep.episode_number,
        episode_title: ep.episode_title || `第${ep.episode_number}集`,
        has_detailed: ep.status === 'generated' || ep.status === 'edited',
        content_status: ep.content_status || null,  // 正文生成状态
        content_word_count: ep.content_word_count || 0,  // 正文字数
        ...ep
      }))
      
      console.log('[分集大纲] 处理后列表:', episodeOutlines.value)
    }
  } catch (error) {
    console.error('加载分集大纲失败', error)
  }
}

// 一键生成全部分集大纲（支持断点续传）
async function handleGenerateAllEpisodeOutlines(episodeNumbers = null) {
  const totalEp = totalEpisodeCount.value
  if (totalEp === 0) {
    ElMessage.warning('请先设置集数')
    return
  }
  
  // 如果传入了指定的集数列表，使用它；否则使用断点续传逻辑
  let pendingEpisodes
  if (episodeNumbers && Array.isArray(episodeNumbers)) {
    pendingEpisodes = episodeNumbers
  } else {
    // 断点续传：计算未生成的集数
    const existingEpisodes = episodeOutlines.value
      .filter(ep => ep.has_detailed)
      .map(ep => ep.episode_number)
    
    const allEpisodes = Array.from({ length: totalEp }, (_, i) => i + 1)
    pendingEpisodes = allEpisodes.filter(ep => !existingEpisodes.includes(ep))
  }
  
  if (pendingEpisodes.length === 0) {
    ElMessage.success('全部分集大纲已生成，无需重复生成')
    return
  }
  
  // 构建确认消息
  const startEp = Math.min(...pendingEpisodes)
  const confirmMsg = pendingEpisodes.length !== totalEp
    ? `将生成第 ${startEp} 至第 ${Math.max(...pendingEpisodes)} 集，共 ${pendingEpisodes.length} 集。确定继续吗？`
    : `确定要生成全部 ${pendingEpisodes.length} 集的详细大纲吗？这可能需要较长时间。`
  
  try {
    await ElMessageBox.confirm(confirmMsg, '确认生成', { type: 'info' })
    
    // 设置任务状态
    taskStore.setTask({
      project_id: projectId.value,
      task_type: 'episode_outline',
      status: 'running',
      total_count: pendingEpisodes.length,
      completed_count: 0
    })
    
    generatingEpisodeOutlines.value = true
    // 创建 AbortController 用于取消请求
    abortController.value = new AbortController()
    ElMessage.info(`开始生成第 ${startEp} 至第 ${Math.max(...pendingEpisodes)} 集，共 ${pendingEpisodes.length} 集...`)
    
    // 启动任务状态轮询
    startTaskPolling()
    
    const res = await novelWriterApi.generateAllEpisodeOutlines(projectId.value, {
      episode_numbers: pendingEpisodes,
      stop_on_error: true
    }, abortController.value.signal)
    
    // 停止轮询
    stopTaskPolling()
    
    if (res.success) {
      ElMessage.success(`分集大纲生成完成！成功 ${res.data.completed_count} 集，失败 ${res.data.failed_count} 集`)
      
      // 先刷新项目信息
      await loadProject()
      
      // 然后刷新分集大纲列表
      await loadEpisodeOutlines()
      
      console.log('[分集大纲] 批量生成完成，列表已刷新')
    }
  } catch (error) {
    // 停止轮询
    stopTaskPolling()
    // 如果是请求被取消（包括用户取消确认框或API请求被取消）
    if (error === 'cancel' || error?.cancelled) {
      console.log('[分集大纲] 批量生成被取消')
      return
    }
    console.error('[分集大纲] 批量生成失败:', error)
    ElMessage.error('生成分集大纲失败')
  } finally {
    generatingEpisodeOutlines.value = false
    abortController.value = null
    // 清除任务状态
    taskStore.clearTask()
  }
}

// 生成单集详细大纲
async function handleGenerateSingleEpisodeOutline(episodeNum) {
  generatingSingleEpisode.value = episodeNum
  try {
    ElMessage.info(`正在生成第 ${episodeNum} 集详细大纲...`)
    
    // 首先尝试带干预的生成
    const res = await novelWriterApi.generateOutlineWithIntervention(projectId.value, episodeNum, {
      content_type: 'series_script'
    })
    
    if (res.success) {
      const status = res.data?.status
      
      if (status === 'need_intervention') {
        // 需要用户干预，显示干预对话框
        showInterventionDialog(episodeNum, res.data)
        return
      } else if (status === 'success' || status === 'completed') {
        // 生成成功
        ElMessage.success(`第 ${episodeNum} 集详细大纲生成成功`)
        
        // 先刷新项目信息（后端已保存大纲到 project.episode_outlines）
        await loadProject()
        
        // 然后刷新分集大纲列表
        await loadEpisodeOutlines()
        
        console.log('[分集大纲] 第', episodeNum, '集生成完成，列表已刷新')
      } else if (status === 'skipped') {
        ElMessage.info(`第 ${episodeNum} 集已跳过`)
      } else {
        ElMessage.error(res.data?.message || '生成失败')
      }
    } else {
      ElMessage.error(res.data?.error_message || res.data?.message || '生成失败')
    }
  } catch (error) {
    // 如果是请求被取消，静默处理
    if (error?.cancelled) {
      console.log('[分集大纲] 生成请求被取消')
      return
    }
    console.error('[分集大纲] 生成失败:', error)
    ElMessage.error(`第 ${episodeNum} 集详细大纲生成失败`)
  } finally {
    generatingSingleEpisode.value = null
  }
}

// 查看分集大纲详情
async function showEpisodeOutlineDetail(outline) {
  try {
    const res = await novelWriterApi.getEpisodeOutline(projectId.value, outline.episode_number)
    if (res.success && res.data) {
      currentOutlineDetail.value = {
        episode_number: outline.episode_number,
        episode_title: outline.episode_title || `第${outline.episode_number}集`,
        raw_content: res.data.detailed_outline || ''
      }
      outlineDetailVisible.value = true
    }
  } catch (error) {
    console.error('获取分集大纲详情失败', error)
    ElMessage.error('获取大纲详情失败')
  }
}

// 开始编辑大纲
function startEditOutline() {
  outlineEditContent.value = currentOutlineDetail.value.raw_content
  outlineEditTitle.value = currentOutlineDetail.value.episode_title
  outlineEditMode.value = true
}

// 取消编辑大纲
function cancelEditOutline() {
  outlineEditMode.value = false
  outlineEditContent.value = ''
  outlineEditTitle.value = ''
}

// 保存编辑的大纲
async function saveOutlineEdit() {
  if (!outlineEditContent.value.trim()) {
    ElMessage.warning('大纲内容不能为空')
    return
  }
  
  savingOutlineEdit.value = true
  try {
    const res = await novelWriterApi.updateEpisodeOutline(
      projectId.value,
      currentOutlineDetail.value.episode_number,
      {
        episode_title: outlineEditTitle.value,
        detailed_outline: outlineEditContent.value
      }
    )
    
    if (res.success) {
      // 更新当前显示的内容
      currentOutlineDetail.value.episode_title = outlineEditTitle.value
      currentOutlineDetail.value.raw_content = outlineEditContent.value
      outlineEditMode.value = false
      
      // 刷新列表
      await loadEpisodeOutlines()
      
      ElMessage.success('大纲已保存')
    }
  } catch (error) {
    console.error('保存大纲失败', error)
    ElMessage.error('保存失败')
  } finally {
    savingOutlineEdit.value = false
  }
}

// 下载单集大纲（从弹窗）
function downloadSingleEpisodeOutline() {
  const content = currentOutlineDetail.value.raw_content
  if (!content) {
    ElMessage.warning('暂无内容可下载')
    return
  }
  
  const episodeNum = currentOutlineDetail.value.episode_number
  const episodeTitle = currentOutlineDetail.value.episode_title
  const fileName = `${project.value?.title || '剧本'}_第${episodeNum}集_${episodeTitle}.md`
  
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.click()
  URL.revokeObjectURL(url)
  
  ElMessage.success('下载成功')
}

// 下载单集大纲（从列表直接下载）
async function downloadEpisodeOutline(outline) {
  try {
    const res = await novelWriterApi.getEpisodeOutline(projectId.value, outline.episode_number)
    if (res.success && res.data?.detailed_outline) {
      const content = res.data.detailed_outline
      const fileName = `${project.value?.title || '剧本'}_第${outline.episode_number}集_${outline.episode_title}.md`
      
      const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      a.click()
      URL.revokeObjectURL(url)
      
      ElMessage.success('下载成功')
    } else {
      ElMessage.warning('暂无内容可下载')
    }
  } catch (error) {
    console.error('下载大纲失败', error)
    ElMessage.error('下载失败')
  }
}

// 下载全部分集大纲
async function downloadAllEpisodeOutlines() {
  const generatedOutlines = episodeOutlines.value.filter(e => e.has_detailed)
  
  if (generatedOutlines.length === 0) {
    ElMessage.warning('暂无已生成的大纲可下载')
    return
  }
  
  try {
    // 获取所有已生成的大纲内容
    const promises = generatedOutlines.map(outline => 
      novelWriterApi.getEpisodeOutline(projectId.value, outline.episode_number)
    )
    
    const results = await Promise.all(promises)
    
    // 合并内容
    let mergedContent = `# ${project.value?.title || '剧本'} - 分集详细大纲\n\n`
    mergedContent += `> 共 ${generatedOutlines.length} 集\n\n`
    mergedContent += `---\n\n`
    
    results.forEach((res, index) => {
      const outline = generatedOutlines[index]
      if (res.success && res.data?.detailed_outline) {
        mergedContent += `## 第${outline.episode_number}集 ${outline.episode_title}\n\n`
        mergedContent += res.data.detailed_outline
        mergedContent += '\n\n---\n\n'
      }
    })
    
    const fileName = `${project.value?.title || '剧本'}_分集详细大纲_全集.md`
    const blob = new Blob([mergedContent], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success(`已下载 ${generatedOutlines.length} 集大纲`)
  } catch (error) {
    console.error('下载全部大纲失败', error)
    ElMessage.error('下载失败')
  }
}

// 下载全部分集正文
async function downloadAllEpisodeContent() {
  const generatedContents = episodeOutlines.value.filter(e => e.content_status === 'generated')
  
  if (generatedContents.length === 0) {
    ElMessage.warning('暂无已生成的正文可下载')
    return
  }
  
  try {
    ElMessage.info('正在获取正文内容...')
    
    // 调用后端API获取全部正文
    const res = await novelWriterApi.getAllEpisodeContent(projectId.value)
    
    if (!res.success || !res.data?.contents?.length) {
      ElMessage.warning('暂无正文内容可下载')
      return
    }
    
    const contents = res.data.contents
    const projectTitle = res.data.project_title || '剧本'
    
    // 合并内容
    let mergedContent = `# ${projectTitle} - 分集正文\n\n`
    mergedContent += `> 共 ${contents.length} 集\n\n`
    mergedContent += `---\n\n`
    
    contents.forEach((item) => {
      mergedContent += `## 第${item.episode_number}集 ${item.chapter_title}\n\n`
      mergedContent += item.content
      mergedContent += '\n\n---\n\n'
    })
    
    const fileName = `${projectTitle}_分集正文_全集.md`
    const blob = new Blob([mergedContent], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success(`已下载 ${contents.length} 集正文`)
  } catch (error) {
    console.error('下载全部正文失败', error)
    ElMessage.error('下载失败')
  }
}

// 辅助函数
// 开始编辑分集大纲标题
function startEditEpisodeTitle(outline) {
  editingEpisodeTitle.value = outline.episode_number
  editEpisodeTitleValue.value = outline.episode_title || ''
}

// 取消编辑分集大纲标题
function cancelEditEpisodeTitle() {
  editingEpisodeTitle.value = null
  editEpisodeTitleValue.value = ''
}

// 保存分集大纲标题
async function saveEpisodeTitle(outline) {
  if (!editEpisodeTitleValue.value.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }

  // 如果没有变化，直接关闭编辑模式
  if (editEpisodeTitleValue.value === outline.episode_title) {
    editingEpisodeTitle.value = null
    return
  }

  try {
    const res = await novelWriterApi.updateEpisodeOutline(
      projectId.value, 
      outline.episode_number, 
      { episode_title: editEpisodeTitleValue.value }
    )
    
    if (res.success) {
      // 更新本地数据
      outline.episode_title = editEpisodeTitleValue.value
      editingEpisodeTitle.value = null
      ElMessage.success('集标题已更新')
    }
  } catch (error) {
    console.error('更新集标题失败', error)
    ElMessage.error('更新失败')
  }
}

// 终止生成
function handleStopGeneration() {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
  }
  
  generating.value = false
  selectedEpisode.value = null
  selectedChapter.value = null
  selectedScene.value = null
  
  ElMessage.warning('已终止生成')
}


// ==================== 批量正文生成方法 ====================

// 批量生成剧集正文（支持断点续传）
async function handleGenerateAllEpisodeContent(episodeNumbers = null) {
  const totalEp = totalEpisodeCount.value
  if (totalEp === 0) { ElMessage.warning('请先设置集数'); return }
  
  // 断点续传：计算未生成正文的集数（需要有详细大纲且正文未生成）
  const episodesWithOutline = episodeOutlines.value.filter(ep => ep.has_detailed)
  if (episodesWithOutline.length === 0) {
    ElMessage.warning('请先生成分集详细大纲')
    return
  }
  
  // 如果传入了指定的集数列表，使用它；否则使用断点续传逻辑
  let pendingEpisodes
  if (episodeNumbers && Array.isArray(episodeNumbers)) {
    // 过滤出有大纲的集数
    pendingEpisodes = episodeNumbers.filter(n => episodesWithOutline.some(ep => ep.episode_number === n))
    if (pendingEpisodes.length === 0) {
      ElMessage.warning('指定的集数没有详细大纲，请先生成大纲')
      return
    }
  } else {
    const existingContent = episodesWithOutline
      .filter(ep => ep.content_status === 'generated')
      .map(ep => ep.episode_number)
    
    const allEpisodeNumbers = episodesWithOutline.map(ep => ep.episode_number)
    pendingEpisodes = allEpisodeNumbers.filter(ep => !existingContent.includes(ep))
  }
  
  if (pendingEpisodes.length === 0) {
    ElMessage.success('全部分集正文已生成，无需重复生成')
    return
  }
  
  // 构建确认消息
  const startEp = Math.min(...pendingEpisodes)
  const confirmMsg = `将生成第 ${startEp} 至第 ${Math.max(...pendingEpisodes)} 集，共 ${pendingEpisodes.length} 集的正文。确定继续吗？`
  
  try {
    await ElMessageBox.confirm(confirmMsg, '确认批量生成', { type: 'info' })
    
    // 设置任务状态
    taskStore.setTask({
      project_id: projectId.value,
      task_type: 'episode_content',
      status: 'running',
      total_count: pendingEpisodes.length,
      completed_count: 0
    })
    
    generatingAllContent.value = true
    batchContentType.value = 'episode'
    abortController.value = new AbortController()
    ElMessage.info(`开始生成第 ${startEp} 至第 ${Math.max(...pendingEpisodes)} 集，共 ${pendingEpisodes.length} 集正文...`)
    
    // 启动任务状态轮询
    startTaskPolling()
    
    const res = await novelWriterApi.generateAllEpisodeContent(projectId.value, {
      unit_numbers: pendingEpisodes,
      stop_on_error: true
    }, abortController.value.signal)
    
    // 停止轮询
    stopTaskPolling()
    
    if (res.success) {
      ElMessage.success('批量生成完成！成功' + res.data.completed_count + '集')
      await loadProject(); await loadChapters(); await loadEpisodeOutlines()
    }
  } catch (error) {
    stopTaskPolling()
    if (error?.name === 'CanceledError' || error?.cancelled) { ElMessage.warning('批量生成已终止') }
    else if (error !== 'cancel') { ElMessage.error(error.response?.data?.detail || '批量生成失败') }
  } finally { generatingAllContent.value = false; batchContentType.value = null; abortController.value = null; taskStore.clearTask() }
}

// 批量生成小说正文（支持断点续传）
async function handleGenerateAllChapterContent(chapterNumbers = null) {
  const totalCh = totalChapterOutlineCount.value
  if (totalCh === 0) { ElMessage.warning('请先设置章节数'); return }
  
  // 断点续传：计算未生成正文的章数（需要有详细大纲且正文未生成）
  const chaptersWithOutline = chapterOutlines.value.filter(ch => ch.has_detailed)
  if (chaptersWithOutline.length === 0) {
    ElMessage.warning('请先生成章节详细大纲')
    return
  }
  
  // 如果传入了指定的章节列表，使用它；否则使用断点续传逻辑
  let pendingChapters
  if (chapterNumbers && Array.isArray(chapterNumbers)) {
    // 过滤出有大纲的章数
    pendingChapters = chapterNumbers.filter(n => chaptersWithOutline.some(ch => ch.chapter_number === n))
    if (pendingChapters.length === 0) {
      ElMessage.warning('指定的章节没有详细大纲，请先生成大纲')
      return
    }
  } else {
    const existingContent = chaptersWithOutline
      .filter(ch => ch.content_status === 'generated')
      .map(ch => ch.chapter_number)
    
    const allChapterNumbers = chaptersWithOutline.map(ch => ch.chapter_number)
    pendingChapters = allChapterNumbers.filter(ch => !existingContent.includes(ch))
  }
  
  if (pendingChapters.length === 0) {
    ElMessage.success('全部章节正文已生成，无需重复生成')
    return
  }
  
  // 构建确认消息
  const startCh = Math.min(...pendingChapters)
  const confirmMsg = `将生成第 ${startCh} 至第 ${Math.max(...pendingChapters)} 章，共 ${pendingChapters.length} 章的正文。确定继续吗？`
  
  try {
    await ElMessageBox.confirm(confirmMsg, '确认批量生成', { type: 'info' })
    
    // 设置任务状态
    taskStore.setTask({
      project_id: projectId.value,
      task_type: 'chapter_content',
      status: 'running',
      total_count: pendingChapters.length,
      completed_count: 0
    })
    
    generatingAllContent.value = true
    batchContentType.value = 'chapter'
    abortController.value = new AbortController()
    ElMessage.info(`开始生成第 ${startCh} 至第 ${Math.max(...pendingChapters)} 章，共 ${pendingChapters.length} 章正文...`)
    
    // 启动任务状态轮询
    startTaskPolling()
    
    const res = await novelWriterApi.generateAllChapterContent(projectId.value, {
      unit_numbers: pendingChapters,
      stop_on_error: true
    }, abortController.value.signal)
    
    // 停止轮询
    stopTaskPolling()
    
    if (res.success) {
      ElMessage.success('批量生成完成！成功' + res.data.completed_count + '章')
      await loadProject(); await loadChapters(); await loadChapterOutlines()
    }
  } catch (error) {
    stopTaskPolling()
    if (error?.name === 'CanceledError' || error?.cancelled) { ElMessage.warning('批量生成已终止') }
    else if (error !== 'cancel') { ElMessage.error(error.response?.data?.detail || '批量生成失败') }
  } finally { generatingAllContent.value = false; batchContentType.value = null; abortController.value = null; taskStore.clearTask() }
}

// 批量生成电影正文（支持断点续传）
async function handleGenerateAllSceneContent(sceneNumbers = null) {
  const totalSc = totalSceneOutlineCount.value
  if (totalSc === 0) { ElMessage.warning('请先设置场景数'); return }
  
  // 断点续传：计算未生成正文的场数（需要有详细大纲且正文未生成）
  const scenesWithOutline = sceneOutlines.value.filter(sc => sc.has_detailed)
  if (scenesWithOutline.length === 0) {
    ElMessage.warning('请先生成场景详细大纲')
    return
  }
  
  // 如果传入了指定的场景列表，使用它；否则使用断点续传逻辑
  let pendingScenes
  if (sceneNumbers && Array.isArray(sceneNumbers)) {
    // 过滤出有大纲的场数
    pendingScenes = sceneNumbers.filter(n => scenesWithOutline.some(sc => sc.scene_number === n))
    if (pendingScenes.length === 0) {
      ElMessage.warning('指定的场景没有详细大纲，请先生成大纲')
      return
    }
  } else {
    const existingContent = scenesWithOutline
      .filter(sc => sc.content_status === 'generated')
      .map(sc => sc.scene_number)
    
    const allSceneNumbers = scenesWithOutline.map(sc => sc.scene_number)
    pendingScenes = allSceneNumbers.filter(sc => !existingContent.includes(sc))
  }
  
  if (pendingScenes.length === 0) {
    ElMessage.success('全部场景正文已生成，无需重复生成')
    return
  }
  
  // 构建确认消息
  const startSc = Math.min(...pendingScenes)
  const confirmMsg = `将生成第 ${startSc} 至第 ${Math.max(...pendingScenes)} 场，共 ${pendingScenes.length} 场的正文。确定继续吗？`
  
  try {
    await ElMessageBox.confirm(confirmMsg, '确认批量生成', { type: 'info' })
    
    // 设置任务状态
    taskStore.setTask({
      project_id: projectId.value,
      task_type: 'scene_content',
      status: 'running',
      total_count: pendingScenes.length,
      completed_count: 0
    })
    
    generatingAllContent.value = true
    batchContentType.value = 'scene'
    abortController.value = new AbortController()
    ElMessage.info(`开始生成第 ${startSc} 至第 ${Math.max(...pendingScenes)} 场，共 ${pendingScenes.length} 场正文...`)
    
    // 启动任务状态轮询
    startTaskPolling()
    
    const res = await novelWriterApi.generateAllSceneContent(projectId.value, {
      unit_numbers: pendingScenes,
      stop_on_error: true
    }, abortController.value.signal)
    
    // 停止轮询
    stopTaskPolling()
    
    if (res.success) {
      ElMessage.success('批量生成完成！成功' + res.data.completed_count + '场')
      await loadProject(); await loadChapters(); await loadSceneOutlines()
    }
  } catch (error) {
    stopTaskPolling()
    if (error?.name === 'CanceledError' || error?.cancelled) { ElMessage.warning('批量生成已终止') }
    else if (error !== 'cancel') { ElMessage.error(error.response?.data?.detail || '批量生成失败') }
  } finally { generatingAllContent.value = false; batchContentType.value = null; abortController.value = null; taskStore.clearTask() }
}

// 终止批量生成
function handleStopBatchGeneration() {
  // 停止轮询
  stopTaskPolling()
  if (abortController.value) { abortController.value.abort(); abortController.value = null }
  generatingAllContent.value = false
  batchContentType.value = null
  // 同时调用后端取消任务
  taskStore.cancelTask(projectId.value)
  ElMessage.warning('已终止批量生成')
}

// ==================== 指定数量生成对话框相关方法 ====================

// 打开指定数量生成对话框
function openBatchCountDialog(type, contentType) {
  // type: 'outline' 或 'content'
  // contentType: 'chapter', 'episode', 'scene'
  
  let defaultStart = 1
  let maxUnit = 100
  let unitLabel = '章'
  
  if (type === 'outline') {
    if (contentType === 'chapter') {
      const existing = chapterOutlines.value.filter(o => o.has_detailed).map(o => o.chapter_number)
      defaultStart = existing.length > 0 ? Math.max(...existing) + 1 : 1
      maxUnit = totalChapterOutlineCount.value || 100
      unitLabel = '章'
    } else if (contentType === 'episode') {
      const existing = episodeOutlines.value.filter(o => o.has_detailed).map(o => o.episode_number)
      defaultStart = existing.length > 0 ? Math.max(...existing) + 1 : 1
      maxUnit = totalEpisodeCount.value || 100
      unitLabel = '集'
    } else if (contentType === 'scene') {
      const existing = sceneOutlines.value.filter(o => o.has_detailed).map(o => o.scene_number)
      defaultStart = existing.length > 0 ? Math.max(...existing) + 1 : 1
      maxUnit = totalSceneOutlineCount.value || 100
      unitLabel = '场'
    }
  } else {
    // 正文生成：基于已有大纲但未生成正文的单元
    if (contentType === 'chapter') {
      const chaptersWithOutline = chapterOutlines.value.filter(ch => ch.has_detailed)
      const existingContent = chaptersWithOutline.filter(ch => ch.content_status === 'generated').map(ch => ch.chapter_number)
      const pending = chaptersWithOutline.map(ch => ch.chapter_number).filter(n => !existingContent.includes(n))
      defaultStart = pending.length > 0 ? Math.min(...pending) : 1
      maxUnit = totalChapterOutlineCount.value || 100
      unitLabel = '章'
    } else if (contentType === 'episode') {
      const episodesWithOutline = episodeOutlines.value.filter(ep => ep.has_detailed)
      const existingContent = episodesWithOutline.filter(ep => ep.content_status === 'generated').map(ep => ep.episode_number)
      const pending = episodesWithOutline.map(ep => ep.episode_number).filter(n => !existingContent.includes(n))
      defaultStart = pending.length > 0 ? Math.min(...pending) : 1
      maxUnit = totalEpisodeCount.value || 100
      unitLabel = '集'
    } else if (contentType === 'scene') {
      const scenesWithOutline = sceneOutlines.value.filter(sc => sc.has_detailed)
      const existingContent = scenesWithOutline.filter(sc => sc.content_status === 'generated').map(sc => sc.scene_number)
      const pending = scenesWithOutline.map(sc => sc.scene_number).filter(n => !existingContent.includes(n))
      defaultStart = pending.length > 0 ? Math.min(...pending) : 1
      maxUnit = totalSceneOutlineCount.value || 100
      unitLabel = '场'
    }
  }
  
  batchCountConfig.value = {
    startUnit: defaultStart,
    count: 5,
    maxUnit: maxUnit,
    unitLabel: unitLabel,
    type: type,
    contentType: contentType
  }
  showBatchCountDialog.value = true
}

// 执行指定数量生成
async function executeBatchCountGenerate() {
  const { startUnit, count, type, contentType, maxUnit } = batchCountConfig.value
  
  // 计算单元号列表（不超过最大单元数）
  const endUnit = Math.min(startUnit + count - 1, maxUnit)
  const unitNumbers = Array.from({ length: endUnit - startUnit + 1 }, (_, i) => startUnit + i)
  
  showBatchCountDialog.value = false
  
  // 根据类型调用对应的批量生成方法
  if (type === 'outline') {
    if (contentType === 'chapter') {
      await handleGenerateAllChapterOutlines(unitNumbers)
    } else if (contentType === 'episode') {
      await handleGenerateAllEpisodeOutlines(unitNumbers)
    } else if (contentType === 'scene') {
      await handleGenerateAllSceneOutlines(unitNumbers)
    }
  } else {
    if (contentType === 'chapter') {
      await handleGenerateAllChapterContent(unitNumbers)
    } else if (contentType === 'episode') {
      await handleGenerateAllEpisodeContent(unitNumbers)
    } else if (contentType === 'scene') {
      await handleGenerateAllSceneContent(unitNumbers)
    }
  }
}

// 统一的任务取消处理（用于页面刷新后恢复的终止按钮）
async function handleCancelTask() {
  const confirmed = await ElMessageBox.confirm(
    '确定要终止当前生成任务吗？',
    '确认终止',
    { type: 'warning' }
  ).catch(() => false)
  
  if (confirmed) {
    // 先中止本地 AbortController
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    
    // 重置所有生成状态
    generatingEpisodeOutlines.value = false
    generatingChapterOutlines.value = false
    generatingSceneOutlines.value = false
    generatingAllContent.value = false
    batchContentType.value = null
    
    // 调用后端取消任务
    const success = await taskStore.cancelTask(projectId.value)
    
    if (success) {
      // 停止任务轮询
      stopTaskPolling()
      ElMessage.warning('已终止生成任务')
      
      // 刷新数据
      await loadProject()
      if (taskStore.isOutlineTask()) {
        if (project.value.content_type === 'series_script') {
          await loadEpisodeOutlines()
        } else if (project.value.content_type === 'novel') {
          await loadChapterOutlines()
        } else if (project.value.content_type === 'movie_script') {
          await loadSceneOutlines()
        }
      }
    }
  }
}


// 生成分集正文
async function generateEpisodeContent(outline) {
  const episodeNum = outline.episode_number
  
  // 检查是否有分集详细大纲
  if (!outline.has_detailed) {
    ElMessage.warning('请先生成分集详细大纲')
    return
  }
  
  try {
    // 如果正文已生成，提示用户确认
    if (outline.content_status === 'generated') {
      await ElMessageBox.confirm(
        `第${episodeNum}集正文已生成，重新生成将覆盖原有内容。确定要继续吗？`,
        '确认重新生成',
        { type: 'warning' }
      )
    } else {
      await ElMessageBox.confirm(
        `确定要生成第${episodeNum}集的正文吗？可能需要较长时间。`,
        '确认生成',
        { type: 'info' }
      )
    }
    
    generating.value = true
    selectedEpisode.value = episodeNum
    ElMessage.info(`开始生成第${episodeNum}集正文...`)
    
    // 创建 AbortController
    abortController.value = new AbortController()
    
    // 调用新的单集正文生成API
    const res = await novelWriterApi.generateEpisodeContent(projectId.value, episodeNum, abortController.value.signal)
    
    if (res.success) {
      ElMessage.success(`第${episodeNum}集正文生成成功，共${res.data.word_count}字`)
      
      // 刷新项目信息和章节列表
      await loadProject()
      await loadChapters()
      
      // 自动选中新章节并显示内容
      if (res.data.chapter) {
        const newChapter = {
          ...res.data.chapter,
          chapter_number: res.data.chapter.chapter_number,
          chapter_title: res.data.chapter.chapter_title,
          status: 'completed',
          word_count: res.data.chapter.word_count
        }
        selectChapter(newChapter)
        chapterContent.value = res.data.content
      }
    } else {
      ElMessage.error(res.data?.error_message || '生成失败')
    }
  } catch (error) {
    if (error?.name === 'CanceledError' || error?.cancelled) {
      console.log('生成已被用户取消')
    } else if (error !== 'cancel') {
      console.error('生成分集正文失败:', error)
      ElMessage.error(error.response?.data?.detail || '生成失败')
    }
  } finally {
    generating.value = false
    selectedEpisode.value = null
    abortController.value = null
  }
}

// 生成小说章节正文
async function generateChapterContent(outline) {
  const chapterNum = outline.chapter_number
  
  // 检查是否有章节详细大纲
  if (!outline.has_detailed) {
    ElMessage.warning('请先生成章节详细大纲')
    return
  }
  
  try {
    // 如果正文已生成，提示用户确认
    if (outline.content_status === 'generated') {
      await ElMessageBox.confirm(
        `第${chapterNum}章正文已生成，重新生成将覆盖原有内容。确定要继续吗？`,
        '确认重新生成',
        { type: 'warning' }
      )
    } else {
      await ElMessageBox.confirm(
        `确定要生成第${chapterNum}章的正文吗？可能需要较长时间。`,
        '确认生成',
        { type: 'info' }
      )
    }
    
    generating.value = true
    selectedChapter.value = chapterNum
    ElMessage.info(`开始生成第${chapterNum}章正文...`)
    
    // 创建 AbortController
    abortController.value = new AbortController()
    
    // 调用章节正文生成API
    const res = await novelWriterApi.generateChapterContent(projectId.value, chapterNum, abortController.value.signal)
    
    if (res.success) {
      ElMessage.success(`第${chapterNum}章正文生成成功，共${res.data.word_count}字`)
      
      // 刷新项目信息和章节列表
      await loadProject()
      await loadChapters()
      await loadChapterOutlines()
      
      // 自动选中新章节并显示内容
      if (res.data.chapter) {
        const newChapter = {
          ...res.data.chapter,
          chapter_number: res.data.chapter.chapter_number,
          chapter_title: res.data.chapter.chapter_title,
          status: 'completed',
          word_count: res.data.chapter.word_count
        }
        selectChapter(newChapter)
        chapterContent.value = res.data.content
      }
    } else {
      ElMessage.error(res.data?.error_message || '生成失败')
    }
  } catch (error) {
    if (error?.name === 'CanceledError' || error?.cancelled) {
      console.log('生成已被用户取消')
    } else if (error !== 'cancel') {
      console.error('生成章节正文失败:', error)
      ElMessage.error(error.response?.data?.detail || '生成失败')
    }
  } finally {
    generating.value = false
    selectedChapter.value = null
    abortController.value = null
  }
}

// 生成电影场景正文
async function generateSceneContent(outline) {
  const sceneNum = outline.scene_number
  
  // 检查是否有场景详细大纲
  if (!outline.has_detailed) {
    ElMessage.warning('请先生成场景详细大纲')
    return
  }
  
  try {
    // 如果正文已生成，提示用户确认
    if (outline.content_status === 'generated') {
      await ElMessageBox.confirm(
        `第${sceneNum}场正文已生成，重新生成将覆盖原有内容。确定要继续吗？`,
        '确认重新生成',
        { type: 'warning' }
      )
    } else {
      await ElMessageBox.confirm(
        `确定要生成第${sceneNum}场的正文吗？可能需要较长时间。`,
        '确认生成',
        { type: 'info' }
      )
    }
    
    generating.value = true
    selectedScene.value = sceneNum
    ElMessage.info(`开始生成第${sceneNum}场正文...`)
    
    // 创建 AbortController
    abortController.value = new AbortController()
    
    // 调用场景正文生成API
    const res = await novelWriterApi.generateSceneContent(projectId.value, sceneNum, abortController.value.signal)
    
    if (res.success) {
      ElMessage.success(`第${sceneNum}场正文生成成功，共${res.data.word_count}字`)
      
      // 刷新项目信息和章节列表
      await loadProject()
      await loadChapters()
      await loadSceneOutlines()
      
      // 自动选中新章节并显示内容
      if (res.data.chapter || res.data.content) {
        const newChapter = {
          id: res.data.chapter?.id,
          chapter_number: sceneNum,
          chapter_title: res.data.scene_title || `第${sceneNum}场`,
          status: 'completed',
          word_count: res.data.word_count
        }
        selectChapter(newChapter)
        chapterContent.value = res.data.content
      }
    } else {
      ElMessage.error(res.data?.error_message || '生成失败')
    }
  } catch (error) {
    if (error?.name === 'CanceledError' || error?.cancelled) {
      console.log('生成已被用户取消')
    } else if (error !== 'cancel') {
      console.error('生成场景正文失败:', error)
      ElMessage.error(error.response?.data?.detail || '生成失败')
    }
  } finally {
    generating.value = false
    selectedScene.value = null
    abortController.value = null
  }
}

// ==================== 章节详细大纲相关方法（小说专用） ====================

// 加载章节大纲列表
async function loadChapterOutlines() {
  if (project.value?.content_type !== 'novel') {
    return
  }
  
  try {
    const res = await novelWriterApi.getChapterOutlines(projectId.value)
    
    if (res.success && res.data) {
      const chapters = res.data.chapters || []
      
      chapterOutlines.value = chapters.map(ch => ({
        chapter_number: ch.chapter_number,
        chapter_title: ch.chapter_title || `第${ch.chapter_number}章`,
        has_detailed: ch.status === 'generated' || ch.status === 'edited',
        content_status: ch.content_status || null,
        content_word_count: ch.content_word_count || 0,
        ...ch
      }))
    }
  } catch (error) {
    console.error('加载章节大纲失败', error)
  }
}

// 一键生成全部章节大纲（支持断点续传）
async function handleGenerateAllChapterOutlines(chapterNumbers = null) {
  const totalCh = totalChapterOutlineCount.value
  if (totalCh === 0) {
    ElMessage.warning('请先设置章节数')
    return
  }
  
  // 如果传入了指定的章节列表，使用它；否则使用断点续传逻辑
  let pendingChapters
  if (chapterNumbers && Array.isArray(chapterNumbers)) {
    pendingChapters = chapterNumbers
  } else {
    // 断点续传：计算未生成的章数
    const existingChapters = chapterOutlines.value
      .filter(ch => ch.has_detailed)
      .map(ch => ch.chapter_number)
    
    const allChapters = Array.from({ length: totalCh }, (_, i) => i + 1)
    pendingChapters = allChapters.filter(ch => !existingChapters.includes(ch))
  }
  
  if (pendingChapters.length === 0) {
    ElMessage.success('全部章节大纲已生成，无需重复生成')
    return
  }
  
  // 构建确认消息
  const startCh = Math.min(...pendingChapters)
  const confirmMsg = pendingChapters.length !== totalCh
    ? `将生成第 ${startCh} 至第 ${Math.max(...pendingChapters)} 章，共 ${pendingChapters.length} 章。确定继续吗？`
    : `确定要生成全部 ${pendingChapters.length} 章的详细大纲吗？这可能需要较长时间。`
  
  try {
    await ElMessageBox.confirm(confirmMsg, '确认生成', { type: 'info' })
    
    // 设置任务状态
    taskStore.setTask({
      project_id: projectId.value,
      task_type: 'chapter_outline',
      status: 'running',
      total_count: pendingChapters.length,
      completed_count: 0
    })
    
    generatingChapterOutlines.value = true
    // 创建 AbortController 用于取消请求
    abortController.value = new AbortController()
    ElMessage.info(`开始生成第 ${startCh} 至第 ${Math.max(...pendingChapters)} 章，共 ${pendingChapters.length} 章...`)
    
    // 启动任务状态轮询
    startTaskPolling()
    
    const res = await novelWriterApi.generateAllChapterOutlines(projectId.value, {
      chapter_numbers: pendingChapters,
      stop_on_error: true
    }, abortController.value.signal)
    
    // 停止轮询
    stopTaskPolling()
    
    if (res.success) {
      ElMessage.success(`章节大纲生成完成！成功 ${res.data.completed_count} 章，失败 ${res.data.failed_count} 章`)
      await loadProject()
      await loadChapterOutlines()
    }
  } catch (error) {
    // 停止轮询
    stopTaskPolling()
    if (error === 'cancel' || error?.cancelled) {
      return
    }
    console.error('生成章节大纲失败:', error)
    ElMessage.error('生成章节大纲失败')
  } finally {
    generatingChapterOutlines.value = false
    abortController.value = null
    // 清除任务状态
    taskStore.clearTask()
  }
}

// 生成单章详细大纲（带用户干预支持）
async function handleGenerateSingleChapterOutline(chapterNum, forceRegenerate = false) {
  generatingSingleChapterOutline.value = chapterNum
  try {
    ElMessage.info(`正在生成第 ${chapterNum} 章详细大纲...`)
    
    // 首先尝试带干预的生成
    const res = await novelWriterApi.generateOutlineWithIntervention(projectId.value, chapterNum, {
      content_type: project.value?.content_type || 'novel',
      force_regenerate: forceRegenerate
    })
    
    if (res.success) {
      const status = res.data?.status
      
      if (status === 'need_intervention') {
        // 需要用户干预，显示干预对话框
        showInterventionDialog(chapterNum, res.data)
        return
      } else if (status === 'already_exists') {
        // 已存在详细大纲，显示提示
        ElMessage.info(`第 ${chapterNum} 章已存在详细大纲，如需重新生成请点击强制重新生成`)
        return
      } else if (status === 'success' || status === 'completed') {
        // 生成成功
        ElMessage.success(`第 ${chapterNum} 章详细大纲生成成功`)
        await loadProject()
        await loadChapterOutlines()
      } else if (status === 'skipped') {
        ElMessage.info(`第 ${chapterNum} 章已跳过`)
      } else {
        ElMessage.error(res.data?.message || '生成失败')
      }
    } else {
      ElMessage.error(res.data?.error_message || res.data?.message || '生成失败')
    }
  } catch (error) {
    if (error?.cancelled) {
      return
    }
    console.error('生成章节大纲失败:', error)
    ElMessage.error(`第 ${chapterNum} 章详细大纲生成失败`)
  } finally {
    generatingSingleChapterOutline.value = null
  }
}

// 显示用户干预对话框
function showInterventionDialog(unitNumber, data) {
  interventionData.value = {
    unit_number: unitNumber,
    content_type: project.value?.content_type || 'novel',
    inferred_summary: data.inferred_summary || '',
    reference_info: data.reference_info || null,
    message: data.message || '缺少原始概要，请选择处理方式'
  }
  interventionUserChoice.value = ''
  interventionUserGuidance.value = ''
  interventionDialogVisible.value = true
}

// 用户干预确认处理
async function handleInterventionConfirm() {
  if (!interventionUserChoice.value) {
    ElMessage.warning('请选择处理方式')
    return
  }
  
  if (interventionUserChoice.value === 'provide' && !interventionUserGuidance.value.trim()) {
    ElMessage.warning('请输入章节概要内容')
    return
  }
  
  interventionLoading.value = true
  
  try {
    const res = await novelWriterApi.generateOutlineWithIntervention(
      projectId.value,
      interventionData.value.unit_number,
      {
        content_type: interventionData.value.content_type,
        user_choice: interventionUserChoice.value,
        user_guidance: interventionUserChoice.value === 'provide' ? interventionUserGuidance.value.trim() : null
      }
    )
    
    if (res.success) {
      const status = res.data?.status
      
      if (status === 'success' || status === 'completed') {
        ElMessage.success(`第 ${interventionData.value.unit_number} 单元详细大纲生成成功`)
        interventionDialogVisible.value = false
        await loadProject()
        await loadChapterOutlines()
      } else if (status === 'skipped') {
        ElMessage.info(`第 ${interventionData.value.unit_number} 单元已跳过`)
        interventionDialogVisible.value = false
        await loadChapterOutlines()
      } else if (status === 'show_reference') {
        // 显示相邻章节参考信息
        interventionData.value.reference_info = {
          prev_unit: res.data.previous_unit,
          next_unit: res.data.next_unit
        }
        // 显示参考信息提示
        ElMessage.info('已获取相邻章节信息，请参考后选择处理方式')
        // 保持对话框打开，让用户看到参考信息后做决定
      } else if (status === 'need_guidance') {
        ElMessage.warning('请输入章节概要内容')
      } else {
        ElMessage.error(res.data?.message || '处理失败')
      }
    } else {
      ElMessage.error(res.data?.message || '处理失败')
    }
  } catch (error) {
    console.error('干预处理失败:', error)
    ElMessage.error('处理失败')
  } finally {
    interventionLoading.value = false
  }
}

// 用户干预取消处理
function handleInterventionCancel() {
  interventionDialogVisible.value = false
  generatingSingleChapterOutline.value = null
}

// 查看章节大纲详情
async function showChapterOutlineDetail(outline) {
  try {
    const res = await novelWriterApi.getChapterOutline(projectId.value, outline.chapter_number)
    if (res.success && res.data) {
      currentChapterOutlineDetail.value = {
        chapter_number: outline.chapter_number,
        chapter_title: outline.chapter_title || `第${outline.chapter_number}章`,
        raw_content: res.data.detailed_outline || '',
        revision_info: res.data.revision_info || null,
        original_content: res.data.original_content || null
      }
      chapterOutlineDetailVisible.value = true
    }
  } catch (error) {
    console.error('获取章节大纲详情失败', error)
    ElMessage.error('获取大纲详情失败')
  }
}

// 显示章节大纲修正对比对话框
function showChapterOutlineRevisionCompare() {
  // 设置原始内容和修正后内容
  chapterOutlineOriginalContent.value = currentChapterOutlineDetail.value.original_content || ''
  chapterOutlineRevisedContent.value = currentChapterOutlineDetail.value.raw_content || ''
  chapterOutlineRevisionInfo.value = currentChapterOutlineDetail.value.revision_info || null
  chapterOutlineRevisionViewMode.value = 'diff'
  chapterOutlineRevisionCompareVisible.value = true
}

// 开始编辑章节大纲
function startEditChapterOutline() {
  chapterOutlineEditContent.value = currentChapterOutlineDetail.value.raw_content
  chapterOutlineEditTitle.value = currentChapterOutlineDetail.value.chapter_title
  chapterOutlineEditMode.value = true
}

// 取消编辑章节大纲
function cancelEditChapterOutline() {
  chapterOutlineEditMode.value = false
  chapterOutlineEditContent.value = ''
  chapterOutlineEditTitle.value = ''
}

// 保存编辑的章节大纲
async function saveChapterOutlineEdit() {
  if (!chapterOutlineEditContent.value.trim()) {
    ElMessage.warning('大纲内容不能为空')
    return
  }
  
  savingChapterOutlineEdit.value = true
  try {
    const res = await novelWriterApi.updateChapterOutline(
      projectId.value,
      currentChapterOutlineDetail.value.chapter_number,
      {
        chapter_title: chapterOutlineEditTitle.value,
        detailed_outline: chapterOutlineEditContent.value
      }
    )
    
    if (res.success) {
      currentChapterOutlineDetail.value.chapter_title = chapterOutlineEditTitle.value
      currentChapterOutlineDetail.value.raw_content = chapterOutlineEditContent.value
      chapterOutlineEditMode.value = false
      await loadChapterOutlines()
      ElMessage.success('大纲已保存')
    }
  } catch (error) {
    console.error('保存章节大纲失败', error)
    ElMessage.error('保存失败')
  } finally {
    savingChapterOutlineEdit.value = false
  }
}

// 下载单章大纲（从弹窗）
function downloadSingleChapterOutline() {
  const content = currentChapterOutlineDetail.value.raw_content
  if (!content) {
    ElMessage.warning('暂无内容可下载')
    return
  }
  
  const chapterNum = currentChapterOutlineDetail.value.chapter_number
  const chapterTitle = currentChapterOutlineDetail.value.chapter_title
  const fileName = `${project.value?.title || '小说'}_第${chapterNum}章_${chapterTitle}.md`
  
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.click()
  URL.revokeObjectURL(url)
  
  ElMessage.success('下载成功')
}

// 下载单章大纲（从列表直接下载）
async function downloadChapterOutline(outline) {
  try {
    const res = await novelWriterApi.getChapterOutline(projectId.value, outline.chapter_number)
    if (res.success && res.data?.detailed_outline) {
      const content = res.data.detailed_outline
      const fileName = `${project.value?.title || '小说'}_第${outline.chapter_number}章_${outline.chapter_title}.md`
      
      const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      a.click()
      URL.revokeObjectURL(url)
      
      ElMessage.success('下载成功')
    } else {
      ElMessage.warning('暂无内容可下载')
    }
  } catch (error) {
    console.error('下载章节大纲失败', error)
    ElMessage.error('下载失败')
  }
}

// 下载全部章节大纲
async function downloadAllChapterOutlines() {
  const generatedOutlines = chapterOutlines.value.filter(c => c.has_detailed)
  
  if (generatedOutlines.length === 0) {
    ElMessage.warning('暂无已生成的大纲可下载')
    return
  }
  
  try {
    const promises = generatedOutlines.map(outline => 
      novelWriterApi.getChapterOutline(projectId.value, outline.chapter_number)
    )
    
    const results = await Promise.all(promises)
    
    let mergedContent = `# ${project.value?.title || '小说'} - 章节详细大纲\n\n`
    mergedContent += `> 共 ${generatedOutlines.length} 章\n\n`
    mergedContent += `---\n\n`
    
    results.forEach((res, index) => {
      const outline = generatedOutlines[index]
      if (res.success && res.data?.detailed_outline) {
        mergedContent += `## 第${outline.chapter_number}章 ${outline.chapter_title}\n\n`
        mergedContent += res.data.detailed_outline
        mergedContent += '\n\n---\n\n'
      }
    })
    
    const fileName = `${project.value?.title || '小说'}_章节详细大纲_全章.md`
    const blob = new Blob([mergedContent], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success(`已下载 ${generatedOutlines.length} 章大纲`)
  } catch (error) {
    console.error('下载全部章节大纲失败', error)
    ElMessage.error('下载失败')
  }
}

// 下载全部章节正文
async function downloadAllChapterContent() {
  const generatedContents = chapterOutlines.value.filter(c => c.content_status === 'generated')
  
  if (generatedContents.length === 0) {
    ElMessage.warning('暂无已生成的正文可下载')
    return
  }
  
  try {
    ElMessage.info('正在获取正文内容...')
    
    // 调用后端API获取全部正文
    const res = await novelWriterApi.getAllChapterContent(projectId.value)
    
    if (!res.success || !res.data?.contents?.length) {
      ElMessage.warning('暂无正文内容可下载')
      return
    }
    
    const contents = res.data.contents
    const projectTitle = res.data.project_title || '小说'
    
    // 合并内容
    let mergedContent = `# ${projectTitle} - 章节正文\n\n`
    mergedContent += `> 共 ${contents.length} 章\n\n`
    mergedContent += `---\n\n`
    
    contents.forEach((item) => {
      mergedContent += `## 第${item.chapter_number}章 ${item.chapter_title}\n\n`
      mergedContent += item.content
      mergedContent += '\n\n---\n\n'
    })
    
    const fileName = `${projectTitle}_章节正文_全章.md`
    const blob = new Blob([mergedContent], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success(`已下载 ${contents.length} 章正文`)
  } catch (error) {
    console.error('下载全部章节正文失败', error)
    ElMessage.error('下载失败')
  }
}

// 章节大纲标题编辑
function startEditChapterOutlineTitle(outline) {
  editingChapterOutlineTitle.value = outline.chapter_number
  editChapterOutlineTitleValue.value = outline.chapter_title || ''
}

function cancelEditChapterOutlineTitle() {
  editingChapterOutlineTitle.value = null
  editChapterOutlineTitleValue.value = ''
}

async function saveChapterOutlineTitle(outline) {
  if (!editChapterOutlineTitleValue.value.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }

  if (editChapterOutlineTitleValue.value === outline.chapter_title) {
    editingChapterOutlineTitle.value = null
    return
  }

  try {
    const res = await novelWriterApi.updateChapterOutline(
      projectId.value, 
      outline.chapter_number, 
      { chapter_title: editChapterOutlineTitleValue.value }
    )
    
    if (res.success) {
      outline.chapter_title = editChapterOutlineTitleValue.value
      editingChapterOutlineTitle.value = null
      ElMessage.success('章节标题已更新')
    }
  } catch (error) {
    console.error('更新章节标题失败', error)
    ElMessage.error('更新失败')
  }
}

// ==================== 场景详细大纲相关方法（电影剧本专用） ====================

// 加载场景大纲列表
async function loadSceneOutlines() {
  if (project.value?.content_type !== 'movie_script') {
    return
  }
  
  try {
    const res = await novelWriterApi.getSceneOutlines(projectId.value)
    
    if (res.success && res.data) {
      const scenes = res.data.scenes || []
      
      sceneOutlines.value = scenes.map(sc => ({
        scene_number: sc.scene_number,
        scene_title: sc.scene_title || sc.location || `第${sc.scene_number}场`,
        location: sc.location,
        has_detailed: sc.status === 'generated' || sc.status === 'edited',
        content_status: sc.content_status || null,
        content_word_count: sc.content_word_count || 0,
        ...sc
      }))
    }
  } catch (error) {
    console.error('加载场景大纲失败', error)
  }
}

// 一键生成全部场景大纲（支持断点续传）
async function handleGenerateAllSceneOutlines(sceneNumbers = null) {
  const totalSc = totalSceneOutlineCount.value
  if (totalSc === 0) {
    ElMessage.warning('请先设置场景数')
    return
  }
  
  // 如果传入了指定的场景列表，使用它；否则使用断点续传逻辑
  let pendingScenes
  if (sceneNumbers && Array.isArray(sceneNumbers)) {
    pendingScenes = sceneNumbers
  } else {
    // 断点续传：计算未生成的场数
    const existingScenes = sceneOutlines.value
      .filter(sc => sc.has_detailed)
      .map(sc => sc.scene_number)
    
    const allScenes = Array.from({ length: totalSc }, (_, i) => i + 1)
    pendingScenes = allScenes.filter(sc => !existingScenes.includes(sc))
  }
  
  if (pendingScenes.length === 0) {
    ElMessage.success('全部场景大纲已生成，无需重复生成')
    return
  }
  
  // 构建确认消息
  const startSc = Math.min(...pendingScenes)
  const confirmMsg = pendingScenes.length !== totalSc
    ? `将生成第 ${startSc} 至第 ${Math.max(...pendingScenes)} 场，共 ${pendingScenes.length} 场。确定继续吗？`
    : `确定要生成全部 ${pendingScenes.length} 场的详细大纲吗？这可能需要较长时间。`
  
  try {
    await ElMessageBox.confirm(confirmMsg, '确认生成', { type: 'info' })
    
    // 设置任务状态
    taskStore.setTask({
      project_id: projectId.value,
      task_type: 'scene_outline',
      status: 'running',
      total_count: pendingScenes.length,
      completed_count: 0
    })
    
    generatingSceneOutlines.value = true
    // 创建 AbortController 用于取消请求
    abortController.value = new AbortController()
    ElMessage.info(`开始生成第 ${startSc} 至第 ${Math.max(...pendingScenes)} 场，共 ${pendingScenes.length} 场...`)
    
    // 启动任务状态轮询
    startTaskPolling()
    
    const res = await novelWriterApi.generateAllSceneOutlines(projectId.value, {
      scene_numbers: pendingScenes,
      stop_on_error: true
    }, abortController.value.signal)
    
    // 停止轮询
    stopTaskPolling()
    
    if (res.success) {
      ElMessage.success(`场景大纲生成完成！成功 ${res.data.completed_count} 场，失败 ${res.data.failed_count} 场`)
      await loadProject()
      await loadSceneOutlines()
    }
  } catch (error) {
    // 停止轮询
    stopTaskPolling()
    if (error === 'cancel' || error?.cancelled) {
      return
    }
    console.error('生成场景大纲失败:', error)
    ElMessage.error('生成场景大纲失败')
  } finally {
    generatingSceneOutlines.value = false
    abortController.value = null
    // 清除任务状态
    taskStore.clearTask()
  }
}

// 生成单场景详细大纲（带用户干预支持）
async function handleGenerateSingleSceneOutline(sceneNum) {
  generatingSingleSceneOutline.value = sceneNum
  try {
    ElMessage.info(`正在生成第 ${sceneNum} 场详细大纲...`)
    
    // 首先尝试带干预的生成
    const res = await novelWriterApi.generateOutlineWithIntervention(projectId.value, sceneNum, {
      content_type: 'movie_script'
    })
    
    if (res.success) {
      const status = res.data?.status
      
      if (status === 'need_intervention') {
        // 需要用户干预，显示干预对话框
        showInterventionDialog(sceneNum, res.data)
        return
      } else if (status === 'success' || status === 'completed') {
        // 生成成功
        ElMessage.success(`第 ${sceneNum} 场详细大纲生成成功`)
        await loadProject()
        await loadSceneOutlines()
      } else if (status === 'skipped') {
        ElMessage.info(`第 ${sceneNum} 场已跳过`)
      } else {
        ElMessage.error(res.data?.message || '生成失败')
      }
    } else {
      ElMessage.error(res.data?.error_message || res.data?.message || '生成失败')
    }
  } catch (error) {
    if (error?.cancelled) {
      return
    }
    console.error('生成场景大纲失败:', error)
    ElMessage.error(`第 ${sceneNum} 场详细大纲生成失败`)
  } finally {
    generatingSingleSceneOutline.value = null
  }
}

// 查看场景大纲详情
async function showSceneOutlineDetail(outline) {
  try {
    const res = await novelWriterApi.getSceneOutline(projectId.value, outline.scene_number)
    if (res.success && res.data) {
      currentSceneOutlineDetail.value = {
        scene_number: outline.scene_number,
        scene_title: outline.scene_title || `第${outline.scene_number}场`,
        raw_content: res.data.detailed_outline || ''
      }
      sceneOutlineDetailVisible.value = true
    }
  } catch (error) {
    console.error('获取场景大纲详情失败', error)
    ElMessage.error('获取大纲详情失败')
  }
}

// 开始编辑场景大纲
function startEditSceneOutline() {
  sceneOutlineEditContent.value = currentSceneOutlineDetail.value.raw_content
  sceneOutlineEditTitle.value = currentSceneOutlineDetail.value.scene_title
  sceneOutlineEditMode.value = true
}

// 取消编辑场景大纲
function cancelEditSceneOutline() {
  sceneOutlineEditMode.value = false
  sceneOutlineEditContent.value = ''
  sceneOutlineEditTitle.value = ''
}

// 保存编辑的场景大纲
async function saveSceneOutlineEdit() {
  if (!sceneOutlineEditContent.value.trim()) {
    ElMessage.warning('大纲内容不能为空')
    return
  }
  
  savingSceneOutlineEdit.value = true
  try {
    const res = await novelWriterApi.updateSceneOutline(
      projectId.value,
      currentSceneOutlineDetail.value.scene_number,
      {
        scene_title: sceneOutlineEditTitle.value,
        detailed_outline: sceneOutlineEditContent.value
      }
    )
    
    if (res.success) {
      currentSceneOutlineDetail.value.scene_title = sceneOutlineEditTitle.value
      currentSceneOutlineDetail.value.raw_content = sceneOutlineEditContent.value
      sceneOutlineEditMode.value = false
      await loadSceneOutlines()
      ElMessage.success('大纲已保存')
    }
  } catch (error) {
    console.error('保存场景大纲失败', error)
    ElMessage.error('保存失败')
  } finally {
    savingSceneOutlineEdit.value = false
  }
}

// 下载单场景大纲（从弹窗）
function downloadSingleSceneOutline() {
  const content = currentSceneOutlineDetail.value.raw_content
  if (!content) {
    ElMessage.warning('暂无内容可下载')
    return
  }
  
  const sceneNum = currentSceneOutlineDetail.value.scene_number
  const sceneTitle = currentSceneOutlineDetail.value.scene_title
  const fileName = `${project.value?.title || '电影剧本'}_第${sceneNum}场_${sceneTitle}.md`
  
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.click()
  URL.revokeObjectURL(url)
  
  ElMessage.success('下载成功')
}

// 下载单场景大纲（从列表直接下载）
async function downloadSceneOutline(outline) {
  try {
    const res = await novelWriterApi.getSceneOutline(projectId.value, outline.scene_number)
    if (res.success && res.data?.detailed_outline) {
      const content = res.data.detailed_outline
      const fileName = `${project.value?.title || '电影剧本'}_第${outline.scene_number}场_${outline.scene_title}.md`
      
      const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      a.click()
      URL.revokeObjectURL(url)
      
      ElMessage.success('下载成功')
    } else {
      ElMessage.warning('暂无内容可下载')
    }
  } catch (error) {
    console.error('下载场景大纲失败', error)
    ElMessage.error('下载失败')
  }
}

// 下载全部场景大纲
async function downloadAllSceneOutlines() {
  const generatedOutlines = sceneOutlines.value.filter(s => s.has_detailed)
  
  if (generatedOutlines.length === 0) {
    ElMessage.warning('暂无已生成的大纲可下载')
    return
  }
  
  try {
    const promises = generatedOutlines.map(outline => 
      novelWriterApi.getSceneOutline(projectId.value, outline.scene_number)
    )
    
    const results = await Promise.all(promises)
    
    let mergedContent = `# ${project.value?.title || '电影剧本'} - 场景详细大纲\n\n`
    mergedContent += `> 共 ${generatedOutlines.length} 场\n\n`
    mergedContent += `---\n\n`
    
    results.forEach((res, index) => {
      const outline = generatedOutlines[index]
      if (res.success && res.data?.detailed_outline) {
        mergedContent += `## 第${outline.scene_number}场 ${outline.scene_title}\n\n`
        mergedContent += res.data.detailed_outline
        mergedContent += '\n\n---\n\n'
      }
    })
    
    const fileName = `${project.value?.title || '电影剧本'}_场景详细大纲_全场.md`
    const blob = new Blob([mergedContent], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success(`已下载 ${generatedOutlines.length} 场大纲`)
  } catch (error) {
    console.error('下载全部场景大纲失败', error)
    ElMessage.error('下载失败')
  }
}

// 下载全部场景正文
async function downloadAllSceneContent() {
  const generatedContents = sceneOutlines.value.filter(s => s.content_status === 'generated')
  
  if (generatedContents.length === 0) {
    ElMessage.warning('暂无已生成的正文可下载')
    return
  }
  
  try {
    ElMessage.info('正在获取正文内容...')
    
    // 调用后端API获取全部正文
    const res = await novelWriterApi.getAllSceneContent(projectId.value)
    
    if (!res.success || !res.data?.contents?.length) {
      ElMessage.warning('暂无正文内容可下载')
      return
    }
    
    const contents = res.data.contents
    const projectTitle = res.data.project_title || '电影剧本'
    
    // 合并内容
    let mergedContent = `# ${projectTitle} - 场景正文\n\n`
    mergedContent += `> 共 ${contents.length} 场\n\n`
    mergedContent += `---\n\n`
    
    contents.forEach((item) => {
      mergedContent += `## 第${item.scene_number}场 ${item.chapter_title}\n\n`
      mergedContent += item.content
      mergedContent += '\n\n---\n\n'
    })
    
    const fileName = `${projectTitle}_场景正文_全场.md`
    const blob = new Blob([mergedContent], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success(`已下载 ${contents.length} 场正文`)
  } catch (error) {
    console.error('下载全部场景正文失败', error)
    ElMessage.error('下载失败')
  }
}

// 场景大纲标题编辑
function startEditSceneOutlineTitle(outline) {
  editingSceneOutlineTitle.value = outline.scene_number
  editSceneOutlineTitleValue.value = outline.scene_title || ''
}

function cancelEditSceneOutlineTitle() {
  editingSceneOutlineTitle.value = null
  editSceneOutlineTitleValue.value = ''
}

async function saveSceneOutlineTitle(outline) {
  if (!editSceneOutlineTitleValue.value.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }

  if (editSceneOutlineTitleValue.value === outline.scene_title) {
    editingSceneOutlineTitle.value = null
    return
  }

  try {
    const res = await novelWriterApi.updateSceneOutline(
      projectId.value, 
      outline.scene_number, 
      { scene_title: editSceneOutlineTitleValue.value }
    )
    
    if (res.success) {
      outline.scene_title = editSceneOutlineTitleValue.value
      editingSceneOutlineTitle.value = null
      ElMessage.success('场景标题已更新')
    }
  } catch (error) {
    console.error('更新场景标题失败', error)
    ElMessage.error('更新失败')
  }
}

function getStatusType(status) {
  const types = { init: 'info', generating: 'primary', completed: 'success', failed: 'danger', paused: 'warning' }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = { init: '初始化', generating: '生成中', completed: '已完成', failed: '失败', paused: '已暂停' }
  return texts[status] || status
}

function getChapterStatusType(status) {
  const types = { pending: 'info', drafting: 'warning', completed: 'success', failed: 'danger' }
  return types[status] || 'info'
}

function getChapterStatusText(status) {
  const texts = { pending: '待生成', drafting: '生成中', completed: '已完成', failed: '失败' }
  return texts[status] || status
}

function formatDateTime(str) {
  if (!str) return ''
  return new Date(str).toLocaleString()
}

// 步骤图标映射
function getStepIcon(iconName) {
  const iconMap = {
    'Document': Document,
    'Reading': Reading,
    'Cpu': Cpu,
    'DataAnalysis': DataAnalysis,
    'ChatDotRound': ChatDotRound,
    'Edit': Edit,
    'Folder': Folder,
    'List': List,
    'Loading': Loading,
    'Finished': Finished,
    'CircleCheck': CircleCheck,
    'CircleClose': CircleClose,
    'Warning': Warning
  }
  return iconMap[iconName] || Loading
}

// 格式化耗时
function formatDuration(ms) {
  if (!ms || ms < 0) return ''
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

// 获取显示的步骤列表（去重，只显示每个步骤的最新状态）
const getDisplaySteps = computed(() => {
  const steps = taskStore.stepsHistory
  if (!steps || steps.length === 0) return []
  
  // 去重：只保留每个key的最新状态
  const stepMap = new Map()
  for (const step of steps) {
    const key = step.key
    if (!stepMap.has(key) || step.status === 'done' || step.status === 'error') {
      stepMap.set(key, step)
    }
  }
  
  return Array.from(stepMap.values()).reverse()
})

function showOutlineUpload() {
  // 滚动到上传区域
}

// ==================== 任务状态实时更新（SSE + 轮询降级）====================

/**
 * 启动 SSE 连接，实时接收任务状态更新
 * SSE 优于轮询，断线自动重连
 */
function startSSEConnection() {
  // 先关闭现有连接
  stopSSEConnection()
  
  const url = novelWriterApi.getTaskEventsURL(projectId.value)
  
  try {
    // 创建 EventSource 连接
    const eventSource = new EventSource(url)
    sseConnection.value = eventSource
    
    eventSource.onopen = () => {
      console.log('[SSE] 连接已建立')
      // SSE 连接成功，停止轮询
      stopTaskPolling()
    }
    
    eventSource.onmessage = (event) => {
      try {
        const taskData = event.data === 'null' ? null : JSON.parse(event.data)
        
        if (taskData) {
          // 更新 taskStore
          taskStore.setTask(taskData)
          
          // 刷新对应列表
          refreshListByTaskType(taskData.task_type)
          
          // 任务结束处理
          if (taskData.status !== 'running') {
            // 任务已完成，延迟关闭连接
            setTimeout(() => {
              if (taskStore.currentTask?.status !== 'running') {
                stopSSEConnection()
              }
            }, 1000)
          }
        } else {
          // 收到 null，表示无任务
          taskStore.clearTask()
          stopSSEConnection()
        }
      } catch (e) {
        console.error('[SSE] 解析消息失败:', e)
      }
    }
    
    eventSource.onerror = (error) => {
      console.warn('[SSE] 连接错误，准备重连:', error)
      eventSource.close()
      sseConnection.value = null
      
      // 检查是否仍有运行中的任务，有则重连
      if (taskStore.isRunning) {
        // 清除旧的重连计时器
        if (sseReconnectTimer.value) {
          clearTimeout(sseReconnectTimer.value)
        }
        // 延迟重连
        sseReconnectTimer.value = setTimeout(() => {
          console.log('[SSE] 尝试重连...')
          startSSEConnection()
        }, SSE_RECONNECT_DELAY)
      }
    }
  } catch (e) {
    console.error('[SSE] 创建连接失败:', e)
    // SSE 失败，降级到轮询
    startTaskPolling()
  }
}

/**
 * 停止 SSE 连接
 */
function stopSSEConnection() {
  // 清除重连计时器
  if (sseReconnectTimer.value) {
    clearTimeout(sseReconnectTimer.value)
    sseReconnectTimer.value = null
  }
  
  // 关闭 SSE 连接
  if (sseConnection.value) {
    sseConnection.value.close()
    sseConnection.value = null
    console.log('[SSE] 连接已关闭')
  }
}

/**
 * 启动任务状态监控（优先 SSE，降级轮询）
 */
function startTaskMonitoring() {
  // 优先尝试 SSE
  if (typeof EventSource !== 'undefined') {
    startSSEConnection()
  } else {
    // 浏览器不支持 SSE，使用轮询
    startTaskPolling()
  }
}

/**
 * 停止任务状态监控
 */
function stopTaskMonitoring() {
  stopSSEConnection()
  stopTaskPolling()
}

/**
 * 启动任务状态轮询（降级方案）
 * 简化方案：每次轮询都刷新列表，确保实时性
 */
function startTaskPolling() {
  // 清除现有定时器
  stopTaskPolling()
  
  console.log('[轮询] 启动任务状态轮询')
  
  // 设置定时轮询
  taskPollingTimer.value = setInterval(async () => {
    const task = await taskStore.fetchTaskStatus(projectId.value)
    
    if (!task) {
      // 任务不存在，停止轮询
      stopTaskPolling()
      return
    }
    
    // 每次轮询都刷新列表，确保实时显示最新进度
    await refreshListByTaskType(task.task_type)
    
    // 任务结束处理
    if (task.status !== 'running') {
      stopTaskPolling()
    }
  }, TASK_POLLING_INTERVAL)
}

/**
 * 停止任务状态轮询
 */
function stopTaskPolling() {
  if (taskPollingTimer.value) {
    clearInterval(taskPollingTimer.value)
    taskPollingTimer.value = null
  }
}

/**
 * 根据任务类型刷新对应的列表
 */
async function refreshListByTaskType(taskType) {
  if (!taskType) return
  
  try {
    if (taskType === 'episode_outline') {
      await loadEpisodeOutlines()
    } else if (taskType === 'chapter_outline') {
      await loadChapterOutlines()
    } else if (taskType === 'scene_outline') {
      await loadSceneOutlines()
    } else if (taskType === 'episode_content') {
      await loadEpisodeOutlines()
    } else if (taskType === 'chapter_content') {
      await loadChapterOutlines()
    } else if (taskType === 'scene_content') {
      await loadSceneOutlines()
    }
  } catch (error) {
    console.error('刷新列表失败:', error)
  }
}

onMounted(async () => {
  // 第一步：加载项目基础信息
  await loadProject()
  await loadChapters()
  
  // 第二步：关键！先获取任务状态，确保进度条能正确显示
  // 这必须在加载列表之前完成，因为进度条依赖 taskStore.hasTask
  const task = await taskStore.fetchTaskStatus(projectId.value)
  
  // 第三步：加载对应类型的大纲列表
  if (project.value?.content_type === 'novel') {
    await loadChapterOutlines()
  } else if (project.value?.content_type === 'series_script') {
    await loadEpisodeOutlines()
  } else if (project.value?.content_type === 'movie_script') {
    await loadSceneOutlines()
  }
  
  // 第四步：加载知识库状态
  await loadKnowledgeBaseStatus()
  
  // 第五步：根据任务状态决定下一步操作
  if (task) {
    if (task.status === 'running') {
      // 任务仍在运行，启动 SSE 监控（优先）或轮询（降级）并提示用户
      ElMessage.info(`检测到正在进行的${taskStore.taskTypeLabel}任务，进度: ${task.completed_count || 0}/${task.total_count || 0}`)
      startTaskMonitoring()
    } else if (task.status === 'failed' || task.status === 'cancelled' || task.status === 'completed') {
      // 历史任务已结束（服务器重启或正常完成），不显示旧状态条，直接清除
      taskStore.clearTask()
    }
  }
})

onUnmounted(() => {
  // 组件卸载时停止所有监控
  stopTaskMonitoring()
  // 停止知识库构建轮询
  if (kbBuildPollingTimer) {
    clearInterval(kbBuildPollingTimer)
    kbBuildPollingTimer = null
  }
  // 移除页面可见性监听
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

/**
 * 处理页面可见性变化
 * 当用户切换回页面时，自动刷新任务状态
 */
function handleVisibilityChange() {
  if (!document.hidden) {
    // 页面重新可见，刷新任务状态
    taskStore.fetchTaskStatus(projectId.value).then(task => {
      if (task && task.status === 'running') {
        // 如果任务正在运行但没有监控，重新启动
        if (!sseConnection.value && !taskPollingTimer.value) {
          taskStore.setTask(task)
          startTaskMonitoring()
        }
      } else if (task && (task.status === 'failed' || task.status === 'cancelled' || task.status === 'completed')) {
        // 历史结束任务，清除显示
        taskStore.clearTask()
      }
    })
  }
}

// 添加页面可见性监听
document.addEventListener('visibilitychange', handleVisibilityChange)

// 监听项目变化，加载相应类型的大纲
watch(() => project.value, (newVal) => {
  if (!newVal) return
  
  // 优先根据 content_type 判断，避免 project_type 导致的错误匹配
  if (newVal.content_type === 'movie_script') {
    loadSceneOutlines()
  } else if (newVal.content_type === 'series_script') {
    loadEpisodeOutlines()
  } else if (newVal.content_type === 'novel') {
    loadChapterOutlines()
  } else if (newVal.project_type === 'script') {
    // 兼容旧数据：没有 content_type 但有 project_type 的情况
    loadEpisodeOutlines()
  }
}, { immediate: true })
</script>

<style lang="scss" scoped>
.project-detail-page {
  // 任务状态提示条样式
  .task-status-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
    color: #fff;
    padding: 12px 20px;
    border-radius: 8px;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(238, 90, 90, 0.3);
    animation: pulse-glow 2s ease-in-out infinite;

    .task-info {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
      flex-wrap: wrap;

      .el-icon {
        font-size: 18px;
      }

      .task-type {
        font-weight: 600;
        font-size: 15px;
      }

      .task-progress {
        font-size: 14px;
        opacity: 0.9;
      }

      .current-step {
        display: flex;
        align-items: center;
        gap: 6px;
        background: rgba(255, 255, 255, 0.15);
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 13px;
        margin-left: 8px;

        .el-icon {
          font-size: 14px;
        }

        .step-message {
          &.step-done {
            color: #a5f3a5;
          }
          &.step-error {
            color: #ffc1c1;
          }
        }
      }
    }

    .task-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .el-button {
      background: rgba(255, 255, 255, 0.2);
      border-color: rgba(255, 255, 255, 0.3);
      color: #fff;

      &:hover {
        background: rgba(255, 255, 255, 0.3);
        border-color: rgba(255, 255, 255, 0.5);
      }
    }
  }

  // 步骤历史样式
  .steps-history {
    max-height: 400px;
    overflow-y: auto;

    .steps-title {
      font-weight: 600;
      font-size: 14px;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid #eee;
      color: #303133;
    }

    .step-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      margin-bottom: 4px;
      border-radius: 6px;
      background: #f5f7fa;
      font-size: 13px;

      &.step-running {
        background: #fdf6ec;
        .step-text {
          color: #e6a23c;
        }
      }

      &.step-done {
        background: #f0f9eb;
        .step-text {
          color: #67c23a;
        }
      }

      &.step-error {
        background: #fef0f0;
        .step-text {
          color: #f56c6c;
        }
      }

      .step-text {
        flex: 1;
        color: #606266;
      }

      .step-duration {
        font-size: 12px;
        color: #909399;
        margin-right: 8px;
      }
    }
  }

  @keyframes pulse-glow {
    0%, 100% {
      box-shadow: 0 4px 12px rgba(238, 90, 90, 0.3);
    }
    50% {
      box-shadow: 0 4px 20px rgba(238, 90, 90, 0.5);
    }
  }

  // 非运行状态的任务状态条样式（用于任务完成/取消后短暂显示）
  &.is-completed {
    background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
    animation: none;
  }

  &.is-cancelled {
    background: linear-gradient(135deg, #909399 0%, #a6a9ad 100%);
    animation: none;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      .project-title {
        font-size: 20px;
        font-weight: 600;
        margin: 0;
      }
    }

    .header-actions {
      display: flex;
      gap: 8px;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .outline-upload-area {
    padding: 40px;
    text-align: center;
  }

  .outline-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    background: #f5f7fa;
    border-radius: 8px;
    margin-bottom: 16px;

    .outline-status {
      display: flex;
      align-items: center;
      gap: 8px;

      span {
        font-weight: 500;
      }
    }
  }

  .chapter-setup-area {
    padding: 16px;
    background: #fdf6ec;
    border-radius: 8px;
    margin-bottom: 16px;

    .setup-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;

      .setup-info {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #606266;

        strong {
          color: #E6A23C;
          font-size: 18px;
        }
      }

      .setup-actions {
        display: flex;
        align-items: center;
        gap: 12px;
      }
    }
  }

  // 单元概述上传区域样式
  .unit-summaries-upload-area {
    padding: 16px;
    background: #f0f9ff;
    border-radius: 8px;
    margin-bottom: 16px;

    .unit-summaries-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;

      .info-text {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #606266;
      }
    }
  }

  // 已有单元概述信息区域样式
  .unit-summaries-info-area {
    padding: 16px;
    background: #f0f9ff;
    border-radius: 8px;
    margin-bottom: 16px;

    .unit-summaries-status {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;

      .status-info {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #606266;

        strong {
          color: #67c23a;
          font-size: 18px;
        }
      }
    }
  }

  // 分集详细大纲区域样式
  .episode-outline-area {
    padding: 16px;
    background: #ecf5ff;
    border-radius: 8px;
    margin-bottom: 16px;

    .episode-outline-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;

      .outline-stats {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #606266;

        strong {
          color: #409EFC;
          font-size: 18px;
        }
      }

      .outline-actions {
        display: flex;
        align-items: center;
        gap: 12px;
      }
    }

    .episode-outline-list {
      max-height: 250px;
      overflow-y: auto;
      border: 1px solid #e4e7ed;
      border-radius: 4px;
      padding: 8px;
      background: #fff;

      .episode-outline-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        border-bottom: 1px solid #ebeef5;
        gap: 16px;

        &:last-child {
          border-bottom: none;
        }

        &:hover {
          background: #f5f7fa;
        }

        &.has-outline {
          background: #f0f9eb;
        }

        &.has-content {
          background: #fdf6ec;
          border-left: 3px solid #E6A23C;
        }

        &.is-generating {
          background: #fdf6ec;
          border-left: 3px solid #E6A23C;
          animation: pulse 1.5s ease-in-out infinite;
        }

        // 左侧标题区域
        .outline-left {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          min-width: 0;
          overflow: hidden;

          .episode-num {
            font-weight: 600;
            color: #303133;
            white-space: nowrap;
            flex-shrink: 0;
          }

          .episode-title {
            color: #606266;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            
            &.editable {
              cursor: pointer;
              padding: 2px 6px;
              border-radius: 4px;
              transition: background 0.2s;
              
              &:hover {
                background: #e6e8eb;
              }
            }
          }
        }

        // 右侧状态和操作区域
        .outline-right {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 6px;
          flex-shrink: 0;

          .status-tags {
            display: flex;
            align-items: center;
            gap: 6px;
          }

          .action-buttons {
            display: flex;
            align-items: center;
            gap: 4px;
            flex-wrap: nowrap;
          }
        }

        .generating-tag {
          .el-icon {
            margin-right: 4px;
          }
        }
      }
    }
  }
  
  // 章节大纲区域样式（小说专用）
  .chapter-outline-area {
    padding: 16px;
    background: #f0f9eb;
    border-radius: 8px;
    margin-bottom: 16px;

    .chapter-outline-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;

      .outline-stats {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #606266;

        strong {
          color: #67c23a;
          font-size: 18px;
        }
      }

      .outline-actions {
        display: flex;
        align-items: center;
        gap: 12px;
      }
    }

    .chapter-outline-list {
      max-height: 250px;
      overflow-y: auto;
      border: 1px solid #e4e7ed;
      border-radius: 4px;
      padding: 8px;
      background: #fff;

      .chapter-outline-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        border-bottom: 1px solid #ebeef5;
        gap: 16px;

        &:last-child {
          border-bottom: none;
        }

        &:hover {
          background: #f5f7fa;
        }

        &.has-outline {
          background: #f0f9eb;
        }

        &.has-content {
          background: #fdf6ec;
          border-left: 3px solid #E6A23C;
        }

        &.is-generating {
          background: #fdf6ec;
          border-left: 3px solid #E6A23C;
          animation: pulse 1.5s ease-in-out infinite;
        }

        // 左侧标题区域
        .outline-left {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          min-width: 0; // 允许收缩
          overflow: hidden;

          .chapter-num {
            font-weight: 600;
            color: #303133;
            white-space: nowrap;
            flex-shrink: 0;
          }

          .chapter-title-text {
            color: #606266;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            
            &.editable {
              cursor: pointer;
              padding: 2px 6px;
              border-radius: 4px;
              transition: background 0.2s;
              
              &:hover {
                background: #e6e8eb;
              }
            }
          }
        }

        // 右侧状态和操作区域
        .outline-right {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 6px;
          flex-shrink: 0;

          .status-tags {
            display: flex;
            align-items: center;
            gap: 6px;
          }

          .action-buttons {
            display: flex;
            align-items: center;
            gap: 4px;
            flex-wrap: nowrap;
          }
        }

        .generating-tag {
          .el-icon {
            margin-right: 4px;
          }
        }
      }
    }
  }
  
  // 场景大纲区域样式（电影剧本专用）
  .scene-outline-area {
    padding: 16px;
    background: #fef0f0;
    border-radius: 8px;
    margin-bottom: 16px;

    .scene-outline-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;

      .outline-stats {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #606266;

        strong {
          color: #f56c6c;
          font-size: 18px;
        }
      }

      .outline-actions {
        display: flex;
        align-items: center;
        gap: 12px;
      }
    }

    .scene-outline-list {
      max-height: 250px;
      overflow-y: auto;
      border: 1px solid #e4e7ed;
      border-radius: 4px;
      padding: 8px;
      background: #fff;

      .scene-outline-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        border-bottom: 1px solid #ebeef5;
        gap: 16px;

        &:last-child {
          border-bottom: none;
        }

        &:hover {
          background: #f5f7fa;
        }

        &.has-outline {
          background: #f0f9eb;
        }

        &.has-content {
          background: #fdf6ec;
          border-left: 3px solid #E6A23C;
        }

        &.is-generating {
          background: #fdf6ec;
          border-left: 3px solid #E6A23C;
          animation: pulse 1.5s ease-in-out infinite;
        }

        // 左侧标题区域
        .outline-left {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          min-width: 0;
          overflow: hidden;

          .scene-num {
            font-weight: 600;
            color: #303133;
            white-space: nowrap;
            flex-shrink: 0;
          }

          .scene-title-text {
            color: #606266;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            
            &.editable {
              cursor: pointer;
              padding: 2px 6px;
              border-radius: 4px;
              transition: background 0.2s;
              
              &:hover {
                background: #e6e8eb;
              }
            }
          }
        }

        // 右侧状态和操作区域
        .outline-right {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 6px;
          flex-shrink: 0;

          .status-tags {
            display: flex;
            align-items: center;
            gap: 6px;
          }

          .action-buttons {
            display: flex;
            align-items: center;
            gap: 4px;
            flex-wrap: nowrap;
          }
        }

        .generating-tag {
          .el-icon {
            margin-right: 4px;
          }
        }
      }
    }
  }
  
  // 大纲详情内容样式
  .outline-detail-content {
    max-height: 60vh;
    overflow-y: auto;
    padding: 16px;
    background: #fafafa;
    border-radius: 8px;
    line-height: 1.8;
    
    h1, h2, h3, h4, h5, h6 {
      margin: 20px 0 10px;
      font-weight: 600;
    }
    
    h1 { font-size: 24px; }
    h2 { font-size: 20px; }
    h3 { font-size: 18px; }
    
    p {
      margin: 10px 0;
    }
    
    ul, ol {
      padding-left: 20px;
      margin: 10px 0;
    }
    
    code {
      background: #f5f5f5;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'Consolas', monospace;
    }
    
    pre {
      background: #f5f5f5;
      padding: 12px;
      border-radius: 4px;
      overflow-x: auto;
    }
    
    blockquote {
      border-left: 4px solid #409eff;
      padding-left: 16px;
      margin: 10px 0;
      color: #606266;
    }
    
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
      
      th, td {
        border: 1px solid #ebeef5;
        padding: 8px 12px;
        text-align: left;
      }
      
      th {
        background: #f5f7fa;
        font-weight: 500;
      }
    }
  }
  
  // 大纲编辑模式样式
  .outline-edit-mode {
    padding: 16px;
    background: #fff;
    border-radius: 8px;
    border: 1px solid #ebeef5;
    
    :deep(.el-textarea__inner) {
      font-family: inherit;
      line-height: 1.8;
    }
  }

  .chapter-list {
    max-height: 320px;
    overflow-y: auto;

    .chapter-actions-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      margin-bottom: 8px;
      border-bottom: 1px solid #ebeef5;
      
      .action-buttons {
        display: flex;
        gap: 8px;
      }
    }

    .chapter-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px;
      border-radius: 8px;
      cursor: pointer;
      transition: background 0.3s;

      &:hover {
        background: #f5f7fa;
      }

      &.active {
        background: #ecf5ff;
      }

      .chapter-info {
        .chapter-number {
          font-weight: 500;
          margin-right: 8px;
        }

        .chapter-title {
          color: #606266;
          
          &.editable {
            cursor: pointer;
            padding: 2px 6px;
            border-radius: 4px;
            transition: background 0.2s;
            
            &:hover {
              background: #e6e8eb;
            }
          }
        }
      }

      .chapter-status {
        display: flex;
        align-items: center;
        gap: 8px;

        .word-count {
          font-size: 12px;
          color: #909399;
        }
      }
    }
  }

  .chapter-content {
    :deep(.el-textarea__inner) {
      font-family: inherit;
      line-height: 1.8;
      font-size: 14px;
    }
  }

  // 正文编辑器卡片样式优化
  .content-card {
    :deep(.el-card__body) {
      padding: 16px;
    }
    
    .chapter-content {
      min-height: 500px;
    }
  }

  .status-card, .config-card, .stats-card {
    margin-bottom: 12px;

    .status-item, .config-item, .stats-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 0;
      border-bottom: 1px solid #ebeef5;

      &:last-child {
        border-bottom: none;
      }

      .label {
        color: #909399;
        font-size: 13px;
      }

      .value {
        font-weight: 500;
        font-size: 13px;
      }
    }
  }

  // 紧凑卡片样式
  .compact-card {
    :deep(.el-card__header) {
      padding: 12px 16px;
      font-size: 14px;
    }
    
    :deep(.el-card__body) {
      padding: 12px 16px;
    }
  }

  // 状态网格布局
  .status-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    
    .status-item-compact {
      display: flex;
      flex-direction: column;
      gap: 4px;
      
      .label {
        font-size: 12px;
        color: #909399;
      }
      
      .value {
        font-weight: 500;
        font-size: 14px;
      }
    }
  }

  // 统计网格布局
  .stats-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
    
    .stats-item-compact {
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      .label {
        font-size: 12px;
        color: #909399;
      }
      
      .value {
        font-weight: 500;
        font-size: 13px;
        
        &.small {
          font-size: 12px;
          color: #606266;
        }
      }
    }
  }

  .form-tip {
    font-size: 12px;
    color: #909399;
    margin-left: 12px;
  }

  // 用户干预对话框样式
  .intervention-content {
    // 提示横幅
    .intervention-banner {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 16px;
      border-radius: 12px;
      margin-bottom: 20px;
      background: linear-gradient(135deg, #fef3e2 0%, #fdf6ec 100%);
      border: 1px solid #f5dab1;

      .banner-icon {
        font-size: 24px;
        flex-shrink: 0;
        color: #e6a23c;
      }

      .banner-info {
        flex: 1;

        .banner-message {
          font-size: 14px;
          color: #606266;
          line-height: 1.5;
        }
      }
    }

    // 推断概要
    .inferred-summary {
      background: #f8fafc;
      border: 1px solid #e4e7ed;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 20px;

      .summary-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        color: #606266;
        margin-bottom: 12px;
        font-weight: 500;

        .el-icon {
          font-size: 16px;
          color: #909399;
        }
      }

      .summary-content {
        font-size: 14px;
        line-height: 1.7;
        color: #303133;
        padding: 12px;
        background: #fff;
        border-radius: 8px;
        border: 1px solid #ebeef5;
      }
    }

    // 选项区域
    .intervention-options {
      .options-title {
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 16px;
        color: #303133;
      }

      .options-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;

        .option-card {
          position: relative;
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 16px;
          border: 2px solid #e4e7ed;
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.2s ease;
          background: #fff;

          &:hover {
            border-color: #c0c4cc;
            background: #fafafa;
          }

          &.active {
            border-color: #409eff;
            background: linear-gradient(135deg, #f0f7ff 0%, #e8f4ff 100%);

            .option-icon {
              background: #409eff;
              color: #fff;
            }
          }

          .option-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: #f0f2f5;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            color: #606266;
            flex-shrink: 0;
            transition: all 0.2s ease;
          }

          .option-info {
            flex: 1;
            min-width: 0;

            .option-label {
              font-size: 14px;
              font-weight: 500;
              color: #303133;
              margin-bottom: 4px;
            }

            .option-desc {
              font-size: 12px;
              color: #909399;
              line-height: 1.4;
            }
          }

          .option-check {
            position: absolute;
            top: 8px;
            right: 8px;
            font-size: 18px;
            color: #409eff;
          }
        }
      }
    }

    // 用户输入
    .user-guidance-input {
      margin-top: 20px;

      .input-label {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        color: #606266;
        margin-bottom: 12px;
        font-weight: 500;

        .el-icon {
          font-size: 16px;
          color: #909399;
        }
      }
    }
  }
}

// 生成中动画
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

// 知识库状态卡片样式
.knowledge-base-card,
.kb-setting-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kb-stats-info {
  font-size: 13px;
  color: #606266;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
  
  &.warn {
    color: #e6a23c;
  }
}

.knowledge-base-card {
  .card-header-flex {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .kb-status-pending {
    .kb-hint {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 12px;
      color: #e6a23c;
      font-size: 13px;
    }
  }

  .kb-status-building {
    .kb-progress {
      margin-bottom: 16px;
      
      .kb-message {
        margin-top: 8px;
        font-size: 13px;
        color: #606266;
        text-align: center;
      }
    }
  }

  .kb-status-ready {
    .kb-stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      margin-bottom: 16px;

      .kb-stat-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: #f5f7fa;
        border-radius: 6px;

        .kb-stat-label {
          font-size: 12px;
          color: #909399;
        }

        .kb-stat-value {
          font-size: 14px;
          font-weight: 600;
          color: #303133;
        }
      }
    }

    .kb-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
  }

  .kb-status-failed {
    .el-alert {
      margin-bottom: 12px;
    }
  }
}

// 单元图谱重建弹窗样式
.unit-graph-rebuild-content {
  .unit-status-overview {
    display: flex;
    justify-content: space-around;
    margin-bottom: 16px;
  }

  .rebuild-options {
    h4 {
      margin-bottom: 12px;
      color: #303133;
    }

    .el-radio-group {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .unit-selector {
      margin-top: 16px;
      
      .el-transfer {
        display: flex;
        justify-content: center;
      }
    }

    .unbuilt-units-list {
      margin-top: 16px;
      padding: 12px;
      background: #f5f7fa;
      border-radius: 8px;
    }
  }

  .build-progress {
    margin-top: 20px;
    padding: 16px;
    background: #f5f7fa;
    border-radius: 8px;

    .progress-message {
      margin-top: 8px;
      text-align: center;
      color: #606266;
    }
  }
}

// 知识图谱可视化样式
.knowledge-graph-container {
  .graph-type-selector {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
  }

  .graph-stats {
    margin-bottom: 16px;
  }

  .graph-visualization {
    min-height: 400px;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    overflow: hidden;

    .graph-empty {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 400px;
    }

    .graph-canvas {
      display: flex;
      height: 400px;
      overflow: hidden;

      .nodes-list-view {
        flex: 1;
        overflow-y: auto;
        border-right: 1px solid #e4e7ed;
        padding: 12px;

        .node-type-header {
          display: flex;
          align-items: center;
          gap: 8px;

          .node-count {
            font-size: 12px;
            color: #909399;
          }
        }

        .node-list {
          .node-item {
            padding: 8px 12px;
            margin: 4px 0;
            background: #f5f7fa;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;

            &:hover {
              background: #e6f7ff;
            }

            &.selected {
              background: #bae7ff;
              border-left: 3px solid #1890ff;
            }

            .node-name {
              display: block;
              font-weight: 500;
              color: #303133;
            }

            .node-desc {
              display: block;
              font-size: 12px;
              color: #909399;
              margin-top: 4px;
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;
            }
          }
        }
      }

      .edges-list-view {
        flex: 1;
        overflow-y: auto;
        padding: 12px;

        .edges-header {
          display: flex;
          align-items: center;
          gap: 8px;
          font-weight: 600;
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid #e4e7ed;
        }

        .edges-list {
          .edge-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 0;
            font-size: 13px;

            .edge-source {
              color: #409eff;
              font-weight: 500;
            }

            .edge-relation {
              color: #67c23a;
              background: #f0f9eb;
              padding: 2px 8px;
              border-radius: 4px;
              font-size: 12px;
            }

            .edge-target {
              color: #e6a23c;
              font-weight: 500;
            }
          }
        }
      }
    }
  }

  .node-detail-panel {
    margin-top: 16px;

    .detail-header {
      display: flex;
      align-items: center;
      gap: 8px;

      .detail-name {
        font-size: 16px;
        font-weight: 600;
      }
    }

    .detail-content {
      p {
        margin: 8px 0;
        font-size: 14px;
        color: #606266;
      }

      .related-edges {
        margin-top: 12px;
        padding-top: 12px;
        border-top: 1px solid #e4e7ed;

        .related-edge {
          padding: 4px 0;
          font-size: 13px;
          color: #606266;
        }
      }
    }
  }
}

// 修正对比弹窗样式
.revision-compare-container {
  .revision-info-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 8px;

    .revision-stats {
      font-size: 14px;
      color: #606266;

      strong {
        color: #409eff;
      }

      .word-change {
        margin-left: 8px;
        font-weight: 500;
        
        &.increase {
          color: #67c23a;
        }
        
        &.decrease {
          color: #f56c6c;
        }
      }
    }

    .revision-time {
      font-size: 13px;
      color: #909399;
      margin-left: auto;
    }
  }

  .knowledge-used-info {
    margin-bottom: 16px;

    .knowledge-detail {
      p {
        margin: 8px 0;
        font-size: 13px;
        color: #606266;
      }
    }
  }

  // 视图切换
  .view-switch {
    margin-bottom: 16px;
    display: flex;
    justify-content: center;
  }

  // 差异对比视图
  .diff-view {
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    overflow: hidden;
    max-height: calc(100vh - 400px);
    overflow-y: auto;

    .diff-legend {
      display: flex;
      gap: 24px;
      padding: 12px 16px;
      background: #f5f7fa;
      border-bottom: 1px solid #e4e7ed;
      position: sticky;
      top: 0;
      z-index: 1;

      .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #606266;

        .legend-color {
          width: 16px;
          height: 16px;
          border-radius: 3px;
        }

        &.added .legend-color {
          background: #d4edda;
          border: 1px solid #c3e6cb;
        }

        &.removed .legend-color {
          background: #f8d7da;
          border: 1px solid #f5c6cb;
        }

        &.modified .legend-color {
          background: #fff3cd;
          border: 1px solid #ffeeba;
        }
      }
    }

    .diff-content {
      padding: 16px;
      font-family: 'Microsoft YaHei', sans-serif;
      line-height: 1.8;
      font-size: 14px;

      // 使用 :deep() 穿透 scoped 样式，使样式应用于 v-html 动态插入的内容
      :deep(.diff-paragraph) {
        padding: 8px 12px;
        margin-bottom: 8px;
        border-radius: 4px;
        white-space: pre-wrap;
        word-break: break-word;

        &.unchanged {
          background: transparent;
          color: #303133;
        }

        &.added {
          background: #d4edda;
          border-left: 4px solid #28a745;
          color: #155724;
        }

        &.removed {
          background: #f8d7da;
          border-left: 4px solid #dc3545;
          color: #721c24;
          text-decoration: line-through;
          opacity: 0.8;
        }
      }
    }
  }

  .compare-view {
    display: flex;
    gap: 16px;
    height: calc(100vh - 350px);
    min-height: 400px;

    .compare-panel {
      flex: 1;
      display: flex;
      flex-direction: column;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      overflow: hidden;

      .panel-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        background: #f5f7fa;
        border-bottom: 1px solid #e4e7ed;

        .panel-word-count {
          font-size: 13px;
          color: #909399;
        }
      }

      .panel-content {
        flex: 1;
        overflow: hidden;

        .el-textarea {
          height: 100%;

          :deep(.el-textarea__inner) {
            height: 100% !important;
            min-height: 100% !important;
            border: none;
            border-radius: 0;
            font-family: 'Microsoft YaHei', sans-serif;
            line-height: 1.8;
          }
        }
      }
    }
  }
}

// 合规审核详情弹窗样式
.compliance-detail-container {
  .compliance-summary {
    margin-bottom: 20px;

    .compliance-meta {
      margin-top: 12px;
      font-size: 13px;
      color: #909399;
    }
  }

  .compliance-issues {
    .issues-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid #ebeef5;
    }

    .issues-list {
      max-height: calc(100vh - 350px);
      overflow-y: auto;
    }

    .issue-item {
      padding: 16px;
      margin-bottom: 12px;
      border-radius: 8px;
      border: 1px solid #e4e7ed;
      background: #fafafa;

      &.severity-high {
        border-left: 4px solid #f56c6c;
        background: #fef0f0;
      }

      &.severity-medium {
        border-left: 4px solid #e6a23c;
        background: #fdf6ec;
      }

      &.severity-low {
        border-left: 4px solid #909399;
        background: #f4f4f5;
      }

      .issue-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;

        .issue-type {
          font-weight: 500;
          color: #303133;
        }

        .issue-location {
          font-size: 12px;
          color: #909399;
        }
      }

      .issue-content {
        margin-bottom: 12px;
        padding: 12px;
        background: rgba(255, 255, 255, 0.8);
        border-radius: 4px;

        .issue-text, .issue-context {
          margin-bottom: 8px;
          font-size: 14px;
          line-height: 1.6;

          .label {
            color: #909399;
            margin-right: 8px;
          }

          .text {
            color: #f56c6c;
            font-weight: 500;
          }

          .context {
            color: #606266;
          }
        }
      }

      .issue-footer {
        .issue-reason, .issue-suggestion {
          font-size: 13px;
          line-height: 1.6;
          margin-bottom: 6px;

          .label {
            color: #909399;
            margin-right: 8px;
          }
        }
      }
    }
  }
}

// 章节列表合规标记样式
.chapter-status {
  .compliance-tag {
    cursor: pointer;
    margin-left: 8px;
    
    &:hover {
      opacity: 0.9;
      transform: scale(1.05);
    }
    
    &.has-issues {
      animation: pulse 2s infinite;
      font-weight: 500;
    }
  }
}

// 合规问题脉冲动画
@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.4);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(245, 108, 108, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0);
  }
}

// 章节卡片合规问题样式
.chapter-item {
  &.has-compliance-issue {
    border-left: 3px solid #f56c6c;
    background: linear-gradient(to right, rgba(245, 108, 108, 0.05), transparent);
  }
}
</style>
