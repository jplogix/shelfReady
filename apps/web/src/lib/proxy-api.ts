import { NextRequest, NextResponse } from "next/server";

const API_ORIGIN = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

export async function proxyToApi(req: NextRequest, path: string): Promise<NextResponse> {
  const target = new URL(path, API_ORIGIN);
  target.search = req.nextUrl.search;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("connection");

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

  return new NextResponse(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: responseHeaders,
  });
}
