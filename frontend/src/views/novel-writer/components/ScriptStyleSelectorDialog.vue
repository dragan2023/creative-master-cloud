<!--
  剧本风格选择器对话框

  功能：
  1. 支持剧集(series_script)和电影(movie_script)两种类型的多维风格选择
  2. 每个维度（视觉风格、叙事节奏、对白风格等）独立选择子风格
  3. 调整风格强度

  创建时间: 2026-05-08
  版本: 1.0.0
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="750px"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="script-style-selector">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <template #title>
          {{ contentType === 'movie_script' ? '电影剧本' : '连续剧剧本' }}多维风格选择 — 从多个艺术维度定义创作风格
        </template>
      </el-alert>

      <!-- 维度选择 -->
      <div class="dimension-list">
        <div
          v-for="dim in availableDimensions"
          :key="dim.key"
          class="dimension-card"
        >
          <div class="dim-header">
            <span class="dim-icon">{{ dim.icon }}</span>
            <span class="dim-name">{{ dim.label }}</span>
            <span class="dim-desc">{{ dim.description }}</span>
          </div>

          <div class="dim-options">
            <el-checkbox-group
              :model-value="getDimSelectedValues(dim.key)"
              @update:model-value="(vals) => onDimChange(dim.key, vals)"
              :max="1"
            >
              <el-checkbox
                v-for="opt in dim.options"
                :key="opt.value"
                :value="opt.value"
                :label="opt.label"
                border
                size="small"
                class="dim-checkbox"
              />
            </el-checkbox-group>
          </div>
        </div>
      </div>

      <!-- 已选风格汇总 -->
      <div class="selected-summary" v-if="hasSelection">
        <div class="summary-header">
          <span>已选风格维度 ({{ selectedCount }})</span>
          <el-button size="small" text type="danger" @click="clearAll">清空全部</el-button>
        </div>
        <div class="summary-tags">
          <el-tag
            v-for="(item, idx) in selectedItems"
            :key="idx"
            closable
            type="primary"
            size="small"
            @close="onDimChange(item.dimKey, [])"
            style="margin-right: 6px; margin-bottom: 6px;"
          >
            {{ item.dimLabel }}: {{ item.styleLabel }}
          </el-tag>
        </div>
      </div>

      <!-- 强度滑块 -->
      <div class="intensity-section" v-if="hasSelection">
        <div class="intensity-label">
          <span>风格强度:</span>
          <span class="intensity-value">{{ Math.round(localIntensity * 100) }}%</span>
        </div>
        <el-slider
          v-model="intensityPercent"
          :min="20"
          :max="100"
          :step="5"
          :marks="intensityMarks"
        />
        <div class="intensity-hint">
          <span v-if="intensityPercent <= 40">淡入 - 风格特征轻微体现</span>
          <span v-else-if="intensityPercent <= 70">适中 - 风格特征明显但不突兀</span>
          <span v-else>强烈 - 风格特征非常突出</span>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button
        type="primary"
        @click="confirmSelection"
        :disabled="!hasSelection"
      >
        确认选择
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: { type: Boolean, default: false },
  contentType: { type: String, default: 'series_script' },  // 'series_script' | 'movie_script'
  initialDimensions: { type: Object, default: () => ({}) },
  initialIntensity: { type: Number, default: 0.7 }
})

const emit = defineEmits(['update:visible', 'confirm'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const dialogTitle = computed(() => {
  return props.contentType === 'movie_script' ? '电影风格选择器' : '剧集风格选择器'
})

const localIntensity = ref(props.initialIntensity)
const intensityPercent = computed({
  get: () => Math.round(localIntensity.value * 100),
  set: (val) => { localIntensity.value = val / 100 }
})

const intensityMarks = {
  20: '20%',
  50: '50%',
  80: '80%',
  100: '100%'
}

// 当前选择的维度映射: { dimKey: [selectedValues] }
const selectedDimValues = ref({})

// 可用维度定义（根据内容类型）
const availableDimensions = computed(() => {
  if (props.contentType === 'movie_script') {
    return [
      {
        key: 'visual_style',
        label: '视觉风格',
        icon: '🎬',
        description: '镜头语言与画面美学',
        options: [
          { value: '现实主义', label: '现实主义' },
          { value: '诗意写实', label: '诗意写实' },
          { value: '魔幻现实', label: '魔幻现实' },
          { value: '表现主义', label: '表现主义' },
          { value: '黑色电影', label: '黑色电影' },
          { value: '新浪潮', label: '新浪潮' },
        ]
      },
      {
        key: 'narrative_rhythm',
        label: '叙事节奏',
        icon: '⏱️',
        description: '情节推进的速度与张力',
        options: [
          { value: '快节奏', label: '快节奏' },
          { value: '中速叙事', label: '中速叙事' },
          { value: '慢节奏沉浸', label: '慢节奏沉浸' },
          { value: '起伏交错', label: '起伏交错' },
        ]
      },
      {
        key: 'dialogue_style',
        label: '对白风格',
        icon: '💬',
        description: '角色对话的语言特点',
        options: [
          { value: '生活化', label: '生活化' },
          { value: '文学化', label: '文学化' },
          { value: '简约主义', label: '简约主义' },
          { value: '诗意化', label: '诗意化' },
          { value: '幽默诙谐', label: '幽默诙谐' },
        ]
      },
      {
        key: 'emotional_tone',
        label: '情感基调',
        icon: '🎭',
        description: '整体情感氛围',
        options: [
          { value: '温暖治愈', label: '温暖治愈' },
          { value: '冷峻克制', label: '冷峻克制' },
          { value: '悲壮史诗', label: '悲壮史诗' },
          { value: '悬疑紧张', label: '悬疑紧张' },
          { value: '浪漫抒情', label: '浪漫抒情' },
        ]
      },
      {
        key: 'structural_style',
        label: '结构风格',
        icon: '🏗️',
        description: '剧本结构设计方式',
        options: [
          { value: '线性叙事', label: '线性叙事' },
          { value: '非线性', label: '非线性' },
          { value: '多线并行', label: '多线并行' },
          { value: '环形结构', label: '环形结构' },
          { value: '碎片化', label: '碎片化' },
        ]
      },
    ]
  }
  // series_script 维度
  return [
    {
      key: 'visual_style',
      label: '视觉风格',
      icon: '🎬',
      description: '镜头语言与画面美学',
      options: [
        { value: '现实主义', label: '现实主义' },
        { value: '诗意写实', label: '诗意写实' },
        { value: '魔幻现实', label: '魔幻现实' },
        { value: '表现主义', label: '表现主义' },
        { value: '黑色电影', label: '黑色电影' },
        { value: '新浪潮', label: '新浪潮' },
      ]
    },
    {
      key: 'narrative_rhythm',
      label: '叙事节奏',
      icon: '⏱️',
      description: '情节推进的速度与张力',
      options: [
        { value: '快节奏', label: '快节奏' },
        { value: '中速叙事', label: '中速叙事' },
        { value: '慢节奏沉浸', label: '慢节奏沉浸' },
        { value: '张弛有度', label: '张弛有度' },
        { value: '季播节奏', label: '季播节奏' },
      ]
    },
    {
      key: 'dialogue_style',
      label: '对白风格',
      icon: '💬',
      description: '角色对话的语言特点',
      options: [
        { value: '生活化', label: '生活化' },
        { value: '文学化', label: '文学化' },
        { value: '简约主义', label: '简约主义' },
        { value: '诗意化', label: '诗意化' },
        { value: '幽默诙谐', label: '幽默诙谐' },
      ]
    },
    {
      key: 'emotional_tone',
      label: '情感基调',
      icon: '🎭',
      description: '整体情感氛围',
      options: [
        { value: '温暖治愈', label: '温暖治愈' },
        { value: '冷峻克制', label: '冷峻克制' },
        { value: '悲壮史诗', label: '悲壮史诗' },
        { value: '悬疑紧张', label: '悬疑紧张' },
        { value: '浪漫抒情', label: '浪漫抒情' },
      ]
    },
    {
      key: 'episode_structure',
      label: '集间结构',
      icon: '📺',
      description: '连续剧特有的集间组织方式',
      options: [
        { value: '连续剧', label: '连续剧' },
        { value: '单元剧', label: '单元剧' },
        { value: '混合型', label: '混合型' },
        { value: '回环式', label: '回环式' },
      ]
    },
  ]
})

function getDimSelectedValues(dimKey) {
  return selectedDimValues.value[dimKey] || []
}

function onDimChange(dimKey, values) {
  selectedDimValues.value = {
    ...selectedDimValues.value,
    [dimKey]: values
  }
}

const selectedItems = computed(() => {
  const items = []
  for (const dim of availableDimensions.value) {
    const vals = selectedDimValues.value[dim.key]
    if (vals && vals.length > 0) {
      items.push({
        dimKey: dim.key,
        dimLabel: dim.label,
        styleLabel: vals[0]
      })
    }
  }
  return items
})

const selectedCount = computed(() => selectedItems.value.length)

const hasSelection = computed(() => selectedCount.value > 0)

function clearAll() {
  selectedDimValues.value = {}
}

function confirmSelection() {
  // 构建与 useStyleManagement.handleScriptStyleConfirm 兼容的数据结构
  const dimensions = {}
  const selectedNames = []
  for (const item of selectedItems.value) {
    dimensions[item.dimLabel] = [{ name: item.styleLabel }]
    selectedNames.push(`${item.dimLabel}:${item.styleLabel}`)
  }

  emit('confirm', {
    styleType: props.contentType === 'movie_script' ? 'movie' : 'series',
    seriesSubType: 'long',  // 默认长剧
    dimensions,
    selectedNames,
    intensity: localIntensity.value
  })

  ElMessage.success(`已选择 ${selectedNames.length} 个维度的剧本风格`)
  dialogVisible.value = false
}

// 从 initialDimensions 恢复之前的选择
watch(() => props.visible, (val) => {
  if (val) {
    localIntensity.value = props.initialIntensity

    // 恢复之前的选择
    if (props.initialDimensions && Object.keys(props.initialDimensions).length > 0 && Object.keys(selectedDimValues.value).length === 0) {
      const restored = {}
      for (const dim of availableDimensions.value) {
        const existing = props.initialDimensions[dim.label]
        if (existing && existing.length > 0) {
          const name = existing[0]?.name || String(existing[0] || '')
          // 匹配维度中的选项
          const matched = dim.options.find(o => o.value === name)
          if (matched) {
            restored[dim.key] = [matched.value]
          }
        }
      }
      selectedDimValues.value = restored
    }
  }
})
</script>

<style lang="scss">
.script-style-selector {
  .dimension-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-height: 440px;
    overflow-y: auto;
    padding: 4px;
  }

  .dimension-card {
    padding: 12px 14px;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    background: #fafbfc;
    transition: border-color 0.2s;

    &:hover {
      border-color: #a0cfff;
    }

    .dim-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;

      .dim-icon {
        font-size: 18px;
      }

      .dim-name {
        font-size: 14px;
        font-weight: 600;
        color: #303133;
        min-width: 70px;
      }

      .dim-desc {
        font-size: 12px;
        color: #909399;
      }
    }

    .dim-options {
      .dim-checkbox {
        margin-right: 8px !important;
        margin-bottom: 4px !important;
      }
    }
  }

  .selected-summary {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid #e4e7ed;

    .summary-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 500;
      color: #303133;
    }

    .summary-tags {
      display: flex;
      flex-wrap: wrap;
    }
  }

  .intensity-section {
    margin-top: 16px;
    padding: 14px;
    background: #fafafa;
    border-radius: 8px;

    .intensity-label {
      display: flex;
      justify-content: space-between;
      margin-bottom: 4px;
      font-size: 13px;
      color: #303133;

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
</style>
