"use client";

import { Popup } from "react-map-gl/maplibre";
import { X, Building2, Phone, MapPin } from "lucide-react";
import { useGeoHealthStore } from "@/lib/store";

export function ProviderPopup() {
  const { selectedProvider, setSelectedProvider } = useGeoHealthStore();

  if (!selectedProvider || !selectedProvider.lng || !selectedProvider.lat) {
    return null;
  }

  const isFqhc = selectedProvider.is_fqhc;
  const isOrg = selectedProvider.entity_type === "2";

  // Format phone number: "8165551234" → "(816) 555-1234"
  const formatPhone = (raw: string | null) => {
    if (!raw || raw.length < 10) return raw;
    const digits = raw.replace(/\D/g, "");
    if (digits.length === 10) {
      return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
    }
    return raw;
  };

  return (
    <Popup
      longitude={selectedProvider.lng}
      latitude={selectedProvider.lat}
      anchor="bottom"
      closeOnClick={false}
      onClose={() => setSelectedProvider(null)}
      closeButton={false}
      maxWidth="320px"
      className="provider-popup"
    >
      <div className="relative min-w-[260px] rounded-lg bg-white p-3 text-sm shadow-lg">
        {/* Close button */}
        <button
          onClick={() => setSelectedProvider(null)}
          className="absolute right-2 top-2 rounded-full p-0.5 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600"
          aria-label="Close"
        >
          <X className="h-3.5 w-3.5" />
        </button>

        {/* Provider name + credential */}
        <div className="pr-6">
          <h3 className="text-sm font-semibold text-stone-800">
            {isOrg ? (
              <span className="flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5 text-stone-400" />
                {selectedProvider.provider_name}
              </span>
            ) : (
              <>
                {selectedProvider.provider_name}
                {selectedProvider.credential && (
                  <span className="ml-1 font-normal text-stone-500">
                    , {selectedProvider.credential}
                  </span>
                )}
              </>
            )}
          </h3>
          <p className="mt-0.5 text-xs text-stone-500">
            {selectedProvider.taxonomy_description || selectedProvider.primary_taxonomy}
            <span className="ml-1 text-stone-400">
              ({selectedProvider.primary_taxonomy})
            </span>
          </p>
        </div>

        {/* Divider */}
        <hr className="my-2 border-stone-200" />

        {/* Address */}
        {(selectedProvider.practice_address || selectedProvider.practice_city) && (
          <div className="flex items-start gap-1.5 text-xs text-stone-600">
            <MapPin className="mt-0.5 h-3 w-3 shrink-0 text-stone-400" />
            <div>
              {selectedProvider.practice_address && (
                <div>{selectedProvider.practice_address}</div>
              )}
              <div>
                {selectedProvider.practice_city && `${selectedProvider.practice_city}, `}
                {selectedProvider.practice_state}
                {selectedProvider.practice_zip && ` ${selectedProvider.practice_zip}`}
              </div>
            </div>
          </div>
        )}

        {/* Phone */}
        {selectedProvider.phone && (
          <div className="mt-1.5 flex items-center gap-1.5 text-xs">
            <Phone className="h-3 w-3 text-stone-400" />
            <a
              href={`tel:${selectedProvider.phone}`}
              className="text-accent-600 hover:underline"
            >
              {formatPhone(selectedProvider.phone)}
            </a>
          </div>
        )}

        {/* FQHC Badge */}
        {isFqhc && (
          <>
            <hr className="my-2 border-stone-200" />
            <div className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700">
              <div className="h-2 w-2 rounded-full bg-rose-500" />
              Federally Qualified Health Center
            </div>
          </>
        )}

        {/* NPI + Tract */}
        <div className="mt-2 flex items-center gap-3 text-[10px] text-stone-400">
          <span>NPI: {selectedProvider.npi}</span>
          {selectedProvider.tract_fips && (
            <span>Tract: {selectedProvider.tract_fips}</span>
          )}
        </div>
      </div>
    </Popup>
  );
}
