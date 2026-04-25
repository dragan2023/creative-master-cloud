<template>
  <div class="quality-analysis-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <el-button :icon="ArrowLeft" @click="goBack" text>返回项目</el-button>
      <h3>AI 质量分析</h3>
    </div>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else-if="!projectId" class="error-state">
      <el-empty description="缺少项目ID，请从项目详情页进入" />
    </div>

    <div v-else class="quality-content">
      <!-- 综合得分 -->
      <el-card class="score-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>综合质量评分</span>
            <el-button size="small" type="primary" @click="runFullAnalysis" :loading="analyzing">
              重新分析
            </el-button>
          </div>
        </template>
        <div class="score-section">
          <el-progress
            type="dashboard"
            :percentage="overallScore"
            :color="scoreColor"
            :width="160"
          >
            <template #default="{ percentage }">
              <span class="score-value">{{ percentage }}</span>
              <span class="score-label">分</span>
            </template>
          </el-progress>
          <div class="score-desc">
            <p class="score-level">{{ scoreLevel }}</p>
            <p class="score-detail">基于三维质控（一致性、逻辑性、完整性）综合评估</p>
          </div>
        </div>
      </el-card>

      <!-- 三维度得分 -->
      <el-row :gutter="16" class="dimension-cards">
        <el-col :span="8" v-for="dim in dimensions" :key="dim.key">
          <el-card shadow="hover" class="dimension-card">
            <div class="dim-header">
              <el-icon :size="24" :color="dim.color"><component :is="dim.icon" /></el-icon>
              <span class="dim-name">{{ dim.name }}</span>
            </div>
            <div class="dim-score">
              <span :style="{ color: dim.color }">{{ dim.score }}</span>
              <span class="dim-max">/100</span>
            </div>
            <el-progress
              :percentage="dim.score"
              :color="dim.color"
              :stroke-width="8"
              :show-text="false"
            />
            <p class="dim-desc">{{ dim.description }}</p>
          </el-card>
        </el-col>
      </el-row>

      <!-- 问题列表 -->
      <el-card class="issues-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>检测到的问题 ({{ issues.length }})</span>
            <el-select v-model="severityFilter" size="small" style="width: 140px" clearable placeholder="筛选严重程度">
              <el-option label="严重" value="high" />
              <el-option label="中等" value="medium" />
              <el-option label="轻微" value="low" />
            </el-select>
          </div>
        </template>
        <div v-if="filteredIssues.length === 0" class="no-issues">
          <el-empty description="未检测到问题" :image-size="80" />
        </div>
        <div v-else class="issues-list">
          <div
            v-for="(issue, idx) in filteredIssues"
            :key="idx"
            class="issue-item"
            :class="`severity-${issue.severity}`"
          >
            <div class="issue-header">
              <el-tag :type="getSeverityType(issue.severity)" size="small">
                {{ getSeverityLabel(issue.severity) }}
              </el-tag>
              <el-tag type="info" size="small">{{ issue.dimension || '通用' }}</el-tag>
              <span class="issue-location" v-if="issue.location">{{ issue.location }}</span>
            </div>
            <div class="issue-body">
              <p class="issue-desc">{{ issue.description }}</p>
              <p class="issue-suggestion" v-if="issue.suggestion">
                <strong>建议：</strong>{{ issue.suggestion }}
              </p>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 已应用修正 -->
      <el-card v-if="appliedFixes.length > 0" class="fixes-card" shadow="hover">
        <template #header>
          <span>已应用修正 ({{ appliedFixes.length }})</span>
        </template>
        <el-timeline>
          <el-timeline-item
            v-for="(fix, idx) in appliedFixes"
            :key="idx"
            :timestamp="fix.timestamp || ''"
            placement="top"
            :type="fix.success ? 'success' : 'danger'"
          >
            <div class="fix-item">
              <p class="fix-desc">{{ fix.description || `修正 #${idx + 1}` }}</p>
              <div v-if="fix.original_text" class="fix-diff">
                <span class="fix-removed">{{ fix.original_text }}</span>
                <span class="arrow">→</span>
                <span class="fix-added">{{ fix.fixed_text }}</span>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, DataAnalysis, Connection, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { novelWriterApi, qualityControlApi } from '@/api'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.projectId || route.params.id)
const loading = ref(true)
const analyzing = ref(false)
const overallScore = ref(0)
const issues = ref([])
const appliedFixes = ref([])
const severityFilter = ref('')

const dimensions = ref([
  {
    key: 'consistency',
    name: '一致性',
    description: '角色、设定、情节前后是否一致',
    score: 0,
    color: '#409EFF',
    icon: 'Connection'
  },
  {
    key: 'logic',
    name: '逻辑性',
    description: '情节发展、因果关系是否合理',
    score: 0,
    color: '#E6A23C',
    icon: 'DataAnalysis'
  },
  {
    key: 'completeness',
    name: '完整性',
    description: '故事线索、角色发展是否完整',
    score: 0,
    color: '#67C23A',
    icon: 'Document'
  }
])

const scoreColor = computed(() => {
  const s = overallScore.value
  if (s >= 80) return '#67c23a'
  if (s >= 60) return '#e6a23c'
  return '#f56c6c'
})

const scoreLevel = computed(() => {
  const s = overallScore.value
  if (s >= 90) return '优秀'
  if (s >= 80) return '良好'
  if (s >= 70) return '中等'
  if (s >= 60) return '及格'
  return '需改进'
})

const filteredIssues = computed(() => {
  if (!severityFilter.value) return issues.value
  return issues.value.filter(i => i.severity === severityFilter.value)
})

function goBack() {
  if (projectId.value) {
    router.push(`/novel-writer/${projectId.value}`)
  } else {
    router.push('/novel-writer')
  }
}

function getSeverityType(severity) {
  if (severity === 'high' || severity === '严重') return 'danger'
  if (severity === 'medium' || severity === '中等') return 'warning'
  return 'info'
}

function getSeverityLabel(severity) {
  if (severity === 'high') return '严重'
  if (severity === 'medium') return '中等'
  if (severity === 'low') return '轻微'
  return severity
}

async function loadProjectData() {
  if (!projectId.value) {
    loading.value = false
    return
  }

  try {
    loading.value = true
    const res = await novelWriterApi.getProject(projectId.value)
    if (res.data?.code === 0 || res.data?.data) {
      const project = res.data.data || res.data
      // 从项目元数据中加载质控数据
      const metadata = project.metadata || project.meta || {}
      const qcData = metadata.quality_control || metadata.qc || {}

      if (qcData.overall_score !== undefined) {
        overallScore.value = qcData.overall_score
      }
      if (qcData.issues) {
        issues.value = qcData.issues
      }
      if (qcData.dimensions) {
        dimensions.value.forEach(dim => {
          if (qcData.dimensions[dim.key] !== undefined) {
            dim.score = qcData.dimensions[dim.key]
          }
        })
      }
      if (qcData.applied_fixes) {
        appliedFixes.value = qcData.applied_fixes
      }

      // 从各维度分数计算总分
      if (!qcData.overall_score && qcData.dimensions) {
        const dimScores = Object.values(qcData.dimensions)
        if (dimScores.length > 0) {
          overallScore.value = Math.round(dimScores.reduce((a, b) => a + b, 0) / dimScores.length)
        }
      }
    }
  } catch (e) {
    console.error('[QualityAnalysis] 加载项目数据失败:', e)
  } finally {
    loading.value = false
  }
}

async function runFullAnalysis() {
  if (!projectId.value) return
  analyzing.value = true
  try {
    const res = await qualityControlApi.reAnalyze({
      project_id: projectId.value,
      content_type: 'novel'
    })
    if (res.data?.code === 0 || res.data?.data) {
      const data = res.data.data || res.data
      overallScore.value = data.overall_score || 0
      issues.value = data.issues || []

      if (data.dimensions) {
        dimensions.value.forEach(dim => {
          if (data.dimensions[dim.key] !== undefined) {
            dim.score = data.dimensions[dim.key]
          }
        })
      }

      ElMessage.success('质量分析完成')
    }
  } catch (e) {
    console.error('[QualityAnalysis] 分析失败:', e)
    ElMessage.error('质量分析失败，请稍后重试')
  } finally {
    analyzing.value = false
  }
}

onMounted(() => {
  loadProjectData()
})
</script>

<style lang="scss" scoped>
.quality-analysis-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;

  .page-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid #eee;

    h3 { margin: 0; font-size: 18px; }
  }

  .score-card {
    margin-bottom: 16px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .score-section {
      display: flex;
      align-items: center;
      gap: 32px;
      padding: 16px 0;

      .score-value { font-size: 36px; font-weight: 700; }
      .score-label { font-size: 14px; color: #909399; }
      .score-desc {
        .score-level { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
        .score-detail { font-size: 13px; color: #909399; }
      }
    }
  }

  .dimension-cards {
    margin-bottom: 16px;

    .dimension-card {
      text-align: center;

      .dim-header {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        margin-bottom: 12px;

        .dim-name { font-weight: 600; font-size: 15px; }
      }

      .dim-score {
        margin-bottom: 8px;
        font-size: 28px;
        font-weight: 700;

        .dim-max { font-size: 14px; color: #c0c4cc; font-weight: 400; }
      }

      .dim-desc {
        margin-top: 8px;
        font-size: 12px;
        color: #909399;
      }
    }
  }

  .issues-card, .fixes-card {
    margin-bottom: 16px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  }

  .issue-item {
    padding: 12px;
    margin-bottom: 8px;
    border-radius: 6px;
    border-left: 3px solid #dcdfe6;

    &.severity-high { border-left-color: #f56c6c; background: #fef0f0; }
    &.severity-medium { border-left-color: #e6a23c; background: #fdf6ec; }
    &.severity-low { border-left-color: #909399; background: #f4f4f5; }

    .issue-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;

      .issue-location { font-size: 12px; color: #909399; }
    }

    .issue-desc { font-size: 14px; margin: 0 0 4px; }
    .issue-suggestion { font-size: 13px; color: #606266; margin: 0; }
  }

  .fix-item {
    .fix-desc { font-size: 14px; margin: 0 0 4px; }

    .fix-diff {
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 8px;

      .fix-removed { color: #f56c6c; text-decoration: line-through; }
      .fix-added { color: #67c23a; font-weight: 500; }
      .arrow { color: #909399; }
    }
  }
}
</style>
