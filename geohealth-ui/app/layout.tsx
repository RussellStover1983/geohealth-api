import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: {
    default: "GeoHealth — Census-tract health intelligence for healthcare",
    template: "%s · GeoHealth",
  },
  description:
    "Type an address. Get the social determinants of health, chronic-disease prevalence, environmental exposures, and provider supply for the surrounding census tract — sourced from Census, CDC, EPA, and HRSA. Open data, MIT licensed.",
  keywords: [
    "SDOH",
    "social determinants of health",
    "census tract",
    "health equity",
    "CDC PLACES",
    "SVI",
    "EPA EJScreen",
    "HRSA HPSA",
    "NPPES",
    "direct primary care",
    "DPC market fit",
  ],
  openGraph: {
    title: "GeoHealth — Census-tract health intelligence for healthcare",
    description:
      "Census-tract-level demographics, SVI, CDC PLACES, EPA EJScreen, and provider supply — sourced from federal data, served via API, map, and Python SDK.",
    type: "website",
    url: "https://geohealth-api.vercel.app",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="font-sans">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
