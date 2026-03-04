"""Add npi_providers table for individual provider map pins.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-04 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "npi_providers",
        sa.Column(
            "npi", sa.String(10), primary_key=True,
            comment="National Provider Identifier",
        ),
        sa.Column(
            "entity_type", sa.String(1), nullable=False,
            comment="1=individual, 2=organization",
        ),
        sa.Column("provider_name", sa.Text(), nullable=False),
        sa.Column("credential", sa.String(50), nullable=True),
        sa.Column("gender", sa.String(1), nullable=True),
        sa.Column(
            "primary_taxonomy", sa.String(15), nullable=False,
            comment="Primary taxonomy code",
        ),
        sa.Column("taxonomy_description", sa.Text(), nullable=True),
        sa.Column(
            "provider_type", sa.String(30), nullable=False,
            comment="pcp|fqhc|urgent_care|rural_health_clinic|primary_care_clinic|community_health_center",
        ),
        sa.Column("practice_address", sa.Text(), nullable=True),
        sa.Column("practice_city", sa.String(100), nullable=True),
        sa.Column("practice_state", sa.String(2), nullable=False),
        sa.Column("practice_zip", sa.String(5), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("is_fqhc", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "tract_fips", sa.String(11), nullable=True,
            comment="Census tract FIPS from geocoder",
        ),
        sa.Column("geom", Geometry("POINT", srid=4326), nullable=True),
    )
    op.create_index(
        "ix_npi_providers_geom", "npi_providers", ["geom"],
        postgresql_using="gist",
    )
    op.create_index("ix_npi_providers_state", "npi_providers", ["practice_state"])
    op.create_index("ix_npi_providers_type", "npi_providers", ["provider_type"])
    op.create_index("ix_npi_providers_tract", "npi_providers", ["tract_fips"])


def downgrade() -> None:
    op.drop_index("ix_npi_providers_tract", table_name="npi_providers")
    op.drop_index("ix_npi_providers_type", table_name="npi_providers")
    op.drop_index("ix_npi_providers_state", table_name="npi_providers")
    op.drop_index(
        "ix_npi_providers_geom", table_name="npi_providers",
        postgresql_using="gist",
    )
    op.drop_table("npi_providers")
