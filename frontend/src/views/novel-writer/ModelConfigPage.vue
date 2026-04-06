<!--
  多Agent协作文学作品生成系统 - 模型配置独立页面
  
  模块: writing-engine
  文件: ModelConfigPage.vue
  功能: 提供独立的模型配置管理入口，无需进入项目即可配置
  
  依赖关系:
      - 组件: ModelConfigPanel.vue
      - 路由: /novel-writer/model-config
  
  创建时间: 2026-03-30
  版本: 1.0.0
-->
<template>
  <div class="model-config-page">
    <div class="page-header">
      <el-button @click="goBack" text>
        <el-icon><ArrowLeft /></el-icon>
        返回列表
      </el-button>
      <h2 class="page-title">LLM模型配置管理</h2>
    </div>
    
    <div class="page-content">
      <ModelConfigPanel />
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import ModelConfigPanel from './ModelConfigPanel.vue'

const router = useRouter()

function goBack() {
  router.push('/novel-writer')
}
</script>

<style lang="scss" scoped>
.model-config-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  
  .page-title {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: #303133;
    display: flex;
    align-items: center;
    gap: 10px;
    
    &::before {
      content: '';
      width: 4px;
      height: 20px;
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 2px;
    }
  }
}

.page-content {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}
</style>
