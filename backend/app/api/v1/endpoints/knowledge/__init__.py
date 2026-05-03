"""知识库API端点包

FastAPI路由定义，将请求分发给各处理函数
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import ResponseModel
from app.schemas.knowledge import (
    KnowledgeBaseCreate, KnowledgeBaseResponse, KnowledgeBaseUploadResponse,
    KnowledgeBaseUpdate, DualTrackRetrieveRequest, DualTrackRetrieveResponse,
    KnowledgeGraphData
)

from ._upload import upload_knowledge_base_handler
from ._crud import (
    list_knowledge_bases_handler, get_knowledge_base_handler,
    delete_knowledge_base_handler, update_knowledge_base_handler
)
from ._search import search_knowledge_base_handler, dual_track_retrieve_handler
from ._graph import (
    get_global_knowledge_graph_handler, get_all_general_knowledge_bases_handler,
    get_knowledge_graph_handler, extract_entities_from_kb_handler
)
from ._processing import (
    get_processing_progress_handler, get_all_processing_progress_endpoint_handler,
    stop_knowledge_processing_handler
)

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.post("/upload", response_model=ResponseModel[KnowledgeBaseUploadResponse])
async def upload_knowledge_base(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    file: UploadFile = File(...),
    description: str = Form(None),
    category: str = Form("general"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """上传用户知识库（支持LLM知识图谱生成）"""
    data = await upload_knowledge_base_handler(
        background_tasks, name, file, description, category, current_user, db
    )
    return ResponseModel(data=data)


@router.get("", response_model=ResponseModel[list])
async def list_knowledge_bases(
    category: str = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """获取用户的知识库列表"""
    return await list_knowledge_bases_handler(category, current_user, db)


@router.get("/{kb_id}", response_model=ResponseModel[KnowledgeBaseResponse])
async def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """获取知识库详情"""
    return await get_knowledge_base_handler(kb_id, current_user, db)


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """删除知识库（保留记录，清除向量和文件）"""
    return await delete_knowledge_base_handler(kb_id, current_user, db)


@router.put("/{kb_id}", response_model=ResponseModel[KnowledgeBaseResponse])
async def update_knowledge_base(
    kb_id: int,
    update_data: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """更新知识库信息（名称、描述、业务模块分类）"""
    return await update_knowledge_base_handler(kb_id, update_data, current_user, db)


@router.post("/{kb_id}/search")
async def search_knowledge_base(
    kb_id: int,
    query: str,
    n_results: int = 5,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """搜索知识库"""
    return await search_knowledge_base_handler(kb_id, query, n_results, current_user, db)


@router.get("/graph/global")
async def get_global_knowledge_graph(
    max_nodes: int = 100,
    current_user: User = Depends(get_current_user)
):
    """获取全局知识图谱数据（用于可视化）"""
    return await get_global_knowledge_graph_handler(max_nodes, current_user)


@router.get("/{kb_id}/progress")
async def get_processing_progress(
    kb_id: int,
    current_user: User = Depends(get_current_user)
):
    """获取知识库处理进度"""
    return await get_processing_progress_handler(kb_id, current_user)


@router.get("/processing/all")
async def get_all_processing_progress_endpoint(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """获取所有正在处理的知识库进度"""
    return await get_all_processing_progress_endpoint_handler(current_user, db)


@router.post("/{kb_id}/stop")
async def stop_knowledge_processing(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """终止知识库处理进程"""
    return await stop_knowledge_processing_handler(kb_id, current_user, db)


@router.get("/general/all", response_model=ResponseModel[List[KnowledgeBaseResponse]])
async def get_all_general_knowledge_bases(
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有通用类型的知识库"""
    return await get_all_general_knowledge_bases_handler(current_user, db)


@router.post("/retrieve/dual-track", response_model=ResponseModel[DualTrackRetrieveResponse])
async def dual_track_retrieve(
    request: DualTrackRetrieveRequest,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """三层知识库检索策略"""
    return await dual_track_retrieve_handler(request, current_user, db)


@router.get("/{kb_id}/graph", response_model=ResponseModel[KnowledgeGraphData])
async def get_knowledge_graph(
    kb_id: int,
    max_nodes: int = 100,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取知识库的知识图谱数据（用于可视化）"""
    return await get_knowledge_graph_handler(kb_id, max_nodes, current_user, db)


@router.post("/{kb_id}/extract-entities", response_model=ResponseModel[Dict[str, Any]])
async def extract_entities_from_kb(
    kb_id: int,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """使用 LLM 从知识库文档中提取实体和关系"""
    return await extract_entities_from_kb_handler(kb_id, background_tasks, current_user, db)
