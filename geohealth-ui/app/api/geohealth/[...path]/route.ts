import { NextRequest, NextResponse } from "next/server";

/**
 * BFF Proxy — forwards requests to the GeoHealth API with the server-side API key.
 *
 * Browser calls:  GET /api/geohealth/v1/context?address=...
 * This route:     GET https://geohealth-api-production.up.railway.app/v1/context?address=...
 *                 with X-API-Key header injected server-side.
 *
 * The real API key (GEOHEALTH_API_KEY) is never sent to the browser.
 */

const UPSTREAM =
  process.env.GEOHEALTH_API_URL ||
  "https://geohealth-api-production.up.railway.app";

const API_KEY = process.env.GEOHEALTH_API_KEY || "";

// Allowed upstream path prefixes — reject anything else
const ALLOWED_PREFIXES = [
  "/health",
  "/metrics",
  "/v1/context",
  "/v1/batch",
  "/v1/nearby",
  "/v1/compare",
  "/v1/trends",
  "/v1/demographics",
  "/v1/stats",
  "/v1/dictionary",
  "/v1/tracts",
  "/v1/providers",
  "/llms.txt",
  "/llms-full.txt",
];

function isAllowedPath(path: string): boolean {
  return ALLOWED_PREFIXES.some((prefix) => path === prefix || path.startsWith(prefix + "?") || path.startsWith(prefix + "/"));
}

async function proxyRequest(req: NextRequest, { params }: { params: { path: string[] } }) {
  const upstreamPath = "/" + params.path.join("/");

  // Reject paths that aren't in our allowlist
  if (!isAllowedPath(upstreamPath)) {
    return NextResponse.json(
      { error: true, status_code: 404, detail: "Not found" },
      { status: 404 }
    );
  }

  // Build upstream URL preserving query params
  const url = new URL(upstreamPath, UPSTREAM);
  req.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  // Forward the request with the server-side API key
  const headers: Record<string, string> = {
    "Accept": "application/json",
  };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }

  // Forward request body for POST methods
  let body: string | undefined;
  if (req.method === "POST") {
    body = await req.text();
    headers["Content-Type"] = "application/json";
  }

  try {
    const upstream = await fetch(url.toString(), {
      method: req.method,
      headers,
      body,
    });

    // Stream the response back
    const data = await upstream.text();
    const responseHeaders = new Headers();

    // Forward rate-limit headers so the UI can display them
    const passthroughHeaders = [
      "x-ratelimit-limit",
      "x-ratelimit-remaining",
      "x-ratelimit-reset",
      "x-request-id",
      "content-type",
    ];
    for (const h of passthroughHeaders) {
      const val = upstream.headers.get(h);
      if (val) responseHeaders.set(h, val);
    }

    // Add cache headers for mostly-static data
    if (upstreamPath === "/v1/dictionary" || upstreamPath.startsWith("/llms")) {
      responseHeaders.set("Cache-Control", "public, max-age=3600");
    }

    return new NextResponse(data, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (err) {
    console.error("Proxy error:", err);
    return NextResponse.json(
      { error: true, status_code: 502, detail: "Failed to reach upstream API" },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
