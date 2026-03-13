"use client";

import Link from "next/link";
import { ArrowLeft, ExternalLink, Database, BookOpen, Github, Scale } from "lucide-react";
import { Logo } from "@/components/shared/Logo";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { DATA_SOURCES, COMPONENT_SOURCES } from "@/lib/data-sources";

const DPC_DIMENSIONS = [
  {
    name: "Demand",
    weight: "25%",
    description:
      "Measures the need for primary care services in the area. Higher uninsured rates, chronic disease burden, and social vulnerability indicate greater demand for accessible, affordable care models like DPC.",
    indicators: [
      { name: "Uninsured Rate", weight: "25%", source: "Census ACS", direction: "Higher = more demand" },
      { name: "Chronic Disease Burden", weight: "25%", source: "CDC PLACES", direction: "Higher = more demand" },
      { name: "Working-Age Population", weight: "15%", source: "Census ACS", direction: "Larger = bigger market" },
      { name: "SVI Socioeconomic Theme", weight: "15%", source: "CDC/ATSDR SVI", direction: "Higher = more need" },
    ],
  },
  {
    name: "Affordability",
    weight: "20%",
    description:
      "Evaluates the population's ability to pay for DPC membership (typically $75–$150/month). Higher incomes, lower housing burden, and stronger employment indicate more capacity to subscribe.",
    indicators: [
      { name: "Median Household Income", weight: "35%", source: "Census ACS", direction: "Higher = more ability to pay" },
      { name: "DPC as % of Income", weight: "30%", source: "Census ACS (derived)", direction: "Lower = more affordable" },
      { name: "Employment Rate", weight: "20%", source: "Census ACS", direction: "Higher = more stable income" },
      { name: "Housing Cost Burden", weight: "15%", source: "Census ACS", direction: "Lower = more disposable income" },
    ],
  },
  {
    name: "Supply Gap",
    weight: "25%",
    description:
      "Identifies areas with insufficient primary care infrastructure. Fewer PCPs, HPSA designations, and limited safety-net facilities signal opportunities for new DPC practices.",
    indicators: [
      { name: "PCP per 100k Population", weight: "40%", source: "NPPES NPI", direction: "Lower = more opportunity" },
      { name: "HPSA Score", weight: "35%", source: "HRSA HPSA", direction: "Higher = greater shortage" },
      { name: "FQHC Presence", weight: "25%", source: "NPPES NPI", direction: "Fewer = less safety-net coverage" },
    ],
  },
  {
    name: "Employer",
    weight: "20%",
    description:
      "Assesses the local business landscape for employer-sponsored DPC partnerships. Mid-size employers (10–249 employees) are the primary target for DPC group contracts.",
    indicators: [
      { name: "Target Establishment %", weight: "40%", source: "Census CBP", direction: "More mid-size = better" },
      { name: "Average Annual Wage", weight: "35%", source: "Census CBP", direction: "Higher = can afford DPC benefit" },
      { name: "Total Establishments", weight: "25%", source: "Census CBP", direction: "More = more prospects" },
    ],
  },
  {
    name: "Competition",
    weight: "10%",
    description:
      "Evaluates the competitive landscape. Areas with fewer competing facilities (FQHCs, urgent care, rural health clinics) and lower PCP density represent less saturated markets.",
    indicators: [
      { name: "Competing Facility Count", weight: "50%", source: "NPPES NPI", direction: "Fewer = less competition" },
      { name: "PCP Density", weight: "50%", source: "NPPES NPI", direction: "Lower = less saturation" },
    ],
  },
];

function DataSourceCard({ sourceId }: { sourceId: string }) {
  const source = DATA_SOURCES[sourceId];
  if (!source) return null;

  // Find which components use this source
  const usedBy = Object.entries(COMPONENT_SOURCES)
    .filter(([, ids]) => ids.includes(sourceId))
    .map(([key]) => key.replace(/_/g, " ").replace(/\bdpc\b/g, "DPC"));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-sm">
          <span>{source.fullName}</span>
          <Badge variant="secondary" className="text-[10px] shrink-0 ml-2">
            {source.vintage}
          </Badge>
        </CardTitle>
        <p className="text-xs text-stone-500">{source.provider}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs leading-relaxed text-stone-600">{source.description}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-stone-400">
          <span>Updates: {source.updateFrequency}</span>
          <span>Geography: {source.geography}</span>
        </div>
        {usedBy.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {usedBy.map((component) => (
              <Badge key={component} variant="secondary" className="text-[9px] capitalize">
                {component}
              </Badge>
            ))}
          </div>
        )}
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-teal-600 hover:text-teal-700 hover:underline"
        >
          Official source <ExternalLink className="h-3 w-3" />
        </a>
      </CardContent>
    </Card>
  );
}

export default function MethodologyPage() {
  return (
    <div className="min-h-screen bg-stone-50">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-white">
        <div className="mx-auto flex h-14 max-w-4xl items-center gap-4 px-4">
          <Logo size="sm" />
          <Separator orientation="vertical" className="h-6" />
          <h1 className="text-sm font-semibold text-stone-900">Data Sources &amp; Methodology</h1>
          <div className="ml-auto">
            <Link href="/">
              <Button variant="ghost" size="sm" className="gap-1.5 text-xs">
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to Explorer
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8 space-y-12">
        {/* Introduction */}
        <section>
          <p className="text-sm leading-relaxed text-stone-600 max-w-prose">
            GeoHealth SDOH Explorer aggregates federal public health, demographic, and environmental
            datasets to provide census-tract-level intelligence. This page documents every data
            source, how scores are computed, and the limitations of the analysis. All data is sourced
            from U.S. government agencies and is publicly available.
          </p>
        </section>

        {/* Data Sources */}
        <section>
          <div className="flex items-center gap-2 mb-6">
            <Database className="h-5 w-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-stone-900">Data Sources</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {Object.keys(DATA_SOURCES).map((id) => (
              <DataSourceCard key={id} sourceId={id} />
            ))}
          </div>
        </section>

        <Separator />

        {/* SDOH Index Methodology */}
        <section>
          <div className="flex items-center gap-2 mb-6">
            <Scale className="h-5 w-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-stone-900">SDOH Index</h2>
          </div>
          <Card>
            <CardContent className="pt-6 space-y-3">
              <p className="text-xs leading-relaxed text-stone-600">
                The SDOH Index (0–1) is a composite vulnerability score combining poverty rate,
                uninsured rate, unemployment rate, and CDC SVI percentile rankings. Higher values
                indicate greater social determinant burden. The index is computed server-side using
                min-max normalization across loaded tracts and equal weighting of components.
              </p>
              <div className="flex gap-4 text-[10px] text-stone-400">
                <span>Range: 0 (least vulnerable) – 1 (most vulnerable)</span>
                <span>Sources: Census ACS, CDC/ATSDR SVI</span>
              </div>
            </CardContent>
          </Card>
        </section>

        <Separator />

        {/* DPC Market Fit Methodology */}
        <section>
          <div className="flex items-center gap-2 mb-6">
            <BookOpen className="h-5 w-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-stone-900">DPC Market Fit Scoring</h2>
          </div>

          <Card className="mb-6">
            <CardContent className="pt-6 space-y-4">
              <p className="text-xs leading-relaxed text-stone-600">
                The DPC (Direct Primary Care) Market Fit score estimates the geographic viability
                for Direct Primary Care practices. DPC is a membership-based primary care model
                where patients pay a monthly fee (typically $75–$150) for comprehensive primary care
                without insurance billing. The composite score (0–100) is a weighted average of five
                dimensions, each scored independently using min-max normalization against national
                reference ranges.
              </p>
              <div className="grid grid-cols-4 gap-3 text-center">
                {(["WEAK", "MODERATE", "STRONG", "EXCELLENT"] as const).map((cat) => {
                  const ranges: Record<string, string> = {
                    WEAK: "0–39",
                    MODERATE: "40–59",
                    STRONG: "60–79",
                    EXCELLENT: "80–100",
                  };
                  const colors: Record<string, string> = {
                    WEAK: "bg-red-50 border-red-200 text-red-700",
                    MODERATE: "bg-amber-50 border-amber-200 text-amber-700",
                    STRONG: "bg-blue-50 border-blue-200 text-blue-700",
                    EXCELLENT: "bg-emerald-50 border-emerald-200 text-emerald-700",
                  };
                  return (
                    <div key={cat} className={`rounded-lg border p-2 ${colors[cat]}`}>
                      <p className="text-xs font-semibold">{cat}</p>
                      <p className="text-[10px]">{ranges[cat]}</p>
                    </div>
                  );
                })}
              </div>
              <p className="text-[10px] text-stone-400">
                Data completeness is tracked per dimension. When completeness is below 100%, the
                score reflects only available indicators, and competition scores are capped at 70 to
                prevent inflated ratings.
              </p>
            </CardContent>
          </Card>

          {/* Dimension Details */}
          <div className="space-y-4">
            {DPC_DIMENSIONS.map((dim) => (
              <Card key={dim.name}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span>{dim.name}</span>
                    <Badge variant="secondary" className="text-[10px]">
                      Weight: {dim.weight}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-xs leading-relaxed text-stone-600">{dim.description}</p>
                  <div className="overflow-hidden rounded-lg border border-stone-200">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-stone-50">
                          <th className="px-3 py-1.5 text-left font-medium text-stone-500">Indicator</th>
                          <th className="px-3 py-1.5 text-left font-medium text-stone-500">Weight</th>
                          <th className="px-3 py-1.5 text-left font-medium text-stone-500">Source</th>
                          <th className="px-3 py-1.5 text-left font-medium text-stone-500">Direction</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dim.indicators.map((ind) => (
                          <tr key={ind.name} className="border-t border-stone-100">
                            <td className="px-3 py-1.5 text-stone-700">{ind.name}</td>
                            <td className="px-3 py-1.5 text-stone-500">{ind.weight}</td>
                            <td className="px-3 py-1.5 text-stone-500">{ind.source}</td>
                            <td className="px-3 py-1.5 text-stone-400">{ind.direction}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <Separator />

        {/* Health Outcomes */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="h-5 w-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-stone-900">Health Outcomes Benchmarking</h2>
          </div>
          <Card>
            <CardContent className="pt-6 space-y-3">
              <p className="text-xs leading-relaxed text-stone-600">
                Health outcome measures from CDC PLACES are benchmarked against national averages.
                Each tract value is compared to its national benchmark using a ratio. Values within
                85–115% of the benchmark are marked moderate (amber). Values below 85% are marked
                favorable (green), and above 115% are marked as elevated (red). For preventive
                measures (routine checkups, dental visits), the comparison is inverted—higher is better.
              </p>
              <p className="text-[10px] text-stone-400">
                CDC PLACES estimates are model-based using BRFSS data and should be interpreted as
                estimates, not direct measurements. Small-area estimates may have wider confidence intervals
                in low-population tracts.
              </p>
            </CardContent>
          </Card>
        </section>

        <Separator />

        {/* Limitations */}
        <section>
          <h2 className="text-lg font-semibold text-stone-900 mb-4">Limitations</h2>
          <Card>
            <CardContent className="pt-6">
              <ul className="space-y-2 text-xs leading-relaxed text-stone-600 list-disc list-inside">
                <li>
                  <strong>Geographic coverage:</strong> Currently limited to 4 states (GA, KS, MN, MO)
                  covering 6,784 census tracts. National coverage is planned.
                </li>
                <li>
                  <strong>Temporal lag:</strong> ACS 5-year estimates represent 2018–2022 averages.
                  Rapid demographic shifts may not yet be reflected.
                </li>
                <li>
                  <strong>Model-based estimates:</strong> CDC PLACES health measures are modeled from
                  BRFSS survey data, not direct measurements. Confidence intervals vary by tract size.
                </li>
                <li>
                  <strong>DPC scoring is exploratory:</strong> The market fit model uses heuristic
                  weights and national reference ranges. It is intended for screening, not as a
                  definitive business assessment.
                </li>
                <li>
                  <strong>Provider data currency:</strong> NPPES data is refreshed monthly, but
                  provider practice locations may lag behind actual moves or closures.
                </li>
                <li>
                  <strong>County-level employer data:</strong> Census CBP employer data is at the
                  county level and may not reflect within-county variation for large counties.
                </li>
                <li>
                  <strong>HPSA boundaries:</strong> HRSA HPSA designations are at the county or
                  service area level, not tract level. A tract within a non-HPSA county may still
                  experience provider shortages.
                </li>
              </ul>
            </CardContent>
          </Card>
        </section>

        <Separator />

        {/* Links */}
        <section>
          <h2 className="text-lg font-semibold text-stone-900 mb-4">Documentation &amp; Source Code</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <a
              href="https://russellstover1983.github.io/geohealth-api/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 rounded-lg border border-stone-200 bg-white p-4 hover:border-teal-300 hover:shadow-sm transition-all"
            >
              <BookOpen className="h-5 w-5 text-teal-600 shrink-0" />
              <div>
                <p className="text-sm font-medium text-stone-800">API Documentation</p>
                <p className="text-[10px] text-stone-400">Endpoints, schemas, and data dictionary</p>
              </div>
              <ExternalLink className="ml-auto h-3.5 w-3.5 text-stone-300" />
            </a>
            <a
              href="https://github.com/RussellStover1983/geohealth-api"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 rounded-lg border border-stone-200 bg-white p-4 hover:border-teal-300 hover:shadow-sm transition-all"
            >
              <Github className="h-5 w-5 text-stone-700 shrink-0" />
              <div>
                <p className="text-sm font-medium text-stone-800">GitHub Repository</p>
                <p className="text-[10px] text-stone-400">Source code, ETL pipelines, scoring engine</p>
              </div>
              <ExternalLink className="ml-auto h-3.5 w-3.5 text-stone-300" />
            </a>
          </div>
        </section>

        {/* Suggested Citation */}
        <section>
          <h2 className="text-lg font-semibold text-stone-900 mb-4">Suggested Citation</h2>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs leading-relaxed text-stone-600 font-mono bg-stone-50 rounded-lg p-4 border border-stone-200">
                GeoHealth SDOH Explorer. Data from U.S. Census Bureau American Community Survey,
                CDC PLACES, CDC/ATSDR Social Vulnerability Index, HRSA HPSA, CMS NPPES, Census
                County Business Patterns, and EPA EJScreen. Available at
                https://geohealth-api.vercel.app. Accessed [date].
              </p>
              <p className="mt-2 text-[10px] text-stone-400">
                When citing specific data, please also cite the original source agency (e.g.,
                &ldquo;CDC PLACES 2023 Release, based on BRFSS 2022 data&rdquo;).
              </p>
            </CardContent>
          </Card>
        </section>

        {/* Footer */}
        <footer className="pt-4 pb-8 text-center text-[10px] text-stone-400">
          <p>
            All data sourced from U.S. federal agencies. This tool is for informational and research
            purposes and does not constitute medical, financial, or professional advice.
          </p>
        </footer>
      </main>
    </div>
  );
}
