import { NextRequest, NextResponse } from "next/server";

interface NominatimResult {
  display_name: string;
  lat: string;
  lon: string;
}

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")?.trim();
  if (!q || q.length < 3) {
    return NextResponse.json([]);
  }

  try {
    const url = new URL("https://nominatim.openstreetmap.org/search");
    url.searchParams.set("q", q);
    url.searchParams.set("format", "json");
    url.searchParams.set("countrycodes", "us");
    url.searchParams.set("limit", "5");
    url.searchParams.set("addressdetails", "0");

    const res = await fetch(url.toString(), {
      headers: { "User-Agent": "GeoHealth-SDOH-Explorer/1.0" },
      next: { revalidate: 300 },
    });

    if (!res.ok) {
      return NextResponse.json([]);
    }

    const data: NominatimResult[] = await res.json();
    const suggestions = data.map((r) => ({
      display_name: r.display_name,
      lat: parseFloat(r.lat),
      lng: parseFloat(r.lon),
    }));

    return NextResponse.json(suggestions, {
      headers: { "Cache-Control": "public, max-age=300" },
    });
  } catch {
    return NextResponse.json([]);
  }
}
