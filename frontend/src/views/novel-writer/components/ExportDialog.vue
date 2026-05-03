<!--
  组件: ExportDialog
  自动生成于: 脚本批量拆分
-->
<template>
<el-form :model="exportForm" label-width="100px">
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio value="txt">TXT</el-radio>
            <el-radio value="md">Markdown</el-radio>
            <el-radio value="docx">Word</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="包含元数据">
          <el-switch v-model="exportForm.include_metadata" />
        </el-form-item>
        <el-form-item label="范围">
          <el-input v-model="exportForm.chapter_range" :placeholder="`留空导出全部，如：1-10`" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleExport" :loading="exporting">导出</el-button>
      </template>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
    visible: { type: Boolean, default: false },
    exportForm: { type: Object },
    exporting: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'export'])
const handleClose = () => emit('update:visible', false)

</script>
