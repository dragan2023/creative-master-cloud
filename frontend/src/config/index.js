// API基础配置
// 开发环境使用空字符串，让请求走 Vite 代理（避免 CORS）
// 生产环境使用完整 URL
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// LLM提供商配置（2025-2026年最新）
// 所有服务商使用OpenAI兼容API格式，用户可自定义api_base和model_name
// vision: 是否支持图片输入（多模态）
// description: 模型能力说明
export const LLM_PROVIDERS = [
  {
    value: 'deepseek',
    label: 'DeepSeek',
    doc_url: 'https://platform.deepseek.com',
    api_base: 'https://api.deepseek.com/v1',
    notice: '国内服务商，直连即可',
    models: [
      { 
        id: 'deepseek-chat', 
        name: 'DeepSeek-V3.2', 
        context: '128K', 
        vision: false,
        description: '通用对话模型，擅长创意写作、代码生成、逻辑推理'
      },
      { 
        id: 'deepseek-reasoner', 
        name: 'DeepSeek-R1', 
        context: '128K', 
        vision: false,
        description: '深度推理模型，擅长数学计算、复杂逻辑分析'
      }
    ]
  },
  {
    value: 'doubao',
    label: '豆包 (字节跳动/火山引擎)',
    doc_url: 'https://console.volcengine.com/ark',
    api_base: 'https://ark.cn-beijing.volces.com/api/v3',
    notice: '模型名称需填写接入点ID（Endpoint ID），如：ep-2024xxxx-xxxxx。请在火山引擎控制台创建推理接入点后获取。',
    models: [
      { 
        id: 'ep-xxxx-xxxx', 
        name: 'Endpoint ID示例', 
        context: '256K', 
        vision: true,
        description: '请在火山引擎控制台创建接入点，使用接入点ID作为模型名称'
      }
    ]
  },
  {
    value: 'qianwen',
    label: '通义千问 (阿里云)',
    doc_url: 'https://bailian.console.aliyun.com',
    api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    notice: '国内服务商，直连即可',
    models: [
      { 
        id: 'qwen-max', 
        name: 'Qwen-Max', 
        context: '256K', 
        vision: true,
        description: '旗舰多模态模型，综合能力最强'
      },
      { 
        id: 'qwen-plus', 
        name: 'Qwen-Plus', 
        context: '1M', 
        vision: true,
        description: '多模态模型，超长上下文'
      },
      { 
        id: 'qwen-turbo', 
        name: 'Qwen-Turbo', 
        context: '1M', 
        vision: true,
        description: '快速多模态模型，响应快'
      },
      { 
        id: 'qwen-coder-plus', 
        name: 'Qwen-Coder-Plus', 
        context: '1M', 
        vision: false,
        description: '代码专用模型'
      },
      { 
        id: 'qwen-vl-max', 
        name: 'Qwen-VL-Max', 
        context: '32K', 
        vision: true,
        description: '视觉理解专用模型，擅长OCR、图表分析'
      }
    ]
  },
  {
    value: 'zhipu',
    label: '智谱AI (GLM)',
    doc_url: 'https://open.bigmodel.cn',
    api_base: 'https://open.bigmodel.cn/api/paas/v4',
    notice: '国内服务商，直连即可',
    models: [
      { 
        id: 'glm-4-plus', 
        name: 'GLM-4-Plus', 
        context: '128K', 
        vision: false,
        description: '旗舰对话模型，擅长中文创作、知识问答'
      },
      { 
        id: 'glm-4-flash', 
        name: 'GLM-4-Flash', 
        context: '128K', 
        vision: false,
        description: '快速模型，性价比高'
      },
      { 
        id: 'glm-4-air', 
        name: 'GLM-4-Air', 
        context: '128K', 
        vision: false,
        description: '均衡模型'
      },
      { 
        id: 'glm-z1-air', 
        name: 'GLM-Z1-Air', 
        context: '128K', 
        vision: false,
        description: '推理增强模型'
      },
      { 
        id: 'glm-4v-plus', 
        name: 'GLM-4V-Plus', 
        context: '128K', 
        vision: true,
        description: '多模态模型，支持图片理解'
      }
    ]
  },
  {
    value: 'moonshot',
    label: '月之暗面 (Kimi)',
    doc_url: 'https://platform.moonshot.cn',
    api_base: 'https://api.moonshot.cn/v1',
    notice: '国内服务商，直连即可',
    models: [
      { 
        id: 'kimi-latest', 
        name: 'Kimi Latest', 
        context: '128K', 
        vision: true,
        description: '最新多模态模型，综合能力最强'
      },
      { 
        id: 'moonshot-v1-8k', 
        name: 'Moonshot V1 8K', 
        context: '8K', 
        vision: false,
        description: '标准模型'
      },
      { 
        id: 'moonshot-v1-32k', 
        name: 'Moonshot V1 32K', 
        context: '32K', 
        vision: false,
        description: '中长上下文模型'
      },
      { 
        id: 'moonshot-v1-128k', 
        name: 'Moonshot V1 128K', 
        context: '128K', 
        vision: false,
        description: '长上下文模型'
      }
    ]
  },
  {
    value: 'baichuan',
    label: '百川智能',
    doc_url: 'https://platform.baichuan-ai.com',
    api_base: 'https://api.baichuan-ai.com/v1',
    notice: '国内服务商，直连即可',
    models: [
      { 
        id: 'Baichuan4', 
        name: 'Baichuan4', 
        context: '128K', 
        vision: true,
        description: '旗舰多模态模型'
      },
      { 
        id: 'Baichuan4-Turbo', 
        name: 'Baichuan4 Turbo', 
        context: '128K', 
        vision: true,
        description: '快速多模态模型'
      },
      { 
        id: 'Baichuan3-Turbo', 
        name: 'Baichuan3 Turbo', 
        context: '128K', 
        vision: false,
        description: '对话模型'
      }
    ]
  },
  {
    value: 'minimax',
    label: 'MiniMax',
    doc_url: 'https://platform.minimax.io',
    api_base: 'https://api.minimax.chat/v1',
    notice: '部分API需要group_id参数，请参考官方文档',
    models: [
      { 
        id: 'MiniMax-Text-01', 
        name: 'MiniMax-Text-01', 
        context: '4M', 
        vision: false,
        description: '超长上下文模型（400万token）'
      },
      { 
        id: 'abab6.5s-chat', 
        name: 'abab6.5s', 
        context: '245K', 
        vision: false,
        description: '快速模型'
      },
      { 
        id: 'abab6.5g-chat', 
        name: 'abab6.5g', 
        context: '245K', 
        vision: true,
        description: '多模态模型'
      }
    ]
  },
  {
    value: 'yi',
    label: '零一万物 (Yi)',
    doc_url: 'https://platform.lingyiwanwu.com',
    api_base: 'https://api.lingyiwanwu.com/v1',
    notice: '国内服务商，直连即可',
    models: [
      { 
        id: 'yi-large', 
        name: 'Yi Large', 
        context: '32K', 
        vision: false,
        description: '旗舰对话模型'
      },
      { 
        id: 'yi-large-turbo', 
        name: 'Yi Large Turbo', 
        context: '16K', 
        vision: false,
        description: '快速模型'
      },
      { 
        id: 'yi-medium', 
        name: 'Yi Medium', 
        context: '16K', 
        vision: false,
        description: '均衡模型'
      },
      { 
        id: 'yi-vl-plus', 
        name: 'Yi-VL-Plus', 
        context: '16K', 
        vision: true,
        description: '多模态模型'
      }
    ]
  },
  {
    value: 'siliconflow',
    label: '硅基流动 (SiliconFlow)',
    doc_url: 'https://cloud.siliconflow.cn',
    api_base: 'https://api.siliconflow.cn/v1',
    notice: '聚合平台，提供多种开源模型API，模型名称格式：开发者/模型名',
    models: [
      { 
        id: 'deepseek-ai/DeepSeek-V3', 
        name: 'DeepSeek-V3', 
        context: '64K', 
        vision: false,
        description: '开源旗舰模型'
      },
      { 
        id: 'Qwen/Qwen2.5-72B-Instruct', 
        name: 'Qwen2.5-72B', 
        context: '32K', 
        vision: false,
        description: '开源大模型'
      },
      { 
        id: 'Qwen/Qwen2-VL-72B-Instruct', 
        name: 'Qwen2-VL-72B', 
        context: '32K', 
        vision: true,
        description: '开源多模态模型'
      },
      { 
        id: 'meta-llama/Llama-3.3-70B-Instruct', 
        name: 'Llama-3.3-70B', 
        context: '8K', 
        vision: false,
        description: 'Meta开源模型'
      }
    ]
  },
  {
    value: 'modelscope',
    label: '魔搭 (ModelScope)',
    doc_url: 'https://modelscope.cn',
    api_base: 'https://api-inference.modelscope.cn/v1',
    notice: '阿里云模型社区，提供多种模型API',
    models: [
      { 
        id: 'qwen-plus', 
        name: 'Qwen-Plus', 
        context: '128K', 
        vision: true,
        description: '多模态模型'
      },
      { 
        id: 'qwen-turbo', 
        name: 'Qwen-Turbo', 
        context: '8K', 
        vision: false,
        description: '快速模型'
      },
      { 
        id: 'qwen-max', 
        name: 'Qwen-Max', 
        context: '32K', 
        vision: true,
        description: '旗舰多模态模型'
      },
      { 
        id: 'deepseek-v3', 
        name: 'DeepSeek-V3', 
        context: '64K', 
        vision: false,
        description: '开源旗舰模型'
      }
    ]
  },
  {
    value: 'openai',
    label: 'OpenAI',
    doc_url: 'https://platform.openai.com',
    api_base: 'https://api.openai.com/v1',
    notice: '国外服务商，需要代理访问',
    models: [
      { 
        id: 'gpt-4o', 
        name: 'GPT-4o', 
        context: '128K', 
        vision: true,
        description: '旗舰多模态模型，综合能力最强'
      },
      { 
        id: 'gpt-4o-mini', 
        name: 'GPT-4o Mini', 
        context: '128K', 
        vision: true,
        description: '轻量多模态模型，性价比高'
      },
      { 
        id: 'gpt-4-turbo', 
        name: 'GPT-4 Turbo', 
        context: '128K', 
        vision: true,
        description: '多模态模型'
      },
      { 
        id: 'o1-preview', 
        name: 'o1 Preview', 
        context: '128K', 
        vision: false,
        description: '推理增强模型'
      },
      { 
        id: 'o1-mini', 
        name: 'o1 Mini', 
        context: '128K', 
        vision: false,
        description: '轻量推理模型'
      }
    ]
  },
  {
    value: 'google',
    label: 'Google Gemini',
    doc_url: 'https://aistudio.google.com',
    api_base: '',  // Google使用自己的SDK，不需要api_base
    notice: '国外服务商，需要代理访问。使用Google AI Studio API Key',
    models: [
      { 
        id: 'gemini-2.0-flash', 
        name: 'Gemini 2.0 Flash', 
        context: '1M', 
        vision: true,
        description: '最新多模态模型，响应快'
      },
      { 
        id: 'gemini-2.0-flash-lite', 
        name: 'Gemini 2.0 Flash-Lite', 
        context: '1M', 
        vision: true,
        description: '轻量多模态模型'
      },
      { 
        id: 'gemini-1.5-pro', 
        name: 'Gemini 1.5 Pro', 
        context: '2M', 
        vision: true,
        description: '超长上下文多模态模型（200万token）'
      },
      { 
        id: 'gemini-1.5-flash', 
        name: 'Gemini 1.5 Flash', 
        context: '1M', 
        vision: true,
        description: '快速多模态模型'
      }
    ]
  },
  {
    value: 'openrouter',
    label: 'OpenRouter',
    doc_url: 'https://openrouter.ai',
    api_base: 'https://openrouter.ai/api/v1',
    notice: '国外模型聚合平台，国内直连，支持支付宝充值。模型格式：提供商/模型名',
    models: [
      // OpenAI 模型
      { 
        id: 'openai/gpt-4o', 
        name: 'GPT-4o', 
        context: '128K', 
        vision: true,
        description: 'OpenAI旗舰多模态模型'
      },
      { 
        id: 'openai/gpt-4o-mini', 
        name: 'GPT-4o Mini', 
        context: '128K', 
        vision: true,
        description: '轻量多模态模型，性价比高'
      },
      { 
        id: 'openai/o1-preview', 
        name: 'o1 Preview', 
        context: '128K', 
        vision: false,
        description: '推理增强模型'
      },
      { 
        id: 'openai/o1-mini', 
        name: 'o1 Mini', 
        context: '128K', 
        vision: false,
        description: '轻量推理模型'
      },
      // Google 模型
      { 
        id: 'google/gemini-2.0-flash-001', 
        name: 'Gemini 2.0 Flash', 
        context: '1M', 
        vision: true,
        description: 'Google最新多模态模型'
      },
      { 
        id: 'google/gemini-1.5-pro', 
        name: 'Gemini 1.5 Pro', 
        context: '2M', 
        vision: true,
        description: '超长上下文模型'
      },
      { 
        id: 'google/gemini-1.5-flash', 
        name: 'Gemini 1.5 Flash', 
        context: '1M', 
        vision: true,
        description: '快速多模态模型'
      },
      // Anthropic 模型
      { 
        id: 'anthropic/claude-3.5-sonnet', 
        name: 'Claude 3.5 Sonnet', 
        context: '200K', 
        vision: true,
        description: 'Anthropic最强模型'
      },
      { 
        id: 'anthropic/claude-3.5-haiku', 
        name: 'Claude 3.5 Haiku', 
        context: '200K', 
        vision: true,
        description: '快速轻量模型'
      },
      { 
        id: 'anthropic/claude-3-opus', 
        name: 'Claude 3 Opus', 
        context: '200K', 
        vision: true,
        description: '旗舰模型'
      },
      // xAI 模型
      { 
        id: 'x-ai/grok-beta', 
        name: 'Grok Beta', 
        context: '128K', 
        vision: false,
        description: 'xAI旗舰模型'
      },
      { 
        id: 'x-ai/grok-2-1212', 
        name: 'Grok 2', 
        context: '128K', 
        vision: false,
        description: 'xAI最新模型'
      },
      // Meta 模型
      { 
        id: 'meta-llama/llama-3.3-70b-instruct', 
        name: 'Llama 3.3 70B', 
        context: '8K', 
        vision: false,
        description: 'Meta开源旗舰模型'
      },
      { 
        id: 'meta-llama/llama-3.2-90b-vision-instruct', 
        name: 'Llama 3.2 90B Vision', 
        context: '128K', 
        vision: true,
        description: 'Meta多模态模型'
      },
      // DeepSeek 模型
      { 
        id: 'deepseek/deepseek-chat', 
        name: 'DeepSeek Chat', 
        context: '64K', 
        vision: false,
        description: 'DeepSeek对话模型'
      },
      { 
        id: 'deepseek/deepseek-r1', 
        name: 'DeepSeek R1', 
        context: '64K', 
        vision: false,
        description: 'DeepSeek推理模型'
      }
    ]
  }
]

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
