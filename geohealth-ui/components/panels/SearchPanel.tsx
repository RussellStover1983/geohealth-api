"use client";

import { useState, useCallback, useRef, useEffect, type FormEvent, type KeyboardEvent } from "react";
import { Search, Loader2, MapPin } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useGeoHealthStore } from "@/lib/store";
import { useContextLookup, useTractsGeoJSON, useAddressSuggestions } from "@/lib/api/hooks";
import type { AddressSuggestion } from "@/lib/api/hooks";
import { toast } from "@/lib/use-toast";

export function SearchPanel() {
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);

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
  const autocomplete = useAddressSuggestions();

  // Perform the actual address lookup (shared by Enter and suggestion click)
  const performLookup = useCallback(
    async (address: string) => {
      setSearchQuery(address);
      setIsSearching(true);
      setIsOpen(false);
      autocomplete.clear();

      const result = await contextLookup.lookup(address);

      if (result) {
        const { location, tract, narrative } = result;
        setSearchLocation({ lat: location.lat, lng: location.lng });
        flyTo({ latitude: location.lat, longitude: location.lng, zoom: 12 });

        if (tract) {
          setSelectedTract(tract, narrative);
          const stateFips = tract.state_fips;
          if (!loadedStates.has(stateFips)) {
            const geojson = await tractsLoader.load({ state_fips: stateFips, limit: 2000 });
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
      contextLookup,
      tractsLoader,
      autocomplete,
      setSelectedTract,
      mergeTractsGeoJSON,
      loadedStates,
      setSearchLocation,
      flyTo,
      setSearchQuery,
      setIsSearching,
    ]
  );

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const address = inputValue.trim();
      if (!address) return;
      performLookup(address);
    },
    [inputValue, performLookup]
  );

  const selectSuggestion = useCallback(
    (suggestion: AddressSuggestion) => {
      setInputValue(suggestion.display_name);
      setActiveIndex(-1);
      performLookup(suggestion.display_name);
    },
    [performLookup]
  );

  // Handle input changes — trigger autocomplete
  const handleInputChange = useCallback(
    (value: string) => {
      setInputValue(value);
      setActiveIndex(-1);
      if (value.trim().length >= 3) {
        autocomplete.search(value);
        setIsOpen(true);
      } else {
        autocomplete.clear();
        setIsOpen(false);
      }
    },
    [autocomplete]
  );

  // Show dropdown when suggestions arrive
  useEffect(() => {
    if (autocomplete.suggestions.length > 0) {
      setIsOpen(true);
    }
  }, [autocomplete.suggestions]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!isOpen || autocomplete.suggestions.length === 0) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setActiveIndex((prev) =>
            prev < autocomplete.suggestions.length - 1 ? prev + 1 : 0
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setActiveIndex((prev) =>
            prev > 0 ? prev - 1 : autocomplete.suggestions.length - 1
          );
          break;
        case "Enter":
          if (activeIndex >= 0) {
            e.preventDefault();
            selectSuggestion(autocomplete.suggestions[activeIndex]);
          }
          // If no suggestion selected, form submit handles it
          break;
        case "Escape":
          e.preventDefault();
          setIsOpen(false);
          setActiveIndex(-1);
          break;
      }
    },
    [isOpen, activeIndex, autocomplete.suggestions, selectSuggestion]
  );

  // Scroll active option into view
  useEffect(() => {
    if (activeIndex >= 0 && listboxRef.current) {
      const item = listboxRef.current.children[activeIndex] as HTMLElement;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [activeIndex]);

  // Click-outside dismissal
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setActiveIndex(-1);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const isLoading = contextLookup.isLoading || tractsLoader.isLoading;
  const showDropdown = isOpen && autocomplete.suggestions.length > 0 && !isLoading;

  return (
    <div ref={containerRef} className="relative">
      <form onSubmit={handleSubmit}>
        <div className="relative">
          <MapPin className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
          <Input
            type="text"
            placeholder="Search an address..."
            value={inputValue}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              if (autocomplete.suggestions.length > 0) setIsOpen(true);
            }}
            className="h-11 pl-9 pr-10 text-sm"
            disabled={isLoading}
            role="combobox"
            aria-expanded={showDropdown}
            aria-controls="address-suggestions"
            aria-activedescendant={
              activeIndex >= 0 ? `suggestion-${activeIndex}` : undefined
            }
            aria-autocomplete="list"
            aria-label="Search address"
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

      {/* Autocomplete dropdown */}
      {showDropdown && (
        <ul
          ref={listboxRef}
          id="address-suggestions"
          role="listbox"
          className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-stone-200 bg-white py-1 shadow-lg"
        >
          {autocomplete.suggestions.map((suggestion, i) => (
            <li
              key={`${suggestion.lat}-${suggestion.lng}-${i}`}
              id={`suggestion-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              className={`flex cursor-pointer items-start gap-2 px-3 py-2 text-sm ${
                i === activeIndex
                  ? "bg-accent-50 text-accent-900"
                  : "text-stone-700 hover:bg-stone-50"
              }`}
              onMouseDown={(e) => {
                e.preventDefault(); // Prevent blur before click fires
                selectSuggestion(suggestion);
              }}
              onMouseEnter={() => setActiveIndex(i)}
            >
              <MapPin className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-stone-400" />
              <span className="line-clamp-2">{suggestion.display_name}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Loading indicator for autocomplete */}
      {isOpen && autocomplete.isLoading && autocomplete.suggestions.length === 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-stone-200 bg-white px-3 py-3 shadow-lg">
          <div className="flex items-center gap-2 text-xs text-stone-400">
            <Loader2 className="h-3 w-3 animate-spin" />
            Searching...
          </div>
        </div>
      )}
    </div>
  );
}
