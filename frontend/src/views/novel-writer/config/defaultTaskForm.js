/**
 * 写作任务默认表单配置
 *
 * 提供 createDefaultTaskForm() 工厂函数和 AGENT_ROLES 常量，
 * 消除 useWorkbenchTask.js 和 useWritingTask.js 中的重复定义。
 *
 * @module views/novel-writer/config/defaultTaskForm
 */

/** 所有可配置的 Agent 角色键列表 */
export const AGENT_ROLES = [
  "orchestrator",
  "structural",
  "writer",
  "logic_editor",
  "style_editor",
  "compliance",
  "knowledge",
]

/** Agent 角色默认温度值 */
const AGENT_DEFAULT_TEMPERATURES = {
  orchestrator: 0.3,
  structural: 0.6,
  writer: 0.8,
  logic_editor: 0.2,
  style_editor: 0.6,
  compliance: 0.1,
  knowledge: 0.3,
}

/**
 * 创建一个空字符串值的 Agent 配置对象（用于 models, providers, api_bases, api_keys）
 */
function createEmptyAgentMap(defaultValue = "") {
  const map = {}
  for (const role of AGENT_ROLES) {
    map[role] = defaultValue
  }
  return map
}

/**
 * 创建一个 null 值的 Agent 配置对象（用于 config_ids）
 */
function createNullAgentMap() {
  const map = {}
  for (const role of AGENT_ROLES) {
    map[role] = null
  }
  return map
}

/**
 * 创建默认任务表单
 *
 * @returns {Object} 包含所有 Agent 配置字段的默认表单对象
 */
export function createDefaultTaskForm() {
  return {
    start_from: 1,
    unit_count: null,
    words_per_chapter: 3000,
    concurrency: 3,
    generation_mode: "direct",
    agent_models: createEmptyAgentMap(""),
    agent_temps: createEmptyAgentMapFrom(AGENT_DEFAULT_TEMPERATURES),
    agent_providers: createEmptyAgentMap(""),
    agent_api_bases: createEmptyAgentMap(""),
    agent_api_keys: createEmptyAgentMap(""),
    agent_config_ids: createNullAgentMap(),
  }
}

/**
 * 从预设值创建 Agent 配置映射
 */
function createEmptyAgentMapFrom(presets) {
  const map = {}
  for (const role of AGENT_ROLES) {
    map[role] = presets[role] ?? 0.7
  }
  return map
}
