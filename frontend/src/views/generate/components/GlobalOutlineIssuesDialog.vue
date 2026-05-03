<!--
  组件: GlobalOutlineIssuesDialog
  全局大纲问题详情弹窗
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="全局大纲质控问题"
    width="800px"
  >
    <div class="issues-dialog-content">
      <el-collapse v-model="activeGlobalOutlineIssues">
        <el-collapse-item 
          v-for="(issue, index) in qcReport?.issues || []" 
          :key="issue.id || index"
          :name="`issue-${issue.id || index}`"
        >
          <template #title>
            <div class="issue-title">
              <el-tag :type="getSeverityType(issue.severity)" size="small">
                {{ getSeverityLabel(issue.severity) }}
              </el-tag>
              <el-tag 
                v-if="issue.priority" 
                :type="issue.priority === 'critical' ? 'danger' : issue.priority === 'high' ? 'warning' : 'info'" 
                size="small"
                style="margin-left: 8px;"
              >
                {{ issue.priority === 'critical' ? '紧急' : issue.priority === 'high' ? '高' : issue.priority === 'medium' ? '中' : '低' }}优先级
              </el-tag>
              <span class="issue-dimension">[{{ getDimensionLabel(issue.dimension) }}]</span>
              <span class="issue-desc">{{ issue.description }}</span>
            </div>
          </template>
          <div class="issue-detail">
            <p v-if="issue.evidence">
              <strong>原文证据:</strong> {{ issue.evidence }}
            </p>
            <div v-if="issue.suggestion">
              <strong>修改建议:</strong>
              <pre class="suggestion-content">{{ issue.suggestion }}</pre>
            </div>
            
            <!-- 调用LLM修正按钮 -->
            <div class="issue-actions" style="margin-top: 16px;">
              <el-button 
                type="primary" 
                size="small" 
                @click="$emit('revise', { issue, qualityReport: qcReport })"
                :loading="revisingIssueId === issue.id"
              >
                <el-icon><MagicStick /></el-icon>
                调用LLM修正
              </el-button>
            </div>
            
            <!-- 用户反馈按钮 -->
            <div v-if="!issue.user_feedback" class="feedback-section" style="margin-top: 16px;">
              <el-divider content-position="left">这个检测结果准确吗?</el-divider>
              <el-button-group>
                <el-button size="small" type="success" @click="$emit('feedback', { issue, type: 'accepted' })">
                  <el-icon><Select /></el-icon>
                  准确
                </el-button>
                <el-button size="small" @click="$emit('feedback', { issue, type: 'ignored' })">
                  <el-icon><RemoveFilled /></el-icon>
                  忽略
                </el-button>
                <el-button size="small" type="danger" @click="$emit('feedback', { issue, type: 'false_positive' })">
                  <el-icon><CircleClose /></el-icon>
                  误报
                </el-button>
              </el-button-group>
            </div>
            <div v-else class="feedback-recorded">
              <el-tag type="success" size="small">
                您的反馈已记录: {{ issue.user_feedback === 'accepted' ? '准确' : issue.user_feedback === 'ignored' ? '忽略' : '误报' }}
              </el-tag>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </el-dialog>
</template>

<script setup>
import { getSeverityType, getSeverityLabel, getDimensionLabel } from '@/views/generate/utils/qcHelpers'
import { MagicStick, Select, RemoveFilled, CircleClose } from '@element-plus/icons-vue'
import { ref } from 'vue'

const activeGlobalOutlineIssues = ref([])

defineProps({
  visible: { type: Boolean, default: false },
  qcReport: { type: Object },
  revisingIssueId: { type: String, default: null }
})

defineEmits(['update:visible', 'revise', 'feedback'])
</script>
