<template>
  <!-- 欢迎对话框 -->
  <el-dialog
    v-model="welcomeVisible"
    title="🎉 欢迎使用全能创意大师"
    width="600px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    class="onboarding-dialog welcome-dialog"
    aria-label="新手欢迎引导"
    @opened="focusFirstAction"
  >
    <div class="onboarding-content">
      <div class="welcome-header">
        <el-icon :size="64" color="#409EFF"><MagicStick /></el-icon>
        <h2>开启您的AI创作之旅</h2>
      </div>
      
      <div class="steps-preview">
        <div class="step-item active">
          <div class="step-number">1</div>
          <div class="step-text">
            <strong>欢迎引导</strong>
            <p>了解系统核心功能</p>
          </div>
        </div>
        <div class="step-item" :class="{ active: !hasAPIKeys }">
          <div class="step-number">2</div>
          <div class="step-text">
            <strong>配置API Key</strong>
            <p>连接AI模型（必需）</p>
          </div>
        </div>
        <div class="step-item">
          <div class="step-number">3</div>
          <div class="step-text">
            <strong>开始创作</strong>
            <p>选择模块生成内容</p>
          </div>
        </div>
      </div>
      
      <el-alert
        title="💡 提示"
        type="info"
        :closable="false"
        show-icon
      >
        <p>首次使用需要配置API Key才能生成功能。系统将引导您完成设置。</p>
      </el-alert>
    </div>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleSkip" size="large">
          跳过引导
        </el-button>
        <el-button type="primary" @click="handleWelcomeComplete" size="large">
          开始配置 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>
    </template>
  </el-dialog>
  
  <!-- API Key配置引导对话框 -->
  <el-dialog
    v-model="apiGuideVisible"
    title="🔑 配置API Key"
    width="650px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    class="onboarding-dialog api-guide-dialog"
    aria-label="API Key 配置引导"
    @opened="focusFirstAction"
  >
    <div class="onboarding-content">
      <div class="api-guide-header">
        <el-icon :size="48" color="#E6A23C"><Key /></el-icon>
        <h2>连接AI模型</h2>
      </div>
      
      <div class="api-guide-steps">
        <div class="guide-step">
          <div class="guide-step-number">1</div>
          <div class="guide-step-content">
            <h4>获取API Key</h4>
            <p>从AI模型提供商获取API密钥：</p>
            <ul>
              <li><strong>OpenAI</strong>: platform.openai.com</li>
              <li><strong>智谱AI</strong>: open.bigmodel.cn</li>
              <li><strong>DeepSeek</strong>: platform.deepseek.com</li>
              <li><strong>其他</strong>: 查看模型提供商文档</li>
            </ul>
          </div>
        </div>
        
        <div class="guide-step">
          <div class="guide-step-number">2</div>
          <div class="guide-step-content">
            <h4>配置密钥</h4>
            <p>点击下方按钮进入API Key管理页面：</p>
            <el-button type="primary" @click="goToApiKeyPage" size="large">
              <el-icon><Key /></el-icon>
              前往配置
            </el-button>
          </div>
        </div>
        
        <div class="guide-step">
          <div class="guide-step-number">3</div>
          <div class="guide-step-content">
            <h4>测试连接</h4>
            <p>添加密钥后，点击"测试连接"验证是否配置成功</p>
          </div>
        </div>
      </div>
      
      <el-alert
        title="🔒 安全提示"
        type="warning"
        :closable="false"
        show-icon
      >
        <p>API Key仅保存在您的本地数据库中，不会上传到任何第三方服务器。</p>
      </el-alert>
    </div>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleSkip" size="large">
          稍后配置
        </el-button>
        <el-button type="success" @click="handleApiGuideComplete" size="large">
          我已完成配置 <el-icon><Check /></el-icon>
        </el-button>
      </div>
    </template>
  </el-dialog>
  
  <!-- 首次生成庆祝 -->
  <el-dialog
    v-model="celebrationVisible"
    width="400px"
    :show-close="false"
    class="celebration-dialog"
  >
    <div class="celebration-content">
      <div class="celebration-icon">🎊</div>
      <h2>恭喜！</h2>
      <p>您完成了第一次AI生成</p>
      <div class="celebration-tips">
        <p>💡 下一步建议：</p>
        <ul>
          <li>尝试"小说/剧本生成"创作长篇作品</li>
          <li>使用知识库增强生成质量</li>
          <li>探索质控功能优化内容</li>
        </ul>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { MagicStick, ArrowRight, Key, Check } from '@element-plus/icons-vue'

const props = defineProps({
  showWelcome: {
    type: Boolean,
    default: false
  },
  showApiGuide: {
    type: Boolean,
    default: false
  },
  showCelebration: {
    type: Boolean,
    default: false
  },
  hasAPIKeys: {
    type: Boolean,
    default: false
  },
  /** 当前引导版本号 */
  onboardingVersion: {
    type: Number,
    default: 1
  }
})

const emit = defineEmits(['welcome-complete', 'api-guide-complete', 'skip-all'])

const router = useRouter()

const welcomeVisible = computed({
  get: () => props.showWelcome,
  set: (val) => {
    if (!val) emit('welcome-complete')
  }
})

const apiGuideVisible = computed({
  get: () => props.showApiGuide,
  set: (val) => {
    if (!val) emit('api-guide-complete')
  }
})

const celebrationVisible = computed({
  get: () => props.showCelebration,
  set: () => {}
})

function handleWelcomeComplete() {
  emit('welcome-complete')
}

function handleApiGuideComplete() {
  emit('api-guide-complete')
}

function handleSkip() {
  emit('skip-all')
}

function goToApiKeyPage() {
  router.push('/api-keys')
}

/**
 * 对话框打开时将焦点移动到第一个可操作按钮
 * 提升键盘无障碍体验
 */
function focusFirstAction() {
  // 使用 nextTick 确保 DOM 已渲染
  setTimeout(() => {
    const dialog = document.querySelector('.onboarding-dialog .el-dialog__footer .el-button--primary')
    if (dialog) dialog.focus()
  }, 100)
}
</script>

<style lang="scss" scoped>
.onboarding-dialog {
  :deep(.el-dialog__header) {
    border-bottom: 1px solid rgba(64, 158, 255, 0.1);
    padding: 20px 24px;
  }
  
  :deep(.el-dialog__body) {
    padding: 24px;
  }
  
  :deep(.el-dialog__footer) {
    border-top: 1px solid rgba(64, 158, 255, 0.1);
    padding: 16px 24px;
  }
}

.onboarding-content {
  .welcome-header,
  .api-guide-header {
    text-align: center;
    margin-bottom: 24px;
    
    .el-icon {
      margin-bottom: 12px;
    }
    
    h2 {
      font-size: 24px;
      color: #303133;
      margin: 0;
    }
  }
  
  .steps-preview {
    margin: 24px 0;
    
    .step-item {
      display: flex;
      align-items: flex-start;
      gap: 16px;
      padding: 16px;
      margin-bottom: 12px;
      border-radius: 12px;
      background: #f5f7fa;
      opacity: 0.5;
      transition: all 0.3s;
      
      &.active {
        background: linear-gradient(135deg, rgba(64, 158, 255, 0.1), rgba(0, 212, 170, 0.1));
        opacity: 1;
        border: 1px solid rgba(64, 158, 255, 0.3);
      }
      
      .step-number {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #409EFF;
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 16px;
        flex-shrink: 0;
      }
      
      .step-text {
        flex: 1;
        
        strong {
          display: block;
          font-size: 16px;
          color: #303133;
          margin-bottom: 4px;
        }
        
        p {
          margin: 0;
          font-size: 14px;
          color: #606266;
        }
      }
    }
  }
  
  .api-guide-steps {
    margin: 24px 0;
    
    .guide-step {
      display: flex;
      gap: 16px;
      padding: 20px;
      margin-bottom: 16px;
      background: #fafafa;
      border-radius: 12px;
      border-left: 4px solid #409EFF;
      
      .guide-step-number {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #409EFF;
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        flex-shrink: 0;
      }
      
      .guide-step-content {
        flex: 1;
        
        h4 {
          margin: 0 0 8px;
          font-size: 16px;
          color: #303133;
        }
        
        p {
          margin: 0 0 12px;
          font-size: 14px;
          color: #606266;
        }
        
        ul {
          margin: 0;
          padding-left: 20px;
          
          li {
            font-size: 14px;
            color: #606266;
            margin-bottom: 6px;
            
            strong {
              color: #303133;
            }
          }
        }
      }
    }
  }
  
  .el-alert {
    margin-top: 20px;
  }
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  
  .el-button {
    min-width: 120px;
  }
}

.celebration-dialog {
  :deep(.el-dialog__body) {
    padding: 40px 24px;
    text-align: center;
  }
}

.celebration-content {
  .celebration-icon {
    font-size: 80px;
    margin-bottom: 16px;
    animation: celebration-bounce 0.6s ease-out;
  }
  
  h2 {
    font-size: 28px;
    color: #303133;
    margin: 0 0 8px;
    background: linear-gradient(90deg, #409EFF, #00D4AA);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  > p {
    font-size: 16px;
    color: #606266;
    margin: 0 0 24px;
  }
  
  .celebration-tips {
    text-align: left;
    background: #f5f7fa;
    padding: 16px 20px;
    border-radius: 12px;
    
    > p {
      margin: 0 0 12px;
      font-size: 14px;
      color: #303133;
      font-weight: 600;
    }
    
    ul {
      margin: 0;
      padding-left: 20px;
      
      li {
        font-size: 14px;
        color: #606266;
        margin-bottom: 8px;
      }
    }
  }
}

@keyframes celebration-bounce {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
