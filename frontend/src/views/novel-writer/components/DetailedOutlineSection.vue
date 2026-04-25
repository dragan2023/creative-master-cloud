<template>
  <div class="detailed-outline-section">
    <el-divider content-position="left">详细大纲</el-divider>
    <!-- 根据内容类型分发到不同子组件 -->
    <div v-if="contentType === 'series_script'">
      <div class="section-header">
        <span>剧集大纲</span>
        <el-button size="small" type="primary" @click="$emit('generate-all-episode-outlines')" :loading="generatingEpisodeOutlines">
          全部生成
        </el-button>
      </div>
      <div v-for="(ep, idx) in episodeOutlines" :key="idx" class="outline-item">
        <div class="outline-item-header">
          <span>第{{ ep.unit_index || idx + 1 }}集</span>
          <div class="outline-item-actions">
            <el-button size="small" text @click="$emit('show-episode-outline-detail', ep)">查看</el-button>
            <el-button size="small" text @click="$emit('generate-episode-content', ep)">生成内容</el-button>
          </div>
        </div>
        <div class="outline-item-title">{{ ep.title || `第${ep.unit_index || idx + 1}集` }}</div>
      </div>
    </div>

    <div v-else-if="contentType === 'novel'">
      <div class="section-header">
        <span>章节大纲</span>
        <el-button size="small" type="primary" @click="$emit('generate-all-chapter-outlines')" :loading="generatingChapterOutlines">
          全部生成
        </el-button>
      </div>
      <div v-for="(ch, idx) in chapterOutlines" :key="idx" class="outline-item">
        <div class="outline-item-header">
          <span>第{{ ch.unit_index || idx + 1 }}章</span>
          <div class="outline-item-actions">
            <el-button size="small" text @click="$emit('show-chapter-outline-detail', ch)">查看</el-button>
            <el-button size="small" text @click="$emit('generate-chapter-content', ch)">生成内容</el-button>
          </div>
        </div>
        <div class="outline-item-title">{{ ch.title || `第${ch.unit_index || idx + 1}章` }}</div>
      </div>
    </div>

    <div v-else-if="contentType === 'movie_script'">
      <div class="section-header">
        <span>场景大纲</span>
        <el-button size="small" type="primary" @click="$emit('generate-all-scene-outlines')" :loading="generatingSceneOutlines">
          全部生成
        </el-button>
      </div>
      <div v-for="(sc, idx) in sceneOutlines" :key="idx" class="outline-item">
        <div class="outline-item-header">
          <span>场景{{ sc.unit_index || idx + 1 }}</span>
          <div class="outline-item-actions">
            <el-button size="small" text @click="$emit('show-scene-outline-detail', sc)">查看</el-button>
            <el-button size="small" text @click="$emit('generate-scene-content', sc)">生成内容</el-button>
          </div>
        </div>
        <div class="outline-item-title">{{ sc.title || `场景${sc.unit_index || idx + 1}` }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  contentType: { type: String, default: 'novel' },
  chapters: { type: Array, default: () => [] },
  episodeOutlines: { type: Array, default: () => [] },
  chapterOutlines: { type: Array, default: () => [] },
  sceneOutlines: { type: Array, default: () => [] },
  generatedEpisodeCount: { type: Number, default: 0 },
  totalEpisodeCount: { type: Number, default: 0 },
  generatedChapterOutlineCount: { type: Number, default: 0 },
  totalChapterOutlineCount: { type: Number, default: 0 },
  generatedSceneOutlineCount: { type: Number, default: 0 },
  totalSceneOutlineCount: { type: Number, default: 0 },
  generatingEpisodeOutlines: { type: Boolean, default: false },
  generatingChapterOutlines: { type: Boolean, default: false },
  generatingSceneOutlines: { type: Boolean, default: false },
  generating: { type: Boolean, default: false },
  taskStore: { type: Object, default: null },
  selectedEpisode: { type: Object, default: null },
  generatingSingleEpisode: { type: Boolean, default: false },
  generatingSingleChapterOutline: { type: Boolean, default: false },
  generatingSingleSceneOutline: { type: Boolean, default: false },
  selectedChapter: { type: Object, default: null },
  selectedScene: { type: Object, default: null },
  editingEpisodeTitle: { type: Number, default: -1 },
  editEpisodeTitleValue: { type: String, default: '' },
  editingChapterOutlineTitle: { type: Number, default: -1 },
  editChapterOutlineTitleValue: { type: String, default: '' },
  editingSceneOutlineTitle: { type: Number, default: -1 },
  editSceneOutlineTitleValue: { type: String, default: '' }
})

defineEmits([
  'generate-all-episode-outlines', 'generate-single-episode-outline',
  'show-episode-outline-detail', 'download-episode-outline', 'download-all-episode-outlines',
  'generate-episode-content', 'stop-generation', 'delete-episode-content', 'delete-episode-outline',
  'edit-episode-title', 'save-episode-title', 'cancel-edit-episode-title',
  'generate-all-chapter-outlines', 'generate-single-chapter-outline',
  'show-chapter-outline-detail', 'download-chapter-outline', 'download-all-chapter-outlines',
  'generate-chapter-content', 'regenerate-chapter-outline', 'delete-chapter-content', 'delete-chapter-outline',
  'edit-chapter-outline-title', 'save-chapter-outline-title', 'cancel-edit-chapter-outline-title',
  'generate-all-scene-outlines', 'generate-single-scene-outline',
  'show-scene-outline-detail', 'download-scene-outline', 'download-all-scene-outlines',
  'generate-scene-content', 'delete-scene-content', 'delete-scene-outline',
  'edit-scene-outline-title', 'save-scene-outline-title', 'cancel-edit-scene-outline-title',
  'update:edit-episode-title-value', 'update:edit-chapter-outline-title-value', 'update:edit-scene-outline-title-value',
  'open-batch-dialog'
])
</script>

<style lang="scss" scoped>
.detailed-outline-section {
  padding: 12px 0;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    font-weight: 600;
  }

  .outline-item {
    padding: 8px 12px;
    border: 1px solid #ebeef5;
    border-radius: 4px;
    margin-bottom: 8px;

    &-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    &-title {
      font-size: 13px;
      color: #606266;
      margin-top: 4px;
    }

    &-actions {
      display: flex;
      gap: 4px;
    }
  }
}
</style>
