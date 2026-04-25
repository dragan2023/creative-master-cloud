"""大纲管理 - 上传端点（upload-outline, upload-unit-summaries, upload-unit-summaries-file）+ 解析辅助函数"""
import os
import re
import tempfile
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import Depends, UploadFile, File
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
from app.schemas.novel_writer import OutlineUploadResponse

from ..utils import router, logger, get_project_data_dir
from ._models import UnitSummariesUploadRequest, UnitSummariesUploadResponse


def extract_chapter_count(content: str, content_type: str = "novel") -> int:
    """从大纲内容中提取章节数/集数/场景数"""
    from app.services.proofread.chapter_recognizer import count_chapters
    return count_chapters(content, content_type)


def extract_outline_units(content: str, content_type: str = "novel") -> List[Dict[str, Any]]:
    """从大纲内容中提取结构化单元（章节/分集/场景）"""
    from app.services.proofread.chapter_recognizer import recognize_chapters

    matches = recognize_chapters(content, content_type)
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


def parse_unit_summaries_from_content(content: str, content_type: str) -> Dict[str, Any]:
    """从文件内容中解析单元概述"""
    result = {}
    logger.info(
        f"[单元概述解析] 开始解析, content_type={content_type}, 内容长度={len(content)}")

    if content_type == "movie_script":
        patterns = [
            r'\*\*第(\d+)场[：:\s]*(.+?)\*\*',
            r'第(\d+)场[：:\s]+(.+?)(?:\n|$)',
        ]
        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            all_matches.extend(matches)

        seen = set()
        for match in all_matches:
            unit_num = int(match[0])
            if unit_num not in seen:
                seen.add(unit_num)
                title = match[1].strip()
                title = re.sub(r'[\*\s]+$', '', title)

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
        if content_type == "novel":
            unit_char = "章"
            summary_keyword = "本章"
        else:
            unit_char = "集"
            summary_keyword = "本集"

        patterns = [
            rf'###\s*第(\d+){unit_char}[：:\s]*(.+?)(?:\n|$)',
            rf'##\s*第(\d+){unit_char}[：:\s]*(.+?)(?:\n|$)',
            rf'第(\d+){unit_char}[：:\s]+(.+?)(?:\n|$)',
            rf'第(\d+){unit_char}\s+(.+?)(?:\n|$)',
        ]
        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            all_matches.extend(matches)

        seen = set()
        for match in all_matches:
            unit_num = int(match[0])
            if unit_num not in seen:
                seen.add(unit_num)
                title = match[1].strip()
                title = re.sub(r'^[：:\s]+', '', title)
                title = re.sub(r'[\*\s]+$', '', title)

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


@router.post("/projects/{project_id}/upload-outline", response_model=ResponseModel[OutlineUploadResponse])
async def upload_outline(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传大纲文件"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        file_ext = os.path.splitext(file.filename)[1].lower()
        logger.info(f"[大纲上传] 文件名: {file.filename}, 扩展名: {file_ext}")

        outline_content = None

        if file_ext in ['.txt', '.md']:
            content = await file.read()
            try:
                outline_content = content.decode('utf-8')
            except UnicodeDecodeError:
                outline_content = content.decode('gbk', errors='ignore')
            logger.info(f"[大纲上传] 文本文件直接解码成功，长度: {len(outline_content)}字")

        elif file_ext in ['.docx', '.doc']:
            from app.tools.file_parser import get_file_parser

            temp_file = os.path.join(
                tempfile.gettempdir(), f"outline_{project_id}_{file.filename}")
            content = await file.read()
            with open(temp_file, 'wb') as f:
                f.write(content)

            file_parser = get_file_parser()
            parse_result = await file_parser.parse(temp_file)

            try:
                os.remove(temp_file)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")

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

        actual_char_count = len(outline_content.strip())
        logger.info(f"[大纲上传] 大纲实际字数: {actual_char_count}字")

        project_dir = get_project_data_dir(project.project_code)
        outline_file = os.path.join(
            project_dir, f"{project.project_code}_outline.txt")

        with open(outline_file, 'w', encoding='utf-8') as f:
            f.write(outline_content)
        logger.info(f"[大纲上传] 文件已保存: {outline_file}")

        project.outline_file_path = outline_file
        project.outline_content = outline_content

        content_type = getattr(project, 'content_type', None)
        if not content_type:
            if project.project_type == ProjectType.NOVEL:
                content_type = "novel"
            else:
                content_type = "series_script"

        extracted_count = extract_chapter_count(outline_content, content_type)

        await db.commit()
        logger.info(f"[大纲上传] 数据库已提交, 提取{content_type}单元数: {extracted_count}")

        unit_labels = {"novel": "章节", "series_script": "分集", "movie_script": "场景"}
        unit_label = unit_labels.get(content_type, "章节")

        logger.info(f"大纲上传成功: {project.title}, 提取{unit_label}数: {extracted_count}")

        return ResponseModel(
            success=True,
            data=OutlineUploadResponse(
                project_id=project.id,
                outline_content=outline_content[:1000] + "..." if len(outline_content) > 1000 else outline_content,
                extracted_chapters=extracted_count,
                message=f"大纲上传成功，共{actual_char_count}字，识别到{extracted_count}个{unit_label}"
            )
        )

    except AppException:
        raise
    except Exception as e:
        logger.error(f"上传大纲失败: {str(e)}")
        raise AppException(ErrorCode.INTERNAL_ERROR, str(e))


@router.post("/projects/{project_id}/upload-unit-summaries", response_model=ResponseModel[UnitSummariesUploadResponse])
async def upload_unit_summaries(
    project_id: int,
    request: UnitSummariesUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传单元概述"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        unit_summaries = request.unit_summaries
        if not unit_summaries or not isinstance(unit_summaries, dict):
            raise ValidationException("单元概述格式无效")

        for key, unit in unit_summaries.items():
            if not isinstance(unit, dict):
                raise ValidationException(f"单元 {key} 格式无效")
            if 'summary' not in unit:
                raise ValidationException(f"单元 {key} 缺少 summary 字段")

        project.unit_summaries = unit_summaries
        flag_modified(project, 'unit_summaries')
        project.unit_summaries_status = 'completed'
        project.unit_summaries_created_at = datetime.now().isoformat()

        if request.global_outline:
            project.global_outline_content = request.global_outline
            project.global_outline_status = 'completed'
            project.global_outline_created_at = datetime.now().isoformat()

        project.total_chapters = len(unit_summaries)

        await db.commit()

        logger.info(f"单元概述上传成功: project_id={project_id}, unit_count={len(unit_summaries)}")

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
    """上传单元概述文件"""
    try:
        query = select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id
        )
        result = await db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ResourceNotFoundException("项目不存在")

        file_ext = os.path.splitext(file.filename)[1].lower()
        logger.info(f"[单元概述上传] 文件名: {file.filename}, 扩展名: {file_ext}")

        file_content = None

        if file_ext in ['.txt', '.md']:
            content = await file.read()
            try:
                file_content = content.decode('utf-8')
            except UnicodeDecodeError:
                file_content = content.decode('gbk', errors='ignore')
            logger.info(f"[单元概述上传] 文本文件直接解码成功，长度: {len(file_content)}字")

        elif file_ext in ['.docx', '.doc']:
            from app.tools.file_parser import get_file_parser

            temp_file = os.path.join(
                tempfile.gettempdir(), f"unit_summaries_{project_id}_{file.filename}")
            content = await file.read()
            with open(temp_file, 'wb') as f:
                f.write(content)

            file_parser = get_file_parser()
            parse_result = await file_parser.parse(temp_file)

            try:
                os.remove(temp_file)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")

            if "error" in parse_result:
                raise ValidationException(f"文件解析失败: {parse_result['error']}")

            file_content = parse_result.get("content", "")
            logger.info(f"[单元概述上传] Word文件解析成功，长度: {len(file_content)}字")

        else:
            raise ValidationException(f"不支持的文件格式: {file_ext}，支持 .txt, .md, .docx, .doc")

        if not file_content or not file_content.strip():
            raise ValidationException("文件内容为空")

        content_type = getattr(project, 'content_type', None)
        if not content_type:
            if project.project_type == ProjectType.NOVEL:
                content_type = "novel"
            else:
                content_type = "series_script"

        unit_summaries = parse_unit_summaries_from_content(file_content, content_type)

        if not unit_summaries:
            raise ValidationException("无法从文件中解析出单元概述，请检查文件格式是否正确")

        project.unit_summaries = unit_summaries
        flag_modified(project, 'unit_summaries')
        project.unit_summaries_status = 'completed'
        project.unit_summaries_created_at = datetime.now().isoformat()
        project.total_chapters = len(unit_summaries)

        await db.commit()

        logger.info(f"单元概述文件上传成功: project_id={project_id}, unit_count={len(unit_summaries)}")

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
