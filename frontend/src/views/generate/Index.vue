<template>
  <div class="generate-page">
    <h1 class="page-title">创意生成</h1>
    <p class="page-desc">选择一个创作模块开始生成您的创意内容</p>
    
    <div class="module-grid">
      <div
        v-for="module in creativeModules"
        :key="module.key"
        class="module-card"
        :style="{ '--module-color': module.color }"
        @click="selectModule(module)"
      >
        <div class="module-icon">
          <el-icon :size="48">
            <component :is="resolveElementIcon(module.icon)" />
          </el-icon>
        </div>
        <div class="module-content">
          <h2>{{ module.title }}</h2>
          <p>{{ module.description }}</p>
        </div>
        <div class="module-arrow">
          <el-icon :size="20"><ArrowRight /></el-icon>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { CREATIVE_MODULES } from '@/config'
import { resolveElementIcon } from '@/utils/elementIcons'

const router = useRouter()
const creativeModules = CREATIVE_MODULES

function selectModule(module) {
  router.push(`/generate/${module.key}`)
}
</script>

<style lang="scss" scoped>
.generate-page {
  max-width: 1000px;
  margin: 0 auto;
  
  .page-title {
    font-size: 28px;
    color: #303133;
    margin-bottom: 10px;
  }
  
  .page-desc {
    color: #909399;
    margin-bottom: 30px;
  }
}

.module-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  
  .module-card {
    display: flex;
    align-items: center;
    background: #fff;
    border-radius: 16px;
    padding: 24px 30px;
    cursor: pointer;
    transition: all 0.3s;
    border-left: 4px solid var(--module-color);
    
    &:hover {
      transform: translateX(8px);
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
      
      .module-icon {
        transform: scale(1.1);
        background: var(--module-color);
        color: #fff;
      }
      
      .module-arrow {
        opacity: 1;
        transform: translateX(10px);
      }
    }
    
    .module-icon {
      width: 80px;
      height: 80px;
      border-radius: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 0, 0, 0.04);
      color: var(--module-color);
      transition: all 0.3s;
      flex-shrink: 0;
    }
    
    .module-content {
      flex: 1;
      margin-left: 24px;
      
      h2 {
        font-size: 20px;
        color: #303133;
        margin-bottom: 8px;
      }
      
      p {
        color: #909399;
        font-size: 14px;
      }
    }
    
    .module-arrow {
      opacity: 0.3;
      color: var(--module-color);
      transition: all 0.3s;
    }
  }
}
</style>
