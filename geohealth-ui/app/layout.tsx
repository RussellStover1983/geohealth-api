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
  title: "GeoHealth SDOH Explorer",
  description:
    "Census-tract-level geographic health intelligence. Explore social determinants of health, CDC PLACES measures, EPA environmental data, and more.",
  keywords: [
    "SDOH",
    "social determinants of health",
    "census tract",
    "health equity",
    "CDC PLACES",
    "SVI",
    "EPA EJScreen",
  ],
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
