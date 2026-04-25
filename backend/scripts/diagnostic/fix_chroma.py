"""
修复ChromaDB向量库索引损坏问题
"""
import sys
from pathlib import Path
import shutil
import json

# 添加backend目录到路径
backend_dir = Path(__file__).parent
chroma_dir = backend_dir / "data" / "chroma"


def check_chroma_health():
    """检查ChromaDB知识库健康状态"""
    if not chroma_dir.exists():
        print(f"❌ ChromaDB目录不存在: {chroma_dir}")
        return False

    print(f"✓ ChromaDB目录: {chroma_dir}")
    kb_dirs = list(chroma_dir.glob("*"))
    print(f"✓ 知识库总数: {len(kb_dirs)}")

    broken_kbs = []

    for kb_dir in kb_dirs:
        if not kb_dir.is_dir():
            continue

        kb_id = kb_dir.name

        # 检查是否存在关键文件
        hnsw_dir = kb_dir / "hnsw_index"
        metadata_file = kb_dir / "chroma.sqlite3"

        has_hnsw = hnsw_dir.exists()
        has_metadata = metadata_file.exists()

        if not has_metadata:
            print(f"\n⚠️  知识库 {kb_id}: 缺少metadata文件")
            broken_kbs.append(kb_id)
            continue

        if not has_hnsw:
            print(f"⚠️  知识库 {kb_id}: 缺少HNSW索引(可能正常)")

    if broken_kbs:
        print(f"\n❌ 发现 {len(broken_kbs)} 个损坏的知识库:")
        for kb_id in broken_kbs:
            print(f"  - {kb_id}")
        return False
    else:
        print("\n✅ 所有知识库检查通过")
        return True


def fix_broken_kb(kb_id):
    """修复单个损坏的知识库"""
    kb_dir = chroma_dir / kb_id

    if not kb_dir.exists():
        print(f"知识库目录不存在: {kb_id}")
        return False

    print(f"\n修复知识库: {kb_id}")

    # 备份原目录
    backup_dir = chroma_dir / f"{kb_id}_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    print(f"  1. 备份到 {backup_dir.name}")
    shutil.copytree(kb_dir, backup_dir)

    # 删除损坏的索引
    hnsw_dir = kb_dir / "hnsw_index"
    if hnsw_dir.exists():
        print(f"  2. 删除损坏的HNSW索引")
        shutil.rmtree(hnsw_dir)

    print(f"  3. ✓ 修复完成,需要重新构建索引")
    print(f"  提示: 请在系统中重新导入该知识库的文档")

    return True


def main():
    print("=" * 60)
    print("ChromaDB向量库健康检查与修复工具")
    print("=" * 60)

    # 检查健康状态
    is_healthy = check_chroma_health()

    if is_healthy:
        print("\n✅ 无需修复,所有知识库正常")
        return

    # 询问是否修复
    print("\n" + "=" * 60)
    response = input("是否修复损坏的知识库? (y/n): ").strip().lower()

    if response != 'y':
        print("取消修复")
        return

    # 获取损坏的kb列表
    kb_dirs = list(chroma_dir.glob("*"))
    broken_kbs = []

    for kb_dir in kb_dirs:
        if not kb_dir.is_dir():
            continue
        metadata_file = kb_dir / "chroma.sqlite3"
        if not metadata_file.exists():
            broken_kbs.append(kb_dir.name)

    if not broken_kbs:
        print("\n✅ 没有发现需要修复的知识库")
        return

    print(f"\n开始修复 {len(broken_kbs)} 个知识库...")

    for kb_id in broken_kbs:
        try:
            fix_broken_kb(kb_id)
        except Exception as e:
            print(f"❌ 修复失败 {kb_id}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("修复完成!")
    print("=" * 60)
    print("\n后续步骤:")
    print("1. 重启后端服务")
    print("2. 在系统中重新导入损坏知识库的文档")
    print("3. 系统将自动重建HNSW索引")


if __name__ == "__main__":
    main()
