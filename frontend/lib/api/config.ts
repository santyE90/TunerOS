const DEFAULT_API_URL = "http://127.0.0.1:8000";

function withoutTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

export const TUNEROS_API_URL = withoutTrailingSlash(
  process.env.NEXT_PUBLIC_TUNEROS_API_URL ?? DEFAULT_API_URL,
);

function websocketUrlFromApi(apiUrl: string): string {
  if (apiUrl.startsWith("https://")) {
    return `wss://${apiUrl.slice("https://".length)}`;
  }
  if (apiUrl.startsWith("http://")) {
    return `ws://${apiUrl.slice("http://".length)}`;
  }
  throw new Error("NEXT_PUBLIC_TUNEROS_API_URL must use http:// or https://");
}

export const TUNEROS_WS_URL = withoutTrailingSlash(
  process.env.NEXT_PUBLIC_TUNEROS_WS_URL ?? websocketUrlFromApi(TUNEROS_API_URL),
);
