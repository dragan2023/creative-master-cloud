<template>
  <div class="novel-writer-page">
    <div class="page-header">
      <h1 class="page-title">小说/剧本生成</h1>
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        新建项目
      </el-button>
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
          <el-dropdown @click.stop trigger="click">
            <el-icon class="more-icon"><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="editProject(project)">编辑</el-dropdown-item>
                <el-dropdown-item @click="deleteProject(project)" divided>删除</el-dropdown-item>
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
                  <el-select v-model="projectForm.series_script_config.series_type" placeholder="选择剧集类型">
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
                    <el-input-number v-model="projectForm.series_script_config.episode_duration_range[0]" :min="1" :max="120" :step="5" style="width: 100px;" />
                    <span>-</span>
                    <el-input-number v-model="projectForm.series_script_config.episode_duration_range[1]" :min="1" :max="120" :step="5" style="width: 100px;" />
                    <span class="unit">分钟</span>
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
                  <el-select v-model="projectForm.movie_script_config.movie_type" placeholder="选择电影类型">
                    <el-option label="院线电影" value="院线电影" />
                    <el-option label="网络电影" value="网络电影" />
                    <el-option label="微电影" value="微电影" />
                    <el-option label="纪录片" value="纪录片" />
                    <el-option label="动画电影" value="动画电影" />
                  </el-select>
                </el-form-item>
                <el-form-item label="电影时长">
                  <el-input-number v-model="projectForm.movie_script_config.total_duration" :min="5" :max="180" :step="5" />
                  <span class="unit">分钟</span>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MoreFilled, Notebook, Film, VideoCamera } from '@element-plus/icons-vue'
import { novelWriterApi } from '@/api/novel-writer'

const router = useRouter()

// ==================== 常量配置 ====================

// 内容类型提示
const CONTENT_TYPE_HINTS = {
  'novel': '小说：根据大纲生成章节正文，每章约3000字',
  'series_script': '剧集剧本：根据大纲生成分集剧本，支持电视剧/网络剧/短剧等',
  'movie_script': '电影剧本：根据大纲生成场景剧本，支持院线电影/网络电影等'
}

// 小说配置默认值
const DEFAULT_NOVEL_CONFIG = {
  target_platform: '',
  total_words: null,
  words_per_chapter: 3000,
  style_reference: '',
  temperature: 0.8,
  narrative_perspective: '第三人称',
  tone: '正剧'
}

// 剧集剧本配置默认值
const DEFAULT_SERIES_SCRIPT_CONFIG = {
  series_type: '电视剧',
  episode_duration_range: [30, 45],
  scenes_per_episode_range: null,
  format_standard: '标准格式',
  dialogue_narration_ratio: '均衡',
  target_broadcast: '',
  episode_count: 24,
  style_reference: '',
  dialogue_style: '自然对话',
  narrative_rhythm: '紧凑',
  script_mode: 'real'  // 剧本模式：real=现实模式，virtual=虚拟模式
}

// 电影剧本配置默认值
const DEFAULT_MOVIE_SCRIPT_CONFIG = {
  movie_type: '院线电影',
  total_duration: 90,
  format_standard: '标准格式',
  dialogue_narration_ratio: '均衡',
  target_platform: '',
  style_reference: '',
  dialogue_style: '自然对话',
  narrative_rhythm: '紧凑',
  script_mode: 'real'  // 剧本模式：real=现实模式，virtual=虚拟模式
}

// 剧集类型对应的时长配置
const SERIES_DURATION_CONFIG = {
  '电视剧': { min: 40, max: 60, defaultMin: 45, defaultMax: 50, hint: '电视剧通常45-50分钟/集' },
  '网络剧': { min: 20, max: 50, defaultMin: 30, defaultMax: 45, hint: '网络剧通常30-45分钟/集' },
  '短剧': { min: 3, max: 20, defaultMin: 5, defaultMax: 15, hint: '短剧通常5-15分钟/集' }
}

// 电影类型对应的时长配置
const MOVIE_DURATION_CONFIG = {
  '院线电影': { default: 120, hint: '院线电影通常90-120分钟' },
  '网络电影': { default: 90, hint: '网络电影通常60-90分钟' },
  '微电影': { default: 30, hint: '微电影通常20-45分钟' },
  '纪录片': { default: 90, hint: '纪录片时长灵活' },
  '动画电影': { default: 90, hint: '动画电影通常80-100分钟' }
}

// 剧本格式标准选项
const FORMAT_STANDARD_OPTIONS = [
  { value: '标准格式', label: '标准格式', desc: '包含场景头、角色名、动作描述、对白等完整元素' },
  { value: '简格式', label: '简格式', desc: '精简场景描述，突出对白核心' },
  { value: '网络平台格式', label: '网络平台格式', desc: '适配流媒体平台，节奏快、信息密度高' },
  { value: '短剧格式', label: '短剧格式', desc: '单场戏结构清晰，适合竖屏观看' }
]

// 对白与叙述比例选项
const DIALOGUE_RATIO_OPTIONS = [
  { value: '对话为主', label: '对话为主', desc: '60%以上为对白' },
  { value: '均衡', label: '均衡', desc: '对白与动作描述各占约50%' },
  { value: '叙述为主', label: '叙述为主', desc: '侧重场景描述' },
  { value: '动作导向', label: '动作导向', desc: '以动作描述为主' }
]

// 投放平台选项
const TARGET_BROADCAST_OPTIONS = [
  '央视', '地方卫视', '爱奇艺', '腾讯视频', '优酷', '芒果TV', 'B站', '抖音', '快手', 'Netflix', '院线发行'
]

// 小说投放平台选项
const NOVEL_PLATFORM_OPTIONS = [
  '起点中文网', '晋江文学城', '番茄小说', '豆瓣阅读', '纵横中文网', '17K小说网', '飞卢小说', '其他'
]

// ==================== 数据状态 ====================

const projects = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(12)
const filterType = ref('')
const filterStatus = ref('')

// 对话框
const dialogVisible = ref(false)
const editingProject = ref(null)
const saving = ref(false)

// 表单数据
const projectForm = ref({
  title: '',
  content_type: 'novel',
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
  graphrag_enabled: true
})

// ==================== 计算属性 ====================

const contentTypeHint = computed(() => {
  return CONTENT_TYPE_HINTS[projectForm.value.content_type] || ''
})

// ==================== 方法 ====================

// 获取类型标签
function getTypeLabel(contentType) {
  const labels = {
    'novel': '小说',
    'series_script': '剧集',
    'movie_script': '电影',
    'script': '剧本' // 兼容旧版
  }
  return labels[contentType] || '未知'
}

// 获取类型样式类
function getTypeClass(contentType) {
  const classes = {
    'novel': 'novel',
    'series_script': 'series-script',
    'movie_script': 'movie-script',
    'script': 'script' // 兼容旧版
  }
  return classes[contentType] || 'novel'
}

// 获取单位标签
function getUnitLabel(contentType) {
  const labels = {
    'novel': '章',
    'series_script': '集',
    'movie_script': '场',
    'script': '章'
  }
  return labels[contentType] || '章'
}

// 内容类型变更处理
function onContentTypeChange(contentType) {
  // 重置对应的配置
  if (contentType === 'novel') {
    projectForm.value.novel_config = { ...DEFAULT_NOVEL_CONFIG }
  } else if (contentType === 'series_script') {
    projectForm.value.series_script_config = { ...DEFAULT_SERIES_SCRIPT_CONFIG }
  } else if (contentType === 'movie_script') {
    projectForm.value.movie_script_config = { ...DEFAULT_MOVIE_SCRIPT_CONFIG }
  }
}

// 加载项目列表
async function loadProjects() {
  loading.value = true
  try {
    const res = await novelWriterApi.getProjects({
      content_type: filterType.value,  // 使用新版参数
      status: filterStatus.value,
      page: currentPage.value,
      page_size: pageSize.value
    })
    
    if (res.success) {
      projects.value = res.data.items
      total.value = res.data.total
    } else {
      ElMessage.error(res.message || '加载项目列表失败')
    }
  } catch (error) {
    ElMessage.error('加载项目列表失败')
  } finally {
    loading.value = false
  }
}

// 显示创建对话框
function showCreateDialog() {
  editingProject.value = null
  projectForm.value = {
    title: '',
    content_type: 'novel',
    genre: '',
    novel_config: { ...DEFAULT_NOVEL_CONFIG },
    series_script_config: { ...DEFAULT_SERIES_SCRIPT_CONFIG },
    movie_script_config: { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
    kb_vertical_enabled: false,
    kb_user_specific_enabled: false,
    kb_manual_enabled: false,
    graphrag_enabled: true
  }
  dialogVisible.value = true
}

// 编辑项目
function editProject(project) {
  editingProject.value = project
  
  // 获取内容类型
  const contentType = project.content_type || (project.project_type === 'novel' ? 'novel' : 'series_script')
  
  projectForm.value = {
    title: project.title,
    content_type: contentType,
    genre: project.genre || '',
    // 从项目数据中获取配置
    novel_config: project.novel_config || { ...DEFAULT_NOVEL_CONFIG },
    series_script_config: project.series_script_config || { ...DEFAULT_SERIES_SCRIPT_CONFIG },
    movie_script_config: project.movie_script_config || { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
    // 知识库配置
    kb_vertical_enabled: project.knowledge_base_config?.kb_vertical_enabled || false,
    kb_user_specific_enabled: project.knowledge_base_config?.kb_user_specific_enabled || false,
    kb_manual_enabled: project.knowledge_base_config?.kb_manual_enabled || false,
    graphrag_enabled: project.knowledge_base_config?.graphrag_enabled !== false
  }
  
  dialogVisible.value = true
}

// 保存项目
async function saveProject() {
  if (!projectForm.value.title) {
    ElMessage.warning('请输入项目标题')
    return
  }

  saving.value = true
  try {
    const data = {
      title: projectForm.value.title,
      content_type: projectForm.value.content_type,
      genre: projectForm.value.genre,
      // 根据内容类型传递对应配置
      novel_config: projectForm.value.content_type === 'novel' ? projectForm.value.novel_config : null,
      series_script_config: projectForm.value.content_type === 'series_script' ? projectForm.value.series_script_config : null,
      movie_script_config: projectForm.value.content_type === 'movie_script' ? projectForm.value.movie_script_config : null,
      // 知识库配置
      knowledge_base_config: {
        kb_vertical_enabled: projectForm.value.kb_vertical_enabled,
        kb_user_specific_enabled: projectForm.value.kb_user_specific_enabled,
        kb_manual_enabled: projectForm.value.kb_manual_enabled,
        graphrag_enabled: projectForm.value.graphrag_enabled,
        kb_vertical_ids: [],
        kb_user_specific_ids: [],
        kb_manual_ids: []
      }
    }

    if (editingProject.value) {
      await novelWriterApi.updateProject(editingProject.value.id, data)
      ElMessage.success('项目已更新')
      dialogVisible.value = false
      loadProjects()
    } else {
      const res = await novelWriterApi.createProject(data)
      ElMessage.success('项目创建成功')
      dialogVisible.value = false
      await loadProjects()
      router.push(`/novel-writer/${res.data.id}`)
    }
  } catch (error) {
    ElMessage.error(editingProject.value ? '更新失败' : '创建失败')
  } finally {
    saving.value = false
  }
}

// 删除项目
async function deleteProject(project) {
  try {
    await ElMessageBox.confirm(
      `确定要删除项目"${project.title}"吗？删除后无法恢复。`,
      '确认删除',
      { type: 'warning' }
    )

    await novelWriterApi.deleteProject(project.id)
    ElMessage.success('项目已删除')
    loadProjects()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 跳转到项目详情
function goToProject(projectId) {
  router.push(`/novel-writer/${projectId}`)
}

// 辅助函数
function getStatusType(status) {
  const types = {
    init: 'info',
    directory: 'warning',
    generating: 'primary',
    completed: 'success',
    failed: 'danger',
    paused: 'warning'
  }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = {
    init: '初始化',
    directory: '目录生成中',
    generating: '生成中',
    completed: '已完成',
    failed: '失败',
    paused: '已暂停'
  }
  return texts[status] || status
}

function getProgressStatus(status) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return null
}

function formatTime(timeStr) {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`

  return date.toLocaleDateString()
}

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

    .more-icon {
      cursor: pointer;
      color: #909399;
      transition: all 0.3s;
      padding: 4px;
      border-radius: 4px;

      &:hover {
        color: #409eff;
        background: rgba(64, 158, 255, 0.1);
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
