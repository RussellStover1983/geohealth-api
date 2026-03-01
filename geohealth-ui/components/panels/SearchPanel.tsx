"use client";

import { useState, useCallback, type FormEvent } from "react";
import { Search, Loader2, MapPin } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useGeoHealthStore } from "@/lib/store";
import { useContextLookup, useTractsGeoJSON } from "@/lib/api/hooks";
import { toast } from "@/lib/use-toast";

export function SearchPanel() {
  const [inputValue, setInputValue] = useState("");
  const {
    setSelectedTract,
    mergeTractsGeoJSON,
    loadedStates,
    setSearchLocation,
    flyTo,
    setSearchQuery,
    setIsSearching,
  } = useGeoHealthStore();

  const contextLookup = useContextLookup();
  const tractsLoader = useTractsGeoJSON();

  const handleSearch = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const address = inputValue.trim();
      if (!address) return;

      setSearchQuery(address);
      setIsSearching(true);

      // Look up the address
      const result = await contextLookup.lookup(address);

      if (result) {
        const { location, tract, narrative } = result;

        // Set search marker and fly to location
        setSearchLocation({ lat: location.lat, lng: location.lng });
        flyTo({ latitude: location.lat, longitude: location.lng, zoom: 12 });

        // Set selected tract
        if (tract) {
          setSelectedTract(tract, narrative);

          // Load entire state's tract polygons if not already loaded
          const stateFips = tract.state_fips;
          if (!loadedStates.has(stateFips)) {
            const geojson = await tractsLoader.load({
              state_fips: stateFips,
              limit: 2000,
            });
            if (geojson) {
              mergeTractsGeoJSON(geojson, stateFips);
            }
          }
        }
      } else if (contextLookup.error) {
        toast({
          title: "Lookup failed",
          description: contextLookup.error,
          variant: "destructive",
        });
      }

      setIsSearching(false);
    },
    [
      inputValue,
      contextLookup,
      tractsLoader,
      setSelectedTract,
      mergeTractsGeoJSON,
      loadedStates,
      setSearchLocation,
      flyTo,
      setSearchQuery,
      setIsSearching,
    ]
  );

  const isLoading = contextLookup.isLoading || tractsLoader.isLoading;

  return (
    <form onSubmit={handleSearch} className="relative">
      <div className="relative">
        <MapPin className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
        <Input
          type="text"
          placeholder="Search an address..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="h-11 pl-9 pr-10 text-sm"
          aria-label="Search address"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !inputValue.trim()}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-2 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600 disabled:opacity-50"
          aria-label="Search"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
        </button>
      </div>
    </form>
  );
}
