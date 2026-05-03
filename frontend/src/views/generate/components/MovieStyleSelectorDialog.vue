<!--
  电影风格选择器对话框
  功能：
  1. 六大维度电影风格选择（风格流派/导演风格/叙事风格/剪辑流派/表演风格/台词风格）
  2. 每个维度限选1项，可跨维度选择
  3. 调整风格强度
  4. 静态数据源（movieStyles.js）

  创建时间: 2026-05-03
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="选择电影风格"
    width="860px"
    destroy-on-close
    :close-on-click-modal="false"
    class="movie-style-dialog"
  >
    <div class="movie-style-selector">
      <!-- 维度标签（左侧） -->
      <div class="dimension-sidebar">
        <div
          v-for="dim in dimensions"
          :key="dim.id"
          class="dimension-tab"
          :class="{
            active: activeDimension === dim.id,
            'has-selection': selectedByDimension[dim.id] !== null
          }"
          @click="activeDimension = dim.id"
        >
          <span class="dim-name">{{ dim.name }}</span>
          <span class="dim-count">{{ dim.styles.length }}</span>
          <el-icon v-if="selectedByDimension[dim.id]" class="dim-check"><CircleCheckFilled /></el-icon>
        </div>
      </div>

      <!-- 右侧内容区 -->
      <div class="dimension-content">
        <div class="content-header">
          <h4 class="dim-title">{{ currentDimension?.name }}</h4>
          <p class="dim-desc">{{ currentDimension?.description }}</p>
        </div>

        <!-- 风格卡片网格 -->
        <div class="style-grid">
          <div
            v-for="style in currentDimensionStyles"
            :key="style.id"
            class="style-card"
            :class="{ selected: isSelectedInDimension(activeDimension, style.id) }"
            @click="toggleStyleInDimension(activeDimension, style)"
          >
            <div class="style-badge" v-if="isSelectedInDimension(activeDimension, style.id)">
              <el-icon><Check /></el-icon>
            </div>
            <h5 class="style-name">{{ style.name }}</h5>
            <p class="style-desc">{{ style.description }}</p>
            <div class="style-meta" v-if="style.examples && style.examples.length">
              <span class="meta-label">代表:</span>
              <span class="meta-value">{{ style.examples.slice(0, 2).join('、') }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 已选风格汇总 -->
    <div class="selected-summary" v-if="selectedCount > 0">
      <div class="summary-header">
        <span>已选电影风格 ({{ selectedCount }}/{{ dimensions.length }} 维度)</span>
        <el-button size="small" text type="danger" @click="clearAll">清空全部</el-button>
      </div>
      <div class="summary-tags">
        <template v-for="dim in dimensions" :key="dim.id">
          <el-tag
            v-if="selectedByDimension[dim.id]"
            closable
            type="primary"
            size="small"
            @close="clearDimension(dim.id)"
          >
            <span class="tag-dim">{{ dim.name }}:</span>
            <span class="tag-name">{{ selectedByDimension[dim.id].name }}</span>
          </el-tag>
        </template>
      </div>
    </div>

    <!-- 强度滑块 -->
    <div class="intensity-section" v-if="selectedCount > 0">
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
        <span v-if="intensityPercent <= 40">淡入 - 风格特征轻微体现</span>
        <span v-else-if="intensityPercent <= 70">适中 - 风格特征明显但不突兀</span>
        <span v-else>强烈 - 风格特征非常突出</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button
        type="primary"
        @click="confirmSelection"
        :disabled="selectedCount === 0"
      >
        确认选择
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, CircleCheckFilled } from '@element-plus/icons-vue'
import { movieStyleDimensions, getMovieStylesByDimension } from '../composables/movieStyles'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialSelected: { type: Object, default: () => ({}) },
  initialIntensity: { type: Number, default: 0.7 }
})

const emit = defineEmits(['update:visible', 'confirm'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const dimensions = movieStyleDimensions
const activeDimension = ref(dimensions[0]?.id || '')

// 每个维度的选择：{ [dimensionId]: styleObject | null }
const selectedByDimension = reactive({})
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

const currentDimension = computed(() => {
  return dimensions.find(d => d.id === activeDimension.value)
})

const currentDimensionStyles = computed(() => {
  return getMovieStylesByDimension(activeDimension.value)
})

const selectedCount = computed(() => {
  return Object.values(selectedByDimension).filter(v => v !== null && v !== undefined).length
})

function isSelectedInDimension(dimId, styleId) {
  const selected = selectedByDimension[dimId]
  return selected && selected.id === styleId
}

function toggleStyleInDimension(dimId, style) {
  if (isSelectedInDimension(dimId, style.id)) {
    // 取消选择
    selectedByDimension[dimId] = null
  } else {
    // 选中（同一维度内替换）
    selectedByDimension[dimId] = { ...style }
  }
}

function clearDimension(dimId) {
  selectedByDimension[dimId] = null
}

function clearAll() {
  dimensions.forEach(d => {
    selectedByDimension[d.id] = null
  })
}

function confirmSelection() {
  if (selectedCount.value === 0) return

  // 构建选择结果
  const selectedDimensions = {}
  const selectedNames = []

  dimensions.forEach(d => {
    const selected = selectedByDimension[d.id]
    if (selected) {
      selectedDimensions[d.name] = [{
        id: selected.id,
        name: selected.name,
        description: selected.description,
        examples: selected.examples
      }]
      selectedNames.push(selected.name)
    }
  })

  const result = {
    styleType: 'movie',
    dimensions: selectedDimensions,
    selectedNames,
    intensity: intensity.value
  }

  emit('confirm', result)
  ElMessage.success(`已选择 ${selectedCount.value} 个维度的电影风格: ${selectedNames.join('、')}`)
  dialogVisible.value = false
}

// 对话框打开时恢复之前的选择
watch(() => props.visible, (val) => {
  if (val) {
    intensity.value = props.initialIntensity
    // 默认选中第一个维度
    if (!activeDimension.value) {
      activeDimension.value = dimensions[0]?.id || ''
    }
    // 恢复之前的选择
    if (props.initialSelected && props.initialSelected.dimensions) {
      const dims = props.initialSelected.dimensions
      Object.keys(selectedByDimension).forEach(k => {
        selectedByDimension[k] = null
      })
      for (const [dimName, styles] of Object.entries(dims)) {
        const dim = dimensions.find(d => d.name === dimName)
        if (dim && styles && styles.length > 0) {
          selectedByDimension[dim.id] = styles[0]
        }
      }
    }
    if (props.initialIntensity) {
      intensity.value = props.initialIntensity
    }
  }
})
</script>

<style lang="scss">
.movie-style-dialog {
  .movie-style-selector {
    display: flex;
    gap: 16px;
    min-height: 420px;
    max-height: 55vh;
  }

  .dimension-sidebar {
    width: 150px;
    flex-shrink: 0;
    border-right: 1px solid #e4e7ed;
    padding-right: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 420px;
    overflow-y: auto;
  }

  .dimension-tab {
    display: flex;
    align-items: center;
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.25s ease;
    font-size: 13px;
    position: relative;
    color: #606266;

    &:hover {
      background: #f0f5ff;
      color: #409eff;
    }

    &.active {
      background: #ecf5ff;
      color: #409eff;
      font-weight: 600;
      box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
    }

    &.has-selection {
      .dim-check {
        color: #67c23a;
      }
    }

    .dim-name {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .dim-count {
      font-size: 11px;
      color: #909399;
      margin-left: 6px;
    }

    .dim-check {
      margin-left: 4px;
      font-size: 14px;
    }
  }

  .dimension-content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .content-header {
    margin-bottom: 12px;

    .dim-title {
      margin: 0 0 4px;
      font-size: 15px;
      font-weight: 600;
      color: #303133;
    }

    .dim-desc {
      margin: 0;
      font-size: 12px;
      color: #909399;
    }
  }

  .style-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 10px;
    max-height: 400px;
    overflow-y: auto;
    padding: 2px;

    &::-webkit-scrollbar {
      width: 6px;
    }
    &::-webkit-scrollbar-track {
      background: transparent;
    }
    &::-webkit-scrollbar-thumb {
      background: #c0c4cc;
      border-radius: 3px;
      &:hover {
        background: #909399;
      }
    }
  }

  .style-card {
    padding: 16px 12px;
    border: 2px solid #e4e7ed;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: center;

    &:hover {
      border-color: #409eff;
      box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
      transform: translateY(-2px) scale(1.01);
    }

    &:active {
      transform: translateY(0) scale(0.98);
      transition-duration: 0.1s;
    }

    &.selected {
      border-color: #409eff;
      background: #ecf5ff;
      box-shadow: 0 2px 10px rgba(64, 158, 255, 0.2);
      animation: movieSelectPulse 0.4s ease;
    }

    .style-badge {
      position: absolute;
      top: 4px;
      right: 4px;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #409eff;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      box-shadow: 0 2px 6px rgba(64, 158, 255, 0.35);
      animation: movieBadgePop 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }

    .style-name {
      margin: 0 0 4px;
      font-size: 14px;
      font-weight: 600;
      padding-right: 24px;
    }

    .style-desc {
      margin: 0 0 6px;
      font-size: 12px;
      color: #606266;
      line-height: 1.6;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .style-meta {
      font-size: 11px;
      color: #909399;

      .meta-label {
        margin-right: 2px;
      }

      .meta-value {
        color: #606266;
      }
    }
  }

  .selected-summary {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid #e4e7ed;

    .summary-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 500;
    }

    .summary-tags {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;

      .tag-dim {
        font-weight: 500;
        margin-right: 2px;
      }

      .tag-name {
        font-weight: 400;
      }
    }
  }

  .intensity-section {
    margin-top: 14px;
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

@keyframes movieSelectPulse {
  0% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(64, 158, 255, 0); }
  100% { box-shadow: 0 2px 10px rgba(64, 158, 255, 0.2); }
}

@keyframes movieBadgePop {
  0% { transform: scale(0); opacity: 0; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
</style>
