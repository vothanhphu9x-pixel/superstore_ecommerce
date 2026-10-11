import { NextRequest, NextResponse } from "next/server";

import {
  InternalApiConfigurationError,
  internalFetch,
} from "@/lib/server/internalApi";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

function isAllowedRoute(method: string, segments: string[]): boolean {
  const path = segments.join("/");

  if (method === "GET") {
    return (
      path === "staff/me" ||
      path === "dashboard" ||
      path.startsWith("dashboard/")
    );
  }

  if (method === "POST") {
    return path === "staff/login" || path === "staff/logout";
  }

  return false;
}

function isCrossSitePost(request: NextRequest): boolean {
  if (request.method !== "POST") {
    return false;
  }

  const origin = request.headers.get("origin");

  /*
   * Không có Origin vẫn được phép để curl và server-side request
   * hoạt động. Browser cross-site POST thường sẽ có Origin.
   */
  if (!origin) {
    return false;
  }

  return origin !== process.env.Frontend_Origin;
}

function copySetCookieHeaders(
  upstream: Response,
  responseHeaders: Headers,
): void {
  /*
   * Node/Undici có getSetCookie(). Fallback về get("set-cookie")
   * để tương thích với runtime không cung cấp method này.
   */
  const headersWithSetCookie = upstream.headers as Headers & {
    getSetCookie?: () => string[];
  };

  const cookies = headersWithSetCookie.getSetCookie?.() ?? [];

  if (cookies.length > 0) {
    for (const cookie of cookies) {
      responseHeaders.append("set-cookie", cookie);
    }

    return;
  }

  const singleCookie = upstream.headers.get("set-cookie");

  if (singleCookie) {
    responseHeaders.append("set-cookie", singleCookie);
  }
}

async function forwardRequest(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  try {
    const { path: segments } = await context.params;

    if (!isAllowedRoute(request.method, segments)) {
      return NextResponse.json(
        {
          detail: "Internal route is not allowed",
        },
        {
          status: 404,
        },
      );
    }

    if (isCrossSitePost(request)) {
      return NextResponse.json(
        {
          detail: "Cross-site request is not allowed",
        },
        {
          status: 403,
        },
      );
    }

    const upstreamHeaders = new Headers();

    /*
     * Chuyển staff HttpOnly cookie từ browser sang FastAPI.
     * JavaScript phía browser không thể đọc giá trị cookie.
     */
    const cookie = request.headers.get("cookie");

    if (cookie) {
      upstreamHeaders.set("cookie", cookie);
    }

    const contentType = request.headers.get("content-type");

    if (contentType) {
      upstreamHeaders.set("content-type", contentType);
    }

    const forwardedFor =
      request.headers.get("x-forwarded-for") ??
      request.headers.get("x-real-ip");

    if (forwardedFor) {
      upstreamHeaders.set("x-forwarded-for", forwardedFor);
    }

    const requestBody =
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.text();

    /*
     * internalFetch yêu cầu path bắt đầu bằng /api/,
     * do đó path này khớp chính xác với code Step 6 của bạn.
     */
    const apiPath = `/api/${segments.join("/")}` + request.nextUrl.search;

    const upstream = await internalFetch(apiPath, {
      method: request.method,
      headers: upstreamHeaders,
      body: requestBody,
    });

    const responseHeaders = new Headers();

    const responseContentType = upstream.headers.get("content-type");

    if (responseContentType) {
      responseHeaders.set("content-type", responseContentType);
    }

    copySetCookieHeaders(upstream, responseHeaders);

    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (error) {
    if (error instanceof InternalApiConfigurationError) {
      console.error("Internal API configuration error:", error.message);

      return NextResponse.json(
        {
          detail: "Internal API is not configured",
        },
        {
          status: 500,
        },
      );
    }

    if (error instanceof Error && error.name === "TimeoutError") {
      return NextResponse.json(
        {
          detail: "Internal API request timed out",
        },
        {
          status: 504,
        },
      );
    }

    console.error("Internal API proxy error:", error);

    return NextResponse.json(
      {
        detail: "Internal API is unavailable",
      },
      {
        status: 502,
      },
    );
  }
}

export const GET = forwardRequest;
export const POST = forwardRequest;
