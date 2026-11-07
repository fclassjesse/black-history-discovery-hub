"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-06
"""
from alembic import op

from app.db import Base
from app.models import SQL_HELPERS
import app.models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for stmt in SQL_HELPERS:
        op.execute(stmt)
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    op.execute("DROP FUNCTION IF EXISTS bhdh_arr_text(text[])")
