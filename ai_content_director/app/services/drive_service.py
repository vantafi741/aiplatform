"""Google Drive helper service cho pipeline Drive -> Facebook."""
from typing import Any, Dict, List, Tuple

from app.config import get_settings
from app.services.gdrive_dropzone import list_files, move_file


def list_ready_files() -> List[Tuple[str, Dict[str, Any]]]:
    """
    Scan READY folders từ ENV và trả về list item.

    Returns:
        List[(expected_type, file_meta)]
    """
    settings = get_settings()
    files: List[Tuple[str, Dict[str, Any]]] = []

    if settings.gdrive_ready_images_folder_id:
        for meta in list_files(settings.gdrive_ready_images_folder_id):
            files.append(("image", meta))

    if settings.gdrive_ready_videos_folder_id:
        for meta in list_files(settings.gdrive_ready_videos_folder_id):
            files.append(("video", meta))

    return files


def move_to_processed(file_id: str) -> bool:
    """Move file sang PROCESSED folder nếu cấu hình đủ."""
    settings = get_settings()
    if not settings.gdrive_processed_folder_id:
        return False
    move_file(file_id, settings.gdrive_processed_folder_id)
    return True


def move_to_rejected(file_id: str) -> bool:
    """Move file sang REJECTED folder nếu cấu hình đủ."""
    settings = get_settings()
    if not settings.gdrive_rejected_folder_id:
        return False
    move_file(file_id, settings.gdrive_rejected_folder_id)
    return True

