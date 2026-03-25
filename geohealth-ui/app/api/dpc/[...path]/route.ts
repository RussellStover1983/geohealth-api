import { NextRequest, NextResponse } from "next/server";

/**
 * DPC Market Fit API Proxy — forwards requests to the DPC API.
 *
 * Browser calls:  GET /api/dpc/api/v1/market-fit?tract_fips=...
 * This route:     GET <DPC_API_URL>/api/v1/market-fit?tract_fips=...
 */

const UPSTREAM =
  process.env.DPC_API_URL || "http://localhost:8001";

const ALLOWED_PREFIXES = [
  "/api/v1/market-fit",
  "/api/v1/providers",
  "/health",
];

function isAllowedPath(path: string): boolean {
  return ALLOWED_PREFIXES.some(
    (prefix) =>
      path === prefix ||
      path.startsWith(prefix + "?") ||
      path.startsWith(prefix + "/")
  );
}

async function proxyRequest(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const upstreamPath = "/" + params.path.join("/");

  if (!isAllowedPath(upstreamPath)) {
    return NextResponse.json(
      { error: true, status_code: 404, detail: "Not found" },
      { status: 404 }
    );
  }

  const url = new URL(upstreamPath, UPSTREAM);
  req.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  try {
    const upstream = await fetch(url.toString(), {
      method: req.method,
      headers: { Accept: "application/json" },
    });

    const data = await upstream.text();
    const responseHeaders = new Headers();
    const ct = upstream.headers.get("content-type");
    if (ct) responseHeaders.set("content-type", ct);

    // Cache market-fit responses briefly (5 min)
    if (upstream.ok) {
      responseHeaders.set("Cache-Control", "public, max-age=300");
    }

    return new NextResponse(data, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (err) {
    console.error("DPC proxy error:", err);
    return NextResponse.json(
      {
        error: true,
        status_code: 502,
        detail: "Failed to reach DPC Market Fit API",
      },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
