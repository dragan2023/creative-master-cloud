// API基础配置
// 开发环境使用空字符串，让请求走 Vite 代理（避免 CORS）
// 生产环境使用完整 URL
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// 模型类型定义
export const MODEL_TYPES = {
  TEXT: 'text',      // 文本模型（支持多模态输入）
  IMAGE: 'image',    // 图像生成模型
  VIDEO: 'video'     // 视频生成模型
}

// LLM提供商配置（2026年最新）
// 所有服务商使用OpenAI兼容API格式，用户可自定义api_base和model_name
// type: 模型类型 - text(文本模型), image(图像生成), video(视频生成)
// vision: 是否支持图片输入（多模态）
// description: 模型能力说明
export const LLM_PROVIDERS = [
  // ==================== 通义千问（阿里云百炼）====================
  {
    value: 'qianwen',
    label: '通义千问 (阿里云百炼)',
    doc_url: 'https://bailian.console.aliyun.com',
    api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    notice: '国内服务商，直连即可。支持文本、图像、视频多模态输入。',
    type: 'text',
    models: [
      { 
        id: 'qwen3.5-plus', 
        name: 'Qwen3.5-Plus', 
        context: '256K', 
        vision: true,
        type: 'text',
        description: '旗舰多模态模型，支持文本/图像/视频输入，擅长语言理解、逻辑推理、代码生成'
      },
      { 
        id: 'qwen3.5-plus-2026-02-15', 
        name: 'Qwen3.5-Plus (快照)', 
        context: '256K', 
        vision: true,
        type: 'text',
        description: 'Qwen3.5-Plus 快照版本'
      }
    ]
  },
  {
    value: 'qianwen-image',
    label: '通义千问-图像生成',
    doc_url: 'https://bailian.console.aliyun.com',
    api_base: 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
    notice: '图像生成模型，通过文本描述生成图像。支持中英双语渲染。',
    type: 'image',
    models: [
      { 
        id: 'z-image-turbo', 
        name: 'Z-Image-Turbo', 
        context: '-', 
        vision: false,
        type: 'image',
        description: '轻量级文生图模型，快速生成高质量图像，分辨率512-2048px'
      },
      { 
        id: 'qwen-image-edit-max-2026-01-16', 
        name: 'Qwen-Image-Edit-Max', 
        context: '-', 
        vision: true,
        type: 'image',
        description: '图像编辑模型，支持角色一致性、工业设计、几何推理'
      }
    ]
  },
  
  // ==================== 火山引擎（豆包）====================
  {
    value: 'doubao',
    label: '豆包 (字节跳动/火山引擎)',
    doc_url: 'https://console.volcengine.com/ark',
    api_base: 'https://ark.cn-beijing.volces.com/api/v3',
    notice: 'doubao-seed-2-0-pro支持文本、图像、视频多模态输入。模型名称填写接入点ID。',
    type: 'text',
    models: [
      { 
        id: 'doubao-seed-2-0-pro-260215', 
        name: 'Doubao-Seed-2.0-Pro', 
        context: '256K', 
        vision: true,
        type: 'text',
        description: '旗舰多模态模型，支持文本/图像/视频输入，擅长复杂推理、工具调用、视频理解'
      },
      { 
        id: 'deepseek-v3-2-251201', 
        name: 'DeepSeek-V3.2 (火山引擎)', 
        context: '128K', 
        vision: false,
        type: 'text',
        description: 'DeepSeek V3.2版本，支持隐式缓存，擅长推理和工具调用'
      }
    ]
  },
  {
    value: 'doubao-image',
    label: '豆包-图像生成',
    doc_url: 'https://console.volcengine.com/ark',
    api_base: 'https://ark.cn-beijing.volces.com/api/v3',
    notice: 'Seedream系列图像生成模型，支持文本生成图像、图像编辑。',
    type: 'image',
    models: [
      { 
        id: 'doubao-seedream-5-0-260128', 
        name: 'Seedream-5.0', 
        context: '-', 
        vision: false,
        type: 'image',
        description: '最新图像生成模型，高质量文生图'
      }
    ]
  },
  
  // ==================== 硅基流动 ====================
  {
    value: 'siliconflow',
    label: '硅基流动 (SiliconFlow)',
    doc_url: 'https://cloud.siliconflow.cn',
    api_base: 'https://api.siliconflow.cn/v1',
    notice: '聚合平台，提供多种开源模型API，模型名称格式：开发者/模型名',
    type: 'text',
    models: [
      { 
        id: 'deepseek-ai/DeepSeek-V3.2', 
        name: 'DeepSeek-V3.2', 
        context: '164K', 
        vision: false,
        type: 'text',
        description: '推理优先模型，支持思考模式下的工具调用，Agent能力增强'
      }
    ]
  },
  
  // ==================== OpenRouter ====================
  {
    value: 'openrouter',
    label: 'OpenRouter',
    doc_url: 'https://openrouter.ai',
    api_base: 'https://openrouter.ai/api/v1',
    notice: '国外模型聚合平台，国内直连，支持支付宝充值。模型格式：提供商/模型名',
    type: 'text',
    models: [
      // Google Gemini 文本模型
      { 
        id: 'google/gemini-3.1-pro-preview', 
        name: 'Gemini 3.1 Pro', 
        context: '1M', 
        vision: true,
        type: 'text',
        description: 'Google多模态模型，擅长推理和工具调用'
      },
      // OpenAI 模型
      { 
        id: 'openai/gpt-5.2-pro', 
        name: 'GPT-5.2 Pro', 
        context: '400K', 
        vision: true,
        type: 'text',
        description: 'OpenAI最新旗舰模型，40万token上下文，擅长编码和复杂推理'
      }
    ]
  },
  {
    value: 'openrouter-image',
    label: 'OpenRouter-图像生成',
    doc_url: 'https://openrouter.ai',
    api_base: 'https://openrouter.ai/api/v1',
    notice: '通过OpenRouter访问的图像生成模型。',
    type: 'image',
    models: [
      { 
        id: 'google/gemini-3-pro-image-preview', 
        name: 'Gemini 3 Pro Image', 
        context: '-', 
        vision: false,
        type: 'image',
        description: 'Google最新图像生成模型，支持文本生成高质量图像'
      }
    ]
  }
]

// 按类型分组的提供商（用于前端筛选）
export const PROVIDERS_BY_TYPE = {
  text: LLM_PROVIDERS.filter(p => p.type === 'text'),
  image: LLM_PROVIDERS.filter(p => p.type === 'image'),
  video: LLM_PROVIDERS.filter(p => p.type === 'video')
}

// 创意生成模块配置
export const CREATIVE_MODULES = [
  {
    key: 'short-video',
    title: '短视频脚本',
    icon: 'VideoCamera',
    description: '为抖音、快手等平台生成短视频脚本',
    color: '#FF6B6B'
  },
  {
    key: 'script',
    title: '剧本大纲',
    icon: 'Document',
    description: '电影、电视剧、网剧剧本大纲生成',
    color: '#4ECDC4'
  },
  {
    key: 'novel',
    title: '小说大纲',
    icon: 'Notebook',
    description: '网络小说、短篇故事大纲创作',
    color: '#45B7D1'
  },
  {
    key: 'print-ad',
    title: '平面广告',
    icon: 'Picture',
    description: '海报、宣传单、户外广告文案',
    color: '#96CEB4'
  },
  {
    key: 'tvc',
    title: 'TVC广告脚本',
    icon: 'Film',
    description: '电视广告、商业视频脚本',
    color: '#FFEAA7'
  }
]
