import { NextResponse } from "next/server";

import { internalFetch } from "@/lib/server/internalApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const upstream = await internalFetch("/api/health/live");

    const result = await upstream.json();

    if (!upstream.ok || result.status !== "ok") {
      throw new Error("Probe failed");
    }

    return NextResponse.json(
      {
        status: "ok",
        api: "up",
      },
      {
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  } catch {
    return NextResponse.json(
      {
        status: "unavailable",
        api: "down",
      },
      {
        status: 503,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }
}
