"""
全局知识图谱清理工具

用途: 清理已膨胀的全局图谱,移除误同步的单元实体,仅保留全局大纲实体

设计原则:
- 不限制全局图谱实体总数 (详细大纲可能包含大量实体)
- 仅清理单元级别的实体 (地点状态/章节事件/道具状态等)
- 保留全局大纲实体 (世界观/设定/大事件/主线/核心人物等)

使用方法:
    python -m backend.scripts.cleanup_global_graph --project-id 123 --dry-run
    python -m backend.scripts.cleanup_global_graph --project-id 123 --execute

作者: 全能创意大师团队
日期: 2026-04-28
版本: v3.2.0 - 增强单元实体检测和统计
"""
import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.tools.novel_graph_rag.impl.generator import NovelKnowledgeGraph
from app.services.novel_writer.project_knowledge_base.impl.project_knowledge_base import ProjectKnowledgeBase


def cleanup_global_graph(project_id: int, dry_run: bool = True):
    """
    清理全局图谱中的单元实体
    
    Args:
        project_id: 项目ID
        dry_run: True=仅预览, False=实际执行
    """
    print(f"🔍 开始清理项目 {project_id} 的全局知识图谱...")
    print(f"模式: {'预览' if dry_run else '执行'}\n")
    
    kb = ProjectKnowledgeBase(db=None)  # 不需要数据库连接
    global_graph_path = kb.get_graph_path(project_id, unit_number=None)
    
    if not os.path.exists(global_graph_path):
        print(f"❌ 全局图谱不存在: {global_graph_path}")
        return
    
    graph = NovelKnowledgeGraph(persist_path=global_graph_path)
    if not graph.load():
        print("❌ 加载全局图谱失败")
        return
    
    # 统计当前状态
    total_nodes = graph.graph.number_of_nodes()
    total_edges = graph.graph.number_of_edges()
    
    print(f" 清理前: {total_nodes}个实体, {total_edges}条关系")
    print(f"📁 图谱文件: {global_graph_path}\n")
    
    # 识别需要保留的实体类型 (全局大纲实体)
    macro_entity_types = {
        "世界观", "设定", "大事件", "主线剧情", 
        "核心设定", "背景", "规则", "人物设定",
        "人物", "主角", "配角", "反派", "组织"  # 新增：常见人物类型
    }
    
    #  [知识图谱优化 v3.2] 明确定义单元实体类型（必须移除）
    unit_entity_types = {
        "地点状态", "章节事件", "道具状态", "伏笔", "群体", "设施",
        "设施状态变化", "设施归属变更", "设施物理状态",
        "事件状态变化", "事件影响", "事件因果链", "详细事件",
        "群体组织", "群体状态变化", "群体成员变动", "群体关系变化",
        "道具物品", "道具状态变化", "道具归属变更", "道具功能使用",
        "伏笔回收", "世界规则", "规则引用", "规则例外", "世界观规则",
        "时间节点", "时间流逝",
        "身份变化", "位置变化", "关系变化",
        "性格发展", "心理状态", "能力成长", "行为模式"
    }
    
    entities_to_remove = []
    entities_to_keep = []
    unit_entities_by_type = {}  # 按类型统计单元实体
    
    for node_id, node_data in graph.graph.nodes(data=True):
        entity_type = node_data.get("type", "")
        doc_id = node_data.get("doc_id", "")
        
        # 优先级1: 明确禁止的单元实体类型
        if entity_type in unit_entity_types:
            entities_to_remove.append((node_id, entity_type, doc_id))
            unit_entities_by_type[entity_type] = unit_entities_by_type.get(entity_type, 0) + 1
        
        # 优先级2: 明确允许的宏观实体类型
        elif entity_type in macro_entity_types:
            entities_to_keep.append((node_id, entity_type))
        
        # 优先级3: 根据doc_id判断（chapter_前缀表示单元实体）
        elif doc_id.startswith("chapter_"):
            entities_to_remove.append((node_id, entity_type, doc_id))
            unit_entities_by_type[entity_type] = unit_entities_by_type.get(entity_type, 0) + 1
        
        # 优先级4: 未知来源，保守保留
        else:
            entities_to_keep.append((node_id, entity_type))
    
    print(f"📋 将保留: {len(entities_to_keep)}个实体")
    for node_id, entity_type in entities_to_keep[:15]:
        print(f"  ✅ {node_id} ({entity_type})")
    if len(entities_to_keep) > 15:
        print(f"  ... 还有 {len(entities_to_keep) - 15} 个实体")
    
    print(f"\n🗑️  将移除: {len(entities_to_remove)}个实体")
    print(f"📈 单元实体类型分布:")
    for entity_type, count in sorted(unit_entities_by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  ❌ {entity_type}: {count}个")
    
    print(f"\n前10个将被移除的实体:")
    for node_id, entity_type, doc_id in entities_to_remove[:10]:
        print(f"  ❌ {node_id} ({entity_type}, {doc_id})")
    if len(entities_to_remove) > 10:
        print(f"  ... 还有 {len(entities_to_remove) - 10} 个实体")
    
    if dry_run:
        print("\n🔍 [预览模式] 未实际执行清理")
        print("如需执行,请使用: --execute 参数")
        
        # 显示预期效果
        print(f"\n📈 预期效果:")
        print(f"  清理前: {total_nodes}个实体, {total_edges}条关系")
        print(f"  清理后: {len(entities_to_keep)}个实体, (关系将自动清理)")
        print(f"  减少: {total_nodes - len(entities_to_keep)}个实体 ({(total_nodes - len(entities_to_keep))/total_nodes*100:.1f}%)")
        
        # 提供建议
        if total_nodes > 200:
            print(f"\n⚠️  警告: 全局图谱实体数过多({total_nodes}个)，建议执行清理！")
            print(f"   正常全局大纲图谱应在50-150个实体之间")
        return
    
    # 执行清理
    print(f"\n⚙️  开始执行清理...")
    for node_id, entity_type, doc_id in entities_to_remove:
        try:
            # 移除节点及其关系
            graph.graph.remove_node(node_id)
        except Exception as e:
            print(f"  ️  移除节点失败 {node_id}: {e}")
    
    # 保存清理后的图谱
    save_success = graph.save()
    if not save_success:
        print("❌ 保存清理后的图谱失败")
        return
    
    print(f"\n✅ 清理完成:")
    print(f"   清理前: {total_nodes}个实体, {total_edges}条关系")
    print(f"   清理后: {graph.graph.number_of_nodes()}个实体, {graph.graph.number_of_edges()}条关系")
    print(f"   减少: {total_nodes - graph.graph.number_of_nodes()}个实体 ({(total_nodes - graph.graph.number_of_nodes())/total_nodes*100:.1f}%)")
    print(f"   保存成功: {global_graph_path}")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="全局知识图谱清理工具 - 移除单元实体,仅保留全局大纲实体"
    )
    parser.add_argument(
        "--project-id", 
        type=int, 
        required=True,
        help="项目ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="预览模式 (默认)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行清理"
    )
    
    args = parser.parse_args()
    
    if args.execute:
        cleanup_global_graph(args.project_id, dry_run=False)
    else:
        cleanup_global_graph(args.project_id, dry_run=True)


if __name__ == "__main__":
    main()
