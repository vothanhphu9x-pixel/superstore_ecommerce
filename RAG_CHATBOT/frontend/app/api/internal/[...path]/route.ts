import { isIP } from "node:net";

import { NextRequest, NextResponse } from "next/server";

import {
  InternalApiConfigurationError,
  internalFetch,
} from "@/lib/server/internalApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const GET_ROUTES = new Set([
  "staff/me",
  "dashboard",
  "dashboard/kpi",
  "dashboard/revenue-trend",
  "dashboard/by-category",
  "dashboard/by-region",
  "dashboard/top-products",
]);

const POST_ROUTES = new Set(["staff/login", "staff/logout"]);

type Context = {
  params: Promise<{
    path: string[];
  }>;
};

function failure(detail: string, status: number): NextResponse {
  return NextResponse.json(
    { detail },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}

async function forward(
  request: NextRequest,
  context: Context,
): Promise<NextResponse> {
  try {
    const { path } = await context.params;
    const route = path.join("/");

    const allowedRoutes = request.method === "GET" ? GET_ROUTES : POST_ROUTES;

    if (!allowedRoutes.has(route)) {
      return failure("Internal route is not allowed", 404);
    }

    if (request.method === "POST") {
      const configuredOrigin = process.env.Frontend_Origin;

      if (process.env.NODE_ENV === "production" && !configuredOrigin) {
        throw new InternalApiConfigurationError(
          "Frontend_Origin is not configured",
        );
      }

      const expectedOrigin = new URL(configuredOrigin ?? request.nextUrl.origin)
        .origin;

      if (request.headers.get("origin") !== expectedOrigin) {
        return failure("Origin is not allowed", 403);
      }
    }

    const headers = new Headers();

    const session = request.cookies.get("superstore_staff")?.value;

    if (session && /^[A-Za-z0-9._-]+$/.test(session)) {
      headers.set("Cookie", `superstore_staff=${session}`);
    }

    if (process.env.VERCEL === "1") {
      const address = request.headers.get("x-vercel-forwarded-for")?.trim();

      if (address && isIP(address)) {
        headers.set("X-Superstore-Client-IP", address);
      }
    }

    let body: string | undefined;

    if (route === "staff/login") {
      const contentType = request.headers
        .get("content-type")
        ?.split(";")[0]
        .trim();

      if (contentType !== "application/json") {
        return failure("JSON body is required", 415);
      }

      body = await request.text();

      if (Buffer.byteLength(body) > 16_384) {
        return failure("Request is too large", 413);
      }

      headers.set("Content-Type", "application/json");
    }

    const started = Date.now();

    const upstream = await internalFetch(
      `/api/${route}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body,
      },
    );

    if (upstream.status >= 300 && upstream.status < 400) {
      return failure("Unexpected upstream redirect", 502);
    }

    const responseBody = await upstream.arrayBuffer();

    const responseHeaders = new Headers({
      "Cache-Control": "no-store",
    });

    const forwardedResponseHeaders = [
      "content-type",
      "retry-after",
      "x-request-id",
    ];

    for (const name of forwardedResponseHeaders) {
      const value = upstream.headers.get(name);

      if (value) {
        responseHeaders.set(name, value);
      }
    }

    for (const cookie of upstream.headers.getSetCookie()) {
      responseHeaders.append("Set-Cookie", cookie);
    }

    console.info(
      JSON.stringify({
        event: "internal_proxy",
        route,
        status: upstream.status,
        duration_ms: Date.now() - started,
        request_id: upstream.headers.get("x-request-id"),
      }),
    );

    const bodylessResponse = upstream.status === 204 || upstream.status === 205;

    return new NextResponse(bodylessResponse ? null : responseBody, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (error) {
    if (error instanceof InternalApiConfigurationError) {
      return failure("Internal API is not configured", 500);
    }

    if (
      error instanceof Error &&
      ["TimeoutError", "AbortError"].includes(error.name)
    ) {
      return failure("Internal API request timed out", 504);
    }

    console.error(
      JSON.stringify({
        event: "internal_proxy_failed",
      }),
    );

    return failure("Internal API is unavailable", 502);
  }
}

export const GET = forward;
export const POST = forward;
