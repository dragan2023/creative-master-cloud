<!--
  组件: ChapterOutlineDetailDialog
  自动生成于: 脚本批量拆分
-->
<template>
<!-- 修正信息提示 -->
      <el-alert
        v-if='outline.revision_info?.applied'
        type='success'
        :closable='false'
        show-icon
        style='margin-bottom: 12px;'
      >
        <template #title>
          <span>已应用逻辑一致性修正</span>
          <span style='margin-left: 12px; font-size: 12px; color: #909399;'>
            原文 {{ outline.revision_info?.original_length }} 字 → 修正后 {{ outline.revision_info?.revised_length }} 字
          </span>
        </template>
      </el-alert>

      <!-- 查看模式 -->
      <div v-if='!editMode' class='outline-detail-content markdown-content' v-html='renderedContent'></div>
      
      <!-- 编辑模式 -->
      <div v-else class='outline-edit-mode'>
        <el-input
          v-model='editTitle'
          placeholder='章节标题'
          style='margin-bottom: 12px;'
        />
        <el-input
          v-model='editContent'
          type='textarea'
          :rows='20'
          placeholder='章节大纲内容'
        />
      </div>
      
      <template #footer>
        <div class='dialog-footer-actions'>
          <div>
            <el-button v-if='!editMode && outline.revision_info?.applied' type='success' plain @click='showChapterOutlineRevisionCompare'>
              <el-icon><View /></el-icon>
              查看修正对比
            </el-button>
            <el-button v-if='!editMode' type='primary' @click='startEditChapterOutline'>
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
          </div>
          <div>
            <template v-if='editMode'>
              <el-button @click='cancelEditChapterOutline'>取消</el-button>
              <el-button type='primary' @click='saveChapterOutlineEdit' :loading='saving'>
                保存修改
              </el-button>
            </template>
            <template v-else>
              <el-button @click='chapterOutlineDetailVisible = false'>关闭</el-button>
              <el-button type='primary' @click='downloadSingleChapterOutline'>
                <el-icon><Download /></el-icon>
                下载
              </el-button>
            </template>
          </div>
        </div>
      </template>
</template>

<script setup>
import { ref } from 'vue'
import { View, Edit, Download } from '@element-plus/icons-vue'

defineProps({
    visible: { type: Boolean, default: false },
    outline: { type: Object, default: () => ({}) },
    editMode: { type: Boolean, default: false },
    editTitle: { type: String, default: '' },
    editContent: { type: String, default: '' },
    saving: { type: Boolean, default: false },
    renderedContent: { type: String, default: '' }
})

defineEmits(['update:visible', 'start-edit', 'save', 'cancel-edit', 'download', 'show-revision-compare'])

</script>
