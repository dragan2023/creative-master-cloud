<!--
  组件: CostTransparencyPanel
  成本与性能透明度面板 - 折叠式显示模型/耗时/Token/预估成本

  Props:
  - model: 模型名称
  - provider: LLM提供商
  - durationMs: 耗时(毫秒)
  - tokenCount: Token消耗总数
  - promptTokens: 提示词Token数
  - completionTokens: 补全Token数
  - collapsed: 是否默认折叠

  @date: 2026-07-24
  @version: v1.0 (Phase 02)
-->
<template>
  <div class="cost-transparency-panel">
    <el-collapse v-model="activeNames">
      <el-collapse-item name="cost-info">
        <template #title>
          <div class="collapse-title">
            <el-icon><TrendCharts /></el-icon>
            <span>本次消耗详情</span>
            <el-tag v-if="tokenCount > 0" size="small" type="info" effect="plain">
              {{ formatTokens(tokenCount) }} Tokens
            </el-tag>
            <el-tag v-if="durationMs > 0" size="small" type="info" effect="plain">
              {{ formatDuration(durationMs) }}
            </el-tag>
          </div>
        </template>

        <div class="cost-details">
          <!-- 模型信息 -->
          <div class="detail-row">
            <span class="detail-label">模型</span>
            <span class="detail-value">
              {{ provider ? `${provider}/` : '' }}{{ model || '未知' }}
            </span>
          </div>

          <!-- 耗时 -->
          <div v-if="durationMs > 0" class="detail-row">
            <span class="detail-label">总耗时</span>
            <span class="detail-value">{{ formatDuration(durationMs) }}</span>
          </div>

          <!-- Token 详情 -->
          <template v-if="tokenCount > 0">
            <el-divider content-position="left">Token 消耗</el-divider>
            <div class="detail-row">
              <span class="detail-label">总计</span>
              <span class="detail-value token-count">{{ formatTokens(tokenCount) }}</span>
            </div>
            <div v-if="promptTokens > 0" class="detail-row">
              <span class="detail-label">提示词</span>
              <span class="detail-value">{{ formatTokens(promptTokens) }}</span>
            </div>
            <div v-if="completionTokens > 0" class="detail-row">
              <span class="detail-label">生成</span>
              <span class="detail-value">{{ formatTokens(completionTokens) }}</span>
            </div>

            <!-- 预估成本（仅在有价格配置时显示） -->
            <div v-if="estimatedCost !== null" class="detail-row cost-row">
              <span class="detail-label">预估成本</span>
              <span class="detail-value cost-value">
                ¥{{ estimatedCost }}
              </span>
            </div>
            <div v-else class="detail-row">
              <span class="detail-label">预估成本</span>
              <span class="detail-value no-cost">缺少价格配置，不估算金额</span>
            </div>
          </template>

          <!-- 无Token数据 -->
          <div v-else class="no-data">
            <el-text type="info" size="small">暂无详细消耗数据</el-text>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { TrendCharts } from '@element-plus/icons-vue'

const props = defineProps({
  model: { type: String, default: '' },
  provider: { type: String, default: '' },
  durationMs: { type: Number, default: 0 },
  tokenCount: { type: Number, default: 0 },
  promptTokens: { type: Number, default: 0 },
  completionTokens: { type: Number, default: 0 },
  collapsed: { type: Boolean, default: true }
})

const activeNames = computed(() => props.collapsed ? [] : ['cost-info'])

/**
 * 格式化Token数（加千分位分隔）
 */
function formatTokens(count) {
  if (!count || count === 0) return '0'
  if (count >= 1000) {
    return (count / 1000).toFixed(1) + 'k'
  }
  return count.toLocaleString()
}

/**
 * 格式化耗时
 */
function formatDuration(ms) {
  if (!ms || ms === 0) return '-'
  if (ms < 1000) return `${ms}ms`
  const seconds = (ms / 1000).toFixed(1)
  if (ms < 60000) return `${seconds}s`
  const minutes = Math.floor(ms / 60000)
  const remainingSeconds = ((ms % 60000) / 1000).toFixed(0)
  return `${minutes}分${remainingSeconds}秒`
}

/**
 * 预估成本（元）- 仅当有价格配置时计算
 * 默认不估算，子组件可覆盖
 */
const estimatedCost = computed(() => {
  // 当前版本不估算金额，仅展示Token
  return null
})
</script>

<style lang="scss" scoped>
.cost-transparency-panel {
  margin-top: 16px;

  :deep(.el-collapse) {
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    overflow: hidden;

    .el-collapse-item__header {
      padding: 0 14px;
      height: 40px;
      line-height: 40px;
      background: #fafcff;
      font-size: 13px;

      .collapse-title {
        display: flex;
        align-items: center;
        gap: 6px;
        flex: 1;
      }
    }

    .el-collapse-item__wrap {
      border-top: 1px solid #ebeef5;
    }
  }

  .cost-details {
    padding: 12px 16px;

    .detail-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 0;
      font-size: 13px;

      .detail-label {
        color: #909399;
        flex-shrink: 0;
      }

      .detail-value {
        color: #303133;
        font-family: 'Courier New', monospace;

        &.token-count {
          font-weight: 600;
          color: #409eff;
        }

        &.cost-value {
          font-weight: 600;
          color: #e6a23c;
        }

        &.no-cost {
          color: #c0c4cc;
          font-family: inherit;
          font-size: 12px;
          font-style: italic;
        }
      }

      &.cost-row {
        padding-top: 10px;
        border-top: 1px dashed #ebeef5;
      }
    }

    .el-divider {
      margin: 8px 0;

      :deep(.el-divider__text) {
        font-size: 12px;
        color: #909399;
        background: #fff;
      }
    }

    .no-data {
      text-align: center;
      padding: 12px 0;
    }
  }
}
</style>
