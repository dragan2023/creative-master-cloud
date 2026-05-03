<!--
  组件: EpisodeOutlineDetailDialog
  自动生成于: 脚本批量拆分
-->
<template>
<!-- 查看模式 -->
      <div v-if='!editMode' class='outline-detail-content markdown-content' v-html='renderedContent'></div>
      
      <!-- 编辑模式 -->
      <div v-else class='outline-edit-mode'>
        <el-form label-width='80px'>
          <el-form-item label='集标题'>
            <el-input v-model='editTitle' placeholder='请输入集标题' />
          </el-form-item>
          <el-form-item label='大纲内容'>
            <el-input
              v-model='editContent'
              type='textarea'
              :rows='20'
              placeholder='请输入分集详细大纲内容'
            />
          </el-form-item>
        </el-form>
      </div>
      
      <template #footer>
        <div style='display: flex; justify-content: space-between; width: 100%;'>
          <div>
            <el-button v-if='!editMode' type='primary' plain @click='startEditOutline'>
              <el-icon><Setting /></el-icon>
              编辑大纲
            </el-button>
          </div>
          <div>
            <template v-if='editMode'>
              <el-button @click='cancelEditOutline'>取消</el-button>
              <el-button type='primary' @click='saveOutlineEdit' :loading='saving'>
                保存修改
              </el-button>
            </template>
            <template v-else>
              <el-button @click='outlineDetailVisible = false'>关闭</el-button>
              <el-button type='primary' @click='downloadSingleEpisodeOutline'>
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
