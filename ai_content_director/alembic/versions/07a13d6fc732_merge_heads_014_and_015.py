"""merge heads 014 and 015

Revision ID: 07a13d6fc732
Revises: 014, 015
Create Date: 2026-02-23
"""

from typing import Sequence, Union


revision: str = "07a13d6fc732"
down_revision: Union[str, Sequence[str], None] = ("014", "015")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
