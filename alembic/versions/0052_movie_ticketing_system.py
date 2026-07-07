"""create movie ticketing system tables

Revision ID: 0052_movie_ticketing_system
Revises: 0051_product_clone_fields
Create Date: 2026-07-07 12:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0052_movie_ticketing_system"
down_revision = "0051_product_clone_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. movies table
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("movie_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("director", sa.String(length=64), nullable=False),
        sa.Column("actors", sa.Text(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("movie_type", sa.String(length=64), nullable=False),
        sa.Column("release_date", sa.String(length=32), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("introduction", sa.Text(), nullable=True),
        sa.Column("poster", sa.String(length=512), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'showing'")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_movies_movie_id", "movies", ["movie_id"], unique=True)
    op.create_index("ix_movies_status", "movies", ["status"])

    # 2. cinemas table
    op.create_table(
        "cinemas",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("cinema_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("logo", sa.String(length=512), nullable=True),
        sa.Column("address", sa.String(length=256), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_cinemas_cinema_id", "cinemas", ["cinema_id"], unique=True)
    op.create_index("ix_cinemas_city", "cinemas", ["city"])

    # 3. movie_halls table
    op.create_table(
        "movie_halls",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("hall_id", sa.String(length=64), nullable=False),
        sa.Column("cinema_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("hall_type", sa.String(length=32), nullable=False, server_default=sa.text("'普通'")),
        sa.Column(
            "seat_layout",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_movie_halls_hall_id", "movie_halls", ["hall_id"], unique=True)
    op.create_index("ix_movie_halls_cinema_id", "movie_halls", ["cinema_id"])

    # 4. movie_showtimes table
    op.create_table(
        "movie_showtimes",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("showtime_id", sa.String(length=64), nullable=False),
        sa.Column("movie_id", sa.String(length=64), nullable=False),
        sa.Column("cinema_id", sa.String(length=64), nullable=False),
        sa.Column("hall_id", sa.String(length=64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("original_price", sa.Integer(), nullable=False),
        sa.Column("language_version", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_movie_showtimes_showtime_id", "movie_showtimes", ["showtime_id"], unique=True)
    op.create_index("ix_movie_showtimes_movie_id", "movie_showtimes", ["movie_id"])
    op.create_index("ix_movie_showtimes_cinema_id", "movie_showtimes", ["cinema_id"])
    op.create_index("ix_movie_showtimes_hall_id", "movie_showtimes", ["hall_id"])

    # 5. movie_ticket_orders table
    op.create_table(
        "movie_ticket_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("showtime_id", sa.String(length=64), nullable=False),
        sa.Column(
            "seats",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("price_paid", sa.Integer(), nullable=False),
        sa.Column("pay_status", sa.String(length=32), nullable=False, server_default=sa.text("'pending_pay'")),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ticket_code", sa.String(length=64), nullable=True),
        sa.Column("expire_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_movie_ticket_orders_order_id", "movie_ticket_orders", ["order_id"], unique=True)
    op.create_index("ix_movie_ticket_orders_user_id", "movie_ticket_orders", ["user_id"])
    op.create_index("ix_movie_ticket_orders_showtime_id", "movie_ticket_orders", ["showtime_id"])
    op.create_index("ix_movie_ticket_orders_pay_status", "movie_ticket_orders", ["pay_status"])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table("movie_ticket_orders")
    op.drop_table("movie_showtimes")
    op.drop_table("movie_halls")
    op.drop_table("cinemas")
    op.drop_table("movies")
