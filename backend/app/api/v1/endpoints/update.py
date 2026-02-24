"""
软件更新 API 端点
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import httpx
import hashlib
import os
import asyncio
from datetime import datetime

from app.core.config import get_settings
from app.core.logger import get_logger
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/update", tags=["更新"])
settings = get_settings()
logger = get_logger("update")


# ==================== 数据模型 ====================

class VersionInfo(BaseModel):
    """版本信息"""
    current_version: str = Field(..., description="当前版本号")
    minimum_version: str = Field(..., description="最低支持版本")
    download_url: str = Field(..., description="下载地址")
    download_url_mirror: Optional[str] = Field(None, description="镜像下载地址")
    update_notes: str = Field(..., description="更新说明")
    release_date: str = Field(..., description="发布日期")
    file_size_mb: int = Field(..., description="文件大小(MB)")
    file_hash_md5: str = Field(..., description="MD5校验值")
    force_update: bool = Field(False, description="是否强制更新")
    changelog_url: Optional[str] = Field(None, description="更新日志地址")


class UpdateCheckRequest(BaseModel):
    """更新检查请求"""
    current_version: str = Field(..., description="当前版本号")
    platform: Optional[str] = Field("windows", description="操作系统")


class UpdateCheckResponse(BaseModel):
    """更新检查响应"""
    has_update: bool = Field(..., description="是否有更新")
    is_critical: bool = Field(False, description="是否为关键更新")
    current_version: str = Field(..., description="当前版本")
    latest_version: str = Field(..., description="最新版本")
    download_url: str = Field(..., description="下载地址")
    download_url_mirror: Optional[str] = Field(None, description="镜像下载地址")
    file_size_mb: int = Field(..., description="文件大小(MB)")
    file_hash_md5: str = Field(..., description="MD5校验值")
    update_notes: str = Field(..., description="更新说明")
    release_date: str = Field(..., description="发布日期")
    force_update: bool = Field(False, description="是否强制更新")


class DownloadProgress(BaseModel):
    """下载进度"""
    status: str = Field(..., description="状态: downloading/complete/error")
    progress: float = Field(0, description="进度百分比 0-100")
    downloaded_mb: float = Field(0, description="已下载MB")
    total_mb: float = Field(0, description="总大小MB")
    speed_mbps: Optional[float] = Field(None, description="下载速度MB/s")
    eta_seconds: Optional[int] = Field(None, description="预计剩余秒数")
    message: Optional[str] = Field(None, description="消息")


# ==================== 版本比较工具 ====================

def compare_versions(v1: str, v2: str) -> int:
    """
    比较两个版本号
    返回: 1 表示 v1 > v2, -1 表示 v1 < v2, 0 表示相等
    """
    def parse_version(v):
        return [int(x) for x in v.split('.')]
    
    parts1 = parse_version(v1)
    parts2 = parse_version(v2)
    
    # 补齐版本号长度
    max_len = max(len(parts1), len(parts2))
    parts1.extend([0] * (max_len - len(parts1)))
    parts2.extend([0] * (max_len - len(parts2)))
    
    for p1, p2 in zip(parts1, parts2):
        if p1 > p2:
            return 1
        elif p1 < p2:
            return -1
    return 0


# ==================== API 端点 ====================

@router.get("/version.json")
async def get_version_info():
    """
    获取最新版本信息（公开接口，用于托管在静态服务器）
    这个接口返回的数据可以被 GitHub Pages 或其他静态托管服务使用
    """
    try:
        # 从远程服务器获取版本信息
        version_url = os.environ.get(
            "VERSION_CHECK_URL",
            "https://raw.githubusercontent.com/YOUR_USERNAME/creative-master/main/version.json"
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(version_url)
            if response.status_code == 200:
                return response.json()
            else:
                # 返回本地默认版本信息
                return VersionInfo(
                    current_version=settings.APP_VERSION,
                    minimum_version="0.9.0",
                    download_url="",
                    download_url_mirror="",
                    update_notes="当前为最新版本",
                    release_date=datetime.now().strftime("%Y-%m-%d"),
                    file_size_mb=0,
                    file_hash_md5="",
                    force_update=False
                ).model_dump()
    except Exception as e:
        logger.error(f"获取版本信息失败: {str(e)}")
        # 返回本地版本信息作为备选
        return VersionInfo(
            current_version=settings.APP_VERSION,
            minimum_version="0.9.0",
            download_url="",
            download_url_mirror="",
            update_notes="当前为最新版本",
            release_date=datetime.now().strftime("%Y-%m-%d"),
            file_size_mb=0,
            file_hash_md5="",
            force_update=False
        ).model_dump()


@router.post("/check", response_model=ResponseModel[UpdateCheckResponse])
async def check_update(request: UpdateCheckRequest):
    """
    检查软件更新
    
    - 比较当前版本与最新版本
    - 返回更新信息和下载地址
    """
    try:
        # 获取最新版本信息
        version_url = os.environ.get(
            "VERSION_CHECK_URL",
            "https://raw.githubusercontent.com/YOUR_USERNAME/creative-master/main/version.json"
        )
        
        # 尝试从 GitHub 获取版本信息
        version_info = None
        
        # 首先尝试镜像地址（国内加速）
        mirror_url = "https://ghproxy.com/" + version_url
        
        for url in [mirror_url, version_url]:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        version_info = response.json()
                        break
            except:
                continue
        
        if not version_info:
            # 使用本地版本信息
            version_info = {
                "current_version": settings.APP_VERSION,
                "minimum_version": "0.9.0",
                "download_url": "",
                "download_url_mirror": "",
                "update_notes": "无法获取更新信息",
                "release_date": datetime.now().strftime("%Y-%m-%d"),
                "file_size_mb": 0,
                "file_hash_md5": "",
                "force_update": False
            }
        
        latest_version = version_info.get("current_version", settings.APP_VERSION)
        
        # 比较版本
        comparison = compare_versions(latest_version, request.current_version)
        has_update = comparison > 0
        
        # 检查是否为关键更新（当前版本低于最低支持版本）
        minimum_version = version_info.get("minimum_version", "0.0.0")
        is_critical = compare_versions(minimum_version, request.current_version) > 0
        
        # 选择下载地址（优先使用镜像）
        download_url = version_info.get("download_url_mirror") or version_info.get("download_url", "")
        
        result = UpdateCheckResponse(
            has_update=has_update,
            is_critical=is_critical,
            current_version=request.current_version,
            latest_version=latest_version,
            download_url=download_url,
            download_url_mirror=version_info.get("download_url_mirror"),
            file_size_mb=version_info.get("file_size_mb", 0),
            file_hash_md5=version_info.get("file_hash_md5", ""),
            update_notes=version_info.get("update_notes", ""),
            release_date=version_info.get("release_date", ""),
            force_update=version_info.get("force_update", False) or is_critical
        )
        
        if has_update:
            logger.info(f"检测到新版本: {latest_version} (当前: {request.current_version})")
        
        return ResponseModel(data=result)
        
    except Exception as e:
        logger.error(f"检查更新失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"检查更新失败: {str(e)}")


@router.get("/download", response_model=ResponseModel[dict])
async def get_download_info():
    """
    获取下载信息
    """
    try:
        version_url = os.environ.get(
            "VERSION_CHECK_URL",
            "https://raw.githubusercontent.com/YOUR_USERNAME/creative-master/main/version.json"
        )
        
        # 尝试镜像地址
        mirror_url = "https://ghproxy.com/" + version_url
        
        version_info = None
        for url in [mirror_url, version_url]:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        version_info = response.json()
                        break
            except:
                continue
        
        if not version_info:
            raise HTTPException(status_code=503, detail="无法获取下载信息")
        
        return ResponseModel(data={
            "version": version_info.get("current_version"),
            "download_url": version_info.get("download_url_mirror") or version_info.get("download_url"),
            "file_size_mb": version_info.get("file_size_mb"),
            "file_hash_md5": version_info.get("file_hash_md5"),
            "release_date": version_info.get("release_date")
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取下载信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取下载信息失败: {str(e)}")


@router.get("/changelog")
async def get_changelog():
    """
    获取更新日志
    """
    try:
        changelog_url = os.environ.get(
            "CHANGELOG_URL",
            "https://raw.githubusercontent.com/YOUR_USERNAME/creative-master/main/CHANGELOG.md"
        )
        
        # 尝试镜像地址
        mirror_url = "https://ghproxy.com/" + changelog_url
        
        for url in [mirror_url, changelog_url]:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return {"content": response.text}
            except:
                continue
        
        return {"content": "无法获取更新日志"}
        
    except Exception as e:
        logger.error(f"获取更新日志失败: {str(e)}")
        return {"content": f"获取失败: {str(e)}"}


@router.get("/current-version")
async def get_current_version():
    """
    获取当前运行的版本
    """
    return {
        "version": settings.APP_VERSION,
        "app_name": settings.APP_NAME,
        "build_date": datetime.now().strftime("%Y-%m-%d")
    }
