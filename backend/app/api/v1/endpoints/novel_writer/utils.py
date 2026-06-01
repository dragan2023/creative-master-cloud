"""
小说/剧本生成模块 - 工具函数和共享资源

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logger import get_logger
from app.models import ProjectType
from app.schemas.novel_writer import (
    NovelProjectResponse,
    NovelConfig, SeriesScriptConfig, MovieScriptConfig,
    ContentType
)
from app.services.task_manager import (
    set_memory_cancel_token, clear_memory_cancel_token, 
    is_memory_cancelled, trigger_memory_cancel
)


router = APIRouter(prefix="/novel-writer", tags=["小说/剧本生成"])
settings = get_settings()
logger = get_logger("novel_writer")


# 内存取消令牌由 task_manager 模块管理
# 以下函数为 task_manager 内存令牌的便捷包装

def set_cancel_token(project_id: int) -> asyncio.Event:
    """为项目创建取消令牌（同时设置内存令牌）"""
    return set_memory_cancel_token(project_id)


def get_cancel_token(project_id: int) -> Optional[asyncio.Event]:
    """获取项目的取消令牌"""
    from app.services.task_manager import get_memory_cancel_token
    return get_memory_cancel_token(project_id)


def clear_cancel_token(project_id: int):
    """清除项目的取消令牌"""
    clear_memory_cancel_token(project_id)


def is_cancelled(project_id: int) -> bool:
    """检查项目是否被取消"""
    return is_memory_cancelled(project_id)


# ==================== 工具函数 ====================

def generate_project_code() -> str:
    """生成项目代码 NW_{timestamp}_{random_id}"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_id = uuid.uuid4().hex[:6]
    return f"NW_{timestamp}_{random_id}"


def get_project_data_dir(project_code: str) -> str:
    """获取项目数据目录"""
    base_dir = settings.CHROMA_PERSIST_DIR.replace(
        "/chroma", "/novel_projects")
    project_dir = os.path.join(base_dir, project_code)
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(os.path.join(project_dir, "chapters"), exist_ok=True)
    return project_dir


def _build_project_response(project) -> NovelProjectResponse:
    """构建项目响应对象（统一处理新版和旧版字段）"""
    # 获取content_type
    content_type = None
    if hasattr(project, 'content_type') and project.content_type:
        try:
            content_type = ContentType(project.content_type)
        except ValueError:
            pass

    # 兼容旧版：如果没有content_type，根据project_type推断
    if not content_type:
        if project.project_type == ProjectType.NOVEL:
            content_type = ContentType.NOVEL
        else:
            content_type = ContentType.SERIES_SCRIPT  # 默认为剧集剧本

    # 构建配置对象
    novel_config = None
    series_script_config = None
    movie_script_config = None

    # 从数据库字段获取配置
    if hasattr(project, 'novel_config') and project.novel_config:
        novel_config = NovelConfig(**project.novel_config) if isinstance(
            project.novel_config, dict) else project.novel_config
    if hasattr(project, 'series_script_config') and project.series_script_config:
        series_script_config = SeriesScriptConfig(**project.series_script_config) if isinstance(
            project.series_script_config, dict) else project.series_script_config
    if hasattr(project, 'movie_script_config') and project.movie_script_config:
        movie_script_config = MovieScriptConfig(**project.movie_script_config) if isinstance(
            project.movie_script_config, dict) else project.movie_script_config

    return NovelProjectResponse(
        id=project.id,
        title=project.title,
        project_type=project.project_type,
        content_type=content_type,
        genre=project.genre,
        target_platform=project.target_platform,
        status=project.status,
        total_chapters=project.total_chapters,
        completed_chapters=project.completed_chapters,
        current_chapter=project.current_chapter,
        progress_percentage=project.get_progress_percentage(),
        novel_config=novel_config,
        series_script_config=series_script_config,
        movie_script_config=movie_script_config,
        generation_config=project.generation_config,
        knowledge_base_config=project.knowledge_base_config,
        script_config=project.script_config,
        project_code=project.project_code,
        total_tokens=project.total_tokens,
        total_duration_ms=project.total_duration_ms,
        outline_content=project.outline_content,
        outline_word_count=len(project.outline_content.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")) if project.outline_content else 0,
        unit_summaries=project.unit_summaries if hasattr(project, 'unit_summaries') else None,
        unit_summaries_status=project.unit_summaries_status if hasattr(project, 'unit_summaries_status') else None,
        ai_elimination_enabled=project.ai_elimination_enabled if hasattr(project, 'ai_elimination_enabled') and project.ai_elimination_enabled is not None else True,
        ai_elimination_threshold=project.ai_elimination_threshold if hasattr(project, 'ai_elimination_threshold') and project.ai_elimination_threshold is not None else 50,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


def _chinese_to_number(chinese: str) -> int:
    """将中文数字转换为阿拉伯数字

    保留此函数以兼容旧代码，委托给统一的 ChapterRecognizer 处理
    """
    from app.services.proofread.chapter_recognizer import ChapterRecognizer

    recognizer = ChapterRecognizer()
    return recognizer._chinese_to_number(chinese)


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
    import re

    result = {}

    # 记录解析过程
    logger.info(f"[单元概述解析] 开始解析, content_type={content_type}, 内容长度={len(content)}")

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

                # 提取梗概（支持多种格式，兼容LLM误用"本章"代替"本集/本场"）
                summary = ""
                fallback_keyword = "本章" if content_type != "novel" else None
                summary_patterns = [
                    rf'第{unit_num}{unit_char}.*?\*\*{summary_keyword}梗概\*\*[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|\n\*\*第\d+{unit_char}|$)',
                    rf'第{unit_num}{unit_char}.*?{summary_keyword}梗概[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|\n\*\*第\d+{unit_char}|$)',
                    rf'\*\*{summary_keyword}梗概\*\*[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|\n\*\*第\d+{unit_char}|$)',
                ]
                # 添加回退关键词匹配（如剧集误输出"本章梗概"）
                if fallback_keyword and fallback_keyword != summary_keyword:
                    summary_patterns.extend([
                        rf'第{unit_num}{unit_char}.*?\*\*{fallback_keyword}梗概\*\*[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|\n\*\*第\d+{unit_char}|$)',
                        rf'第{unit_num}{unit_char}.*?{fallback_keyword}梗概[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|\n\*\*第\d+{unit_char}|$)',
                    ])
                # 最后回退：仅匹配 梗概：
                summary_patterns.append(
                    rf'第{unit_num}{unit_char}.*?梗概[：:]\s*(.+?)(?=###|##|\n第\d+{unit_char}|\n\*\*第\d+{unit_char}|$)'
                )

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

        logger.info(f"[单元概述解析] {'小说' if content_type == 'novel' else '剧集'}解析完成, 匹配到 {len(result)} 个单元")

    if not result:
        logger.warning(f"[单元概述解析] 未能解析出任何单元，content_type={content_type}")
        logger.debug(f"[单元概述解析] 内容预览: {content[:200]}...")

    return result
