"""
小说/剧本生成模块 - 大纲管理 API 端点

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
import re
import json
import tempfile
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import Depends, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import (
    ResourceNotFoundException, ValidationException, AppException, ErrorCode
)

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, NovelProject, ProjectType
from app.schemas.common import ResponseModel
from app.schemas.novel_writer import (
    OutlineUploadResponse,
    ChapterOutlineBase, ChapterOutlineCreate, ChapterOutlineUpdate, ChapterOutlineResponse,
    ChapterOutlineListResponse, ChapterOutlineGenerateRequest,
    SceneOutlineBase, SceneOutlineCreate, SceneOutlineUpdate, SceneOutlineResponse,
    SceneOutlineListResponse, SceneOutlineGenerateRequest
)

from .utils import router, logger, get_project_data_dir


# ==================== 单元概述质控请求/响应模型 ====================

class UnitSummariesQualityControlRequest(BaseModel):
    """单元概述质控请求"""
    enable_auto_revision: bool = Field(
        default=True,
        description="是否启用自动修正严重问题"
    )


class UnitSummariesQualityControlResponse(BaseModel):
    """单元概述质控响应"""
    success: bool
    quality_report: Dict[str, Any]
    revision_summary: List[Dict[str, Any]]
    revised_count: int
    message: str


# ==================== 单元概述上传请求模型 ====================

class UnitSummariesUploadRequest(BaseModel):
    """单元概述上传请求"""
    unit_summaries: Dict[str, Any]  # 单元概述字典
    global_outline: Optional[str] = None  # 可选的全局大纲


class UnitSummariesUploadResponse(BaseModel):
    """单元概述上传响应"""
    project_id: int
    unit_count: int
    message: str


class OutlineInterventionRequest(BaseModel):
    """详细大纲生成干预请求"""
    content_type: str = Field(
        default="novel", description="内容类型: novel/series_script/movie_script")
    user_choice: Optional[str] = Field(
        default=None, description="用户选择: accept/provide/reference/skip")
    user_guidance: Optional[str] = Field(default=None, description="用户提供的概要内容")
    force_regenerate: bool = Field(
        default=False, description="是否强制重新生成（即使已存在详细大纲）")


# ==================== 大纲上传 API ====================

@router.post("/projects/{project_id}/upload-outline", response_model=ResponseModel[OutlineUploadResponse])
async def upload_outline(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传大纲文件

    根据项目类型自动识别：
    - 小说：识别章节数
    - 剧集剧本：识别分集数
    - 电影剧本：识别场景数

    上传后自动触发知识库构建（如果启用GraphRAG）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取文件扩展名
        file_ext = os.path.splitext(file.filename)[1].lower()
        logger.info(f"[大纲上传] 文件名: {file.filename}, 扩展名: {file_ext}")

        # 根据文件类型选择解析方式
        outline_content = None

        if file_ext in ['.txt', '.md']:
            # 文本文件直接读取
            content = await file.read()
            try:
                outline_content = content.decode('utf-8')
            except UnicodeDecodeError:
                outline_content = content.decode('gbk', errors='ignore')
            logger.info(f"[大纲上传] 文本文件直接解码成功，长度: {len(outline_content)}字")

        elif file_ext in ['.docx', '.doc']:
            # Word文件需要使用file_parser正确解析
            from app.tools.file_parser import get_file_parser

            # 保存临时文件
            temp_file = os.path.join(
                tempfile.gettempdir(), f"outline_{project_id}_{file.filename}")
            content = await file.read()
            with open(temp_file, 'wb') as f:
                f.write(content)

            # 使用file_parser解析
            file_parser = get_file_parser()
            parse_result = await file_parser.parse(temp_file)

            # 清理临时文件
            try:
                os.remove(temp_file)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")
                pass

            if "error" in parse_result:
                raise ValidationException(f"文件解析失败: {parse_result['error']}")

            outline_content = parse_result.get("content", "")
            char_count = parse_result.get("metadata", {}).get(
                "char_count", len(outline_content))
            logger.info(f"[大纲上传] Word文件解析成功，实际字符数: {char_count}")

        else:
            raise ValidationException(f"不支持的文件格式: {file_ext}")

        if not outline_content or not outline_content.strip():
            raise ValidationException("大纲内容为空")

        # 计算实际字数（去除空白字符后的字符数）
        actual_char_count = len(outline_content.strip())
        logger.info(f"[大纲上传] 大纲实际字数: {actual_char_count}字")

        # 保存大纲到文件
        project_dir = get_project_data_dir(project.project_code)
        outline_file = os.path.join(
            project_dir, f"{project.project_code}_outline.txt")

        with open(outline_file, 'w', encoding='utf-8') as f:
            f.write(outline_content)
        logger.info(f"[大纲上传] 文件已保存: {outline_file}")

        # 更新项目的大纲字段
        project.outline_file_path = outline_file
        project.outline_content = outline_content
        logger.info(
            f"[大纲上传] 项目字段已更新: outline_content长度={len(outline_content)}")

        # 获取项目的content_type
        content_type = getattr(project, 'content_type', None)
        if not content_type:
            # 兼容旧版：根据project_type推断
            if project.project_type == ProjectType.NOVEL:
                content_type = "novel"
            else:
                content_type = "series_script"

        # 根据内容类型提取单元数
        extracted_count = extract_chapter_count(outline_content, content_type)

        # 提交数据库更改
        await db.commit()
        logger.info(f"[大纲上传] 数据库已提交, 提取{content_type}单元数: {extracted_count}")

        # 获取单元标签
        unit_labels = {
            "novel": "章节",
            "series_script": "分集",
            "movie_script": "场景"
        }
        unit_label = unit_labels.get(content_type, "章节")

        logger.info(
            f"大纲上传成功: {project.title}, 提取{unit_label}数: {extracted_count}")

        return ResponseModel(
            success=True,
            data=OutlineUploadResponse(
                project_id=project.id,
                outline_content=outline_content[:1000] + "..." if len(
                    outline_content) > 1000 else outline_content,
                extracted_chapters=extracted_count,
                message=f"大纲上传成功，共{actual_char_count}字，识别到{extracted_count}个{unit_label}"
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"上传大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 单元概述上传 API ====================

@router.post("/projects/{project_id}/upload-unit-summaries", response_model=ResponseModel[UnitSummariesUploadResponse])
async def upload_unit_summaries(
    project_id: int,
    request: UnitSummariesUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传单元概述

    用于正文生成板块，支持用户手动上传单元概述数据。
    单元概述用于指导单元详细大纲的生成。

    Args:
        project_id: 项目ID
        request: 包含 unit_summaries 字典和可选的 global_outline

    Returns:
        上传结果
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 验证单元概述格式
        unit_summaries = request.unit_summaries
        if not unit_summaries or not isinstance(unit_summaries, dict):
            raise ValidationException("单元概述格式无效")

        # 验证每个单元的结构
        for key, unit in unit_summaries.items():
            if not isinstance(unit, dict):
                raise ValidationException(f"单元 {key} 格式无效")
            # 确保有必要的字段
            if 'summary' not in unit:
                raise ValidationException(f"单元 {key} 缺少 summary 字段")

        # 更新项目的单元概述字段
        project.unit_summaries = unit_summaries
        flag_modified(project, 'unit_summaries')
        project.unit_summaries_status = 'completed'
        project.unit_summaries_created_at = datetime.now().isoformat()

        # 如果提供了全局大纲，也一并更新
        if request.global_outline:
            project.global_outline_content = request.global_outline
            project.global_outline_status = 'completed'
            project.global_outline_created_at = datetime.now().isoformat()

        # 更新项目的总单元数
        project.total_chapters = len(unit_summaries)

        await db.commit()

        logger.info(
            f"单元概述上传成功: project_id={project_id}, unit_count={len(unit_summaries)}")

        return ResponseModel(
            success=True,
            data=UnitSummariesUploadResponse(
                project_id=project.id,
                unit_count=len(unit_summaries),
                message=f"单元概述上传成功，共 {len(unit_summaries)} 个单元"
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"上传单元概述失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/projects/{project_id}/upload-unit-summaries-file", response_model=ResponseModel[UnitSummariesUploadResponse])
async def upload_unit_summaries_file(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传单元概述文件

    支持与全局大纲相同的文件格式：.txt, .md, .docx, .doc
    自动解析文件内容并提取单元概述结构

    文件格式要求：
    - 小说：包含章节标题（如 ### 第1章：xxx）和梗概内容
    - 剧集剧本：包含分集标题（如 ### 第1集：xxx）和梗概内容
    - 电影剧本：包含场景标题（如 **第1场：xxx）和梗概内容
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取文件扩展名
        file_ext = os.path.splitext(file.filename)[1].lower()
        logger.info(f"[单元概述上传] 文件名: {file.filename}, 扩展名: {file_ext}")

        # 根据文件类型选择解析方式（复用大纲上传的逻辑）
        file_content = None

        if file_ext in ['.txt', '.md']:
            # 文本文件直接读取
            content = await file.read()
            try:
                file_content = content.decode('utf-8')
            except UnicodeDecodeError:
                file_content = content.decode('gbk', errors='ignore')
            logger.info(f"[单元概述上传] 文本文件直接解码成功，长度: {len(file_content)}字")

        elif file_ext in ['.docx', '.doc']:
            # Word文件需要使用file_parser正确解析
            from app.tools.file_parser import get_file_parser

            # 保存临时文件
            temp_file = os.path.join(
                tempfile.gettempdir(), f"unit_summaries_{project_id}_{file.filename}")
            content = await file.read()
            with open(temp_file, 'wb') as f:
                f.write(content)

            # 使用file_parser解析
            file_parser = get_file_parser()
            parse_result = await file_parser.parse(temp_file)

            # 清理临时文件
            try:
                os.remove(temp_file)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")
                pass

            if "error" in parse_result:
                raise ValidationException(f"文件解析失败: {parse_result['error']}")

            file_content = parse_result.get("content", "")
            logger.info(f"[单元概述上传] Word文件解析成功，长度: {len(file_content)}字")

        else:
            raise ValidationException(
                f"不支持的文件格式: {file_ext}，支持 .txt, .md, .docx, .doc")

        if not file_content or not file_content.strip():
            raise ValidationException("文件内容为空")

        # 获取项目的content_type
        content_type = getattr(project, 'content_type', None)
        if not content_type:
            # 兼容旧版：根据project_type推断
            if project.project_type == ProjectType.NOVEL:
                content_type = "novel"
            else:
                content_type = "series_script"

        # 解析单元概述内容
        unit_summaries = parse_unit_summaries_from_content(
            file_content, content_type)

        if not unit_summaries:
            raise ValidationException(
                "无法从文件中解析出单元概述，请检查文件格式是否正确"
            )

        # 更新项目的单元概述字段
        project.unit_summaries = unit_summaries
        flag_modified(project, 'unit_summaries')
        project.unit_summaries_status = 'completed'
        project.unit_summaries_created_at = datetime.now().isoformat()
        project.total_chapters = len(unit_summaries)

        await db.commit()

        logger.info(
            f"单元概述文件上传成功: project_id={project_id}, unit_count={len(unit_summaries)}")

        return ResponseModel(
            success=True,
            data=UnitSummariesUploadResponse(
                project_id=project.id,
                unit_count=len(unit_summaries),
                message=f"单元概述上传成功，共解析出 {len(unit_summaries)} 个单元"
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"上传单元概述文件失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 大纲解析辅助函数 ====================

def parse_unit_summaries_from_content(content: str, content_type: str) -> Dict[str, Any]:
    """
    从文件内容中解析单元概述

    支持多种格式变体：
    - 小说：### 第X章：标题 或 第X章：标题 或 第X章 标题
    - 剧集：### 第X集：标题 或 第X集：标题 或 第X集 标题
    - 电影：**第X场：标题** 或 第X场：标题 或 第X场 标题

    梗概格式：
    - **本章梗概**：内容 或 本章梗概：内容 或 梗概：内容
    - **本集梗概**：内容 或 本集梗概：内容
    - **本场梗概**：内容 或 本场梗概：内容

    Args:
        content: 文件内容
        content_type: 内容类型（novel/series_script/movie_script）

    Returns:
        单元概述字典 {"1": {"unit_number": 1, "title": "...", "summary": "..."}, ...}
    """
    result = {}

    # 记录解析过程
    logger.info(
        f"[单元概述解析] 开始解析, content_type={content_type}, 内容长度={len(content)}")

    if content_type == "movie_script":
        # 电影剧本：匹配多种格式的场景标题
        patterns = [
            r'\*\*第(\d+)场[：:\s]*(.+?)\*\*',  # **第X场：标题**
            r'第(\d+)场[：:\s]+(.+?)(?:\n|$)',   # 第X场：标题 或 第X场 标题
        ]

        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            all_matches.extend(matches)

        # 去重（保留第一次出现的）
        seen = set()
        for match in all_matches:
            unit_num = int(match[0])
            if unit_num not in seen:
                seen.add(unit_num)
                title = match[1].strip()
                # 清理标题中可能的多余字符
                title = re.sub(r'[\*\s]+$', '', title)

                # 提取本场梗概（支持多种格式）
                summary = ""
                summary_patterns = [
                    rf'第{unit_num}场.*?\*\*本场梗概\*\*[：:]\s*(.+?)(?=\*\*第\d+场|第\d+场|$)',
                    rf'第{unit_num}场.*?本场梗概[：:]\s*(.+?)(?=第\d+场|$)',
                    rf'第{unit_num}场.*?梗概[：:]\s*(.+?)(?=第\d+场|$)',
                ]

                for sp in summary_patterns:
                    sm = re.search(sp, content, re.DOTALL)
                    if sm:
                        summary = sm.group(1).strip()
                        break

                result[str(unit_num)] = {
                    "unit_number": unit_num,
                    "title": title,
                    "summary": summary,
                    "status": "completed"
                }

        logger.info(f"[单元概述解析] 电影剧本解析完成, 匹配到 {len(result)} 个场景")

    else:
        # 小说/剧集：匹配多种格式的章节/分集标题
        if content_type == "novel":
            unit_char = "章"
            summary_keyword = "本章"
        else:  # series_script
            unit_char = "集"
            summary_keyword = "本集"

        # 多种标题格式
        patterns = [
            rf'###\s*第(\d+){unit_char}[：:\s]*(.+?)(?:\n|$)',  # ### 第X章：标题
            rf'##\s*第(\d+){unit_char}[：:\s]*(.+?)(?:\n|$)',   # ## 第X章：标题
            rf'第(\d+){unit_char}[：:\s]+(.+?)(?:\n|$)',        # 第X章：标题
            rf'第(\d+){unit_char}\s+(.+?)(?:\n|$)',             # 第X章 标题
        ]

        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            all_matches.extend(matches)

        # 去重
        seen = set()
        for match in all_matches:
            unit_num = int(match[0])
            if unit_num not in seen:
                seen.add(unit_num)
                title = match[1].strip()
                # 清理标题
                title = re.sub(r'^[：:\s]+', '', title)
                title = re.sub(r'[\*\s]+$', '', title)

                # 提取梗概（支持多种格式）
                summary = ""
                summary_patterns = [
                    rf'第{unit_num}{unit_char}.*?\*\*{summary_keyword}梗概\*\*[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|$)',
                    rf'第{unit_num}{unit_char}.*?{summary_keyword}梗概[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|$)',
                    rf'第{unit_num}{unit_char}.*?梗概[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|$)',
                    rf'\*\*{summary_keyword}梗概\*\*[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|$)',
                ]

                for sp in summary_patterns:
                    sm = re.search(sp, content, re.DOTALL)
                    if sm:
                        summary = sm.group(1).strip()
                        break

                result[str(unit_num)] = {
                    "unit_number": unit_num,
                    "title": title,
                    "summary": summary,
                    "status": "completed"
                }

        logger.info(
            f"[单元概述解析] {'小说' if content_type == 'novel' else '剧集'}解析完成, 匹配到 {len(result)} 个单元")

    if not result:
        logger.warning(f"[单元概述解析] 未能解析出任何单元，content_type={content_type}")
        logger.debug(f"[单元概述解析] 内容预览: {content[:200]}...")

    return result


def extract_chapter_count(content: str, content_type: str = "novel") -> int:
    """从大纲内容中提取章节数/集数/场景数

    使用统一的 ChapterRecognizer 进行识别，确保与校对功能一致

    根据内容类型使用不同的识别规则：
    - novel: 识别章节（第X章、Chapter X等）
    - series_script: 识别分集（第X集、Episode X等）
    - movie_script: 识别场景（第X场、Scene X等）

    Args:
        content: 大纲内容
        content_type: 内容类型（novel/series_script/movie_script）

    Returns:
        识别到的章节数/集数/场景数
    """
    from app.services.proofread.chapter_recognizer import count_chapters

    return count_chapters(content, content_type)


def extract_outline_units(content: str, content_type: str = "novel") -> List[Dict[str, Any]]:
    """从大纲内容中提取结构化单元（章节/分集/场景）

    使用统一的 ChapterRecognizer 进行识别，确保与校对功能一致

    返回每个单元的序号和标题，供前端确认和调整

    Args:
        content: 大纲内容
        content_type: 内容类型

    Returns:
        单元列表，每个单元包含 number, title, content
    """
    from app.services.proofread.chapter_recognizer import recognize_chapters

    matches = recognize_chapters(content, content_type)

    # 确定单元类型名称
    unit_type_map = {
        "novel": "章",
        "series_script": "集",
        "movie_script": "场"
    }
    unit_type = unit_type_map.get(content_type, "章")

    units = []
    for match in matches:
        units.append({
            "number": match["number"],
            "title": match["title"] or f"第{match['number']}{unit_type}",
            "line": match.get("original_line", ""),
            "confidence": match.get("confidence", 1.0)
        })

    return units


# ==================== 章节详细大纲 API（小说专用） ====================

@router.get("/projects/{project_id}/chapter-outlines", response_model=ResponseModel[ChapterOutlineListResponse])
async def get_chapter_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取所有章节详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取章节大纲
        chapter_outlines = project.chapter_outlines or {}

        # 获取总章节数
        total_chapters = project.total_chapters or 0

        # 如果没有配置总章节数，尝试从大纲中提取
        if total_chapters == 0 and project.outline_content:
            total_chapters = extract_chapter_count(
                project.outline_content, "novel")

        # 构建响应列表
        chapters = []
        generated_count = 0

        for ch_num in range(1, total_chapters + 1):
            ch_outline = chapter_outlines.get(str(ch_num), {})
            if ch_outline:
                generated_count += 1
                chapters.append(ChapterOutlineResponse(
                    chapter_number=ch_outline.get("chapter_number", ch_num),
                    chapter_title=ch_outline.get("chapter_title"),
                    chapter_summary=ch_outline.get("chapter_summary"),
                    detailed_outline=ch_outline.get("detailed_outline", ""),
                    key_events=ch_outline.get("key_events"),
                    character_arcs=ch_outline.get("character_arcs"),
                    suspense_points=ch_outline.get("suspense_points"),
                    emotional_tone=ch_outline.get("emotional_tone"),
                    status=ch_outline.get("status", "generated"),
                    content_status=ch_outline.get("content_status"),
                    content_word_count=ch_outline.get("content_word_count"),
                    created_at=ch_outline.get("created_at"),
                    updated_at=ch_outline.get("updated_at")
                ))
            else:
                chapters.append(ChapterOutlineResponse(
                    chapter_number=ch_num,
                    chapter_title=f"第{ch_num}章",
                    chapter_summary=None,
                    detailed_outline="",
                    status="pending"
                ))

        return ResponseModel(
            success=True,
            data=ChapterOutlineListResponse(
                project_id=project.id,
                total_chapters=total_chapters,
                generated_count=generated_count,
                chapters=chapters
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取章节大纲列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.get("/projects/{project_id}/chapter-outlines/{chapter_num}", response_model=ResponseModel[ChapterOutlineResponse])
async def get_chapter_outline(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个章节详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取章节大纲
        chapter_outlines = project.chapter_outlines or {}
        ch_outline = chapter_outlines.get(str(chapter_num))

        if not ch_outline:
            raise ResourceNotFoundException(f"第{chapter_num}章的详细大纲尚未生成")

        return ResponseModel(
            success=True,
            data=ChapterOutlineResponse(
                chapter_number=ch_outline.get("chapter_number", chapter_num),
                chapter_title=ch_outline.get("chapter_title"),
                chapter_summary=ch_outline.get("chapter_summary"),
                detailed_outline=ch_outline.get("detailed_outline", ""),
                key_events=ch_outline.get("key_events"),
                character_arcs=ch_outline.get("character_arcs"),
                suspense_points=ch_outline.get("suspense_points"),
                emotional_tone=ch_outline.get("emotional_tone"),
                status=ch_outline.get("status", "generated"),
                created_at=ch_outline.get("created_at"),
                updated_at=ch_outline.get("updated_at"),
                original_content=ch_outline.get("original_content"),
                revision_info=ch_outline.get("revision_info")
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取章节大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.put("/projects/{project_id}/chapter-outlines/{chapter_num}")
async def update_chapter_outline(
    project_id: int,
    chapter_num: int,
    request: ChapterOutlineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新章节详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取现有大纲
        chapter_outlines = project.chapter_outlines or {}
        ch_outline = chapter_outlines.get(str(chapter_num), {})

        if not ch_outline:
            ch_outline = {
                "chapter_number": chapter_num,
                "chapter_title": f"第{chapter_num}章",
                "chapter_summary": "",
                "detailed_outline": "",
                "status": "pending"
            }

        # 更新字段
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                ch_outline[key] = value

        # 更新状态和时间
        ch_outline["status"] = "edited"
        ch_outline["updated_at"] = datetime.now().isoformat()

        # 保存
        if not project.chapter_outlines:
            project.chapter_outlines = {}

        updated_outlines = dict(project.chapter_outlines)
        updated_outlines[str(chapter_num)] = ch_outline
        project.chapter_outlines = updated_outlines

        flag_modified(project, 'chapter_outlines')

        await db.commit()
        await db.refresh(project)

        logger.info(f"第{chapter_num}章详细大纲已更新: {project.title}")

        return ResponseModel(
            success=True,
            data=ChapterOutlineResponse(
                chapter_number=ch_outline.get("chapter_number", chapter_num),
                chapter_title=ch_outline.get("chapter_title"),
                chapter_summary=ch_outline.get("chapter_summary"),
                detailed_outline=ch_outline.get("detailed_outline", ""),
                key_events=ch_outline.get("key_events"),
                character_arcs=ch_outline.get("character_arcs"),
                suspense_points=ch_outline.get("suspense_points"),
                emotional_tone=ch_outline.get("emotional_tone"),
                status=ch_outline.get("status", "edited"),
                created_at=ch_outline.get("created_at"),
                updated_at=ch_outline.get("updated_at")
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"更新章节大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.delete("/projects/{project_id}/chapter-outlines/{chapter_num}")
async def delete_chapter_outline(
    project_id: int,
    chapter_num: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除章节详细大纲（小说专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 删除大纲
        chapter_outlines = project.chapter_outlines or {}
        if str(chapter_num) in chapter_outlines:
            del chapter_outlines[str(chapter_num)]
            project.chapter_outlines = chapter_outlines
            flag_modified(project, 'chapter_outlines')
            await db.commit()
            logger.info(f"第{chapter_num}章详细大纲已删除: {project.title}")
            return ResponseModel(success=True, message=f"第{chapter_num}章详细大纲已删除")
        else:
            raise ResourceNotFoundException(f"第{chapter_num}章的详细大纲不存在")

    except AppException:
        raise
    except Exception as e:
        logger.error(f"删除章节大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 场景详细大纲 API（电影剧本专用） ====================

@router.get("/projects/{project_id}/scene-outlines", response_model=ResponseModel[SceneOutlineListResponse])
async def get_scene_outlines(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取所有场景详细大纲（电影剧本专用）
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 获取场景大纲
        scene_outlines = project.scene_outlines or {}

        # 获取总场景数
        total_scenes = project.total_chapters or 0

        # 如果没有配置总场景数，尝试从大纲中提取
        if total_scenes == 0 and project.outline_content:
            total_scenes = extract_chapter_count(
                project.outline_content, "movie_script")

        # 构建响应列表
        scenes = []
        generated_count = 0

        for sc_num in range(1, total_scenes + 1):
            sc_outline = scene_outlines.get(str(sc_num), {})
            if sc_outline:
                generated_count += 1
                scenes.append(SceneOutlineResponse(
                    scene_number=sc_outline.get("scene_number", sc_num),
                    scene_title=sc_outline.get("scene_title"),
                    location=sc_outline.get("location"),
                    scene_summary=sc_outline.get("scene_summary"),
                    detailed_outline=sc_outline.get("detailed_outline", ""),
                    characters=sc_outline.get("characters"),
                    estimated_duration=sc_outline.get("estimated_duration"),
                    key_action=sc_outline.get("key_action"),
                    dialogue_focus=sc_outline.get("dialogue_focus"),
                    status=sc_outline.get("status", "generated"),
                    content_status=sc_outline.get("content_status"),
                    content_word_count=sc_outline.get("content_word_count"),
                    created_at=sc_outline.get("created_at"),
                    updated_at=sc_outline.get("updated_at")
                ))
            else:
                scenes.append(SceneOutlineResponse(
                    scene_number=sc_num,
                    scene_title=f"第{sc_num}场",
                    location=None,
                    scene_summary=None,
                    detailed_outline="",
                    status="pending"
                ))

        return ResponseModel(
            success=True,
            data=SceneOutlineListResponse(
                project_id=project.id,
                total_scenes=total_scenes,
                generated_count=generated_count,
                scenes=scenes
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"获取场景大纲列表失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


# ==================== 章节大纲生成提示词 ====================

CHAPTER_OUTLINE_GENERATE_PROMPT = """你是一位专业的小说大纲撰写专家。请根据以下信息，为指定章节生成详细的章节大纲。

## 项目信息
- 书名：{title}
- 类型：{genre}
- 基调：{tone}

## 全局大纲摘要
{global_outline_summary}

## 章节简要概述
- 章节：第{chapter_num}章
- 标题：{chapter_title}
- 概要：{chapter_summary}

## 输出要求

请为第{chapter_num}章生成一份详细的章节大纲，包含以下内容：

1. **章节标题**：保持原标题或优化
2. **章节概要**（200-300字）：完整描述本章的情节发展，包含开端、发展、转折、结尾
3. **详细大纲**（500-800字）：按场景或情节节点展开，描写具体的情节发展、人物互动、场景转换
4. **关键事件**（3-5个）：列出本章的关键情节点
5. **角色发展**：描述本章中主要角色的成长或变化
6. **悬念设置**：本章的悬念或钩子，引出下一章
7. **情感基调**：本章的情感氛围

## 输出格式（JSON）

请严格按照以下JSON格式输出：

```json
{{
    "chapter_number": {chapter_num},
    "chapter_title": "章节标题",
    "chapter_summary": "200-300字的章节概要",
    "detailed_outline": "500-800字的详细大纲",
    "key_events": ["事件1", "事件2", "事件3"],
    "character_arcs": "角色发展描述",
    "suspense_points": "悬念设置",
    "emotional_tone": "情感基调"
}}
```

请直接输出JSON内容，不要包含markdown代码块标记。
"""


# ==================== 章节大纲生成 API ====================

@router.post("/projects/{project_id}/generate-chapter-outlines")
async def generate_chapter_outlines(
    project_id: int,
    request: ChapterOutlineGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    生成章节详细大纲（小说专用）

    基于项目的全局大纲和单元概述，为指定章节生成详细的章节大纲。

    支持三种生成模式：
    1. 指定章节列表：通过 chapter_numbers 参数指定
    2. 范围生成：通过 start_unit 和 unit_count 参数指定起始和数量
    3. 全量生成：不指定参数时自动生成所有未生成的章节

    断点续传：当 skip_existing=True 时，会自动跳过已生成的章节

    Args:
        project_id: 项目ID
        request: 生成请求，包含：
            - chapter_numbers: 指定要生成的章节列表
            - start_unit: 起始单元编号（范围模式）
            - unit_count: 生成数量（范围模式）
            - stop_on_error: 出错时是否停止
            - skip_existing: 是否跳过已生成的章节（断点续传）

    Returns:
        生成结果，包含成功和失败的章节列表
    """
    try:
        # 获取项目
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 检查是否为小说类型
        if project.content_type and project.content_type != "novel":
            raise ValidationException("此功能仅适用于小说类型项目")

        # 获取全局大纲
        global_outline = project.outline_content or ""

        # 获取单元概述
        unit_summaries = project.unit_summaries or {}
        if not unit_summaries:
            raise ValidationException("请先生成单元概述（第二阶段大纲）")

        # 确定要生成的章节
        total_chapters = project.total_chapters or len(unit_summaries)
        existing_outlines = project.chapter_outlines or {}

        if request.chapter_numbers:
            # 指定章节列表
            chapters_to_generate = request.chapter_numbers
        elif request.start_unit is not None:
            # 使用范围参数：start_unit 和 unit_count
            start = request.start_unit
            if request.unit_count is not None:
                end = min(start + request.unit_count - 1, total_chapters)
            else:
                end = total_chapters
            chapters_to_generate = list(range(start, end + 1))

            # 如果启用了断点续传，过滤掉已生成的章节
            if request.skip_existing:
                chapters_to_generate = [
                    ch for ch in chapters_to_generate
                    if str(ch) not in existing_outlines or
                    existing_outlines[str(ch)].get("status") == "pending"
                ]
        else:
            # 生成所有未生成详细大纲的章节
            chapters_to_generate = [
                i for i in range(1, total_chapters + 1)
                if str(i) not in existing_outlines or
                existing_outlines[str(i)].get("status") == "pending"
            ]

        if not chapters_to_generate:
            return ResponseModel(
                success=True,
                message="所有章节的详细大纲已存在",
                data={
                    "generated": [],
                    "failed": [],
                    "total_chapters": total_chapters,
                    "generated_count": len(existing_outlines)
                }
            )

        # 获取LLM配置
        from app.agents.llm_manager import get_llm_manager
        from app.models.writing_model_config import WritingModelConfig
        from app.models.api_key import UserAPIKey
        from app.core.security import api_key_encryption
        from app.core.config import PRESET_MODELS

        llm_manager = get_llm_manager()
        provider_name = None
        model_name = None
        api_key = None
        api_base = None

        # 优先级1：从 WritingModelConfig 获取
        wmc_stmt = select(WritingModelConfig).where(
            WritingModelConfig.user_id == current_user.id,
            WritingModelConfig.is_active == True
        ).order_by(WritingModelConfig.updated_at.desc())
        wmc_result = await db.execute(wmc_stmt)
        wmc_config = wmc_result.scalar_one_or_none()

        if wmc_config:
            provider_name = wmc_config.provider
            model_name = wmc_config.model_id
            api_base = wmc_config.api_base
            try:
                api_key = api_key_encryption.decrypt(wmc_config.encrypted_key)
                logger.info(
                    f"使用 WritingModelConfig: provider={provider_name}, model={model_name}")
            except Exception as decrypt_error:
                logger.warning(
                    f"WritingModelConfig API密钥解密失败，可能SECRET_KEY已变更: {decrypt_error}")
                provider_name = None
                model_name = None
                api_key = None
                api_base = None

        # 优先级2：从 UserAPIKey 获取
        if not provider_name:
            api_key_stmt = select(UserAPIKey).where(
                UserAPIKey.user_id == current_user.id,
                UserAPIKey.is_valid == True
            ).order_by(UserAPIKey.is_default.desc())
            api_key_result = await db.execute(api_key_stmt)
            api_key_record = api_key_result.scalar_one_or_none()

            if api_key_record:
                provider_name = api_key_record.provider
                model_name = api_key_record.model_name
                api_base = api_key_record.api_base
                try:
                    api_key = api_key_encryption.decrypt(
                        api_key_record.encrypted_key)
                except Exception as decrypt_error:
                    logger.warning(f"UserAPIKey 解密失败: {decrypt_error}")
                    api_key_record.is_valid = False
                    await db.commit()
                    raise ValidationException(
                        "API密钥解密失败，SECRET_KEY可能已变更，请重新配置API密钥")

                preset = PRESET_MODELS.get(provider_name, {})
                if not model_name:
                    model_name = preset.get("default_model")
                if not api_base:
                    api_base = preset.get("api_base")

        if not provider_name or not api_key:
            raise ValidationException("请先配置API密钥")

        # 创建Provider
        try:
            provider = llm_manager.create_provider(
                provider_name=provider_name,
                api_key=api_key,
                model_name=model_name,
                api_base=api_base
            )
        except ValueError as e:
            raise ValidationException(str(e))

        # 准备全局大纲摘要（取前3000字）
        global_outline_summary = global_outline[:3000] if len(
            global_outline) > 3000 else global_outline

        # 生成各章节详细大纲
        generated = []
        failed = []
        updated_outlines = dict(existing_outlines)

        for chapter_num in chapters_to_generate:
            try:
                # 获取章节简要概述
                unit_key = str(chapter_num)
                unit_data = unit_summaries.get(unit_key, {})
                chapter_title = unit_data.get("title", f"第{chapter_num}章")
                chapter_summary = unit_data.get("summary", "")

                if not chapter_summary:
                    logger.warning(f"章节 {chapter_num} 没有简要概述，跳过")
                    continue

                # 构建提示词
                novel_config = project.novel_config or {}
                prompt = CHAPTER_OUTLINE_GENERATE_PROMPT.format(
                    title=project.title or "未命名",
                    genre=project.genre or "未指定",
                    tone=novel_config.get("tone", "正剧"),
                    global_outline_summary=global_outline_summary,
                    chapter_num=chapter_num,
                    chapter_title=chapter_title,
                    chapter_summary=chapter_summary
                )

                # 调用LLM生成
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=None,
                    temperature=0.7,
                    max_tokens=2000
                )
                response_text = response.content.strip()

                # 解析JSON响应
                if response_text.startswith("```"):
                    response_text = re.sub(r'^```\w*\n?', '', response_text)
                    response_text = re.sub(r'\n?```$', '', response_text)

                outline_data = json.loads(response_text)

                # 添加元数据
                outline_data["chapter_number"] = chapter_num
                outline_data["status"] = "generated"
                outline_data["created_at"] = datetime.now().isoformat()
                outline_data["updated_at"] = datetime.now().isoformat()

                # 保存到字典
                updated_outlines[str(chapter_num)] = outline_data
                generated.append(chapter_num)

                logger.info(f"章节 {chapter_num} 详细大纲生成成功")

            except json.JSONDecodeError as e:
                logger.error(f"章节 {chapter_num} JSON解析失败: {str(e)}")
                failed.append({"chapter": chapter_num, "error": "JSON解析失败"})
                if request.stop_on_error:
                    break
            except Exception as e:
                logger.error(f"章节 {chapter_num} 生成失败: {str(e)}")
                failed.append({"chapter": chapter_num, "error": str(e)})
                if request.stop_on_error:
                    break

        # 保存到数据库
        if generated:
            project.chapter_outlines = updated_outlines
            flag_modified(project, 'chapter_outlines')
            await db.commit()

        return ResponseModel(
            success=len(generated) > 0,
            message=f"成功生成 {len(generated)} 个章节详细大纲",
            data={
                "generated": generated,
                "failed": failed,
                "total_chapters": total_chapters,
                "generated_count": len(updated_outlines)
            }
        )

    except AppException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e) if str(e) else repr(e)
        logger.error(f"生成章节详细大纲失败: {error_detail}\n{traceback.format_exc()}")
        raise AppException(ErrorCode.INTERNAL_ERROR, error_detail or "内部服务器错误")


# ==================== 章节大纲异步生成（支持中断） ====================

# 章节大纲生成任务状态缓存
_chapter_outline_tasks: Dict[int, Dict[str, Any]] = {}


def _set_chapter_outline_task(project_id: int, task_data: Dict[str, Any]):
    """设置章节大纲生成任务状态"""
    _chapter_outline_tasks[project_id] = task_data


def _get_chapter_outline_task(project_id: int) -> Optional[Dict[str, Any]]:
    """获取章节大纲生成任务状态"""
    return _chapter_outline_tasks.get(project_id)


def _clear_chapter_outline_task(project_id: int):
    """清除章节大纲生成任务状态"""
    if project_id in _chapter_outline_tasks:
        del _chapter_outline_tasks[project_id]


# ==================== 单元概述质控触发 API ====================

@router.post("/projects/{project_id}/unit-summaries/quality-control",
             response_model=ResponseModel[UnitSummariesQualityControlResponse])
async def trigger_unit_summaries_quality_control(
    project_id: int,
    request: UnitSummariesQualityControlRequest = UnitSummariesQualityControlRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    手动触发单元概述质控检测

    流程:
    1. 获取项目的单元概述数据
    2. 执行五维度质控检测(unit_structure, unit_character, unit_consistency, unit_timeline_space, unit_ooc)
    3. 自动修正严重问题(如果enable_auto_revision=True)
    4. 返回质控报告和修改对比

    质控维度:
    - unit_structure: 单元结构层(章节标题、梗概完整性)
    - unit_character: 人物发展层(人物成长轨迹、性格变化)
    - unit_consistency: 一致性层(与全局大纲的偏离度)
    """
    try:
        from app.services.outline_generator import OutlineGenerator
        from app.services.quality_control import QualityControlService
        from app.agents.llm_manager import get_llm_manager

        # 1. 获取项目数据和单元概述
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        # 并发控制: 检查是否已有质控在运行
        if project.unit_summaries_status == 'quality_control_running':
            raise ValidationException("质控检测正在进行中,请勿重复触发")

        unit_summaries = project.unit_summaries or {}
        # 兼容两种全局大纲存储位置: global_outline_content(两阶段生成) 或 outline_content(上传)
        global_outline = project.global_outline_content or project.outline_content or ""
        content_type = project.content_type or "novel"

        if not unit_summaries:
            raise ValidationException("项目暂无单元概述数据")

        logger.info(
            f"[单元概述质控] 开始质控检测: "
            f"project_id={project_id}, units={len(unit_summaries)}, "
            f"content_type={content_type}"
        )

        # 标记质控开始
        original_status = project.unit_summaries_status
        project.unit_summaries_status = 'quality_control_running'
        await db.commit()

        try:
            # 2. 构建质控数据
            chapters_data = []
            for unit_num, unit_data in unit_summaries.items():
                chapters_data.append({
                    "id": int(unit_num),
                    "unit_id": unit_data.get("unit_id", f"unit-{unit_num}"),
                    "chapter_number": int(unit_num),
                    "content": unit_data.get("full_content", "") or unit_data.get("summary", ""),
                    "summary": unit_data.get("summary", ""),
                    "full_content": unit_data.get("full_content", ""),
                    "title": unit_data.get("title", ""),
                    "status": "completed"
                })

            # 3. 执行质控分析
            qc_service = QualityControlService(db=db)
            outline_generator = OutlineGenerator(db=db)

            quality_report = await outline_generator._analyze_unit_summaries_quality(
                qc_service=qc_service,
                chapters_data=chapters_data,
                dimensions=["unit_structure",
                            "unit_character", "unit_consistency",
                            "unit_timeline_space", "unit_ooc"],
                depth="deep",
                global_outline=global_outline,
                user_id=current_user.id
            )

            logger.info(
                f"[单元概述质控] 质控分析完成: "
                f"发现{len(quality_report.get('issues', []))}个问题"
            )

            # 4. 自动修正严重问题
            revision_summary = []
            revised_count = 0

            if request.enable_auto_revision:
                critical_issues = [
                    issue for issue in quality_report.get("issues", [])
                    if issue.get("severity") == "critical"
                ]

                if critical_issues:
                    logger.info(
                        f"[单元概述质控] 发现{len(critical_issues)}个严重问题,开始自动修正"
                    )

                    # 构建修正提示词
                    revision_prompt = outline_generator._build_quality_revision_prompt(
                        unit_summaries=unit_summaries,
                        quality_report_dict=quality_report,
                        global_outline=global_outline,
                        content_type=content_type
                    )

                    # 获取LLM提供商
                    llm_manager = get_llm_manager()
                    llm_provider = await llm_manager.get_provider_from_db(
                        db, current_user.id
                    )

                    if llm_provider:
                        # 调用LLM修正
                        revision_response = await llm_provider.generate(
                            prompt=revision_prompt,
                            temperature=0.7
                        )

                        # 解析修正结果
                        revised_parsed = outline_generator._parse_quality_revision_result(
                            revision_response.content, unit_summaries
                        )

                        # 生成修改对比
                        if revised_parsed:
                            for unit_num, revised_data in revised_parsed.items():
                                if unit_num in unit_summaries:
                                    original = unit_summaries[unit_num].get(
                                        "summary", "")
                                    revised = revised_data.get(
                                        "summary", original)

                                    if original != revised:
                                        revision_summary.append({
                                            "unit_number": int(unit_num),
                                            "unit_title": unit_summaries[unit_num].get("title", ""),
                                            "original_summary": original,
                                            "revised_summary": revised,
                                            "revision_reason": revised_data.get("revision_reason", "")
                                        })

                            # 保存修正后的数据到数据库
                            updated_summaries = {**unit_summaries}
                            for unit_num, revised_data in revised_parsed.items():
                                if unit_num in updated_summaries:
                                    # 保留原始数据的所有字段,仅更新修正字段
                                    original_unit = updated_summaries[unit_num]
                                    updated_summaries[unit_num] = {
                                        **original_unit,  # 保留所有原始字段
                                        "summary": revised_data.get("summary", original_unit.get("summary", "")),
                                        "quality_revised": True,
                                        "revision_reason": revised_data.get("revision_reason", ""),
                                        "revised_at": datetime.now().isoformat()  # 添加修正时间戳
                                    }

                            project.unit_summaries = updated_summaries
                            flag_modified(project, 'unit_summaries')
                            await db.commit()

                            revised_count = len(revision_summary)
                            logger.info(
                                f"[单元概述质控] 自动修正完成: 修正{revised_count}个单元"
                            )
                    else:
                        logger.warning("[单元概述质控] 无法获取LLM提供商,跳过自动修正")
                else:
                    logger.info("[单元概述质控] 无严重问题,无需修正")
            else:
                logger.info("[单元概述质控] 用户禁用自动修正")

            # 5. 返回结果
            message = f"质控完成,发现{len(quality_report.get('issues', []))}个问题"
            if revised_count > 0:
                message += f",自动修正{revised_count}个单元"

            return ResponseModel(
                success=True,
                data=UnitSummariesQualityControlResponse(
                    success=True,
                    quality_report=quality_report,
                    revision_summary=revision_summary,
                    revised_count=revised_count,
                    message=message
                )
            )

        finally:
            # 恢复原始状态
            project.unit_summaries_status = original_status if original_status != 'quality_control_running' else 'completed'
            await db.commit()

    except ResourceNotFoundException:
        raise
    except ValidationException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e) if str(e) else repr(e)
        logger.error(
            f"[单元概述质控] 质控检测失败: {error_detail}\n{traceback.format_exc()}")
        raise AppException(ErrorCode.INTERNAL_ERROR, f"质控检测失败: {error_detail}")
