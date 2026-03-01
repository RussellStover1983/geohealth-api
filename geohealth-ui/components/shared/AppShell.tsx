"use client";

import { Suspense, lazy } from "react";
import { PanelLeftClose, PanelLeft } from "lucide-react";
import { Logo } from "./Logo";
import { SearchPanel } from "@/components/panels/SearchPanel";
import { LayerPanel } from "@/components/panels/LayerPanel";
import { TractDetailPanel } from "@/components/panels/TractDetailPanel";
import { MapLoadingSkeleton } from "./LoadingStates";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useGeoHealthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

// Dynamically import map to avoid SSR issues with MapLibre
const MapContainer = lazy(() =>
  import("@/components/map/MapContainer").then((mod) => ({
    default: mod.MapContainer,
  }))
);

export function AppShell() {
  const { isSidebarCollapsed, toggleSidebar } = useGeoHealthStore();

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background">
      {/* Topbar */}
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-stone-200 bg-white px-4">
        <Logo />
        <div className="mx-auto w-full max-w-lg">
          <SearchPanel />
        </div>
        <div className="flex items-center gap-2">
          <Badge label="4 states" />
          <Badge label="6,784 tracts" />
        </div>
      </header>

      {/* Main content */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <aside
          className={cn(
            "shrink-0 border-r border-stone-200 bg-stone-50 transition-all duration-300",
            isSidebarCollapsed ? "w-0 overflow-hidden opacity-0" : "w-[300px]"
          )}
        >
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between px-5 py-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleSidebar}
                className="h-8 w-8"
                aria-label="Collapse sidebar"
              >
                <PanelLeftClose className="h-4 w-4" />
              </Button>
            </div>
            <Separator />
            <ScrollArea className="flex-1">
              <LayerPanel />
            </ScrollArea>
          </div>
        </aside>

        {/* Sidebar collapsed toggle */}
        {isSidebarCollapsed && (
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="absolute left-2 top-2 z-10 h-9 w-9 rounded-lg bg-white shadow-md"
            aria-label="Expand sidebar"
          >
            <PanelLeft className="h-4 w-4" />
          </Button>
        )}

        {/* Map canvas */}
        <main className="relative flex-1">
          <Suspense fallback={<MapLoadingSkeleton />}>
            <MapContainer />
          </Suspense>

          {/* Detail panel overlay */}
          <TractDetailPanel />
        </main>
      </div>
    </div>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="hidden rounded-full bg-stone-100 px-2.5 py-0.5 text-[10px] font-medium text-stone-500 lg:inline-block">
      {label}
    </span>
  );
}
