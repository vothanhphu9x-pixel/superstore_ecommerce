import "server-only";

const DEFAULT_API_URL = "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 15_000;

export class InternalApiConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InternalApiConfigurationError";
  }
}

function getConfiguration() {
  const rawUrl = process.env.INTERNAL_API_URL ?? DEFAULT_API_URL;
  const apiKey = process.env.API_KEY?.trim() ?? "";

  let baseUrl: URL;

  try {
    baseUrl = new URL(rawUrl);
  } catch {
    throw new InternalApiConfigurationError(
      "INTERNAL_API_URL is not a valid URL",
    );
  }

  if (!["http:", "https:"].includes(baseUrl.protocol)) {
    throw new InternalApiConfigurationError(
      "INTERNAL_API_URL must use http or https",
    );
  }

  if (!apiKey || apiKey.startsWith("CHANGE_ME")) {
    throw new InternalApiConfigurationError("API_KEY is not configured");
  }

  return {
    baseUrl: baseUrl.toString().replace(/\/$/, ""),
    apiKey,
  };
}

export async function internalFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const { baseUrl, apiKey } = getConfiguration();

  if (!path.startsWith("/api/")) {
    throw new InternalApiConfigurationError(
      "Internal API path must start with /api/",
    );
  }

  const headers = new Headers(init.headers);

  /*
   * Set sau init.headers để caller không thể ghi đè key thật.
   * Browser không gọi trực tiếp hàm này vì file đã import server-only.
   */
  headers.set("X-API-Key", apiKey);
  headers.set("Accept", "application/json");

  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    redirect: "manual",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });

  return response;
}
