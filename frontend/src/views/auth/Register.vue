<template>
  <div class="register-page">
    <div class="register-container">
      <!-- 左侧装饰 -->
      <div class="register-left">
        <div class="brand">
          <el-icon :size="60" color="#fff"><MagicStick /></el-icon>
          <h1>全能创意大师</h1>
          <p>开启您的AI创意之旅</p>
        </div>
        
        <div class="benefits">
          <h3>注册即可享受</h3>
          <ul>
            <li>
              <el-icon><Check /></el-icon>
              <span>多种AI模型支持</span>
            </li>
            <li>
              <el-icon><Check /></el-icon>
              <span>私有知识库定制</span>
            </li>
            <li>
              <el-icon><Check /></el-icon>
              <span>创作历史记录</span>
            </li>
            <li>
              <el-icon><Check /></el-icon>
              <span>实时流式输出</span>
            </li>
          </ul>
        </div>
      </div>
      
      <!-- 右侧注册表单 -->
      <div class="register-right">
        <div class="register-form-container">
          <h2>创建账户</h2>
          <p class="subtitle">填写以下信息完成注册</p>
          
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            @submit.prevent="handleRegister"
            size="large"
          >
            <el-form-item prop="username">
              <el-input
                v-model="form.username"
                placeholder="用户名"
                :prefix-icon="User"
              />
            </el-form-item>
            
            <el-form-item prop="email">
              <el-input
                v-model="form.email"
                placeholder="邮箱"
                :prefix-icon="Message"
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
            
            <el-form-item prop="confirmPassword">
              <el-input
                v-model="form.confirmPassword"
                type="password"
                placeholder="确认密码"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>
            
            <el-form-item>
              <el-button
                type="primary"
                native-type="submit"
                :loading="loading"
                class="register-btn"
              >
                注册
              </el-button>
            </el-form-item>
          </el-form>
          
          <div class="footer">
            <span>已有账户？</span>
            <router-link to="/login">立即登录</router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名3-20个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

async function handleRegister() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  loading.value = true
  try {
    await userStore.register({
      username: form.username,
      email: form.email,
      password: form.password
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (error) {
    console.error('注册失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.register-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
}

.register-container {
  display: flex;
  width: 900px;
  height: 600px;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.register-left {
  width: 380px;
  padding: 50px 40px;
  background: linear-gradient(135deg, #67C23A 0%, #38ef7d 100%);
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
  
  .benefits {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    margin-top: 30px;
    
    h3 {
      color: #fff;
      font-size: 18px;
      margin-bottom: 20px;
      text-align: center;
    }
    
    ul {
      list-style: none;
      padding: 0;
      
      li {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #fff;
        font-size: 15px;
        padding: 12px 20px;
        margin-bottom: 10px;
        background: rgba(255, 255, 255, 0.15);
        border-radius: 8px;
      }
    }
  }
}

.register-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  
  .register-form-container {
    width: 100%;
    max-width: 320px;
    
    h2 {
      font-size: 28px;
      color: #303133;
      margin-bottom: 8px;
    }
    
    .subtitle {
      color: #909399;
      margin-bottom: 25px;
    }
    
    .register-btn {
      width: 100%;
      height: 44px;
      font-size: 16px;
    }
    
    .footer {
      text-align: center;
      margin-top: 20px;
      color: #909399;
      
      a {
        color: #67C23A;
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
