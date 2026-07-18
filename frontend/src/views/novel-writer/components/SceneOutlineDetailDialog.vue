<!--
  组件: SceneOutlineDetailDialog
  自动生成于: 脚本批量拆分
-->
<template>
<!-- 查看模式 -->
      <div v-if='!editMode' class='outline-detail-content markdown-content' v-html='renderedContent'></div>
      
      <!-- 编辑模式 -->
      <div v-else class='outline-edit-mode'>
        <el-input
          v-model='editTitle'
          placeholder='场景标题'
          style='margin-bottom: 12px;'
        />
        <el-input
          v-model='editContent'
          type='textarea'
          :rows='20'
          placeholder='场景大纲内容'
        />
      </div>
      
      <template #footer>
        <div class='dialog-footer-actions'>
          <div>
            <el-button v-if='!editMode' type='primary' @click='startEditSceneOutline'>
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
          </div>
          <div>
            <template v-if='editMode'>
              <el-button @click='cancelEditSceneOutline'>取消</el-button>
              <el-button type='primary' @click='saveSceneOutlineEdit' :loading='saving'>
                保存修改
              </el-button>
            </template>
            <template v-else>
              <el-button @click='sceneOutlineDetailVisible = false'>关闭</el-button>
              <el-button type='primary' @click='downloadSingleSceneOutline'>
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
import { Edit, Download } from '@element-plus/icons-vue'

defineProps({
    visible: { type: Boolean, default: false },
    outline: { type: Object, default: () => ({}) },
    editMode: { type: Boolean, default: false },
    editTitle: { type: String, default: '' },
    editContent: { type: String, default: '' },
    saving: { type: Boolean, default: false },
    renderedContent: { type: String, default: '' }
})

defineEmits(['update:visible', 'start-edit', 'save', 'cancel-edit', 'download'])

</script>
