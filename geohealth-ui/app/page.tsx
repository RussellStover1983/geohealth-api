"use client";

import { AppShell } from "@/components/shared/AppShell";
import { TooltipProvider } from "@/components/ui/tooltip";

export default function HomePage() {
  return (
    <TooltipProvider delayDuration={200}>
      <AppShell />
    </TooltipProvider>
  );
}
