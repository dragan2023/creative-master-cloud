<template>
  <div class="project-status-panel">
    <el-card class="status-card">
      <template #header><span>项目状态</span></template>
      <el-descriptions :column="1" size="small" border>
        <el-descriptions-item label="内容类型">{{ project?.content_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目状态">{{ project?.status || '-' }}</el-descriptions-item>
        <el-descriptions-item label="总字数">{{ totalWords || 0 }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(project?.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDate(project?.updated_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="config-card" style="margin-top: 12px;">
      <template #header><span>生成配置</span></template>
      <el-descriptions :column="1" size="small" border>
        <el-descriptions-item :label="unitLabel + '数量'">{{ project?.unit_count || '-' }}</el-descriptions-item>
        <el-descriptions-item label="LLM模型">{{ project?.llm_model || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="stats-card" style="margin-top: 12px;">
      <template #header><span>生成统计</span></template>
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-value">{{ project?.generated_count || 0 }}</div>
          <div class="stat-label">已生成</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ totalWords || 0 }}</div>
          <div class="stat-label">总字数</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
defineProps({
  project: { type: Object, default: null },
  unitLabel: { type: String, default: '章节' },
  totalWords: { type: Number, default: 0 }
})

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}
</script>

<style lang="scss" scoped>
.project-status-panel {
  .stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    text-align: center;

    .stat-item {
      .stat-value { font-size: 20px; font-weight: 600; color: #409eff; }
      .stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
    }
  }
}
</style>
