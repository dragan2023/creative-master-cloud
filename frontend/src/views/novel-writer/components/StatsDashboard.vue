<template>
  <el-card v-if="stats" class="stats-dashboard" shadow="hover">
    <template #header>
      <div class="panel-header">
        <span>
          <el-icon><TrendCharts /></el-icon>
          Agent统计
        </span>
      </div>
    </template>

    <el-row :gutter="20">
      <!-- 总体统计 -->
      <el-col :span="6">
        <div class="stat-card total">
          <div class="stat-icon">
            <el-icon><Coin /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">
              {{ formatNumber(stats?._summary?.total_tokens || stats?.total_tokens || 0) }}
            </div>
            <div class="stat-label">总Token数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card cost">
          <div class="stat-icon">
            <el-icon><Money /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">
              ${{ (stats?._summary?.total_cost || stats?.total_cost || 0).toFixed(4) }}
            </div>
            <div class="stat-label">总费用</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card time">
          <div class="stat-icon">
            <el-icon><Timer /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ formattedDuration }}</div>
            <div class="stat-label">总耗时</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card efficiency">
          <div class="stat-icon">
            <el-icon><Odometer /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ calculateEfficiency() }}</div>
            <div class="stat-label">Token/秒</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Agent详细统计 -->
    <el-divider content-position="left">Agent详细统计</el-divider>
    <el-table
      :data="stats.by_agent || []"
      stripe
      style="width: 100%"
    >
      <el-table-column prop="agent_name" label="Agent" width="120">
        <template #default="{ row }">
          <el-tag :type="getAgentTagType(row.agent_name)" effect="plain">
            {{ row.agent_name }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="model_id"
        label="模型"
        min-width="150"
        show-overflow-tooltip
      />
      <el-table-column
        prop="call_count"
        label="调用次数"
        width="100"
        align="center"
      />
      <el-table-column
        prop="total_tokens"
        label="Token数"
        width="120"
        align="right"
      >
        <template #default="{ row }">
          {{ formatNumber(row.total_tokens) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="total_cost"
        label="费用"
        width="100"
        align="right"
      >
        <template #default="{ row }">
          ${{ row.total_cost?.toFixed(4) || "0.0000" }}
        </template>
      </el-table-column>
      <el-table-column
        prop="total_duration_sec"
        label="耗时"
        width="100"
        align="right"
      >
        <template #default="{ row }">
          {{ row.total_duration_sec?.toFixed(1) || "0.0" }}s
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import {
  TrendCharts,
  Coin,
  Money,
  Timer,
  Odometer,
} from "@element-plus/icons-vue";
import { formatNumber } from "../utils/contentHelpers";

const props = defineProps({
  stats: { type: Object, default: null },
  formattedDuration: { type: String, default: "00:00:00" },
  currentTask: { type: Object, default: null },
});

function getAgentTagType(agentName) {
  const typeMap = {
    结构师: "primary",
    写手: "success",
    逻辑编辑: "warning",
    风格润色: "",
    合规审查: "danger",
    合成: "info",
  };
  return typeMap[agentName] || "info";
}

function calculateEfficiency() {
  const tokens =
    props.stats?._summary?.total_tokens ||
    props.stats?.total_tokens ||
    0;
  const task = props.currentTask;
  if (!task) return "0";

  const start = task.start_time ? new Date(task.start_time) : null;
  const end = task.end_time ? new Date(task.end_time) : null;

  let ms = 0;
  if (start && end) {
    ms = end - start;
  } else if (start) {
    // If task is still running, use current time
    ms = Date.now() - start;
  }

  const durationSec = ms / 1000;
  if (durationSec === 0) return "0";
  return (tokens / durationSec).toFixed(1);
}
</script>

<style lang="scss" scoped>
.stats-dashboard {
  margin-top: 20px;

  .panel-header {
    display: flex;
    align-items: center;

    .el-icon {
      margin-right: 4px;
    }
  }

  .stat-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    border-radius: 8px;
    background: #f5f7fa;

    &.total {
      background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
      .stat-icon { color: #409eff; }
    }

    &.cost {
      background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
      .stat-icon { color: #67c23a; }
    }

    &.time {
      background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
      .stat-icon { color: #e6a23c; }
    }

    &.efficiency {
      background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
      .stat-icon { color: #f56c6c; }
    }

    .stat-icon {
      font-size: 32px;
    }

    .stat-info {
      .stat-value {
        font-size: 20px;
        font-weight: 600;
        color: #303133;
      }

      .stat-label {
        font-size: 12px;
        color: #909399;
        margin-top: 2px;
      }
    }
  }
}
</style>
