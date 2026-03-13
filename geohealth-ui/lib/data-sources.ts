/**
 * Centralized data source definitions for attribution and methodology documentation.
 */

export interface DataSource {
  id: string;
  name: string;
  fullName: string;
  provider: string;
  description: string;
  url: string;
  vintage: string;
  updateFrequency: string;
  geography: string;
}

export const DATA_SOURCES: Record<string, DataSource> = {
  census_acs: {
    id: "census_acs",
    name: "Census ACS",
    fullName: "American Community Survey 5-Year Estimates",
    provider: "U.S. Census Bureau",
    description:
      "Demographic, economic, and housing data at the census tract level including income, poverty, insurance coverage, employment, and age distribution.",
    url: "https://www.census.gov/programs-surveys/acs",
    vintage: "2018–2022",
    updateFrequency: "Annual (5-year rolling)",
    geography: "Census tract",
  },
  cdc_places: {
    id: "cdc_places",
    name: "CDC PLACES",
    fullName: "Population Level Analysis and Community Estimates (PLACES)",
    provider: "Centers for Disease Control and Prevention",
    description:
      "Model-based estimates for 36 chronic disease measures at the census tract level, derived from the Behavioral Risk Factor Surveillance System (BRFSS).",
    url: "https://www.cdc.gov/places/",
    vintage: "2023 Release",
    updateFrequency: "Annual",
    geography: "Census tract",
  },
  cdc_svi: {
    id: "cdc_svi",
    name: "CDC/ATSDR SVI",
    fullName: "Social Vulnerability Index",
    provider: "CDC/Agency for Toxic Substances and Disease Registry",
    description:
      "Percentile-ranked index across four themes: Socioeconomic Status, Household Characteristics, Racial/Ethnic Minority Status, and Housing Type/Transportation. Used to identify communities most at risk during public health emergencies.",
    url: "https://www.atsdr.cdc.gov/placeandhealth/svi/",
    vintage: "2022",
    updateFrequency: "Biennial",
    geography: "Census tract",
  },
  epa_ejscreen: {
    id: "epa_ejscreen",
    name: "EPA EJScreen",
    fullName: "Environmental Justice Screening and Mapping Tool",
    provider: "U.S. Environmental Protection Agency",
    description:
      "Environmental and demographic indicators including PM2.5, ozone, lead paint, air toxics cancer risk, traffic proximity, and Superfund site proximity.",
    url: "https://www.epa.gov/ejscreen",
    vintage: "2024",
    updateFrequency: "Annual",
    geography: "Census tract / block group",
  },
  nppes_npi: {
    id: "nppes_npi",
    name: "NPPES NPI",
    fullName: "National Plan and Provider Enumeration System",
    provider: "Centers for Medicare & Medicaid Services (CMS)",
    description:
      "Registry of all healthcare providers in the U.S. Used to identify primary care physicians (PCPs), FQHCs, urgent care centers, and rural health clinics by taxonomy code and practice location.",
    url: "https://nppes.cms.hhs.gov/",
    vintage: "Monthly updates",
    updateFrequency: "Monthly",
    geography: "Provider address (geocoded to tract)",
  },
  hrsa_hpsa: {
    id: "hrsa_hpsa",
    name: "HRSA HPSA",
    fullName: "Health Professional Shortage Area Designations",
    provider: "Health Resources and Services Administration",
    description:
      "Federal designation identifying geographic areas, populations, or facilities with shortages of primary care, dental, or mental health providers. HPSA scores range 0–25, with higher scores indicating greater shortage.",
    url: "https://data.hrsa.gov/topics/health-workforce/shortage-areas",
    vintage: "2024",
    updateFrequency: "Quarterly",
    geography: "County / service area",
  },
  census_cbp: {
    id: "census_cbp",
    name: "Census CBP",
    fullName: "County Business Patterns",
    provider: "U.S. Census Bureau",
    description:
      "Annual data on business establishments, employment, and payroll by county and industry (NAICS). Used to assess employer landscape for DPC partnership potential—specifically mid-size employers (10–249 employees) and average wages.",
    url: "https://www.census.gov/programs-surveys/cbp.html",
    vintage: "2022",
    updateFrequency: "Annual",
    geography: "County",
  },
  census_tiger: {
    id: "census_tiger",
    name: "TIGER/Line",
    fullName: "Topologically Integrated Geographic Encoding and Referencing",
    provider: "U.S. Census Bureau",
    description:
      "Geographic boundary shapefiles for census tracts, counties, and states. Used for map rendering and spatial operations.",
    url: "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
    vintage: "2022",
    updateFrequency: "Annual",
    geography: "Census tract",
  },
};

/**
 * Maps each UI component/card to its underlying data sources.
 */
export const COMPONENT_SOURCES: Record<string, string[]> = {
  demographics: ["census_acs"],
  svi: ["cdc_svi"],
  health_outcomes: ["cdc_places"],
  environmental: ["epa_ejscreen"],
  trends: ["census_acs"],
  comparison: ["census_acs", "cdc_places", "cdc_svi"],
  dpc_demand: ["census_acs", "cdc_places", "cdc_svi"],
  dpc_supply_gap: ["nppes_npi", "hrsa_hpsa"],
  dpc_affordability: ["census_acs"],
  dpc_employer: ["census_cbp"],
  dpc_competition: ["nppes_npi"],
  dpc_composite: ["census_acs", "cdc_places", "cdc_svi", "nppes_npi", "hrsa_hpsa", "census_cbp"],
  providers: ["nppes_npi"],
  map_boundaries: ["census_tiger"],
};

export function getSourcesForComponent(componentKey: string): DataSource[] {
  const ids = COMPONENT_SOURCES[componentKey] ?? [];
  return ids.map((id) => DATA_SOURCES[id]).filter(Boolean);
}
