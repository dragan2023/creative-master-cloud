<!--
  组件: QCHistoryDialog
  质控历史详情弹窗
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="质控历史详情"
    width="800px"
  >
    <div class="qc-history-content">
      <!-- 质控执行信息 -->
      <el-descriptions :column="2" border class="qc-summary">
        <el-descriptions-item label="执行时间">
          {{ qcReportData?.applied_at || '自动质控' }}
        </el-descriptions-item>
        <el-descriptions-item label="修正问题数">
          <el-tag :type="issuesFixed > 0 ? 'warning' : 'success'">
            {{ issuesFixed }}个
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="综合得分" v-if="qcReportData?.overall_score">
          <el-tag :type="getScoreType(qcReportData.overall_score)">
            {{ qcReportData.overall_score?.toFixed(1) || 0 }}分
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="问题总数" v-if="qcReportData?.issues">
          <el-tag :type="qcReportData.issues?.length > 0 ? 'warning' : 'success'">
            {{ qcReportData.issues?.length || 0 }}个
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      
      <!-- 维度得分 -->
      <div v-if="qcReportData?.dimension_scores" class="dimension-scores" style="margin: 16px 0;">
        <h4>维度得分</h4>
        <el-row :gutter="16">
          <el-col :span="6" v-for="(score, dim) in qcReportData.dimension_scores" :key="dim">
            <el-card shadow="hover" class="dimension-card">
              <template #header>
                <div class="card-header">
                  <span>{{ getDimensionLabel(dim) }}</span>
                </div>
              </template>
              <el-progress 
                :percentage="score" 
                :color="getScoreColor(score)"
                :stroke-width="12"
              />
              <div class="score-text">{{ score.toFixed(1) }}分</div>
            </el-card>
          </el-col>
        </el-row>
      </div>
      
      <!-- 问题列表 -->
      <div v-if="qcReportData?.issues?.length > 0" class="issues-list">
        <h4>检测到的问题</h4>
        <el-collapse accordion>
          <el-collapse-item 
            v-for="issue in qcReportData.issues" 
            :key="issue.id"
            :name="issue.id"
          >
            <template #title>
              <div class="issue-title">
                <el-tag 
                  :type="getSeverityType(issue.severity)" 
                  size="small"
                  style="margin-right: 8px;"
                >
                  {{ getSeverityLabel(issue.severity) }}
                </el-tag>
                <span class="issue-category">{{ issue.category }}</span>
              </div>
            </template>
            <div class="issue-content">
              <p><strong>描述:</strong> {{ issue.description }}</p>
              <p v-if="issue.evidence"><strong>证据:</strong> {{ issue.evidence }}</p>
              <p v-if="issue.suggestion"><strong>建议:</strong> {{ issue.suggestion }}</p>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
      
      <!-- 无问题提示 -->
      <el-alert
        v-else-if="qcReportData"
        title="质量检测通过"
        type="success"
        :closable="false"
        style="margin-top: 16px;"
      >
        内容质量良好，未发现需要修正的问题。
      </el-alert>
    </div>
    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { getSeverityType, getSeverityLabel, getDimensionLabel, getScoreType, getScoreColor } from '@/views/generate/utils/qcHelpers'

defineProps({
  visible: { type: Boolean, default: false },
  qcReportData: { type: Object },
  issuesFixed: { type: Number, default: 0 }
})

const emit = defineEmits(['update:visible'])
const handleClose = () => emit('update:visible', false)
</script>
