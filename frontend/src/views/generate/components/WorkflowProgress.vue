<template>
  <div class="workflow-container" v-if="generating || workflowSteps.length > 0">
    <div class="workflow-header">
      <h3>
        <el-icon class="workflow-icon" :class="{ 'is-spinning': generating }"><Loading /></el-icon>
        Agent 工作流程
      </h3>
      <el-tag v-if="workflowComplete" type="success" size="small">已完成</el-tag>
      <el-tag v-else-if="generating" type="warning" size="small">执行中...</el-tag>
    </div>
    
    <div class="workflow-steps">
      <div
        v-for="(step, index) in workflowSteps"
        :key="`${step.step}-${index}`"
        class="workflow-step"
        :class="{
          'is-running': step.status === 'running',
          'is-done': step.status === 'done',
          'is-error': step.status === 'error'
        }"
      >
        <div class="step-icon">
          <el-icon v-if="step.status === 'running'" class="is-spinning"><Loading /></el-icon>
          <el-icon v-else-if="step.status === 'done'" color="#67C23A"><CircleCheck /></el-icon>
          <el-icon v-else-if="step.status === 'error'" color="#F56C6C"><CircleClose /></el-icon>
          <el-icon v-else><component :is="step.icon" /></el-icon>
        </div>
        <div class="step-content">
          <div class="step-message">{{ step.message }}</div>
        </div>
        <div class="step-status">
          <el-tag v-if="step.status === 'done'" type="success" size="small">完成</el-tag>
          <el-tag v-else-if="step.status === 'running'" type="warning" size="small">执行中</el-tag>
          <el-tag v-else-if="step.status === 'error'" type="danger" size="small">失败</el-tag>
        </div>
      </div>
    </div>
  </div>
  
  <!-- 空状态提示 -->
  <div class="workflow-empty" v-else>
    <el-empty description="填写表单后开始生成，工作流程将在此显示" />
  </div>
</template>

<script setup>
import { stepIcons } from '../composables/useWorkflow'

defineProps({
  generating: {
    type: Boolean,
    default: false
  },
  workflowSteps: {
    type: Array,
    default: () => []
  },
  workflowComplete: {
    type: Boolean,
    default: false
  }
})
</script>

<style lang="scss" scoped>
.workflow-container {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(64, 158, 255, 0.08);
  position: sticky;
  top: 20px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
  
  &::-webkit-scrollbar {
    width: 6px;
  }
  
  &::-webkit-scrollbar-track {
    background: #f5f7fa;
    border-radius: 3px;
  }
  
  &::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #409EFF, #00D4AA);
    border-radius: 3px;
    
    &:hover {
      background: #409EFF;
    }
  }
  
  .workflow-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 2px solid #f0f2f5;
    
    h3 {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      
      .workflow-icon {
        color: #667eea;
        
        &.is-spinning {
          animation: spin 1s linear infinite;
        }
      }
    }
  }
  
  .workflow-steps {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .workflow-step {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: #f8f9fa;
    border-radius: 8px;
    transition: all 0.3s ease;
    border: 1px solid transparent;
    
    &.is-running {
      background: linear-gradient(135deg, #fff5e6 0%, #ffe8cc 100%);
      border-color: #ffd591;
      box-shadow: 0 2px 8px rgba(255, 213, 145, 0.3);
    }
    
    &.is-done {
      background: linear-gradient(135deg, #f0f9ff 0%, #e6f4ff 100%);
      border-color: #91d5ff;
    }
    
    &.is-error {
      background: linear-gradient(135deg, #fff1f0 0%, #ffccc7 100%);
      border-color: #ffa39e;
    }
    
    .step-icon {
      flex-shrink: 0;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: #fff;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
      
      .el-icon {
        font-size: 18px;
        
        &.is-spinning {
          animation: spin 1s linear infinite;
        }
      }
    }
    
    .step-content {
      flex: 1;
      min-width: 0;
      
      .step-message {
        font-size: 14px;
        color: #303133;
        line-height: 1.5;
        word-break: break-word;
      }
    }
    
    .step-status {
      flex-shrink: 0;
    }
  }
}

.workflow-empty {
  background: #fff;
  border-radius: 16px;
  padding: 60px 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(64, 158, 255, 0.08);
  text-align: center;
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
