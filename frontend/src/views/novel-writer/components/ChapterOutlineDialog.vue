<!--
  章节大纲预览对话框组件
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="`第${chapterOutline?.chapter_number || ''}章详细大纲`"
    width="800px"
    top="5vh"
    destroy-on-close
    class="chapter-outline-dialog"
  >
    <div v-if="chapterOutline" class="chapter-outline-content">
      <!-- 章节基本信息 -->
      <div class="outline-header">
        <h3 class="chapter-title">{{ chapterOutline.chapter_title }}</h3>
        <div class="chapter-meta">
          <el-tag
            v-if="chapterOutline.status === 'generated'"
            type="success"
            size="small"
          >
            已生成
          </el-tag>
          <el-tag
            v-else-if="chapterOutline.status === 'edited'"
            type="warning"
            size="small"
          >
            已编辑
          </el-tag>
          <span v-if="chapterOutline.updated_at" class="update-time">
            更新于 {{ formatTime(chapterOutline.updated_at) }}
          </span>
        </div>
      </div>

      <!-- 章节概要 -->
      <div v-if="chapterOutline.chapter_summary" class="outline-section">
        <div class="section-label">章节概要</div>
        <p class="section-content">{{ chapterOutline.chapter_summary }}</p>
      </div>

      <!-- 详细大纲 -->
      <div v-if="chapterOutline.detailed_outline" class="outline-section">
        <div class="section-label">详细大纲</div>
        <div class="section-content detailed-outline">
          {{ chapterOutline.detailed_outline }}
        </div>
      </div>

      <!-- 关键事件 -->
      <div v-if="chapterOutline.key_events?.length" class="outline-section">
        <div class="section-label">关键事件</div>
        <ul class="key-events-list">
          <li v-for="(event, idx) in chapterOutline.key_events" :key="idx">
            {{ event }}
          </li>
        </ul>
      </div>
    </div>
    <el-empty v-else description="暂无大纲数据" />
    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
      <el-button type="primary" @click="$emit('edit')">编辑</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  chapterOutline: {
    type: Object,
    default: null
  }
})

defineEmits(['update:visible', 'edit'])

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<style lang="scss" scoped>
.chapter-outline-dialog {
  .chapter-outline-content {
    max-height: 60vh;
    overflow-y: auto;
  }

  .outline-header {
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid #ebeef5;

    .chapter-title {
      margin: 0 0 8px 0;
      font-size: 18px;
      color: #303133;
    }

    .chapter-meta {
      display: flex;
      align-items: center;
      gap: 12px;

      .update-time {
        font-size: 12px;
        color: #909399;
      }
    }
  }

  .outline-section {
    margin-bottom: 16px;

    .section-label {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 8px;
      padding-left: 8px;
      border-left: 3px solid #409eff;
    }

    .section-content {
      font-size: 14px;
      color: #606266;
      line-height: 1.8;
      margin: 0;
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 4px;
    }

    .detailed-outline {
      white-space: pre-wrap;
    }

    .key-events-list {
      margin: 0;
      padding: 0 0 0 20px;

      li {
        font-size: 14px;
        color: #606266;
        line-height: 2;
        position: relative;

        &::marker {
          color: #409eff;
        }
      }
    }
  }
}
</style>
