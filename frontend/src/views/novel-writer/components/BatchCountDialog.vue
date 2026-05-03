<!--
  组件: BatchCountDialog
  自动生成于: 脚本批量拆分
-->
<template>
<el-form label-width="100px">
        <el-form-item label="起始单元">
          <el-input-number 
            v-model="config.startUnit" 
            :min="1" 
            :max="config.maxUnit"
          />
        </el-form-item>
        <el-form-item label="生成数量">
          <el-input-number 
            v-model="config.count" 
            :min="1" 
            :max="50"
          />
        </el-form-item>
        <el-form-item label="预计生成">
          <el-text>
            第 {{ config.startUnit }} 至第 {{ Math.min(config.startUnit + config.count - 1, config.maxUnit) }} {{ config.unitLabel }}
          </el-text>
          <el-text v-if="config.startUnit + config.count - 1 > config.maxUnit" type="warning">
            (已超出最大单元数)
          </el-text>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleClose">取消</el-button>
        <el-button 
          type="primary" 
          @click="executeBatchCountGenerate" 
          :loading="loading"
        >
          开始生成
        </el-button>
      </template>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
    visible: { type: Boolean, default: false },
    config: { type: Object, default: () => ({}) },
    loading: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'execute'])
const handleClose = () => emit('update:visible', false)

</script>
