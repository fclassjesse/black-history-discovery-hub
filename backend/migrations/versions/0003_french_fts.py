"""French full-text search: second generated tsvector ('french' dictionary) on records and record_chunks + GIN indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07

Generated columns backfill themselves, so no re-seed is needed. Queries (app/services/search.py) run the same
websearch query against both dictionaries and fuse the rankings.
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE records ADD COLUMN IF NOT EXISTS search_tsv_fr tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('french', coalesce(title,'')), 'A') ||
            setweight(to_tsvector('french', bhdh_arr_text(creators) || ' ' || bhdh_arr_text(subjects)), 'B') ||
            setweight(to_tsvector('french', coalesce(description,'')), 'C')
        ) STORED
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_search_tsv_fr ON records USING gin (search_tsv_fr)")
    op.execute(
        "ALTER TABLE record_chunks ADD COLUMN IF NOT EXISTS tsv_fr tsvector GENERATED ALWAYS AS (to_tsvector('french', coalesce(text,''))) STORED"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_tsv_fr ON record_chunks USING gin (tsv_fr)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_tsv_fr")
    op.execute("ALTER TABLE record_chunks DROP COLUMN IF EXISTS tsv_fr")
    op.execute("DROP INDEX IF EXISTS ix_records_search_tsv_fr")
    op.execute("ALTER TABLE records DROP COLUMN IF EXISTS search_tsv_fr")
