<template>
  <div class="chapter-list">
    <div class="list-header">
      <span>{{ unitLabel }}列表</span>
      <div class="header-actions">
        <el-button size="small" @click="$emit('regenerate-directory')" :loading="loadingDirectory">重新生成目录</el-button>
        <el-button size="small" @click="$emit('regenerate-names')" :loading="loadingNames">重新生成名称</el-button>
        <el-button size="small" type="primary" @click="$emit('open-batch-dialog')">批量生成</el-button>
      </div>
    </div>
    <div class="chapter-items">
      <div
        v-for="(ch, idx) in chapters"
        :key="ch.id || idx"
        class="chapter-item"
        :class="{ selected: selectedChapter?.id === ch.id }"
        @click="$emit('select', ch)"
      >
        <div class="chapter-info">
          <span class="chapter-index">{{ idx + 1 }}.</span>
          <template v-if="editingChapter === idx">
            <el-input
              v-model="localEditTitleValue"
              size="small"
              style="width: 200px;"
              @keyup.enter="$emit('save-title', { index: idx, title: localEditTitleValue })"
              @keyup.escape="$emit('cancel-edit')"
            />
          </template>
          <span v-else class="chapter-title" @dblclick="$emit('edit-title', idx)">
            {{ ch.title || `第${idx + 1}${unitLabel}` }}
          </span>
          <el-tag v-if="ch.has_content" type="success" size="small">已生成</el-tag>
          <el-tag v-if="ch.compliance_status === 'flagged'" type="danger" size="small">合规标记</el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  chapters: { type: Array, default: () => [] },
  selectedChapter: { type: Object, default: null },
  contentType: { type: String, default: 'novel' },
  unitLabel: { type: String, default: '章节' },
  episodeOutlines: { type: Array, default: () => [] },
  chapterOutlines: { type: Array, default: () => [] },
  sceneOutlines: { type: Array, default: () => [] },
  loadingDirectory: { type: Boolean, default: false },
  loadingNames: { type: Boolean, default: false },
  loadingAllContent: { type: Boolean, default: false },
  batchContentType: { type: String, default: '' },
  taskStore: { type: Object, default: null },
  editingChapter: { type: Number, default: -1 },
  editTitleValue: { type: String, default: '' }
})

const emit = defineEmits([
  'select', 'edit-title', 'save-title', 'cancel-edit', 'update:edit-title-value',
  'regenerate-directory', 'regenerate-names', 'show-compliance', 'open-batch-dialog',
  'generate-all-episode-content', 'download-all-episode-content',
  'generate-all-chapter-content', 'download-all-chapter-content',
  'generate-all-scene-content', 'download-all-scene-content'
])

const localEditTitleValue = ref(props.editTitleValue)
watch(() => props.editTitleValue, (val) => { localEditTitleValue.value = val })
watch(localEditTitleValue, (val) => { emit('update:edit-title-value', val) })
</script>

<style lang="scss" scoped>
.chapter-list {
  .list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .header-actions {
      display: flex;
      gap: 4px;
    }
  }

  .chapter-item {
    padding: 8px 12px;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    margin-bottom: 4px;
    transition: all 0.2s;

    &:hover { background: #f5f7fa; }
    &.selected { background: #ecf5ff; border-color: #b3d8ff; }

    .chapter-info {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .chapter-index { color: #909399; font-size: 13px; }
    .chapter-title { font-size: 14px; cursor: text; }
  }
}
</style>
