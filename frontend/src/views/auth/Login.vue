<template>
  <AuthLayout
    accent-color="#409EFF"
    accent-rgb="64, 158, 255"
    secondary-color="#00D4AA"
    secondary-rgb="0, 212, 170"
    container-height="580px"
  >
    <template #brand-subtitle>基于AI的智能创意生成平台</template>

    <template #left-content>
      <div class="features">
        <div class="auth-list-item">
          <div class="auth-list-icon">
            <el-icon :size="22"><VideoCamera /></el-icon>
          </div>
          <span>短视频脚本生成</span>
        </div>
        <div class="auth-list-item">
          <div class="auth-list-icon">
            <el-icon :size="22"><Document /></el-icon>
          </div>
          <span>剧本大纲创作</span>
        </div>
        <div class="auth-list-item">
          <div class="auth-list-icon">
            <el-icon :size="22"><Notebook /></el-icon>
          </div>
          <span>小说大纲生成</span>
        </div>
        <div class="auth-list-item">
          <div class="auth-list-icon">
            <el-icon :size="22"><Picture /></el-icon>
          </div>
          <span>平面广告设计</span>
        </div>
        <div class="auth-list-item">
          <div class="auth-list-icon">
            <el-icon :size="22"><Film /></el-icon>
          </div>
          <span>TVC广告脚本</span>
        </div>
      </div>
    </template>

    <template #form-title>欢迎登录</template>
    <template #form-subtitle>登录您的账户开始创作</template>

    <template #form-content>
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
            maxlength="50"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
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
            <span v-if="!loading">登录</span>
            <span v-else>登录中...</span>
          </el-button>
        </el-form-item>
      </el-form>
    </template>

    <template #footer>
      <span>还没有账户？</span>
      <router-link to="/register">立即注册</router-link>
    </template>
  </AuthLayout>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock, VideoCamera, Document, Notebook, Picture, Film } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import AuthLayout from './AuthLayout.vue'

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
  // 防重复提交：如果正在加载中，直接返回
  if (loading.value) {
    console.warn('[Login] 登录请求进行中，忽略重复提交')
    return
  }
  
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login(form)
    ElMessage.success('登录成功')

    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (error) {
    console.error('登录失败:', error)
    ElMessage.error(error.response?.data?.message || '登录失败，请检查用户名和密码')
  } finally {
    // 添加300ms冷却期，防止快速重试
    setTimeout(() => {
      loading.value = false
    }, 300)
  }
}
</script>

<style lang="scss" scoped>
// 列表项样式已统一迁移到 AuthLayout 的 .auth-list-item
.features {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
