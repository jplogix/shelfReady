import { NextRequest, NextResponse } from "next/server";

import { applySessionCookie, hasValidSession, isLocalDevelopment, isPublicApiPath } from "./operator-session";
import { apiToken, internalApiUrl } from "./server-config";

export async function proxyToApi(req: NextRequest, path: string): Promise<NextResponse> {
  const publicPath = isPublicApiPath(path);
  let authorized = hasValidSession(req);
  if (!authorized && isLocalDevelopment(req) && !publicPath) {
    authorized = true;
  }
  if (!publicPath && req.method !== "GET" && req.method !== "HEAD" && !authorized) {
    return NextResponse.json(
      { error: "operator_session_required", detail: "Sign in with OPERATOR_ACCESS_TOKEN to use operator writes." },
      { status: 401 },
    );
  }
  if (!publicPath && !authorized && (req.method === "GET" || req.method === "HEAD")) {
    return NextResponse.json(
      { error: "operator_session_required", detail: "Operator session required." },
      { status: 401 },
    );
  }

  const target = new URL(path, `${internalApiUrl()}/`);
  target.search = req.nextUrl.search;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (!publicPath || req.headers.get("authorization")) {
    headers.set("Authorization", `Bearer ${apiToken()}`);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  const res = await fetch(target, init);
  const responseHeaders = new Headers(res.headers);
  responseHeaders.delete("transfer-encoding");
  const out = new NextResponse(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: responseHeaders,
  });
  if (isLocalDevelopment(req) && !hasValidSession(req)) {
    applySessionCookie(out);
  }
  return out;
}
