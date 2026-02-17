"""KB service: CRUD + ILIKE search cho content generator."""
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KbItem

# Giới hạn độ dài KB context inject vào prompt (ký tự)
KB_CONTEXT_MAX_CHARS = 2000


async def create_kb_item(
    db: AsyncSession,
    tenant_id: UUID,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
) -> KbItem:
    """Tạo một mục KB. Caller commit session."""
    item = KbItem(
        tenant_id=tenant_id,
        title=title,
        content=content,
        tags=tags or [],
    )
    db.add(item)
    await db.flush()
    return item


async def bulk_create_kb_items(
    db: AsyncSession,
    tenant_id: UUID,
    items: List[dict],
) -> List[UUID]:
    """
    Bulk tạo nhiều mục KB. items: list of {"title", "content", "tags"}.
    Trả về list id đã tạo.
    """
    ids: List[UUID] = []
    for row in items:
        item = KbItem(
            tenant_id=tenant_id,
            title=row.get("title") or "",
            content=row.get("content") or "",
            tags=row.get("tags") if isinstance(row.get("tags"), list) else [],
        )
        db.add(item)
        await db.flush()
        ids.append(item.id)
    return ids


async def list_kb_items(
    db: AsyncSession,
    tenant_id: UUID,
) -> List[KbItem]:
    """Lấy tất cả KB items của tenant (theo created_at)."""
    q = (
        select(KbItem)
        .where(KbItem.tenant_id == tenant_id)
        .order_by(KbItem.created_at)
    )
    r = await db.execute(q)
    return list(r.scalars().all())


async def query_kb_ilike(
    db: AsyncSession,
    tenant_id: UUID,
    query: str,
    top_k: int = 10,
) -> List[KbItem]:
    """
    Tìm KB items theo query: ILIKE trên title và content.
    Trả về tối đa top_k bản ghi (không sắp xếp relevance).
    """
    pattern = f"%{query.strip()}%"
    q = (
        select(KbItem)
        .where(KbItem.tenant_id == tenant_id)
        .where(or_(KbItem.title.ilike(pattern), KbItem.content.ilike(pattern)))
        .order_by(KbItem.created_at)
        .limit(top_k)
    )
    r = await db.execute(q)
    return list(r.scalars().all())


def build_kb_context_string(
    items: List[KbItem],
    max_chars: int = KB_CONTEXT_MAX_CHARS,
) -> Tuple[str, int, int]:
    """
    Ghép nội dung KB thành một chuỗi để inject vào prompt.
    Returns (context_string, kb_hit_count, kb_chars_used).
    """
    if not items:
        return "", 0, 0
    parts: List[str] = []
    total = 0
    for it in items:
        block = f"[{it.title}]\n{it.content}".strip()
        if total + len(block) + 2 <= max_chars:
            parts.append(block)
            total += len(block) + 2
        else:
            remaining = max_chars - total - 4
            if remaining > 20:
                parts.append(block[:remaining] + "...")
                total = max_chars
            break
    return "\n\n".join(parts), len(items), total
