# -*- coding: utf-8 -*-
"""
预置模型与搜索服务提供商配置

从 config.py 分离出的静态数据字典，减少主配置文件的体积。
"""
# 预置模型配置（2026年最新）
# 模型类型: text(文本模型), image(图像生成模型), video(视频模型)
# vision: 是否支持图片输入（多模态）
# description: 模型能力说明
PRESET_MODELS = {
    # ==================== 通义千问（阿里云百炼）====================
    "qianwen": {
        "name": "通义千问 (阿里云百炼)",
        "provider": "qianwen",
        "notice": "国内服务商，直连即可。支持文本、图像、视频多模态输入。",
        "models": [
            # 文本模型（多模态）
            {"id": "qwen3.5-plus", "name": "Qwen3.5-Plus", "context": "256K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "旗舰多模态模型，支持文本/图像/视频输入，擅长语言理解、逻辑推理、代码生成、智能体任务"},
            {"id": "qwen3.5-plus-2026-02-15", "name": "Qwen3.5-Plus (快照)", "context": "256K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "Qwen3.5-Plus 快照版本"},
        ],
        "default_model": "qwen3.5-plus",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "doc_url": "https://bailian.console.aliyun.com"
    },
    # 图像生成模型（单独配置）
    "qianwen-image": {
        "name": "通义千问-图像生成 (阿里云百炼)",
        "provider": "qianwen",
        "notice": "图像生成模型，通过文本描述生成图像。支持中英双语渲染。",
        "models": [
            {"id": "z-image-turbo", "name": "Z-Image-Turbo", "context": "-",
                "vision": False, "type": "image",
                "description": "轻量级文生图模型，快速生成高质量图像，分辨率512-2048px"},
            {"id": "qwen-image-edit-max-2026-01-16", "name": "Qwen-Image-Edit-Max", "context": "-",
                "vision": True, "type": "image",
                "description": "图像编辑模型，支持角色一致性、工业设计、几何推理"},
        ],
        "default_model": "z-image-turbo",
        "api_base": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        "doc_url": "https://bailian.console.aliyun.com"
    },

    # ==================== 火山引擎（豆包）====================
    "doubao": {
        "name": "豆包 (字节跳动/火山引擎)",
        "provider": "doubao",
        "notice": "模型名称需填写接入点ID（Endpoint ID），如：ep-2024xxxx-xxxxx。doubao-seed-2-0-pro支持文本、图像、视频多模态输入。",
        "models": [
            # 文本模型（多模态）
            {"id": "doubao-seed-2-0-pro-260215", "name": "Doubao-Seed-2.0-Pro", "context": "256K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "旗舰多模态模型，支持文本/图像/视频输入，擅长复杂推理、工具调用、视频理解"},
            {"id": "deepseek-v3-2-251201", "name": "DeepSeek-V3.2 (火山引擎)", "context": "128K",
                "vision": False, "type": "text", "max_output_tokens": 16384,
                "description": "DeepSeek V3.2版本，支持隐式缓存，擅长推理和工具调用"},
        ],
        "default_model": "doubao-seed-2-0-pro-260215",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "doc_url": "https://console.volcengine.com/ark"
    },
    # 图像生成模型（豆包Seedream系列）
    "doubao-image": {
        "name": "豆包-图像生成 (火山引擎)",
        "provider": "doubao",
        "notice": "Seedream系列图像生成模型，支持文本生成图像、图像编辑。",
        "models": [
            {"id": "doubao-seedream-5-0-260128", "name": "Seedream-5.0", "context": "-",
                "vision": False, "type": "image",
                "description": "最新图像生成模型，高质量文生图"},
        ],
        "default_model": "doubao-seedream-5-0-260128",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "doc_url": "https://console.volcengine.com/ark"
    },

    # ==================== DeepSeek（官方）====================
    "deepseek": {
        "name": "DeepSeek (官方)",
        "provider": "deepseek",
        "notice": "DeepSeek 官方 API，base_url 为 https://api.deepseek.com。deepseek-chat/reasoner 将于 2026/07/24 弃用，请使用 V4 系列。",
        "models": [
            {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "context": "1M",
                "vision": False, "type": "text", "max_output_tokens": 32768,
                "description": "旗舰模型，1M上下文，最强推理能力，支持思考模式（reasoning_effort参数）"},
            {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "context": "1M",
                "vision": False, "type": "text", "max_output_tokens": 32768,
                "description": "快速模型，1M上下文，高性价比。非思考模式等效旧deepseek-chat，思考模式等效旧deepseek-reasoner"},
            # 旧版兼容（2026/07/24 弃用）
            {"id": "deepseek-chat", "name": "DeepSeek Chat (旧版→V4 Flash)", "context": "128K",
                "vision": False, "type": "text", "max_output_tokens": 32768,
                "description": "⚠️ 将于2026/07/24弃用，对应V4 Flash非思考模式"},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner (旧版→V4 Flash)", "context": "128K",
                "vision": False, "type": "text", "max_output_tokens": 32768,
                "description": "⚠️ 将于2026/07/24弃用，对应V4 Flash思考模式"},
        ],
        "default_model": "deepseek-v4-flash",
        "api_base": "https://api.deepseek.com",
        "doc_url": "https://api-docs.deepseek.com"
    },

    # ==================== 硅基流动 ====================
    "siliconflow": {
        "name": "硅基流动 (SiliconFlow)",
        "provider": "siliconflow",
        "notice": "聚合平台，提供多种开源模型API，模型名称格式：开发者/模型名",
        "models": [
            {"id": "deepseek-ai/DeepSeek-V3.2", "name": "DeepSeek-V3.2", "context": "164K",
                "vision": False, "type": "text", "max_output_tokens": 16384,
                "description": "推理优先模型，支持思考模式下的工具调用，Agent能力增强"},
        ],
        "default_model": "deepseek-ai/DeepSeek-V3.2",
        "api_base": "https://api.siliconflow.cn/v1",
        "doc_url": "https://cloud.siliconflow.cn"
    },

    # ==================== OpenRouter ====================
    "openrouter": {
        "name": "OpenRouter",
        "provider": "openrouter",
        "notice": "国外模型聚合平台，国内直连，支持支付宝充值。模型格式：提供商/模型名",
        "models": [
            # Google Gemini 文本模型
            {"id": "google/gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro", "context": "1M",
                "vision": True, "type": "text", "max_output_tokens": 65536,
                "description": "Google多模态模型，擅长推理和工具调用"},
            # OpenAI 模型
            {"id": "openai/gpt-5.2-pro", "name": "GPT-5.2 Pro", "context": "400K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "OpenAI最新旗舰模型，40万token上下文，擅长编码和复杂推理"},
        ],
        "default_model": "google/gemini-3.1-pro-preview",
        "api_base": "https://openrouter.ai/api/v1",
        "doc_url": "https://openrouter.ai"
    },
    # OpenRouter 图像生成模型
    "openrouter-image": {
        "name": "OpenRouter-图像生成",
        "provider": "openrouter",
        "notice": "通过OpenRouter访问的图像生成模型。",
        "models": [
            {"id": "google/gemini-3-pro-image-preview", "name": "Gemini 3 Pro Image", "context": "-",
                "vision": False, "type": "image",
                "description": "Google最新图像生成模型，支持文本生成高质量图像"},
        ],
        "default_model": "google/gemini-3-pro-image-preview",
        "api_base": "https://openrouter.ai/api/v1",
        "doc_url": "https://openrouter.ai"
    },

    # ==================== 贞贞AI工坊（平价API聚合平台）====================
    "t8star": {
        "name": "贞贞AI工坊",
        "provider": "t8star",
        "notice": "平价API聚合平台，支持500+模型。分组需在官网令牌后台配置。",
        "api_base": "https://ai.t8star.cn/v1",
        "doc_url": "https://ai.t8star.cn/about",
        # 分组在贞贞工坊网站后台配置，无需在此选择
        "channels": [],
        "models": [
            # 文本模型
            {"id": "gpt-5.2-pro", "name": "GPT-5.2 Pro", "context": "400K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "OpenAI旗舰模型，40万token上下文"},
            {"id": "gpt-5.2-thinking", "name": "GPT-5.2 Thinking", "context": "200K",
                "vision": True, "type": "text", "max_output_tokens": 16384,
                "description": "OpenAI深度思考模型"},
            {"id": "claude-opus-4-5-20251101", "name": "Claude 4.5 Opus", "context": "200K",
                "vision": True, "type": "text", "max_output_tokens": 16384,
                "description": "Anthropic最强推理模型"},
            {"id": "glm-5", "name": "GLM-5", "context": "128K",
                "vision": False, "type": "text", "max_output_tokens": 8192,
                "description": "智谱AI SOTA模型，支持缓存计费"},
        ],
        "default_model": "gpt-5.2-pro"
    },
    # 贞贞AI工坊-图像生成
    "t8star-image": {
        "name": "贞贞AI工坊-图像生成",
        "provider": "t8star",
        "notice": "图像生成模型，支持Nano Banana 2、Gemini等。分组需在官网令牌后台配置。",
        "api_base": "https://ai.t8star.cn/v1",
        "doc_url": "https://ai.t8star.cn/about",
        # 分组在贞贞工坊网站后台配置，无需在此选择
        "channels": [],
        "models": [
            {"id": "gemini-3-pro-image-preview", "name": "Gemini 3 Pro Image", "context": "-",
                "vision": False, "type": "image",
                "description": "Google图像生成，支持高分辨率"},
            {"id": "nano-banana-2", "name": "Nano Banana 2", "context": "-",
                "vision": False, "type": "image",
                "description": "支持2K/4K高清"},
            {"id": "nano-banana-2-2k", "name": "Nano Banana 2 (2K)", "context": "-",
                "vision": False, "type": "image",
                "description": "固定2K分辨率"},
            {"id": "nano-banana-2-4k", "name": "Nano Banana 2 (4K)", "context": "-",
                "vision": False, "type": "image",
                "description": "固定4K分辨率"},
            {"id": "doubao-seedream-4-5", "name": "豆包Seedream 4.5", "context": "-",
                "vision": False, "type": "image",
                "description": "人物一致性好"},
        ],
        "default_model": "gemini-3-pro-image-preview"
    },
    # 贞贞AI工坊-视频生成
    "t8star-video": {
        "name": "贞贞AI工坊-视频生成",
        "provider": "t8star",
        "notice": "视频生成模型，Sora2/Veo3.1等。分组需在官网令牌后台配置。",
        "api_base": "https://ai.t8star.cn/v1",
        "doc_url": "https://ai.t8star.cn/about",
        # 分组在贞贞工坊网站后台配置，无需在此选择
        "channels": [],
        "models": [
            {"id": "sora-2", "name": "Sora 2", "context": "-",
                "vision": False, "type": "video",
                "description": "OpenAI视频生成，支持15秒"},
            {"id": "sora-2-pro", "name": "Sora 2 Pro", "context": "-",
                "vision": False, "type": "video",
                "description": "高清无水印版本"},
            {"id": "veo3.1", "name": "Veo3.1", "context": "-",
                "vision": False, "type": "video",
                "description": "Google视频生成"},
            {"id": "veo3.1-pro", "name": "Veo3.1 Pro", "context": "-",
                "vision": False, "type": "video",
                "description": "Google高质量视频"},
            {"id": "grok-video-3", "name": "Grok Video 3", "context": "-",
                "vision": False, "type": "video",
                "description": "支持中文配音，10秒视频"},
        ],
        "default_model": "sora-2"
    }
}

# ==================== 搜索服务提供商配置（国产化）====================
SEARCH_PROVIDERS = {
    "bocha": {
        "name": "博查AI搜索",
        "api_base": "https://api.bochaai.com/v1",
        "test_endpoint": "/web-search",
        "doc_url": "https://open.bochaai.com",
        "notice": "国内AI搜索服务，专为AI应用优化。无需代理，直连可用。",
        "models": [
            {"id": "bocha-web-search", "name": "博查Web搜索", "type": "search",
                "description": "高质量多模态AI搜索引擎，支持自然语言搜索"}
        ],
        "default_model": "bocha-web-search"
    },
    "baidu": {
        "name": "百度搜索",
        "api_base": "https://qianfan.baidubce.com/v2",
        "test_endpoint": "/ai_search/chat/completions",
        "doc_url": "https://ai.baidu.com/ai-doc/AppBuilder/pmaxd1hvy",
        "notice": "百度官方搜索API，中文搜索质量最高。免费额度：100次/天。",
        "models": [
            {"id": "baidu-ai-search", "name": "百度AI搜索", "type": "search",
                "description": "百度智能搜索，支持网页、图片、视频多模态搜索"}
        ],
        "default_model": "baidu-ai-search"
    }
}

__all__ = ["PRESET_MODELS", "SEARCH_PROVIDERS"]
