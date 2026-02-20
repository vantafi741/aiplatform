"""
Chuẩn hóa query param boolean: tránh string "false" bị coi là truthy.
FastAPI có thể nhận ?ai=false dưới dạng str "false"; if ai: sẽ thành True.
"""


def ensure_bool_query(value: bool | str | None) -> bool:
    """
    Chuyển giá trị query (bool hoặc str) sang bool thật.
    Chỉ trả về True khi value là True hoặc str "true"/"1"/"yes" (không phân biệt hoa thường).
    "false", "0", "no", "", None => False.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in ("true", "1", "yes")
