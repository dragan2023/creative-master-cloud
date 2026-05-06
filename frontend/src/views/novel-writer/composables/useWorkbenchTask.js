/**
 * useWorkbenchTask - 任务创建和管理
 *
 * 处理 WritingWorkbench 中的任务创建、中断、续传、删除、导出等操作
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'
import { writingTaskApi } from '@/api/writing-task'
import { agentConfigs } from '../config/agentConfig'

/**
 * @param {Object} options - 配置选项
 * @param {Object} options.writingStore - writingTask Store
 * @param {import('vue').ComputedRef} options.projectId - 项目ID（计算属性）
 * @param {Object} options.styleMgmt - useStyleManagement 的返回值
 * @param {import('vue').ComputedRef} options.projectTotalUnits - 项目总单元数
 * @param {import('vue').ComputedRef} options.unitSummaries - 单元概述数据
 * @param {import('vue').Ref} options.chapters - 章节列表（可能来自 props）
 * @param {Function} options.emit - emit 函数
 * @param {Function} options.loadProjectData - 重新加载项目数据的函数
 */
export function useWorkbenchTask(options) {
  const {
    writingStore,
    projectId,
    styleMgmt,
    projectTotalUnits,
    unitSummaries,
    chapters,
    emit,
    loadProjectData,
    actualContentType,
  } = options

  // ==================== 知识库状态（P1改造新增） ====================
  const kbStatus = ref({ status: 'pending' })
  const buildingKb = ref(false)

  // 加载知识库状态（延迟加载，不在初始化时调用）
  async function loadKbStatus() {
    try {
      const res = await novelWriterApi.getKnowledgeBaseStatus(projectId.value)
      if (res.success) {
        kbStatus.value = res.data
      }
    } catch (error) {
      console.warn('加载知识库状态失败:', error)
    }
  }

  // 注意：不在初始化时立即加载知识库状态，避免触发向量库初始化
  // 由调用方在需要时手动调用 loadKbStatus()

  // ==================== 表单 ====================
  const taskForm = ref({
    start_from: 1,
    unit_count: null,
    words_per_chapter: 3000,
    concurrency: 3,
    generation_mode: "direct",
    agent_models: {
      orchestrator: "",
      structural: "",
      writer: "",
      logic_editor: "",
      style_editor: "",
      compliance: "",
      knowledge: "",
    },
    agent_temps: {
      orchestrator: 0.3,
      structural: 0.6,
      writer: 0.8,
      logic_editor: 0.2,
      style_editor: 0.6,
      compliance: 0.1,
      knowledge: 0.3,
    },
    agent_providers: {
      orchestrator: "",
      structural: "",
      writer: "",
      logic_editor: "",
      style_editor: "",
      compliance: "",
      knowledge: "",
    },
    agent_api_bases: {
      orchestrator: "",
      structural: "",
      writer: "",
      logic_editor: "",
      style_editor: "",
      compliance: "",
      knowledge: "",
    },
    agent_api_keys: {
      orchestrator: "",
      structural: "",
      writer: "",
      logic_editor: "",
      style_editor: "",
      compliance: "",
      knowledge: "",
    },
    agent_config_ids: {
      orchestrator: null,
      structural: null,
      writer: null,
      logic_editor: null,
      style_editor: null,
      compliance: null,
      knowledge: null,
    },
    // 剧集/电影专属参数（Task 8）
    series_type: '电视剧',
    episode_duration_min: 30,
    episode_duration_max: 45,
    scenes_per_episode_range: null,
    movie_type: '电影',
    scene_duration_min: 10,
    scene_duration_max: 15,
    total_scenes: 0,
    script_mode: 'real',
  })

  // ==================== 响应式状态 ====================
  const showOutlineUploadDialog = ref(false)
  const uploadingOutline = ref(false)
  const showUnitSummariesUploadDialog = ref(false)
  const unitSummariesUploadMode = ref('file')
  const unitSummariesInput = ref('')
  const globalOutlineInput = ref('')
  const uploadingUnitSummaries = ref(false)
  const generatingDirectory = ref(false)
  const showContinueDialog = ref(false)
  const continueUnitCount = ref(1)

  // ==================== 方法 ====================

  // 测试Agent连接
  async function handleTestConnection(agentRole) {
    const modelId = taskForm.value.agent_models[agentRole];
    const provider = taskForm.value.agent_providers[agentRole];

    if (!modelId || !provider) {
      ElMessage.warning("请先填写模型ID和供应商");
      return;
    }

    const testingAgent = {}
    testingAgent[agentRole] = true;
    try {
      const config = {
        model_id: modelId,
        provider: provider,
        api_base: taskForm.value.agent_api_bases[agentRole] || undefined,
        api_key: taskForm.value.agent_api_keys[agentRole] || undefined,
      };
      const res = await writingStore.testConnection(config);
      if (res?.success) {
        ElMessage.success("连接成功");
      } else {
        ElMessage.error(res?.message || "连接失败");
      }
    } catch (error) {
      ElMessage.error("测试连接失败: " + (error.message || "未知错误"));
    } finally {
      testingAgent[agentRole] = false;
    }
  }

  /**
   * Task 8: 按内容类型构建专属配置参数
   * 将风格选择器数据和类型专属参数嵌入到任务config中
   */
  function buildTypeSpecificConfig() {
    const ct = actualContentType?.value || 'novel'

    if (ct === 'series_script') {
      return {
        content_type: 'series_script',
        series_type: taskForm.value.series_type || '电视剧',
        episode_duration_range: [
          taskForm.value.episode_duration_min || 30,
          taskForm.value.episode_duration_max || 45
        ],
        scenes_per_episode_range: taskForm.value.scenes_per_episode_range || null,
        series_style_dimensions: styleMgmt?.seriesStyleData?.value?.dimensions || {},
        series_style_names: styleMgmt?.seriesStyleData?.value?.selectedNames || [],
        series_style_intensity: styleMgmt?.seriesStyleData?.value?.intensity || 0.7,
        series_style_type: styleMgmt?.seriesStyleData?.value?.seriesSubType || 'long',
        script_mode: taskForm.value.script_mode || 'real',
      }
    }

    if (ct === 'movie_script') {
      return {
        content_type: 'movie_script',
        movie_type: taskForm.value.movie_type || '电影',
        duration_range: [
          taskForm.value.scene_duration_min || 10,
          taskForm.value.scene_duration_max || 15
        ],
        total_scenes: taskForm.value.total_scenes || 0,
        movie_style_dimensions: styleMgmt?.movieStyleData?.value?.dimensions || {},
        movie_style_names: styleMgmt?.movieStyleData?.value?.selectedNames || [],
        movie_style_intensity: styleMgmt?.movieStyleData?.value?.intensity || 0.7,
        script_mode: taskForm.value.script_mode || 'real',
      }
    }

    // novel 类型无需额外参数
    return { content_type: 'novel' }
  }

  // 创建任务
  async function handleCreateTask() {
    // 校验配置完整性
    const configurableAgentsList = agentConfigs.filter((a) => a.configurable);
    const unconfigured = configurableAgentsList.filter((a) => {
      const configId = taskForm.value.agent_config_ids[a.role];
      if (configId && configId !== "custom") return false; // 使用预配置，算已配置
      if (configId === "custom") {
        return (
          !taskForm.value.agent_models[a.role] ||
          !taskForm.value.agent_providers[a.role]
        );
      }
      return true; // 未选择任何配置
    });
    if (unconfigured.length > 0) {
      ElMessage.warning(
        `请先配置以下Agent的模型: ${unconfigured.map((a) => a.label).join("、")}`,
      );
      return;
    }

    // 验证并获取正确的项目总单元数
    let actualTotalUnits = projectTotalUnits.value;

    // 如果计算属性为0或无效，从 unitSummaries 或 chapters 计算
    if (!actualTotalUnits || actualTotalUnits <= 0) {
      if (unitSummaries.value && Object.keys(unitSummaries.value).length > 0) {
        actualTotalUnits = Object.keys(unitSummaries.value).length;
      } else if (chapters.value && chapters.value.length > 0) {
        actualTotalUnits = chapters.value.length;
      }
    }

    // 验证起始单元
    const startFrom = taskForm.value.start_from || 1;
    if (startFrom > actualTotalUnits) {
      ElMessage.warning(
        `起始单元 ${startFrom} 超出范围（总单元数: ${actualTotalUnits}）`,
      );
      return;
    }

    // 计算有效 unit_count
    let effectiveUnitCount = taskForm.value.unit_count;
    const availableUnits = actualTotalUnits - startFrom + 1;

    if (!effectiveUnitCount || effectiveUnitCount > availableUnits) {
      effectiveUnitCount = availableUnits;
    }

    console.log(
      `[创建任务] 实际总单元数: ${actualTotalUnits}, 起始: ${startFrom}, 生成数量: ${effectiveUnitCount}`,
    );

    // 构建Agent配置（仅包含可配置且有值的Agent）
    const agentsConfig = {};

    // 遍历所有可配置的Agent
    for (const agent of configurableAgentsList) {
      const configId = taskForm.value.agent_config_ids[agent.role];

      if (configId && configId !== "custom") {
        // 使用预配置模型
        agentsConfig[agent.role] = {
          config_id: configId, // 传预配置ID给后端
          temperature: taskForm.value.agent_temps[agent.role] ?? 0.7,
        };
      } else {
        // 自定义配置（保持原有逻辑）
        agentsConfig[agent.role] = {
          model: taskForm.value.agent_models[agent.role] || "",
          provider: taskForm.value.agent_providers[agent.role] || "",
          temperature: taskForm.value.agent_temps[agent.role] ?? 0.7,
          api_base: taskForm.value.agent_api_bases[agent.role] || undefined,
          api_key: taskForm.value.agent_api_keys[agent.role] || undefined,
        };
      }
    }

    const task = await writingStore.createTask(projectId.value, {
      start_from: startFrom,
      unit_count: effectiveUnitCount || null,
      config: {
        words_per_chapter: taskForm.value.words_per_chapter,
        concurrency: taskForm.value.concurrency,
        generation_mode: "direct",
        agents: agentsConfig,
        agent_api_bases: taskForm.value.agent_api_bases,
        agent_api_keys: taskForm.value.agent_api_keys,
        // 文风知识库配置
        style_guide: {
          style_library_guide: styleMgmt?.styleGuide?.value || null,
          writing_styles: styleMgmt?.selectedStyleIds?.value?.length > 0 ? styleMgmt.selectedStyleIds.value : null,
          style_intensity: styleMgmt?.styleIntensity?.value !== 0.7 ? styleMgmt.styleIntensity.value : null,
        },
        // Task 8: 按内容类型发送专属参数
        ...buildTypeSpecificConfig(),
      },
    });
    if (task) {
      // 清空表单
      taskForm.value.start_from = 1;
      taskForm.value.unit_count = null;
    }
  }

  // 中断任务
  async function handleInterrupt() {
    try {
      await writingStore.interruptTask(writingStore.currentTask.id);
    } catch (error) {
      console.error("中断任务失败:", error);
    }
  }

  // 续传任务
  async function handleResume() {
    await writingStore.resumeTask(writingStore.currentTask.id);
  }

  // 继续生成任务
  async function handleContinue(unitCount) {
    if (!unitCount || unitCount < 1) {
      ElMessage.warning("请输入有效的生成数量");
      return;
    }

    try {
      showContinueDialog.value = false;
      await writingStore.continueTask(
        writingStore.currentTask.id,
        unitCount,
      );
      ElMessage.success(`已开始继续生成 ${unitCount} 个单元`);
    } catch (error) {
      console.error("继续生成失败:", error);
      ElMessage.error("继续生成失败: " + (error.message || "未知错误"));
    }
  }

  // 上传大纲
  async function handleUploadOutline(content) {
    if (!content?.trim()) {
      ElMessage.warning("请输入大纲内容");
      return;
    }

    uploadingOutline.value = true;
    try {
      const res = await novelWriterApi.updateProject(projectId.value, {
        outline_content: content,
      });

      if (res.success) {
        ElMessage.success("大纲上传成功");
        showOutlineUploadDialog.value = false;
        // 重新加载项目数据
        if (loadProjectData) await loadProjectData();
      } else {
        ElMessage.error(res.message || "上传失败");
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || "上传失败");
    } finally {
      uploadingOutline.value = false;
    }
  }

  // 生成目录
  async function handleGenerateDirectory() {
    generatingDirectory.value = true;
    try {
      const res = await novelWriterApi.generateDirectory(projectId.value, {
        total_chapters: projectTotalUnits.value || 10,
        chapter_naming_style: "数字编号",
        generate_names: true,
      });
      if (res.success) {
        ElMessage.success("目录生成成功");
        // 重新加载项目数据
        if (loadProjectData) await loadProjectData();
      } else {
        ElMessage.error(res.message || "目录生成失败");
      }
    } catch (error) {
      ElMessage.error("目录生成失败");
    } finally {
      generatingDirectory.value = false;
    }
  }

  // 删除知识库
  async function handleDeleteKnowledgeBase() {
    try {
      const res = await novelWriterApi.deleteKnowledgeBase(projectId.value)
      if (res.success) {
        ElMessage.success('知识库已删除')
        kbStatus.value = { status: 'not_built', progress: null }
      }
    } catch (error) {
      ElMessage.error('删除知识库失败')
    }
  }

  // 构建知识库 - 基于项目大纲构建项目专属知识图谱，辅助AI进行正文生成
  async function handleBuildKnowledgeBase() {
    buildingKb.value = true
    try {
      const res = await novelWriterApi.buildKnowledgeBase(projectId.value)
      if (res.success) {
        ElMessage.success('知识库构建任务已启动')
        kbStatus.value = { status: 'building', progress: 0 }
        // 开始轮询状态
        startKbPolling()
      } else {
        ElMessage.error(res.message || '构建失败')
      }
    } catch (error) {
      ElMessage.error('知识库构建失败')
    } finally {
      buildingKb.value = false
    }
  }

  // 知识库状态轮询
  let kbPollingTimer = null
  function startKbPolling() {
    if (kbPollingTimer) clearInterval(kbPollingTimer)
    kbPollingTimer = setInterval(async () => {
      try {
        const res = await novelWriterApi.getKnowledgeBaseStatus(projectId.value)
        if (res.success) {
          kbStatus.value = res.data
          if (res.data.status !== 'building') {
            clearInterval(kbPollingTimer)
            kbPollingTimer = null
            if (res.data.status === 'ready') {
              ElMessage.success('知识库构建完成')
            } else if (res.data.status === 'failed') {
              ElMessage.error('知识库构建失败')
            }
          }
        }
      } catch (error) {
        console.warn('轮询知识库状态失败:', error)
      }
    }, 2000)
  }

  // 任务AI文风消除开关变更
  function handleTaskAiEliminationChange(value) {
    // 同步到项目设置
    if (styleMgmt?.handleAiEliminationChange) {
      styleMgmt.handleAiEliminationChange(value);
    }
  }

  // 取消上传
  function handleCancelUnitSummariesUpload() {
    showUnitSummariesUploadDialog.value = false;
  }

  // 上传单元概述文件（接收el-upload的options对象）
  async function handleUploadUnitSummariesFile(options) {
    const file = options?.file;
    if (!file) {
      ElMessage.warning("请选择要上传的文件");
      return;
    }

    const validExtensions = ['.txt', '.md', '.doc', '.docx'];
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!validExtensions.includes(fileExt)) {
      ElMessage.error(`不支持的文件格式: ${fileExt}，支持 .txt, .md, .doc, .docx`);
      return;
    }

    uploadingUnitSummaries.value = true;
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await novelWriterApi.uploadUnitSummariesFile(
        projectId.value,
        formData,
      );
      if (res.success) {
        const unitCount = res.data?.unit_count || 0;
        ElMessage.success(res.data?.message || "单元概述上传成功");
        showUnitSummariesUploadDialog.value = false;
        // 清空表单
        unitSummariesInput.value = '';
        globalOutlineInput.value = '';
        // 自动填充生成数量
        if (unitCount > 0 && !taskForm.value.unit_count) {
          taskForm.value.unit_count = unitCount;
        }
        // 重新加载项目数据
        if (loadProjectData) await loadProjectData();
      } else {
        ElMessage.error(res.data?.message || "上传失败");
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || "上传失败");
    } finally {
      uploadingUnitSummaries.value = false;
    }
  }

  // P0改造：上传单元概述内容（支持JSON和Markdown两种格式）
  async function handleUploadUnitSummariesContent(contentData) {
    // contentData = { format: 'json'|'markdown', parsedData: Object, rawContent: string }
    if (!contentData || !contentData.parsedData) {
      ElMessage.warning("请输入单元概述内容");
      return;
    }

    const unitSummaries = contentData.parsedData;
    
    // 验证数据格式
    if (typeof unitSummaries !== "object" || Array.isArray(unitSummaries)) {
      ElMessage.error("单元概述格式错误，应为对象格式");
      return;
    }

    uploadingUnitSummaries.value = true;
    try {
      const data = { unit_summaries: unitSummaries };
      if (globalOutlineInput.value.trim()) {
        data.global_outline = globalOutlineInput.value.trim();
      }

      const res = await novelWriterApi.uploadUnitSummaries(
        projectId.value,
        data,
      );
      if (res.success) {
        const unitCount = res.data?.unit_count || 0;
        ElMessage.success(res.data?.message || "单元概述上传成功");
        showUnitSummariesUploadDialog.value = false;
        unitSummariesInput.value = "";
        globalOutlineInput.value = "";
        // 自动填充生成数量
        if (unitCount > 0 && !taskForm.value.unit_count) {
          taskForm.value.unit_count = unitCount;
        }
        // 重新加载项目数据
        if (loadProjectData) await loadProjectData();
      } else {
        ElMessage.error(res.data?.message || "上传失败");
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || "上传失败");
    } finally {
      uploadingUnitSummaries.value = false;
    }
  }

  // 删除任务
  async function handleDelete() {
    try {
      await ElMessageBox.confirm(
        "确定要删除此任务吗？删除后将清除所有进度数据。",
        "确认删除",
        { type: "warning" },
      );
      await writingStore.deleteTask(writingStore.currentTask.id);
    } catch (error) {
      if (error !== "cancel") {
        console.error("删除任务失败:", error);
      }
    }
  }

  // 导出任务内容
  async function handleExport() {
    try {
      const taskId = writingStore.currentTask?.id;
      if (!taskId) return;

      const response = await writingTaskApi.exportTask(taskId, "md");
      const blob = new Blob([response.data || response], {
        type: "text/markdown;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `writing_task_${taskId}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      ElMessage.success("下载成功");
    } catch (error) {
      console.error("导出失败:", error);
      ElMessage.error("导出失败: " + (error.message || "未知错误"));
    }
  }

  return {
    // 表单
    taskForm,

    // 状态
    showOutlineUploadDialog,
    uploadingOutline,
    showUnitSummariesUploadDialog,
    unitSummariesUploadMode,
    unitSummariesInput,
    globalOutlineInput,
    uploadingUnitSummaries,
    generatingDirectory,
    showContinueDialog,
    continueUnitCount,

    // 知识库状态（P1改造新增）
    kbStatus,
    buildingKb,

    // 方法
    handleTestConnection,
    handleCreateTask,
    handleInterrupt,
    handleResume,
    handleContinue,
    handleUploadOutline,
    handleGenerateDirectory,
    handleBuildKnowledgeBase,
    handleDeleteKnowledgeBase,
    handleTaskAiEliminationChange,
    handleCancelUnitSummariesUpload,
    handleUploadUnitSummariesFile,
    handleUploadUnitSummariesContent,
    handleDelete,
    handleExport,
    
    // 知识库状态加载（延迟加载）
    loadKbStatus,
  }
}
