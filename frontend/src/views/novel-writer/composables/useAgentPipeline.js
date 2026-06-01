/**
 * useAgentPipeline - Agent流水线和工作流
 *
 * 处理 WritingWorkbench 中的 Agent 流水线状态、工作流步骤、Provider/模型配置等功能
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { writingTaskApi } from '@/api/writing-task'
import { agentConfigs } from '../config/agentConfig'

/**
 * @param {Object} writingStore - writingTask Store
 * @param {import('vue').Ref} taskFormRef - taskForm ref（用于修改表单中的agent配置）
 */
export function useAgentPipeline(writingStore, taskFormRef) {
  // ==================== 响应式状态 ====================
  const showAgentConfigDialog = ref(false)
  const quickApplyConfigId = ref(null)
  const availableProviders = ref([])
  const loadingProviders = ref(false)
  const modelConfigs = ref([])
  const loadingConfigs = ref(false)

  // ==================== 计算属性 ====================

  // 格式化耗时
  const formattedDuration = computed(() => {
    const task = writingStore.currentTask;
    if (!task) return "00:00:00";

    const start = task.start_time ? new Date(task.start_time) : null;
    const end = task.end_time ? new Date(task.end_time) : null;

    let ms = 0;
    if (start && end) {
      ms = end - start;
    } else if (start && writingStore.isRunning) {
      ms = Date.now() - start;
    }

    if (ms === 0) return "00:00:00";

    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    return `${hours.toString().padStart(2, "0")}:${(minutes % 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
  });

  // Agent流水线状态
  // 后端通过 workflow_step 消息（type="workflow_step"，含 agent_name + status 字段）
  // 来推送各Agent的运行状态。task_progress 消息也可能携带 agent_name。
  const agentPipeline = computed(() => {
    const messages = writingStore.progressMessages;
    const isRunning = writingStore.isRunning;
    const isCompleted = writingStore.isCompleted;

    const pipeline = agentConfigs.map((agent) => {
      // 查找该Agent的相关消息（优先 workflow_step，其次 task_progress 带agent_name的消息）
      const agentMsgs = messages.filter(
        (m) =>
          (m.type === "workflow_step" && m.data?.agent_name?.includes(agent.label)) ||
          (m.type === "task_progress" && m.agent_name?.includes(agent.label)) ||
          m.data?.agent_role === agent.role ||
          m.data?.agent_name?.includes(agent.label),
      );
      // 取最后一条消息（最新状态），消息通过 push 追加到数组末尾
      const latestMsg = agentMsgs.length > 0 ? agentMsgs[agentMsgs.length - 1] : null;

      let status = "waiting";
      let statusLabel = "等待中";
      let statusType = "info";

      if (latestMsg) {
        // workflow_step 消息：status 为 "running" | "done" | "error"
        if (latestMsg.type === "workflow_step") {
          if (latestMsg.data?.status === "done") {
            status = "completed";
            statusLabel = "已完成";
            statusType = "success";
          } else if (latestMsg.data?.status === "error") {
            status = "error";
            statusLabel = "失败";
            statusType = "danger";
          } else if (latestMsg.data?.status === "running") {
            status = "running";
            statusLabel = "运行中";
            statusType = "primary";
          }
        }
        // task_progress 消息携带 agent_name 时，使用其 status 字段
        else if (latestMsg.type === "task_progress" && latestMsg.agent_name) {
          if (latestMsg.status === "completed" || latestMsg.status === "done") {
            status = "completed";
            statusLabel = "已完成";
            statusType = "success";
          } else if (latestMsg.status === "failed" || latestMsg.status === "error") {
            status = "error";
            statusLabel = "失败";
            statusType = "danger";
          } else if (latestMsg.status === "started" || latestMsg.status === "processing") {
            status = "running";
            statusLabel = "运行中";
            statusType = "primary";
          }
        }
        // 兼容旧的 agent_complete / agent_error / agent_start 类型（如果后端未来恢复）
        else if (
          latestMsg.type === "agent_complete" ||
          latestMsg.type === "unit_complete"
        ) {
          status = "completed";
          statusLabel = "已完成";
          statusType = "success";
        } else if (latestMsg.type === "agent_error") {
          status = "error";
          statusLabel = "失败";
          statusType = "danger";
        } else if (
          latestMsg.type === "agent_start" ||
          latestMsg.data?.message?.includes("开始")
        ) {
          status = "running";
          statusLabel = "运行中";
          statusType = "primary";
        }
      } else if (isRunning) {
        // 任务运行中，但该Agent尚未收到任何消息 → 等待调度
        status = "waiting";
        statusLabel = "等待中";
        statusType = "info";
      }

      // 如果任务已完成，所有Agent都标记为完成
      if (isCompleted) {
        status = "completed";
        statusLabel = "已完成";
        statusType = "success";
      }

      return {
        ...agent,
        status,
        statusLabel,
        statusType,
      };
    });

    return pipeline;
  });

  // 当前处理信息
  const currentProcessingInfo = computed(() => {
    const current = writingStore.currentUnit;
    if (!current || !writingStore.isRunning) return null;

    const msg = writingStore.progressMessages.find(
      (m) => m.data?.unit_index === current.unit_index,
    );
    if (msg) {
      return `正在处理: ${current.unit_title || `单元 ${current.unit_index}`} - ${msg.data?.message || ""}`;
    }
    return `正在处理: ${current.unit_title || `单元 ${current.unit_index}`}`;
  });

  // 工作流步骤（从WebSocket消息中提取）
  const workflowSteps = computed(() => {
    const steps = [];
    const messages = writingStore.progressMessages;

    // 遍历消息，提取工作流步骤
    for (const msg of messages) {
      // 处理 unit_progress 类型的消息（包含 workflow 信息）
      if (msg.type === "unit_progress" && msg.data?.status) {
        const status = msg.data.status;
        const progress = msg.data.progress || 0;

        // 将单元进度转换为工作流步骤
        let stepMessage = "";
        let stepIcon = "MagicStick";

        switch (status) {
          case "structuring":
            stepMessage = `单元 ${msg.data.unit_index || ""}: 结构拆解中..`;
            stepIcon = "OfficeBuilding";
            break;
          case "writing":
            stepMessage = `单元 ${msg.data.unit_index || ""}: 内容生成中..`;
            stepIcon = "EditPen";
            break;
          case "reviewing":
            stepMessage = `单元 ${msg.data.unit_index || ""}: 审阅润色中..`;
            stepIcon = "View";
            break;
          case "assembling":
            stepMessage = `单元 ${msg.data.unit_index || ""}: 内容组装中..`;
            stepIcon = "SetUp";
            break;
          case "completed":
            stepMessage = `单元 ${msg.data.unit_index || ""}: 处理完成`;
            stepIcon = "CircleCheck";
            break;
          default:
            stepMessage =
              msg.data.message || `单元 ${msg.data.unit_index || ""}: ${status}`;
        }

        // 检查是否已存在相同单元的相同步骤
        const existingStep = steps.find(
          (s) => s.step === `unit_${msg.data.unit_index}_${status}`,
        );
        if (!existingStep) {
          steps.push({
            step: `unit_${msg.data.unit_index}_${status}`,
            status:
              status === "completed"
                ? "done"
                : status === "failed"
                  ? "error"
                  : "running",
            message: stepMessage,
            icon: stepIcon,
            progress,
          });
        }
      }

      // 处理 scene_progress 类型的消息
      if (msg.type === "scene_progress" && msg.data?.status) {
        const status = msg.data.status;
        const unitIdx = msg.data.unit_index || "";
        const sceneIdx = msg.data.scene_index || "";

        if (status === "writing") {
          steps.push({
            step: `scene_${unitIdx}_${sceneIdx}_writing`,
            status: "running",
            message: `单元 ${unitIdx} 场景 ${sceneIdx}: 内容生成中..`,
            icon: "EditPen",
          });
        } else if (status === "completed" || status === "done") {
          steps.push({
            step: `scene_${unitIdx}_${sceneIdx}_done`,
            status: "done",
            message: `单元 ${unitIdx} 场景 ${sceneIdx}: 生成完成`,
            icon: "CircleCheck",
          });
        } else if (status === "failed") {
          steps.push({
            step: `scene_${unitIdx}_${sceneIdx}_error`,
            status: "error",
            message: `单元 ${unitIdx} 场景 ${sceneIdx}: 生成失败`,
            icon: "CircleClose",
          });
        }
      }

      // 处理 task_progress 类型的消息
      if (msg.type === "task_progress" && msg.data) {
        const completed = msg.data.completed_units || 0;
        const total = msg.data.total_units || 0;
        if (completed > 0) {
          steps.push({
            step: `task_progress_${completed}`,
            status: "done",
            message: `已完成 ${completed}/${total} 单元`,
            icon: "DataLine",
          });
        }
      }
    }

    // 只保留最近的5个步骤
    return steps.slice(-5);
  });

  // ==================== 方法 ====================

  // 加载可用Provider列表
  async function loadProviders() {
    loadingProviders.value = true;
    try {
      const res = await writingTaskApi.getAvailableProviders();
      // 后端返回格式: { data: { providers: [...] }, message: "..." }
      availableProviders.value =
        res.data?.data?.providers || res.data?.providers || [];
    } catch (error) {
      console.error("加载Provider列表失败:", error);
      // 使用默认列表作为降级
      availableProviders.value = [
        {
          name: "qianwen",
          display_name: "通义千问 (阿里云百炼)",
          api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
          is_preset: true,
          models: [],
        },
        {
          name: "doubao",
          display_name: "豆包 (字节跳动/火山引擎)",
          api_base: "https://ark.cn-beijing.volces.com/api/v3",
          is_preset: true,
          models: [],
        },
        {
          name: "siliconflow",
          display_name: "硅基流动 (SiliconFlow)",
          api_base: "https://api.siliconflow.cn/v1",
          is_preset: true,
          models: [],
        },
        {
          name: "openrouter",
          display_name: "OpenRouter",
          api_base: "https://openrouter.ai/api/v1",
          is_preset: true,
          models: [],
        },
        {
          name: "t8star",
          display_name: "贞贞AI工坊",
          api_base: "https://ai.t8star.cn/v1",
          is_preset: true,
          models: [],
        },
        {
          name: "custom",
          display_name: "自定义服务商",
          api_base: "",
          is_preset: false,
          models: [],
        },
      ];
    } finally {
      loadingProviders.value = false;
    }
  }

  // 加载预配置模型列表
  async function loadModelConfigs() {
    loadingConfigs.value = true;
    try {
      const res = await writingTaskApi.getModelConfigs();
      // 后端返回格式: { data: [...配置列表], message: "..." }
      modelConfigs.value = res.data?.data || res.data || [];
    } catch (error) {
      console.error("加载模型配置失败:", error);
      modelConfigs.value = [];
    } finally {
      loadingConfigs.value = false;
    }
  }

  // 模型配置选择变更
  function onModelConfigChange(role, configId) {
    if (!taskFormRef || !taskFormRef.value) return;
    const taskForm = taskFormRef.value;

    if (configId === "custom") {
      // 清空预配置关联，让用户手动输入
      return;
    }
    const config = modelConfigs.value.find((c) => c.id === configId);
    if (config) {
      // 自动填充provider/model/api_base（api_key由后端通过config_id获取）
      taskForm.agent_providers[role] = config.provider;
      taskForm.agent_models[role] = config.model_id;
      taskForm.agent_api_bases[role] = config.api_base || "";
      taskForm.agent_api_keys[role] = ""; // 使用预配置的key，不需要前端传
    }
  }

  // 一键应用同一模型到所有Agent
  function applyToAllAgents(configId) {
    if (!taskFormRef || !taskFormRef.value) return;
    const taskForm = taskFormRef.value;

    const configurableRoles = agentConfigs
      .filter((a) => a.configurable)
      .map((a) => a.role);
    for (const role of configurableRoles) {
      taskForm.agent_config_ids[role] = configId;
      onModelConfigChange(role, configId);
    }
    ElMessage.success("已应用到所有Agent");
  }

  // 快速应用模型配置（对话框中使用）
  function handleQuickApply() {
    if (!quickApplyConfigId.value) return;
    applyToAllAgents(quickApplyConfigId.value);
  }

  // Provider变更时，自动填充api_base
  function onProviderChange(role, providerName) {
    if (!taskFormRef || !taskFormRef.value) return;
    const taskForm = taskFormRef.value;

    const provider = availableProviders.value.find(
      (p) => p.name === providerName,
    );
    if (provider && provider.api_base) {
      taskForm.agent_api_bases[role] = provider.api_base;
    } else {
      taskForm.agent_api_bases[role] = "";
    }
    // 清空model选择
    taskForm.agent_models[role] = "";
  }

  // 获取指定provider的模型列表（用于下拉建议）
  function getProviderModels(role) {
    if (!taskFormRef || !taskFormRef.value) return [];
    const taskForm = taskFormRef.value;

    const providerName = taskForm.agent_providers[role];
    const provider = availableProviders.value.find(
      (p) => p.name === providerName,
    );
    return provider?.models || [];
  }

  return {
    // 状态
    showAgentConfigDialog,
    quickApplyConfigId,
    availableProviders,
    loadingProviders,
    modelConfigs,
    loadingConfigs,

    // 计算属性
    formattedDuration,
    agentPipeline,
    currentProcessingInfo,
    workflowSteps,

    // 方法
    loadProviders,
    loadModelConfigs,
    onModelConfigChange,
    applyToAllAgents,
    handleQuickApply,
    onProviderChange,
    getProviderModels,
  }
}
