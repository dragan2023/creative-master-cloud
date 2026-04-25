<!--
  文风选择器对话框
  功能：
  1. 从文风知识库中选择1-3种文风
  2. 调整风格强度
  3. 调用后端API融合文风并返回风格指南

  创建时间: 2026-04-11
  版本: 1.1.0 (61种文风)
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="选择写作文风"
    width="800px"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="style-selector">
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <el-skeleton :rows="5" animated />
      </div>

      <template v-else>
        <!-- 分类标签 -->
        <div class="category-tabs">
          <el-radio-group v-model="activeCategory" size="small">
            <el-radio-button
              v-for="cat in categories"
              :key="cat.id"
              :value="cat.id"
            >
              {{ cat.name }} ({{ cat.count }})
            </el-radio-button>
          </el-radio-group>
        </div>

        <!-- 文风卡片网格 -->
        <div class="style-grid">
          <div
            v-for="style in currentStyles"
            :key="style.id"
            class="style-card"
            :class="{
              selected: isSelected(style.id),
              'primary-style': getStyleIndex(style.id) === 0,
              'secondary-style': getStyleIndex(style.id) > 0
            }"
            @click="toggleStyle(style)"
          >
            <div class="style-badge" v-if="getStyleIndex(style.id) >= 0">
              {{ getStyleIndex(style.id) === 0 ? '主风格' : `辅风格${getStyleIndex(style.id)}` }}
            </div>
            <h5 class="style-name">{{ style.name }}</h5>
            <p class="style-desc">{{ style.description }}</p>
            <div class="style-meta" v-if="style.examples && style.examples.length">
              <span class="meta-label">代表:</span>
              <span class="meta-value">{{ style.examples.slice(0, 2).join('、') }}</span>
            </div>
          </div>
        </div>

        <!-- 已选文风 -->
        <div class="selected-section" v-if="selectedStyles.length > 0">
          <div class="selected-header">
            <span>已选文风 ({{ selectedStyles.length }}/3)</span>
            <el-button size="small" text type="danger" @click="clearAll">清空</el-button>
          </div>
          <div class="selected-tags">
            <el-tag
              v-for="(style, idx) in selectedStyles"
              :key="style.id"
              closable
              :type="idx === 0 ? '' : 'warning'"
              @close="removeStyle(idx)"
            >
              {{ idx === 0 ? '主' : '辅' }}: {{ style.name }}
            </el-tag>
          </div>
        </div>

        <!-- 强度滑块 -->
        <div class="intensity-section" v-if="selectedStyles.length > 0">
          <div class="intensity-label">
            <span>风格强度:</span>
            <span class="intensity-value">{{ Math.round(intensity * 100) }}%</span>
          </div>
          <el-slider
            v-model="intensityPercent"
            :min="20"
            :max="100"
            :step="5"
            :marks="intensityMarks"
          />
          <div class="intensity-hint">
            <span v-if="intensityPercent <= 40">淡入 - 文风特征轻微体现</span>
            <span v-else-if="intensityPercent <= 70">适中 - 文风特征明显但不突兀</span>
            <span v-else>强烈 - 文风特征非常突出</span>
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button
        type="primary"
        @click="confirmSelection"
        :loading="blending"
        :disabled="selectedStyles.length === 0"
      >
        确认选择
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialStyleIds: { type: Array, default: () => [] },
  initialIntensity: { type: Number, default: 0.7 }
})

const emit = defineEmits(['update:visible', 'confirm'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const loading = ref(false)
const blending = ref(false)
const categories = ref([])
const allStyles = ref({})
const activeCategory = ref('')
const selectedStyles = ref([])
const intensity = ref(props.initialIntensity)
const intensityPercent = computed({
  get: () => Math.round(intensity.value * 100),
  set: (val) => { intensity.value = val / 100 }
})

const intensityMarks = {
  20: '20%',
  50: '50%',
  70: '70%',
  100: '100%'
}

const currentStyles = computed(() => {
  return allStyles.value[activeCategory.value] || []
})

// 加载文风库
async function loadStyleLibrary() {
  loading.value = true
  try {
    const res = await novelWriterApi.getStyleLibrary()
    const data = res.data?.data || res.data

    if (data) {
      // 处理分类信息
      if (data.categories) {
        categories.value = Object.entries(data.categories).map(([id, cat]) => ({
          id,
          name: cat.name,
          description: cat.description,
          count: cat.count
        }))
        if (categories.value.length > 0 && !activeCategory.value) {
          activeCategory.value = categories.value[0].id
        }
      }

      // 处理文风列表（按分类组织）
      if (data.styles && Array.isArray(data.styles)) {
        const grouped = {}
        for (const style of data.styles) {
          const catId = style.category || 'other'
          if (!grouped[catId]) grouped[catId] = []
          grouped[catId].push(style)
        }
        allStyles.value = grouped
      }

      console.log('[StyleSelector] 加载成功:', {
        categories: categories.value.length,
        totalStyles: Object.values(allStyles.value).flat().length
      })
    }
  } catch (e) {
    console.error('[StyleSelector] 加载文风库异常:', e)
    ElMessage.error('加载文风库失败')
  } finally {
    loading.value = false
  }
}

function isSelected(styleId) {
  return selectedStyles.value.some(s => s.id === styleId)
}

function getStyleIndex(styleId) {
  return selectedStyles.value.findIndex(s => s.id === styleId)
}

function toggleStyle(style) {
  const idx = getStyleIndex(style.id)
  if (idx >= 0) {
    selectedStyles.value.splice(idx, 1)
  } else {
    if (selectedStyles.value.length >= 3) {
      ElMessage.warning('最多选择3种文风')
      return
    }
    selectedStyles.value.push(style)
  }
}

function removeStyle(idx) {
  selectedStyles.value.splice(idx, 1)
}

function clearAll() {
  selectedStyles.value = []
}

// 确认选择 - 调用后端融合API
async function confirmSelection() {
  if (selectedStyles.value.length === 0) return

  blending.value = true
  try {
    const styleIds = selectedStyles.value.map(s => s.id)
    const styleNames = selectedStyles.value.map(s => s.name)

    // 调用融合API
    const res = await novelWriterApi.blendStyles(styleIds, intensity.value)
    const data = res.data?.data || res.data

    const styleGuide = data?.style_guide || data?.guide || data || {}

    emit('confirm', {
      styleIds,
      styleNames,
      intensity: intensity.value,
      styleGuide
    })

    ElMessage.success(`已选择 ${styleNames.length} 种文风: ${styleNames.join(' + ')}`)
    dialogVisible.value = false
  } catch (e) {
    console.error('[StyleSelector] 融合文风失败:', e)
    // 即使融合失败，也返回基本选择信息
    const styleIds = selectedStyles.value.map(s => s.id)
    const styleNames = selectedStyles.value.map(s => s.name)
    emit('confirm', {
      styleIds,
      styleNames,
      intensity: intensity.value,
      styleGuide: null
    })
    ElMessage.warning('文风融合服务暂时不可用，已记录您的选择')
    dialogVisible.value = false
  } finally {
    blending.value = false
  }
}

// 初始化已选文风
watch(() => props.visible, (val) => {
  if (val) {
    if (categories.value.length === 0) {
      loadStyleLibrary()
    }
    // 恢复之前的选择
    intensity.value = props.initialIntensity
    if (props.initialStyleIds.length > 0 && selectedStyles.value.length === 0) {
      // 从allStyles中查找对应的文风
      const all = Object.values(allStyles.value).flat()
      selectedStyles.value = props.initialStyleIds
        .map(id => all.find(s => s.id === id))
        .filter(Boolean)
    }
  }
})
</script>

<style lang="scss">
/* 非scoped：el-dialog会teleport内容到body，scoped样式会失效 */
.style-selector {
  .loading-state {
    padding: 40px 0;
  }

  .category-tabs {
    margin-bottom: 16px;
    overflow-x: auto;
  }

  .style-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
    max-height: 400px;
    overflow-y: auto;
    padding: 4px;
  }

  .style-card {
    padding: 12px;
    border: 2px solid #e4e7ed;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;

    &::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: radial-gradient(circle at center, rgba(64, 158, 255, 0.1) 0%, transparent 70%);
      opacity: 0;
      transition: opacity 0.3s;
      pointer-events: none;
    }

    &:hover {
      border-color: #409eff;
      box-shadow: 0 6px 20px rgba(64, 158, 255, 0.25);
      transform: translateY(-3px) scale(1.02);

      &::after { opacity: 1; }
    }

    &:active {
      transform: translateY(0) scale(0.97);
      transition-duration: 0.1s;
    }

    &.selected {
      border-color: #409eff;
      background: #ecf5ff;
      box-shadow: 0 2px 12px rgba(64, 158, 255, 0.25);
      animation: selectPulse 0.5s ease;
    }

    &.primary-style {
      border-color: #409eff;
      background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
      box-shadow: 0 2px 12px rgba(64, 158, 255, 0.3);
    }

    &.secondary-style {
      border-color: #e6a23c;
      background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
      box-shadow: 0 2px 12px rgba(230, 162, 60, 0.25);
    }

    .style-badge {
      position: absolute;
      top: 4px;
      right: 4px;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 10px;
      background: #409eff;
      color: #fff;
      font-weight: 600;
      box-shadow: 0 2px 6px rgba(64, 158, 255, 0.4);
      animation: badgePop 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }

    &.secondary-style .style-badge {
      background: #e6a23c;
    }

    .style-name {
      margin: 0 0 4px;
      font-size: 14px;
      font-weight: 600;
    }

    .style-desc {
      margin: 0 0 6px;
      font-size: 12px;
      color: #606266;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .style-meta {
      font-size: 11px;
      color: #909399;

      .meta-label { margin-right: 2px; }
    }
  }

  .selected-section {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid #e4e7ed;

    .selected-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 500;
    }

    .selected-tags {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
  }

  .intensity-section {
    margin-top: 16px;
    padding: 12px;
    background: #fafafa;
    border-radius: 6px;

    .intensity-label {
      display: flex;
      justify-content: space-between;
      margin-bottom: 4px;
      font-size: 13px;

      .intensity-value {
        font-weight: 600;
        color: #409eff;
      }
    }

    .intensity-hint {
      margin-top: 4px;
      font-size: 12px;
      color: #909399;
      text-align: center;
    }
  }
}

@keyframes selectPulse {
  0% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(64, 158, 255, 0); }
  100% { box-shadow: 0 2px 12px rgba(64, 158, 255, 0.25); }
}

@keyframes badgePop {
  0% { transform: scale(0); opacity: 0; }
  50% { transform: scale(1.4); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}

@keyframes cardGlow {
  0% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.3); }
  100% { box-shadow: 0 0 12px 2px rgba(64, 158, 255, 0.15); }
}
</style>
