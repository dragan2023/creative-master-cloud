<template>
  <div class="unit-summaries-section" v-if="project?.outline_content">
    <el-divider content-position="left">单元概述</el-divider>
    <div class="summaries-actions">
      <el-button size="small" @click="onShowUploadDialog">上传概述</el-button>
      <el-button size="small" type="warning" :loading="qualityControlLoading" @click="onQualityControl">
        质控检测
      </el-button>
    </div>
    <div class="summaries-status">
      <el-tag v-if="project.unit_summaries_status === 'completed'" type="success" size="small">概述已生成</el-tag>
      <el-tag v-else-if="project.unit_summaries_status === 'processing'" type="info" size="small">生成中...</el-tag>
      <el-tag v-else size="small" type="info">未生成</el-tag>
    </div>
  </div>
</template>

<script setup>
defineProps({
  project: { type: Object, default: null },
  qualityControlLoading: { type: Boolean, default: false },
  onShowUploadDialog: { type: Function, default: null },
  onQualityControl: { type: Function, default: null }
})
</script>

<style lang="scss" scoped>
.unit-summaries-section {
  padding: 12px 0;

  .summaries-actions {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
  }
}
</style>
