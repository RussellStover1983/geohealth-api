"use client";

import { Popup } from "react-map-gl/maplibre";
import { useGeoHealthStore } from "@/lib/store";
import type { ProviderProperties } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const TAXONOMY_LABELS: Record<string, string> = {
  "207Q00000X": "Family Medicine",
  "207QA0505X": "Family Medicine – Adult",
  "207R00000X": "Internal Medicine",
  "207RA0000X": "Internal Medicine – Adolescent",
  "207RG0100X": "Internal Medicine – Gastroenterology",
  "208D00000X": "General Practice",
  "208000000X": "Pediatrics",
  "2080A0000X": "Pediatrics – Adolescent",
  "363LF0000X": "NP – Family",
  "363LP0200X": "NP – Pediatrics",
  "363LA2200X": "NP – Adult Health",
  "363LG0600X": "NP – Gerontology",
  "363LP0222X": "NP – Pediatrics – Critical Care",
  "363A00000X": "Physician Assistant",
  "363AM0700X": "PA – Medical",
  "261QF0400X": "FQHC",
  "261QR1300X": "Rural Health Clinic",
  "261QU0200X": "Urgent Care",
  "261QP2300X": "Primary Care Clinic",
  "261QC1500X": "Community Health Center",
};

const TYPE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  PCP: { bg: "bg-teal-100", text: "text-teal-800", label: "PCP" },
  FQHC: { bg: "bg-orange-100", text: "text-orange-800", label: "FQHC" },
  URGENT_CARE: { bg: "bg-amber-100", text: "text-amber-800", label: "Urgent Care" },
  RURAL_HEALTH: { bg: "bg-emerald-100", text: "text-emerald-800", label: "Rural Health" },
  PRIMARY_CARE_CLINIC: { bg: "bg-blue-100", text: "text-blue-800", label: "Primary Care Clinic" },
  COMMUNITY_HEALTH_CENTER: { bg: "bg-purple-100", text: "text-purple-800", label: "Community Health" },
};

interface ProviderPopupProps {
  provider: ProviderProperties;
  longitude: number;
  latitude: number;
}

export function ProviderPopup({ provider, longitude, latitude }: ProviderPopupProps) {
  const { setSelectedProvider } = useGeoHealthStore();
  const typeStyle = TYPE_STYLES[provider.provider_type] ?? TYPE_STYLES.PCP;
  const taxonomyLabel = TAXONOMY_LABELS[provider.taxonomy_code] ?? provider.taxonomy_code;

  return (
    <Popup
      longitude={longitude}
      latitude={latitude}
      anchor="bottom"
      closeOnClick={false}
      onClose={() => setSelectedProvider(null)}
      className="provider-popup"
      maxWidth="280px"
    >
      <div className="px-1 py-0.5">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-semibold text-stone-900 leading-tight">
            {provider.name}
          </h3>
        </div>

        <div className="mt-1.5 flex items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium",
              typeStyle.bg,
              typeStyle.text
            )}
          >
            {typeStyle.label}
          </span>
          <span className="text-[10px] text-stone-500">{taxonomyLabel}</span>
        </div>

        <p className="mt-1.5 text-xs text-stone-600 leading-snug">
          {provider.address}
        </p>

        <p className="mt-1 text-[10px] text-stone-400">
          NPI: {provider.npi}
        </p>
      </div>
    </Popup>
  );
}
