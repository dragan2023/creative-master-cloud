<template>
  <div class="login-page">
    <div class="login-container">
      <!-- 左侧装饰 -->
      <div class="login-left">
        <div class="brand">
          <el-icon :size="60" color="#fff"><MagicStick /></el-icon>
          <h1>全能创意大师</h1>
          <p>基于AI的智能创意生成平台</p>
        </div>
        
        <div class="features">
          <div class="feature-item">
            <el-icon :size="24"><VideoCamera /></el-icon>
            <span>短视频脚本生成</span>
          </div>
          <div class="feature-item">
            <el-icon :size="24"><Document /></el-icon>
            <span>剧本大纲创作</span>
          </div>
          <div class="feature-item">
            <el-icon :size="24"><Notebook /></el-icon>
            <span>小说大纲生成</span>
          </div>
          <div class="feature-item">
            <el-icon :size="24"><Picture /></el-icon>
            <span>平面广告设计</span>
          </div>
          <div class="feature-item">
            <el-icon :size="24"><Film /></el-icon>
            <span>TVC广告脚本</span>
          </div>
        </div>
      </div>
      
      <!-- 右侧登录表单 -->
      <div class="login-right">
        <div class="login-form-container">
          <h2>欢迎登录</h2>
          <p class="subtitle">登录您的账户开始创作</p>
          
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            @submit.prevent="handleLogin"
            size="large"
          >
            <el-form-item prop="username">
              <el-input
                v-model="form.username"
                placeholder="用户名"
                :prefix-icon="User"
              />
            </el-form-item>
            
            <el-form-item prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密码"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>
            
            <el-form-item>
              <el-button
                type="primary"
                native-type="submit"
                :loading="loading"
                class="login-btn"
              >
                登录
              </el-button>
            </el-form-item>
          </el-form>
          
          <div class="footer">
            <span>还没有账户？</span>
            <router-link to="/register">立即注册</router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ]
}

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  loading.value = true
  try {
    await userStore.login(form)
    ElMessage.success('登录成功')
    
    // 跳转到之前的页面或首页
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (error) {
    console.error('登录失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-container {
  display: flex;
  width: 900px;
  height: 560px;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-left {
  width: 400px;
  padding: 60px 40px;
  background: linear-gradient(135deg, #409EFF 0%, #36D1DC 100%);
  display: flex;
  flex-direction: column;
  
  .brand {
    text-align: center;
    color: #fff;
    
    h1 {
      margin: 20px 0 10px;
      font-size: 28px;
    }
    
    p {
      opacity: 0.9;
      font-size: 14px;
    }
  }
  
  .features {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 20px;
    margin-top: 40px;
    
    .feature-item {
      display: flex;
      align-items: center;
      gap: 12px;
      color: #fff;
      font-size: 15px;
      padding: 10px 20px;
      background: rgba(255, 255, 255, 0.15);
      border-radius: 8px;
    }
  }
}

.login-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  
  .login-form-container {
    width: 100%;
    max-width: 320px;
    
    h2 {
      font-size: 28px;
      color: #303133;
      margin-bottom: 8px;
    }
    
    .subtitle {
      color: #909399;
      margin-bottom: 30px;
    }
    
    .login-btn {
      width: 100%;
      height: 44px;
      font-size: 16px;
    }
    
    .footer {
      text-align: center;
      margin-top: 20px;
      color: #909399;
      
      a {
        color: #409EFF;
        text-decoration: none;
        margin-left: 5px;
        
        &:hover {
          text-decoration: underline;
        }
      }
    }
  }
}
</style>
