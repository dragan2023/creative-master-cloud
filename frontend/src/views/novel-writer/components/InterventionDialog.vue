<!--
  组件: InterventionDialog
  用户干预弹窗
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="用户干预"
    width="600px"
  >
    <div class="intervention-content">
      <!-- 提示信息 -->
      <div class="intervention-banner">
        <div class="banner-icon">
          <el-icon><WarningFilled /></el-icon>
        </div>
        <div class="banner-info">
          <div class="banner-message">{{ interventionData.message }}</div>
        </div>
      </div>

      <!-- 推断的概要内容 -->
      <div v-if="interventionData.inferred_summary" class="inferred-summary">
        <div class="summary-header">
          <el-icon><Reading /></el-icon>
          <span>系统推断的章节概要</span>
        </div>
        <div class="summary-content">
          {{ interventionData.inferred_summary }}
        </div>
      </div>

      <!-- 用户选择 -->
      <div class="intervention-options">
        <div class="options-title">请选择处理方式</div>
        <div class="options-grid">
          <div
            v-for="option in interventionOptions"
            :key="option.value"
            class="option-card"
            :class="{ active: userChoice === option.value }"
            @click="$emit('update:userChoice', option.value)"
          >
            <div class="option-icon">
              <el-icon><component :is="resolveElementIcon(option.icon)" /></el-icon>
            </div>
            <div class="option-info">
              <div class="option-label">{{ option.label }}</div>
              <div class="option-desc">{{ option.desc }}</div>
            </div>
            <div v-if="userChoice === option.value" class="option-check">
              <el-icon><CircleCheckFilled /></el-icon>
            </div>
          </div>
        </div>
      </div>

      <!-- 用户输入概要内容 -->
      <div v-if="userChoice === 'provide'" class="user-guidance-input">
        <div class="input-label">
          <el-icon><Edit /></el-icon>
          <span>请输入章节概要内容</span>
        </div>
        <el-input
          :model-value="userGuidance"
          @update:model-value="$emit('update:userGuidance', $event)"
          type="textarea"
          :rows="4"
          placeholder="请输入本章概要内容，包括主要剧情、关键事件、人物发展等..."
        />
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('cancel')">取消</el-button>
      <el-button 
        type="primary" 
        @click="$emit('confirm')"
        :loading="loading"
        :disabled="!userChoice || (userChoice === 'provide' && !userGuidance.trim())"
      >
        确认
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { WarningFilled, Reading, CircleCheckFilled, Edit } from '@element-plus/icons-vue'
import { resolveElementIcon } from '@/utils/elementIcons'

defineProps({
  visible: { type: Boolean, default: false },
  interventionData: { type: Object, default: () => ({}) },
  interventionOptions: { type: Array, default: () => ([]) },
  loading: { type: Boolean, default: false },
  userChoice: { type: String, default: '' },
  userGuidance: { type: String, default: '' }
})

defineEmits(['update:visible', 'update:userChoice', 'update:userGuidance', 'confirm', 'cancel'])
</script>
