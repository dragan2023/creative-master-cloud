<!--
  组件: ComplianceDetailDialog
  自动生成于: 脚本批量拆分
-->
<template>
<div class="compliance-detail-container">
        <!-- 审核概况 -->
        <div class="compliance-summary">
          <el-alert
            :type="complianceData?.has_issues ? 'warning' : 'success'"
            :closable="false"
            show-icon
          >
            <template #title>
              <span v-if="complianceData?.has_issues">
                发现 {{ complianceData?.issue_count }} 处潜在合规问题
              </span>
              <span v-else>内容合规，未发现问题</span>
            </template>
          </el-alert>
          <div class="compliance-meta" v-if="complianceData">
            <span>审核时间: {{ formatDateTime(complianceData.check_time) }}</span>
            <span style="margin-left: 16px;">审核级别: {{ complianceData.level === 'strict' ? '严格' : complianceData.level === 'loose' ? '宽松' : '标准' }}</span>
          </div>
        </div>

        <!-- 问题列表 -->
        <div v-if="complianceData?.issues?.length" class="compliance-issues">
          <div class="issues-header">
            <span>问题分布：</span>
            <el-tag type="danger" size="small" v-if="complianceData.issue_summary?.high">
              高危 {{ complianceData.issue_summary.high }}
            </el-tag>
            <el-tag type="warning" size="small" v-if="complianceData.issue_summary?.medium">
              中等 {{ complianceData.issue_summary.medium }}
            </el-tag>
            <el-tag type="info" size="small" v-if="complianceData.issue_summary?.low">
              低危 {{ complianceData.issue_summary.low }}
            </el-tag>
          </div>

          <div class="issues-list">
            <div 
              v-for="issue in complianceData.issues" 
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
                  <span class="context" v-html="sanitizeHtml(issue.context)"></span>
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
        <el-button @click="handleClose">关闭</el-button>
      </template>
</template>

<script setup>
import { formatDateTime, getIssueTypeLabel } from '@/views/novel-writer/utils/contentHelpers'
import DOMPurify from 'dompurify'
import { ref } from 'vue'

defineProps({
    visible: { type: Boolean, default: false },
    complianceData: { type: Object }
})

const emit = defineEmits(['update:visible'])
/** 安全渲染HTML内容，防止XSS攻击 */
const sanitizeHtml = (html) => {
  if (!html) return ''
  return DOMPurify.sanitize(html)
}

const handleClose = () => emit('update:visible', false)

</script>
