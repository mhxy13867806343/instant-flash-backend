from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import get_current_user_required
from app.models.user import User

router = APIRouter(prefix="/api/upload", tags=["用户端上传"])

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "static" / "v1" / "upload"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".avi"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 200 * 1024 * 1024
CONTENT_TYPE_SUFFIXES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-msvideo": ".avi",
}


def ok(data: object = None, message: str = "success") -> dict[str, object]:
    return {"code": 200, "message": message, "data": data or {}}


def fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": {}},
    )


def safe_upload_name(filename: str) -> str:
    path = Path(filename or "upload.bin")
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", path.stem).strip("-") or "upload"
    suffix = path.suffix.lower()
    return f"{stem}{suffix}"


def suffix_from_content_type(content_type: str | None) -> str:
    return CONTENT_TYPE_SUFFIXES.get((content_type or "").split(";", 1)[0].strip().lower(), "")


def infer_media_type(filename: str, media_type: str | None, content_type: str | None) -> str:
    normalized = (media_type or "").strip().lower()
    suffix = Path(filename).suffix.lower()
    if normalized in {"image", "video"}:
        return normalized
    if suffix in IMAGE_SUFFIXES or (content_type or "").startswith("image/"):
        return "image"
    if suffix in VIDEO_SUFFIXES or (content_type or "").startswith("video/"):
        return "video"
    raise fail(status.HTTP_400_BAD_REQUEST, "文件格式不支持，仅支持图片或视频")


def is_valid_image_content(content: bytes, suffix: str) -> bool:
    if suffix == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    if suffix == ".webp":
        return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    if suffix == ".bmp":
        return content.startswith(b"BM")
    return False


def is_valid_video_content(content: bytes, suffix: str) -> bool:
    if suffix in {".mp4", ".mov", ".m4v"}:
        return len(content) >= 12 and content[4:8] == b"ftyp"
    if suffix == ".webm":
        return content.startswith(b"\x1aE\xdf\xa3")
    if suffix == ".avi":
        return len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"AVI "
    return False


def validate_media_content(content: bytes, media_type: str, suffix: str) -> None:
    if media_type == "image" and not is_valid_image_content(content, suffix):
        raise fail(status.HTTP_400_BAD_REQUEST, "图片文件内容不正确")
    if media_type == "video" and not is_valid_video_content(content, suffix):
        raise fail(status.HTTP_400_BAD_REQUEST, "视频文件内容不正确")


def save_media_file(file: UploadFile, current_user: User, media_type: str | None) -> dict[str, object]:
    original_name = safe_upload_name(file.filename or "upload.bin")
    suffix = Path(original_name).suffix.lower()
    resolved_type = infer_media_type(original_name, media_type, file.content_type)
    if not suffix:
        suffix = suffix_from_content_type(file.content_type)
        if suffix:
            original_name = f"{Path(original_name).stem}{suffix}"
    allowed_suffixes = IMAGE_SUFFIXES if resolved_type == "image" else VIDEO_SUFFIXES
    if suffix not in allowed_suffixes:
        message = "图片格式不正确" if resolved_type == "image" else "视频格式不正确"
        raise fail(status.HTTP_400_BAD_REQUEST, message)

    content = file.file.read()
    if not content:
        raise fail(status.HTTP_400_BAD_REQUEST, "上传文件不能为空")
    max_size = MAX_IMAGE_SIZE if resolved_type == "image" else MAX_VIDEO_SIZE
    if len(content) > max_size:
        size_text = "10MB" if resolved_type == "image" else "200MB"
        raise fail(status.HTTP_400_BAD_REQUEST, f"上传文件不能超过 {size_text}")
    validate_media_content(content, resolved_type, suffix)

    md5 = hashlib.md5(content).hexdigest()
    upload_dir = UPLOAD_ROOT / resolved_type / current_user.user_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{md5}{suffix}"
    file_path = upload_dir / stored_name
    file_path.write_bytes(content)
    relative_path = Path("v1") / "upload" / resolved_type / current_user.user_id / stored_name
    url = f"static/{relative_path.as_posix()}"
    return {
        "url": url,
        "name": original_name,
        "filename": stored_name,
        "type": resolved_type,
        "mediaType": resolved_type,
        "contentType": file.content_type or "",
        "size": len(content),
        "md5": md5,
    }


@router.post(
    "/media",
    summary="上传发布媒体",
    description="用户端发布动态前上传图片或视频，返回真实静态 URL。前端把返回的 url 放到发布动态 images/media 列表中。",
)
@router.post(
    "/post-media",
    include_in_schema=False,
)
def upload_post_media(
    current_user: Annotated[User, Depends(get_current_user_required)],
    file: Annotated[UploadFile, File(description="图片或视频文件")],
    media_type: Annotated[str | None, Form(alias="type", description="媒体类型：image/video，不传则按文件后缀自动识别")] = None,
) -> dict[str, object]:
    return ok(save_media_file(file, current_user, media_type), "上传成功")


@router.post(
    "/media/batch",
    summary="批量上传发布媒体",
    description="用户端发布动态前批量上传图片或视频，返回每个文件的真实静态 URL。",
)
def upload_post_media_batch(
    current_user: Annotated[User, Depends(get_current_user_required)],
    files: Annotated[list[UploadFile], File(description="图片或视频文件列表")],
    media_type: Annotated[str | None, Form(alias="type", description="媒体类型：image/video，不传则按文件后缀自动识别")] = None,
) -> dict[str, object]:
    uploaded = [save_media_file(file, current_user, media_type) for file in files]
    return ok({"list": uploaded, "items": uploaded, "total": len(uploaded)}, "上传成功")
