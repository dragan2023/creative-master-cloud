<!--
  组件: IssuesDetailDialog
  质控问题详情弹窗
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="质控问题详情"
    width="900px"
  >
    <div class="issues-dialog-content">
      <el-collapse v-model="activeIssues">
        <el-collapse-item 
          v-for="(issue, index) in qualityReport.issues" 
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
              <el-tag 
                v-if="issue.metadata?.adjusted_by_feedback" 
                type="success" 
                size="small"
                style="margin-left: 8px;"
              >
                已优化
              </el-tag>
              <span class="issue-dimension">[{{ issue.dimension }}]</span>
              <span class="issue-desc">{{ issue.description }}</span>
            </div>
          </template>
          <div class="issue-detail">
            <p v-if="issue.location">
              <strong>位置:</strong> 第{{ issue.location.chapter_number }}单元
            </p>
            <p v-if="issue.evidence">
              <strong>原文证据:</strong> {{ issue.evidence }}
            </p>
            <div v-if="issue.suggestion">
              <strong>修改建议:</strong>
              <pre class="suggestion-content">{{ issue.suggestion }}</pre>
            </div>
            
            <p v-if="issue.fix_difficulty">
              <strong>修正难度:</strong> 
              <el-tag :type="issue.fix_difficulty === 'easy' ? 'success' : issue.fix_difficulty === 'medium' ? 'warning' : 'danger'" size="small">
                {{ issue.fix_difficulty === 'easy' ? '简单' : issue.fix_difficulty === 'medium' ? '中等' : '困难' }}
              </el-tag>
            </p>
            
            <div v-if="issue.auto_fix" class="auto-fix-section">
              <el-divider content-position="left">自动修正方案</el-divider>
              <el-alert 
                :title="issue.auto_fix.description" 
                type="info" 
                :closable="false"
                show-icon
              />
              <el-row :gutter="16" style="margin-top: 12px;">
                <el-col :span="12">
                  <h5>修正前</h5>
                  <el-input 
                    type="textarea" 
                    :rows="6" 
                    :model-value="issue.auto_fix.original"
                    readonly
                    class="content-comparison"
                  />
                </el-col>
                <el-col :span="12">
                  <h5>修正后</h5>
                  <el-input 
                    type="textarea" 
                    :rows="6" 
                    :model-value="issue.auto_fix.fixed"
                    readonly
                    class="content-comparison"
                  />
                </el-col>
              </el-row>
              <div class="auto-fix-actions">
                <el-tag size="small">
                  置信度: {{ (issue.auto_fix.confidence * 100).toFixed(0) }}%
                </el-tag>
                <el-button 
                  type="primary" 
                  size="small" 
                  @click="$emit('apply-fix', issue)"
                  :loading="applyingFixIndex === (qualityReport?.issues || []).indexOf(issue)"
                  style="margin-left: 12px;"
                >
                  <el-icon><Check /></el-icon>
                  应用修正
                </el-button>
              </div>
            </div>
            <div v-else class="no-auto-fix">
              <el-button 
                type="warning" 
                size="small" 
                @click="$emit('apply-fix', issue)"
                :loading="applyingFixIndex === (qualityReport?.issues || []).indexOf(issue)"
              >
                <el-icon><Edit /></el-icon>
                生成并应用修正
              </el-button>
            </div>
            
            <div v-if="!issue.user_feedback" class="feedback-section">
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
import { getSeverityType, getSeverityLabel } from '@/views/generate/utils/qcHelpers'
import { Check, Edit, Select, RemoveFilled, CircleClose } from '@element-plus/icons-vue'
import { ref } from 'vue'

const activeIssues = ref([])

defineProps({
  visible: { type: Boolean, default: false },
  qualityReport: { type: Object },
  applyingFixIndex: { type: Number, default: -1 }
})

defineEmits(['update:visible', 'apply-fix', 'feedback'])
</script>
