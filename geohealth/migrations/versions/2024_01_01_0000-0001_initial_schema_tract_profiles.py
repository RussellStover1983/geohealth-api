"""initial schema tract_profiles

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "tract_profiles",
        sa.Column("geoid", sa.String(11), primary_key=True,
                  comment="Full FIPS: state(2)+county(3)+tract(6)"),
        sa.Column("state_fips", sa.String(2), nullable=False),
        sa.Column("county_fips", sa.String(3), nullable=False),
        sa.Column("tract_code", sa.String(6), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("geom",
                  geoalchemy2.types.Geometry(
                      geometry_type="MULTIPOLYGON", srid=4326,
                      from_text="ST_GeomFromEWKT",
                      name="geometry",
                  ),
                  nullable=True),
        # ACS demographics
        sa.Column("total_population", sa.Integer(), nullable=True),
        sa.Column("median_household_income", sa.Float(), nullable=True),
        sa.Column("poverty_rate", sa.Float(), nullable=True),
        sa.Column("uninsured_rate", sa.Float(), nullable=True),
        sa.Column("unemployment_rate", sa.Float(), nullable=True),
        sa.Column("median_age", sa.Float(), nullable=True),
        # JSONB data sources
        sa.Column("svi_themes", postgresql.JSONB(), nullable=True,
                  comment="CDC/ATSDR SVI theme scores"),
        sa.Column("places_measures", postgresql.JSONB(), nullable=True,
                  comment="CDC PLACES health outcome measures"),
        # Composite index
        sa.Column("sdoh_index", sa.Float(), nullable=True,
                  comment="Composite SDOH vulnerability index"),
    )

    op.create_index("ix_tract_profiles_state_fips", "tract_profiles", ["state_fips"])
    op.create_index("ix_tract_profiles_geom", "tract_profiles", ["geom"],
                    postgresql_using="gist")


def downgrade() -> None:
    op.drop_index("ix_tract_profiles_geom", table_name="tract_profiles",
                  postgresql_using="gist")
    op.drop_index("ix_tract_profiles_state_fips", table_name="tract_profiles")
    op.drop_table("tract_profiles")
