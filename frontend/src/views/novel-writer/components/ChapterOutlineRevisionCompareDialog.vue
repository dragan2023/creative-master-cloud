<!--
  组件: ChapterOutlineRevisionCompareDialog
  自动生成于: 脚本批量拆分
-->
<template>
<div class='revision-compare-container'>
        <!-- 修正信息 -->
        <div class='revision-info-header'>
          <el-tag type='success'>已应用逻辑一致性修正</el-tag>
          <span class='revision-stats'>
            原文 <strong>{{ revisionInfo?.original_length || originalContent?.length || 0 }}</strong> 字 
            → 修正后 <strong>{{ revisionInfo?.revised_length || revisedContent?.length || 0 }}</strong> 字
            <span v-if='wordChange !== 0' :class='["word-change", wordChange > 0 ? "increase" : "decrease"]'>
              ({{ wordChange > 0 ? "+" : "" }}{{ wordChange }}字)
            </span>
          </span>
          <span class='revision-time' v-if='revisionInfo?.revised_at'>
            修正时间: {{ formatDateTime(revisionInfo.revised_at) }}
          </span>
        </div>

        <!-- 视图切换标签 -->
        <div class='view-switch'>
          <el-radio-group v-model='chapterOutlineRevisionViewMode' size='small'>
            <el-radio-button value='diff'>差异对比</el-radio-button>
            <el-radio-button value='side'>左右对照</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 差异对比视图 -->
        <div v-if='chapterOutlineRevisionViewMode === "diff"' class='diff-view'>
          <div class='diff-legend'>
            <span class='legend-item added'><span class='legend-color'></span>新增内容</span>
            <span class='legend-item removed'><span class='legend-color'></span>删除内容</span>
            <span class='legend-item modified'><span class='legend-color'></span>修改内容</span>
          </div>
          <div class='diff-content' v-html='diffHtml'></div>
        </div>

        <!-- 左右对照视图 -->
        <div v-else class='compare-view'>
          <div class='compare-panel'>
            <div class='panel-header'>
              <el-tag type='warning'>原始大纲</el-tag>
              <span class='panel-word-count'>{{ originalContent?.length || 0 }} 字</span>
            </div>
            <div class='panel-content'>
              <el-input
                v-model='originalContent'
                type='textarea'
                :rows='25'
                readonly
              />
            </div>
          </div>
          
          <div class='compare-panel'>
            <div class='panel-header'>
              <el-tag type='success'>修正后大纲</el-tag>
              <span class='panel-word-count'>{{ revisedContent?.length || 0 }} 字</span>
            </div>
            <div class='panel-content'>
              <el-input
                v-model='revisedContent'
                type='textarea'
                :rows='25'
                readonly
              />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click='chapterOutlineRevisionCompareVisible = false'>关闭</el-button>
      </template>
</template>

<script setup>
import { formatDateTime } from '@/views/novel-writer/utils/contentHelpers'
import { ref } from 'vue'

defineProps({
    visible: { type: Boolean, default: false },
    revisionInfo: { type: Object },
    originalContent: { type: String, default: '' },
    revisedContent: { type: String, default: '' },
    diffHtml: { type: String, default: '' },
    wordChange: { type: Number, default: 0 }
})

defineEmits(['update:visible'])

const chapterOutlineRevisionViewMode = ref('diff')

</script>
