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

        <!-- 单元内容显示区域（v3.1新增 - 默认显示QC修正稿） -->
        <div
          v-if="hasUnitContent(unit)"
          class="unit-content-area"
        >
          <div class="unit-content-header">
            <span class="content-version-tag">
              <el-tag v-if="isShowingFixedVersion(unit)" type="success" size="small" effect="plain">
                <el-icon><CircleCheckFilled /></el-icon>修正稿
              </el-tag>
              <el-tag v-else type="info" size="small" effect="plain">初稿</el-tag>
            </span>
            <span class="content-word-count" v-if="getDisplayContent(unit)">
              {{ getDisplayContent(unit).length }} 字
            </span>
            <div class="content-actions">
              <el-button v-if="!isEditingUnit(unit.unit_index)" type="primary" size="small" plain @click.stop="startEditUnit(unit)">
                <el-icon><Edit /></el-icon> 编辑内容
              </el-button>
              <template v-else>
                <el-button type="success" size="small" @click.stop="saveUnitEdit(unit)" :loading="savingEdits[unit.unit_index]">
                  <el-icon><Check /></el-icon> 保存修改
                </el-button>
                <el-button size="small" @click.stop="cancelUnitEdit(unit)">
                  <el-icon><Close /></el-icon> 取消
                </el-button>
              </template>
            </div>
          </div>
          <div class="unit-content-body">
            <el-input
              v-if="isEditingUnit(unit.unit_index)"
              v-model="editContents[unit.unit_index]"
              type="textarea"
              :rows="15"
              placeholder="请输入单元内容..."
            />
            <div v-else class="content-preview markdown-content" v-html="renderMarkdown(getDisplayContent(unit))"></div>
          </div>
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
import { ref, computed } from "vue";
import {
  List,
  Connection,
  DataAnalysis,
  Download,
  CircleCheck,
  CircleCheckFilled,
  Loading,
  Edit,
  Check,
  Close,
} from "@element-plus/icons-vue";
import { marked } from "marked";
import {
  getSceneStatusType,
  getSceneStatusLabel,
} from "../utils/contentHelpers";
import { novelWriterApi } from "@/api/novel-writer";
import { ElMessage } from "element-plus";
import { useWritingTaskStore } from "@/stores/writingTask";

const writingStore = useWritingTaskStore();

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
  "unit-content-updated",
]);

const collapseModel = computed({
  get: () => props.activeUnits,
  set: (val) => emit("update:activeUnits", val),
});

// ==================== 内容编辑状态 ====================
const editingUnitIndex = ref(null);
const editContents = ref({});
const savingEdits = ref({});

function isEditingUnit(unitIndex) {
  return editingUnitIndex.value === unitIndex;
}

function startEditUnit(unit) {
  editingUnitIndex.value = unit.unit_index;
  editContents.value[unit.unit_index] = getDisplayContent(unit);
}

function cancelUnitEdit(unit) {
  editingUnitIndex.value = null;
  delete editContents.value[unit.unit_index];
}

async function saveUnitEdit(unit) {
  const newContent = editContents.value[unit.unit_index];
  if (!newContent || newContent.trim() === '') {
    ElMessage.warning('内容不能为空');
    return;
  }

  const projectId = writingStore.currentTask?.project_id;
  if (!projectId) {
    ElMessage.error('无法获取项目ID，请刷新页面后重试');
    return;
  }

  savingEdits.value[unit.unit_index] = true;
  try {
    await novelWriterApi.updateUnitContent({
      unit_index: unit.unit_index,
      content: newContent,
      project_id: projectId
    });

    // 本地立即更新 unit 内容
    unit.final_content = newContent;
    unit.word_count = newContent.length;

    // 同步更新 quality_control 中的修正稿
    if (unit.quality_control) {
      unit.quality_control.content_after_qc_fix = newContent;
      unit.quality_control.fixed_content = newContent;
    }

    ElMessage.success('内容已保存');
    editingUnitIndex.value = null;
    delete editContents.value[unit.unit_index];

    emit('unit-content-updated', {
      unit_index: unit.unit_index,
      content: newContent
    });
  } catch (error) {
    console.error('[UnitListPanel] 保存内容失败:', error);
    ElMessage.error('保存失败: ' + (error.message || '未知错误'));
  } finally {
    savingEdits.value[unit.unit_index] = false;
  }
}

// ==================== 内容显示逻辑 ====================

/**
 * 获取单元展示内容
 * 优先级：content_after_qc_fix (修正稿) > fixed_content > final_content
 */
function getDisplayContent(unit) {
  if (!unit) return '';
  const qc = unit.quality_control;
  if (qc) {
    // 优先显示QC修正稿
    if (qc.content_after_qc_fix) return qc.content_after_qc_fix;
    if (qc.fixed_content) return qc.fixed_content;
  }
  // 回退到 final_content
  return unit.final_content || '';
}

/** 判断是否有内容可显示 */
function hasUnitContent(unit) {
  return !!getDisplayContent(unit);
}

/** 判断当前显示的是否为修正稿 */
function isShowingFixedVersion(unit) {
  const qc = unit.quality_control;
  return !!(qc && (qc.content_after_qc_fix || qc.fixed_content));
}

/** Markdown渲染 */
function renderMarkdown(text) {
  if (!text) return '';
  try {
    return marked.parse(text);
  } catch {
    return text;
  }
}

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
        min-width: 0; // 允许收缩
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
  
      .qc-badge {
        cursor: pointer;
        transition: transform 0.2s;
        flex-shrink: 0; // 防止被压缩
  
        &:hover {
          transform: scale(1.1);
        }
      }
  
      .unit-word-count {
        font-size: 12px;
        color: #909399;
        flex-shrink: 0; // 防止被压缩
        white-space: nowrap; // 防止换行
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

    .unit-content-area {
      margin-bottom: 12px;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      overflow: hidden;

      .unit-content-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 12px;
        background: #fafafa;
        border-bottom: 1px solid #ebeef5;

        .content-version-tag {
          flex-shrink: 0;
        }

        .content-word-count {
          font-size: 12px;
          color: #909399;
          flex-shrink: 0;
        }

        .content-actions {
          margin-left: auto;
          display: flex;
          gap: 8px;
        }
      }

      .unit-content-body {
        padding: 12px;

        .content-preview {
          max-height: 400px;
          overflow-y: auto;
          font-size: 14px;
          line-height: 1.8;
          color: #303133;
          white-space: pre-wrap;
          word-break: break-word;

          :deep(p) {
            margin-bottom: 8px;
          }

          :deep(h1), :deep(h2), :deep(h3),
          :deep(h4), :deep(h5), :deep(h6) {
            margin-top: 12px;
            margin-bottom: 8px;
            font-weight: 600;
          }

          :deep(ul), :deep(ol) {
            padding-left: 20px;
            margin-bottom: 8px;
          }
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
