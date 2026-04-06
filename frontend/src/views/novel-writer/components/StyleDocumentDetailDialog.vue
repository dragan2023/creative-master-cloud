<!--
  风格文档详情对话框组件
  
  功能增强：
  - 增加空状态处理
  - 增加数据加载中状态
  - 增强数据健壮性检查
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="风格文档详情"
    width="700px"
    destroy-on-close
  >
    <!-- 空状态处理 -->
    <div v-if="!styleDocumentInfo" class="empty-state">
      <el-empty description="暂无风格文档数据">
        <el-button type="primary" @click="$emit('refresh')">重新加载</el-button>
      </el-empty>
    </div>
    
    <!-- 数据展示 -->
    <div v-else class="style-detail-content">
      <!-- 风格特征 -->
      <div class="detail-section" v-if="hasStyleProfile">
        <h4>风格特征</h4>
        <div class="profile-grid">
          <div class="profile-item" v-if="styleDocumentInfo.style_profile?.vocabulary">
            <span class="item-label">词汇特征</span>
            <span class="item-value">{{ styleDocumentInfo.style_profile.vocabulary?.word_preference || '-' }}</span>
          </div>
          <div class="profile-item" v-if="styleDocumentInfo.style_profile?.sentence_structure">
            <span class="item-label">句式特征</span>
            <span class="item-value">{{ styleDocumentInfo.style_profile.sentence_structure?.rhythm || styleDocumentInfo.style_profile.sentence_structure?.average_length || '-' }}</span>
          </div>
          <div class="profile-item" v-if="styleDocumentInfo.style_profile?.narrative_style">
            <span class="item-label">叙事特征</span>
            <span class="item-value">{{ styleDocumentInfo.style_profile.narrative_style?.perspective || '-' }}</span>
          </div>
          <div class="profile-item" v-if="styleDocumentInfo.style_profile?.dialogue_style">
            <span class="item-label">对话风格</span>
            <span class="item-value">{{ styleDocumentInfo.style_profile.dialogue_style?.style || '-' }}</span>
          </div>
        </div>
      </div>

      <!-- 模仿要点 -->
      <div class="detail-section" v-if="hasImitationPoints">
        <h4>模仿要点</h4>
        <ul class="imitation-points">
          <li v-for="(point, index) in styleDocumentInfo.key_imitation_points" :key="index">
            {{ point }}
          </li>
        </ul>
      </div>

      <!-- 应避免的模式 -->
      <div class="detail-section" v-if="hasAvoidPatterns">
        <h4>应避免的模式</h4>
        <ul class="avoid-patterns">
          <li v-for="(pattern, index) in styleDocumentInfo.avoid_patterns" :key="index">
            {{ pattern }}
          </li>
        </ul>
      </div>

      <!-- 示例转换 -->
      <div class="detail-section" v-if="hasExampleTransformations">
        <h4>示例转换</h4>
        <div class="transformations-list">
          <div 
            v-for="(transform, index) in styleDocumentInfo.example_transformations" 
            :key="index"
            class="transformation-item"
          >
            <div class="original-text">
              <span class="label">原文：</span>
              <span>{{ transform.original || '-' }}</span>
            </div>
            <div class="styled-text">
              <span class="label">风格化：</span>
              <span>{{ transform.styled || '-' }}</span>
            </div>
            <div class="explanation" v-if="transform.explanation">
              <span class="label">说明：</span>
              <span>{{ transform.explanation }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 风格指南 -->
      <div class="detail-section" v-if="hasStyleGuide">
        <h4>风格指南</h4>
        <p class="style-guide">{{ styleDocumentInfo.style_guide_for_writing }}</p>
      </div>
      
      <!-- 无数据提示 -->
      <div v-if="!hasAnyData" class="no-data-tip">
        <el-text type="info">风格文档分析结果尚未生成或不完整，请重新上传分析。</el-text>
      </div>
    </div>
    
    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
      <el-button type="primary" v-if="styleDocumentInfo" @click="$emit('refresh')">刷新数据</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  styleDocumentInfo: {
    type: Object,
    default: null
  }
})

defineEmits(['update:visible', 'refresh'])

// 计算属性：检查数据完整性
const hasStyleProfile = computed(() => {
  const profile = props.styleDocumentInfo?.style_profile
  return profile && (
    profile.vocabulary || 
    profile.sentence_structure || 
    profile.narrative_style ||
    profile.dialogue_style
  )
})

const hasImitationPoints = computed(() => {
  return props.styleDocumentInfo?.key_imitation_points?.length > 0
})

const hasAvoidPatterns = computed(() => {
  return props.styleDocumentInfo?.avoid_patterns?.length > 0
})

const hasExampleTransformations = computed(() => {
  return props.styleDocumentInfo?.example_transformations?.length > 0
})

const hasStyleGuide = computed(() => {
  return !!props.styleDocumentInfo?.style_guide_for_writing
})

const hasAnyData = computed(() => {
  return hasStyleProfile.value || 
         hasImitationPoints.value || 
         hasAvoidPatterns.value || 
         hasStyleGuide.value ||
         hasExampleTransformations.value
})
</script>

<style lang="scss" scoped>
.empty-state {
  padding: 40px 0;
  text-align: center;
}

.style-detail-content {
  .detail-section {
    margin-bottom: 20px;

    h4 {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 12px;
      padding-left: 8px;
      border-left: 3px solid #409eff;
    }

    .profile-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;

      .profile-item {
        padding: 10px 12px;
        background: #f5f7fa;
        border-radius: 6px;

        .item-label {
          display: block;
          font-size: 12px;
          color: #909399;
          margin-bottom: 4px;
        }

        .item-value {
          font-size: 13px;
          color: #606266;
        }
      }
    }

    .imitation-points,
    .avoid-patterns {
      margin: 0;
      padding: 0 0 0 20px;

      li {
        font-size: 13px;
        color: #606266;
        line-height: 1.8;
        margin-bottom: 6px;
      }
    }

    .avoid-patterns li {
      color: #f56c6c;
    }

    .style-guide {
      font-size: 13px;
      color: #606266;
      line-height: 1.8;
      padding: 12px 16px;
      background: #f5f7fa;
      border-radius: 8px;
      margin: 0;
    }
    
    .transformations-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
      
      .transformation-item {
        padding: 12px;
        background: #f5f7fa;
        border-radius: 8px;
        
        .original-text,
        .styled-text,
        .explanation {
          margin-bottom: 6px;
          font-size: 13px;
          line-height: 1.6;
          
          .label {
            color: #909399;
            margin-right: 8px;
          }
        }
        
        .styled-text {
          color: #67c23a;
        }
        
        .explanation {
          color: #909399;
          font-size: 12px;
          margin-bottom: 0;
        }
      }
    }
  }
  
  .no-data-tip {
    padding: 20px;
    text-align: center;
    background: #fafafa;
    border-radius: 8px;
  }
}
</style>
