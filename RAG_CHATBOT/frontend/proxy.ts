import { NextRequest, NextResponse } from "next/server";

const STAFF_COOKIE_NAME = "superstore_staff";

export function proxy(request: NextRequest) {
  const sessionCookie = request.cookies.get(STAFF_COOKIE_NAME)?.value;

  if (!sessionCookie) {
    const loginUrl = new URL("/login", request.url);

    loginUrl.searchParams.set(
      "next",
      `${request.nextUrl.pathname}${request.nextUrl.search}`,
    );

    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
