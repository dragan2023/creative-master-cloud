<template>
  <AuthLayout
    accent-color="#00D4AA"
    accent-rgb="0, 212, 170"
    secondary-color="#409EFF"
    secondary-rgb="64, 158, 255"
    container-height="620px"
  >
    <template #brand-subtitle>开启您的AI创意之旅</template>

    <template #left-content>
      <div class="benefits">
        <h3 class="auth-list-title">注册即可享受</h3>
        <div class="auth-list-item">
          <div class="auth-list-icon small"><el-icon><Check /></el-icon></div>
          <span>多种AI模型支持</span>
        </div>
        <div class="auth-list-item">
          <div class="auth-list-icon small"><el-icon><Check /></el-icon></div>
          <span>私有知识库定制</span>
        </div>
        <div class="auth-list-item">
          <div class="auth-list-icon small"><el-icon><Check /></el-icon></div>
          <span>创作历史记录</span>
        </div>
        <div class="auth-list-item">
          <div class="auth-list-icon small"><el-icon><Check /></el-icon></div>
          <span>实时流式输出</span>
        </div>
      </div>
    </template>

    <template #form-title>创建账户</template>
    <template #form-subtitle>填写以下信息完成注册</template>

    <template #form-content>
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
            placeholder="用户名（3-50个字符）"
            :prefix-icon="User"
            maxlength="50"
            show-word-limit
            clearable
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
            placeholder="密码（6-50个字符）"
            :prefix-icon="Lock"
            show-password
            maxlength="50"
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="确认密码"
            :prefix-icon="Lock"
            show-password
            maxlength="50"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            class="auth-submit-btn"
          >
            <span v-if="!loading">注册</span>
            <span v-else>注册中...</span>
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <template #footer>
      <span>已有账户？</span>
      <router-link to="/login">立即登录</router-link>
    </template>
  </AuthLayout>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message, Check } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores'
import { ElMessage } from 'element-plus'
import AuthLayout from './AuthLayout.vue'

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
    { min: 3, max: 50, message: '用户名长度为3-50个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 50, message: '密码长度为6-50个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

async function handleRegister() {
  // 防重复提交：如果正在加载中，直接返回
  if (loading.value) {
    console.warn('[Register] 注册请求进行中，忽略重复提交')
    return
  }
  
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
    // 添加错误提示（原来缺失）
    ElMessage.error(error.response?.data?.message || '注册失败，请稍后重试')
  } finally {
    // 添加300ms冷却期，防止快速重试
    setTimeout(() => {
      loading.value = false
    }, 300)
  }
}
</script>

<style lang="scss" scoped>
// 列表项样式已统一迁移到 AuthLayout 的 .auth-list-item / .auth-list-title
.benefits {
  margin-top: 30px;
}
</style>
