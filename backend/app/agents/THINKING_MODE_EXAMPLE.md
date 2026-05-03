# DeepSeek 思考模式配置示例

## 功能说明

DeepSeek V4 Pro 和 V4 Flash 模型支持思考模式（Thinking Mode），在输出最终回答之前，模型会先输出一段思维链内容（reasoning_content），以提升最终答案的准确性。

## 配置方式

### 1. 环境变量配置（可选）

在 `.env` 文件中添加以下配置：

```bash
# DeepSeek思考模式配置
DEEPSEEK_ENABLE_THINKING=true        # 是否启用思考模式（默认false）
DEEPSEEK_REASONING_EFFORT=high       # 思考强度：high 或 max（默认high）
DEEPSEEK_THINKING_SAVE_DIR=./data/thinking_logs  # 思考过程保存目录
```

### 2. 代码中使用

#### 方式一：通过 LLM Manager 创建时指定

```python
from app.agents.llm_manager import get_llm_manager

llm_manager = get_llm_manager()

# 创建支持思考模式的 DeepSeek 提供者
provider = llm_manager.create_provider(
    provider_name="deepseek",
    api_key="your-api-key",
    model_name="deepseek-v4-pro",
    reasoning_effort="high",          # 思考强度：high 或 max
    enable_thinking=True,             # 启用思考模式
    thinking_save_dir="./data/thinking_logs"  # 思考过程保存目录
)

# 调用时指定模块名称（用于文件名）
response = await provider.generate(
    prompt="请分析这个故事的逻辑结构",
    module_name="logic_analysis"  # 将保存为 logic_analysis_20260430_143022.txt
)

# 访问思考过程（可选）
if response.reasoning_content:
    print("思考过程已保存到文件")
```

#### 方式二：直接创建 DeepSeekProvider

```python
from app.agents.deepseek_provider import DeepSeekProvider

provider = DeepSeekProvider(
    api_key="your-api-key",
    model_name="deepseek-v4-pro",
    reasoning_effort="max",           # 使用最高思考强度
    enable_thinking=True,
    thinking_save_dir="./data/thinking_logs"
)

# 非流式调用
response = await provider.generate(
    prompt="请进行深度文学分析",
    module_name="literature_analysis"
)

# 流式调用（思考过程不会输出到前端，但会保存到文件）
async for chunk in provider.generate_stream(
    prompt="请进行深度文学分析",
    module_name="literature_analysis_stream"
):
    print(chunk, end="", flush=True)
```

## 思考过程文件

思考过程会自动保存到指定目录，文件命名格式为：

```
{模块名}_{时间戳}.txt
```

示例：
- `logic_analysis_20260430_143022.txt`
- `literature_analysis_stream_20260430_143045.txt`

文件内容格式：

```
=== DeepSeek 思考过程记录 ===
时间: 2026-04-30 14:30:22
模型: deepseek-v4-pro
模块: logic_analysis
思考强度: high
==================================================

[这里是完整的思考过程内容...]
```

## 重要说明

### 1. 思考模式参数限制

根据 DeepSeek 官方文档，启用思考模式后，以下参数**不会生效**：
- `temperature`
- `top_p`
- `presence_penalty`
- `frequency_penalty`

系统会自动处理这些参数的冲突。

### 2. 支持的模型

目前支持思考模式的模型：
- `deepseek-v4-pro`（推荐，最强推理能力）
- `deepseek-v4-flash`（高性价比）
- `deepseek-reasoner`（旧版，将于2026/07/24弃用）

### 3. 思考强度选项

- `high`：高强度思考（默认，适用于大多数复杂任务）
- `max`：最高强度思考（适用于极复杂的推理任务，耗时更长）

### 4. 多轮对话说明

根据官方文档：
- 如果模型**未进行工具调用**，则中间 assistant 的 `reasoning_content` 无需参与上下文拼接
- 如果模型**进行了工具调用**，则中间 assistant 的 `reasoning_content` **必须**参与上下文拼接

### 5. 前端显示

思考过程**不会**显示在前端，只会：
1. 保存到指定的日志目录
2. 在 `LLMResponse` 对象的 `reasoning_content` 字段中返回（供后端使用）

## 完整示例：在质控分析中使用思考模式

```python
from app.agents.llm_manager import get_llm_manager

async def analyze_with_thinking(prompt: str, module_name: str):
    """使用思考模式进行深度分析"""
    llm_manager = get_llm_manager()
    
    provider = llm_manager.create_provider(
        provider_name="deepseek",
        api_key="your-api-key",
        model_name="deepseek-v4-pro",
        reasoning_effort="high",
        enable_thinking=True,
        thinking_save_dir="./data/thinking_logs"
    )
    
    response = await provider.generate(
        prompt=prompt,
        system_prompt="你是一个专业的文学分析助手。",
        module_name=module_name
    )
    
    return {
        "content": response.content,
        "has_thinking": response.reasoning_content is not None,
        "usage": response.usage
    }
```

## 查看思考过程

所有思考过程文件保存在 `./data/thinking_logs/` 目录下，你可以随时查看：

```bash
# Windows PowerShell
Get-ChildItem .\data\thinking_logs\ -Name

# 查看特定文件
Get-Content .\data\thinking_logs\logic_analysis_20260430_143022.txt
```

## 性能影响

启用思考模式后：
- ⏱️ **响应时间**：增加 30%-100%（取决于思考强度）
- 💰 **Token消耗**：增加（reasoning_content 也计入输出token）
- ✅ **输出质量**：显著提升复杂任务的答案准确性

建议在以下场景启用：
- 逻辑分析
- 复杂推理
- 质控检测
- 文学评论

在以下场景可以关闭：
- 简单问答
- 内容生成（小说、文章）
- 快速响应需求
