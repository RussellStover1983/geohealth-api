from geoalchemy2 import Geometry
from sqlalchemy import Column, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TractProfile(Base):
    __tablename__ = "tract_profiles"

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

    def __repr__(self) -> str:
        return f"<TractProfile geoid={self.geoid}>"
