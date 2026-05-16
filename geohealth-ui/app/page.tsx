import Link from "next/link";
import {
  ArrowRight,
  Map as MapIcon,
  BookOpen,
  Github,
  Users,
  ShieldAlert,
  HeartPulse,
  Wind,
  Stethoscope,
  Sparkles,
  Code2,
  ExternalLink,
} from "lucide-react";
import { Logo } from "@/components/shared/Logo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const DOCS_URL = "https://russellstover1983.github.io/geohealth-api/";
const API_URL = "https://geohealth-api-production.up.railway.app";
const GITHUB_URL = "https://github.com/RussellStover1983/geohealth-api";
const PYPI_URL = "https://pypi.org/project/geohealth-api/";

const FEATURES = [
  {
    icon: Users,
    title: "Demographics & Trends",
    body: "ACS population, income, poverty, insurance, unemployment, and age — plus multi-year history (2018–2022) with absolute and percent change.",
    source: "U.S. Census Bureau",
  },
  {
    icon: ShieldAlert,
    title: "Social Vulnerability",
    body: "CDC/ATSDR SVI percentile rankings across four themes — socioeconomic status, household composition, minority status & language, housing & transportation.",
    source: "CDC / ATSDR",
  },
  {
    icon: HeartPulse,
    title: "Health Outcomes",
    body: "Fourteen tract-level health measures from CDC PLACES — diabetes, obesity, mental health, asthma, hypertension, smoking, dental visits, and more.",
    source: "CDC PLACES",
  },
  {
    icon: Wind,
    title: "Environmental Exposure",
    body: "EPA EJScreen indicators — PM2.5, ozone, diesel particulate matter, lead paint, Superfund proximity, hazardous waste, and air toxics cancer risk.",
    source: "EPA EJScreen",
  },
  {
    icon: Stethoscope,
    title: "Provider Supply",
    body: "PCP density, individual NPI provider lookup, HRSA HPSA shortage designations, and FQHC presence — the supply side of access.",
    source: "NPPES · HRSA",
  },
  {
    icon: Sparkles,
    title: "Decision Support",
    body: "Composite SDOH index, AI-generated plain-English narratives, and a Direct Primary Care market-fit score (0–100) across five dimensions.",
    source: "Computed",
  },
];

const STATS = [
  { value: "50 + DC", label: "states covered" },
  { value: "~84K", label: "census tracts" },
  { value: "50+", label: "metrics per tract" },
  { value: "7", label: "federal data sources" },
];

const DATA_SOURCES = [
  "U.S. Census Bureau",
  "CDC",
  "CDC / ATSDR",
  "EPA",
  "HRSA",
  "CMS NPPES",
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      {/* Top nav */}
      <header className="sticky top-0 z-20 border-b border-stone-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
          <Link href="/" className="flex items-center">
            <Logo size="md" />
          </Link>
          <nav className="ml-auto hidden items-center gap-1 sm:flex">
            <Link href="/explore">
              <Button variant="ghost" size="sm" className="text-xs">
                Explore the Map
              </Button>
            </Link>
            <Link href="/methodology">
              <Button variant="ghost" size="sm" className="text-xs">
                Methodology
              </Button>
            </Link>
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">
              <Button variant="ghost" size="sm" className="text-xs">
                Docs
              </Button>
            </a>
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
              <Button variant="ghost" size="sm" className="text-xs gap-1.5">
                <Github className="h-3.5 w-3.5" />
                GitHub
              </Button>
            </a>
          </nav>
          <Link href="/explore" className="sm:hidden">
            <Button size="sm" className="text-xs">
              Open Map
            </Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-stone-200">
        <div
          className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[500px] bg-gradient-to-b from-teal-50/60 via-stone-50 to-stone-50"
          aria-hidden
        />
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
          <div className="max-w-3xl">
            <Badge variant="secondary" className="mb-6 text-[11px] font-medium">
              Open data · MIT licensed · Live API
            </Badge>
            <h1 className="text-4xl font-bold leading-[1.1] tracking-tight text-stone-900 sm:text-5xl md:text-6xl">
              Census-tract intelligence for healthcare that meets people where they are.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-relaxed text-stone-600 sm:text-lg">
              Type an address. Get the social determinants of health, chronic-disease prevalence,
              environmental exposures, and provider supply for the surrounding census tract — sourced
              from Census, CDC, EPA, and HRSA, refreshed on the cadence each agency publishes.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/explore">
                <Button size="lg" className="gap-2">
                  <MapIcon className="h-4 w-4" />
                  Explore the Map
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">
                <Button size="lg" variant="outline" className="gap-2">
                  <BookOpen className="h-4 w-4" />
                  Read the Docs
                </Button>
              </a>
            </div>
          </div>

          {/* Stats strip */}
          <dl className="mt-16 grid grid-cols-2 gap-4 border-t border-stone-200 pt-8 sm:grid-cols-4 sm:gap-6">
            {STATS.map((s) => (
              <div key={s.label}>
                <dt className="text-[11px] uppercase tracking-wider text-stone-500">{s.label}</dt>
                <dd className="mt-1 text-2xl font-semibold tabular-nums text-stone-900 sm:text-3xl">
                  {s.value}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* Value prop */}
      <section className="border-b border-stone-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="grid gap-12 md:grid-cols-[1fr_1.4fr] md:items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-teal-600">
                Why census tracts
              </p>
              <h2 className="mt-3 text-3xl font-bold leading-tight tracking-tight text-stone-900 sm:text-4xl">
                ZIP codes hide what tracts reveal.
              </h2>
            </div>
            <div className="space-y-6 text-base leading-relaxed text-stone-600">
              <p>
                Health outcomes vary block by block. A ZIP-level view averages away the gradients
                that matter — the diabetes prevalence on one side of a freeway, the uninsured rate
                two stops down the bus line, the housing-cost burden in one neighborhood of a
                county that looks affluent in aggregate.
              </p>
              <p>
                GeoHealth resolves any U.S. address to its census tract and returns the data
                clinicians, planners, and researchers actually need to act on — at the granularity
                where intervention happens.
              </p>
              <ul className="space-y-3 pt-2">
                {[
                  "Understand a patient's social and environmental context in seconds.",
                  "Target outreach and resources to the populations who need them most.",
                  "Quantify health-equity gaps with peer-reviewed federal data.",
                ].map((item) => (
                  <li key={item} className="flex gap-3">
                    <span
                      className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-600"
                      aria-hidden
                    />
                    <span className="text-stone-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-b border-stone-200">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-wider text-teal-600">
              What you get
            </p>
            <h2 className="mt-3 text-3xl font-bold leading-tight tracking-tight text-stone-900 sm:text-4xl">
              Six layers of context, one address away.
            </h2>
            <p className="mt-4 text-base leading-relaxed text-stone-600">
              Every census tract is enriched with demographic, vulnerability, health-outcome,
              environmental, provider-supply, and decision-support signals — all queryable through
              one API, one map, and one Python SDK.
            </p>
          </div>

          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="group rounded-2xl border border-stone-200 bg-white p-6 transition-all hover:border-teal-300 hover:shadow-sm"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-700">
                  <f.icon className="h-5 w-5" strokeWidth={2} />
                </div>
                <h3 className="mt-5 text-base font-semibold text-stone-900">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-stone-600">{f.body}</p>
                <p className="mt-4 text-[11px] uppercase tracking-wider text-stone-400">
                  {f.source}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Data provenance strip */}
      <section className="border-b border-stone-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <div className="flex flex-col items-start gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-teal-600">
                Provenance
              </p>
              <p className="mt-2 text-base text-stone-700">
                Built entirely on publicly available federal data — no proprietary signals, no
                opaque models.
              </p>
            </div>
            <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium text-stone-500">
              {DATA_SOURCES.map((source) => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          </div>
          <p className="mt-4 text-xs text-stone-400">
            See the{" "}
            <Link href="/methodology" className="text-teal-600 underline-offset-4 hover:underline">
              Methodology page
            </Link>{" "}
            for vintages, update cadence, and scoring details.
          </p>
        </div>
      </section>

      {/* Developer block */}
      <section className="border-b border-stone-200">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="grid gap-12 md:grid-cols-2 md:items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-teal-600">
                For developers &amp; AI agents
              </p>
              <h2 className="mt-3 text-3xl font-bold leading-tight tracking-tight text-stone-900 sm:text-4xl">
                A typed API, a Python SDK, and a native MCP server.
              </h2>
              <p className="mt-4 text-base leading-relaxed text-stone-600">
                Hit the REST API directly, install the typed Python client, or wire it into Claude
                Desktop and Claude Code as a native MCP tool. Authenticated requests, rate-limit
                headers, OpenAPI 3.1 schema, and an <code className="text-[13px]">/llms.txt</code>{" "}
                agent overview included.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" className="gap-2">
                    <BookOpen className="h-4 w-4" />
                    API Reference
                  </Button>
                </a>
                <a href={PYPI_URL} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" className="gap-2">
                    <Code2 className="h-4 w-4" />
                    Python SDK
                  </Button>
                </a>
                <a href={`${API_URL}/docs`} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" className="gap-2">
                    Swagger UI
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                </a>
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-stone-800 bg-stone-900 shadow-xl">
              <div className="flex items-center gap-2 border-b border-stone-800 bg-stone-950 px-4 py-2.5">
                <div className="flex gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-stone-700" aria-hidden />
                  <span className="h-2.5 w-2.5 rounded-full bg-stone-700" aria-hidden />
                  <span className="h-2.5 w-2.5 rounded-full bg-stone-700" aria-hidden />
                </div>
                <span className="ml-2 text-[11px] text-stone-500">geohealth.py</span>
              </div>
              <pre className="overflow-x-auto px-5 py-5 text-[12.5px] leading-relaxed text-stone-200">
                <code>{`from geohealth.sdk import GeoHealthClient

BASE = "https://geohealth-api-production.up.railway.app"

with GeoHealthClient(BASE, api_key="…") as client:
    ctx = client.context(
        address="1234 Main St, Minneapolis, MN",
        narrative=True,
    )

    print(ctx.tract.geoid)              # 27053026200
    print(ctx.tract.poverty_rate)       # 18.2
    print(ctx.tract.svi_themes.rpl_themes)
    print(ctx.tract.places_measures.diabetes)
    print(ctx.narrative)                # Plain-English summary`}</code>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="bg-stone-900 text-stone-50">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="flex flex-col items-start gap-8 md:flex-row md:items-center md:justify-between">
            <div className="max-w-xl">
              <h2 className="text-3xl font-bold leading-tight tracking-tight text-white sm:text-4xl">
                Start where the data lives — the map.
              </h2>
              <p className="mt-4 text-base leading-relaxed text-stone-300">
                Search any U.S. address. Toggle layers across SDOH, health outcomes, environment,
                and provider supply. Click a tract to see every metric, side by side.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href="/explore">
                <Button size="lg" className="gap-2 bg-teal-600 text-white hover:bg-teal-700">
                  <MapIcon className="h-4 w-4" />
                  Explore the Map
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
                <Button
                  size="lg"
                  variant="outline"
                  className="gap-2 border-stone-700 bg-transparent text-stone-100 hover:bg-stone-800 hover:text-white"
                >
                  <Github className="h-4 w-4" />
                  View on GitHub
                </Button>
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-stone-200 bg-stone-50">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
          <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div>
              <Logo size="md" />
              <p className="mt-3 max-w-sm text-xs leading-relaxed text-stone-500">
                Open-source geographic health intelligence for clinicians, researchers, and
                developers. MIT licensed.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-x-10 gap-y-2 text-sm sm:grid-cols-3">
              <Link href="/explore" className="text-stone-600 hover:text-teal-700">
                Explore the Map
              </Link>
              <Link href="/methodology" className="text-stone-600 hover:text-teal-700">
                Methodology
              </Link>
              <a
                href={DOCS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-stone-600 hover:text-teal-700"
              >
                Documentation
              </a>
              <a
                href={`${API_URL}/docs`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-stone-600 hover:text-teal-700"
              >
                Swagger UI
              </a>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-stone-600 hover:text-teal-700"
              >
                GitHub
              </a>
              <a
                href={PYPI_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-stone-600 hover:text-teal-700"
              >
                PyPI
              </a>
            </div>
          </div>
          <p className="mt-8 border-t border-stone-200 pt-6 text-[11px] leading-relaxed text-stone-400">
            All data sourced from U.S. federal agencies. This tool is for informational and research
            purposes and does not constitute medical, financial, or professional advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
