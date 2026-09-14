const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);

export function internalApiUrl(): string {
  const configured = process.env.INTERNAL_API_URL || process.env.API_URL;
  if (process.env.NODE_ENV === "production") {
    if (!configured) {
      throw new Error(
        "INTERNAL_API_URL is required in production. Point it at the separately hosted ShelfReady API, not localhost.",
      );
    }
    let parsed: URL;
    try {
      parsed = new URL(configured);
    } catch {
      throw new Error(`INTERNAL_API_URL is invalid: ${configured}`);
    }
    if (LOCAL_HOSTS.has(parsed.hostname)) {
      throw new Error(
        "INTERNAL_API_URL must not be localhost in production. The API and worker are hosted separately from the web app.",
      );
    }
    return configured.replace(/\/$/, "");
  }
  return (configured || "http://127.0.0.1:8000").replace(/\/$/, "");
}

export function apiToken(): string {
  const token = process.env.API_TOKEN || process.env.SHELFREADY_API_TOKEN;
  if (!token) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("API_TOKEN or SHELFREADY_API_TOKEN must be set on the Next.js server. Do not use NEXT_PUBLIC_API_TOKEN.");
    }
    return "dev-token-change-me";
  }
  return token;
}

export function operatorAccessToken(): string {
  return process.env.OPERATOR_ACCESS_TOKEN || apiToken();
}
