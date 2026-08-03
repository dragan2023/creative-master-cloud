<!--
  组件: ReviewItemCard
  统一审阅项卡片 - 展示"原文/建议/原因"三列或窄屏顺序卡片

  Props:
  - item: 审阅项数据 (issue_id, dimension, severity, reason, before_text, after_text, status, ...)
  - applying: 是否正在应用此修正
  - showActions: 是否显示操作按钮

  Events:
  - apply: 应用此项
  - skip: 跳过此项
  - undo: 撤销此项

  @date: 2026-07-24
  @version: v1.0 (Phase 02)
-->
<template>
  <div class="review-item-card" :class="[`severity-${item.severity}`, `status-${item.status}`]">
    <!-- 头部：维度 + 严重性 + 状态 -->
    <div class="card-header">
      <div class="header-left">
        <el-tag :type="severityTagType" size="small" effect="dark">
          {{ severityLabel }}
        </el-tag>
        <span class="item-dimension">{{ dimensionLabel }}</span>
        <span class="item-id">{{ item.issue_id }}</span>
        <el-tag v-if="item.status === 'applied'" type="success" size="small" effect="plain">
          已应用
        </el-tag>
        <el-tag v-else-if="item.status === 'skipped'" type="info" size="small" effect="plain">
          已跳过
        </el-tag>
        <el-tag v-else-if="item.status === 'reverted'" type="warning" size="small" effect="plain">
          已撤销
        </el-tag>
      </div>
      <div class="header-right">
        <span v-if="item.location?.chapter_number" class="location-badge">
          <el-icon><Location /></el-icon>
          第{{ item.location.chapter_number }}单元
        </span>
      </div>
    </div>

    <!-- 原因 -->
    <div class="card-reason">
      <div class="reason-label">
        <el-icon><InfoFilled /></el-icon>
        <strong>问题说明</strong>
        <!-- 知识来源标注 -->
        <span v-if="knowledgeSourceLabel" class="knowledge-source" :class="knowledgeSourceClass">
          <el-icon><Collection /></el-icon>
          {{ knowledgeSourceLabel }}
        </span>
      </div>
      <p class="reason-text">{{ item.reason || item.description || '无详细说明' }}</p>
      <p v-if="item.evidence" class="evidence-text">
        <strong>证据:</strong> {{ item.evidence }}
      </p>
    </div>

    <!-- 三列：原文 / 建议 / (空) - 桌面端 -->
    <div v-if="hasContent" class="card-compare desktop-compare">
      <div class="compare-column before-column">
        <div class="column-header">
          <el-tag type="danger" size="small" effect="plain">原文</el-tag>
          <span class="word-count">{{ beforeWordCount }} 字</span>
        </div>
        <div class="column-content">
          <pre class="content-text">{{ item.before_text || item.evidence || '（无原文）' }}</pre>
        </div>
      </div>
      <div class="compare-arrow">
        <el-icon :size="20"><Right /></el-icon>
      </div>
      <div class="compare-column after-column">
        <div class="column-header">
          <el-tag type="success" size="small" effect="plain">建议</el-tag>
          <span class="word-count">{{ afterWordCount }} 字</span>
        </div>
        <div class="column-content">
          <pre class="content-text">{{ item.after_text || item.suggestion || '（无建议文本）' }}</pre>
        </div>
      </div>
    </div>

    <!-- 窄屏：顺序卡片 -->
    <div v-else-if="hasContent" class="card-compare mobile-compare">
      <div class="mobile-section before-section">
        <div class="section-header">
          <el-tag type="danger" size="small" effect="plain">原文</el-tag>
        </div>
        <pre class="content-text">{{ item.before_text || item.evidence || '（无原文）' }}</pre>
      </div>
      <div class="mobile-section after-section">
        <div class="section-header">
          <el-tag type="success" size="small" effect="plain">建议</el-tag>
        </div>
        <pre class="content-text">{{ item.after_text || item.suggestion || '（无建议文本）' }}</pre>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div v-if="showActions && item.status !== 'applied'" class="card-actions">
      <el-button
        type="primary"
        size="small"
        :loading="applying"
        :disabled="!item.after_text && !item.suggestion"
        @click="$emit('apply', item)"
      >
        <el-icon><Check /></el-icon>
        应用此项
      </el-button>
      <el-button
        size="small"
        @click="$emit('skip', item)"
      >
        <el-icon><Remove /></el-icon>
        跳过此项
      </el-button>
    </div>
    <div v-else-if="showActions && item.status === 'applied'" class="card-actions">
      <el-button
        type="warning"
        size="small"
        @click="$emit('undo', item)"
      >
        <el-icon><RefreshLeft /></el-icon>
        撤销
      </el-button>
      <el-tag type="success" size="small" effect="dark">✓ 已应用</el-tag>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Check, Remove, RefreshLeft, InfoFilled, Collection, Location, Right } from '@element-plus/icons-vue'

const props = defineProps({
  item: { type: Object, required: true },
  applying: { type: Boolean, default: false },
  showActions: { type: Boolean, default: true }
})

defineEmits(['apply', 'skip', 'undo'])

const severityTagType = computed(() => {
  const map = { critical: 'danger', major: 'warning', minor: 'info' }
  return map[props.item.severity] || 'info'
})

const severityLabel = computed(() => {
  const map = { critical: '严重', major: '重要', minor: '建议' }
  return map[props.item.severity] || '未知'
})

const dimensionLabel = computed(() => {
  const map = {
    style: '风格',
    structure: '结构',
    consistency: '一致性',
    character: '人物',
    logic: '逻辑',
    timeline: '时间线',
    global_structure: '全局结构',
    unit_structure: '单元结构',
    unit_character: '单元人物',
    unit_consistency: '单元一致性',
  }
  return map[props.item.dimension] || props.item.dimension || '未知维度'
})

const knowledgeSourceLabel = computed(() => {
  const ks = props.item.knowledge_source
  if (!ks) return null
  if (ks.source_type === 'knowledge_base') return '知识库驱动'
  if (ks.source_type === 'model_inference') return '模型推断'
  if (ks.source_type === 'hybrid') return '知识库+模型推断'
  return null
})

const knowledgeSourceClass = computed(() => {
  const ks = props.item.knowledge_source
  if (!ks) return ''
  return ks.source_type === 'knowledge_base' ? 'source-kb' : 'source-model'
})

const hasContent = computed(() => {
  return !!(props.item.before_text || props.item.after_text || props.item.evidence || props.item.suggestion)
})

const beforeWordCount = computed(() => {
  const text = props.item.before_text || props.item.evidence || ''
  return text.length
})

const afterWordCount = computed(() => {
  const text = props.item.after_text || props.item.suggestion || ''
  return text.length
})
</script>

<style lang="scss" scoped>
.review-item-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  margin-bottom: 12px;
  background: #fff;
  overflow: hidden;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  &.severity-critical {
    border-left: 4px solid #f56c6c;
  }
  &.severity-major {
    border-left: 4px solid #e6a23c;
  }
  &.severity-minor {
    border-left: 4px solid #909399;
  }
  &.status-applied {
    border-left-color: #67c23a;
    background: #f0f9eb;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: #fafafa;
    border-bottom: 1px solid #ebeef5;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;

      .item-dimension {
        font-weight: 600;
        color: #303133;
        font-size: 13px;
      }

      .item-id {
        color: #c0c4cc;
        font-size: 11px;
        font-family: monospace;
      }
    }

    .header-right {
      .location-badge {
        color: #909399;
        font-size: 12px;
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
  }

  .card-reason {
    padding: 10px 14px;
    background: #fafcff;
    border-bottom: 1px solid #ebeef5;

    .reason-label {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 6px;
      color: #303133;
      font-size: 13px;

      .knowledge-source {
        margin-left: auto;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 4px;
        display: flex;
        align-items: center;
        gap: 3px;

        &.source-kb {
          background: #ecf5ff;
          color: #409eff;
        }
        &.source-model {
          background: #fdf6ec;
          color: #e6a23c;
        }
      }
    }

    .reason-text {
      margin: 0;
      font-size: 13px;
      color: #606266;
      line-height: 1.6;
    }

    .evidence-text {
      margin: 6px 0 0;
      font-size: 12px;
      color: #909399;
    }
  }

  .card-compare {
    padding: 0;

    &.desktop-compare {
      display: flex;
      border-bottom: 1px solid #ebeef5;

      .compare-column {
        flex: 1;
        min-width: 0;

        &:first-child {
          border-right: 1px solid #ebeef5;
        }
      }

      .compare-arrow {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        flex-shrink: 0;
        color: #c0c4cc;
      }

      .column-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px;
        background: #fafafa;
        border-bottom: 1px solid #ebeef5;

        .word-count {
          font-size: 11px;
          color: #c0c4cc;
        }
      }

      .column-content {
        padding: 10px 12px;

        .content-text {
          margin: 0;
          font-size: 12px;
          line-height: 1.6;
          color: #303133;
          white-space: pre-wrap;
          word-break: break-word;
          max-height: 200px;
          overflow-y: auto;
          font-family: inherit;
        }
      }
    }

    &.mobile-compare {
      display: none;
      border-bottom: 1px solid #ebeef5;

      .mobile-section {
        padding: 10px 14px;

        &:first-child {
          border-bottom: 1px dashed #ebeef5;
        }

        .section-header {
          margin-bottom: 6px;
        }

        .content-text {
          margin: 0;
          font-size: 12px;
          line-height: 1.6;
          color: #303133;
          white-space: pre-wrap;
          word-break: break-word;
          font-family: inherit;
        }
      }
    }
  }

  .card-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    background: #fafafa;
    border-top: 1px solid #ebeef5;
  }
}

// 窄屏适配 (<768px)：三列变为顺序卡片
@media (max-width: 768px) {
  .review-item-card {
    .card-compare.desktop-compare {
      display: none !important;
    }
    .card-compare.mobile-compare {
      display: block !important;
    }
  }
}
</style>
