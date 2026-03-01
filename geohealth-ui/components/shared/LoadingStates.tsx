"use client";

import { Skeleton } from "@/components/ui/skeleton";

export function DetailPanelSkeleton() {
  return (
    <div className="space-y-4 p-5">
      {/* Header */}
      <div>
        <Skeleton className="h-5 w-3/4" />
        <div className="mt-2 flex gap-2">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-5 w-16" />
        </div>
      </div>

      {/* Narrative */}
      <Skeleton className="h-24 w-full rounded-xl" />

      {/* Demographics */}
      <div className="rounded-xl border p-4">
        <Skeleton className="mb-3 h-4 w-24" />
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i}>
              <Skeleton className="mb-1 h-2.5 w-16" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      </div>

      {/* SVI */}
      <div className="rounded-xl border p-4">
        <Skeleton className="mb-3 h-4 w-32" />
        <Skeleton className="h-[200px] w-full" />
      </div>

      {/* Health outcomes */}
      <div className="rounded-xl border p-4">
        <Skeleton className="mb-3 h-4 w-28" />
        <div className="grid grid-cols-3 gap-2">
          {Array.from({ length: 9 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function LayerPanelSkeleton() {
  return (
    <div className="space-y-3 p-5">
      <Skeleton className="h-4 w-20" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <div className="ml-4 space-y-1.5">
            {Array.from({ length: 3 }).map((_, j) => (
              <Skeleton key={j} className="h-3 w-28" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function MapLoadingSkeleton() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-stone-100">
      <div className="text-center">
        <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
        <p className="text-sm text-stone-500">Loading map...</p>
      </div>
    </div>
  );
}
