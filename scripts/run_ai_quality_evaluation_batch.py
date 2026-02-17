"""
AI Quality Evaluation Batch: gọi planner + content generate, export JSON, validate hashtag/CTA.
Dùng tenant_id có sẵn (env TENANT_ID hoặc tham số dòng lệnh). Không tạo tenant mới.

Chạy (server phải đang chạy tại API_BASE_URL, mặc định http://localhost:8000):
  set TENANT_ID=<uuid>
  python run_ai_quality_evaluation_batch.py
  hoặc: python run_ai_quality_evaluation_batch.py <tenant_id>

Tạo ra: evaluation_planner_7d.json, evaluation_content_6.json (cùng thư mục script).
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PLANNER_OUT = os.path.join(OUT_DIR, "evaluation_planner_7d.json")
CONTENT_OUT = os.path.join(OUT_DIR, "evaluation_content_6.json")


def request(method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    url = BASE_URL + path
    if params:
        q = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{q}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err = json.loads(body)
            detail = err.get("detail", body)
        except Exception:
            detail = body
        raise SystemExit(f"HTTP {e.code}: {detail}")
    except Exception as e:
        raise SystemExit(f"Request failed: {e}")


def count_hashtags(hashtags_str: str) -> int:
    """Đếm số hashtag = số token cách nhau bởi space (phải đúng 6)."""
    if not (hashtags_str or hashtags_str.strip()):
        return 0
    tokens = [t for t in hashtags_str.strip().split() if t]
    return len(tokens)


def extract_cta_like(caption: str) -> str:
    """Lấy phần giống CTA: câu cuối hoặc 25 ký tự cuối (đã trim)."""
    if not (caption or caption.strip()):
        return ""
    s = caption.strip()
    for sep in [". ", "! ", "? ", "\n"]:
        if sep in s:
            last = s.rsplit(sep, 1)[-1].strip()
            if len(last) >= 5:
                return last
    return s[-25:].strip() if len(s) >= 25 else s


def main() -> None:
    tenant_id = os.environ.get("TENANT_ID") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not tenant_id:
        print("Usage: TENANT_ID=<uuid> python run_ai_quality_evaluation_batch.py")
        print("   or: python run_ai_quality_evaluation_batch.py <tenant_id>")
        sys.exit(1)

    print("=== AI Quality Evaluation Batch ===")
    print(f"Base URL: {BASE_URL}")
    print(f"Tenant ID: {tenant_id}")
    print()

    # 1) Planner: force=true, ai=true, days=7
    print("1) POST /planner/generate?force=true&ai=true (days=7)")
    planner_body = {"tenant_id": tenant_id, "days": 7}
    planner_resp = request(
        "POST",
        "/planner/generate",
        body=planner_body,
        params={"force": "true", "ai": "true"},
    )
    with open(PLANNER_OUT, "w", encoding="utf-8") as f:
        json.dump(planner_resp, f, ensure_ascii=False, indent=2)
    print(f"   Saved: {PLANNER_OUT}")

    # 2) Content samples: force=true, ai=true, count=6
    print("2) POST /content/generate-samples?force=true&ai=true (count=6)")
    content_body = {"tenant_id": tenant_id, "count": 6}
    content_resp = request(
        "POST",
        "/content/generate-samples",
        body=content_body,
        params={"force": "true", "ai": "true"},
    )
    with open(CONTENT_OUT, "w", encoding="utf-8") as f:
        json.dump(content_resp, f, ensure_ascii=False, indent=2)
    print(f"   Saved: {CONTENT_OUT}")
    print()

    # 3) Console summary (structured)
    items = content_resp.get("items") or []
    print("---- PLANNER SUMMARY ----")
    print(f"used_ai: {planner_resp.get('used_ai')}")
    print(f"used_fallback: {planner_resp.get('used_fallback')}")
    print(f"model: {planner_resp.get('model')}")
    print(f"number of items: {len(planner_resp.get('items') or [])}")
    print()
    print("---- CONTENT SUMMARY ----")
    print(f"used_ai: {content_resp.get('used_ai')}")
    print(f"used_fallback: {content_resp.get('used_fallback')}")
    print(f"model: {content_resp.get('model')}")
    print(f"number of items: {len(items)}")
    if items:
        scores = [it.get("confidence_score") for it in items]
        print(f"confidence scores list: {scores}")
    print()

    # 4) Validate: exactly 6 hashtags per content post
    errors = []
    for i, it in enumerate(items):
        hashtags_str = it.get("hashtags") or ""
        n = count_hashtags(hashtags_str)
        if n != 6:
            errors.append(f"[Item {i+1}] Expected 6 hashtags, got {n}: {hashtags_str!r}")

    # 5) Validate: no CTA repetition across posts
    captions = [it.get("caption") or "" for it in items]
    ctas = [extract_cta_like(c) for c in captions]
    seen = {}
    for i, cta in enumerate(ctas):
        if not cta:
            continue
        cta_norm = re.sub(r"\s+", " ", cta.strip()).lower()
        if len(cta_norm) < 4:
            continue
        if cta_norm in seen:
            errors.append(f"[CTA repeat] Post {seen[cta_norm]+1} and Post {i+1} have same CTA: {cta!r}")
        seen[cta_norm] = i

    if errors:
        print("---- VALIDATION ERRORS ----")
        for e in errors:
            if "hashtag" in e.lower():
                print(f"  - hashtag count mismatch: {e}")
            elif "CTA" in e:
                print(f"  - CTA repetition detected: {e}")
            else:
                print(f"  - {e}")
    else:
        print("---- VALIDATION ---- OK (6 hashtags per post, no CTA repetition)")

    print()
    print("Done. Files: " + PLANNER_OUT + ", " + CONTENT_OUT)


if __name__ == "__main__":
    main()
