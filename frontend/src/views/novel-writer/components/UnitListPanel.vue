<template>
  <el-card class="units-panel" shadow="hover">
    <template #header>
      <div class="panel-header">
        <span>
          <el-icon><List /></el-icon>
          单元列表
        </span>
        <div class="panel-header-actions">
          <!-- 质控快捷入口 -->
          <el-tooltip content="正文质量管控：检测问题、应用修正、查看报告" placement="top">
            <el-button
              type="warning"
              size="small"
              plain
              @click="$emit('show-quality-control')"
            >
              <el-icon><CircleCheck /></el-icon>
              质控
            </el-button>
          </el-tooltip>
          <!-- 知识图谱快捷入口 -->
          <el-tooltip content="查看实时知识图谱：人物关系、地点、事件等" placement="top">
            <el-button
              type="primary"
              size="small"
              plain
              @click="$emit('show-knowledge-graph')"
            >
              <el-icon><Connection /></el-icon>
              知识图谱
            </el-button>
          </el-tooltip>
          <!-- 一致性检查报告快捷入口 -->
          <el-tooltip content="查看一致性检查报告：人物状态、设施状态、待回收伏笔等" placement="top">
            <el-button
              type="success"
              size="small"
              plain
              @click="$emit('show-consistency-report')"
            >
              <el-icon><DataAnalysis /></el-icon>
              一致性报告
            </el-button>
          </el-tooltip>
          <el-tag type="info" size="small">
            {{ displayUnits.length }} 单元
          </el-tag>
        </div>
      </div>
    </template>

    <el-collapse v-model="collapseModel" class="units-collapse">
      <el-collapse-item
        v-for="unit in displayUnits"
        :key="unit.unit_index"
        :name="unit.unit_index"
        @click="$emit('expand-unit', unit)"
      >
        <template #title>
          <div class="unit-title">
            <span class="unit-index">#{{ unit.unit_index }}</span>
            <span class="unit-name" :title="unit.unit_title">
              {{ unit.unit_title || `单元 ${unit.unit_index}` }}
            </span>
            <el-tag :type="getUnitStatusType(unit.status)" size="small">
              {{ getUnitStatusLabel(unit.status) }}
            </el-tag>
            <!-- 质控状态徽章 -->
            <el-tag
              v-if="unit.quality_control && unit.quality_control.status"
              :type="getQCStatusType(unit.quality_control)"
              size="small"
              effect="plain"
              class="qc-badge"
              @click.stop="$emit('show-unit-qc', unit.unit_index)"
            >
              <el-icon v-if="unit.quality_control.status === 'running'" class="is-loading"><Loading /></el-icon>
              <span v-else-if="unit.quality_control.score">
                {{ unit.quality_control.score }}分
              </span>
              <span v-else>
                {{ getQCStatusLabel(unit.quality_control.status) }}
              </span>
            </el-tag>
            <span v-if="unit.word_count > 0" class="unit-word-count">
              {{ unit.word_count }} 字
            </span>
            <el-button
              v-if="unit.status === 'completed'"
              type="primary"
              size="small"
              link
              @click.stop="$emit('export-unit', unit.unit_index)"
            >
              <el-icon><Download /></el-icon>
            </el-button>
          </div>
        </template>

        <!-- 质控简要信息（展开后显示） -->
        <div
          v-if="unit.quality_control && unit.quality_control.status === 'completed'"
          class="qc-summary-row"
          @click.stop="$emit('show-unit-qc', unit.unit_index)"
        >
          <span class="qc-summary-text">
            <el-icon><CircleCheckFilled /></el-icon>
            质控得分: {{ unit.quality_control.score || 0 }}分
            <span class="qc-issues">{{ unit.quality_control.issues_count || 0 }}个问题</span>
            <span v-if="unit.quality_control.fixed_count" class="qc-fixed">
              {{ unit.quality_control.fixed_count }}个修正已应用
            </span>
          </span>
          <el-button type="primary" size="small" link>
            查看详情
          </el-button>
        </div>

        <!-- 场景列表 -->
        <div
          class="scenes-list"
          v-loading="loadingScenes[unit.unit_index]"
        >
          <div
            v-for="scene in getScenes(unit.unit_index)"
            :key="scene.scene_index"
            class="scene-item"
            @click.stop="$emit('scene-click', scene, unit)"
          >
            <div class="scene-info">
              <span class="scene-index">场景 {{ scene.scene_index }}</span>
              <span class="scene-title">{{ scene.scene_title || "未命名场景" }}</span>
            </div>
            <div class="scene-meta">
              <el-tag
                :type="getSceneStatusType(scene.status)"
                size="small"
              >
                {{ getSceneStatusLabel(scene.status) }}
              </el-tag>
              <span v-if="scene.word_count > 0" class="scene-word-count">
                {{ scene.word_count }} 字
              </span>
            </div>
          </div>
          <el-empty
            v-if="getScenes(unit.unit_index).length === 0 && !loadingScenes[unit.unit_index]"
            description="暂无场景"
            :image-size="40"
          />
        </div>
      </el-collapse-item>
    </el-collapse>

    <el-empty
      v-if="displayUnits.length === 0"
      description="暂无单元数据"
      :image-size="60"
    />
  </el-card>
</template>

<script setup>
import { computed } from "vue";
import {
  List,
  Connection,
  DataAnalysis,
  Download,
  CircleCheck,
  CircleCheckFilled,
  Loading,
} from "@element-plus/icons-vue";
import {
  getSceneStatusType,
  getSceneStatusLabel,
} from "../utils/contentHelpers";

const props = defineProps({
  displayUnits: { type: Array, default: () => [] },
  activeUnits: { type: Array, default: () => [] },
  unitLabel: { type: String, default: "章" },
  loadingScenes: { type: Object, default: () => ({}) },
  scenes: { type: Object, default: () => ({}) },
});

const emit = defineEmits([
  "update:activeUnits",
  "expand-unit",
  "export-unit",
  "scene-click",
  "show-knowledge-graph",
  "show-consistency-report",
  "show-quality-control",
  "show-unit-qc",
]);

const collapseModel = computed({
  get: () => props.activeUnits,
  set: (val) => emit("update:activeUnits", val),
});

function getScenes(unitIndex) {
  return props.scenes[unitIndex] || [];
}

function getUnitStatusType(status) {
  const typeMap = {
    pending: "info",
    processing: "primary",
    completed: "success",
    failed: "danger",
  };
  return typeMap[status] || "info";
}

function getUnitStatusLabel(status) {
  const labelMap = {
    pending: "等待中",
    processing: "处理中",
    completed: "已完成",
    failed: "失败",
  };
  return labelMap[status] || status;
}

// 质控状态类型（基于得分）
function getQCStatusType(qc) {
  if (qc.status === "running") return "primary";
  if (qc.status === "failed") return "danger";
  const score = qc.score || 0;
  if (score >= 80) return "success";
  if (score >= 60) return "warning";
  return "danger";
}

// 质控状态标签
function getQCStatusLabel(status) {
  const labelMap = {
    pending: "待质控",
    running: "检测中",
    completed: "已完成",
    failed: "失败",
  };
  return labelMap[status] || status;
}
</script>

<style lang="scss" scoped>
.units-panel {
  height: 100%;
  min-height: 500px;

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .el-icon {
      margin-right: 4px;
    }

    .panel-header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }
  }

  .units-collapse {
    .unit-title {
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 1;
      padding-right: 16px;

      .unit-index {
        font-weight: 600;
        color: #409eff;
        min-width: 40px;
      }

      .unit-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .qc-badge {
        cursor: pointer;
        transition: transform 0.2s;

        &:hover {
          transform: scale(1.1);
        }
      }

      .unit-word-count {
        font-size: 12px;
        color: #909399;
      }
    }

    .qc-summary-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      margin-bottom: 8px;
      background: #fdf6ec;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.2s;

      &:hover {
        background: #faecd8;
      }

      .qc-summary-text {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;

        .el-icon {
          color: #e6a23c;
        }

        .qc-issues {
          color: #909399;
        }

        .qc-fixed {
          color: #67c23a;
        }
      }
    }

    .scenes-list {
      padding: 8px 0;

      .scene-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        margin-bottom: 8px;
        background: #f5f7fa;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s;

        &:hover {
          background: #ecf5ff;
        }

        .scene-info {
          display: flex;
          flex-direction: column;
          gap: 2px;

          .scene-index {
            font-size: 12px;
            color: #909399;
          }

          .scene-title {
            font-size: 13px;
            color: #303133;
          }
        }

        .scene-meta {
          display: flex;
          align-items: center;
          gap: 8px;

          .scene-word-count {
            font-size: 12px;
            color: #909399;
          }
        }
      }
    }
  }
}
</style>
