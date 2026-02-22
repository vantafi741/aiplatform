#!/usr/bin/env python3
"""
Script kiểm tra idempotent: gọi POST /api/gdrive/ingest 2 lần với cùng tenant_id,
sau đó assert số lượng content_assets không tăng (và lần 2 count_ingested=0).

Cách chạy (từ thư mục ai_content_director, server đang chạy):
  python scripts/gdrive_ingest_idempotent_check.py <base_url> <tenant_id>

Ví dụ:
  python scripts/gdrive_ingest_idempotent_check.py http://localhost:8000 550e8400-e29b-41d4-a716-446655440000
"""
import argparse
import sys

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Gọi ingest 2 lần, assert assets count ổn định")
    parser.add_argument("base_url", help="Base URL API (vd: http://localhost:8000)")
    parser.add_argument("tenant_id", help="Tenant UUID")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    tenant_id = args.tenant_id

    with httpx.Client(timeout=60.0) as client:
        # Lần 1
        r1 = client.post(f"{base}/api/gdrive/ingest", json={"tenant_id": tenant_id})
        r1.raise_for_status()
        d1 = r1.json()
        count_ingested_1 = d1.get("count_ingested", 0)

        # Đếm assets sau lần 1
        list1 = client.get(f"{base}/api/assets", params={"tenant_id": tenant_id})
        list1.raise_for_status()
        assets_1 = list1.json().get("assets", [])
        n1 = len(assets_1)

        # Lần 2
        r2 = client.post(f"{base}/api/gdrive/ingest", json={"tenant_id": tenant_id})
        r2.raise_for_status()
        d2 = r2.json()
        count_ingested_2 = d2.get("count_ingested", 0)
        skipped_2 = d2.get("skipped_existing", 0)

        # Đếm assets sau lần 2
        list2 = client.get(f"{base}/api/assets", params={"tenant_id": tenant_id})
        list2.raise_for_status()
        assets_2 = list2.json().get("assets", [])
        n2 = len(assets_2)

    # Assert idempotent
    ok = True
    if n2 != n1:
        print(f"FAIL: Số assets thay đổi sau lần 2: {n1} -> {n2}")
        ok = False
    if count_ingested_2 != 0:
        print(f"FAIL: Lần 2 count_ingested phải = 0, got {count_ingested_2}")
        ok = False

    if ok:
        print(f"OK: Idempotent. Lần 1 ingested={count_ingested_1}, assets={n1}; lần 2 ingested={count_ingested_2}, skipped_existing={skipped_2}, assets={n2}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
