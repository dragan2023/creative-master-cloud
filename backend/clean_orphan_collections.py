"""
清理孤立的ChromaDB集合

这些集合在数据库中已不存在，但仍占用空间并可能引发错误
"""
from app.core.logger import get_logger
from app.core.vector_store import VectorStore
import sys
import os

# 必须在导入chromadb之前设置pysqlite3
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(__file__))


logger = get_logger("clean_orphan")


def clean_orphan_collections():
    """清理孤立的ChromaDB集合"""
    print("\n" + "="*60)
    print("清理孤立的ChromaDB集合")
    print("="*60)

    # 孤立的集合列表（数据库中已不存在）
    orphan_collections = [
        "kb_7da6f659-4729-469d-9752-00ca9cd140a6",
        "kb_393175c3-3e13-4fcf-8434-6e877ed825df"
    ]

    vector_store = VectorStore()
    deleted_count = 0

    for coll_name in orphan_collections:
        try:
            print(f"\n尝试删除集合: {coll_name}")
            vector_store.delete_collection(coll_name)
            print(f"  ✅ 已删除")
            deleted_count += 1
        except ValueError as e:
            if "does not exist" in str(e).lower():
                print(f"  ⚠️  集合不存在（可能已被删除）")
            else:
                print(f"  ❌ 删除失败: {e}")
        except Exception as e:
            print(f"  ❌ 删除失败: {e}")

    print("\n" + "="*60)
    print(f"✅ 清理完成！共删除 {deleted_count} 个孤立集合")
    print("="*60)
    print("\n建议操作:")
    print("1. 重启后端服务")
    print("2. 检查日志确认无相关错误")


if __name__ == "__main__":
    clean_orphan_collections()
