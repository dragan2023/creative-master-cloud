<template>
  <div class="novel-writer-page">
    <div class="page-header">
      <h1 class="page-title">小说/剧本生成</h1>
      <div class="header-actions">
        <el-button @click="goToModelConfig">
          <el-icon><Setting /></el-icon>
          模型配置
        </el-button>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          新建项目
        </el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filterType" placeholder="内容类型" clearable @change="loadProjects">
        <el-option label="全部" value="" />
        <el-option label="小说" value="novel" />
        <el-option label="剧集剧本" value="series_script" />
        <el-option label="电影剧本" value="movie_script" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="项目状态" clearable @change="loadProjects">
        <el-option label="全部" value="" />
        <el-option label="初始化" value="init" />
        <el-option label="生成中" value="generating" />
        <el-option label="已完成" value="completed" />
        <el-option label="已暂停" value="paused" />
        <el-option label="失败" value="failed" />
      </el-select>
    </div>

    <!-- 项目列表 -->
    <div class="project-grid" v-loading="loading">
      <el-empty v-if="projects.length === 0" description="暂无项目，点击上方按钮创建">
        <el-button type="primary" @click="showCreateDialog">创建第一个项目</el-button>
      </el-empty>

      <div
        v-for="project in projects"
        :key="project.id"
        class="project-card"
        @click="goToProject(project.id)"
      >
        <div class="card-header">
          <div class="project-type" :class="getTypeClass(project.content_type || project.project_type)">
            {{ getTypeLabel(project.content_type || project.project_type) }}
          </div>
          <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, project)">
            <div class="more-icon-wrapper" @click.stop>
              <el-icon class="more-icon"><MoreFilled /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <h3 class="project-title">{{ project.title }}</h3>

        <div class="project-meta">
          <span v-if="project.genre">{{ project.genre }}</span>
          <span v-if="project.target_platform">{{ project.target_platform }}</span>
        </div>

        <div class="project-progress">
          <div class="progress-info">
            <span>进度: {{ project.completed_chapters }}/{{ project.total_chapters }}{{ getUnitLabel(project.content_type) }}</span>
            <span class="progress-percent">{{ project.progress_percentage.toFixed(1) }}%</span>
          </div>
          <el-progress
            :percentage="project.progress_percentage"
            :status="getProgressStatus(project.status)"
            :stroke-width="8"
          />
        </div>

        <div class="project-status">
          <el-tag :type="getStatusType(project.status)" size="small">
            {{ getStatusText(project.status) }}
          </el-tag>
          <span class="update-time">{{ formatTime(project.updated_at) }}</span>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="pagination" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadProjects"
      />
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingProject ? '编辑项目' : '创建新项目'"
      width="600px"
    >
      <el-form :model="projectForm" label-width="100px">
        <el-form-item label="项目标题" required>
          <el-input v-model="projectForm.title" placeholder="请输入项目标题" />
        </el-form-item>

        <el-form-item label="内容类型" required>
          <el-radio-group v-model="projectForm.content_type" @change="onContentTypeChange">
            <el-radio-button value="novel">
              <el-icon><Notebook /></el-icon>
              小说
            </el-radio-button>
            <el-radio-button value="series_script">
              <el-icon><VideoCamera /></el-icon>
              剧集剧本
            </el-radio-button>
            <el-radio-button value="movie_script">
              <el-icon><Film /></el-icon>
              电影剧本
            </el-radio-button>
          </el-radio-group>
          <div class="content-type-hint">
            <el-text type="info" size="small">{{ contentTypeHint }}</el-text>
          </div>
        </el-form-item>

        <el-form-item label="题材标签">
          <el-input v-model="projectForm.genre" placeholder="如：言情、悬疑、科幻" />
        </el-form-item>

        <!-- v4.2：知识图谱继承 -->
        <el-form-item label="继承知识图谱">
          <el-input-number
            v-model="projectForm.inheritKbId"
            :min="1"
            placeholder="粘贴四阶段生成的图谱ID"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip kb-inherit-tip">
            <el-icon><InfoFilled /></el-icon>
            在创意生成页面构建知识图谱后，复制图谱ID粘贴到此处即可继承
            <br />留空则创建不带知识图谱的项目
          </div>
        </el-form-item>

        <el-form-item label="生成配置">
          <el-collapse>
            <el-collapse-item title="高级设置" name="advanced">
              <!-- 小说配置 -->
              <template v-if="projectForm.content_type === 'novel'">
                <el-form-item label="投放平台">
                  <el-select v-model="projectForm.novel_config.target_platform" placeholder="选择投放平台" clearable filterable>
                    <el-option 
                      v-for="platform in NOVEL_PLATFORM_OPTIONS" 
                      :key="platform"
                      :label="platform" 
                      :value="platform"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="每章字数">
                  <el-input-number v-model="projectForm.novel_config.words_per_chapter" :min="1000" :max="10000" :step="500" />
                  <span class="unit">字</span>
                </el-form-item>
                <el-form-item label="总字数">
                  <el-input-number v-model="projectForm.novel_config.total_words" :min="10000" :max="5000000" :step="10000" placeholder="可选" />
                  <span class="unit">字（可选）</span>
                </el-form-item>
                <el-form-item label="叙事视角">
                  <el-select v-model="projectForm.novel_config.narrative_perspective">
                    <el-option label="第一人称" value="第一人称" />
                    <el-option label="第三人称" value="第三人称" />
                  </el-select>
                </el-form-item>
                <el-form-item label="基调风格">
                  <el-select v-model="projectForm.novel_config.tone" placeholder="选择风格">
                    <el-option label="正剧" value="正剧" />
                    <el-option label="轻松" value="轻松" />
                    <el-option label="幽默" value="幽默" />
                    <el-option label="严肃" value="严肃" />
                    <el-option label="温馨" value="温馨" />
                    <el-option label="热血" value="热血" />
                  </el-select>
                </el-form-item>
                <el-form-item label="风格模仿">
                  <el-input 
                    v-model="projectForm.novel_config.style_reference" 
                    type="textarea" 
                    :rows="2"
                    placeholder="可粘贴喜欢的作品片段，AI将模仿其风格（可选）" 
                  />
                </el-form-item>
                <el-form-item label="温度参数">
                  <el-slider v-model="projectForm.novel_config.temperature" :min="0" :max="1" :step="0.1" show-input />
                </el-form-item>
              </template>
              
              <!-- 剧集剧本配置 -->
              <template v-else-if="projectForm.content_type === 'series_script'">
                <el-form-item label="剧本模式">
                  <el-radio-group v-model="projectForm.series_script_config.script_mode">
                    <el-radio value="real">
                      <span>现实模式</span>
                      <el-tag size="small" type="info" style="margin-left: 4px;">真人拍摄</el-tag>
                    </el-radio>
                    <el-radio value="virtual">
                      <span>虚拟模式</span>
                      <el-tag size="small" type="success" style="margin-left: 4px;">AI视频生成</el-tag>
                    </el-radio>
                  </el-radio-group>
                  <div class="form-tip">
                    <el-text type="info" size="small">虚拟模式将简化分镜复杂度，更适合AI视频生成</el-text>
                  </div>
                </el-form-item>
                <el-form-item label="剧集类型">
                  <el-select v-model="projectForm.series_script_config.series_type" placeholder="选择剧集类型" @change="onSeriesTypeChange">
                    <el-option label="电视剧" value="电视剧" />
                    <el-option label="网络剧" value="网络剧" />
                    <el-option label="短剧" value="短剧" />
                    <el-option label="微短剧" value="微短剧" />
                    <el-option label="网剧" value="网剧" />
                    <el-option label="竖屏剧" value="竖屏剧" />
                  </el-select>
                </el-form-item>
                <el-form-item label="总集数">
                  <el-input-number v-model="projectForm.series_script_config.episode_count" :min="1" :max="100" />
                </el-form-item>
                <el-form-item label="每集时长">
                  <div class="config-row">
                    <el-input-number 
                      v-model="projectForm.series_script_config.episode_duration_range[0]" 
                      :min="getSeriesDurationMin()" 
                      :max="getSeriesDurationMax()" 
                      :step="5" 
                      style="width: 100px;" 
                    />
                    <span>-</span>
                    <el-input-number 
                      v-model="projectForm.series_script_config.episode_duration_range[1]" 
                      :min="getSeriesDurationMin()" 
                      :max="getSeriesDurationMax()" 
                      :step="5" 
                      style="width: 100px;" 
                    />
                    <span class="unit">分钟</span>
                  </div>
                  <div class="form-tip" v-if="getSeriesDurationHint()">
                    <el-text type="info" size="small">{{ getSeriesDurationHint() }}</el-text>
                  </div>
                </el-form-item>
                <el-form-item label="剧本格式">
                  <el-select v-model="projectForm.series_script_config.format_standard" placeholder="选择格式标准">
                    <el-option 
                      v-for="opt in FORMAT_STANDARD_OPTIONS" 
                      :key="opt.value"
                      :label="opt.label" 
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="对白比例">
                  <el-select v-model="projectForm.series_script_config.dialogue_narration_ratio" placeholder="选择对白比例">
                    <el-option 
                      v-for="opt in DIALOGUE_RATIO_OPTIONS" 
                      :key="opt.value"
                      :label="opt.label" 
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="投放平台">
                  <el-select v-model="projectForm.series_script_config.target_broadcast" placeholder="选择目标投放平台" clearable filterable>
                    <el-option 
                      v-for="platform in TARGET_BROADCAST_OPTIONS" 
                      :key="platform"
                      :label="platform" 
                      :value="platform"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="风格模仿">
                  <el-input 
                    v-model="projectForm.series_script_config.style_reference" 
                    type="textarea" 
                    :rows="2"
                    placeholder="可粘贴喜欢的剧本片段，AI将模仿其风格（可选）" 
                  />
                </el-form-item>
              </template>
              
              <!-- 电影剧本配置 -->
              <template v-else-if="projectForm.content_type === 'movie_script'">
                <el-form-item label="剧本模式">
                  <el-radio-group v-model="projectForm.movie_script_config.script_mode">
                    <el-radio value="real">
                      <span>现实模式</span>
                      <el-tag size="small" type="info" style="margin-left: 4px;">真人拍摄</el-tag>
                    </el-radio>
                    <el-radio value="virtual">
                      <span>虚拟模式</span>
                      <el-tag size="small" type="success" style="margin-left: 4px;">AI视频生成</el-tag>
                    </el-radio>
                  </el-radio-group>
                  <div class="form-tip">
                    <el-text type="info" size="small">虚拟模式将简化分镜复杂度，更适合AI视频生成</el-text>
                  </div>
                </el-form-item>
                <el-form-item label="电影类型">
                  <el-select v-model="projectForm.movie_script_config.movie_type" placeholder="选择电影类型" @change="onMovieTypeChange">
                    <el-option label="院线电影" value="院线电影" />
                    <el-option label="网络电影" value="网络电影" />
                    <el-option label="微电影" value="微电影" />
                    <el-option label="纪录片" value="纪录片" />
                    <el-option label="动画电影" value="动画电影" />
                  </el-select>
                </el-form-item>
                <el-form-item label="电影时长">
                  <el-input-number 
                    v-model="projectForm.movie_script_config.total_duration" 
                    :min="getMovieDurationMin()" 
                    :max="getMovieDurationMax()" 
                    :step="5" 
                  />
                  <span class="unit">分钟</span>
                  <div class="form-tip" v-if="getMovieDurationHint()">
                    <el-text type="info" size="small">{{ getMovieDurationHint() }}</el-text>
                  </div>
                </el-form-item>
                <el-form-item label="剧本格式">
                  <el-select v-model="projectForm.movie_script_config.format_standard" placeholder="选择格式标准">
                    <el-option label="标准格式" value="标准格式" />
                    <el-option label="影院格式" value="影院格式" />
                    <el-option label="电视电影格式" value="电视电影格式" />
                  </el-select>
                </el-form-item>
                <el-form-item label="对白比例">
                  <el-select v-model="projectForm.movie_script_config.dialogue_narration_ratio" placeholder="选择对白比例">
                    <el-option 
                      v-for="opt in DIALOGUE_RATIO_OPTIONS" 
                      :key="opt.value"
                      :label="opt.label" 
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="投放平台">
                  <el-select v-model="projectForm.movie_script_config.target_platform" placeholder="选择投放平台" clearable>
                    <el-option label="院线发行" value="院线发行" />
                    <el-option label="网络平台" value="网络平台" />
                    <el-option label="电影节" value="电影节" />
                  </el-select>
                </el-form-item>
                <el-form-item label="风格模仿">
                  <el-input 
                    v-model="projectForm.movie_script_config.style_reference" 
                    type="textarea" 
                    :rows="2"
                    placeholder="可粘贴喜欢的剧本片段，AI将模仿其风格（可选）" 
                  />
                </el-form-item>
              </template>
            </el-collapse-item>
            
            <el-collapse-item title="公共知识库配置（可选参考）" name="knowledge">
              <div class="kb-config-hint" style="margin-bottom: 12px; padding: 8px; background: #fdf6ec; border-radius: 4px; font-size: 12px; color: #e6a23c;">
                <i class="el-icon-warning-outline" style="margin-right: 4px;"></i>
                公共知识库用于正文生成时参考创意理论、案例技巧等。项目专属知识库将在上传大纲后自动构建，完全独立于公共知识库。
              </div>
              <el-form-item label="垂直领域知识库">
                <el-switch v-model="projectForm.kb_vertical_enabled" />
                <span class="kb-tip">小说/剧本案例、技巧</span>
              </el-form-item>
              <el-form-item label="用户专属知识库">
                <el-switch v-model="projectForm.kb_user_specific_enabled" />
                <span class="kb-tip">您上传的个性化知识</span>
              </el-form-item>
              <el-form-item label="官方手册">
                <el-switch v-model="projectForm.kb_manual_enabled" />
                <span class="kb-tip">官方规范、标准手册</span>
              </el-form-item>
              <el-form-item label="GraphRAG增强">
                <el-switch v-model="projectForm.graphrag_enabled" />
                <span class="kb-tip">知识图谱增强检索</span>
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProject" :loading="saving">
          {{ editingProject ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onActivated } from 'vue'
import { Plus, MoreFilled, Notebook, Film, VideoCamera, Setting, InfoFilled } from '@element-plus/icons-vue'

// 组合式函数
import { useProjectList } from './composables/useProjectList'
import { useProjectForm } from './composables/useProjectForm'

// 常量配置
import {
  CONTENT_TYPE_HINTS,
  NOVEL_PLATFORM_OPTIONS,
  FORMAT_STANDARD_OPTIONS,
  DIALOGUE_RATIO_OPTIONS,
  TARGET_BROADCAST_OPTIONS,
  getSeriesDurationMin as cfgGetSeriesDurationMin,
  getSeriesDurationMax as cfgGetSeriesDurationMax,
  getSeriesDurationHint as cfgGetSeriesDurationHint,
  getMovieDurationMin as cfgGetMovieDurationMin,
  getMovieDurationMax as cfgGetMovieDurationMax,
  getMovieDurationHint as cfgGetMovieDurationHint,
  updateSeriesDurationByType,
  updateMovieDurationByType
} from './config/projectFormConfig'

// ==================== 项目列表 ====================
const list = useProjectList()
const {
  projects,
  loading,
  total,
  currentPage,
  pageSize,
  filterType,
  filterStatus,
  loadProjects,
  goToProject,
  goToModelConfig,
  handleCommand: listHandleCommand,
  getTypeLabel,
  getTypeClass,
  getUnitLabel,
  getStatusType,
  getStatusText,
  getProgressStatus,
  formatTime
} = list

// ==================== 项目表单 ====================
const form = useProjectForm(loadProjects)
const {
  dialogVisible,
  editingProject,
  saving,
  projectForm,
  showCreateDialog,
  editProject,
  saveProject,
  deleteProject,
  onContentTypeChange: formOnContentTypeChange
} = form

// ==================== 计算属性 ====================
const contentTypeHint = computed(() => {
  return CONTENT_TYPE_HINTS[projectForm.value.content_type] || ''
})

// ==================== 包装函数（保持模板兼容性）====================

function handleCommand(command, project) {
  listHandleCommand(command, project, { editProject, deleteProject })
}

function onContentTypeChange(contentType) {
  formOnContentTypeChange(contentType)
}

function onSeriesTypeChange(seriesType) {
  updateSeriesDurationByType(projectForm.value, seriesType)
}

function onMovieTypeChange(movieType) {
  updateMovieDurationByType(projectForm.value, movieType)
}

function getSeriesDurationMin() {
  return cfgGetSeriesDurationMin(projectForm.value)
}

function getSeriesDurationMax() {
  return cfgGetSeriesDurationMax(projectForm.value)
}

function getSeriesDurationHint() {
  return cfgGetSeriesDurationHint(projectForm.value)
}

function getMovieDurationMin() {
  return cfgGetMovieDurationMin(projectForm.value)
}

function getMovieDurationMax() {
  return cfgGetMovieDurationMax(projectForm.value)
}

function getMovieDurationHint() {
  return cfgGetMovieDurationHint(projectForm.value)
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadProjects()
})

onActivated(() => {
  loadProjects()
})
</script>

<style lang="scss" scoped>
.novel-writer-page {
  max-width: 1200px;
  margin: 0 auto;
}

.form-tip {
  margin-top: 8px;
  line-height: 1.5;
}

.kb-inherit-tip {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;

  .el-icon {
    margin-top: 2px;
    flex-shrink: 0;
  }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  .page-title {
    font-size: 24px;
    font-weight: 600;
    color: #303133;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    
    &::before {
      content: '';
      width: 4px;
      height: 24px;
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 2px;
    }
  }
  
  .header-actions {
    display: flex;
    gap: 12px;
  }
  
  .el-button--primary {
    background: linear-gradient(135deg, #409EFF 0%, #00D4AA 100%);
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
    transition: all 0.3s;
    
    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4);
    }
  }
}

.filter-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;

  .el-select {
    width: 150px;
  }
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 20px;
  min-height: 200px;
}

.project-card {
  background: #fff;
  border-radius: 16px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(64, 158, 255, 0.1);
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #409EFF, #00D4AA);
    transform: scaleX(0);
    transition: transform 0.4s;
  }

  &:hover {
    transform: translateY(-6px);
    box-shadow: 0 12px 40px rgba(64, 158, 255, 0.15);
    border-color: rgba(64, 158, 255, 0.3);
    
    &::before {
      transform: scaleX(1);
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;

    .project-type {
      padding: 5px 14px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;

      &.novel {
        background: linear-gradient(135deg, rgba(64, 158, 255, 0.15), rgba(64, 158, 255, 0.05));
        color: #409eff;
        border: 1px solid rgba(64, 158, 255, 0.2);
      }

      &.series-script {
        background: linear-gradient(135deg, rgba(245, 108, 108, 0.15), rgba(245, 108, 108, 0.05));
        color: #f56c6c;
        border: 1px solid rgba(245, 108, 108, 0.2);
      }
      
      &.movie-script {
        background: linear-gradient(135deg, rgba(103, 194, 58, 0.15), rgba(103, 194, 58, 0.05));
        color: #67c23a;
        border: 1px solid rgba(103, 194, 58, 0.2);
      }
      
      &.script {
        background: linear-gradient(135deg, rgba(245, 108, 108, 0.15), rgba(245, 108, 108, 0.05));
        color: #f56c6c;
        border: 1px solid rgba(245, 108, 108, 0.2);
      }
    }

    .more-icon-wrapper {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.3s;

      &:hover {
        background: rgba(64, 158, 255, 0.1);
      }
    }

    .more-icon {
      font-size: 18px;
      color: #909399;
      transition: all 0.3s;

      &:hover {
        color: #409eff;
      }
    }
  }

  .project-title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin: 0 0 10px 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .project-meta {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #909399;

    span {
      background: rgba(64, 158, 255, 0.06);
      padding: 3px 10px;
      border-radius: 6px;
      border: 1px solid rgba(64, 158, 255, 0.1);
    }
  }

  .project-progress {
    margin-bottom: 14px;

    .progress-info {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;
      font-size: 13px;
      color: #606266;

      .progress-percent {
        color: #409eff;
        font-weight: 600;
      }
    }
    
    :deep(.el-progress) {
      .el-progress-bar__outer {
        background: rgba(64, 158, 255, 0.1);
        border-radius: 6px;
      }
      
      .el-progress-bar__inner {
        background: linear-gradient(90deg, #409EFF, #00D4AA);
        border-radius: 6px;
      }
    }
  }

  .project-status {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .update-time {
      font-size: 12px;
      color: #909399;
    }
  }
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.kb-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 12px;
}

.content-type-hint {
  margin-top: 8px;
}

// 配置表单样式
.config-section {
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
  
  &:last-child {
    border-bottom: none;
  }
  
  .section-title {
    font-size: 14px;
    font-weight: 500;
    color: #606266;
    margin-bottom: 12px;
  }
}

.config-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  
  .label {
    min-width: 80px;
    color: #606266;
    font-size: 13px;
  }
  
  .value {
    flex: 1;
  }
  
  .unit {
    color: #909399;
    font-size: 13px;
  }
}

.hint-text {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

// Radio Button 样式调整
:deep(.el-radio-button__inner) {
  display: flex;
  align-items: center;
  gap: 4px;
}

// 对话框样式
:deep(.el-dialog) {
  border-radius: 16px;
  
  .el-dialog__header {
    padding: 20px 24px;
    border-bottom: 1px solid rgba(64, 158, 255, 0.1);
    
    .el-dialog__title {
      font-weight: 600;
      color: #303133;
    }
  }
  
  .el-dialog__body {
    padding: 24px;
  }
  
  .el-dialog__footer {
    padding: 16px 24px;
    border-top: 1px solid rgba(64, 158, 255, 0.1);
  }
}

.kb-config-hint {
  margin-bottom: 12px;
  padding: 10px 14px;
  background: linear-gradient(135deg, rgba(230, 162, 60, 0.08), rgba(230, 162, 60, 0.03));
  border-radius: 8px;
  font-size: 12px;
  color: #e6a23c;
  border: 1px solid rgba(230, 162, 60, 0.2);
}
</style>
