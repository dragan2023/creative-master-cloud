// API基础配置
// 开发环境使用空字符串，让请求走 Vite 代理（避免 CORS）
// 生产环境使用完整 URL
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// 模型类型定义
export const MODEL_TYPES = {
  TEXT: 'text',      // 文本模型（支持多模态输入）
  IMAGE: 'image',    // 图像生成模型
  VIDEO: 'video',    // 视频生成模型
  SEARCH: 'search'   // 搜索服务（用于热点聚合等）
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
  
  // ==================== DeepSeek（官方）====================
  {
    value: 'deepseek',
    label: 'DeepSeek (官方)',
    doc_url: 'https://api-docs.deepseek.com',
    api_base: 'https://api.deepseek.com',
    notice: 'DeepSeek 官方 API。deepseek-chat/reasoner 将于 2026/07/24 弃用，请使用 V4 系列。',
    type: 'text',
    models: [
      { 
        id: 'deepseek-v4-pro', 
        name: 'DeepSeek V4 Pro', 
        context: '1M', 
        vision: false,
        type: 'text',
        description: '旗舰模型，1M上下文，最强推理能力，支持思考模式（reasoning_effort参数）'
      },
      { 
        id: 'deepseek-v4-flash', 
        name: 'DeepSeek V4 Flash', 
        context: '1M', 
        vision: false,
        type: 'text',
        description: '快速模型，1M上下文，高性价比。非思考模式等效旧deepseek-chat，思考模式等效旧deepseek-reasoner'
      },
      { 
        id: 'deepseek-chat', 
        name: 'DeepSeek Chat (旧版，即将弃用)', 
        context: '128K', 
        vision: false,
        type: 'text',
        description: '⚠️ 将于2026/07/24弃用，对应V4 Flash非思考模式'
      },
      { 
        id: 'deepseek-reasoner', 
        name: 'DeepSeek Reasoner (旧版，即将弃用)', 
        context: '128K', 
        vision: false,
        type: 'text',
        description: '⚠️ 将于2026/07/24弃用，对应V4 Flash思考模式'
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
  },
  
  // ==================== 贞贞AI工坊（平价API聚合平台）====================
  {
    value: 't8star',
    label: '贞贞AI工坊',
    doc_url: 'https://ai.t8star.cn/about',
    api_base: 'https://ai.t8star.cn/v1',
    notice: '平价API聚合平台，支持500+模型。分组需在官网令牌后台配置。',
    type: 'text',
    // 分组在贞贞工坊网站后台配置，无需在此选择
    channels: [],
    models: [
      { 
        id: 'gpt-5.2-pro', 
        name: 'GPT-5.2 Pro', 
        context: '400K', 
        vision: true,
        type: 'text',
        description: 'OpenAI旗舰模型，40万token上下文'
      },
      { 
        id: 'gpt-5.2-thinking', 
        name: 'GPT-5.2 Thinking', 
        context: '200K', 
        vision: true,
        type: 'text',
        description: 'OpenAI深度思考模型'
      },
      { 
        id: 'claude-opus-4-5-20251101', 
        name: 'Claude 4.5 Opus', 
        context: '200K', 
        vision: true,
        type: 'text',
        description: 'Anthropic最强推理模型'
      },
      { 
        id: 'glm-5', 
        name: 'GLM-5', 
        context: '128K', 
        vision: false,
        type: 'text',
        description: '智谱AI SOTA模型，支持缓存计费'
      }
    ]
  },
  // 贞贞AI工坊-图像生成
  {
    value: 't8star-image',
    label: '贞贞AI工坊-图像生成',
    doc_url: 'https://ai.t8star.cn/about',
    api_base: 'https://ai.t8star.cn/v1',
    notice: '图像生成模型，支持Nano Banana 2、Gemini等。分组需在官网令牌后台配置。',
    type: 'image',
    // 分组在贞贞工坊网站后台配置，无需在此选择
    channels: [],
    models: [
      { 
        id: 'gemini-3-pro-image-preview', 
        name: 'Gemini 3 Pro Image', 
        context: '-', 
        vision: false,
        type: 'image',
        description: 'Google图像生成，支持高分辨率'
      },
      { 
        id: 'nano-banana-2', 
        name: 'Nano Banana 2', 
        context: '-', 
        vision: false,
        type: 'image',
        description: '支持2K/4K高清'
      },
      { 
        id: 'nano-banana-2-2k', 
        name: 'Nano Banana 2 (2K)', 
        context: '-', 
        vision: false,
        type: 'image',
        description: '固定2K分辨率'
      },
      { 
        id: 'nano-banana-2-4k', 
        name: 'Nano Banana 2 (4K)', 
        context: '-', 
        vision: false,
        type: 'image',
        description: '固定4K分辨率'
      },
      { 
        id: 'doubao-seedream-4-5', 
        name: '豆包Seedream 4.5', 
        context: '-', 
        vision: false,
        type: 'image',
        description: '人物一致性好'
      }
    ]
  },
  // 贞贞AI工坊-视频生成
  {
    value: 't8star-video',
    label: '贞贞AI工坊-视频生成',
    doc_url: 'https://ai.t8star.cn/about',
    api_base: 'https://ai.t8star.cn/v1',
    notice: '视频生成模型，Sora2/Veo3.1等。分组需在官网令牌后台配置。',
    type: 'video',
    // 分组在贞贞工坊网站后台配置，无需在此选择
    channels: [],
    models: [
      { 
        id: 'sora-2', 
        name: 'Sora 2', 
        context: '-', 
        vision: false,
        type: 'video',
        description: 'OpenAI视频生成，支持15秒'
      },
      { 
        id: 'sora-2-pro', 
        name: 'Sora 2 Pro', 
        context: '-', 
        vision: false,
        type: 'video',
        description: '高清无水印版本'
      },
      { 
        id: 'veo3.1', 
        name: 'Veo3.1', 
        context: '-', 
        vision: false,
        type: 'video',
        description: 'Google视频生成'
      },
      { 
        id: 'veo3.1-pro', 
        name: 'Veo3.1 Pro', 
        context: '-', 
        vision: false,
        type: 'video',
        description: 'Google高质量视频'
      },
      { 
        id: 'grok-video-3', 
        name: 'Grok Video 3', 
        context: '-', 
        vision: false,
        type: 'video',
        description: '支持中文配音，10秒视频'
      }
    ]
  },
  
  // ==================== 搜索服务 ====================
  {
    value: 'bocha',
    label: '博查AI搜索',
    doc_url: 'https://open.bochaai.com',
    api_base: 'https://api.bochaai.com/v1',
    notice: '国内AI搜索服务，专为AI应用优化。无需代理，直连可用。高质量多模态搜索。',
    type: 'search',
    models: [
      { 
        id: 'bocha-web-search', 
        name: '博查Web搜索', 
        context: '-', 
        vision: false,
        type: 'search',
        description: '高质量多模态AI搜索引擎，支持自然语言搜索，专为AI应用优化'
      }
    ]
  },
  {
    value: 'baidu',
    label: '百度搜索',
    doc_url: 'https://ai.baidu.com/ai-doc/AppBuilder/pmaxd1hvy',
    api_base: 'https://qianfan.baidubce.com/v2',
    notice: '百度官方搜索API，中文搜索质量最高。免费额度：100次/天，超出后按量付费。',
    type: 'search',
    models: [
      { 
        id: 'baidu-ai-search', 
        name: '百度AI搜索', 
        context: '-', 
        vision: false,
        type: 'search',
        description: '百度智能搜索，支持网页、图片、视频多模态搜索，中文内容覆盖最全'
      }
    ]
  }
]

// 按类型分组的提供商（用于前端筛选）
export const PROVIDERS_BY_TYPE = {
  text: LLM_PROVIDERS.filter(p => p.type === 'text'),
  image: LLM_PROVIDERS.filter(p => p.type === 'image'),
  video: LLM_PROVIDERS.filter(p => p.type === 'video'),
  search: LLM_PROVIDERS.filter(p => p.type === 'search')
}

// 创意生成模块配置
// 已从 modules.js 导入统一的模块配置
export { CREATIVE_MODULES } from './modules'
