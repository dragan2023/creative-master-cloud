<template>
  <div class="not-found-page">
    <div class="content">
      <h1>404</h1>
      <p>页面未找到</p>
      <el-button type="primary" @click="router.push('/')">返回首页</el-button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style lang="scss" scoped>
.not-found-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  
  .content {
    text-align: center;
    
    h1 {
      font-size: 120px;
      font-weight: 700;
      color: #409EFF;
      margin: 0;
      line-height: 1;
    }
    
    p {
      font-size: 24px;
      color: #606266;
      margin: 20px 0 30px;
    }
  }
}
</style>
