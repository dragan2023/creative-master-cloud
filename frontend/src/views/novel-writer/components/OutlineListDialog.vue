<!--
  已生成大纲列表对话框组件
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="已生成单元大纲列表"
    width="900px"
    top="5vh"
    destroy-on-close
    class="outline-list-dialog"
  >
    <div class="outline-list-content">
      <!-- 统计信息 -->
      <div class="list-stats">
        <el-statistic title="总数" :value="stats.total" />
        <el-statistic title="已生成" :value="stats.generated" />
        <el-statistic title="待生成" :value="stats.pending" />
      </div>

      <!-- 已生成列表 -->
      <el-table :data="outlineList" stripe style="width: 100%" max-height="400">
        <el-table-column prop="chapter_number" label="章节" width="80" align="center">
          <template #default="{ row }"> #{{ row.chapter_number }} </template>
        </el-table-column>
        <el-table-column prop="chapter_title" label="标题" min-width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'generated'" type="success" size="small">已生成</el-tag>
            <el-tag v-else-if="row.status === 'edited'" type="warning" size="small">已编辑</el-tag>
            <el-tag v-else type="info" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="$emit('view', row.chapter_number)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  stats: {
    type: Object,
    default: () => ({ total: 0, generated: 0, pending: 0 })
  },
  outlineList: {
    type: Array,
    default: () => []
  }
})

defineEmits(['update:visible', 'view'])
</script>

<style lang="scss" scoped>
.outline-list-dialog {
  .outline-list-content {
    .list-stats {
      display: flex;
      gap: 40px;
      justify-content: center;
      margin-bottom: 20px;
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;
    }
  }
}
</style>
