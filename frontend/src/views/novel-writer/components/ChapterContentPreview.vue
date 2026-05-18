<template>
  <el-card class="chapter-content-preview" v-if="selectedChapter">
    <template #header>
      <div class="preview-header">
        <span>{{ selectedChapter.chapter_title || unitLabel + '内容' }}</span>
        <div class="preview-actions">
          <el-button size="small" @click="$emit('generate')" :loading="loading">
            {{ content ? '重新生成' : '生成内容' }}
          </el-button>
          <el-button size="small" @click="$emit('save')" :disabled="!content">保存</el-button>
          <el-button size="small" @click="$emit('download')" :disabled="!content">下载</el-button>
        </div>
      </div>
    </template>
    <div class="content-area">
      <el-input
        v-model="localContent"
        type="textarea"
        :autosize="{ minRows: 6, maxRows: 20 }"
        placeholder="暂无内容，点击生成按钮开始创作"
        @input="$emit('update:content', localContent)"
      />
    </div>
    <div class="content-meta" v-if="content">
      <span>字数: {{ content.length }}</span>
      <el-button v-if="revisionInfo" size="small" text type="primary" @click="$emit('show-revision-compare')">
        查看修订
      </el-button>
      <el-button v-if="complianceMarking" size="small" text type="warning" @click="$emit('show-compliance-detail')">
        合规详情
      </el-button>
    </div>
  </el-card>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  selectedChapter: { type: Object, default: null },
  content: { type: String, default: '' },
  unitLabel: { type: String, default: '章节' },
  revisionInfo: { type: [Object, null], default: null },
  complianceMarking: { type: [Object, null], default: null },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['generate', 'save', 'update:content', 'download', 'show-revision-compare', 'show-compliance-detail'])

const localContent = ref(props.content)
watch(() => props.content, (val) => { localContent.value = val })
</script>

<style lang="scss" scoped>
.chapter-content-preview {
  margin-top: 16px;

  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .preview-actions {
      display: flex;
      gap: 4px;
    }
  }

  .content-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
    font-size: 12px;
    color: #909399;
  }
}
</style>
