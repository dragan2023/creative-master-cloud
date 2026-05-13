<!--
  ContentQCReportPanel.vue - 正文质控报告展示面板
  
  功能：
  1. 六维度得分雷达图展示
  2. 问题分类列表（按严重度排序）
  3. 问题详情展开
  4. 修正状态标记
  
  与单元概述质控报告完全独立。
-->
<template>
  <div class="content-qc-report-panel">
    <!-- 得分概览 -->
    <div class="score-overview">
      <div class="overall-score">
        <el-progress
          type="dashboard"
          :percentage="overallScore"
          :color="scoreColor"
          :width="100"
          :stroke-width="8"
        >
          <template #default="{ percentage }">
            <span class="score-number">{{ percentage }}</span>
            <span class="score-label">综合得分</span>
          </template>
        </el-progress>
      </div>
      
      <!-- 六维度得分 -->
      <div class="dimension-scores">
        <div
          v-for="dim in dimensionData"
          :key="dim.key"
          class="dimension-item"
        >
          <div class="dim-header">
            <span class="dim-name">{{ dim.name }}</span>
            <el-tag size="small" :type="getScoreTagType(dim.score)">
              {{ dim.score || '-' }}
            </el-tag>
          </div>
          <el-progress
            :percentage="dim.score || 0"
            :color="getDimColor(dim.score)"
            :show-text="false"
            :stroke-width="4"
          />
          <span class="dim-desc">{{ dim.description }}</span>
        </div>
      </div>
    </div>

    <el-divider />

    <!-- 问题统计 -->
    <div class="issues-summary">
      <el-statistic title="总问题数" :value="statValue(totalIssues)" />
      <el-statistic title="严重问题" :value="statValue(criticalCount)" class="critical-stat" />
      <el-statistic title="已修正" :value="statValue(fixedCount)" class="fixed-stat" />
      <el-statistic title="待处理" :value="statValue(pendingCount)" class="pending-stat" />
    </div>

    <el-divider />

    <!-- 问题列表 -->
    <div class="issues-list">
      <div class="list-header">
        <h4>问题详情</h4>
        <el-radio-group v-model="filterSeverity" size="small">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="critical">严重</el-radio-button>
          <el-radio-button value="warning">中等</el-radio-button>
          <el-radio-button value="info">轻微</el-radio-button>
        </el-radio-group>
      </div>

      <el-collapse v-if="filteredIssues.length > 0" accordion>
        <el-collapse-item
          v-for="(issue, idx) in filteredIssues"
          :key="issue.id || idx"
          :name="idx"
        >
          <template #title>
            <div class="issue-title">
              <el-tag :type="getSeverityType(issue.severity)" size="small">
                {{ issue.severity || 'info' }}
              </el-tag>
              <span class="issue-dimension">{{ getDimensionName(issue.dimension) }}</span>
              <span class="issue-category">{{ issue.category }}</span>
              <el-icon v-if="isIssueFixed(issue)" color="#67c23a"><CircleCheckFilled /></el-icon>
            </div>
          </template>

          <div class="issue-detail">
            <p class="issue-description">
              <strong>问题描述：</strong>{{ issue.description }}
            </p>
            
            <p v-if="issue.evidence" class="issue-evidence">
              <strong>原文证据：</strong>
              <span class="evidence-text">{{ issue.evidence }}</span>
            </p>
            
            <p v-if="issue.suggestion" class="issue-suggestion">
              <strong>修正建议：</strong>{{ issue.suggestion }}
            </p>
            
            <p v-if="issue.location" class="issue-location">
              <strong>位置：</strong>第{{ issue.location.chapter_number || issue.location.unit_index }}章
              {{ issue.location.position ? `，位置${issue.location.position}` : '' }}
            </p>

            <!-- 修正操作 -->
            <div v-if="issue.auto_fix" class="issue-fix-actions">
              <el-button
                type="primary"
                size="small"
                @click="$emit('preview-fix', issue)"
              >
                <el-icon><View /></el-icon>
                预览修正
              </el-button>
              <span class="fix-confidence">
                置信度: {{ Math.round(issue.auto_fix.confidence * 100) }}%
              </span>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>

      <el-empty v-else description="暂无问题" :image-size="60" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { CircleCheckFilled, View } from '@element-plus/icons-vue'

import { QC_DIMENSIONS, getSeverityType, getDimensionName, getScoreColor } from '../composables/useContentQualityControl'

const props = defineProps({
  report: { type: Object, default: null },
  unitIndex: { type: Number, default: null }
})

const emit = defineEmits(['preview-fix', 'apply-fix'])

// 过滤严重度
const filterSeverity = ref('all')

// 综合得分
const overallScore = computed(() => {
  return props.report?.score || props.report?.overall_score || 0
})

// 得分颜色
const scoreColor = computed(() => getScoreColor(overallScore.value))

// 六维度数据
const dimensionData = computed(() => {
  const scores = props.report?.dimension_scores || props.report?.report?.dimension_scores || {}
  return QC_DIMENSIONS.map(dim => ({
    ...dim,
    score: scores[dim.key] || 0
  }))
})

// 问题列表
const issues = computed(() => {
  return props.report?.issues || props.report?.report?.issues || []
})

// 过滤后的问题
const filteredIssues = computed(() => {
  if (filterSeverity.value === 'all') {
    return issues.value
  }
  return issues.value.filter(issue => {
    const sev = issue.severity?.toLowerCase() || 'info'
    return sev === filterSeverity.value
  })
})

// 问题统计
const totalIssues = computed(() => issues.value.length)
const criticalCount = computed(() => 
  issues.value.filter(i => i.severity === 'critical' || i.severity === '严重').length
)
const warningCount = computed(() => 
  issues.value.filter(i => i.severity === 'warning' || i.severity === '中等').length
)
const fixedCount = computed(() => 
  props.report?.fixed_count || props.report?.fixes_applied?.length || 0
)
const pendingCount = computed(() => 
  totalIssues.value - fixedCount.value
)

// 判断问题是否已修正
function isIssueFixed(issue) {
  const fixes = props.report?.fixes_applied || []
  return fixes.some(f => f.issue_id === issue.id)
}

// 获取得分Tag类型
function getScoreTagType(score) {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

// Element Plus el-statistic 兼容：value=0 会导致 InvalidCharacterError
function statValue(val) {
  return val === 0 ? '0' : val
}

// 获取维度得分颜色
function getDimColor(score) {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}
</script>

<style lang="scss" scoped>
.content-qc-report-panel {
  padding: 16px;

  .score-overview {
    display: flex;
    gap: 24px;
    align-items: flex-start;

    .overall-score {
      text-align: center;

      .score-number {
        font-size: 24px;
        font-weight: 700;
        display: block;
      }

      .score-label {
        font-size: 12px;
        color: #909399;
        display: block;
        margin-top: 4px;
      }
    }

    .dimension-scores {
      flex: 1;

      .dimension-item {
        margin-bottom: 12px;

        .dim-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 4px;

          .dim-name {
            font-weight: 500;
            font-size: 13px;
          }
        }

        .dim-desc {
          font-size: 11px;
          color: #909399;
          margin-top: 2px;
        }
      }
    }
  }

  .issues-summary {
    display: flex;
    gap: 24px;
    justify-content: space-around;
    padding: 8px 0;

    :deep(.el-statistic) {
      .el-statistic-title {
        font-size: 12px;
        color: #909399;
      }
      .el-statistic-number {
        font-size: 20px;
      }
    }

    .critical-stat :deep(.el-statistic-number) { color: #f56c6c; }
    .fixed-stat :deep(.el-statistic-number) { color: #67c23a; }
    .pending-stat :deep(.el-statistic-number) { color: #e6a23c; }
  }

  .issues-list {
    .list-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      h4 { margin: 0; font-size: 14px; }
    }

    .issue-title {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 1;

      .issue-dimension {
        font-weight: 500;
        font-size: 13px;
      }

      .issue-category {
        color: #909399;
        font-size: 12px;
      }
    }

    .issue-detail {
      padding: 8px 0;
      font-size: 13px;
      line-height: 1.6;

      p { margin-bottom: 8px; }

      .evidence-text {
        background: #fef0f0;
        padding: 4px 8px;
        border-radius: 4px;
        color: #f56c6c;
      }

      .issue-fix-actions {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 12px;
        padding-top: 8px;
        border-top: 1px solid #e4e7ed;

        .fix-confidence {
          font-size: 12px;
          color: #909399;
        }
      }
    }
  }
}
</style>