"""
Regression test: GDrive ingest idempotent – gọi ingest 2 lần thì số lượng content_assets không tăng.
- Lần 1: count_ingested >= 1 (nếu có file trong mock).
- Lần 2: count_ingested == 0, skipped_existing >= 1, tổng số row content_assets cho tenant không đổi.
Cần DB đã chạy migration 014 (ux_content_assets_tenant_drive_file).
Chạy: pytest tests/test_gdrive_ingest_idempotent.py -v
"""
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.db import async_session_factory
from app.models import ContentAsset, Tenant
from app.services.gdrive_dropzone import ingest_ready_assets


# Một file mock hợp lệ (image/jpeg, size nhỏ)
MOCK_FILE_ID = "test_drive_file_id_001"
MOCK_FILES = [
    {
        "id": MOCK_FILE_ID,
        "name": "test_image.jpg",
        "mimeType": "image/jpeg",
        "size": "1024",
    }
]


@pytest.mark.asyncio
async def test_gdrive_ingest_idempotent_double_run() -> None:
    """
    Gọi ingest_ready_assets 2 lần với cùng tenant và cùng mock file.
    Assert: lần 2 count_ingested=0, số row content_assets không tăng.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        media_dir = Path(tmpdir) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        # Mock settings: đủ folder IDs và local_media_dir = tmp
        mock_settings = type("Settings", (), {})()
        mock_settings.gdrive_sa_json_path = os.devnull  # không thực sự gọi Drive
        mock_settings.gdrive_ready_images_folder_id = "folder_images"
        mock_settings.gdrive_ready_videos_folder_id = None
        mock_settings.gdrive_processed_folder_id = "folder_processed"
        mock_settings.gdrive_rejected_folder_id = "folder_rejected"
        mock_settings.local_media_dir = str(media_dir)
        mock_settings.asset_max_image_mb = 10
        mock_settings.asset_max_video_mb = 200

        def fake_list_files(folder_id: str):
            return MOCK_FILES.copy()

        def fake_download_file(file_id: str, dest_path: str) -> str:
            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
            Path(dest_path).write_bytes(b"fake image content")
            return dest_path

        def fake_move_file(file_id: str, target_folder_id: str) -> None:
            pass

        with (
            patch("app.services.gdrive_dropzone.get_settings", return_value=mock_settings),
            patch("app.services.gdrive_dropzone.list_files", side_effect=fake_list_files),
            patch("app.services.gdrive_dropzone.download_file", side_effect=fake_download_file),
            patch("app.services.gdrive_dropzone.move_file", side_effect=fake_move_file),
        ):
            async with async_session_factory() as db:
                tenant = Tenant(
                    id=uuid.uuid4(),
                    name="GDrive Idempotent Test Tenant",
                    industry="Test",
                )
                db.add(tenant)
                await db.commit()
                await db.refresh(tenant)
                tenant_id = tenant.id

            # Lần 1: ingest
            async with async_session_factory() as db:
                c1, inv1, count_skipped1 = await ingest_ready_assets(db, tenant_id=tenant_id)
                await db.commit()

            async with async_session_factory() as db:
                r = await db.execute(
                    select(func.count(ContentAsset.id)).where(ContentAsset.tenant_id == tenant_id)
                )
                count_after_first = r.scalar_one_or_none() or 0

            assert count_after_first >= 1, "Sau lần 1 phải có ít nhất 1 content_asset"
            assert c1 >= 1, "Lần 1 count_ingested phải >= 1"

            # Lần 2: ingest lại cùng tenant (cùng file) – không được 500, count_skipped tăng
            async with async_session_factory() as db:
                c2, inv2, count_skipped2 = await ingest_ready_assets(db, tenant_id=tenant_id)
                await db.commit()

            async with async_session_factory() as db:
                r = await db.execute(
                    select(func.count(ContentAsset.id)).where(ContentAsset.tenant_id == tenant_id)
                )
                count_after_second = r.scalar_one_or_none() or 0

            # Idempotent: số row không tăng sau lần 2
            assert count_after_second == count_after_first, (
                f"Idempotent: số content_assets không được tăng sau lần 2: "
                f"{count_after_first} -> {count_after_second}"
            )
            assert c2 == 0, f"Lần 2 count_ingested phải = 0, got {c2}"
            assert count_skipped2 >= 1, f"Lần 2 count_skipped phải >= 1 (file trùng bỏ qua), got {count_skipped2}"


@pytest.mark.asyncio
async def test_gdrive_ingest_endpoint_double_call_returns_200() -> None:
    """
    Endpoint test: POST /api/gdrive/ingest gọi 2 lần liên tiếp phải luôn 200,
    lần 2 count_skipped >= 1 và tổng row content_assets không tăng.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        media_dir = Path(tmpdir) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        mock_settings = type("Settings", (), {})()
        mock_settings.gdrive_sa_json_path = os.devnull
        mock_settings.gdrive_ready_images_folder_id = "folder_images"
        mock_settings.gdrive_ready_videos_folder_id = None
        mock_settings.gdrive_processed_folder_id = "folder_processed"
        mock_settings.gdrive_rejected_folder_id = "folder_rejected"
        mock_settings.local_media_dir = str(media_dir)
        mock_settings.asset_max_image_mb = 10
        mock_settings.asset_max_video_mb = 200

        def fake_list_files(folder_id: str):
            return MOCK_FILES.copy()

        def fake_download_file(file_id: str, dest_path: str) -> str:
            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
            Path(dest_path).write_bytes(b"fake image content")
            return dest_path

        def fake_move_file(file_id: str, target_folder_id: str) -> None:
            return None

        with (
            patch("app.services.gdrive_dropzone.get_settings", return_value=mock_settings),
            patch("app.services.gdrive_dropzone.list_files", side_effect=fake_list_files),
            patch("app.services.gdrive_dropzone.download_file", side_effect=fake_download_file),
            patch("app.services.gdrive_dropzone.move_file", side_effect=fake_move_file),
        ):
            async with async_session_factory() as db:
                tenant = Tenant(
                    id=uuid.uuid4(),
                    name="GDrive Endpoint Idempotent Tenant",
                    industry="Test",
                )
                db.add(tenant)
                await db.commit()
                await db.refresh(tenant)
                tenant_id = tenant.id

            from app.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {"tenant_id": str(tenant_id)}

                resp1 = await client.post("/api/gdrive/ingest", json=payload)
                assert resp1.status_code == 200, resp1.text
                data1 = resp1.json()
                assert data1.get("count_ingested", 0) >= 1

                resp2 = await client.post("/api/gdrive/ingest", json=payload)
                assert resp2.status_code == 200, resp2.text
                data2 = resp2.json()
                assert data2.get("count_ingested", -1) == 0
                assert data2.get("count_skipped", 0) >= 1

            async with async_session_factory() as db:
                r = await db.execute(
                    select(func.count(ContentAsset.id)).where(ContentAsset.tenant_id == tenant_id)
                )
                total_assets = r.scalar_one_or_none() or 0
                assert total_assets == 1, f"Không được tạo duplicate content_assets, got {total_assets}"
