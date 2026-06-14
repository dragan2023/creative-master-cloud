<template>
  <el-card class="units-panel" shadow="hover">
    <template #header>
      <div class="panel-header">
        <span>
          <el-icon><List /></el-icon>
          单元列表
        </span>
        <div class="panel-header-actions">
          <!-- 质控快捷入口 - v4.0优化: 仅小说类型显示 -->
          <el-tooltip v-if="isNovelType" content="正文质量管控：检测问题、应用修正、查看报告" placement="top">
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
            <!-- 质控状态徽章 - v4.0优化: 仅小说类型显示 -->
            <el-tag
              v-if="isNovelType && unit.quality_control && unit.quality_control.status"
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
            <!-- 合规提醒徽章（敏感实体检测） -->
            <el-tag
              v-if="getComplianceIssueCount(unit) > 0"
              type="info"
              size="small"
              effect="plain"
              class="compliance-badge"
              @click.stop="$emit('show-unit-qc', unit.unit_index)"
            >
              <el-icon><WarningFilled /></el-icon>
              <span>{{ getComplianceIssueCount(unit) }}个敏感实体</span>
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

        <!-- 质控简要信息（展开后显示）- v4.0优化: 仅小说类型显示 -->
        <div
          v-if="isNovelType && unit.quality_control && unit.quality_control.status === 'completed'"
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

        <!-- 单元内容版本入口（v4.0重构 - 弹窗化展示） -->
        <div
          v-if="hasUnitContent(unit)"
          class="unit-content-versions"
          :key="'ver-' + unit.unit_index + '-' + versionRefreshKey"
        >
          <div class="versions-header">内容版本</div>
          <div class="versions-list">
            <div
              v-if="getVersionContent(unit, 'draft')"
              class="version-item"
            >
              <div class="version-item-main" @click.stop="openPreview(unit, 'draft')">
                <el-icon><Document /></el-icon>
                <span class="version-label">初稿</span>
                <span class="version-meta">{{ getVersionContent(unit, 'draft').length }} 字</span>
              </div>
              <el-button
                v-if="isScriptType(unit)"
                class="generate-ai-btn"
                type="success"
                size="small"
                plain
                :loading="aiGeneratingUnits[unit.unit_index + '-draft']"
                @click.stop="handleGenerateAIResource(unit, 'draft')"
              >
                生成AI资源
              </el-button>
            </div>
            <!-- v4.0优化: qc_fix版本仅小说类型显示，剧本类型不展示 -->
            <div
              v-if="isNovelType && getVersionContent(unit, 'qc_fix')"
              class="version-item qc-fix"
            >
              <div class="version-item-main" @click.stop="openPreview(unit, 'qc_fix')">
                <el-icon><CircleCheckFilled /></el-icon>
                <span class="version-label">修正稿</span>
                <span class="version-meta">{{ getVersionContent(unit, 'qc_fix').length }} 字</span>
              </div>
              <el-button
                v-if="isScriptType(unit)"
                class="generate-ai-btn"
                type="success"
                size="small"
                plain
                :loading="aiGeneratingUnits[unit.unit_index + '-qc_fix']"
                @click.stop="handleGenerateAIResource(unit, 'qc_fix')"
              >
                生成AI资源
              </el-button>
            </div>
            <div
              v-if="getVersionContent(unit, 'self_revise')"
              class="version-item self-revise"
            >
              <div class="version-item-main" @click.stop="openPreview(unit, 'self_revise')">
                <el-icon><EditPen /></el-icon>
                <span class="version-label">自主修订稿</span>
                <span class="version-meta">{{ getVersionContent(unit, 'self_revise').length }} 字</span>
              </div>
              <el-button
                v-if="isScriptType(unit)"
                class="generate-ai-btn"
                type="success"
                size="small"
                plain
                :loading="aiGeneratingUnits[unit.unit_index + '-self_revise']"
                @click.stop="handleGenerateAIResource(unit, 'self_revise')"
              >
                生成AI资源
              </el-button>
            </div>
          </div>
        </div>

        <!-- AI资源版本入口（v4.1新增 - 独立于正文存储） -->
        <div
          v-if="getAIResourceContent(unit)"
          class="unit-content-versions ai-resource-section"
          :key="'ai-' + unit.unit_index + '-' + versionRefreshKey"
        >
          <div class="versions-header">AI视觉资源</div>
          <div class="versions-list">
            <div
              class="version-item ai-resource"
              @click.stop="openPreview(unit, 'ai_resource')"
            >
              <el-icon><PictureFilled /></el-icon>
              <span class="version-label">AI资源</span>
              <span class="version-meta">{{ getAIResourceContent(unit).length }} 字</span>
            </div>
          </div>
        </div>


      </el-collapse-item>
    </el-collapse>

    <el-empty
      v-if="displayUnits.length === 0"
      description="暂无单元数据"
      :image-size="60"
    />
    <!-- 内容预览弹窗（统一展示初稿/修正稿/自主修订稿） -->
    <ContentPreviewDialog
      v-model:visible="showPreviewDialog"
      :unit="previewUnit"
      :project-id="writingStore.currentTask?.project_id || 0"
      :target-version="previewTargetVersion"
      :content-type="contentType"
      @content-updated="handlePreviewContentUpdated"
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
  EditPen,
  Document,
  WarningFilled,
  PictureFilled,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useWritingTaskStore } from "@/stores/writingTask";
import { novelWriterApi } from "@/api/novel-writer";
import ContentPreviewDialog from "./ContentPreviewDialog.vue";

const writingStore = useWritingTaskStore();

const props = defineProps({
  displayUnits: { type: Array, default: () => [] },
  activeUnits: { type: Array, default: () => [] },
  unitLabel: { type: String, default: "章" },
  contentType: { type: String, default: "novel" },
});

const emit = defineEmits([
  "update:activeUnits",
  "export-unit",
  "show-knowledge-graph",
  "show-consistency-report",
  "show-quality-control",
  "show-unit-qc",
  "unit-content-updated",
]);

// v4.0优化: 是否为小说类型（用于条件渲染质控相关UI）
const isNovelType = computed(() => {
  return props.contentType === 'novel'
});

const collapseModel = computed({
  get: () => props.activeUnits,
  set: (val) => emit("update:activeUnits", val),
});

// ==================== 内容预览弹窗状态 ====================
const showPreviewDialog = ref(false);
const previewUnit = ref(null);
const previewTargetVersion = ref(null);  // v4.0: 从列表点击时传入的目标版本
/** 版本刷新键 — 内容更新后递增，强制 v-if 重新计算 */
const versionRefreshKey = ref(0);

// ==================== AI资源生成状态 ====================
/** 记录正在进行AI资源生成的单元，key: "unitIndex-version" */
const aiGeneratingUnits = ref({});

function openPreview(unit, version) {
  previewUnit.value = unit;
  previewTargetVersion.value = version || null;
  showPreviewDialog.value = true;
}

function handlePreviewContentUpdated(data) {
  // 递增刷新键，强制 version items 的 v-if 重新求值
  versionRefreshKey.value++;
  emit('unit-content-updated', data);
}

// ==================== 内容显示逻辑 ====================

/**
 * 获取指定版本的内容
 * 
 * 三个内容版本的语义（不可混用）：
 * - 'draft':      LLM首次输出的完整稿件 → content_after_generation（永不回退到final_content，因QC后final_content已变更）
 * - 'qc_fix':     自动质控修正后的完整稿件 → content_after_qc_fix
 * - 'self_revise': 用户对话修正后的完整稿件 → content_after_self_revise
 * 
 * @param unit 单元对象
 * @param version 版本标识: 'draft' | 'qc_fix' | 'self_revise'
 */
function getVersionContent(unit, version) {
  if (!unit) return '';
  const qc = unit.quality_control;
  switch (version) {
    case 'self_revise':
      // qc对象优先，top-level字段作为回退
      return qc?.content_after_self_revise || unit.content_after_self_revise || '';
    case 'qc_fix':
      // qc对象优先，top-level字段作为回退；fixed_content是旧字段，作为最后回退
      return qc?.content_after_qc_fix || unit.content_after_qc_fix || qc?.fixed_content || '';
    case 'draft':
      // 初稿永不回退到final_content（QC修正后final_content已是修正稿）
      // 仅从content_after_generation字段读取
      return qc?.content_after_generation || unit.content_after_generation || '';
    default:
      return '';
  }
}

/**
 * 获取单元展示内容
 * 优先级：content_after_self_revise > content_after_qc_fix > content_after_generation > final_content
 */
function getDisplayContent(unit) {
  if (!unit) return '';
  const qc = unit.quality_control;
  if (qc) {
    if (qc.content_after_self_revise) return qc.content_after_self_revise;
    if (qc.content_after_qc_fix) return qc.content_after_qc_fix;
    if (qc.content_after_generation) return qc.content_after_generation;
  }
  // top-level 回退（与qc字段顺序一致）
  if (unit.content_after_self_revise) return unit.content_after_self_revise;
  if (unit.content_after_qc_fix) return unit.content_after_qc_fix;
  if (unit.content_after_generation) return unit.content_after_generation;
  // 最终回退：无版本字段时使用 final_content
  return unit.final_content || '';
}

/** 判断是否有内容可显示 */
function hasUnitContent(unit) {
  return !!getDisplayContent(unit);
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

// v4.0优化: 保留getQCStatusType/getQCStatusLabel方法供小说类型使用
// 剧本类型不会显示相关UI，但方法定义保留以避免引用错误

/**
 * 获取合规提醒（敏感实体检测）数量
 * 优先从 quality_control.compliance_issue_count 读取（WS推送），
 * 回退到从 issues 列表中统计 is_compliance 标记
 */
function getComplianceIssueCount(unit) {
  if (!unit?.quality_control) return 0
  const qc = unit.quality_control
  // 优先使用 WS 推送的计数
  if (typeof qc.compliance_issue_count === 'number') return qc.compliance_issue_count
  // 回退：从 issues 列表统计
  const issues = qc.issues || []
  return issues.filter(i => i.is_compliance).length
}

// ==================== AI资源功能 ====================

/**
 * 获取AI视觉资源内容
 * 从 unit.ai_resource_content 字段读取（独立于正文存储）
 */
function getAIResourceContent(unit) {
  if (!unit) return ''
  return unit.ai_resource_content || ''
}

/**
 * 判断是否为剧本类型（剧集/电影）
 * 只有剧本类型才显示"生成AI资源"按钮
 */
function isScriptType(unit) {
  if (!unit) return false
  // v2.7: content_type 存储在 WritingTask.config 中，不在 WritingUnit 上
  const taskContentType = writingStore.currentTask?.config?.content_type || writingStore.currentTask?.content_type || ''
  return taskContentType === 'series_script' || taskContentType === 'movie_script' || taskContentType === 'script'
}

/**
 * 处理"生成AI资源"按钮点击
 * 调用SSE流式API生成AI视觉资源
 */
async function handleGenerateAIResource(unit, sourceVersion) {
  const projectId = writingStore.currentTask?.project_id
  if (!projectId) {
    ElMessage.error('无法获取项目ID')
    return
  }

  const versionLabels = { draft: '初稿', qc_fix: '修正稿', self_revise: '自主修订稿' }
  const versionLabel = versionLabels[sourceVersion] || sourceVersion

  const generateKey = unit.unit_index + '-' + sourceVersion
  aiGeneratingUnits.value = { ...aiGeneratingUnits.value, [generateKey]: true }

  try {
    const { promise } = novelWriterApi.generateAIResource(
      projectId,
      unit.unit_index,
      sourceVersion,
      (chunk) => {
        // onChunk - 流式输出中，可在这里做进度更新
      },
      (result) => {
        // onDone - 生成完成
        ElMessage.success(`第${unit.unit_index}单元(${versionLabel})AI资源生成完成`)
        // 刷新store中的单元数据
        refreshUnitData(unit.unit_index, result)
        versionRefreshKey.value++
      },
      (error) => {
        // onError
        ElMessage.error(`AI资源生成失败: ${error.message}`)
      }
    )
    await promise
  } catch (error) {
    console.error('[UnitListPanel] AI资源生成失败:', error)
    ElMessage.error('AI资源生成失败: ' + (error.message || '未知错误'))
  } finally {
    aiGeneratingUnits.value = { ...aiGeneratingUnits.value, [generateKey]: false }
  }
}

/**
 * 生成完成后刷新store中的单元数据
 */
function refreshUnitData(unitIndex, result) {
  const unitIdx = writingStore.units.findIndex(u => u.unit_index === unitIndex)
  if (unitIdx !== -1 && result?.content) {
    const storeUnit = writingStore.units[unitIdx]
    storeUnit.ai_resource_content = result.content
  }
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

      .compliance-badge {
        cursor: pointer;
        transition: transform 0.2s;
        flex-shrink: 0;
        background: #ecf5ff !important;
        border-color: #b3d8ff !important;
        color: #409eff !important;

        .el-icon {
          margin-right: 2px;
        }
  
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

    .unit-content-versions {
      margin-bottom: 12px;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      overflow: hidden;

      .versions-header {
        padding: 6px 12px;
        font-size: 12px;
        color: #909399;
        background: #fafafa;
        border-bottom: 1px solid #ebeef5;
      }

      .versions-list {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: 4px;
      }

      .version-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 4px;
        padding: 8px 12px;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s;
        font-size: 13px;

        &:hover {
          background: #ecf5ff;
        }

        .version-item-main {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;
          min-width: 0;
        }

        .generate-ai-btn {
          flex-shrink: 0;
          font-size: 11px;
          padding: 4px 8px;
        }

        .el-icon {
          font-size: 14px;
          color: #909399;
          flex-shrink: 0;
        }

        .version-label {
          font-weight: 500;
          color: #303133;
          flex: 1;
          min-width: 0;
        }

        .version-meta {
          font-size: 12px;
          color: #909399;
          flex-shrink: 0;
        }

        &.qc-fix {
          .el-icon {
            color: #67c23a;
          }
        }

        &.self-revise {
          .el-icon {
            color: #409eff;
          }
        }

        &.ai-resource {
          .el-icon {
            color: #e6a23c;
          }
        }
      }
    }

    .ai-resource-section {
      border-color: #e6a23c33;
      
      .versions-header {
        color: #e6a23c;
      }
    }


  }
}
</style>
