<!--
  剧集风格选择器对话框
  功能：
  1. 支持长篇电视剧 / 网络短剧两种类型
  2. 每种类型包含多个维度（风格流派/导演风格/叙事风格/镜头剪辑风格/演绎风格）
  3. 每个维度限选1项，可跨维度选择
  4. 调整风格强度
  5. 静态数据源（seriesStyles.js）

  创建时间: 2026-05-03
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="选择剧集风格"
    width="880px"
    destroy-on-close
    :close-on-click-modal="false"
    class="series-style-dialog"
  >
    <div class="series-style-selector">
      <!-- 类型切换 -->
      <div class="series-type-toggle">
        <el-radio-group v-model="seriesType" size="default" @change="onTypeChange">
          <el-radio-button
            v-for="opt in seriesTypeOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <div class="selector-body">
        <!-- 维度标签（左侧） -->
        <div class="dimension-sidebar">
          <div
            v-for="dim in currentDimensions"
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
            <h4 class="dim-title">{{ activeDimInfo?.name }}</h4>
            <p class="dim-desc">{{ activeDimInfo?.description }}</p>
          </div>

          <!-- 搜索框 -->
          <el-input
            v-model="searchKeyword"
            placeholder="搜索风格..."
            size="small"
            clearable
            class="search-input"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>

          <!-- 风格卡片网格 -->
          <div class="style-grid">
            <div
              v-for="style in filteredStyles"
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

            <!-- 空状态 -->
            <div v-if="filteredStyles.length === 0" class="empty-state">
              <el-empty description="未找到匹配的风格" :image-size="60" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 已选风格汇总 -->
    <div class="selected-summary" v-if="selectedCount > 0">
      <div class="summary-header">
        <span>已选剧集风格 ({{ selectedCount }}/{{ currentDimensions.length }} 维度)</span>
        <el-button size="small" text type="danger" @click="clearAll">清空全部</el-button>
      </div>
      <div class="summary-tags">
        <template v-for="dim in currentDimensions" :key="dim.id">
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
import { Check, CircleCheckFilled, Search } from '@element-plus/icons-vue'
import {
  longSeriesDimensions,
  shortSeriesDimensions,
  getSeriesDimensionsByType,
  seriesTypeOptions
} from '../composables/seriesStyles'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialSelected: { type: Object, default: () => ({}) },
  initialIntensity: { type: Number, default: 0.7 },
  initialType: { type: String, default: 'long' }  // 'long' | 'short'
})

const emit = defineEmits(['update:visible', 'confirm'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const seriesType = ref(props.initialType || 'long')
const searchKeyword = ref('')

const allDimensionsMap = {
  long: longSeriesDimensions,
  short: shortSeriesDimensions
}

const currentDimensions = computed(() => {
  return getSeriesDimensionsByType(seriesType.value)
})

const activeDimension = ref('')

// 每个维度的选择：{ [dimensionId]: styleObject | null }
const selectedByDimension = reactive({})
// 按类型存储选择（切换类型时保留）
const savedSelections = reactive({
  long: {},
  short: {}
})

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

const activeDimInfo = computed(() => {
  return currentDimensions.value.find(d => d.id === activeDimension.value)
})

const filteredStyles = computed(() => {
  if (!activeDimension.value) return []
  const dim = currentDimensions.value.find(d => d.id === activeDimension.value)
  if (!dim) return []
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return dim.styles
  return dim.styles.filter(s =>
    s.name.toLowerCase().includes(keyword) ||
    s.description.toLowerCase().includes(keyword)
  )
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
    selectedByDimension[dimId] = null
  } else {
    selectedByDimension[dimId] = { ...style }
  }
}

function clearDimension(dimId) {
  selectedByDimension[dimId] = null
}

function clearAll() {
  currentDimensions.value.forEach(d => {
    selectedByDimension[d.id] = null
  })
}

// 类型切换时保存/恢复选择
function onTypeChange(newType) {
  // 保存当前选择
  const currentType = newType === 'long' ? 'short' : 'long'
  savedSelections[currentType] = { ...selectedByDimension }

  // 恢复新类型的选择
  const saved = savedSelections[newType]
  // 清空当前
  Object.keys(selectedByDimension).forEach(k => {
    selectedByDimension[k] = null
  })

  if (saved && Object.keys(saved).length > 0) {
    Object.assign(selectedByDimension, saved)
  }

  // 重置搜索和活跃维度
  searchKeyword.value = ''
  const dims = getSeriesDimensionsByType(newType)
  if (dims.length > 0) {
    activeDimension.value = dims[0].id
  }
}

function confirmSelection() {
  if (selectedCount.value === 0) return

  const selectedDimensions = {}
  const selectedNames = []

  currentDimensions.value.forEach(d => {
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
    styleType: 'series',
    seriesSubType: seriesType.value, // 'long' | 'short'
    dimensions: selectedDimensions,
    selectedNames,
    intensity: intensity.value
  }

  emit('confirm', result)
  ElMessage.success(`已选择 ${selectedCount.value} 个维度的剧集风格: ${selectedNames.join('、')}`)
  dialogVisible.value = false
}

// 对话框打开时恢复之前的选择
watch(() => props.visible, (val) => {
  if (val) {
    intensity.value = props.initialIntensity
    seriesType.value = props.initialType || 'long'

    // 初始化维度
    const dims = getSeriesDimensionsByType(seriesType.value)
    if (dims.length > 0) {
      activeDimension.value = dims[0].id
    }

    // 恢复之前的选择
    if (props.initialSelected && props.initialSelected.dimensions) {
      const dims = props.initialSelected.dimensions
      // 先清空
      Object.keys(selectedByDimension).forEach(k => {
        selectedByDimension[k] = null
      })
      const currentDims = getSeriesDimensionsByType(seriesType.value)
      for (const [dimName, styles] of Object.entries(dims)) {
        const dim = currentDims.find(d => d.name === dimName)
        if (dim && styles && styles.length > 0) {
          selectedByDimension[dim.id] = styles[0]
        }
      }
    }

    if (props.initialSelected && props.initialSelected.seriesSubType) {
      seriesType.value = props.initialSelected.seriesSubType
    }

    searchKeyword.value = ''
  }
})
</script>

<style lang="scss">
.series-style-dialog {
  .series-style-selector {
    min-height: 380px;
  }

  .series-type-toggle {
    margin-bottom: 14px;
    display: flex;
    justify-content: center;

    .el-radio-group {
      .el-radio-button__inner {
        padding: 8px 24px;
      }
    }
  }

  .selector-body {
    display: flex;
    gap: 16px;
    min-height: 380px;
    max-height: 48vh;
  }

  .dimension-sidebar {
    width: 150px;
    flex-shrink: 0;
    border-right: 1px solid #e4e7ed;
    padding-right: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 380px;
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
    margin-bottom: 10px;

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

  .search-input {
    margin-bottom: 10px;
  }

  .style-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 10px;
    max-height: 350px;
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
      animation: seriesSelectPulse 0.4s ease;
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
      animation: seriesBadgePop 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
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

  .empty-state {
    grid-column: 1 / -1;
    display: flex;
    justify-content: center;
    padding: 20px 0;
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

@keyframes seriesSelectPulse {
  0% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(64, 158, 255, 0); }
  100% { box-shadow: 0 2px 10px rgba(64, 158, 255, 0.2); }
}

@keyframes seriesBadgePop {
  0% { transform: scale(0); opacity: 0; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
</style>
