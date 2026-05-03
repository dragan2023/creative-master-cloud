/**
 * 质控模式配置
 * 定义快速/标准/深度三种质控模式的参数
 */
export const qualityControlModes = [
  {
    key: 'quick',
    label: '快速',
    icon: 'Lightning',
    description: '仅规则引擎检测，零Token消耗，秒级返回',
    timeEstimate: '< 1秒',
    type: 'success'
  },
  {
    key: 'standard',
    label: '标准',
    icon: 'CircleCheck',
    description: '规则引擎 + LLM深度分析，推荐日常使用',
    timeEstimate: '5-10秒',
    type: 'primary'
  },
  {
    key: 'deep',
    label: '深度',
    icon: 'Rank',
    description: '全量LLM分析，最高精度，适合重要章节',
    timeEstimate: '10-30秒',
    type: 'warning'
  }
]

/**
 * 单元概述质控维度配置
 * 定义各检测维度的展示信息
 */
export const unitQualityDimensions = [
  {
    key: 'unit_structure',
    label: '单元结构',
    icon: 'Grid',
    description: 'LLM深度检测单元长度、衔接流畅度、情节节奏'
  },
  {
    key: 'unit_character',
    label: '人物发展',
    icon: 'User',
    description: 'LLM深度检测人物状态变化、成长逻辑、关系一致性'
  },
  {
    key: 'unit_consistency',
    label: '大纲一致性',
    icon: 'Connection',
    description: 'LLM深度检测与全局大纲的偏离度、核心要素完整性'
  },
  {
    key: 'unit_timeline_space',
    label: '时间线空间',
    icon: 'Location',
    description: '检测人物位置逻辑、出场时间线、事件因果关系、状态连续性'
  },
  {
    key: 'unit_ooc',
    label: '人物OOC',
    icon: 'Warning',
    description: '检测人物是否违背人设（性格违背、动机矛盾、能力超纲）'
  }
]
