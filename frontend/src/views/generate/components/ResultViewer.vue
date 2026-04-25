<template>
  <div class="result-container" v-if="showResult">
    <!-- 两阶段大纲生成：阶段指示器 -->
    <div v-if="useTwoStageMode" class="outline-stages">
      <el-steps :active="outlineStage" align-center finish-status="success">
        <el-step title="全局大纲" description="世界观、人物、结构" />
        <el-step title="审核修改" description="确认全局大纲" />
        <el-step title="单元概述" description="章节/分集概要" />
        <el-step title="完成" description="可下载或导入" />
      </el-steps>
      <div class="stage-actions">
        <!-- 阶段1：全局大纲生成中，显示中断按钮 -->
        <el-button
          v-if="outlineStage === 1 && globalOutlineGenerating"
          type="danger"
          @click="$emit('stop')"
        >
          <el-icon><CircleClose /></el-icon>
          中断生成
        </el-button>
        <!-- 阶段2：全局大纲完成，显示继续调整大纲、质量检测和继续生成按钮 -->
        <template v-if="outlineStage === 2">
          <!-- 继续调整大纲按钮(与LLM对话修订) -->
          <el-button
            type="warning"
            @click="$emit('start-revision')"
          >
            <el-icon><ChatDotRound /></el-icon>
            继续调整大纲
          </el-button>
          <!-- 质量检测按钮组(v1.1优化: 显示质控状态) -->
          <el-button
            :type="globalOutlineQCReport ? (globalOutlineQCReport.overall_score >= 80 ? 'success' : 'warning') : 'success'"
            @click="handleGlobalOutlineQC"
            :loading="globalOutlineQCLoading"
            :disabled="globalOutlineGenerating"
          >
            <el-icon><DataAnalysis /></el-icon>
            {{ getQCButtonText }}
          </el-button>
          <!-- 质控状态徽标 -->
          <el-tag
            v-if="globalOutlineQCReport && !globalOutlineQCLoading"
            :type="getScoreType(globalOutlineQCReport.overall_score)"
            size="small"
            style="margin-left: 8px;"
          >
            {{ globalOutlineQCReport.overall_score?.toFixed(1) || 0 }}分
            <span v-if="globalOutlineQCReport.issues?.length > 0">
              · {{ globalOutlineQCReport.issues.length }}个问题
            </span>
          </el-tag>
          <!-- 确认并继续生成单元概述 -->
          <el-button
            type="primary"
            @click="$emit('generate-unit-summaries')"
            :loading="unitSummariesGenerating"
          >
            确认全局大纲，继续生成单元概述
          </el-button>
        </template>
        <!-- 阶段3：单元概述生成中，显示中断按钮 -->
        <el-button
          v-if="outlineStage === 3 && unitSummariesGenerating"
          type="danger"
          @click="$emit('cancel-unit-summaries')"
        >
          <el-icon><VideoPause /></el-icon>
          中断生成
        </el-button>
        <!-- 单元概述质量检测按钮（手动触发，阶段3-4显示） -->
        <el-button
          v-if="unitSummaries && Object.keys(unitSummaries).length > 0 && contentType === 'novel' && (outlineStage === 3 || outlineStage === 4)"
          type="warning"
          @click="$emit('quality-control-unit-summaries')"
          :loading="unitSummariesQCLoading"
        >
          <el-icon><Search /></el-icon>
          {{ qcApplied ? '重新检测' : '质量检测' }}
          <el-badge v-if="issuesFixed > 0" :value="issuesFixed" class="qc-badge" />
        </el-button>
        <!-- 阶段4：全部完成，显示下载按钮 -->
        <el-button
          v-if="outlineStage === 4"
          type="success"
          @click="$emit('download-outline')"
        >
          <el-icon><Download /></el-icon>
          下载完整大纲
        </el-button>
        <!-- 续生成按钮：已生成章节数 < 预期总数时显示 -->
        <el-button
          v-if="outlineStage === 4 && canResumeUnitSummaries"
          type="success"
          @click="$emit('resume-unit-summaries')"
          :loading="unitSummariesGenerating"
        >
          <el-icon><RefreshRight /></el-icon>
          续生成剩余{{ remainingUnitCount }}章
        </el-button>
        <!-- 从后端获取断点信息后显示续生成按钮（页面刷新后恢复状态） -->
        <el-button
          v-if="outlineStage === 4 && showResumeFromBackend"
          type="success"
          @click="$emit('resume-unit-summaries-from-backend')"
          :loading="unitSummariesGenerating"
        >
          <el-icon><RefreshRight /></el-icon>
          续生成剩余{{ backendResumeInfo.remaining_count }}章
        </el-button>
        <!-- 从指定单元重新生成 - 已移除，使用续生成替代 -->
        <el-button
          v-if="outlineStage === 4"
          @click="$emit('reset-two-stage')"
        >
          重新开始
        </el-button>
      </div>
      
      <!-- 逻辑检测状态 -->
      <div v-if="logicChecking || logicCheckResult" class="logic-check-status">
        <div v-if="logicChecking" class="logic-checking">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在进行逻辑检测...</span>
        </div>
        <div v-else-if="logicCheckResult" class="logic-check-result">
          <div v-if="logicCheckResult.has_issues" class="has-issues">
            <el-icon><WarningFilled /></el-icon>
            <span>检测到 {{ logicCheckResult.issues?.length || 0 }} 个逻辑问题</span>
            <el-button size="small" text @click="showLogicIssuesDialog = true">
              查看详情
            </el-button>
          </div>
          <div v-else class="no-issues">
            <el-icon><CircleCheckFilled /></el-icon>
            <span>逻辑检测通过，未发现问题</span>
          </div>
        </div>
      </div>
    </div>

    <div class="result-header">
      <h3>{{ useTwoStageMode ? (outlineStage <= 2 ? '全局大纲' : '完整大纲') : '生成结果' }}</h3>
      <div class="result-meta">
        <el-tag v-if="generationDuration" type="info" size="small" class="duration-tag">
          <el-icon><Timer /></el-icon>
          耗时: {{ formatDuration(generationDuration) }}
        </el-tag>
        <!-- v2.3新增：质控详情入口按钮 -->
        <el-button v-if="qcReportData" text size="small" @click="showQCHistoryDialog = true">
          <el-icon><Document /></el-icon>
          质控详情
        </el-button>
        <div class="result-actions">
          <el-button text @click="$emit('copy')">
            <el-icon><CopyDocument /></el-icon>
            复制
          </el-button>
          <el-button text @click="$emit('download')">
            <el-icon><Download /></el-icon>
            下载
          </el-button>
          <el-button v-if="!useTwoStageMode" text @click="$emit('regenerate')">
            <el-icon><Refresh /></el-icon>
            重新生成
          </el-button>
          <el-button v-if="useTwoStageMode && outlineStage > 0" text @click="$emit('reset-two-stage')">
            <el-icon><Refresh /></el-icon>
            重新开始
          </el-button>
        </div>
      </div>
    </div>
    
    <!-- 两阶段大纲生成：全局大纲编辑区（阶段2显示） -->
    <div v-if="useTwoStageMode && outlineStage === 2" class="global-outline-edit">
      <div class="edit-header">
        <span class="edit-tip"><el-icon><Edit /></el-icon> 您可以直接编辑全局大纲内容，修改后将用于生成单元概述</span>
        <div class="edit-actions">
          <!-- 编辑按钮(主要操作,放在最前面) -->
          <el-button v-if="!editingGlobalOutline" type="primary" size="small" @click="$emit('start-edit-global')">
            <el-icon><Edit /></el-icon> 编辑大纲
          </el-button>
          <template v-else>
            <el-button type="success" size="small" @click="$emit('save-global-edit')">
              <el-icon><Check /></el-icon> 保存修改
            </el-button>
            <el-button size="small" @click="$emit('cancel-global-edit')">
              <el-icon><Close /></el-icon> 取消
            </el-button>
          </template>
          <!-- 全局大纲质量检测按钮(次要操作) - v2.3优化 -->
          <!-- 导入大纲场景：显示“重新检测”按钮，调用自动质控API -->
          <el-button 
            v-if="importedOutline"
            type="primary" 
            size="small" 
            @click="handleGlobalOutlineQC"
            :loading="autoQCLoading || globalOutlineQCLoading"
          >
            <el-icon><Refresh /></el-icon>
            重新检测
          </el-button>
          <!-- 非导入场景：不再显示质量检测按钮，已在主操作区显示 -->
        </div>
      </div>
      <div class="edit-content">
        <el-input
          v-if="editingGlobalOutline"
          :model-value="editingGlobalOutlineContent"
          @update:model-value="$emit('update:editingGlobalOutlineContent', $event)"
          type="textarea"
          :rows="20"
          placeholder="请输入全局大纲内容..."
        />
        <div v-else class="preview-content markdown-content" v-html="renderedGlobalOutline"></div>
      </div>
    </div>
    
    <!-- v1.1新增: SSE实时进度显示 -->
    <div v-if="globalOutlineQCLoading && qcProgress" class="qc-progress-panel" style="margin-top: 20px;">
      <el-card shadow="hover">
        <template #header>
          <div class="progress-header">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>质量检测进行中...</span>
          </div>
        </template>
        <div class="progress-content">
          <!-- 总体进度 -->
          <el-progress 
            :percentage="qcProgress.progress || 0" 
            :stroke-width="20"
            :text-inside="true"
            :color="getProgressColor(qcProgress.progress)"
            style="margin-bottom: 16px;"
          />
          
          <!-- 当前状态 -->
          <div class="progress-status">
            <el-tag :type="getProgressStatusType(qcProgress.status)">
              {{ qcProgress.message || '正在分析...' }}
            </el-tag>
            <span v-if="qcProgress.dimension" style="margin-left: 8px; color: #909399;">
              当前维度: {{ getDimensionName(qcProgress.dimension) }}
            </span>
          </div>
          
          <!-- v1.1新增: 重连状态警告 -->
          <el-alert
            v-if="isReconnecting"
            type="warning"
            :closable="false"
            show-icon
            style="margin-top: 12px;"
          >
            <template #title>
              <el-icon class="is-loading" style="margin-right: 4px;"><Loading /></el-icon>
              {{ reconnectMessage }}
            </template>
          </el-alert>
          
          <!-- 维度进度列表 -->
          <div v-if="qcProgress.data?.dimensions" class="dimension-progress" style="margin-top: 16px;">
            <el-row :gutter="8">
              <el-col :span="6" v-for="dim in qcProgress.data.dimensions" :key="dim">
                <el-tag size="small" type="info">{{ getDimensionName(dim) }}</el-tag>
              </el-col>
            </el-row>
          </div>
        </div>
      </el-card>
    </div>
    
    <!-- 全局大纲质控报告显示区（独立显示，不受阶段限制）-->
    <!-- v2.3优化：导入大纲场景不显示完整报告，只显示简短标记 -->
    <div v-if="globalOutlineQCReport && !importedOutline" class="global-outline-qc-report" style="margin-top: 20px;">
        <el-divider content-position="left">
          <el-icon><DataAnalysis /></el-icon>
          全局大纲质量检测报告
          <el-button 
            type="primary" 
            size="small" 
            @click="handleGlobalOutlineQC"
            :loading="globalOutlineQCLoading"
            style="margin-left: 16px;"
          >
            <el-icon><Refresh /></el-icon>
            重新检测
          </el-button>
        </el-divider>
        
        <!-- 质控总结 -->
        <el-descriptions :column="2" border class="qc-summary">
          <el-descriptions-item label="综合得分">
            <el-tag :type="getScoreType(globalOutlineQCReport.overall_score)" size="large">
              {{ globalOutlineQCReport.overall_score?.toFixed(1) || 0 }}分
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="问题总数">
            <el-tag :type="globalOutlineQCReport.issues?.length > 0 ? 'warning' : 'success'">
              {{ globalOutlineQCReport.issues?.length || 0 }}个
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        
        <!-- 四维度得分 -->
        <div class="dimension-scores" style="margin: 16px 0;">
          <h4>维度得分</h4>
          <el-row :gutter="16">
            <el-col :span="6" v-for="(score, dim) in globalOutlineQCReport.dimension_scores" :key="dim">
              <el-card shadow="hover" class="dimension-card">
                <template #header>
                  <div class="card-header">
                    <span>{{ getDimensionName(dim) }}</span>
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
        
        <!-- 问题列表入口按钮 -->
        <div v-if="globalOutlineQCReport.issues?.length > 0" class="issues-entry" style="margin: 16px 0;">
          <el-button 
            type="primary" 
            size="large"
            @click="showGlobalOutlineIssuesDialog = true"
          >
            <el-icon><WarningFilled /></el-icon>
            查看问题详情（{{ globalOutlineQCReport.issues.length }}个问题）
          </el-button>
        </div>
        
        <!-- 问题列表(直接显示) -->
        <div v-if="globalOutlineQCReport.issues?.length > 0 && !showGlobalOutlineIssuesDialog" class="issues-list">
          <h4>检测到的问题</h4>
          <el-collapse accordion>
            <el-collapse-item 
              v-for="issue in globalOutlineQCReport.issues" 
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
                  <span class="issue-id" style="margin-left: 8px; color: #999;">{{ issue.id }}</span>
                </div>
              </template>
              <div class="issue-content">
                <p><strong>描述:</strong> {{ issue.description }}</p>
                <p v-if="issue.evidence"><strong>证据:</strong> {{ issue.evidence }}</p>
                <p v-if="issue.suggestion"><strong>建议:</strong> {{ issue.suggestion }}</p>
                
                <!-- 修正按钮 -->
                <div class="issue-actions" style="margin-top: 12px;">
                  <el-button 
                    type="primary" 
                    size="small" 
                    @click="$emit('revise-global-outline', { issue, qualityReport: globalOutlineQCReport })"
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
                    <el-button size="small" type="success" @click="handleGlobalOutlineFeedback(issue, 'accepted')">
                      <el-icon><Select /></el-icon>
                      准确
                    </el-button>
                    <el-button size="small" @click="handleGlobalOutlineFeedback(issue, 'ignored')">
                      <el-icon><RemoveFilled /></el-icon>
                      忽略
                    </el-button>
                    <el-button size="small" type="danger" @click="handleGlobalOutlineFeedback(issue, 'false_positive')">
                      <el-icon><CircleClose /></el-icon>
                      误报
                    </el-button>
                  </el-button-group>
                </div>
                <div v-else class="feedback-recorded" style="margin-top: 12px;">
                  <el-tag type="success" size="small">
                    您的反馈已记录: {{ issue.user_feedback === 'accepted' ? '准确' : issue.user_feedback === 'ignored' ? '忽略' : '误报' }}
                  </el-tag>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
        
        <!-- 无问题提示 -->
        <el-alert
          v-else
          title="太棒了！未检测到质量问题"
          type="success"
          :closable="false"
          style="margin-top: 16px;"
        >
          <template #default>
            <p>全局大纲质量优秀，可以继续生成单元概述。</p>
          </template>
        </el-alert>
    </div>
    
    <!-- 全局大纲问题详情弹窗 -->
    <el-dialog
      v-model="showGlobalOutlineIssuesDialog"
      title="全局大纲质控问题详情"
      width="900px"
      top="5vh"
      :close-on-click-modal="true"
      destroy-on-close
      class="issues-dialog"
    >
      <div class="issues-dialog-content">
        <el-collapse v-model="activeGlobalOutlineIssues">
          <el-collapse-item 
            v-for="(issue, index) in globalOutlineQCReport?.issues || []" 
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
                <span class="issue-dimension">[{{ getDimensionName(issue.dimension) }}]</span>
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
                  @click="$emit('revise-global-outline', { issue, qualityReport: globalOutlineQCReport })"
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
                  <el-button size="small" type="success" @click="handleGlobalOutlineFeedback(issue, 'accepted')">
                    <el-icon><Select /></el-icon>
                    准确
                  </el-button>
                  <el-button size="small" @click="handleGlobalOutlineFeedback(issue, 'ignored')">
                    <el-icon><RemoveFilled /></el-icon>
                    忽略
                  </el-button>
                  <el-button size="small" type="danger" @click="handleGlobalOutlineFeedback(issue, 'false_positive')">
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
    
    <!-- 单元概述完整质控报告展示区（手动模式）-->
    <!-- v2.4新增：位于单元概述正文上方，包含完整交互功能 -->
    <div v-if="unitSummariesQCReport && unitSummariesQCMode === 'manual'" class="unit-summaries-qc-report" style="margin-top: 20px;">
        <el-divider content-position="left">
          <el-icon><DataAnalysis /></el-icon>
          单元概述质量检测报告（手动模式）
          <el-button 
            type="primary" 
            size="small" 
            @click="$emit('quality-control-unit-summaries')"
            :loading="unitSummariesQCLoading"
            style="margin-left: 16px;"
          >
            <el-icon><Refresh /></el-icon>
            重新检测
          </el-button>
        </el-divider>
        
        <!-- 质控总结 -->
        <el-descriptions :column="2" border class="qc-summary">
          <el-descriptions-item label="综合得分">
            <el-tag :type="getScoreType(unitSummariesQCReport.overall_score)" size="large">
              {{ unitSummariesQCReport.overall_score?.toFixed(1) || 0 }}分
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="问题总数">
            <el-tag :type="unitSummariesQCReport.issues?.length > 0 ? 'warning' : 'success'">
              {{ unitSummariesQCReport.issues?.length || 0 }}个
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
        
        <!-- 维度得分 -->
        <div v-if="unitSummariesQCReport.dimension_scores" class="dimension-scores" style="margin: 16px 0;">
          <h4>维度得分</h4>
          <el-row :gutter="16">
            <el-col :span="6" v-for="(score, dim) in unitSummariesQCReport.dimension_scores" :key="dim">
              <el-card shadow="hover" class="dimension-card">
                <template #header>
                  <div class="card-header">
                    <span>{{ getDimensionName(dim) }}</span>
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
        <div v-if="unitSummariesQCReport.issues?.length > 0" class="issues-list" style="margin: 16px 0;">
          <h4>检测到的问题</h4>
          <el-collapse accordion>
            <el-collapse-item 
              v-for="issue in unitSummariesQCReport.issues" 
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
                  <span v-if="issue.unit_number" class="issue-unit" style="margin-left: 8px; color: #409eff;">
                    第{{ issue.unit_number }}章
                  </span>
                  <span class="issue-id" style="margin-left: 8px; color: #999;">{{ issue.id }}</span>
                </div>
              </template>
              <div class="issue-content">
                <p><strong>描述:</strong> {{ issue.description }}</p>
                <p v-if="issue.evidence"><strong>证据:</strong> {{ issue.evidence }}</p>
                <p v-if="issue.suggestion"><strong>建议:</strong> {{ issue.suggestion }}</p>
                
                <!-- 手动执行LLM修正按钮 -->
                <div class="issue-actions" style="margin-top: 12px;">
                  <el-button 
                    type="primary" 
                    size="small" 
                    @click="handleUnitSummariesIssueRevise(issue)"
                    :loading="revisingUnitIssueId === issue.id"
                  >
                    <el-icon><MagicStick /></el-icon>
                    调用LLM修正
                  </el-button>
                </div>
                
                <!-- 用户反馈按钮 -->
                <div v-if="!issue.user_feedback" class="feedback-section" style="margin-top: 16px;">
                  <el-divider content-position="left">这个检测结果准确吗?</el-divider>
                  <el-button-group>
                    <el-button size="small" type="success" @click="handleUnitSummariesFeedback(issue, 'accepted')">
                      <el-icon><Select /></el-icon>
                      准确
                    </el-button>
                    <el-button size="small" @click="handleUnitSummariesFeedback(issue, 'ignored')">
                      <el-icon><RemoveFilled /></el-icon>
                      忽略
                    </el-button>
                    <el-button size="small" type="danger" @click="handleUnitSummariesFeedback(issue, 'false_positive')">
                      <el-icon><CircleClose /></el-icon>
                      误报
                    </el-button>
                  </el-button-group>
                </div>
                <div v-else class="feedback-recorded" style="margin-top: 12px;">
                  <el-tag type="success" size="small">
                    您的反馈已记录: {{ issue.user_feedback === 'accepted' ? '准确' : issue.user_feedback === 'ignored' ? '忽略' : '误报' }}
                  </el-tag>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
        
        <!-- 清理重复单元按钮（手动模式，始终显示） -->
        <div style="margin: 16px 0;">
          <el-button
            type="warning"
            size="small"
            @click="handleDetectAndCleanDuplicates"
            :loading="removingUnitSummariesDuplicates"
          >
            <el-icon><Delete /></el-icon>
            清理重复单元
          </el-button>
        </div>
        
        <!-- 重复章节检测结果（检测后显示） -->
        <div v-if="unitSummariesDuplicates && unitSummariesDuplicates.length > 0" class="duplicate-detection" style="margin: 16px 0;">
          <el-divider>重复单元检测结果</el-divider>
          <el-alert
            :title="`发现 ${unitSummariesDuplicates.length} 组重复单元`"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 12px;"
          >
            <template #default>
              <div class="duplicate-info">
                检测到重复的章节单元，点击下方按钮清理重复章节，保留第一个出现的章节。
              </div>
            </template>
          </el-alert>
          
          <el-table :data="unitSummariesDuplicates" border size="small" style="margin-bottom: 12px;">
            <el-table-column prop="groupIndex" label="组别" width="60" align="center" />
            <el-table-column label="重复单元" min-width="200">
              <template #default="{ row }">
                <div v-for="(dup, idx) in row.duplicates" :key="idx" class="duplicate-item">
                  <el-tag :type="idx === 0 ? 'success' : 'danger'" size="small" style="margin-right: 8px;">
                    {{ idx === 0 ? '保留' : '删除' }}
                  </el-tag>
                  <strong>{{ dup.title }}</strong>
                  <span class="duplicate-unit-num">（第{{ dup.unitNumber }}章）</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="内容长度" width="120" align="center">
              <template #default="{ row }">
                {{ row.duplicates[0]?.contentLength || 0 }} 字
              </template>
            </el-table-column>
          </el-table>
          
          <el-button
            type="danger"
            size="small"
            @click="handleRemoveUnitSummariesDuplicates"
            :loading="removingUnitSummariesDuplicates"
          >
            <el-icon><Delete /></el-icon>
            确认清理重复单元
          </el-button>
        </div>
        
        <!-- 无问题提示 -->
        <el-alert
          v-if="!unitSummariesQCReport?.issues?.length && !(unitSummariesDuplicates?.length > 0)"
          title="太棒了！未检测到质量问题"
          type="success"
          :closable="false"
          style="margin-top: 16px;"
        >
          <template #default>
            <p>单元概述质量优秀，可以继续后续操作。</p>
          </template>
        </el-alert>
    </div>
    
    <!-- 质量管控报告 (阶段4显示) -->
    <div v-if="useTwoStageMode && outlineStage === 4 && qualityReport" class="quality-control-report">
      <el-divider content-position="left">
        <el-icon><DataAnalysis /></el-icon>
        质量管控报告 v2.1
        <el-button 
          type="primary" 
          size="small" 
          @click="handleReAnalyze"
          :loading="reAnalyzing"
          style="margin-left: 16px;"
        >
          <el-icon><Refresh /></el-icon>
          重新检测
        </el-button>
      </el-divider>
      
      <!-- v2.1新增: 得分变化显示 -->
      <div v-if="scoreChanges" class="score-changes-display" style="margin-bottom: 16px;">
        <el-alert
          title="得分已更新"
          type="success"
          :closable="true"
          @close="scoreChanges = null"
        >
          <template #default>
            <div style="display: flex; align-items: center; gap: 16px;">
              <span><strong>总体得分</strong>:</span>
              <span>{{ scoreChanges.overall.previous.toFixed(1) }} → {{ scoreChanges.overall.current.toFixed(1) }}</span>
              <el-tag 
                :type="scoreChanges.overall.delta >= 0 ? 'success' : 'danger'"
                size="small"
              >
                {{ scoreChanges.overall.delta >= 0 ? '+' : '' }}{{ scoreChanges.overall.delta.toFixed(1) }}
              </el-tag>
              <el-button type="primary" size="small" @click="showScoreChangesDialog" style="margin-left: auto;">
                查看详情
              </el-button>
            </div>
          </template>
        </el-alert>
      </div>
      
      <el-descriptions :column="2" border class="qc-summary">
        <el-descriptions-item label="综合得分">
          <el-tag :type="getScoreType(qualityReport.overall_score)" size="large">
            {{ qualityReport.overall_score?.toFixed(1) || 0 }}分
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="问题总数">
          <el-tag :type="qualityReport.issues?.length > 0 ? 'warning' : 'success'">
            {{ qualityReport.issues?.length || 0 }}个
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      
      <!-- 三维度得分 -->
      <div v-if="qualityReport.dimension_scores" class="dimension-scores">
        <h4>基础维度得分</h4>
        <el-row :gutter="16">
          <el-col :span="8" v-for="(score, dim) in qualityReport.dimension_scores" :key="dim">
            <el-card shadow="hover" class="dimension-card">
              <template #header>
                <span>{{ getDimensionLabel(dim) }}</span>
              </template>
              <el-progress 
                :percentage="score" 
                :color="getScoreColor(score)"
                :format="() => `${score.toFixed(1)}分`"
              />
            </el-card>
          </el-col>
        </el-row>
      </div>
      
      <!-- v2.0新增: 交叉验证维度得分 -->
      <div v-if="qualityReport.cross_validation" class="cross-validation-scores">
        <h4>
          <el-icon><Connection /></el-icon>
          交叉验证维度得分
          <el-tag size="small" type="success" style="margin-left: 8px;">v2.0</el-tag>
        </h4>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="时间线一致性">
            <el-progress 
              :percentage="qualityReport.cross_validation.validation_scores?.timeline_consistency || 0" 
              :color="getScoreColor(qualityReport.cross_validation.validation_scores?.timeline_consistency || 0)"
              :format="() => `${(qualityReport.cross_validation.validation_scores?.timeline_consistency || 0).toFixed(1)}分`"
            />
          </el-descriptions-item>
          <el-descriptions-item label="因果关系一致性">
            <el-progress 
              :percentage="qualityReport.cross_validation.validation_scores?.causality_consistency || 0" 
              :color="getScoreColor(qualityReport.cross_validation.validation_scores?.causality_consistency || 0)"
              :format="() => `${(qualityReport.cross_validation.validation_scores?.causality_consistency || 0).toFixed(1)}分`"
            />
          </el-descriptions-item>
          <el-descriptions-item label="人物-世界观一致性">
            <el-progress 
              :percentage="qualityReport.cross_validation.validation_scores?.character_worldview_consistency || 0" 
              :color="getScoreColor(qualityReport.cross_validation.validation_scores?.character_worldview_consistency || 0)"
              :format="() => `${(qualityReport.cross_validation.validation_scores?.character_worldview_consistency || 0).toFixed(1)}分`"
            />
          </el-descriptions-item>
          <el-descriptions-item label="情节-大纲一致性">
            <el-progress 
              :percentage="qualityReport.cross_validation.validation_scores?.plot_outline_consistency || 0" 
              :color="getScoreColor(qualityReport.cross_validation.validation_scores?.plot_outline_consistency || 0)"
              :format="() => `${(qualityReport.cross_validation.validation_scores?.plot_outline_consistency || 0).toFixed(1)}分`"
            />
          </el-descriptions-item>
        </el-descriptions>
        <el-alert 
          v-if="qualityReport.cross_validation.metadata"
          type="info" 
          :closable="false" 
          show-icon
          style="margin-top: 12px;"
        >
          <template #default>
            验证数据: 
            <span v-if="qualityReport.cross_validation.metadata.has_global_outline">✅ 全局大纲 </span>
            <span v-if="qualityReport.cross_validation.metadata.has_character_profiles">✅ 人物设定 </span>
            <span v-if="qualityReport.cross_validation.metadata.has_worldview_settings">✅ 世界观设定</span>
          </template>
        </el-alert>
      </div>
      
      <!-- 问题列表入口按钮 -->
      <div v-if="qualityReport.issues && qualityReport.issues.length > 0" class="issues-entry">
        <el-button 
          type="primary" 
          size="large"
          @click="showIssuesDialog = true"
        >
          <el-icon><WarningFilled /></el-icon>
          查看问题详情（{{ qualityReport.issues.length }}个问题）
        </el-button>
      </div>
      
      <!-- 无问题提示 -->
      <el-alert
        v-else
        title="质量检查通过"
        type="success"
        :closable="false"
        show-icon
        class="qc-passed"
      >
        恭喜!单元概述质量检查通过,未发现明显问题。
      </el-alert>
    </div>
    
    <!-- 问题详情弹窗 -->
    <el-dialog
      v-model="showIssuesDialog"
      title="质控问题详情"
      width="900px"
      top="5vh"
      :close-on-click-modal="true"
      destroy-on-close
      class="issues-dialog"
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
                    @click="handleApplyFix(issue)"
                    :loading="applyingFix === (qualityReport?.issues || []).indexOf(issue)"
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
                  @click="handleApplyFix(issue)"
                  :loading="applyingFix === (qualityReport?.issues || []).indexOf(issue)"
                >
                  <el-icon><Edit /></el-icon>
                  生成并应用修正
                </el-button>
              </div>
              
              <div v-if="!issue.user_feedback" class="feedback-section">
                <el-divider content-position="left">这个检测结果准确吗?</el-divider>
                <el-button-group>
                  <el-button size="small" type="success" @click="handleFeedback(issue, 'accepted')">
                    <el-icon><Select /></el-icon>
                    准确
                  </el-button>
                  <el-button size="small" @click="handleFeedback(issue, 'ignored')">
                    <el-icon><RemoveFilled /></el-icon>
                    忽略
                  </el-button>
                  <el-button size="small" type="danger" @click="handleFeedback(issue, 'false_positive')">
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
    
    <!-- 修订模式对话框 (多轮对话修订) -->
    <el-dialog
      v-model="props.isRevisionMode"
      :title="useTwoStageMode ? '修订全局大纲' : '修订内容'"
      width="1200px"
      top="5vh"
      :close-on-click-modal="false"
      destroy-on-close
      class="revision-dialog"
    >
      <div class="revision-container">
        <!-- 左侧: 对话区域 -->
        <div class="revision-chat">
          <div class="chat-header">
            <h4>
              <el-icon><ChatDotRound /></el-icon>
              与AI对话修订
              <el-tag v-if="props.currentRevisionRound > 0" type="success" size="small" style="margin-left: 8px;">
                第 {{ props.currentRevisionRound }} 轮修订
              </el-tag>
            </h4>
          </div>
          
          <div class="chat-messages">
            <div v-if="props.revisionMessages.length === 0" class="empty-message">
              <el-empty description="请输入您的修改意见" />
            </div>
            <div v-for="(msg, idx) in props.revisionMessages" :key="idx" class="message-item">
              <div v-if="msg.role === 'user'" class="message user-message">
                <div class="message-avatar">👤</div>
                <div class="message-content">{{ msg.content }}</div>
              </div>
              <div v-else class="message ai-message">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                  <div v-if="msg.loading" class="loading-indicator">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span>AI正在生成修订内容...</span>
                  </div>
                  <div v-else v-html="msg.content"></div>
                </div>
              </div>
            </div>
          </div>
          
          <div class="chat-input">
            <!-- 已上传文件列表 -->
            <div v-if="uploadedFiles.length > 0" class="uploaded-files-list">
              <div v-for="(file, idx) in uploadedFiles" :key="idx" class="file-tag">
                <el-icon><Document /></el-icon>
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">({{ (file.size / 1024).toFixed(1) }}KB)</span>
                <el-icon class="remove-file" @click="removeUploadedFile(idx)"><Close /></el-icon>
              </div>
            </div>
            
            <el-input
              v-model="localRevisionInput"
              type="textarea"
              :rows="3"
              placeholder="请输入修改意见，例如：&#10;- 把主角的职业改为医生&#10;- 增加一个反派角色&#10;- 调整故事背景到现代都市&#10;&#10;💡 提示：可上传TXT/MD参考文件作为修订上下文"
              :disabled="props.revising"
              @keyup.ctrl.enter="handleSubmitRevision"
            />
            
            <div class="input-actions">
              <div class="left-actions">
                <!-- 文件上传按钮 -->
                <el-button text size="small" @click="fileInputRef?.click()">
                  <el-icon><Paperclip /></el-icon>
                  上传参考文件
                </el-button>
                <input
                  ref="fileInputRef"
                  type="file"
                  multiple
                  accept=".txt,.md,.doc,.docx"
                  style="display: none"
                  @change="handleFileSelect"
                />
                <el-text v-if="uploadedFiles.length > 0" type="success" size="small">
                  已上传 {{ uploadedFiles.length }} 个文件
                </el-text>
              </div>
              <div class="right-actions">
                <el-button @click="handleExitRevision">
                  <el-icon><Close /></el-icon>
                  退出修订
                </el-button>
                <el-button 
                  type="primary" 
                  @click="handleSubmitRevision"
                  :loading="props.revising"
                  :disabled="!localRevisionInput.trim() && uploadedFiles.length === 0"
                >
                  <el-icon><Promotion /></el-icon>
                  提交修订意见
                </el-button>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 右侧: 内容预览区域 -->
        <div class="revision-preview">
          <div class="preview-header">
            <h4>
              <el-icon><Document /></el-icon>
              当前内容预览
            </h4>
          </div>
          <div class="preview-content">
            <div v-if="props.revisionContent" class="markdown-content" v-html="renderedRevisionContent"></div>
            <el-empty v-else description="暂无内容" />
          </div>
        </div>
      </div>
      
      <template #footer>
        <div class="revision-footer">
          <el-button @click="handleExitRevision">
            <el-icon><Close /></el-icon>
            退出修订
          </el-button>
          <el-button type="success" @click="handleFinalizeContent">
            <el-icon><Check /></el-icon>
            确认使用当前内容
          </el-button>
        </div>
      </template>
    </el-dialog>
    
    <!-- 默认渲染内容（阶段2时不显示，因为已有编辑区） -->
    <div v-if="!(useTwoStageMode && outlineStage === 2)" class="result-content markdown-content" v-html="renderedContent"></div>
    
    <!-- v2.3新增：质控历史记录弹窗 -->
    <el-dialog
      v-model="showQCHistoryDialog"
      title="质量控制详情"
      width="900px"
      top="5vh"
      :close-on-click-modal="true"
      destroy-on-close
      class="qc-history-dialog"
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
                    <span>{{ getDimensionName(dim) }}</span>
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
        <el-button @click="showQCHistoryDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { 
  DataAnalysis, 
  Connection, 
  Check, 
  Select, 
  RemoveFilled, 
  CircleClose,
  Refresh,
  Edit,
  WarningFilled,
  ChatDotRound,
  Document,
  Loading,
  Promotion,
  Close,
  Upload,
  Paperclip,
  Download,
  RefreshRight,
  Delete,
  MagicStick
} from '@element-plus/icons-vue'
import { qualityControlApi } from '@/api'

const props = defineProps({
  showResult: Boolean,
  useTwoStageMode: Boolean,
  outlineStage: { type: Number, default: 0 },
  globalOutlineGenerating: Boolean,
  unitSummariesGenerating: Boolean,
  logicChecking: Boolean,
  logicCheckResult: Object,
  generationDuration: Number,
  editingGlobalOutline: Boolean,
  editingGlobalOutlineContent: String,
  editingUnitNumber: [Number, String],
  editingUnitContent: String,
  unitSummaries: { type: Object, default: () => ({}) },
  globalOutlineContent: String,
  generatedContent: String,
  contentType: String,
  expectedUnitCount: { type: Number, default: 0 },  // 预期总章节数（新增，用于续生成判断）
  qualityReport: { type: Object, default: null },
  projectId: { type: [Number, String], default: null },  // v2.1新增: 项目ID，支持Number和String
  
  // 修订模式相关 (多轮对话修订)
  isRevisionMode: Boolean,  // 是否在修订模式
  currentRevisionRound: Number,  // 当前修订轮次
  revisionContent: String,  // 修订后的内容
  revisionMessages: { type: Array, default: () => [] },  // 对话消息历史
  revisionHistory: { type: Array, default: () => [] },  // 修订历史
  revising: Boolean,  // 正在修订中
  revisionInput: String,  // 用户输入的修订意见
  
  // 全局大纲质控相关 (v1.0新增)
  globalOutlineQCReport: { type: Object, default: null },  // 全局大纲质控报告
  globalOutlineQCLoading: Boolean,  // 质控检测加载状态
  qcProgress: { type: Object, default: null },  // v1.1新增: SSE实时进度
  revisingIssueId: { type: String, default: null },  // 正在修正的问题ID
  
  // v2.3新增：自动质控状态
  qcApplied: { type: Boolean, default: false },      // 是否已应用质控修正
  issuesFixed: { type: Number, default: 0 },          // 修正的问题数量
  qcReportData: { type: Object, default: null },     // 质控报告数据（用于历史记录）
  importedOutline: { type: Boolean, default: false }, // 是否为导入的大纲
  autoQCLoading: { type: Boolean, default: false },   // 自动质控加载状态
  
  // 单元概述质控相关（手动触发）
  unitSummariesQCLoading: { type: Boolean, default: false },  // 单元概述质控加载状态
  unitSummariesQCReport: { type: Object, default: null },  // v2.4新增：单元概述质控报告（手动模式完整展示）
  unitSummariesQCMode: { type: String, default: 'manual' },  // v2.4新增：质控模式（manual/auto）
  
  // 后端断点信息（可选，用于页面刷新后恢复续生成状态）
  backendResumeInfo: { type: Object, default: null }  // { can_resume, remaining_count, start_from_unit, existing_count, expected_count }
})

// 调试：监控globalOutlineQCReport prop的变化
watch(() => props.globalOutlineQCReport, (newVal) => {
  console.log('========== [ResultViewer] globalOutlineQCReport prop变化 ==========')
  console.log('newVal:', newVal)
  console.log('newVal !== null:', newVal !== null)
  console.log('typeof newVal:', typeof newVal)
  console.log('===============================================================')
}, { deep: true, immediate: true })

const emit = defineEmits([
  'stop',
  'generate-unit-summaries',
  'cancel-unit-summaries',
  'download-outline',
  'open-start-unit-dialog',
  'reset-two-stage',
  'copy',
  'download',
  'regenerate',
  'start-edit-global',
  'save-global-edit',
  'cancel-global-edit',
  'update:editingGlobalOutlineContent',
  'open-revision-detail',
  'edit-unit',
  'save-unit',
  'cancel-edit-unit',
  'update:editingUnitContent',
  'update-unit-content',  // v2.0新增: 更新单元内容
  'update-quality-report',  // v2.1新增: 更新质量报告
  
  // 修订模式相关事件 (多轮对话修订)
  'start-revision',  // 启动修订模式
  'submit-revision',  // 提交修订意见
  'finalize-content',  // 确认使用当前内容
  'exit-revision',  // 退出修订模式
  
  // 全局大纲质控相关事件 (v1.0新增)
  'analyze-global-outline-qc',  // 触发全局大纲质量检测
  'revise-global-outline',  // 触发全局大纲修正
  
  // 单元概述质控相关事件（手动触发）
  'quality-control-unit-summaries',  // 触发单元概述质量检测
  'revise-unit-summaries-issue',  // v2.4新增：触发单元概述问题修正
  'unit-summaries-feedback',  // v2.4新增：单元概述质控用户反馈
  'apply-unit-summaries-revision',  // v2.4新增：应用单元概述修正
  'remove-unit-summaries-duplicates',  // v2.4新增：清理单元概述质控报告中的重复章节（手动模式）
  'resume-unit-summaries',  // 续生成剩余章节
  'resume-unit-summaries-from-backend'  // 从后端断点信息续生成
])

// 续生成相关计算属性
const existingUnitCount = computed(() => {
  return props.unitSummaries ? Object.keys(props.unitSummaries).length : 0
})

const canResumeUnitSummaries = computed(() => {
  const existing = existingUnitCount.value
  const expected = props.expectedUnitCount
  return existing > 0 && expected > 0 && existing < expected
})

// 从后端获取的断点信息（用于页面刷新后恢复）
const showResumeFromBackend = computed(() => {
  return props.backendResumeInfo?.can_resume === true
})

const remainingUnitCount = computed(() => {
  // 优先使用后端断点信息
  if (props.backendResumeInfo?.remaining_count !== undefined) {
    return props.backendResumeInfo.remaining_count
  }
  const existing = existingUnitCount.value
  const expected = props.expectedUnitCount
  return Math.max(0, expected - existing)
})

const formatDuration = (ms) => {
  if (!ms || ms < 0) return ''
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes > 0) {
    return `${minutes}分${remainingSeconds}秒`
  } else {
    return `${remainingSeconds}秒`
  }
}

// 质量报告辅助函数
const getScoreType = (score) => {
  if (!score) return 'info'
  if (score >= 90) return 'success'
  if (score >= 70) return 'primary'
  if (score >= 60) return 'warning'
  return 'danger'
}

const getScoreColor = (score) => {
  if (score >= 90) return '#67c23a'
  if (score >= 70) return '#409eff'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

// v1.1新增: SSE进度辅助函数
const getProgressColor = (progress) => {
  if (progress >= 80) return '#67c23a'
  if (progress >= 50) return '#409eff'
  if (progress >= 20) return '#e6a23c'
  return '#909399'
}

const getProgressStatusType = (status) => {
  switch (status) {
    case 'running': return 'primary'
    case 'success': return 'success'
    case 'failed': return 'danger'
    case 'completed': return 'success'
    case 'error': return 'danger'
    case 'reconnecting': return 'warning'
    default: return 'info'
  }
}

// v1.1新增: 质控按钮文字计算属性
const getQCButtonText = computed(() => {
  if (props.globalOutlineQCLoading) {
    return '检测中...'
  }
  if (props.globalOutlineQCReport) {
    const score = props.globalOutlineQCReport.overall_score || 0
    const issues = props.globalOutlineQCReport.issues?.length || 0
    if (score >= 90) {
      return '质量优秀，重新检测'
    } else if (score >= 70) {
      return '质量良好，重新检测'
    } else if (issues > 0) {
      return `重新检测 (${issues}个问题)`
    }
    return '重新检测'
  }
  return '质量检测'
})

// v1.1新增: 重连状态显示
const isReconnecting = computed(() => {
  return props.qcProgress?.status === 'reconnecting'
})

const reconnectMessage = computed(() => {
  return props.qcProgress?.message || '连接中断，正在重连...'
})

const getDimensionLabel = (dim) => {
  const labels = {
    unit_structure: '单元结构',
    unit_character: '人物发展',
    unit_consistency: '大纲一致性',
    unit_timeline_space: '时间线空间',
    unit_ooc: '人物OOC',
    // 全局大纲四维度 (v1.1新增)
    global_structure: '宏观结构',
    global_character_worldview: '人物与世界观',
    global_plot_consistency: '剧情线一致性',
    global_storyline_integrity: '故事线完整性'
  }
  return labels[dim] || dim
}

// 别名函数,兼容全局大纲质控模板
const getDimensionName = getDimensionLabel

const getSeverityType = (severity) => {
  const types = {
    critical: 'danger',
    warning: 'warning',
    info: 'info'
  }
  return types[severity] || 'info'
}

const getSeverityLabel = (severity) => {
  const labels = {
    critical: '严重',
    warning: '警告',
    info: '提示'
  }
  return labels[severity] || severity
}

const renderedGlobalOutline = computed(() => {
  if (!props.globalOutlineContent) return ''
  return DOMPurify.sanitize(marked(props.globalOutlineContent))
})

const renderedContent = computed(() => {
  if (!props.generatedContent) return ''
  return DOMPurify.sanitize(marked(props.generatedContent))
})

// 修订模式相关
const localRevisionInput = ref('')
const uploadedFiles = ref([])  // 已上传的文件列表
const fileInputRef = ref(null)  // 文件输入引用

const renderedRevisionContent = computed(() => {
  if (!props.revisionContent) return ''
  return DOMPurify.sanitize(marked(props.revisionContent))
})

// 读取文件内容
const readFileContent = async (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    
    // 根据文件类型选择读取方式
    if (file.name.endsWith('.txt') || file.name.endsWith('.md')) {
      reader.onload = (e) => {
        resolve({
          name: file.name,
          content: e.target.result,
          size: file.size
        })
      }
      reader.onerror = reject
      reader.readAsText(file, 'UTF-8')
    } else if (file.name.endsWith('.docx') || file.name.endsWith('.doc')) {
      // 对于docx文件,读取为文本提示用户转换
      resolve({
        name: file.name,
        content: `[DOCX文件: ${file.name}, 大小: ${(file.size / 1024).toFixed(1)}KB]\n提示: 请将DOCX文件转换为TXT或MD格式后上传以获得最佳效果`,
        size: file.size,
        isBinary: true
      })
    } else {
      resolve({
        name: file.name,
        content: `[文件: ${file.name}, 大小: ${(file.size / 1024).toFixed(1)}KB]`,
        size: file.size
      })
    }
  })
}

// 处理文件选择
const handleFileSelect = async (event) => {
  const files = event.target.files
  if (!files || files.length === 0) return
  
  for (const file of files) {
    // 验证文件类型
    const allowedExtensions = ['.txt', '.md', '.doc', '.docx']
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    
    if (!allowedExtensions.includes(ext)) {
      ElMessage.warning(`不支持的文件格式: ${ext}, 仅支持 ${allowedExtensions.join(', ')}`)
      continue
    }
    
    // 验证文件大小(10MB限制)
    if (file.size > 10 * 1024 * 1024) {
      ElMessage.warning(`文件过大: ${file.name}, 限制10MB`)
      continue
    }
    
    try {
      const fileData = await readFileContent(file)
      uploadedFiles.value.push(fileData)
      ElMessage.success(`文件已上传: ${file.name}`)
    } catch (error) {
      console.error('读取文件失败:', error)
      ElMessage.error(`读取文件失败: ${file.name}`)
    }
  }
  
  // 清空input,允许重复选择同一文件
  event.target.value = ''
}

// 移除已上传文件
const removeUploadedFile = (index) => {
  uploadedFiles.value.splice(index, 1)
}

// 提交修订意见
const handleSubmitRevision = () => {
  if ((!localRevisionInput.value.trim() && uploadedFiles.value.length === 0) || props.revising) {
    ElMessage.warning('请输入修订意见或上传参考文件')
    return
  }
  
  // 构建完整的修订意见(包含文件内容)
  let fullInput = localRevisionInput.value.trim()
  
  if (uploadedFiles.value.length > 0) {
    fullInput += '\n\n--- 参考文件内容 ---\n'
    uploadedFiles.value.forEach((file, idx) => {
      fullInput += `\n【文件${idx + 1}: ${file.name}】\n`
      fullInput += file.content + '\n'
    })
  }
  
  emit('submit-revision', fullInput)
  localRevisionInput.value = ''
  uploadedFiles.value = []  // 清空已上传文件
}

// 退出修订模式
const handleExitRevision = () => {
  emit('exit-revision')
}

// 确认使用当前内容
const handleFinalizeContent = () => {
  emit('finalize-content')
}

// v2.0新增: 应用修正状态
const applyingFix = ref(null)

// v2.1新增: 重新分析状态
const reAnalyzing = ref(false)
const previousScore = ref(null)
const scoreChanges = ref(null)

// v2.2新增: 问题详情弹窗状态
const showIssuesDialog = ref(false)
const activeIssues = ref([])

// 全局大纲问题详情弹窗状态
const showGlobalOutlineIssuesDialog = ref(false)
const activeGlobalOutlineIssues = ref([])

// v2.3新增：质控历史记录弹窗状态
const showQCHistoryDialog = ref(false)

// v2.4新增：单元概述质控相关响应式变量
const revisingUnitIssueId = ref(null)  // 正在修正的单元问题ID
const showUnitSummariesReviseDialog = ref(false)  // 单元概述修正对比对话框
const unitSummariesReviseData = ref(null)  // 单元概述修正数据
const unitSummariesDuplicates = ref([])  // v2.4新增：单元概述重复章节
const removingUnitSummariesDuplicates = ref(false)  // v2.4新增：清理重复章节加载状态

// 质量报告响应式引用
const qualityReport = computed(() => props.qualityReport)

// 获取项目ID - 优先使用qualityReport中的project_id
const getProjectId = () => {
  // 1. 优先使用qualityReport中的project_id
  if (qualityReport.value?.project_id && qualityReport.value.project_id > 0) {
    return qualityReport.value.project_id
  }
  // 2. 其次使用props.projectId
  if (props.projectId && props.projectId > 0) {
    return props.projectId
  }
  // 3. 返回0（表示大纲阶段）
  return 0
}

// 获取指定单元的内容（支持多单元范围，如第6-8单元）
const getUnitContent = (chapterNumber) => {
  if (!chapterNumber) return ''
  
  // 解析issue的影响范围（可能跨多单元）
  const startUnit = parseInt(chapterNumber)
  if (isNaN(startUnit)) return ''
  
  // 收集相关单元的内容
  const contents = []
  
  // 1. 优先从unitSummaries中获取
  if (props.unitSummaries && Object.keys(props.unitSummaries).length > 0) {
    // 获取主单元及其前后单元的完整内容（提供上下文）
    const unitKeys = Object.keys(props.unitSummaries).map(Number).sort((a, b) => a - b)
    const startIdx = Math.max(startUnit - 1, unitKeys[0])  // 包含前一单元作为上下文
    const endIdx = Math.min(startUnit + 2, unitKeys[unitKeys.length - 1])  // 包含后两单元
    
    for (let i = startIdx; i <= endIdx; i++) {
      const unit = props.unitSummaries[String(i)]
      if (unit) {
        // v2.1: 优先使用full_content（包含完整的章节格式和内容）
        const unitText = unit.full_content || unit.summary || unit.content || ''
        if (unitText) {
          contents.push(`第${i}单元《${unit.title || ''}》:\n${unitText}`)
        }
      }
    }
    
    if (contents.length > 0) {
      return contents.join('\n\n')
    }
  }
  
  // 2. 从generatedContent中提取对应单元（包含完整格式）
  if (props.generatedContent) {
    const startIdx = Math.max(startUnit - 1, 1)
    const endIdx = startUnit + 2
    
    for (let i = startIdx; i <= endIdx; i++) {
      const patterns = [
        new RegExp(`###\\s*第${i}章[\\s\\S]*?(?=###\\s*第\\d+章|$)`),
        new RegExp(`\\*\\*第${i}集[\\s\\S]*?(?=\\*\\*第\\d+集|$)`),
        new RegExp(`\\*\\*第${i}场[\\s\\S]*?(?=\\*\\*第\\d+场|$)`),
      ]
      for (const pattern of patterns) {
        const match = props.generatedContent.match(pattern)
        if (match) {
          contents.push(match[0].trim())
          break
        }
      }
    }
    
    if (contents.length > 0) {
      return contents.join('\n\n')
    }
  }
  
  return ''
}

// v2.0新增: 处理应用修正
const handleApplyFix = async (issue) => {
  console.log('=== 应用修正调试信息 ===')
  console.log('issue对象:', issue)
  console.log('issue.auto_fix:', issue.auto_fix)
  console.log('qualityReport.value:', qualityReport.value)
  console.log('issue.id:', issue.id)
  console.log('issue.location:', issue.location)
  
  // 如果没有预生成的修正方案,调用LLM生成
  if (!issue.auto_fix || !issue.auto_fix.fixed) {
    console.log('没有auto_fix,调用LLM生成')
    
    const projectId = getProjectId()
    console.log('使用projectId:', projectId)
    
    console.log('调用参数:', {
      issue_id: issue.id,
      chapter_number: issue.location?.chapter_number,
      category: issue.category,
      description: issue.description,
      project_id: projectId
    })
    await generateFixWithLLM(issue)
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要应用此修正吗?\n\n${issue.auto_fix.description}`,
      '确认应用修正',
      {
        confirmButtonText: '应用',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
      
    applyingFix.value = (qualityReport.value?.issues || []).indexOf(issue)
      
    const projectId = getProjectId()
      
    // v2.1: 大纲阶段（project_id=0）直接在前端更新，不调用后端API
    if (projectId === 0) {
      console.log('大纲阶段，直接在前端更新单元内容')
        
      // 触发更新事件，让父组件直接替换unitSummaries中的内容
      emit('update-unit-content', {
        chapter_number: issue.location?.chapter_number,
        unit_id: issue.location?.unit_id,
        content: issue.auto_fix.fixed
      })
        
      ElMessage.success('修正已应用')
      ElMessage.info('修正已应用，您可以点击“重新检测”查看得分变化')
    } else {
      // 数据库阶段：调用后端API应用修正
      console.log('数据库阶段，调用后端API')
        
      const response = await qualityControlApi.applyFix({
        issue_id: issue.id,
        auto_fix: issue.auto_fix,
        chapter_number: issue.location?.chapter_number,
        project_id: projectId
      })
        
      if (response?.success) {
        ElMessage.success('修正已应用')
        // 触发更新事件
        emit('update-unit-content', {
          chapter_number: issue.location?.chapter_number,
          unit_id: issue.location?.unit_id,
          content: issue.auto_fix.fixed
        })
        ElMessage.info('修正已应用，您可以点击“重新检测”查看得分变化')
      } else {
        ElMessage.error(response?.message || '应用修正失败')
      }
    }
  } catch (error) {
    if (error !== 'cancel') {
      // 检测超时错误
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        ElMessage.error('应用修正超时（5分钟），请稍后重试。')
      } else {
        ElMessage.error('应用修正失败: ' + (error.message || ''))
      }
    }
  } finally {
    applyingFix.value = null
  }
}

// v2.0新增: 处理用户反馈
const handleFeedback = async (issue, feedbackType) => {
  console.log('=== 提交反馈调试信息 ===')
  console.log('issue对象:', issue)
  console.log('issue.id:', issue.id)
  console.log('issue.dimension:', issue.dimension)
  console.log('issue.category:', issue.category)
  console.log('feedbackType:', feedbackType)
  
  // 验证必要字段
  if (!issue.id) {
    console.error('issue.id 为空!', issue)
    ElMessage.error('问题ID为空，无法提交反馈')
    return
  }
  
  if (!issue.dimension) {
    console.error('issue.dimension 为空!', issue)
    ElMessage.error('问题维度为空，无法提交反馈')
    return
  }
  
  if (!issue.category) {
    console.error('issue.category 为空!', issue)
    ElMessage.error('问题分类为空，无法提交反馈')
    return
  }
  
  try {
    const requestData = {
      issue_id: issue.id,
      dimension: issue.dimension,
      category: issue.category,
      feedback_type: feedbackType
    }
    
    console.log('调用submitFeedback API, 参数:', requestData)
    
    const response = await qualityControlApi.submitFeedback(requestData)
    
    console.log('submitFeedback API响应:', response)
    console.log('response.success:', response?.success)
    console.log('response.message:', response?.message)
    console.log('response.data:', response?.data)
    
    // axios拦截器返回response.data
    // response = {success: true, message: "...", data: {feedback_id, feedback_type, issue_id}}
    const isSuccess = response?.success === true
    
    if (isSuccess) {
      ElMessage.success(response?.message || '反馈已记录，系统将自动优化检测结果')
      // 标记已反馈 - 直接修改对象属性，Vue会自动追踪
      issue.user_feedback = feedbackType
      console.log('已设置 issue.user_feedback =', feedbackType)
    } else {
      console.error('提交反馈失败:', response)
      ElMessage.error(response?.message || '提交反馈失败')
    }
  } catch (error) {
    console.error('提交反馈错误:', error)
    console.error('错误堆栈:', error.stack)
    console.error('错误响应:', error.response)
    ElMessage.error('提交反馈失败: ' + (error.message || ''))
  }
}

// 全局大纲质控反馈处理
const handleGlobalOutlineFeedback = async (issue, feedbackType) => {
  try {
    console.log('[全局大纲反馈] 提交反馈:', {
      issue_id: issue.id,
      dimension: issue.dimension,
      category: issue.category,
      feedback_type: feedbackType
    })
    
    const requestData = {
      issue_id: issue.id,
      dimension: issue.dimension || 'global_structure',
      category: issue.category || '未知',
      feedback_type: feedbackType,
      comment: `全局大纲质控反馈: ${feedbackType}`
    }
    
    const response = await qualityControlApi.submitFeedback(requestData)
    
    if (response?.success) {
      ElMessage.success(response?.message || '反馈已记录')
      issue.user_feedback = feedbackType
    } else {
      ElMessage.error(response?.message || '提交反馈失败')
    }
  } catch (error) {
    console.error('[全局大纲反馈] 提交失败:', error)
    ElMessage.error('提交反馈失败: ' + (error.message || ''))
  }
}

// v2.4新增：单元概述质控相关方法
/**
 * 处理单元概述问题修正
 */
const handleUnitSummariesIssueRevise = async (issue) => {
  try {
    console.log('[单元概述修正] 开始修正问题:', issue.id)
    revisingUnitIssueId.value = issue.id
    
    // 发射事件到父组件处理修正逻辑
    emit('revise-unit-summaries-issue', {
      issue,
      qualityReport: props.unitSummariesQCReport,
      unitSummaries: props.unitSummaries
    })
  } catch (error) {
    console.error('[单元概述修正] 失败:', error)
    ElMessage.error('修正失败: ' + (error.message || ''))
  } finally {
    revisingUnitIssueId.value = null
  }
}

/**
 * 处理单元概述质控用户反馈
 */
const handleUnitSummariesFeedback = async (issue, feedbackType) => {
  try {
    console.log('[单元概述反馈] 提交反馈:', {
      issue_id: issue.id,
      dimension: issue.dimension,
      category: issue.category,
      feedback_type: feedbackType
    })
    
    const requestData = {
      issue_id: issue.id,
      dimension: issue.dimension || 'unit_structure',
      category: issue.category || '未知',
      feedback_type: feedbackType,
      comment: `单元概述质控反馈: ${feedbackType}`
    }
    
    const response = await qualityControlApi.submitFeedback(requestData)
    
    if (response?.success) {
      ElMessage.success(response?.message || '反馈已记录')
      issue.user_feedback = feedbackType
      
      // 发射事件到父组件
      emit('unit-summaries-feedback', {
        issue,
        feedbackType
      })
    } else {
      ElMessage.error(response?.message || '提交反馈失败')
    }
  } catch (error) {
    console.error('[单元概述反馈] 提交失败:', error)
    ElMessage.error('提交反馈失败: ' + (error.message || ''))
  }
}

/**
 * 应用单元概述修正
 */
const applyUnitSummariesRevision = (revisedData) => {
  try {
    console.log('[单元概述修正] 应用修正:', revisedData)
    
    // 发射事件到父组件处理修正应用
    emit('apply-unit-summaries-revision', revisedData)
    
    ElMessage.success('修正已应用')
    showUnitSummariesReviseDialog.value = false
  } catch (error) {
    console.error('[单元概述修正] 应用失败:', error)
    ElMessage.error('应用修正失败: ' + (error.message || ''))
  }
}

/**
 * 手动模式：检测并清理重复单元
 * 点击按钮后先检测，如果没有重复则提示，如果有重复则显示结果让用户确认清理
 */
const handleDetectAndCleanDuplicates = () => {
  // 使用当前生成的完整内容进行检测
  const content = props.generatedContent
  if (!content) {
    ElMessage.warning('没有可检测的内容')
    return
  }
  
  // 执行检测
  detectUnitSummariesDuplicates(content)
  
  // 检测结果显示在UI中，用户可以看到结果后再决定是否点击"确认清理"
  if (unitSummariesDuplicates.value.length === 0) {
    ElMessage.success('未检测到重复单元，内容质量良好')
  } else {
    ElMessage.warning(`检测到 ${unitSummariesDuplicates.value.length} 组重复单元，请查看详情并确认清理`)
  }
}

/**
 * 检测单元概述重复章节
 * 以章节为单位,比较标题和内容的完全匹配
 */
const detectUnitSummariesDuplicates = (content) => {
  if (!content) {
    unitSummariesDuplicates.value = []
    return
  }
  
  // 解析章节内容
  const chapterRegex = /###\s*第([\u4e00二三四五六七八九十百千万\d]+)[章集场][\uff1a:]\s*(.+?)\n([\s\S]*?)(?=###\s*第|$)/g
  const chapters = []
  let match
  
  while ((match = chapterRegex.exec(content)) !== null) {
    chapters.push({
      unitNumber: match[1],
      title: match[2].trim(),
      content: match[3].trim(),
      fullMatch: match[0]
    })
  }
  
  if (chapters.length === 0) {
    unitSummariesDuplicates.value = []
    return
  }
  
  // 查找重复章节
  const duplicateGroups = []
  const seen = new Map() // title+content -> first index
  
  chapters.forEach((chapter, index) => {
    const key = `${chapter.title}|||${chapter.content}`
    
    if (seen.has(key)) {
      // 找到重复章节
      const firstIndex = seen.get(key)
      let group = duplicateGroups.find(g => g.firstIndex === firstIndex)
      
      if (!group) {
        group = {
          groupIndex: duplicateGroups.length + 1,
          firstIndex: firstIndex,
          duplicates: [chapters[firstIndex]]
        }
        duplicateGroups.push(group)
      }
      
      group.duplicates.push({
        ...chapter,
        contentLength: chapter.content.length
      })
    } else {
      seen.set(key, index)
    }
  })
  
  unitSummariesDuplicates.value = duplicateGroups
}

/**
 * 处理单元概述重复章节清理
 */
const handleRemoveUnitSummariesDuplicates = () => {
  if (unitSummariesDuplicates.value.length === 0) {
    ElMessage.info('没有检测到重复章节')
    return
  }
  
  ElMessageBox.confirm(
    `即将清理 ${unitSummariesDuplicates.value.length} 组重复章节,保留第一个出现的章节,删除后续重复章节。是否继续?`,
    '确认清理重复章节',
    {
      confirmButtonText: '确认清理',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    removingUnitSummariesDuplicates.value = true
    
    // 发射事件到父组件处理清理逻辑
    emit('remove-unit-summaries-duplicates', {
      duplicates: unitSummariesDuplicates.value,
      unitSummaries: props.unitSummaries
    })
    
    // 清理完成后重置检测结果
    unitSummariesDuplicates.value = []
    removingUnitSummariesDuplicates.value = false
    ElMessage.success('重复单元已清理')
  }).catch(() => {
    // 用户取消
  })
}

// v2.1新增: 使用LLM生成修正方案
const generateFixWithLLM = async (issue) => {
  try {
    console.log('=== generateFixWithLLM 开始 ===')
    console.log('issue:', issue)
    
    const projectId = getProjectId()
    const chapterContent = getUnitContent(issue.location?.chapter_number)
    console.log('单元内容长度:', chapterContent.length, '字')
    
    const loadingMsg = ElMessage({
      message: '正在使用AI生成修正方案...',
      type: 'info',
      duration: 0
    })
    
    const requestData = {
      issue_id: issue.id,
      chapter_number: issue.location?.chapter_number || 0,
      category: issue.category || '',
      description: issue.description || '',
      project_id: projectId,
      chapter_content: chapterContent,
      global_outline: props.globalOutlineContent || ''
    }
    
    console.log('调用generateFix API, chapter_content长度:', requestData.chapter_content.length)
    
    // 调用LLM生成修正方案
    const response = await qualityControlApi.generateFix(requestData)
    
    loadingMsg.close()
    
    console.log('generateFix API响应:', response)
    
    // axios拦截器已解包response.data
    // response = {success, message, data: {fixed, description, confidence, ...}}
    if (response?.success && response?.data) {
      const fixData = response.data
      console.log('修正方案生成成功:', fixData)
      
      // 将生成的修正方案附加到issue
      issue.auto_fix = fixData
      
      // 检查是否为降级方案（置信度为0）
      const confidence = fixData.confidence || 0
      if (confidence === 0) {
        ElMessage.warning('LLM生成失败，返回了降级方案。请检查后端日志。')
        return
      }
      
      // 显示修正前后对比并确认
      const confirmMsg = `AI已生成修正方案:\n\n${fixData.description || '无描述'}\n\n置信度: ${(confidence * 100).toFixed(0)}%`
      
      await ElMessageBox.confirm(
        confirmMsg,
        '确认应用修正',
        {
          confirmButtonText: '应用',
          cancelButtonText: '取消',
          type: 'success'
        }
      )
      
      // 用户确认应用修正
      applyingFix.value = (qualityReport.value?.issues || []).indexOf(issue)
      
      // v2.1: 大纲阶段直接前端更新，不调后端API
      if (projectId === 0) {
        console.log('大纲阶段，直接前端更新单元内容')
        emit('update-unit-content', {
          chapter_number: issue.location?.chapter_number,
          unit_id: issue.location?.unit_id,
          content: issue.auto_fix.fixed
        })
        ElMessage.success('修正已应用')
        ElMessage.info('修正已应用，您可以点击“重新检测”查看得分变化')
      } else {
        const applyResponse = await qualityControlApi.applyFix({
          issue_id: issue.id,
          auto_fix: issue.auto_fix,
          chapter_number: issue.location?.chapter_number || 0,
          project_id: projectId
        })
        
        if (applyResponse?.success) {
          ElMessage.success('修正已应用')
          emit('update-unit-content', {
            chapter_number: issue.location?.chapter_number,
            unit_id: issue.location?.unit_id,
            content: issue.auto_fix.fixed
          })
          ElMessage.info('修正已应用，您可以点击“重新检测”查看得分变化')
        } else {
          ElMessage.error(applyResponse?.message || '应用修正失败')
        }
      }
    } else {
      console.error('生成修正方案失败:', response)
      ElMessage.error(response?.message || '生成修正方案失败')
    }
  } catch (error) {
    console.error('generateFixWithLLM 错误:', error)
    if (error !== 'cancel') {
      // 检测超时错误
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        ElMessage.error('生成修正方案超时（5分钟），LLM响应较慢。请稍后重试或尝试其他问题。')
      } else {
        ElMessage.error('生成修正方案失败: ' + (error.message || String(error)))
      }
    }
  } finally {
    applyingFix.value = null
  }
}

// v2.1新增: 重新分析质量
const handleReAnalyze = async () => {
  try {
    reAnalyzing.value = true
    previousScore.value = props.qualityReport?.overall_score
    
    const response = await qualityControlApi.reAnalyze({
      project_id: props.projectId,
      chapter_number: null,
      depth: 'standard'
    })
    
    if (response?.success) {
      const { new_report, score_changes } = response.data || {}
      
      // 更新质量报告
      emit('update-quality-report', new_report)
      
      // 计算得分变化
      if (previousScore.value !== null) {
        scoreChanges.value = {
          overall: {
            previous: previousScore.value,
            current: new_report.overall_score,
            delta: new_report.overall_score - previousScore.value
          },
          dimensions: {}
        }
        
        // 计算各维度得分变化
        const oldDims = props.qualityReport?.dimension_scores || {}
        const newDims = new_report.dimension_scores || {}
        
        for (const [dim, score] of Object.entries(newDims)) {
          scoreChanges.value.dimensions[dim] = {
            previous: oldDims[dim] || 0,
            current: score,
            delta: score - (oldDims[dim] || 0)
          }
        }
        
        ElMessage.success(
          `重新检测完成! 得分: ${previousScore.value.toFixed(1)} → ${new_report.overall_score.toFixed(1)}`
        )
        
        // 显示得分变化对话框
        showScoreChangesDialog()
      } else {
        ElMessage.success('重新检测完成')
      }
    } else {
      ElMessage.error(response?.message || '重新检测失败')
    }
  } catch (error) {
    // 检测超时错误
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.error('重新检测超时（5分钟），请稍后重试。')
    } else {
      ElMessage.error('重新检测失败: ' + (error.message || ''))
    }
  } finally {
    reAnalyzing.value = false
  }
}

// ==================== 全局大纲质控处理函数 (v1.0新增) ====================

/**
 * 触发全局大纲质量检测
 */
const handleGlobalOutlineQC = async () => {
  try {
    // 触发父组件的检测逻辑
    emit('analyze-global-outline-qc')
  } catch (error) {
    console.error('[全局大纲质控] 触发检测失败:', error)
    ElMessage.error('触发质量检测失败')
  }
}

/**
 * 修正全局大纲问题
 */
const handleGlobalOutlineRevise = async (issue) => {
  try {
    // 触发父组件的修正逻辑
    emit('revise-global-outline', {
      issue,
      qualityReport: props.globalOutlineQCReport
    })
  } catch (error) {
    console.error('[全局大纲质控] 触发修正失败:', error)
    ElMessage.error('触发修正失败')
  }
}

// v2.1新增: 显示得分变化对话框
const showScoreChangesDialog = () => {
  if (!scoreChanges.value) return
  
  const deltaText = scoreChanges.value.overall.delta >= 0 ? '+' : ''
  const deltaType = scoreChanges.value.overall.delta >= 0 ? 'success' : 'danger'
  
  let dimensionsHtml = ''
  if (scoreChanges.value.dimensions) {
    dimensionsHtml = Object.entries(scoreChanges.value.dimensions)
      .filter(([_, data]) => data.delta !== 0)  // 只显示有变化的维度
      .map(([dim, data]) => {
        const dimName = {
          'unit_structure': '结构层',
          'unit_character': '人物层',
          'unit_consistency': '一致性层',
          'unit_timeline_space': '时间线空间',
          'unit_ooc': '人物OOC'
        }[dim] || dim
        
        const d = data.delta >= 0 ? '+' : ''
        const t = data.delta >= 0 ? 'success' : 'danger'
        
        return `
          <div style="margin: 8px 0; display: flex; justify-content: space-between; align-items: center;">
            <span>${dimName}</span>
            <span>
              ${data.previous.toFixed(1)} → ${data.current.toFixed(1)}
              <span style="margin-left: 8px; color: ${t === 'success' ? '#67c23a' : '#f56c6c'}; font-weight: bold;">
                ${d}${data.delta.toFixed(1)}
              </span>
            </span>
          </div>
        `
      }).join('')
  }
  
  ElMessageBox.alert(
    `
      <div style="padding: 16px;">
        <h4 style="margin: 0 0 16px 0; color: #303133;">得分变化详情</h4>
        
        <div style="background: #f5f7fa; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 16px;">
            <strong>总体得分</strong>
            <div>
              <span style="color: #909399;">${scoreChanges.value.overall.previous.toFixed(1)}</span>
              <span style="margin: 0 8px; color: #909399;">→</span>
              <span style="color: #303133; font-weight: bold;">${scoreChanges.value.overall.current.toFixed(1)}</span>
              <el-tag type="${deltaType}" size="small" style="margin-left: 8px;">
                ${deltaText}${scoreChanges.value.overall.delta.toFixed(1)}
              </el-tag>
            </div>
          </div>
        </div>
        
        ${dimensionsHtml ? `
          <div style="border-top: 1px solid #ebeef5; padding-top: 16px;">
            <div style="color: #606266; margin-bottom: 12px; font-weight: 500;">维度得分变化:</div>
            ${dimensionsHtml}
          </div>
        ` : ''}
      </div>
    `,
    '得分变化',
    {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '确定',
      type: scoreChanges.value.overall.delta >= 0 ? 'success' : 'info'
    }
  )
}
</script>

<style lang="scss" scoped>
.result-container {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(64, 158, 255, 0.08);
  margin-bottom: 24px;
  
  .result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 2px solid #f0f2f5;
    
    h3 {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 8px;
      
      &::before {
        content: '✨';
        font-size: 20px;
      }
    }
    
    .result-meta {
      display: flex;
      align-items: center;
      gap: 16px;
      
      .duration-tag {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      
      .result-actions {
        display: flex;
        gap: 8px;
        
        .el-button {
          font-weight: 500;
        }
      }
    }
  }
  
  .result-content {
    background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
    border-radius: 8px;
    padding: 24px;
    border: 1px solid #e4e7ed;
    min-height: 200px;
  }
}

.outline-stages {
  margin-bottom: 24px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  
  .el-steps {
    margin-bottom: 20px;
  }
  
  .stage-actions {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-top: 16px;
  }
}

.global-outline-edit {
  margin-bottom: 24px;
  border: 2px solid #409eff;  // 增强边框,使用主题色
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);  // 添加阴影增强可见性
  background: linear-gradient(to bottom, #ffffff, #f8f9fa);  // 渐变背景
  
  .edit-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;  // 增加内边距
    background: linear-gradient(135deg, #ecf5ff 0%, #f5f7fa 100%);  // 渐变背景
    border-bottom: 2px solid #d9ecff;  // 增强分隔线
    
    .edit-tip {
      font-size: 14px;
      color: #409eff;  // 使用主题色,更醒目
      display: flex;
      align-items: center;
      gap: 6px;
      font-weight: 500;  // 加粗
      
      .el-icon {
        font-size: 16px;
      }
    }
    
    .edit-actions {
      display: flex;
      gap: 10px;  // 增加按钮间距
      
      .el-button {
        font-weight: 500;  // 按钮文字加粗
      }
    }
  }
  
  .edit-content {
    padding: 16px;
    
    .el-textarea {
      font-family: monospace;
      border: 1px solid #dcdfe6;
      border-radius: 4px;
      
      &:focus {
        border-color: #409eff;
        box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
      }
    }
    
    .preview-content {
      max-height: 500px;
      overflow-y: auto;
      padding: 12px;  // 增加内边距
      background: #ffffff;
      border: 1px solid #ebeef5;
      border-radius: 4px;
    }
  }
}

.logic-check-status {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  
  .logic-checking {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #409eff;
    font-size: 14px;
    
    .el-icon {
      font-size: 16px;
    }
  }
  
  .logic-check-result {
    .has-issues {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #e6a23c;
      font-size: 14px;
      
      .el-icon {
        font-size: 16px;
      }
    }
    
    .no-issues {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #67c23a;
      font-size: 14px;
      
      .el-icon {
        font-size: 16px;
      }
    }
  }
}

// 全局大纲质控报告样式
.global-outline-qc-report {
  margin-top: 24px;
  padding: 20px;
  background: #fff8e6;
  border-radius: 8px;
  border: 2px solid #e6a23c;
}

// 质量管控报告样式
.quality-control-report {
  margin-top: 24px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.qc-summary {
  margin-bottom: 20px;
}

.dimension-scores {
  margin: 20px 0;
  
  h4 {
    margin-bottom: 16px;
    color: #303133;
  }
}

.dimension-card {
  margin-bottom: 16px;
}

// v2.2: 问题入口按钮
.issues-entry {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

// v2.2: 问题详情弹窗样式
:deep(.issues-dialog) {
  .el-dialog__body {
    padding: 20px;
    max-height: 75vh;
    overflow-y: auto;
  }
  
  .issues-dialog-content {
    .el-collapse {
      border: 1px solid #e4e7ed;
      border-radius: 8px;
    }
  }
}

.issue-title {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.issue-dimension {
  color: #909399;
  font-size: 12px;
}

.issue-desc {
  flex: 1;
  color: #606266;
}

.issue-detail {
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
  
  p {
    margin: 8px 0;
    line-height: 1.6;
    
    strong {
      color: #303133;
    }
  }
}

.qc-passed {
  margin-top: 20px;
}

// 修订模式对话框样式
:deep(.revision-dialog) {
  .el-dialog__body {
    padding: 0;
    height: 75vh;
  }
}

.revision-container {
  display: flex;
  height: 100%;
  gap: 0;
  
  .revision-chat {
    flex: 1;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #e4e7ed;
    
    .chat-header {
      padding: 16px 20px;
      border-bottom: 1px solid #e4e7ed;
      background: #f5f7fa;
      
      h4 {
        margin: 0;
        font-size: 16px;
        color: #303133;
        display: flex;
        align-items: center;
        
        .el-icon {
          margin-right: 8px;
          font-size: 18px;
        }
      }
    }
    
    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      background: #fafafa;
      
      .empty-message {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
      }
      
      .message-item {
        margin-bottom: 16px;
        
        .message {
          display: flex;
          gap: 12px;
          align-items: flex-start;
          
          .message-avatar {
            font-size: 24px;
            flex-shrink: 0;
          }
          
          .message-content {
            flex: 1;
            padding: 12px 16px;
            border-radius: 8px;
            line-height: 1.6;
            
            .loading-indicator {
              display: flex;
              align-items: center;
              gap: 8px;
              color: #409eff;
              
              .el-icon {
                font-size: 16px;
              }
            }
          }
        }
        
        .user-message {
          .message-content {
            background: #ecf5ff;
            border: 1px solid #d9ecff;
          }
        }
        
        .ai-message {
          .message-content {
            background: #ffffff;
            border: 1px solid #e4e7ed;
          }
        }
      }
    }
    
    .chat-input {
      padding: 16px 20px;
      border-top: 1px solid #e4e7ed;
      background: #ffffff;
      
      .uploaded-files-list {
        margin-bottom: 12px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        
        .file-tag {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          background: #ecf5ff;
          border: 1px solid #d9ecff;
          border-radius: 4px;
          font-size: 13px;
          color: #409eff;
          
          .el-icon:first-child {
            font-size: 14px;
          }
          
          .file-name {
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          
          .file-size {
            color: #909399;
            font-size: 12px;
          }
          
          .remove-file {
            cursor: pointer;
            font-size: 14px;
            color: #909399;
            
            &:hover {
              color: #f56c6c;
            }
          }
        }
      }
      
      .el-textarea {
        margin-bottom: 12px;
      }
      
      .input-actions {
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        .left-actions {
          display: flex;
          align-items: center;
          gap: 12px;
          
          .el-button {
            color: #606266;
            
            &:hover {
              color: #409eff;
            }
            
            .el-icon {
              margin-right: 4px;
            }
          }
        }
        
        .right-actions {
          display: flex;
          gap: 8px;
        }
      }
    }
  }
  
  .revision-preview {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: #ffffff;
    
    .preview-header {
      padding: 16px 20px;
      border-bottom: 1px solid #e4e7ed;
      background: #f5f7fa;
      
      h4 {
        margin: 0;
        font-size: 16px;
        color: #303133;
        display: flex;
        align-items: center;
        
        .el-icon {
          margin-right: 8px;
          font-size: 18px;
        }
      }
    }
    
    .preview-content {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      
      .markdown-content {
        line-height: 1.8;
      }
    }
  }
}

.revision-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 12px 0;
}
</style>
