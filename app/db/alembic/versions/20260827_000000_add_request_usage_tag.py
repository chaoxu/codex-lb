"""add request usage tag

Revision ID: 20260827_000000_add_request_usage_tag
Revises: 20260816_000000_add_model_source_embeddings
Create Date: 2026-08-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260827_000000_add_request_usage_tag"
down_revision = "20260816_000000_add_model_source_embeddings"
branch_labels = None
depends_on = None

_TABLE = "request_logs"
_COLUMN = "usage_tag"
_INDEX = "idx_logs_usage_tag"


def _columns(bind) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(_TABLE)}


def _indexes(bind) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if _COLUMN not in _columns(bind):
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=128), nullable=True))
    if _INDEX not in _indexes(bind):
        op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    bind = op.get_bind()
    if _INDEX in _indexes(bind):
        op.drop_index(_INDEX, table_name=_TABLE)
    if _COLUMN in _columns(bind):
        op.drop_column(_TABLE, _COLUMN)
