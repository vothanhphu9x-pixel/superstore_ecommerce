import { NextRequest, NextResponse } from "next/server";

import {
  InternalApiConfigurationError,
  internalFetch,
} from "@/lib/server/internalApi";

const ALLOWED_METRICS = new Set([
  "kpi",
  "revenue-trend",
  "by-category",
  "by-region",
  "top-products",
]);

function previewIsEnabled(): boolean {
  return process.env.ALLOW_UNAUTHENTICATED_INTERNAL_UI === "true";
}

function buildUpstreamPath(segments: string[], search: string): string | null {
  /*
   * Chỉ cho:
   *   /dashboard
   *   /dashboard/<một trong 5 metric>
   *
   * Không dùng prefix-only allowlist vì /dashboard/../../something
   * hoặc endpoint mới thêm nhầm có thể bị proxy ngoài ý muốn.
   */
  if (segments.length === 1 && segments[0] === "dashboard") {
    return `/api/dashboard${search}`;
  }

  if (
    segments.length === 2 &&
    segments[0] === "dashboard" &&
    ALLOWED_METRICS.has(segments[1])
  ) {
    return `/api/dashboard/${segments[1]}${search}`;
  }

  return null;
}

export async function GET(
  request: NextRequest,
  context: {
    params: Promise<{
      path: string[];
    }>;
  },
) {
  if (!previewIsEnabled()) {
    return NextResponse.json(
      {
        detail:
          "Internal dashboard is locked until staff authentication is implemented.",
      },
      {
        status: 503,
      },
    );
  }

  const { path } = await context.params;
  const upstreamPath = buildUpstreamPath(path, request.nextUrl.search);

  if (upstreamPath === null) {
    return NextResponse.json(
      {
        detail: "Internal API path is not allowed.",
      },
      {
        status: 404,
      },
    );
  }

  try {
    const upstream = await internalFetch(upstreamPath, {
      method: "GET",
    });

    const body = await upstream.text();

    if (!upstream.ok) {
      console.error(
        `[internal-proxy] FastAPI ${upstream.status} at ${upstreamPath}: ` +
          body.slice(0, 500),
      );
    }

    return new NextResponse(body, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("Content-Type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    if (error instanceof InternalApiConfigurationError) {
      console.error(
        "[internal-proxy] Server configuration error:",
        error.message,
      );

      return NextResponse.json(
        {
          detail: "Internal API proxy is not configured.",
        },
        {
          status: 503,
        },
      );
    }

    console.error(`[internal-proxy] Request to ${upstreamPath} failed:`, error);

    return NextResponse.json(
      {
        detail: "Cannot connect to the backend. Confirm FastAPI is running.",
      },
      {
        status: 502,
      },
    );
  }
}
