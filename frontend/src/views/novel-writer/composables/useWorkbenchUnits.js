/**
 * useWorkbenchUnits - 单元列表和项目数据管理
 *
 * 处理 WritingWorkbench 中的项目数据加载、单元列表展示、场景管理等功能
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'
import { writingTaskApi } from '@/api/writing-task'

/**
 * @param {Object} props - 组件 props
 * @param {Object} writingStore - writingTask Store
 * @param {Function} emit - emit 函数
 * @param {import('vue').ComputedRef} projectIdRef - 项目ID计算属性（来自父组件）
 */
export function useWorkbenchUnits(props, writingStore, emit, projectIdRef) {
  // ==================== 响应式状态 ====================
  const localProjectData = ref({})
  const loadingProject = ref(false)
  const loadingScenes = ref({})
  const sceneDialogVisible = ref(false)
  const selectedScene = ref(null)
  const selectedUnit = ref(null)

  // ==================== 计算属性 ====================

  // 获取实际的内容类型（优先使用本地加载的项目数据）
  const actualContentType = computed(() => {
    // 优先使用本地加载的项目数据
    if (localProjectData.value?.content_type) {
      return localProjectData.value.content_type;
    }
    // 回退到 props
    return props.contentType || props.projectType || "novel";
  });

  // 根据项目类型获取单元标签
  const unitLabel = computed(() => {
    switch (actualContentType.value) {
      case "series_script":
        return "集";
      case "movie_script":
        return "场";
      default:
        return "章";
    }
  });

  // 是否为小说类型（用于字数控制组件的条件渲染）
  const isNovelType = computed(() => {
    return actualContentType.value === "novel";
  });

  // 剧本类型的时长标签
  const durationLabel = computed(() => {
    switch (actualContentType.value) {
      case "series_script":
        return "单集时长";
      case "movie_script":
        return "单场时长";
      default:
        return "时长控制";
    }
  });

  // 剧本类型的时长提示
  const durationHint = computed(() => {
    switch (actualContentType.value) {
      case "series_script":
        return "剧本按场景时长自动控制，无需手动设置字数";
      case "movie_script":
        return "电影剧本按时长分配场景，字数自动计算";
      default:
        return "剧本按时长控制生成";
    }
  });

  // 合并后的项目数据（优先使用props传入的，其次使用本地加载的）
  const projectData = computed(() => {
    return props.projectData && Object.keys(props.projectData).length > 0
      ? props.projectData
      : localProjectData.value;
  });

  // 项目总单元数（计算属性）
  const projectTotalUnits = computed(() => {
    if (props.projectTotalUnits && props.projectTotalUnits > 0) {
      return props.projectTotalUnits;
    }
    return projectData.value?.total_chapters || 0;
  });

  // 单元概述数据
  const unitSummaries = computed(() => {
    if (props.unitSummaries && Object.keys(props.unitSummaries).length > 0) {
      return props.unitSummaries;
    }
    return projectData.value?.unit_summaries || {};
  });

  // 是否有单元概述
  const hasUnitSummaries = computed(() => {
    return unitSummaries.value && Object.keys(unitSummaries.value).length > 0;
  });

  // 获取当前起始单元的名称
  const currentUnitName = computed(() => {
    const unitIndex = props.taskForm?.start_from || 1;
    if (unitSummaries.value && unitSummaries.value[unitIndex]) {
      return (
        unitSummaries.value[unitIndex].title || unitSummaries.value[unitIndex]
      );
    }
    return `第${unitIndex}${unitLabel.value}`;
  });

  // 显示的单元列表 - 合并 store.units 和 unitSummaries
  const displayUnits = computed(() => {
    // 如果有任务，优先使用 store 中的单元列表
    if (writingStore.currentTask && writingStore.units.length > 0) {
      return writingStore.units;
    }

    // 如果没有任务但有 unitSummaries，从 unitSummaries 构建初始列表
    if (unitSummaries.value && Object.keys(unitSummaries.value).length > 0) {
      return Object.entries(unitSummaries.value)
        .map(([index, summary]) => ({
          unit_index: parseInt(index),
          unit_title:
            typeof summary === "string"
              ? summary
              : summary?.title || `第${index}${unitLabel.value}`,
          unit_summary:
            typeof summary === "string" ? null : summary?.summary || null,
          status: "pending",
          word_count: 0,
        }))
        .sort((a, b) => a.unit_index - b.unit_index);
    }

    // 如果没有 unitSummaries 但有 chapters，从 chapters 构建列表
    if (props.chapters && props.chapters.length > 0) {
      return props.chapters
        .map((chapter) => ({
          unit_index: chapter.chapter_number,
          unit_title: chapter.chapter_title,
          unit_summary: null,
          status: "pending",
          word_count: chapter.word_count || 0,
        }))
        .sort((a, b) => a.unit_index - b.unit_index);
    }

    // 如果有 projectTotalUnits，生成占位列表
    if (projectTotalUnits.value > 0) {
      return Array.from({ length: projectTotalUnits.value }, (_, i) => ({
        unit_index: i + 1,
        unit_title: `第${i + 1}${unitLabel.value}`,
        unit_summary: null,
        status: "pending",
        word_count: 0,
      }));
    }

    return [];
  });

  // 是否有已生成的内容
  const hasGeneratedContent = computed(() => {
    // 检查 store 中是否有已完成的单元
    if (writingStore.units && writingStore.units.length > 0) {
      return writingStore.units.some(
        (u) => u.status === "completed" && u.word_count > 0,
      );
    }
    return false;
  });

  // 是否可以继续生成（任务完成且有更多单元可生成）
  const canContinueGenerate = computed(() => {
    if (!writingStore.currentTask || !writingStore.isCompleted) return false;

    // 检查是否还有未生成的单元
    const completedUnits = writingStore.currentTask.completed_units || 0;
    const totalUnits =
      projectTotalUnits.value ||
      Object.keys(unitSummaries.value || {}).length ||
      props.chapters?.length ||
      0;

    return totalUnits > completedUnits;
  });

  // 选中的场景标题
  const selectedSceneTitle = computed(() => {
    if (!selectedScene.value) return "";
    const unitIdx = selectedUnit.value?.unit_index || "";
    const sceneIdx = selectedScene.value.scene_index;
    const sceneTitle = selectedScene.value.scene_title || `场景 ${sceneIdx}`;
    return `单元 ${unitIdx} - ${sceneTitle}`;
  });

  // ==================== 方法 ====================

  // 加载项目数据
  async function loadProjectData() {
    const pid = projectIdRef?.value || props.projectId;
    if (!pid) return;

    loadingProject.value = true;
    try {
      const res = await novelWriterApi.getProject(pid);
      if (res.success) {
        localProjectData.value = res.data;
      }
    } catch (error) {
      ElMessage.error("加载项目数据失败");
    } finally {
      loadingProject.value = false;
    }
  }

  // 处理单元展开
  async function handleUnitExpand(unit) {
    // 如果已经加载过，不再重复加载
    if (writingStore.scenes[unit.unit_index]) return;

    loadingScenes.value[unit.unit_index] = true;
    await writingStore.fetchScenes(writingStore.currentTask.id, unit.unit_index);
    loadingScenes.value[unit.unit_index] = false;
  }

  // 获取场景列表
  function getScenes(unitIndex) {
    return writingStore.scenes[unitIndex] || [];
  }

  // 导出单个单元内容
  async function handleExportUnit(unitIndex) {
    try {
      const taskId = writingStore.currentTask?.id;
      if (!taskId) {
        ElMessage.warning("没有正在进行的任务");
        return;
      }

      const response = await writingTaskApi.exportUnit(taskId, unitIndex, "txt");
      const blob = new Blob([response.data || response], {
        type: "text/plain;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;

      // 从单元列表获取单元标题
      const unit = displayUnits.value.find((u) => u.unit_index === unitIndex);
      const unitTitle = unit?.unit_title || `第${unitIndex}${unitLabel.value}`;
      a.download = `${unitTitle}.txt`;

      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      ElMessage.success("下载成功");
    } catch (error) {
      console.error("导出单元失败:", error);
      ElMessage.error("导出失败: " + (error.message || "未知错误"));
    }
  }

  // 处理场景点击
  function handleSceneClick(scene, unit) {
    selectedScene.value = scene;
    selectedUnit.value = unit;
    sceneDialogVisible.value = true;
  }

  // 点击单元项
  function handleUnitItemClick(unit, taskForm) {
    // 设置为起始单元
    if (taskForm) {
      taskForm.start_from = unit.unit_index;
    }
  }

  // 获取单元状态类型
  function getUnitStatusType(status) {
    const typeMap = {
      pending: "info",
      processing: "primary",
      completed: "success",
      failed: "danger",
    };
    return typeMap[status] || "info";
  }

  // 获取单元状态标签
  function getUnitStatusLabel(status) {
    const labelMap = {
      pending: "等待中",
      processing: "处理中",
      completed: "已完成",
      failed: "失败",
    };
    return labelMap[status] || status;
  }

  return {
    // 状态
    localProjectData,
    loadingProject,
    loadingScenes,
    sceneDialogVisible,
    selectedScene,
    selectedUnit,

    // 计算属性
    actualContentType,
    unitLabel,
    isNovelType,
    durationLabel,
    durationHint,
    projectData,
    projectTotalUnits,
    unitSummaries,
    hasUnitSummaries,
    currentUnitName,
    displayUnits,
    hasGeneratedContent,
    canContinueGenerate,
    selectedSceneTitle,

    // 方法
    loadProjectData,
    handleUnitExpand,
    getScenes,
    handleExportUnit,
    handleSceneClick,
    handleUnitItemClick,
    getUnitStatusType,
    getUnitStatusLabel,
  }
}
