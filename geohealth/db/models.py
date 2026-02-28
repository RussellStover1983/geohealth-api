from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TractProfile(Base):
    __tablename__ = "tract_profiles"
    __table_args__ = (
        Index("ix_tract_profiles_geom", "geom", postgresql_using="gist"),
    )

    geoid = Column(String(11), primary_key=True, comment="Full FIPS: state(2)+county(3)+tract(6)")
    state_fips = Column(String(2), nullable=False, index=True)
    county_fips = Column(String(3), nullable=False)
    tract_code = Column(String(6), nullable=False)
    name = Column(Text, nullable=True)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)

    # ACS demographics (nullable — populated in later phases)
    total_population = Column(Integer, nullable=True)
    median_household_income = Column(Float, nullable=True)
    poverty_rate = Column(Float, nullable=True)
    uninsured_rate = Column(Float, nullable=True)
    unemployment_rate = Column(Float, nullable=True)
    median_age = Column(Float, nullable=True)

    # SVI themes (JSONB for flexibility)
    svi_themes = Column(JSONB, nullable=True, comment="CDC/ATSDR SVI theme scores")

    # PLACES health measures (JSONB)
    places_measures = Column(JSONB, nullable=True, comment="CDC PLACES health outcome measures")

    # SDOH composite
    sdoh_index = Column(Float, nullable=True, comment="Composite SDOH vulnerability index")

    # Historical trend data (year-keyed ACS snapshots)
    trends = Column(JSONB, nullable=True, comment="Year-keyed historical ACS snapshots")

    # EPA environmental data
    epa_data = Column(JSONB, nullable=True, comment="EPA EJScreen environmental indicators")

    def __repr__(self) -> str:
        return f"<TractProfile geoid={self.geoid}>"


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, nullable=False, comment="Callback URL for webhook delivery")
    api_key_hash = Column(String(64), nullable=False, index=True, comment="SHA-256 hash of owning API key")
    events = Column(JSONB, nullable=False, comment="List of subscribed event types")
    filters = Column(JSONB, nullable=True, comment="Optional filters: state_fips, geoids, thresholds")
    secret = Column(String(64), nullable=True, comment="Shared secret for HMAC signature verification")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<WebhookSubscription id={self.id} url={self.url}>"
