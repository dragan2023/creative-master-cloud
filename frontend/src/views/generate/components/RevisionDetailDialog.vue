<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    :title="dialogTitle"
    width="800px"
    top="5vh"
  >
    <div v-if="unitData" class="revision-detail-container">
      <!-- 修正信息 -->
      <div class="revision-info-header">
        <el-tag type="success">逻辑修正</el-tag>
        <span class="revision-stats">
          原文 <strong>{{ unitData.original_summary?.length || 0 }}</strong> 字 
          → 修正后 <strong>{{ unitData.revised_summary?.length || 0 }}</strong> 字
        </span>
      </div>

      <!-- 视图切换 -->
      <div class="view-switch">
        <el-radio-group :model-value="viewMode" @update:model-value="$emit('update:viewMode', $event)" size="small">
          <el-radio-button value="diff">差异对比</el-radio-button>
          <el-radio-button value="side">左右对照</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 差异对比视图 -->
      <div v-if="viewMode === 'diff'" class="diff-view">
        <div class="diff-legend">
          <span class="legend-item added"><span class="legend-color"></span>新增内容</span>
          <span class="legend-item removed"><span class="legend-color"></span>删除内容</span>
          <span class="legend-item unchanged"><span class="legend-color"></span>未修改</span>
        </div>
        <div class="diff-content" v-html="diffHtml"></div>
      </div>

      <!-- 左右对照视图 -->
      <div v-else class="compare-view">
        <div class="compare-panel">
          <div class="panel-header">
            <el-tag type="warning">原始内容</el-tag>
            <span class="panel-word-count">{{ unitData.original_summary?.length || 0 }} 字</span>
          </div>
          <div class="panel-content">
            <el-input
              :model-value="unitData.original_summary"
              type="textarea"
              :rows="15"
              readonly
            />
          </div>
        </div>
        
        <div class="compare-panel">
          <div class="panel-header">
            <el-tag type="success">修正后内容</el-tag>
            <span class="panel-word-count">{{ unitData.revised_summary?.length || 0 }} 字</span>
          </div>
          <div class="panel-content">
            <el-input
              :model-value="unitData.revised_summary"
              type="textarea"
              :rows="15"
              readonly
            />
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  unitData: { type: Object, default: null },
  unitNumber: { type: [Number, String], default: '' },
  unitLabel: { type: String, default: '章' },
  viewMode: { type: String, default: 'diff' },
  diffHtml: { type: String, default: '' }
})

defineEmits(['update:modelValue', 'update:viewMode'])

const dialogTitle = computed(() => {
  return `修正详情 - 第${props.unitNumber}${props.unitLabel}`
})
</script>
