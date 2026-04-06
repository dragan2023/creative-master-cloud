"""
小说/剧本正文生成 API 端点 - 风格文档管理模块

包含风格文档上传、分析、获取、删除等功能

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
import traceback
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import (
    ResourceNotFoundException, ValidationException, GenerationException,
    AppException, ErrorCode
)

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject
from app.schemas.common import ResponseModel

from .utils import router, settings, logger, get_project_data_dir


# ==================== 风格文档 API ====================

@router.post("/projects/{project_id}/style-document", response_model=ResponseModel)
async def upload_style_document(
    project_id: int,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传风格文档
    
    支持格式：.txt, .docx, .pdf
    上传后自动触发风格分析
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if not file.filename:
            raise ValidationException("文件名不能为空")

        allowed_extensions = ['.txt', '.docx', '.pdf', '.md']
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            raise ValidationException(
                f"不支持的文件格式，仅支持: {', '.join(allowed_extensions)}"
            )

        project_dir = get_project_data_dir(project.project_code)
        style_dir = os.path.join(project_dir, "style")
        os.makedirs(style_dir, exist_ok=True)

        style_filename = f"style_document{file_ext}"
        style_path = os.path.join(style_dir, style_filename)

        content = await file.read()
        with open(style_path, 'wb') as f:
            f.write(content)

        if file_ext == '.txt' or file_ext == '.md':
            style_content = content.decode('utf-8', errors='ignore')
        elif file_ext == '.docx':
            try:
                import docx
                doc = docx.Document(style_path)
                style_content = '\n'.join([para.text for para in doc.paragraphs])
            except ImportError:
                raise GenerationException("服务器未安装python-docx库，无法解析docx文件")
        elif file_ext == '.pdf':
            try:
                import fitz
                doc = fitz.open(style_path)
                style_content = ''
                for page in doc:
                    style_content += page.get_text()
                doc.close()
            except ImportError:
                raise GenerationException("服务器未安装pymupdf库，无法解析pdf文件")
        else:
            style_content = content.decode('utf-8', errors='ignore')

        if len(style_content.strip()) < 100:
            raise ValidationException("风格文档内容过短，至少需要100个字符")

        if len(style_content) > 100000:
            style_content = style_content[:100000]

        project.style_document_path = style_path
        project.style_document_name = file.filename
        project.style_analysis_status = "pending"
        await db.commit()

        if background_tasks:
            background_tasks.add_task(
                analyze_style_document_task,
                project_id,
                style_content
            )

        logger.info(f"风格文档上传成功: project_id={project_id}, file={file.filename}")

        return ResponseModel(
            success=True,
            data={
                "project_id": project_id,
                "style_document_name": file.filename,
                "style_document_uploaded": True,
                "style_analysis_status": "pending",
                "message": "风格文档上传成功，正在分析中..."
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"上传风格文档失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


async def analyze_style_document_task(project_id: int, style_content: str):
    """后台任务：分析风格文档"""
    from sqlalchemy.orm.attributes import flag_modified
    from app.core.database import async_session_maker
    from app.models.writing_model_config import WritingModelConfig
    from app.core.security import api_key_encryption
    
    try:
        async with async_session_maker() as db:
            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()
            
            if not project:
                logger.error(f"项目不存在: project_id={project_id}")
                return
            
            project.style_analysis_status = "analyzing"
            await db.commit()
            
            user_id = project.user_id
        
        from app.agents.writing.style_editor_agent import StyleEditorAgent
        from app.agents.writing.base_agent import AgentContext, AgentRole
        from app.agents.writing.agent_config import AgentConfig, AgentModelConfig
        
        agent_config = AgentConfig()
        
        async with async_session_maker() as db:
            model_query = select(WritingModelConfig).where(
                WritingModelConfig.user_id == user_id,
                WritingModelConfig.is_active == True
            ).order_by(WritingModelConfig.is_valid.desc(), WritingModelConfig.updated_at.desc())
            model_result = await db.execute(model_query)
            model_configs = model_result.scalars().all()
            
            if model_configs:
                model_config = model_configs[0]
                try:
                    decrypted_key = api_key_encryption.decrypt(model_config.encrypted_key)
                except Exception as e:
                    logger.error(f"解密API密钥失败: {e}")
                    decrypted_key = None
                
                agent_model_config = AgentModelConfig(
                    model_id=model_config.model_id,
                    provider=model_config.provider,
                    temperature=0.6,
                    max_tokens=8192,
                    api_base=model_config.api_base,
                    api_key=decrypted_key,
                    config_id=model_config.id
                )
                agent_config.update_config(AgentRole.STYLE_EDITOR, agent_model_config)
                logger.info(f"风格文档分析 - 使用预配置模型: {model_config.name} (provider={model_config.provider}, model={model_config.model_id})")
            else:
                logger.warning(f"风格文档分析 - 用户 {user_id} 没有预配置模型，尝试使用全局配置")
                from app.agents.writing.agent_config import get_default_agent_config
                global_config = get_default_agent_config()
                if global_config.get_config(AgentRole.STYLE_EDITOR):
                    agent_config = global_config
                else:
                    logger.error(f"风格文档分析 - 用户 {user_id} 没有配置任何可用模型")
                    async with async_session_maker() as db:
                        query = select(NovelProject).where(NovelProject.id == project_id)
                        result = await db.execute(query)
                        project = result.scalar_one_or_none()
                        if project:
                            project.style_analysis_status = "failed"
                            project.style_analysis_error = "请先在写作工作台中配置模型"
                            await db.commit()
                    return
        
        agent = StyleEditorAgent(config=agent_config)
        context = AgentContext(
            task_id=f"style_analysis_{project_id}",
            unit_index=0,
            scene_index=0
        )
        
        style_result = await agent.analyze_style_document(style_content, context)
        
        async with async_session_maker() as db:
            query = select(NovelProject).where(NovelProject.id == project_id)
            result = await db.execute(query)
            project = result.scalar_one_or_none()
            
            if not project:
                logger.error(f"项目不存在: project_id={project_id}")
                return
            
            if style_result:
                project.style_config = style_result
                project.style_analysis_status = "completed"
                project.style_analysis_error = None
                flag_modified(project, 'style_config')
                logger.info(f"风格文档分析完成: project_id={project_id}")
            else:
                project.style_analysis_status = "failed"
                project.style_analysis_error = "风格分析返回空结果"
                logger.error(f"风格文档分析失败: project_id={project_id}, 返回空结果")
            
            await db.commit()
            
    except Exception as e:
        logger.error(f"风格文档分析任务失败: {str(e)}\n{traceback.format_exc()}")
        
        try:
            async with async_session_maker() as db:
                query = select(NovelProject).where(NovelProject.id == project_id)
                result = await db.execute(query)
                project = result.scalar_one_or_none()
                
                if project:
                    project.style_analysis_status = "failed"
                    project.style_analysis_error = str(e)
                    await db.commit()
        except Exception as db_error:
            logger.error(f"更新风格分析状态失败: {str(db_error)}")


@router.get("/projects/{project_id}/style-document", response_model=ResponseModel)
async def get_style_document(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取风格文档信息
    
    返回风格文档状态、风格特征分析结果等
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        style_config = project.style_config or {}
        style_profile = style_config.get("style_profile")
        
        # 调试日志：记录原始数据
        logger.info(f"获取风格文档 - style_config keys: {list(style_config.keys()) if style_config else 'empty'}")
        logger.info(f"获取风格文档 - style_profile type: {type(style_profile).__name__ if style_profile else 'None'}")
        
        from app.schemas.novel_writer import StyleProfile
        if style_profile and isinstance(style_profile, dict):
            try:
                # 使用 model_validate 确保嵌套模型也被正确转换
                validated_profile = StyleProfile.model_validate(style_profile)
                # 将 Pydantic 模型转换为字典，确保序列化正确
                style_profile = validated_profile.model_dump(mode='json', exclude_none=True)
                logger.info(f"风格画像转换成功 - name: {validated_profile.name}")
            except Exception as e:
                logger.warning(f"风格画像解析失败，尝试直接构造: {e}")
                style_profile = style_profile  # 保持原始字典格式

        from app.schemas.novel_writer import StyleDocumentResponse
        response_data = StyleDocumentResponse(
            project_id=project_id,
            style_document_uploaded=bool(project.style_document_path),
            style_document_name=project.style_document_name,
            style_profile=style_profile,
            style_guide_for_writing=style_config.get("style_guide_for_writing"),
            key_imitation_points=style_config.get("key_imitation_points"),
            example_transformations=style_config.get("example_transformations"),
            avoid_patterns=style_config.get("avoid_patterns"),
            ai_elimination_enabled=project.ai_elimination_enabled if project.ai_elimination_enabled is not None else True,
            ai_elimination_threshold=project.ai_elimination_threshold or 50,
            created_at=project.created_at,
            updated_at=project.updated_at
        )

        return ResponseModel(
            success=True,
            data=response_data
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取风格文档失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/style-document")
async def delete_style_document(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除风格文档
    
    删除上传的风格文档及其分析结果
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if project.style_document_path and os.path.exists(project.style_document_path):
            os.remove(project.style_document_path)

        project.style_document_path = None
        project.style_document_name = None
        project.style_config = None
        project.style_analysis_status = "pending"
        project.style_analysis_error = None

        await db.commit()

        logger.info(f"风格文档删除成功: project_id={project_id}")

        return ResponseModel(
            success=True,
            message="风格文档已删除"
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除风格文档失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.put("/projects/{project_id}/style-document", response_model=ResponseModel)
async def update_style_document_settings(
    project_id: int,
    request: "StyleDocumentUpdate",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新风格文档设置
    
    更新AI文风消除开关和阈值
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        if request.ai_elimination_enabled is not None:
            project.ai_elimination_enabled = request.ai_elimination_enabled
        
        if request.ai_elimination_threshold is not None:
            project.ai_elimination_threshold = request.ai_elimination_threshold

        await db.commit()
        await db.refresh(project)

        logger.info(f"风格文档设置更新成功: project_id={project_id}")

        return ResponseModel(
            success=True,
            data={
                "project_id": project_id,
                "ai_elimination_enabled": project.ai_elimination_enabled,
                "ai_elimination_threshold": project.ai_elimination_threshold
            }
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新风格文档设置失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/projects/{project_id}/style-guide", response_model=ResponseModel)
async def get_real_time_style_guide(
    project_id: int,
    scene_title: str = Form(...),
    target_words: int = Form(default=3000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取实时风格指导
    
    为写手Agent提供写作过程中的实时风格指导
    """
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        content_type = project.content_type or "novel"
        style_config = project.style_config or {}
        style_document_features = style_config.get("style_guide_for_writing", "")
        
        project_style_params = {}
        if project.novel_config:
            project_style_params = project.novel_config
        elif project.series_script_config:
            project_style_params = project.series_script_config
        elif project.movie_script_config:
            project_style_params = project.movie_script_config

        if not style_document_features:
            from app.schemas.novel_writer import RealTimeStyleGuide
            return ResponseModel(
                success=True,
                data=RealTimeStyleGuide(
                    style_instructions={
                        "language": {"word_preference": "根据项目风格参数", "sentence_structure": "自然流畅", "punctuation": "标准使用"},
                        "narrative": {"perspective_reminder": project_style_params.get("narrative_perspective", "第三人称"), "pacing_guidance": "根据情节调整", "detail_handling": "详略得当"},
                        "description": {"sensory_guidance": "调动五感", "detail_level": "适中", "rhetorical_suggestions": ["适当使用比喻", "注意细节描写"]},
                        "dialogue": {"style_guidance": "自然对话", "character_voice_tips": ["保持角色个性"]},
                        "ai_avoidance": {"patterns_to_avoid": ["避免机械化过渡", "避免空洞形容词"], "humanization_tips": ["增加具体细节", "情感层次化"]}
                    },
                    key_reminders=["保持风格一致性", "注意情节连贯", "人物行为合理"],
                    style_examples={
                        "recommended": "具体、生动、有画面感的表达",
                        "avoid": "抽象、空洞、程式化的表达"
                    }
                )
            )

        from app.agents.writing.style_editor_agent import StyleEditorAgent
        from app.agents.writing.base_agent import AgentContext, AgentRole
        from app.agents.writing.agent_config import AgentConfig, AgentModelConfig
        from app.models.writing_model_config import WritingModelConfig
        from app.core.security import api_key_encryption
        
        agent_config = AgentConfig()
        
        model_query = select(WritingModelConfig).where(
            WritingModelConfig.user_id == current_user.id,
            WritingModelConfig.is_active == True
        ).order_by(WritingModelConfig.is_valid.desc(), WritingModelConfig.updated_at.desc())
        model_result = await db.execute(model_query)
        model_configs = model_result.scalars().all()
        
        if model_configs:
            model_config = model_configs[0]
            try:
                decrypted_key = api_key_encryption.decrypt(model_config.encrypted_key)
            except Exception as e:
                logger.error(f"解密API密钥失败: {e}")
                decrypted_key = None
            
            agent_model_config = AgentModelConfig(
                model_id=model_config.model_id,
                provider=model_config.provider,
                temperature=0.6,
                max_tokens=8192,
                api_base=model_config.api_base,
                api_key=decrypted_key,
                config_id=model_config.id
            )
            agent_config.update_config(AgentRole.STYLE_EDITOR, agent_model_config)
        else:
            from app.agents.writing.agent_config import get_default_agent_config
            global_config = get_default_agent_config()
            if global_config.get_config(AgentRole.STYLE_EDITOR):
                agent_config = global_config
            else:
                raise ValidationException("请先在写作工作台中配置模型")
        
        agent = StyleEditorAgent(config=agent_config)
        context = AgentContext(
            task_id=f"style_guide_{project_id}",
            scene_index=0
        )
        
        style_guide = await agent.get_real_time_style_guide(
            content_type=content_type,
            scene_title=scene_title,
            target_words=target_words,
            project_style_params=project_style_params,
            style_document_features=style_document_features,
            context=context
        )

        if style_guide:
            from app.schemas.novel_writer import RealTimeStyleGuide
            return ResponseModel(
                success=True,
                data=RealTimeStyleGuide(**style_guide)
            )
        else:
            raise GenerationException("获取风格指导失败")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取实时风格指导失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))
