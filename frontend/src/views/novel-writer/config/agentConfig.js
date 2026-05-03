/**
 * Agent角色配置
 * 
 * 定义多Agent协作写作系统中的Agent角色映射、配置列表
 * 与后端 AgentRole 枚举保持一致
 * 
 * @module views/novel-writer/config/agentConfig
 */

/**
 * Agent角色中文显示名映射（与后端 AgentRole 枚举对应）
 */
export const AGENT_ROLE_LABELS = {
  orchestrator: "总线Agent",
  structural: "结构师Agent",
  writer: "写手Agent",
  logic_editor: "逻辑编辑Agent",
  style_editor: "风格润色Agent",
  compliance: "合规审查Agent",
  knowledge: "知识顾问Agent",
  assembler: "合成Agent",
}

/**
 * Agent配置列表（角色名与后端 AgentRole 枚举一致）
 * 注意: assembler 不需要 LLM 配置，只做内容整合
 */
export const agentConfigs = [
  {
    role: "orchestrator",
    label: "总线Agent",
    icon: "Connection",
    configurable: true,
    description:
      "任务调度和流程编排的核心Agent，负责控制其他Agent的协作顺序、管理并发写手数量、处理中断续传等。",
    configTips: {
      modelType: "推荐选择推理能力强的模型，需要稳定的决策输出",
      temperature: "建议 0.2-0.4，决策类任务需要低温度保持稳定性",
      extra: "此Agent是整个系统的调度中心，模型稳定性优先于创意性",
    },
  },
  {
    role: "structural",
    label: "结构师Agent",
    icon: "OfficeBuilding",
    configurable: true,
    description:
      "负责将写作大纲拆解为具体的场景列表，规划每个场景的叙事结构、人物出场、情节走向和目标字数。",
    configTips: {
      modelType: "推荐选择长文本理解和结构化输出能力强的模型",
      temperature: "建议 0.5-0.7，需要平衡结构严谨性和创意空间",
      extra: "结构师的输出质量直接影响后续所有写手的创作质量",
    },
  },
  {
    role: "writer",
    label: "写手Agent",
    icon: "EditPen",
    configurable: true,
    description:
      "核心内容创作Agent，根据场景大纲生成高质量的文学文本，是系统中调用频率最高的Agent。",
    configTips: {
      modelType: "推荐选择中文创作能力最强的模型，这是最核心的创作环节",
      temperature: "建议 0.7-0.9，高温度能增强文学创意性和表达多样性",
      extra: "建议使用最强的创作模型，写手Agent的质量决定了最终作品的质量",
    },
  },
  {
    role: "logic_editor",
    label: "逻辑编辑Agent",
    icon: "View",
    configurable: true,
    description:
      "负责审查内容的逻辑连贯性，包括情节逻辑、角色行为与人设一致性、时间线合理性、场景描述矛盾等。",
    configTips: {
      modelType: "推荐选择推理能力强的模型，如 thinking/reasoning 系列",
      temperature: "建议 0.1-0.3，逻辑分析需要极低温度保证严谨性",
      extra: "推理类模型（如带thinking标签的模型）在逻辑检查任务上表现更优",
    },
  },
  {
    role: "style_editor",
    label: "风格润色Agent",
    icon: "MagicStick",
    configurable: true,
    description:
      "负责优化文学风格、修辞手法、叙述节奏和语言质量，提升文本的文学性和可读性。",
    configTips: {
      modelType: "推荐选择中文理解和文学表达能力强的模型",
      temperature: "建议 0.5-0.7，需要平衡文风润色效果和保持原意",
      extra: "风格润色需要对中文文学有良好理解，建议选择中文优化过的模型",
    },
  },
  {
    role: "compliance",
    label: "合规审查Agent",
    icon: "Warning",
    configurable: true,
    description:
      "采用Trie树本地检测+LLM辅助判断的双层架构，检测敏感内容，确保生成内容符合发布规范。",
    configTips: {
      modelType: "推荐选择安全审查能力强、判断准确的模型",
      temperature: "建议 0.0-0.2，合规判断需要最高一致性，不容许随机性",
      extra: "合规审查的准确性直接关系到内容安全，建议选择经过安全训练的模型",
    },
  },
  {
    role: "knowledge",
    label: "知识顾问Agent",
    icon: "Reading",
    configurable: true,
    description:
      "负责检索项目知识库和上下文信息，为其他Agent提供背景参考资料，确保创作内容与项目设定一致。",
    configTips: {
      modelType: "推荐选择检索增强和准确回答能力强的模型",
      temperature: "建议 0.2-0.4，知识检索需要准确性优先",
      extra: "知识顾问的准确性影响其他Agent的创作一致性",
    },
  },
  {
    role: "assembler",
    label: "合成Agent",
    icon: "SetUp",
    configurable: false,
    description:
      "负责将同一单元下所有场景的最终内容合并为完整文本，纯规则合并，无需配置LLM模型。",
    configTips: null,
  },
]
