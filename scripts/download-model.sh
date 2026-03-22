#!/bin/bash
# ========================================
# 下载 HuggingFace 嵌入模型
# ========================================

set -e

echo "========================================"
echo "下载 all-MiniLM-L6-v2 嵌入模型"
echo "========================================"

# 模型保存目录
MODEL_DIR="backend/data/chroma/models"
mkdir -p "$MODEL_DIR"

# 检查是否设置代理
if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ]; then
    echo "使用代理: $HTTP_PROXY"
fi

# 使用Python下载模型
echo "正在下载模型..."
python3 << 'EOF'
import os
import sys

# 设置模型缓存目录
model_dir = "backend/data/chroma/models"
os.environ["HF_HOME"] = model_dir
os.environ["SENTENCE_TRANSFORMERS_HOME"] = model_dir

try:
    from sentence_transformers import SentenceTransformer
    print("正在下载 all-MiniLM-L6-v2 模型...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("模型下载成功！")
except Exception as e:
    print(f"下载失败: {e}")
    sys.exit(1)
EOF

echo ""
echo "模型已保存到: $MODEL_DIR"
echo "完成！"
