"""
创意生成 API - 文件上传端点

@date: 2026-04-24
@version: v3.1.0 (从generate.py拆分)
"""
import os
import uuid
import aiofiles
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    AuthorizationException,
)
from app.core.logger import get_logger
from app.models import User
from app.schemas.common import ResponseModel

logger = get_logger(__name__)

# 支持的图片格式
ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp"
}

# 支持的文档格式（大纲文件）
ALLOWED_DOC_TYPES = {
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/pdf": ".pdf"
}

# 支持的文档扩展名
ALLOWED_DOC_EXTENSIONS = [".txt", ".md", ".doc", ".docx", ".pdf"]


def register_upload_routes(router: APIRouter):
    """注册文件上传相关路由"""

    @router.post("/upload")
    async def upload_file(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user)
    ):
        """
        上传文件（支持图片和文档）

        Args:
            file: 上传的文件

        Returns:
            文件URL和文件信息
        """
        from app.core.config import get_settings
        settings = get_settings()

        logger.info(
            f"[上传] 开始处理文件上传: filename={file.filename}, content_type={file.content_type}")

        content_type = file.content_type or ""
        file_ext = None
        file_type = None  # 'image' or 'document'

        # 检查是否为图片
        if content_type in ALLOWED_IMAGE_TYPES:
            file_ext = ALLOWED_IMAGE_TYPES[content_type]
            file_type = 'image'
            max_size = settings.MAX_IMAGE_SIZE
        # 检查是否为文档
        elif content_type in ALLOWED_DOC_TYPES:
            file_ext = ALLOWED_DOC_TYPES[content_type]
            file_type = 'document'
            max_size = settings.MAX_DOC_SIZE
        else:
            # 尝试通过文件扩展名判断（优先于 MIME 类型）
            original_ext = os.path.splitext(file.filename)[
                1].lower() if file.filename else ""
            if original_ext in ALLOWED_DOC_EXTENSIONS:
                file_ext = original_ext
                file_type = 'document'
                max_size = settings.MAX_DOC_SIZE
            elif content_type == "application/octet-stream":
                # 对于 application/octet-stream，尝试通过扩展名判断
                original_ext = os.path.splitext(file.filename)[
                    1].lower() if file.filename else ""
                if original_ext in ALLOWED_DOC_EXTENSIONS:
                    file_ext = original_ext
                    file_type = 'document'
                    max_size = settings.MAX_DOC_SIZE
                elif original_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
                    # 检查是否是图片扩展名
                    for mime_type, ext in ALLOWED_IMAGE_TYPES.items():
                        if ext == original_ext or (original_ext == ".jpeg" and ext == ".jpg"):
                            file_ext = ext
                            file_type = 'image'
                            max_size = settings.MAX_IMAGE_SIZE
                            break
                else:
                    logger.warning(
                        f"[上传] 不支持的文件类型: {content_type}, 扩展名: {original_ext}")
                    raise ValidationException(
                        f"不支持的文件类型: {original_ext}。支持图片(png/jpg/gif/webp)或文档(txt/md/doc/docx/pdf)，最大{int(settings.MAX_DOC_SIZE / 1024 / 1024)}MB"
                    )
            else:
                logger.warning(f"[上传] 不支持的文件类型: {content_type or original_ext}")
                raise ValidationException(
                    f"不支持的文件类型: {content_type or original_ext}。支持图片(png/jpg/gif/webp)或文档(txt/md/doc/docx/pdf)，最大{int(settings.MAX_DOC_SIZE / 1024 / 1024)}MB"
                )

        # 检查文件大小
        content = await file.read()
        if len(content) > max_size:
            size_mb = max_size / 1024 / 1024
            raise ValidationException(
                f"文件大小超过限制（{file_type == 'image' and '图片' or '文档'}最大{int(size_mb)}MB）"
            )

        # 获取上传目录
        upload_dir = settings.get_upload_dir()

        # 生成唯一文件名
        file_name = f"{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = os.path.join(upload_dir, file_name)

        # 保存文件
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # 返回文件URL
        file_url = f"/api/v1/generate/uploads/{file_name}"

        logger.info(
            f"[上传] 文件上传成功: filename={file.filename}, saved_as={file_name}, size={len(content)} bytes, url={file_url}")

        return ResponseModel(data={
            "url": file_url,
            "file_name": file_name,
            "content_type": content_type,
            "size": len(content),
            "file_type": file_type
        })

    @router.post("/upload-outline-import")
    async def upload_outline_for_import(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user)
    ):
        """
        上传大纲文件用于导入（解析文件内容并返回）

        支持格式：.txt, .md, .docx, .doc

        Args:
            file: 上传的大纲文件

        Returns:
            文件内容文本
        """
        from app.core.config import get_settings
        from app.tools.file_parser import parse_document_file

        settings = get_settings()

        logger.info(
            f"[导入大纲上传] 开始处理文件上传: filename={file.filename}, content_type={file.content_type}")

        # 验证文件类型
        allowed_extensions = ['.txt', '.md', '.docx', '.doc']
        original_ext = os.path.splitext(file.filename)[
            1].lower() if file.filename else ""

        if original_ext not in allowed_extensions:
            logger.warning(f"[导入大纲上传] 不支持的文件类型: {original_ext}")
            raise ValidationException(
                f"不支持的文件类型: {original_ext}。支持 .txt, .md, .docx, .doc 格式"
            )

        # 检查文件大小（使用配置的最大文档大小）
        content = await file.read()
        max_size = settings.MAX_DOC_SIZE
        if len(content) > max_size:
            raise ValidationException(
                f"文件大小超过限制（最大{int(max_size / 1024 / 1024)}MB）")

        try:
            # 解析文件内容
            text_content = await parse_document_file(file.filename, content)

            if not text_content or not text_content.strip():
                raise ValidationException("文件内容为空")

            logger.info(
                f"[导入大纲上传] 文件上传并解析成功: filename={file.filename}, content_length={len(text_content)}")

            return ResponseModel(data={
                "content": text_content,
                "file_name": file.filename,
                "file_type": original_ext,
                "size": len(content)
            })

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"[导入大纲上传] 文件解析失败: {str(e)}")
            raise ValidationException(f"文件解析失败: {str(e)}")

    @router.post("/upload-unit-summaries-import")
    async def upload_unit_summaries_for_import(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user)
    ):
        """
        上传单元概述文件用于导入

        支持格式：.txt, .md, .docx, .doc

        Args:
            file: 上传的单元概述文件

        Returns:
            文件内容文本
        """
        from app.core.config import get_settings
        from app.tools.file_parser import parse_document_file

        settings = get_settings()

        logger.info(
            f"[导入单元概述上传] 开始处理文件上传: filename={file.filename}, content_type={file.content_type}")

        # 验证文件类型
        allowed_extensions = ['.txt', '.md', '.docx', '.doc']
        original_ext = os.path.splitext(file.filename)[
            1].lower() if file.filename else ""

        if original_ext not in allowed_extensions:
            logger.warning(f"[导入单元概述上传] 不支持的文件类型: {original_ext}")
            raise ValidationException(
                f"不支持的文件类型: {original_ext}。支持 .txt, .md, .docx, .doc 格式"
            )

        # 检查文件大小（使用配置的最大文档大小）
        content = await file.read()
        max_size = settings.MAX_DOC_SIZE
        if len(content) > max_size:
            raise ValidationException(
                f"文件大小超过限制（最大{int(max_size / 1024 / 1024)}MB）")

        try:
            # 解析文件内容
            text_content = await parse_document_file(file.filename, content)

            if not text_content or not text_content.strip():
                raise ValidationException("文件内容为空")

            logger.info(
                f"[导入单元概述上传] 文件上传并解析成功: filename={file.filename}, content_length={len(text_content)}")

            return ResponseModel(data={
                "content": text_content,
                "file_name": file.filename,
                "file_type": original_ext,
                "size": len(content)
            })

        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"[导入单元概述上传] 文件解析失败: {str(e)}")
            raise ValidationException(f"文件解析失败: {str(e)}")

    @router.post("/upload/multiple")
    async def upload_multiple_files(
        files: List[UploadFile] = File(...),
        current_user: User = Depends(get_current_user)
    ):
        """
        批量上传文件

        Args:
            files: 上传的文件列表

        Returns:
            文件URL列表
        """
        if len(files) > 5:
            raise ValidationException("最多同时上传5个文件")

        results = []
        for file in files:
            try:
                result = await upload_file(file, current_user)
                results.append(result.data)
            except ValidationException as e:
                results.append({
                    "error": e.message,
                    "file_name": file.filename
                })

        return ResponseModel(data={"files": results})

    @router.get("/uploads/{file_name}")
    async def get_uploaded_file(file_name: str):
        """
        获取上传的文件

        Args:
            file_name: 文件名

        Returns:
            文件内容
        """
        from fastapi.responses import FileResponse
        from app.core.config import get_settings

        settings = get_settings()
        upload_dir = settings.get_upload_dir()
        file_path = os.path.join(upload_dir, file_name)

        if not os.path.exists(file_path):
            raise ResourceNotFoundException("文件不存在")

        # 安全检查：防止目录遍历攻击
        if not os.path.abspath(file_path).startswith(os.path.abspath(upload_dir)):
            raise AuthorizationException(message="访问被拒绝")

        return FileResponse(file_path)
