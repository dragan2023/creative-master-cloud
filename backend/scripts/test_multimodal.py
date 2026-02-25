"""
多模态功能测试脚本
测试远端 LLM 的图片识别和视频理解能力

使用方法:
    cd backend
    python scripts/test_multimodal.py --test image --api-key YOUR_API_KEY
    python scripts/test_multimodal.py --test video --api-key YOUR_API_KEY
    python scripts/test_multimodal.py --test file --api-key YOUR_API_KEY --file path/to/file.pdf
"""
from openai import AsyncOpenAI
import asyncio
import argparse
import base64
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))


# ==================== 配置 ====================

# 豆包 API 配置
DOUBAO_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
DOUBAO_MODEL = "doubao-seed-2-0-pro-260215"

# 测试图片 URL（公开的测试图片）
TEST_IMAGE_URL = "https://picsum.photos/800/600"

# 测试视频 URL（公开的测试视频）
TEST_VIDEO_URL = "https://www.w3schools.com/html/mov_bbb.mp4"


# ==================== 工具函数 ====================

def encode_file_to_base64(file_path: str) -> str:
    """将文件编码为 base64"""
    with open(file_path, "rb") as f:
        data = f.read()

    # 获取 MIME 类型
    ext = Path(file_path).suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }
    mime_type = mime_types.get(ext, "application/octet-stream")

    base64_data = base64.b64encode(data).decode("utf-8")
    return f"data:{mime_type};base64,{base64_data}"


def get_file_base64_from_url(url: str) -> str:
    """从 URL 获取文件并编码为 base64"""
    import httpx
    response = httpx.get(url, follow_redirects=True)
    content_type = response.headers.get(
        "content-type", "application/octet-stream")
    base64_data = base64.b64encode(response.content).decode("utf-8")
    return f"data:{content_type};base64,{base64_data}"


# ==================== 测试函数 ====================

async def test_image_recognition(api_key: str, image_path: str = None, image_url: str = None):
    """
    测试图片识别能力

    Args:
        api_key: API 密钥
        image_path: 本地图片路径（可选）
        image_url: 图片 URL（可选）
    """
    print("\n" + "="*60)
    print("📸 图片识别测试")
    print("="*60)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=DOUBAO_API_BASE
    )

    # 准备图片数据
    if image_path and os.path.exists(image_path):
        print(f"📁 使用本地图片: {image_path}")
        image_data = encode_file_to_base64(image_path)
    elif image_url:
        print(f"🌐 使用网络图片: {image_url}")
        image_data = image_url  # 直接使用 URL
    else:
        print(f"🌐 使用默认测试图片: {TEST_IMAGE_URL}")
        image_data = TEST_IMAGE_URL

    # 构建消息
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请详细描述这张图片的内容，包括：\n1. 图片的主题和主体\n2. 颜色和构图\n3. 如果是人物，描述其表情、动作、着装\n4. 整体氛围和感觉\n5. 任何你认为有趣的细节"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_data}
                }
            ]
        }
    ]

    print(f"\n🤖 使用模型: {DOUBAO_MODEL}")
    print("⏳ 正在请求 LLM...")

    try:
        response = await client.chat.completions.create(
            model=DOUBAO_MODEL,
            messages=messages,
            max_tokens=1024
        )

        print("\n" + "-"*60)
        print("📝 LLM 响应:")
        print("-"*60)
        print(response.choices[0].message.content)
        print("-"*60)

        # 显示使用情况
        if response.usage:
            print(f"\n📊 Token 使用:")
            print(f"   - Prompt tokens: {response.usage.prompt_tokens}")
            print(
                f"   - Completion tokens: {response.usage.completion_tokens}")
            print(f"   - Total tokens: {response.usage.total_tokens}")

        print("\n✅ 图片识别测试成功！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {type(e).__name__}: {str(e)}")
        return False


async def test_video_understanding(api_key: str, video_path: str = None, video_url: str = None):
    """
    测试视频理解能力

    Args:
        api_key: API 密钥
        video_path: 本地视频路径（可选）
        video_url: 视频 URL（可选）
    """
    print("\n" + "="*60)
    print("🎬 视频理解测试")
    print("="*60)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=DOUBAO_API_BASE
    )

    # 准备视频数据
    if video_path and os.path.exists(video_path):
        print(f"📁 使用本地视频: {video_path}")
        print("⚠️ 注意：视频文件较大，编码可能需要一些时间...")
        video_data = encode_file_to_base64(video_path)
    elif video_url:
        print(f"🌐 使用网络视频: {video_url}")
        video_data = video_url  # 直接使用 URL
    else:
        print(f"🌐 使用默认测试视频: {TEST_VIDEO_URL}")
        video_data = TEST_VIDEO_URL

    # 构建消息
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请分析这个视频的内容，包括：\n1. 视频的主要内容和主题\n2. 场景描述\n3. 如果有人物或动物，描述其行为\n4. 视频的整体风格和氛围\n5. 任何你认为值得注意的细节"
                },
                {
                    "type": "video_url",
                    "video_url": {"url": video_data}
                }
            ]
        }
    ]

    print(f"\n🤖 使用模型: {DOUBAO_MODEL}")
    print("⏳ 正在请求 LLM（视频处理可能需要较长时间）...")

    try:
        response = await client.chat.completions.create(
            model=DOUBAO_MODEL,
            messages=messages,
            max_tokens=2048
        )

        print("\n" + "-"*60)
        print("📝 LLM 响应:")
        print("-"*60)
        print(response.choices[0].message.content)
        print("-"*60)

        # 显示使用情况
        if response.usage:
            print(f"\n📊 Token 使用:")
            print(f"   - Prompt tokens: {response.usage.prompt_tokens}")
            print(
                f"   - Completion tokens: {response.usage.completion_tokens}")
            print(f"   - Total tokens: {response.usage.total_tokens}")

        print("\n✅ 视频理解测试成功！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_file_parsing(api_key: str, file_path: str):
    """
    测试文件解析能力

    Args:
        api_key: API 密钥
        file_path: 文件路径
    """
    print("\n" + "="*60)
    print("📄 文件解析测试")
    print("="*60)

    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False

    # 使用项目的 FileParser 解析文件
    from app.tools.file_parser import get_file_parser

    file_parser = get_file_parser()

    print(f"📁 解析文件: {file_path}")
    print("⏳ 正在解析...")

    result = await file_parser.parse(file_path)

    if "error" in result:
        print(f"❌ 解析失败: {result['error']}")
        return False

    content = result.get("content", "")
    metadata = result.get("metadata", {})

    print(f"\n📊 文件信息:")
    for key, value in metadata.items():
        print(f"   - {key}: {value}")

    print(f"\n📝 文件内容预览 (前 500 字符):")
    print("-"*60)
    print(content[:500] + ("..." if len(content) > 500 else ""))
    print("-"*60)

    # 使用 LLM 总结文件内容
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=DOUBAO_API_BASE
    )

    print(f"\n🤖 使用 LLM 总结文件内容...")

    try:
        response = await client.chat.completions.create(
            model=DOUBAO_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的文档分析助手。请简洁地总结用户提供的文档内容。"
                },
                {
                    "role": "user",
                    "content": f"请总结以下文档的主要内容：\n\n{content}"
                }
            ],
            max_tokens=1024
        )

        print("\n" + "-"*60)
        print("📝 LLM 总结:")
        print("-"*60)
        print(response.choices[0].message.content)
        print("-"*60)

        print("\n✅ 文件解析测试成功！")
        return True

    except Exception as e:
        print(f"❌ LLM 请求失败: {type(e).__name__}: {str(e)}")
        return False


async def test_multimodal_combined(api_key: str, image_path: str = None):
    """
    测试多模态组合（文本 + 图片）
    """
    print("\n" + "="*60)
    print("🔀 多模态组合测试（文本 + 图片）")
    print("="*60)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=DOUBAO_API_BASE
    )

    # 准备图片数据
    if image_path and os.path.exists(image_path):
        image_data = encode_file_to_base64(image_path)
    else:
        image_data = TEST_IMAGE_URL

    # 构建多模态消息
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "这张图片可以用于什么类型的广告创意？请给出3个具体的创意方向，每个方向包含：\n1. 广告主题\n2. 目标受众\n3. 核心卖点\n4. 文案建议"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_data}
                }
            ]
        }
    ]

    print(f"🤖 使用模型: {DOUBAO_MODEL}")
    print("⏳ 正在请求 LLM...")

    try:
        response = await client.chat.completions.create(
            model=DOUBAO_MODEL,
            messages=messages,
            max_tokens=2048
        )

        print("\n" + "-"*60)
        print("📝 LLM 响应:")
        print("-"*60)
        print(response.choices[0].message.content)
        print("-"*60)

        print("\n✅ 多模态组合测试成功！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {type(e).__name__}: {str(e)}")
        return False


# ==================== 主函数 ====================

async def main():
    parser = argparse.ArgumentParser(description="多模态功能测试脚本")
    parser.add_argument(
        "--test", "-t",
        choices=["image", "video", "file", "combined", "all"],
        default="all",
        help="测试类型: image(图片), video(视频), file(文件), combined(组合), all(全部)"
    )
    parser.add_argument(
        "--api-key", "-k",
        required=True,
        help="豆包 API 密钥"
    )
    parser.add_argument(
        "--file", "-f",
        help="测试文件路径（用于 file 测试）"
    )
    parser.add_argument(
        "--image", "-i",
        help="测试图片路径（用于 image 测试）"
    )
    parser.add_argument(
        "--video", "-v",
        help="测试视频路径（用于 video 测试）"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("🚀 多模态功能测试")
    print("="*60)
    print(f"测试类型: {args.test}")
    print(f"模型: {DOUBAO_MODEL}")
    print(f"API Base: {DOUBAO_API_BASE}")

    results = {}

    if args.test in ["image", "all"]:
        results["image"] = await test_image_recognition(args.api_key, args.image)

    if args.test in ["video", "all"]:
        results["video"] = await test_video_understanding(args.api_key, args.video)

    if args.test in ["file", "all"]:
        if args.file:
            results["file"] = await test_file_parsing(args.api_key, args.file)
        elif args.test == "all":
            print("\n⚠️ 跳过文件测试：未指定测试文件（使用 --file 参数指定）")

    if args.test in ["combined", "all"]:
        results["combined"] = await test_multimodal_combined(args.api_key, args.image)

    # 打印结果汇总
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")

    # 返回退出码
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
