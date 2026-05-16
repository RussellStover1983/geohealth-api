import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Explore the Map",
  description:
    "Interactive census-tract map of social determinants of health, CDC PLACES measures, EPA environmental data, provider supply, and DPC market fit across all 50 US states + DC.",
};

export default function ExploreLayout({ children }: { children: React.ReactNode }) {
  return children;
}
