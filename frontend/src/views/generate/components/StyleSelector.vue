<template>
  <el-form-item label="风格类型">
    <div class="style-selector-grid">
      <div class="style-tip-text">可多选一级或二级选项，选一级即代表该分类，选二级则更精确</div>
      <div class="style-groups-container">
        <div v-for="group in styleTypes" :key="group.name" class="style-group">
          <div class="style-group-header">
            <el-checkbox
              :model-value="modelValue.level1.includes(group.name)"
              @change="(val) => handleLevel1Change(group.name, val)"
            >
              <strong>{{ group.name }}</strong>
            </el-checkbox>
          </div>
          <div class="style-group-children">
            <el-checkbox
              v-for="child in group.children"
              :key="child"
              :model-value="modelValue.level2.includes(child)"
              @change="(val) => handleLevel2Change(child, val)"
              size="small"
            >
              {{ child }}
            </el-checkbox>
          </div>
        </div>
      </div>
    </div>
  </el-form-item>
</template>

<script setup>
import { styleTypes } from '../composables/useGenerationForm'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
    default: () => ({ level1: [], level2: [] })
  }
})

const emit = defineEmits(['update:modelValue'])

const handleLevel1Change = (name, checked) => {
  const newLevel1 = checked
    ? [...props.modelValue.level1, name]
    : props.modelValue.level1.filter(item => item !== name)
  
  emit('update:modelValue', {
    ...props.modelValue,
    level1: newLevel1
  })
}

const handleLevel2Change = (name, checked) => {
  const newLevel2 = checked
    ? [...props.modelValue.level2, name]
    : props.modelValue.level2.filter(item => item !== name)
  
  emit('update:modelValue', {
    ...props.modelValue,
    level2: newLevel2
  })
}
</script>

<style lang="scss" scoped>
.style-selector-grid {
  .style-tip-text {
    font-size: 12px;
    color: #909399;
    margin-bottom: 12px;
  }
  
  .style-groups-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    max-height: 400px;
    overflow-y: auto;
    padding: 8px;
    
    @media (max-width: 1200px) {
      grid-template-columns: repeat(3, 1fr);
    }
    
    @media (max-width: 900px) {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  
  .style-group {
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    padding: 8px;
    background: #fafafa;
    
    .style-group-header {
      margin-bottom: 6px;
      
      :deep(.el-checkbox__label) {
        font-size: 13px;
      }
    }
    
    .style-group-children {
      display: flex;
      flex-wrap: wrap;
      gap: 4px 8px;
      
      :deep(.el-checkbox) {
        margin-right: 0;
      }
      
      :deep(.el-checkbox__label) {
        font-size: 12px;
        color: #606266;
      }
    }
  }
}
</style>
