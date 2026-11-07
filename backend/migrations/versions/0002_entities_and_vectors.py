"""entities, work keys, description passages, search log, vector indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LOCAL_MODEL = "BAAI/bge-small-en-v1.5"
LOCAL_DIM = 384


def upgrade() -> None:
    op.execute("ALTER TABLE records ADD COLUMN IF NOT EXISTS people text[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE records ADD COLUMN IF NOT EXISTS places text[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE records ADD COLUMN IF NOT EXISTS communities text[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE records ADD COLUMN IF NOT EXISTS work_keys text[] NOT NULL DEFAULT '{}'")
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_people ON records USING gin (people)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_places ON records USING gin (places)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_communities ON records USING gin (communities)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_work_keys ON records USING gin (work_keys)")

    op.execute("ALTER TABLE record_chunks ADD COLUMN IF NOT EXISTS kind varchar(16) NOT NULL DEFAULT 'page'")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS search_log (
            id uuid PRIMARY KEY,
            created_at timestamptz NOT NULL DEFAULT now(),
            kind varchar(16) NOT NULL DEFAULT 'search',
            query text NOT NULL,
            mode varchar(16),
            filters jsonb NOT NULL DEFAULT '{}'::jsonb,
            result_count integer NOT NULL DEFAULT 0,
            took_ms integer NOT NULL DEFAULT 0,
            abstained boolean
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_search_log_created ON search_log (created_at)")

    # pgvector HNSW indexes. The embedding columns have no fixed dimension (provider switch), so the index is an
    # expression index on a cast, partial per model — the documented pattern for mixed-dimension tables.
    # Queries must use the same expression: (embedding::vector(N)) <=> ... AND embedding_model = '<model>'.
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_records_embedding_hnsw_local ON records USING hnsw ((embedding::vector({LOCAL_DIM})) vector_cosine_ops) "
        f"WHERE embedding_model = '{LOCAL_MODEL}'"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw_local ON record_chunks USING hnsw ((embedding::vector({LOCAL_DIM})) vector_cosine_ops) "
        f"WHERE embedding_model = '{LOCAL_MODEL}'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw_local")
    op.execute("DROP INDEX IF EXISTS ix_records_embedding_hnsw_local")
    op.execute("DROP TABLE IF EXISTS search_log")
    op.execute("ALTER TABLE record_chunks DROP COLUMN IF EXISTS kind")
    for col in ("people", "places", "communities", "work_keys"):
        op.execute(f"ALTER TABLE records DROP COLUMN IF EXISTS {col}")
