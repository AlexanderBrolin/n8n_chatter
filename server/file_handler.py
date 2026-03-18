import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from server.models import FileAttachment

ALLOWED_EXTENSIONS = {
    "txt", "pdf", "doc", "docx", "xls", "xlsx", "csv",
    "png", "jpg", "jpeg", "gif", "webp", "svg",
    "zip", "tar", "gz", "7z", "rar",
    "json", "xml", "yaml", "yml",
    "mp4", "mp3", "ogg", "wav",
    "pptx", "ppt",
}

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}


def get_upload_dir():
    return current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.join(os.path.dirname(__file__), "static", "uploads"),
    )


def save_upload(file_storage):
    """Save an uploaded file and return a FileAttachment (not yet in DB session)."""
    filename = secure_filename(file_storage.filename or "file")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    file_id = uuid.uuid4().hex

    upload_dir = get_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, stored_name)
    file_storage.save(filepath)
    file_size = os.path.getsize(filepath)

    return FileAttachment(
        filename=filename,
        stored_name=stored_name,
        mime_type=file_storage.content_type or "",
        file_size=file_size,
        file_id=file_id,
    )


def is_image(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in IMAGE_EXTENSIONS
